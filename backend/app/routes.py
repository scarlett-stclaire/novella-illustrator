import asyncio
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from . import catalogue, characters_llm, export, ingest, llm, imagegen, providers, recommend, settings_store, storage
from .models import (
    AddCharacterRequest,
    AddSceneRequest,
    Character,
    CreateNovellaRequest,
    IngestUrlsRequest,
    Novella,
    NovellaSummary,
    Progress,
    RegenerateSceneRequest,
    SaveApiKeyRequest,
    Scene,
    SetDefaultProviderRequest,
    SetEnabledEnginesRequest,
    SetOllamaModelRequest,
    SetStorageRootRequest,
    SplitSceneRequest,
    UpdateCharacterRequest,
    UpdateScenePromptRequest,
)

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    ollama_ok = await llm.check_health()
    comfyui_ok = await imagegen.check_health()
    return {"ollama": ollama_ok, "comfyui": comfyui_ok}


@router.get("/engines")
async def get_engines():
    return await imagegen.list_engines()


@router.get("/settings/providers")
async def get_text_providers():
    return {
        "providers": await providers.list_providers(),
        "default_provider_id": providers.resolve_default_provider().id,
    }


@router.get("/settings/ollama-models")
async def get_ollama_models():
    return await providers.list_ollama_models()


@router.post("/settings/ollama-model")
async def set_ollama_model(payload: SetOllamaModelRequest):
    settings_store.set_ollama_model(payload.model or None)
    return {"ok": True}


@router.post("/settings/providers/{provider_id}/key")
async def save_provider_key(provider_id: str, payload: SaveApiKeyRequest):
    meta = providers.PROVIDER_REGISTRY.get(provider_id)
    if meta is None or not meta.requires_api_key:
        raise HTTPException(status_code=404, detail="Unknown provider")

    ok, message = await providers.validate_key(provider_id, payload.api_key)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Key validation failed: {message}")

    settings_store.set_key(provider_id, payload.api_key)
    return {"ok": True}


@router.delete("/settings/providers/{provider_id}/key")
async def delete_provider_key(provider_id: str):
    settings_store.delete_key(provider_id)
    return {"ok": True}


@router.post("/settings/default-provider")
async def set_default_provider(payload: SetDefaultProviderRequest):
    if payload.provider_id is not None and payload.provider_id not in providers.PROVIDER_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown provider")
    settings_store.set_default_text_provider(payload.provider_id)
    return {"ok": True}


@router.get("/settings/catalogue")
async def get_catalogue():
    return {"models": await catalogue.list_models()}


@router.get("/settings/engines")
async def get_settings_engines():
    """F2: every registered image engine with both its availability (model
    files present) and whether the user has it enabled - unlike GET
    /api/engines, this never filters anything out, so disabled engines can
    still be shown (and re-enabled) here."""
    return {"engines": await imagegen.list_engines_for_settings()}


@router.post("/settings/engines")
async def set_settings_engines(payload: SetEnabledEnginesRequest):
    settings_store.set_enabled_engine_ids(payload.engine_ids)
    return {"ok": True}


@router.get("/settings/storage")
async def get_settings_storage():
    """F3: reports the effective storage root in use by this running backend
    process, alongside whatever override is saved (which may differ if it
    was changed since the last restart - storage.py reads it only once, at
    import time)."""
    return {
        "active_root": str(storage.DATA_DIR),
        "saved_override": settings_store.get_storage_root(),
    }


@router.post("/settings/storage")
async def set_settings_storage(payload: SetStorageRootRequest):
    if payload.path:
        path = Path(payload.path).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(
                status_code=400, detail=f"Can't create or write to that path: {exc}"
            )
        settings_store.set_storage_root(str(path))
    else:
        settings_store.set_storage_root(None)
    return {"ok": True, "restart_required": True}


@router.post("/ingest/pdf")
async def ingest_pdf(file: UploadFile = File(...)):
    file_bytes = await file.read()
    try:
        text = ingest.extract_pdf_text(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"text": text}


@router.post("/ingest/urls")
async def ingest_urls(payload: IngestUrlsRequest):
    try:
        text, results = await ingest.extract_urls_text(payload.urls)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"text": text, "results": results}


