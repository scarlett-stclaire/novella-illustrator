import asyncio
import contextlib
import json
import os
import random
import time
import uuid
from pathlib import Path
from typing import Awaitable, Callable, Optional

import httpx
import websockets

from . import settings_store
from .engines import DEFAULT_ENGINE_ID, DEFAULT_NEGATIVE_PROMPT, ENGINES

COMFYUI_BASE_URL = os.environ.get("COMFYUI_BASE_URL", "http://localhost:8188")
COMFYUI_WS_URL = COMFYUI_BASE_URL.replace("http://", "ws://", 1).replace(
    "https://", "wss://", 1
)

# Appended when regenerating from user feedback (e.g. "hands look contorted").
# Some engines (e.g. FLUX.1-schnell) have no negative-prompt input, so
# correction has to be phrased as positive guidance baked into the prompt.
ANATOMY_FIX_HINT = os.environ.get(
    "ANATOMY_FIX_HINT",
    "correct anatomy, proper proportions, symmetrical limbs, correct hand and "
    "finger count, no distortion",
)

POLL_INTERVAL_SECONDS = 2
# Two-phase timeout: ComfyUI processes one job at a time, so queueing several
# scenes is normal and a job can sit waiting a long while before it starts -
# that deserves a generous allowance. Once it's actively sampling (first
# progress event), a stuck/hung job should still be caught reasonably fast.
QUEUE_WAIT_TIMEOUT_SECONDS = 3600
EXECUTION_TIMEOUT_SECONDS = 600

ProgressCallback = Callable[[int, int], Awaitable[None]]


def build_feedback_prompt(image_prompt: str, feedback: str) -> str:
    return f"{image_prompt}, {feedback.strip()}, {ANATOMY_FIX_HINT}"


async def _upload_reference_image(path: Path) -> str:
    """Uploads a character portrait to ComfyUI's /upload/image so a LoadImage
    node (used by IPAdapter-capable engines) can reference it by filename -
    ComfyUI's LoadImage only reads from its own managed input directory, not
    arbitrary filesystem paths. overwrite=true keeps re-generating with the
    same portrait from littering ComfyUI's input dir with "name (1).png"
    copies."""
    async with httpx.AsyncClient(timeout=30) as client:
        with path.open("rb") as f:
            response = await client.post(
                f"{COMFYUI_BASE_URL}/upload/image",
                files={"image": (path.name, f, "image/png")},
                data={"type": "input", "overwrite": "true"},
            )
        response.raise_for_status()
        return response.json()["name"]


async def _relay_progress(
    ws: websockets.WebSocketClientProtocol,
    prompt_id: str,
    on_progress: Optional[ProgressCallback],
    on_first_progress: Callable[[], None],
) -> None:
    """Forwards this prompt's `progress` (sampling step) events from ComfyUI's
    websocket to on_progress, and separately signals on_first_progress once
    (used to switch the caller's timeout from "waiting in queue" to "actively
    generating"). Best-effort: completion/results still come from polling
    /history, so any failure here just means no progress bar/early signal."""
    seen_progress = False
    try:
        async for raw in ws:
            if isinstance(raw, bytes):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            data = msg.get("data", {})
            if data.get("prompt_id") != prompt_id:
                continue
            if msg.get("type") == "progress":
                if not seen_progress:
                    seen_progress = True
                    on_first_progress()
                if on_progress is not None:
                    await on_progress(data.get("value", 0), data.get("max", 0))
    except websockets.WebSocketException:
        return


async def generate_image(
    prompt: str,
    output_path: Path,
    engine_id: str = DEFAULT_ENGINE_ID,
    negative: str = DEFAULT_NEGATIVE_PROMPT,
    reference_image_path: Optional[Path] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> None:
    engine = ENGINES[engine_id]
    reference_image_filename = None
    if engine.supports_reference_image:
        if reference_image_path is None:
            raise ValueError(f"engine {engine_id} requires a reference image")
        reference_image_filename = await _upload_reference_image(reference_image_path)
    workflow = engine.build_workflow(
        prompt, negative, random.randint(0, 2**32 - 1), reference_image_filename
    )
    client_id = str(uuid.uuid4())

    # Connect before queuing so we can't miss early progress events.
    ws = None
    with contextlib.suppress(OSError, websockets.WebSocketException):
        ws = await websockets.connect(
            f"{COMFYUI_WS_URL}/ws?clientId={client_id}", max_size=None
        )

    deadline = time.monotonic() + QUEUE_WAIT_TIMEOUT_SECONDS

    def on_first_progress() -> None:
        nonlocal deadline
        deadline = time.monotonic() + EXECUTION_TIMEOUT_SECONDS

    progress_task = None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            queue_response = await client.post(
                f"{COMFYUI_BASE_URL}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            queue_response.raise_for_status()
            prompt_id = queue_response.json()["prompt_id"]

            if ws is not None:
                progress_task = asyncio.create_task(
                    _relay_progress(ws, prompt_id, on_progress, on_first_progress)
                )

            while time.monotonic() < deadline:
                history_response = await client.get(
                    f"{COMFYUI_BASE_URL}/history/{prompt_id}"
                )
                history_response.raise_for_status()
                history = history_response.json()

                if prompt_id in history:
                    outputs = history[prompt_id]["outputs"]
                    image_info = outputs[engine.output_node]["images"][0]
                    image_response = await client.get(
                        f"{COMFYUI_BASE_URL}/view",
                        params={
                            "filename": image_info["filename"],
                            "subfolder": image_info.get("subfolder", ""),
                            "type": image_info.get("type", "output"),
                        },
                    )
                    image_response.raise_for_status()
                    output_path.write_bytes(image_response.content)
                    return

                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        raise TimeoutError(f"ComfyUI generation timed out for prompt_id={prompt_id}")
    finally:
        if progress_task is not None:
            progress_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await progress_task
        if ws is not None:
            await ws.close()


async def check_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{COMFYUI_BASE_URL}/system_stats")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


async def _engine_availability() -> list[dict]:
    """Reports every registered engine plus whether its model files are
    actually present (visible to ComfyUI), regardless of the user's F2
    enabled-selection - the raw, unfiltered truth that both list_engines()
    and the Settings screen's model-selection list are built from."""
    results = []
    async with httpx.AsyncClient(timeout=10) as client:
        for engine in ENGINES.values():
            node_type, field_name, filename = engine.availability_check
            available = False
            with contextlib.suppress(httpx.HTTPError, KeyError, IndexError):
                response = await client.get(
                    f"{COMFYUI_BASE_URL}/object_info/{node_type}"
                )
                response.raise_for_status()
                options = response.json()[node_type]["input"]["required"][
                    field_name
                ][0]
                available = filename in options
            results.append(
                {"id": engine.id, "label": engine.label, "available": available}
            )
    return results


async def list_engines() -> list[dict]:
    """Engines offered for actual generation: available (model files present)
    AND, per F2 ("only selected models appear in the app"), not deselected
    by the user in Settings. enabled_engine_ids is None by default (every
    available engine enabled), so existing installs aren't left with none."""
    enabled_ids = settings_store.get_enabled_engine_ids()
    return [
        e
        for e in await _engine_availability()
        if enabled_ids is None or e["id"] in enabled_ids
    ]


async def list_engines_for_settings() -> list[dict]:
    """Every registered engine with both its availability (file presence)
    and whether the user currently has it enabled - the Settings screen
    needs to show and toggle disabled engines too, not just hide them."""
    enabled_ids = settings_store.get_enabled_engine_ids()
    return [
        {**e, "enabled": enabled_ids is None or e["id"] in enabled_ids}
        for e in await _engine_availability()
    ]
