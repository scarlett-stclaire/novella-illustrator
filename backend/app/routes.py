import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from . import catalogue, ingest, llm, imagegen, providers, recommend, settings_store, storage
from .models import (
    AddSceneRequest,
    CreateNovellaRequest,
    IngestUrlsRequest,
    Novella,
    NovellaSummary,
    Progress,
    RegenerateSceneRequest,
    SaveApiKeyRequest,
    Scene,
    SetDefaultProviderRequest,
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
async def breakdown_novella(novella_id: str, text_provider_id: Optional[str] = None):
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
            novella_id, novella.text, novella.target_scene_count, text_provider_id
        )
    )

    return novella


async def _run_breakdown(
    novella_id: str,
    text: str,
    target_scene_count: int | None,
    text_provider_id: Optional[str] = None,
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
            providers.get_provider(text_provider_id)
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
    novella = storage.load_novella(novella_id)
    if novella is None:
        raise HTTPException(status_code=404, detail="Novella not found")

    for scene in novella.scenes:
        if scene.id == scene_id:
            scene.image_prompt = payload.image_prompt
            storage.save_novella(novella)
            return novella

    raise HTTPException(status_code=404, detail="Scene not found")


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


@router.post("/novellas/{novella_id}/scenes/{scene_id}/generate", response_model=Novella)
async def generate_scene_image(
    novella_id: str, scene_id: str, engine_id: Optional[str] = None
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

    novella = storage.update_scene(
        novella_id, scene_id, status="generating", error=None, progress=None
    )

    asyncio.create_task(
        _run_generation(novella_id, scene_id, scene.image_prompt, effective_engine_id)
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
    novella_id: str, scene_id: str, image_prompt: str, engine_id: str
) -> None:
    image_dir = storage.novella_image_dir(novella_id)
    output_path = image_dir / f"{scene_id}.png"

    async def on_progress(value: int, max_value: int) -> None:
        storage.update_scene(
            novella_id, scene_id, progress=Progress(value=value, max=max_value)
        )

    try:
        await imagegen.generate_image(
            image_prompt, output_path, engine_id=engine_id, on_progress=on_progress
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
