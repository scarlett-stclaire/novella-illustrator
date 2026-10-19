from app.entity_resolution import merge_characters, normalize_name, names_match


def _names(merged: list[dict]) -> set[str]:
    return {m["name"] for m in merged}


def test_title_and_nickname_merge_into_one_entity():
    raw = [
        {"name": "Mr. Bennett", "synopsis": "A stern father.", "visual_description": ""},
        {"name": "Bill", "synopsis": "", "visual_description": "Tall, grey-haired."},
        {"name": "Bill Bennett", "synopsis": "", "visual_description": ""},
    ]
    merged = merge_characters(raw)
    assert len(merged) == 1
    record = merged[0]
    assert record["name"] == "Bill Bennett"
    assert set(record["aliases"]) == {"Mr. Bennett", "Bill"}


def test_diminutive_merge_elizabeth_and_liz():
    raw = [
        {"name": "Elizabeth", "synopsis": "The eldest daughter.", "visual_description": ""},
        {"name": "Liz", "synopsis": "", "visual_description": "Dark curly hair."},
    ]
    merged = merge_characters(raw)
    assert len(merged) == 1
    assert merged[0]["name"] == "Elizabeth"
    assert merged[0]["aliases"] == ["Liz"]


def test_distinct_full_names_stay_separate():
    raw = [
        {"name": "John Smith", "synopsis": "", "visual_description": ""},
        {"name": "John Doe", "synopsis": "", "visual_description": ""},
    ]
    merged = merge_characters(raw)
    assert len(merged) == 2
    assert _names(merged) == {"John Smith", "John Doe"}


def test_visual_description_merges_and_skips_empty_fragments():
    raw = [
        {"name": "Kael", "synopsis": "", "visual_description": "Dark hair."},
        {"name": "Kael", "synopsis": "", "visual_description": ""},
        {"name": "Kael", "synopsis": "", "visual_description": "Pale skin."},
    ]
    merged = merge_characters(raw)
    assert len(merged) == 1
    assert merged[0]["visual_description"] == "Dark hair.\nPale skin."


def test_source_excerpts_are_deduplicated_and_ordered():
    raw = [
        {"name": "Kael", "source_excerpt": "Kael walked in."},
        {"name": "Kael", "source_excerpt": "Kael walked in."},
        {"name": "Kael", "source_excerpt": "Kael spoke softly."},
    ]
    merged = merge_characters(raw)
    assert merged[0]["source_excerpts"] == ["Kael walked in.", "Kael spoke softly."]


def test_normalize_name_strips_titles_and_punctuation():
    assert normalize_name("Mr. Bennett") == "bennett"
    assert normalize_name("Dr. Smith-Jones") == "smith jones"


def test_normalize_name_maps_diminutives():
    assert normalize_name("Bill") == "william"
    assert normalize_name("Liz") == "elizabeth"


def test_names_match_requires_nonempty_token_overlap():
    # Two names that normalize to nothing (e.g. just a stripped title) must
    # never be treated as matching each other.
    assert not names_match("", "")
    assert not names_match("", "william")
