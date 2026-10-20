"""Text-generation provider abstraction (spec SS8.3's ModelProvider).

Mirrors the Engine/ENGINES registry pattern in engines.py: a small interface
plus a registry, so scene breakdown (and later, character extraction) can
run against the local Ollama model or a frontier API key interchangeably.
"""

import abc
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from pydantic import BaseModel

from . import settings_store

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_TEXT_MODEL", "claude-opus-5")
OPENAI_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-5")


class TextProvider(abc.ABC):
    id: str
    label: str
    requires_api_key: bool = False

    @abc.abstractmethod
    async def is_available(self) -> bool:
        """Whether this provider is currently usable (reachable / has a key)."""

    @abc.abstractmethod
    async def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        response_schema: Optional[type[BaseModel]] = None,
    ) -> str:
        """Send a single system+user turn, return the raw text response.

        response_schema, when given, asks the provider to constrain its
        output to that exact JSON shape (stronger than json_mode's "valid
        JSON, any shape"). Not every provider can actually enforce this -
        see each implementation's docstring."""


class OllamaProvider(TextProvider):
    id = "ollama"
    label = "Ollama (local)"
    requires_api_key = False

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        response_schema: Optional[type[BaseModel]] = None,
    ) -> str:
        """Ollama's `format` field accepts either the string "json" (valid
        JSON, any shape) or a full JSON Schema object (output constrained to
        match it exactly) - response_schema uses the latter, a much
        stronger guarantee than json_mode alone."""
        async with httpx.AsyncClient(timeout=300) as client:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
            }
            if response_schema is not None:
                payload["format"] = response_schema.model_json_schema()
            elif json_mode:
                payload["format"] = "json"
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()["message"]["content"]


class AnthropicProvider(TextProvider):
    id = "anthropic"
    label = "Claude (Anthropic)"
    requires_api_key = True

    def __init__(self, api_key: str, model: str = ANTHROPIC_MODEL):
        self.api_key = api_key
        self.model = model

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        response_schema: Optional[type[BaseModel]] = None,
    ) -> str:
        # response_schema isn't enforced here yet - Claude's structured-output
        # support needs verifying against current API docs before wiring up
        # (tool-use forcing or output_config/format), not guessing the shape.
        # Falls back to the existing free-form JSON instruction either way;
        # llm.py/characters_llm.py already validate+retry defensively.
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        response = await client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class OpenAIProvider(TextProvider):
    id = "openai"
    label = "ChatGPT (OpenAI)"
    requires_api_key = True

    def __init__(self, api_key: str, model: str = OPENAI_MODEL):
        self.api_key = api_key
        self.model = model

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        response_schema: Optional[type[BaseModel]] = None,
    ) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        kwargs = {}
        if response_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "schema": response_schema.model_json_schema(),
                    "strict": True,
                },
            }
        elif json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )
        return response.choices[0].message.content or ""


@dataclass
class ProviderMeta:
    id: str
    label: str
    requires_api_key: bool


PROVIDER_REGISTRY: dict[str, ProviderMeta] = {
    "ollama": ProviderMeta(id="ollama", label=OllamaProvider.label, requires_api_key=False),
    "anthropic": ProviderMeta(
        id="anthropic", label=AnthropicProvider.label, requires_api_key=True
    ),
    "openai": ProviderMeta(id="openai", label=OpenAIProvider.label, requires_api_key=True),
}

DEFAULT_TEXT_PROVIDER_ID = os.environ.get("DEFAULT_TEXT_PROVIDER", "ollama")


def get_provider(provider_id: str, ollama_model: Optional[str] = None) -> TextProvider:
    if provider_id == "ollama":
        # ollama_model is a one-off override (e.g. "use qwen for just this
        # breakdown") - falls back to the Settings-level default, same as
        # before, when not given.
        return OllamaProvider(
            model=ollama_model or settings_store.get_ollama_model() or OLLAMA_MODEL
        )
    if provider_id == "anthropic":
        api_key = settings_store.get_key("anthropic")
        if not api_key:
            raise ValueError("No Anthropic API key configured")
        return AnthropicProvider(api_key=api_key)
    if provider_id == "openai":
        api_key = settings_store.get_key("openai")
        if not api_key:
            raise ValueError("No OpenAI API key configured")
        return OpenAIProvider(api_key=api_key)
    raise ValueError(f"Unknown text provider: {provider_id}")


def resolve_default_provider() -> TextProvider:
    provider_id = settings_store.get_default_text_provider() or DEFAULT_TEXT_PROVIDER_ID
    try:
        return get_provider(provider_id)
    except ValueError:
        return get_provider("ollama")


async def list_ollama_models() -> dict:
    """Locally-installed Ollama models (whatever `ollama pull` has fetched),
    plus which one story breakdown/character extraction currently use -
    lets Settings offer a dropdown instead of hardcoding OLLAMA_MODEL."""
    models: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            for m in response.json().get("models", []):
                models.append(
                    {
                        "name": m["name"],
                        "size_bytes": m.get("size"),
                    }
                )
    except httpx.HTTPError:
        pass
    return {
        "models": models,
        "selected": settings_store.get_ollama_model() or OLLAMA_MODEL,
    }


async def validate_key(provider_id: str, api_key: str) -> tuple[bool, str]:
    """Make a minimal real call to confirm a newly-entered key actually works."""
    try:
        if provider_id == "anthropic":
            provider = AnthropicProvider(api_key=api_key)
        elif provider_id == "openai":
            provider = OpenAIProvider(api_key=api_key)
        else:
            return False, f"{provider_id} does not take an API key"
        await provider.chat("Reply with only the word OK.", "OK?")
        return True, "Key is valid"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


async def list_providers() -> list[dict]:
    result = []
    for meta in PROVIDER_REGISTRY.values():
        api_key = settings_store.get_key(meta.id) if meta.requires_api_key else None
        try:
            provider = get_provider(meta.id)
            available = await provider.is_available()
        except ValueError:
            available = False
        result.append(
            {
                "id": meta.id,
                "label": meta.label,
                "requires_api_key": meta.requires_api_key,
                "available": available,
                "has_key": bool(api_key),
                "masked_key": settings_store.mask_key(api_key) if api_key else None,
            }
        )
    return result