@router.post("/novellas", response_model=Novella)
async def create_novella(payload: CreateNovellaRequest):
    available = await recommend.get_available_engines()
    comparison = recommend.compare_for_text(payload.text, available)

    novella = Novella(
        id=str(uuid.uuid4()),
        title=payload.title,
        text=payload.text,
        target_scene_count=payload.target_scene_count,
        scene_type=comparison["scene_type"],
        complexity=comparison["complexity"],
        recommended_engine_id=comparison["recommended_engine_id"],
    )
    storage.save_novella(novella)
    return novella


EXPORT_FORMATS = {
    "pdf": export.export_pdf,
    "web": export.export_animated_web,
    "epub": export.export_epub,
    "png": export.export_png_set,
    "mov": export.export_mov,
}
EXPORT_EXTENSIONS = {"pdf": ".pdf", "web": ".html", "epub": ".epub", "png": ".zip", "mov": ".mov"}


def _safe_filename(title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", title.strip()).strip("_")
    return cleaned or "novella"


@router.post("/novellas/{novella_id}/export")
async def export_novella(novella_id: str, format: str):
    if format not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown format '{format}'. Choose one of {sorted(EXPORT_FORMATS)}",
        )
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    export_dir = storage.novella_export_dir(novella_id)
    filename = f"{_safe_filename(novella.title)}{EXPORT_EXTENSIONS[format]}"
    output_path = export_dir / filename
    try:
        EXPORT_FORMATS[format](novella, storage.DATA_DIR, output_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "filename": filename,
        "download_url": f"/api/exports/{novella_id}/{filename}",
    }


