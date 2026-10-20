import time
from typing import Optional
from pydantic import BaseModel, Field


class Progress(BaseModel):
    value: int
    max: int


class Scene(BaseModel):
    id: str
    index: int
    summary: str
    image_prompt: str
    image_path: Optional[str] = None
    status: str = "pending"  # pending | generating | done | error
    error: Optional[str] = None
    progress: Optional[Progress] = None
    source_excerpt: Optional[str] = None
    manual: bool = False  # True for scenes added by hand, not by the LLM
    feedback: Optional[str] = None  # correction notes from the last regenerate
    engine_id: Optional[str] = None  # which image-gen engine made the current image
    scene_type: Optional[str] = None  # heuristic classification (F9/F18)
    complexity: Optional[str] = None  # heuristic classification (F9/F18)
    recommended_engine_id: Optional[str] = None  # best-fit engine per capability profile


class Character(BaseModel):
    id: str
    name: str
    aliases: list[str] = []  # other name variants merged into this character
    # (e.g. "Bill"/"Mr. Bennett" merged under "Bill Bennett") - see
    # entity_resolution.py. `name` is always the longest raw variant seen.
    synopsis: str = ""  # narrative role, shown in the character list (F12)
    visual_description: str = ""  # physical/costume details only - locked into
    # scene prompts for appearance consistency (F14); kept separate from
    # synopsis so plot/personality text never leaks into an image prompt
    image_path: Optional[str] = None
    source_excerpts: list[str] = []
    manual: bool = False  # True for characters added by hand, not by the LLM
    status: str = "ready"  # ready | generating | error (image generation)
    error: Optional[str] = None
    progress: Optional[Progress] = None
    engine_id: Optional[str] = None  # which image-gen engine made the current image


class Novella(BaseModel):
    id: str
    title: str
    text: str
    scenes: list[Scene] = []
    status: str = "draft"  # draft | breaking_down | ready | error
    breakdown_progress: Optional[Progress] = None
    # Live-streamed raw model output for the chunk currently being processed
    # (Ollama only - see providers.py's on_token) - so a long single-chunk
    # wait shows real activity, not just an elapsed-time guess.
    breakdown_live_text: Optional[str] = None
    breakdown_error: Optional[str] = None
    target_scene_count: Optional[int] = None
    text_provider_id: Optional[str] = None  # which text provider ran the breakdown
    scene_type: Optional[str] = None  # story-level heuristic classification (F9)
    complexity: Optional[str] = None  # story-level heuristic classification (F9)
    recommended_engine_id: Optional[str] = None  # story-level best-fit engine
    characters: list[Character] = []
    character_status: str = "none"  # none | extracting | ready | error
    character_error: Optional[str] = None
    created_at: float = Field(default_factory=time.time)


class CreateNovellaRequest(BaseModel):
    title: str
    text: str
    target_scene_count: Optional[int] = None


class SaveApiKeyRequest(BaseModel):
    api_key: str


class SetDefaultProviderRequest(BaseModel):
    provider_id: Optional[str] = None


class SetEnabledEnginesRequest(BaseModel):
    # None = every available engine enabled (the default); [] disables all.
    engine_ids: Optional[list[str]] = None


class SetStorageRootRequest(BaseModel):
    # None/empty resets to the default backend/data location.
    path: Optional[str] = None


class SetOllamaModelRequest(BaseModel):
    # None/empty resets to OLLAMA_MODEL from .env.
    model: Optional[str] = None


class IngestUrlsRequest(BaseModel):
    urls: list[str]


class AddCharacterRequest(BaseModel):
    name: str
    synopsis: str = ""
    visual_description: str = ""


class UpdateCharacterRequest(BaseModel):
    name: Optional[str] = None
    synopsis: Optional[str] = None
    visual_description: Optional[str] = None


class UpdateScenePromptRequest(BaseModel):
    image_prompt: Optional[str] = None
    summary: Optional[str] = None  # the chunk's display label ("rename", F11/F25)


class SplitSceneRequest(BaseModel):
    summary_a: str
    image_prompt_a: str
    summary_b: str
    image_prompt_b: str


class AddSceneRequest(BaseModel):
    summary: str
    image_prompt: str
    after_scene_id: Optional[str] = None  # None = insert at the start


class RegenerateSceneRequest(BaseModel):
    feedback: str
    engine_id: Optional[str] = None


class NovellaSummary(BaseModel):
    id: str
    title: str
    scene_count: int
    status: str
    generating_count: int
    created_at: float
