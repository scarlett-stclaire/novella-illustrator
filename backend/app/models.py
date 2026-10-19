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


class Novella(BaseModel):
    id: str
    title: str
    text: str
    scenes: list[Scene] = []
    status: str = "draft"  # draft | breaking_down | ready | error
    breakdown_progress: Optional[Progress] = None
    breakdown_error: Optional[str] = None
    target_scene_count: Optional[int] = None
    text_provider_id: Optional[str] = None  # which text provider ran the breakdown
    scene_type: Optional[str] = None  # story-level heuristic classification (F9)
    complexity: Optional[str] = None  # story-level heuristic classification (F9)
    recommended_engine_id: Optional[str] = None  # story-level best-fit engine
    created_at: float = Field(default_factory=time.time)


class CreateNovellaRequest(BaseModel):
    title: str
    text: str
    target_scene_count: Optional[int] = None


class SaveApiKeyRequest(BaseModel):
    api_key: str


class SetDefaultProviderRequest(BaseModel):
    provider_id: Optional[str] = None


class UpdateScenePromptRequest(BaseModel):
    image_prompt: str


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