@router.get("/novellas/{novella_id}/exports")
async def list_exports(novella_id: str):
    export_dir = storage.novella_export_dir(novella_id)
    files = [
        {
            "filename": path.name,
            "download_url": f"/api/exports/{novella_id}/{path.name}",
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(export_dir.iterdir())
        if path.is_file()
    ]
    return {"files": files}


@router.get("/novellas/{novella_id}/cost-perf")
async def get_novella_cost_perf(novella_id: str):
    """Story-level engine comparison (F9/F18) - shown before/alongside
    chunking. Recomputed live so it reflects currently-available engines,
    rather than trusting the snapshot taken at creation time."""
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")
    available = await recommend.get_available_engines()
    return recommend.compare_for_text(novella.text, available)


@router.get("/novellas", response_model=list[NovellaSummary])
async def get_novellas():
    novellas = sorted(
        storage.list_novellas(), key=lambda n: n.created_at, reverse=True
    )
    return [
        NovellaSummary(
            id=n.id,
            title=n.title,
            scene_count=len(n.scenes),
            status=n.status,
            generating_count=sum(1 for s in n.scenes if s.status == "generating"),
            created_at=n.created_at,
        )
        for n in novellas
    ]


@router.get("/novellas/{novella_id}", response_model=Novella)
async def get_novella(novella_id: str):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")
    return novella


@router.post("/novellas/{novella_id}/breakdown", response_model=Novella)
async def breakdown_novella(
    novella_id: str,
    text_provider_id: Optional[str] = None,
    ollama_model: Optional[str] = None,
):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    if text_provider_id is not None and text_provider_id not in providers.PROVIDER_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown text provider")

    novella = storage.update_novella(
        novella_id,
        scenes=[],
        status="breaking_down",
        breakdown_progress=None,
        breakdown_error=None,
        text_provider_id=text_provider_id,
    )

    asyncio.create_task(
        _run_breakdown(
            novella_id,
            novella.text,
            novella.target_scene_count,
            text_provider_id,
            ollama_model,
        )
    )

    return novella


async def _run_breakdown(
    novella_id: str,
    text: str,
    target_scene_count: int | None,
    text_provider_id: Optional[str] = None,
    ollama_model: Optional[str] = None,
) -> None:
    # Fetched once for the whole breakdown run rather than per-scene - engine
    # availability won't change mid-run, and this avoids hammering ComfyUI's
    # /object_info endpoint once per scene.
    available_engines = await recommend.get_available_engines()

    async def on_chunk_done(value: int, max_value: int, new_items: list[dict]) -> None:
        current = storage.load_novella(novella_id)
        if current is None:
            return
        start_index = len(current.scenes)
        new_scenes = []
        for i, item in enumerate(new_items):
            comparison = recommend.compare_for_text(
                item["image_prompt"], available_engines
            )
            new_scenes.append(
                Scene(
                    id=str(uuid.uuid4()),
                    index=start_index + i,
                    summary=item["summary"],
                    image_prompt=item["image_prompt"],
                    source_excerpt=item.get("source_excerpt") or None,
                    scene_type=comparison["scene_type"],
                    complexity=comparison["complexity"],
                    recommended_engine_id=comparison["recommended_engine_id"],
                )
            )
        storage.update_novella(
            novella_id,
            scenes=current.scenes + new_scenes,
            breakdown_progress=Progress(value=value, max=max_value),
        )

    try:
        provider = (
            providers.get_provider(text_provider_id, ollama_model=ollama_model)
            if text_provider_id
            else providers.resolve_default_provider()
        )
        await llm.breakdown_into_scenes(
            text,
            target_scene_count=target_scene_count,
            on_chunk_done=on_chunk_done,
            provider=provider,
        )
        storage.update_novella(novella_id, status="ready", breakdown_progress=None)
    except Exception as exc:  # noqa: BLE001
        storage.update_novella(
            novella_id, status="error", breakdown_error=str(exc), breakdown_progress=None
        )


@router.post("/novellas/{novella_id}/characters/extract", response_model=Novella)
async def extract_characters(novella_id: str, text_provider_id: Optional[str] = None):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    if text_provider_id is not None and text_provider_id not in providers.PROVIDER_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown text provider")

    novella = storage.update_novella(
        novella_id, character_status="extracting", character_error=None
    )
    asyncio.create_task(
        _run_character_extraction(novella_id, novella.text, text_provider_id)
    )
    return novella


async def _run_character_extraction(
    novella_id: str, text: str, text_provider_id: Optional[str]
) -> None:
    try:
        provider = (
            providers.get_provider(text_provider_id)
            if text_provider_id
            else providers.resolve_default_provider()
        )
        raw_characters = await characters_llm.extract_characters(text, provider)

        current = storage.load_novella(novella_id)
        if current is None:
            return
        existing_by_name = {c.name.lower(): c for c in current.characters}

        merged: list[Character] = []
        for item in raw_characters:
            key = item["name"].lower()
            if key in existing_by_name:
                # Already extracted (or added by hand) - keep the existing
                # record untouched so any image/edits the user made survive
                # a re-extraction.
                merged.append(existing_by_name[key])
            else:
                merged.append(Character(id=str(uuid.uuid4()), **item))

        storage.update_novella(
            novella_id, characters=merged, character_status="ready"
        )
    except Exception as exc:  # noqa: BLE001
        storage.update_novella(
            novella_id, character_status="error", character_error=str(exc)
        )


@router.post("/novellas/{novella_id}/characters", response_model=Novella)
async def add_character(novella_id: str, payload: AddCharacterRequest):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    new_character = Character(
        id=str(uuid.uuid4()),
        name=payload.name,
        synopsis=payload.synopsis,
        visual_description=payload.visual_description,
        manual=True,
    )
    return storage.update_novella(
        novella_id, characters=novella.characters + [new_character]
    )


@router.patch("/novellas/{novella_id}/characters/{character_id}", response_model=Novella)
async def update_character(
    novella_id: str, character_id: str, payload: UpdateCharacterRequest
):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = storage.update_character(novella_id, character_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Character not found")
    return updated


@router.delete("/novellas/{novella_id}/characters/{character_id}", response_model=Novella)
async def delete_character(novella_id: str, character_id: str):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    characters = [c for c in novella.characters if c.id != character_id]
    if len(characters) == len(novella.characters):
        raise HTTPException(status_code=404, detail="Character not found")

    return storage.update_novella(novella_id, characters=characters)


@router.post(
    "/novellas/{novella_id}/characters/{character_id}/image/upload",
    response_model=Novella,
)
async def upload_character_image(
    novella_id: str, character_id: str, file: UploadFile = File(...)
):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")
    if not any(c.id == character_id for c in novella.characters):
        raise HTTPException(status_code=404, detail="Character not found")

    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=422, detail="File must be an image")

    ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(
        file.content_type, ".png"
    )
    image_dir = storage.novella_image_dir(novella_id)
    output_path = image_dir / f"character_{character_id}{ext}"
    output_path.write_bytes(await file.read())

    updated = storage.update_character(
        novella_id,
        character_id,
        image_path=f"/api/images/{novella_id}/character_{character_id}{ext}",
        status="ready",
        error=None,
        engine_id=None,
    )
    return updated


@router.post(
    "/novellas/{novella_id}/characters/{character_id}/image/generate",
    response_model=Novella,
)
async def generate_character_image(
    novella_id: str, character_id: str, engine_id: Optional[str] = None
):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    character = next((c for c in novella.characters if c.id == character_id), None)
    if character is None:
        raise HTTPException(status_code=404, detail="Character not found")

    details = character.visual_description or character.synopsis
    prompt = (
        f"Character portrait of {character.name}: {details}, "
        f"plain neutral background, {llm.STYLE_HINT}"
    )
    effective_engine_id = (
        engine_id or novella.recommended_engine_id or imagegen.DEFAULT_ENGINE_ID
    )

    updated = storage.update_character(
        novella_id, character_id, status="generating", error=None, progress=None
    )
    asyncio.create_task(
        _run_character_generation(novella_id, character_id, prompt, effective_engine_id)
    )
    return updated


async def _run_character_generation(
    novella_id: str, character_id: str, prompt: str, engine_id: str
) -> None:
    image_dir = storage.novella_image_dir(novella_id)
    output_path = image_dir / f"character_{character_id}.png"

    async def on_progress(value: int, max_value: int) -> None:
        storage.update_character(
            novella_id, character_id, progress=Progress(value=value, max=max_value)
        )

    try:
        await imagegen.generate_image(
            prompt, output_path, engine_id=engine_id, on_progress=on_progress
        )
        storage.update_character(
            novella_id,
            character_id,
            status="ready",
            image_path=f"/api/images/{novella_id}/character_{character_id}.png",
            progress=None,
            engine_id=engine_id,
        )
    except Exception as exc:  # noqa: BLE001
        storage.update_character(
            novella_id, character_id, status="error", error=str(exc), progress=None
        )


@router.post("/novellas/{novella_id}/characters/apply-to-scenes", response_model=Novella)
async def apply_characters_to_scenes(novella_id: str):
    """Locks each character's visual_description into the prompt of every
    scene that mentions them by name (F14, practical v1 - see note below).

    This is a text-prompt consistency aid, not true image-conditioning: it
    keeps hair/costume/build details worded the same way across scenes so
    the model is nudged toward a consistent look, but it cannot guarantee
    pixel-level facial consistency the way an IPAdapter/reference-image
    pipeline would. That's flagged in the implementation plan as a separate,
    larger piece of work (new ComfyUI custom node + CLIP vision + per-engine
    IPAdapter weights - a real download/disk-space commitment), not
    attempted here.
    """
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    locked_characters = [c for c in novella.characters if c.visual_description]
    if not locked_characters:
        return novella

    updated_scenes = []
    for scene in novella.scenes:
        haystack = (
            f"{scene.summary} {scene.image_prompt} {scene.source_excerpt or ''}"
        ).lower()
        present = [c for c in locked_characters if c.name.lower() in haystack]
        if present:
            lock_text = "; ".join(
                f"{c.name}: {c.visual_description}" for c in present
            )
            if lock_text not in scene.image_prompt:
                scene.image_prompt = f"{scene.image_prompt}, {lock_text}"
        updated_scenes.append(scene)

    return storage.update_novella(novella_id, scenes=updated_scenes)


@router.post("/novellas/{novella_id}/scenes", response_model=Novella)
async def add_scene(novella_id: str, payload: AddSceneRequest):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    if payload.after_scene_id is not None and not any(
        s.id == payload.after_scene_id for s in novella.scenes
    ):
        raise HTTPException(status_code=404, detail="after_scene_id not found")

    new_scene = Scene(
        id=str(uuid.uuid4()),
        index=0,
        summary=payload.summary,
        image_prompt=payload.image_prompt,
        manual=True,
    )

    scenes = list(novella.scenes)
    if payload.after_scene_id is None:
        scenes.insert(0, new_scene)
    else:
        insert_at = next(
            i for i, s in enumerate(scenes) if s.id == payload.after_scene_id
        )
        scenes.insert(insert_at + 1, new_scene)

    for i, scene in enumerate(scenes):
        scene.index = i

    return storage.update_novella(novella_id, scenes=scenes)


@router.delete("/novellas/{novella_id}/scenes/{scene_id}", response_model=Novella)
async def delete_scene(novella_id: str, scene_id: str):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    scenes = [s for s in novella.scenes if s.id != scene_id]
    if len(scenes) == len(novella.scenes):
        raise HTTPException(status_code=404, detail="Scene not found")

    for i, scene in enumerate(scenes):
        scene.index = i

    return storage.update_novella(novella_id, scenes=scenes)


@router.patch("/novellas/{novella_id}/scenes/{scene_id}", response_model=Novella)
async def update_scene_prompt(
    novella_id: str, scene_id: str, payload: UpdateScenePromptRequest
):
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = storage.update_scene(novella_id, scene_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Novella or scene not found")
    return updated


@router.post("/novellas/{novella_id}/scenes/{scene_id}/move", response_model=Novella)
async def move_scene(novella_id: str, scene_id: str, direction: str):
    """Reorders one scene by one position (F11/F25 "reorder")."""
    if direction not in ("up", "down"):
        raise HTTPException(status_code=422, detail="direction must be 'up' or 'down'")

    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    scenes = list(novella.scenes)
    pos = next((i for i, s in enumerate(scenes) if s.id == scene_id), None)
    if pos is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    target = pos - 1 if direction == "up" else pos + 1
    if target < 0 or target >= len(scenes):
        return novella  # already at the edge - no-op, not an error

    scenes[pos], scenes[target] = scenes[target], scenes[pos]
    for i, scene in enumerate(scenes):
        scene.index = i

    return storage.update_novella(novella_id, scenes=scenes)


@router.post(
    "/novellas/{novella_id}/scenes/{scene_id}/merge-next", response_model=Novella
)
async def merge_scene_with_next(novella_id: str, scene_id: str):
    """Merges a scene with the one immediately after it (F11/F25 "merge").
    The combined chunk keeps the first scene's id/image/engine and absorbs
    the second scene's text; the second scene is removed."""
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    scenes = list(novella.scenes)
    pos = next((i for i, s in enumerate(scenes) if s.id == scene_id), None)
    if pos is None:
        raise HTTPException(status_code=404, detail="Scene not found")
    if pos + 1 >= len(scenes):
        raise HTTPException(status_code=400, detail="No next scene to merge with")

    first, second = scenes[pos], scenes[pos + 1]
    first.summary = f"{first.summary} {second.summary}".strip()
    first.image_prompt = f"{first.image_prompt}, {second.image_prompt}".strip(", ")
    if first.source_excerpt and second.source_excerpt:
        first.source_excerpt = f"{first.source_excerpt} {second.source_excerpt}"
    scenes = [s for s in scenes if s.id != second.id]
    for i, scene in enumerate(scenes):
        scene.index = i

    return storage.update_novella(novella_id, scenes=scenes)


@router.post("/novellas/{novella_id}/scenes/{scene_id}/split", response_model=Novella)
async def split_scene(novella_id: str, scene_id: str, payload: SplitSceneRequest):
    """Replaces one scene with two, at the same position (F11/F25 "split")."""
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    scenes = list(novella.scenes)
    pos = next((i for i, s in enumerate(scenes) if s.id == scene_id), None)
    if pos is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    original = scenes[pos]
    available = await recommend.get_available_engines()
    comparison_a = recommend.compare_for_text(payload.image_prompt_a, available)
    comparison_b = recommend.compare_for_text(payload.image_prompt_b, available)

    scene_a = Scene(
        id=str(uuid.uuid4()),
        index=0,
        summary=payload.summary_a,
        image_prompt=payload.image_prompt_a,
        source_excerpt=original.source_excerpt,
        manual=True,
        scene_type=comparison_a["scene_type"],
        complexity=comparison_a["complexity"],
        recommended_engine_id=comparison_a["recommended_engine_id"],
    )
    scene_b = Scene(
        id=str(uuid.uuid4()),
        index=0,
        summary=payload.summary_b,
        image_prompt=payload.image_prompt_b,
        source_excerpt=original.source_excerpt,
        manual=True,
        scene_type=comparison_b["scene_type"],
        complexity=comparison_b["complexity"],
        recommended_engine_id=comparison_b["recommended_engine_id"],
    )
    scenes[pos : pos + 1] = [scene_a, scene_b]
    for i, scene in enumerate(scenes):
        scene.index = i

    return storage.update_novella(novella_id, scenes=scenes)


@router.get("/novellas/{novella_id}/scenes/{scene_id}/recommend")
async def recommend_scene_engine(
    novella_id: str, scene_id: str, feedback: Optional[str] = None
):
    """Engine comparison for a single scene (F17/F18) - feedback-driven when
    `feedback` is given (e.g. "hands look contorted" -> SDXL + ADetailer),
    otherwise based on the scene's own image prompt."""
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    scene = next((s for s in novella.scenes if s.id == scene_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    available = await recommend.get_available_engines()
    if feedback and feedback.strip():
        return recommend.compare_for_feedback(feedback, available)
    return recommend.compare_for_text(scene.image_prompt, available)


def _character_reference_image_path(
    novella: Novella, character_id: str
) -> Path:
    """Resolves a character's stored portrait URL (/api/images/{novella_id}/...)
    back to the actual file on disk, for feeding into an IPAdapter-capable
    engine as its reference image."""
    character = next((c for c in novella.characters if c.id == character_id), None)
    if character is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if not character.image_path:
        raise HTTPException(
            status_code=400, detail="Character has no portrait to use as a reference"
        )
    return storage.IMAGES_DIR / character.image_path.removeprefix("/api/images/")


@router.post("/novellas/{novella_id}/scenes/{scene_id}/generate", response_model=Novella)
async def generate_scene_image(
    novella_id: str,
    scene_id: str,
    engine_id: Optional[str] = None,
    character_id: Optional[str] = None,
):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    scene = next((s for s in novella.scenes if s.id == scene_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    effective_engine_id = (
        engine_id or scene.recommended_engine_id or imagegen.DEFAULT_ENGINE_ID
    )
    # character_id is an R&D spike for F14 true character-consistent
    # generation (IPAdapter) - only "sdxl_adetailer_ipadapter" has the
    # LoadImage/IPAdapter nodes to use it; other engines ignore it.
    reference_image_path = (
        _character_reference_image_path(novella, character_id)
        if character_id
        else None
    )

    novella = storage.update_scene(
        novella_id, scene_id, status="generating", error=None, progress=None
    )

    asyncio.create_task(
        _run_generation(
            novella_id,
            scene_id,
            scene.image_prompt,
            effective_engine_id,
            reference_image_path,
        )
    )

    return novella


@router.post(
    "/novellas/{novella_id}/scenes/{scene_id}/regenerate", response_model=Novella
)
async def regenerate_scene_image(
    novella_id: str, scene_id: str, payload: RegenerateSceneRequest
):
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    scene = next((s for s in novella.scenes if s.id == scene_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    final_prompt = imagegen.build_feedback_prompt(scene.image_prompt, payload.feedback)

    effective_engine_id = payload.engine_id
    if not effective_engine_id:
        # F17: no engine chosen explicitly - let the feedback text pick one.
        available = await recommend.get_available_engines()
        feedback_recommendation = recommend.compare_for_feedback(
            payload.feedback, available
        )
        effective_engine_id = (
            feedback_recommendation["recommended_engine_id"]
            or scene.recommended_engine_id
            or imagegen.DEFAULT_ENGINE_ID
        )

    novella = storage.update_scene(
        novella_id,
        scene_id,
        status="generating",
        error=None,
        progress=None,
        feedback=payload.feedback,
    )

    asyncio.create_task(
        _run_generation(novella_id, scene_id, final_prompt, effective_engine_id)
    )

    return novella


async def _run_generation(
    novella_id: str,
    scene_id: str,
    image_prompt: str,
    engine_id: str,
    reference_image_path: Optional[Path] = None,
) -> None:
    image_dir = storage.novella_image_dir(novella_id)
    output_path = image_dir / f"{scene_id}.png"

    async def on_progress(value: int, max_value: int) -> None:
        storage.update_scene(
            novella_id, scene_id, progress=Progress(value=value, max=max_value)
        )

    try:
        await imagegen.generate_image(
            image_prompt,
            output_path,
            engine_id=engine_id,
            reference_image_path=reference_image_path,
            on_progress=on_progress,
        )
        storage.update_scene(
            novella_id,
            scene_id,
            status="done",
            image_path=f"/api/images/{novella_id}/{scene_id}.png",
            progress=None,
            engine_id=engine_id,
        )
    except Exception as exc:  # noqa: BLE001
        storage.update_scene(
            novella_id, scene_id, status="error", error=str(exc), progress=None
        )
