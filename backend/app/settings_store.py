"""Machine-local storage for frontier API keys and text-provider settings.

Deliberately kept OUTSIDE the project directory (in the user's home folder,
not under backend/data/) so a key can never end up committed to git even by
accident - this is the interim store called out in the spec as "never in
project files"; it will be swapped for the macOS Keychain once the app is
packaged with Tauri (see the implementation plan's Phase 7).
"""

import json
import os
import stat
import threading
from pathlib import Path
from typing import Optional

SETTINGS_DIR = Path(os.environ.get("NOVELLA_SETTINGS_DIR", Path.home() / ".novella-illustrator"))
SETTINGS_PATH = SETTINGS_DIR / "settings.json"

_lock = threading.Lock()


def _read() -> dict:
    if not SETTINGS_PATH.exists():
        return {
            "api_keys": {},
            "default_text_provider": None,
            "enabled_engine_ids": None,
            "storage_root": None,
            "ollama_model": None,
        }
    data = json.loads(SETTINGS_PATH.read_text())
    data.setdefault("api_keys", {})
    data.setdefault("default_text_provider", None)
    data.setdefault("enabled_engine_ids", None)
    data.setdefault("storage_root", None)
    data.setdefault("ollama_model", None)
    return data


def _write(data: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, indent=2))
    os.chmod(SETTINGS_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0600 - owner read/write only


def get_key(provider_id: str) -> Optional[str]:
    with _lock:
        return _read()["api_keys"].get(provider_id)


def set_key(provider_id: str, api_key: str) -> None:
    with _lock:
        data = _read()
        data["api_keys"][provider_id] = api_key
        _write(data)


def delete_key(provider_id: str) -> None:
    with _lock:
        data = _read()
        data["api_keys"].pop(provider_id, None)
        _write(data)


def has_key(provider_id: str) -> bool:
    return bool(get_key(provider_id))


def mask_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}...{api_key[-4:]}"


def get_default_text_provider() -> Optional[str]:
    with _lock:
        return _read()["default_text_provider"]


def set_default_text_provider(provider_id: Optional[str]) -> None:
    with _lock:
        data = _read()
        data["default_text_provider"] = provider_id
        _write(data)


def get_enabled_engine_ids() -> Optional[list[str]]:
    """None means "all available engines enabled" - the default, so existing
    installs aren't suddenly left with zero engines (F2's "only selected
    models appear" needs an explicit opt-out, not an opt-in by default)."""
    with _lock:
        return _read()["enabled_engine_ids"]


def set_enabled_engine_ids(engine_ids: Optional[list[str]]) -> None:
    with _lock:
        data = _read()
        data["enabled_engine_ids"] = engine_ids
        _write(data)


def get_storage_root() -> Optional[str]:
    """None means "use the default backend/data location" (F3). Changing
    this only takes effect on the next backend restart - storage.py computes
    its directory constants at import time, before any request can change
    this setting."""
    with _lock:
        return _read()["storage_root"]


def set_storage_root(path: Optional[str]) -> None:
    with _lock:
        data = _read()
        data["storage_root"] = path
        _write(data)


def get_ollama_model() -> Optional[str]:
    """None means "use OLLAMA_MODEL from .env" (the original hardcoded
    default) - story breakdown and character extraction both read this to
    pick which locally-installed Ollama model actually does the work."""
    with _lock:
        return _read()["ollama_model"]


def set_ollama_model(model: Optional[str]) -> None:
    with _lock:
        data = _read()
        data["ollama_model"] = model
        _write(data)
