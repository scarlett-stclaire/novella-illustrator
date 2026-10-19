import json
import threading
from pathlib import Path

from . import settings_store
from .models import Novella

# F3: the user can point this at another drive/location via Settings, but it
# only takes effect on the next restart - this module's directory constants
# are computed once at import time, before a running process could ever see
# a change made through the API.
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_custom_root = settings_store.get_storage_root()
DATA_DIR = Path(_custom_root) / "novella-illustrator-data" if _custom_root else _DEFAULT_DATA_DIR
NOVELLAS_DIR = DATA_DIR / "novellas"
IMAGES_DIR = DATA_DIR / "images"
EXPORTS_DIR = DATA_DIR / "exports"

_lock = threading.Lock()


def _novella_path(novella_id: str) -> Path:
    return NOVELLAS_DIR / f"{novella_id}.json"


def init_storage() -> None:
    NOVELLAS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def save_novella(novella: Novella) -> None:
    with _lock:
        _novella_path(novella.id).write_text(novella.model_dump_json(indent=2))


def load_novella(novella_id: str) -> Novella | None:
    path = _novella_path(novella_id)
    if not path.exists():
        return None
    return Novella.model_validate_json(path.read_text())


def list_novellas() -> list[Novella]:
    novellas = []
    for path in sorted(NOVELLAS_DIR.glob("*.json")):
        novellas.append(Novella.model_validate_json(path.read_text()))
    return novellas


def novella_image_dir(novella_id: str) -> Path:
    path = IMAGES_DIR / novella_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def novella_export_dir(novella_id: str) -> Path:
    path = EXPORTS_DIR / novella_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def update_novella(novella_id: str, **fields) -> Novella | None:
    """Atomically read-modify-write top-level Novella fields (e.g. status,
    breakdown_progress, scenes) - see update_scene for why this matters."""
    with _lock:
        path = _novella_path(novella_id)
        if not path.exists():
            return None
        novella = Novella.model_validate_json(path.read_text())
        for key, value in fields.items():
            setattr(novella, key, value)
        path.write_text(novella.model_dump_json(indent=2))
        return novella


def update_character(novella_id: str, character_id: str, **fields) -> Novella | None:
    """Atomically read-modify-write a single character's fields - same
    rationale as update_scene (concurrent background image generation)."""
    with _lock:
        path = _novella_path(novella_id)
        if not path.exists():
            return None
        novella = Novella.model_validate_json(path.read_text())
        for character in novella.characters:
            if character.id == character_id:
                for key, value in fields.items():
                    setattr(character, key, value)
                path.write_text(novella.model_dump_json(indent=2))
                return novella
        return None


def update_scene(novella_id: str, scene_id: str, **fields) -> Novella | None:
    """Atomically read-modify-write a single scene's fields.

    Needed because scene generation runs as a background task that writes
    frequent progress updates while the rest of the app may read/write the
    same novella concurrently.
    """
    with _lock:
        path = _novella_path(novella_id)
        if not path.exists():
            return None
        novella = Novella.model_validate_json(path.read_text())
        for scene in novella.scenes:
            if scene.id == scene_id:
                for key, value in fields.items():
                    setattr(scene, key, value)
                path.write_text(novella.model_dump_json(indent=2))
                return novella
        return None
