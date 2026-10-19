"""Heuristic scene-type / complexity / feedback-issue classification.

Spec section 6.2 explicitly allows "a cheap model or heuristics" for a first
version. These are plain keyword/length heuristics - cheap, fast, no network
call - good enough to drive a *suggested* engine pick that the user can
always override, not a scientific classifier.
"""

import re

SCENE_TYPE_KEYWORDS = {
    "landscape": [
        "mountain", "forest", "sky", "ocean", "sea", "field", "valley",
        "horizon", "coast", "landscape", "sunset", "sunrise", "meadow",
        "cliff", "river", "garden", "wilderness", "shoreline", "desert",
        "hillside", "countryside",
    ],
    "action": [
        "ran", "running", "fought", "fighting", "chased", "chasing",
        "jumped", "explosion", "battle", "sword", "gun", "fled",
        "struck", "collided", "raced", "attack", "attacking", "fled",
        "escaped", "crashed", "charging",
    ],
    "drama": [
        "cried", "crying", "tears", "whispered", "screamed", "argument",
        "shouted", "sobbed", "grief", "anger", "furious", "heartbroken",
        "confrontation", "betrayal", "wept", "sorrow", "anguish",
        "trembling", "despair",
    ],
    "text_heavy": [
        "sign read", "letter", "newspaper", "the book", "words on",
        "note said", "handwriting", "scrawled", "inscription", "banner",
        "headline",
    ],
    "human_figures": [
        "she", "he", "they", "her hand", "his hand", "face", "eyes",
        "smiled", "hair", "dress", "wearing", "body", "arms", "hands",
        "stood", "walked", "her voice", "his voice", "figure",
    ],
}

# Checked in this order - a scene mentioning both a storm and a fistfight
# reads as action before landscape, etc. "generic" is the fallback.
SCENE_TYPE_PRIORITY = ["text_heavy", "action", "drama", "human_figures", "landscape"]


def classify_scene_type(text: str) -> str:
    lowered = text.lower()
    scores = {
        category: sum(lowered.count(kw) for kw in keywords)
        for category, keywords in SCENE_TYPE_KEYWORDS.items()
    }
    best_category = max(SCENE_TYPE_PRIORITY, key=lambda c: scores[c])
    return best_category if scores[best_category] > 0 else "generic"


def classify_complexity(text: str) -> str:
    words = re.findall(r"[A-Za-z']+", text)
    word_count = len(words)
    sentence_count = max(1, len(re.findall(r"[.!?]+", text)))
    quote_count = text.count('"') + text.count("“") + text.count("”")
    capitalized = len({w for w in words if w[:1].isupper() and len(w) > 1})

    # A rough load-bearing score: more named things + more dialogue + longer
    # sentences = harder for an image model to compose correctly in one shot.
    score = (
        (word_count / max(1, sentence_count)) * 0.4
        + capitalized * 1.5
        + quote_count * 0.5
    )

    if score < 12:
        return "simple"
    if score < 28:
        return "moderate"
    return "complex"


FEEDBACK_ISSUE_KEYWORDS = {
    "anatomy": [
        "hand", "finger", "limb", "anatomy", "contort", "deformed",
        "extra arm", "extra leg", "malformed", "proportion", "pose",
        "twisted", "mangled", "melted", "extra finger", "missing finger",
        "weird arm", "weird leg", "merged",
    ],
    "text_rendering": [
        "text", "letters", "words", "sign", "writing", "gibberish",
        "font", "illegible", "unreadable", "typography",
    ],
    "detail": [
        "blurry", "blur", "low detail", "low quality", "soft focus",
        "fuzzy", "lacks detail", "not sharp", "muddy", "pixelated",
        "low res",
    ],
}


def classify_feedback(feedback: str) -> str | None:
    """Returns the dominant issue type mentioned in free-text feedback, or
    None if nothing recognizable was mentioned (caller should fall back to
    a generic scene-type/complexity comparison instead)."""
    lowered = feedback.lower()
    scores = {
        issue: sum(lowered.count(kw) for kw in keywords)
        for issue, keywords in FEEDBACK_ISSUE_KEYWORDS.items()
    }
    best_issue = max(scores, key=scores.get)
    return best_issue if scores[best_issue] > 0 else None
