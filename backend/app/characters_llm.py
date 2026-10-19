"""LLM-driven character extraction (F12), reusing llm.py's chunking/JSON
helpers so long stories are processed the same way scene breakdown is.
Name-variant merging (F12) is a separate, deterministic step - see
entity_resolution.py - not an LLM task."""

from pydantic import BaseModel, Field

from .entity_resolution import merge_characters
from .llm import _chunk_text, _parse_structured
from .providers import TextProvider

SYSTEM_PROMPT = """You are a literary analyst identifying named characters in a \
story passage.

For the given passage, output a JSON object with a "characters" array. Each \
element must be an object with:
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
across passages (and name variants like nicknames or titles) are merged \
automatically afterward.

Return ONLY the JSON object, with no markdown fences and no extra commentary. If \
no named characters appear in this passage, return an empty "characters" array."""


class ExtractedCharacter(BaseModel):
    name: str
    synopsis: str = Field(description="Personality and plot relevance")
    visual_description: str = Field(
        description=(
            "Physical and costume description. Must be an empty string if "
            "not explicitly described in the text."
        )
    )
    source_excerpt: str = Field(description="Exact verbatim substring")


class CharacterList(BaseModel):
    characters: list[ExtractedCharacter]


async def extract_characters(text: str, provider: TextProvider) -> list[dict]:
    chunks = _chunk_text(text)
    raw_items: list[dict] = []
    for chunk in chunks:
        content = await provider.chat(
            SYSTEM_PROMPT, chunk, json_mode=True, response_schema=CharacterList
        )
        parsed = _parse_structured(content, CharacterList, "characters")
        raw_items.extend(parsed)
    return merge_characters(raw_items)
