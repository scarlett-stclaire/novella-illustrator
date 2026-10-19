"""Deterministic, zero-LLM character-identity merging (F12).

Replaces exact case-insensitive name matching (which left "Bill" and "Mr.
Bennett" as two separate characters) with normalization + token-subset
matching + union-find clustering, so name variants collected across
different story chunks resolve to one character record.
"""

import re
from dataclasses import dataclass, field

TITLES = {
    "mr",
    "mrs",
    "ms",
    "miss",
    "dr",
    "prof",
    "sir",
    "lady",
    "lord",
    "madam",
    "master",
}

# Common English diminutives -> root name. Not exhaustive - add entries here
# as real stories surface merges this misses.
DIMINUTIVES = {
    "bill": "william",
    "liz": "elizabeth",
    "dick": "richard",
    "tom": "thomas",
    "bob": "robert",
}

_PUNCT_RE = re.compile(r"[^\w\s]")


def normalize_name(name: str) -> str:
    """Lowercases, strips punctuation, drops titles, and maps diminutives to
    their root name. The raw `name` string is never mutated in place - this
    is only used to decide whether two names refer to the same character."""
    cleaned = _PUNCT_RE.sub(" ", name.lower())
    tokens = [t for t in cleaned.split() if t not in TITLES]
    tokens = [DIMINUTIVES.get(t, t) for t in tokens]
    return " ".join(tokens)


def names_match(norm_a: str, norm_b: str) -> bool:
    """True if the two normalized names are identical, or if one's token set
    is a subset of the other's (e.g. {"william"} is a subset of {"william",
    "bennett"}) - so a first-name-only mention merges with a full name."""
    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    if not tokens_a or not tokens_b:
        return False
    return tokens_a == tokens_b or tokens_a.issubset(tokens_b) or tokens_b.issubset(tokens_a)


class _UnionFind:
    def __init__(self, items: list[str]):
        self._parent = {item: item for item in items}

    def find(self, item: str) -> str:
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, a: str, b: str) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_b] = root_a


@dataclass
class _ClusterAccumulator:
    raw_names: list[str] = field(default_factory=list)
    synopsis_parts: list[str] = field(default_factory=list)
    visual_parts: list[str] = field(default_factory=list)
    source_excerpts: list[str] = field(default_factory=list)


def merge_characters(raw_items: list[dict]) -> list[dict]:
    """Clusters raw per-chunk extractions (each a dict with name/synopsis/
    visual_description/source_excerpt) into one record per actual character.

    Returns a list of dicts shaped for the Character model: name (the
    longest raw name seen - the fullest/most specific form), aliases (the
    other raw name strings that resolved to this same character),
    synopsis/visual_description (non-empty fragments joined with newlines),
    source_excerpts (deduplicated, order preserved)."""
    names = []
    seen = set()
    for item in raw_items:
        name = (item.get("name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    uf = _UnionFind(names)
    normalized = {name: normalize_name(name) for name in names}
    token_sets = {name: frozenset(normalized[name].split()) for name in names}
    # Every distinct normalized token-set actually seen, for the corroboration
    # check below - a dict so repeated sets collapse automatically.
    all_token_sets = set(token_sets.values())

    for i, name_a in enumerate(names):
        for name_b in names[i + 1 :]:
            tokens_a, tokens_b = token_sets[name_a], token_sets[name_b]
            if not tokens_a or not tokens_b:
                continue
            if tokens_a == tokens_b:
                uf.union(name_a, name_b)
                continue
            smaller, larger = (
                (tokens_a, tokens_b) if len(tokens_a) < len(tokens_b) else (tokens_b, tokens_a)
            )
            if not smaller.issubset(larger):
                continue
            if len(smaller) > 1:
                # A 2+-token overlap (e.g. "William Bennett" inside "William
                # Bennett III") is already strong evidence on its own.
                uf.union(name_a, name_b)
                continue
            # The risky case: a single bare token (almost always what's left
            # after stripping a title off a surname-only mention, e.g. "Mr.
            # Hendricks" -> {"hendricks"}) is weak evidence by itself - a
            # shared surname alone doesn't mean the same person (could be two
            # different relatives). Only bridge it into the larger name if
            # some OTHER independently-extracted name corroborates the
            # connection by exactly matching what's left of the larger name
            # once that token is removed (e.g. "Bill" -> {"william"} matching
            # "William Bennett" minus "bennett" -> {"william"}).
            remainder = larger - smaller
            if remainder in all_token_sets:
                uf.union(name_a, name_b)

    clusters: dict[str, _ClusterAccumulator] = {}
    for item in raw_items:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        root = uf.find(name)
        acc = clusters.setdefault(root, _ClusterAccumulator())
        if name not in acc.raw_names:
            acc.raw_names.append(name)
        synopsis = (item.get("synopsis") or "").strip()
        if synopsis:
            acc.synopsis_parts.append(synopsis)
        visual = (item.get("visual_description") or "").strip()
        if visual:
            acc.visual_parts.append(visual)
        excerpt = (item.get("source_excerpt") or "").strip()
        if excerpt and excerpt not in acc.source_excerpts:
            acc.source_excerpts.append(excerpt)

    results = []
    # Iterate in the order each cluster's root first appeared, so output
    # order stays stable/predictable rather than depending on dict hashing.
    seen_roots = set()
    for name in names:
        root = uf.find(name)
        if root in seen_roots:
            continue
        seen_roots.add(root)
        acc = clusters[root]
        primary_name = max(acc.raw_names, key=len)
        aliases = [n for n in acc.raw_names if n != primary_name]
        results.append(
            {
                "name": primary_name,
                "aliases": aliases,
                "synopsis": "\n".join(acc.synopsis_parts),
                "visual_description": "\n".join(acc.visual_parts),
                "source_excerpts": acc.source_excerpts,
            }
        )
    return results
