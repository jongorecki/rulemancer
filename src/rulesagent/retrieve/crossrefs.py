"""Deterministic, post-retrieval cross-reference expansion (L1,
docs/plan-l1-crossref-expansion.md, Part A).

Closes the multi-hop gap in the vector pool (e.g. q016's cost-payment
interaction spans 601.2/601.2g/601.2h/601.2i, and the pool only ever has
room for one of a family of near-duplicate embeddings) WITHOUT an LLM
call: the Comprehensive Rules already spell out its own "see rule X"
cross-references in the chunk text, so following that one hop is free,
has no variance, and can't move any rank the retrieval eval measures --
appended chunks always land after the organic top-k.

What this deliberately does NOT do (binding, see the plan):
- No recursive expansion (refs-of-refs) -- one hop only, matching the
  diagnosis.
- No LLM second-hop query.
- No prompt template change -- callers just get more `[id] text` blocks
  in the same shape.
"""

import re

from rulesagent.contracts import Chunk, Retrieved

# "see rule 704.5" / "rules 601.2a" -- the decimal+letter part is OPTIONAL,
# so a bare "rule 704" (a family reference, no subrule) matches too, feeding
# resolution rule 2 (family-entry fallback) below.
_WORD_REF = re.compile(r"\brules?\s+(\d{3}(?:\.\d+[a-z]?)?)\b", re.IGNORECASE)

# Bare inline mentions with no "rule" word at all, e.g. "(601.2h)". Always
# has a decimal -- a bare 3-digit number alone is too ambiguous to treat as
# a reference (could be a mana value, a year, anything).
_BARE_REF = re.compile(r"\b(\d{3}\.\d+[a-z]?)\b")


def _extract_refs(text: str) -> list[str]:
    """Refs mentioned in `text`, in first-mention (left-to-right) order,
    deduped to their first occurrence. Both patterns are scanned and merged
    by match position -- a ref matched by both (e.g. "601.2i" inside "see
    rule 601.2i") just collapses to one entry, same as a ref mentioned twice
    by coincidence."""
    hits = [(m.start(), m.group(1)) for m in _WORD_REF.finditer(text)]
    hits += [(m.start(), m.group(1)) for m in _BARE_REF.finditer(text)]
    hits.sort(key=lambda h: h[0])
    seen: set[str] = set()
    out: list[str] = []
    for _, ref in hits:
        if ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def _resolve(ref: str, chunk_map: dict[str, Chunk]) -> Chunk | None:
    """Resolution rules (the plan's edge cases):

    1. Exact source_id in chunk_map -> that chunk.
    2. Bare family ref ("704", no decimal): try "704" itself, else fall back
       to "704.1" (the family's entry rule) -- ONE chunk, not the whole
       family (the cap is 5 and a family dump would eat it).
    3. No chunk at all (label-like rules never got their own chunk, e.g.
       701.5 "Cast"): None -- caller records this as a skip rather than
       silently dropping it.
    """
    chunk = chunk_map.get(ref)
    if chunk is not None:
        return chunk
    if "." not in ref:
        return chunk_map.get(f"{ref}.1")
    return None


def expand_crossrefs(
    retrieved: list[Retrieved],
    chunk_map: dict[str, Chunk],
    max_extra: int = 5,
    debug: dict | None = None,
) -> list[Retrieved]:
    """Follow the CR's own cross-references one hop past the organic vector
    pool. Scans `r.chunk.text` for each retrieved chunk IN RANK ORDER,
    collects referenced rule numbers in first-mention order, and appends up
    to `max_extra` referenced chunks the pool missed -- AFTER the organic
    top-k, so nothing the retrieval eval measures (organic ranks/scores)
    moves. Appended entries carry the sentinel score 0.0 (they were never
    scored by the retriever; pretending otherwise would poison any future
    score-reading logic).

    `debug`, if given a dict, is populated in place with `refs_found` (every
    distinct ref seen), `appended` (source_ids actually added), and
    `skipped` (refs that resolved to no chunk at all) -- RulesAgent surfaces
    this as `last_crossref` so misses are observable, not silent. Optional
    so the return type stays exactly `list[Retrieved]`.
    """
    pool_ids = {r.chunk.source_id for r in retrieved}

    refs: list[str] = []
    seen: set[str] = set()
    for r in retrieved:
        for ref in _extract_refs(r.chunk.text):
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)

    out = list(retrieved)
    appended: list[str] = []
    skipped: list[str] = []
    for ref in refs:
        if ref in pool_ids:
            continue  # dedupe against the organic pool
        if len(appended) >= max_extra:
            break  # cap reached -- remaining refs left unresolved
        chunk = _resolve(ref, chunk_map)
        if chunk is None:
            skipped.append(ref)
            continue
        if chunk.source_id in pool_ids:
            continue  # family fallback resolved to something already present
        out.append(Retrieved(chunk=chunk, score=0.0))
        pool_ids.add(chunk.source_id)
        appended.append(chunk.source_id)

    if debug is not None:
        debug.update(refs_found=refs, appended=appended, skipped=skipped)
    return out
