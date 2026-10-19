"""LLM-driven character extraction (F12), reusing llm.py's chunking/JSON
helpers so long stories are processed the same way scene breakdown is."""

from .llm import _chunk_text, _extract_json_array
from .providers import TextProvider

SYSTEM_PROMPT = """You are a literary analyst identifying named characters in a \
story passage.

For the given passage, output a JSON array. Each element must be an object with:
- "name": the character's name as it appears in the text.
- "synopsis": a one or two sentence description of who they are and their role \
in the story.
- "visual_description": ONLY physical and costume details (hair, build, clothing, \
distinguishing features) that are stated or clearly implied in the text - no \
personality traits, no plot details. This is used to keep the character's \
appearance consistent across illustrations, so skip it (empty string) rather \
than inventing details that aren't in the text.
- "source_excerpt": a short VERBATIM quote (5-15 words, copied exactly character \
for character) from the passage where this character is introduced or described. \
It must be an exact substring of the passage.

Only include named individual characters (not crowds or groups, not an unnamed \
narrator). If a character appears in this passage but you've likely already \
described them in an earlier passage, include them again anyway - duplicates \
across passages are merged automatically afterward.

Return ONLY the JSON array, with no markdown fences and no extra commentary. If \
no named characters appear in this passage, return an empty array."""


def _merge_characters(raw_items: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for item in raw_items:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key not in merged:
            merged[key] = {
                "name": name,
                "synopsis": item.get("synopsis") or "",
                "visual_description": item.get("visual_description") or "",
                "source_excerpt": item.get("source_excerpt") or None,
            }
            order.append(key)
        else:
            existing = merged[key]
            if not existing["synopsis"] and item.get("synopsis"):
                existing["synopsis"] = item["synopsis"]
            if not existing["visual_description"] and item.get("visual_description"):
                existing["visual_description"] = item["visual_description"]
            if not existing["source_excerpt"] and item.get("source_excerpt"):
                existing["source_excerpt"] = item["source_excerpt"]
    return [merged[key] for key in order]


async def extract_characters(text: str, provider: TextProvider) -> list[dict]:
    chunks = _chunk_text(text)
    raw_items: list[dict] = []
    for chunk in chunks:
        content = await provider.chat(SYSTEM_PROMPT, chunk, json_mode=True)
        parsed = _extract_json_array(content)
        raw_items.extend(parsed)
    return _merge_characters(raw_items)
