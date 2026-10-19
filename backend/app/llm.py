import json
import os
import re
from typing import Awaitable, Callable, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError

from . import providers
from .providers import TextProvider


class SceneChunk(BaseModel):
    summary: str
    image_prompt: str = Field(
        description=(
            "Vivid, highly-descriptive visual/cinematic prompt (setting, "
            "characters, action, mood, lighting) for a diffusion model"
        )
    )
    source_excerpt: str = Field(
        description="Exact verbatim substring of the input text where this scene occurs"
    )


class SceneBreakdown(BaseModel):
    scenes: list[SceneChunk]

OLLAMA_BASE_URL = providers.OLLAMA_BASE_URL
OLLAMA_MODEL = providers.OLLAMA_MODEL

STYLE_HINT = os.environ.get(
    "ILLUSTRATION_STYLE_HINT",
    "gothic ink-and-paper comic illustration, one dramatic light source "
    "casting deep ink-black shadows, high contrast between black ink and "
    "pale bone-white highlights, muted palette of black ink, bone white and "
    "a single rose-pink accent color, flat printed shading with "
    "crosshatching and halftone dots rather than airbrushed gradients, "
    "strong graphic silhouettes, vignette falling to black at the panel "
    "edges, moody gothic atmosphere",
)

CHUNK_CHAR_LIMIT = 6000

SYSTEM_PROMPT = """You are a visual adaptation scriptwriter. You read story text \
and break it into a sequence of illustratable scenes/panels.

For the given passage, output a JSON object with a "scenes" array. Each element \
must be an object with:
- "summary": a one or two sentence description of what happens in the scene.
- "image_prompt": a single, highly descriptive, visual prompt suitable for feeding \
directly into an image generation model. Describe setting, characters, action, \
mood and lighting. Do not mention that it is a prompt, do not add preamble.
- "source_excerpt": a short VERBATIM quote (5-15 words, copied exactly character \
for character, no paraphrasing) from the passage that this scene is drawn from. \
It must be an exact substring of the passage - used later to locate the scene in \
the original text.

Return ONLY the JSON object, with no markdown fences and no extra commentary."""


def _chunk_text(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) > CHUNK_CHAR_LIMIT:
            chunks.append(current.strip())
            current = ""
        current += para + "\n\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text]


def _extract_json_array(raw: str) -> list:
    """Best-effort fallback parser, used when a provider doesn't enforce the
    SceneBreakdown/CharacterList schema (frontier providers today) and its
    response doesn't validate cleanly against it."""
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            # Expected shape ({"scenes": [...]} / {"characters": [...]}) -
            # unwrap the one list-valued key rather than guessing its name.
            list_values = [v for v in parsed.values() if isinstance(v, list)]
            if len(list_values) == 1:
                return list_values[0]
            # Not that shape either - a single-item response sometimes comes
            # back as one bare object instead of a one-element array.
            return [parsed]
    except json.JSONDecodeError:
        pass

    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array found in LLM response: {raw[:200]}")
    return json.loads(raw[start : end + 1])


def _parse_structured(content: str, schema: type[BaseModel], list_field: str) -> list[dict]:
    """Validates `content` against `schema` (the strong path - holds for
    Ollama, which actually enforces the schema) and returns the list field
    as plain dicts. Falls back to the loose extractor for providers that
    don't enforce schemas and returned something that doesn't quite match."""
    try:
        validated = schema.model_validate_json(content)
        return [item.model_dump() for item in getattr(validated, list_field)]
    except ValidationError:
        return _extract_json_array(content)


async def breakdown_into_scenes(
    text: str,
    target_scene_count: Optional[int] = None,
    on_chunk_done: Optional[Callable[[int, int, list[dict]], Awaitable[None]]] = None,
    provider: Optional[TextProvider] = None,
) -> list[dict]:
    provider = provider or providers.resolve_default_provider()
    chunks = _chunk_text(text)
    total = len(chunks)
    scenes: list[dict] = []

    per_chunk_target = None
    if target_scene_count and target_scene_count > 0:
        per_chunk_target = max(1, round(target_scene_count / total))

    for i, chunk in enumerate(chunks):
        user_content = chunk
        if per_chunk_target is not None:
            plural = "s" if per_chunk_target != 1 else ""
            user_content = (
                f"(Extract approximately {per_chunk_target} scene{plural} "
                f"from the passage below.)\n\n{chunk}"
            )

        content = await provider.chat(
            SYSTEM_PROMPT, user_content, json_mode=True, response_schema=SceneBreakdown
        )

        parsed = _parse_structured(content, SceneBreakdown, "scenes")
        new_scenes = [
            {
                "summary": item.get("summary", ""),
                "image_prompt": f"{item.get('image_prompt', '')}, {STYLE_HINT}",
                "source_excerpt": item.get("source_excerpt", ""),
            }
            for item in parsed
        ]
        scenes.extend(new_scenes)
        if on_chunk_done is not None:
            await on_chunk_done(i + 1, total, new_scenes)

    return scenes


async def check_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return response.status_code == 200
    except httpx.HTTPError:
        return False
