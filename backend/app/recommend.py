"""Model recommendation + cost/performance comparison (F9, F17, F18).

Two entry points, matching the plan's two spec-mandated surfacing points:
- compare_for_text(): story/scene text -> scene-type + complexity fit, used
  right after story input (F9) and per-scene after breakdown.
- compare_for_feedback(): regenerate-panel free text -> issue-driven fit
  (F17), e.g. "hands look contorted" -> SDXL + ADetailer.

Both rank only engines that are actually available (imagegen.list_engines())
and return a compact, already-sorted candidate list the frontend can render
directly - "a compact comparison, not a wall of numbers" per spec 6.3.
"""

import json
from pathlib import Path

from . import imagegen
from .classifier import classify_complexity, classify_feedback, classify_scene_type

PROFILES_PATH = (
    Path(__file__).resolve().parent.parent / "catalogue" / "model_capability_profiles.json"
)

_profiles_cache: dict | None = None


def _load_profiles() -> dict:
    global _profiles_cache
    if _profiles_cache is None:
        _profiles_cache = json.loads(PROFILES_PATH.read_text())
    return _profiles_cache


async def get_available_engines() -> dict[str, dict]:
    """Engines that are both registered and have their weights present,
    keyed by id - the only candidates a recommendation may suggest."""
    return {e["id"]: e for e in await imagegen.list_engines() if e["available"]}


def _rank_by_fit(available: dict[str, dict], scene_type: str, complexity: str) -> list[dict]:
    profiles = _load_profiles()["image_engines"]
    rows = []
    for engine_id, profile in profiles.items():
        if engine_id not in available:
            continue
        score = profile["scene_type_scores"].get(scene_type, 3) + profile[
            "complexity_scores"
        ].get(complexity, 3)
        rows.append(
            {
                "id": engine_id,
                "label": available[engine_id]["label"],
                "score": score,
                "avg_seconds_per_image": profile["avg_seconds_per_image"],
                "notes": profile["notes"],
            }
        )
    rows.sort(key=lambda r: (-r["score"], r["avg_seconds_per_image"]))
    for i, row in enumerate(rows):
        row["recommended"] = i == 0
    return rows


def _rank_by_fix(available: dict[str, dict], issue_type: str | None) -> list[dict]:
    profiles = _load_profiles()["image_engines"]
    rows = []
    for engine_id, profile in profiles.items():
        if engine_id not in available:
            continue
        if issue_type and issue_type in profile["fix_strengths"]:
            score = profile["fix_strengths"][issue_type]
        else:
            # No recognizable issue mentioned - fall back to a generic,
            # middle-of-the-road comparison rather than returning nothing.
            score = profile["scene_type_scores"]["generic"] + profile[
                "complexity_scores"
            ]["moderate"]
        rows.append(
            {
                "id": engine_id,
                "label": available[engine_id]["label"],
                "score": score,
                "avg_seconds_per_image": profile["avg_seconds_per_image"],
                "notes": profile["notes"],
            }
        )
    rows.sort(key=lambda r: (-r["score"], r["avg_seconds_per_image"]))
    for i, row in enumerate(rows):
        row["recommended"] = i == 0
    return rows


def compare_for_text(text: str, available: dict[str, dict]) -> dict:
    scene_type = classify_scene_type(text)
    complexity = classify_complexity(text)
    candidates = _rank_by_fit(available, scene_type, complexity)
    return {
        "scene_type": scene_type,
        "complexity": complexity,
        "candidates": candidates,
        "recommended_engine_id": candidates[0]["id"] if candidates else None,
    }


def compare_for_feedback(feedback: str, available: dict[str, dict]) -> dict:
    issue_type = classify_feedback(feedback)
    candidates = _rank_by_fix(available, issue_type)
    return {
        "issue_type": issue_type,
        "candidates": candidates,
        "recommended_engine_id": candidates[0]["id"] if candidates else None,
    }
