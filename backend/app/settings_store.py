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
        return {"api_keys": {}, "default_text_provider": None}
    data = json.loads(SETTINGS_PATH.read_text())
    data.setdefault("api_keys", {})
    data.setdefault("default_text_provider", None)
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
