import json
import threading
from pathlib import Path

from .models import Novella

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NOVELLAS_DIR = DATA_DIR / "novellas"
IMAGES_DIR = DATA_DIR / "images"

_lock = threading.Lock()


def _novella_path(novella_id: str) -> Path:
    return NOVELLAS_DIR / f"{novella_id}.json"


def init_storage() -> None:
    NOVELLAS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


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
