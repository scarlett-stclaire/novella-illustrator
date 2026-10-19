"""Open-source model catalogue (F23) - loads the repo-tracked manifest and
cross-checks each entry against what's actually installed, so the Settings
screen can show "installed" vs "not yet downloaded" per model without the
manifest itself ever holding weights or install state."""

import json
from pathlib import Path

from . import imagegen, providers

CATALOGUE_PATH = Path(__file__).resolve().parent.parent / "catalogue" / "models.json"

_manifest_cache: dict | None = None


def _load_manifest() -> dict:
    global _manifest_cache
    if _manifest_cache is None:
        _manifest_cache = json.loads(CATALOGUE_PATH.read_text())
    return _manifest_cache


async def list_models() -> list[dict]:
    manifest = _load_manifest()
    image_engines = {e["id"]: e for e in await imagegen.list_engines()}
    ollama_available = await providers.OllamaProvider().is_available()

    results = []
    for entry in manifest["models"]:
        if entry["task_type"] == "image":
            installed = image_engines.get(entry["id"], {}).get("available", False)
        elif entry["id"] == "ollama_llama3_1_8b":
            # Ollama reachability is the strongest signal we can get without
            # an extra network call per model; the default pull target
            # (OLLAMA_MODEL) is what the app actually uses.
            installed = ollama_available and providers.OLLAMA_MODEL == "llama3.1:8b"
        else:
            installed = False
        results.append({**entry, "installed": installed})
    return results
