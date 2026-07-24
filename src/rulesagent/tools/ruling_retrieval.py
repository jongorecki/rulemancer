"""Per-card ruling relevance retrieval -- a mini-RAG over each [card]'s own
rulings (docs/plan-rulings-on-demand.md).

Replaces the wholesale ruling dump. Embed a card's rulings, keep only the few
most relevant to the question. WITHHOLD by default: if nothing clears the
relevance floor, no rulings are included and the rules-RAG + oracle text stand
alone. The grounding call (Jon): the need-signal comes from the corpus
(relevance to the question), not from the model's self-assessed confidence --
which is why this always runs rather than gating on a low-confidence answer.
"""

import hashlib
import json

import numpy as np

from rulesagent.cache import KVCache
from rulesagent.contracts import Card
from rulesagent.index.embed import embed_documents, embed_query

RULING_MODEL = "voyage-4-large"  # same embedding space as the rules index
TOP_N = 5
# Cap the number of rulings included, so a card carrying ~25 near-duplicate
# mechanic-boilerplate rulings (a Duskmourn Room) can't flood the prompt even if
# several clear the floor.
#
# RAISED 3 -> 5 (Jon, 2026-07-24: "only grabbing the top 3 rulings feels like it
# could be biting us. even 5 probably fixes it"). Measured on the 20-question card
# eval AFTER the ruling_emb cache purge (see below) -- the pre-purge numbers were
# scored against corrupted embeddings and are not comparable:
#
#   - c011 (Valki / cascade) GAINS ITS LOAD-BEARING RULING at rank 4: "To determine
#     whether it is legal to play a modal double-faced card, consider only the
#     characteristics of the face you're playing and ignore the other face's
#     characteristics." That is precisely the ruling the question turns on.
#   - c010 and c019 are NOT fixed. c010's ranks 4-5 are about skipping turns and a
#     player losing the game -- irrelevant to its protection-from-instants question;
#     c019's ranks 4-5 don't clear the floor at all. The comment below listing
#     c010/c011/c019 as "outside top-3" stands, but only one of the three was a
#     cap problem. The other two are the genuine semantic-mismatch limit it names.
#   - Cost: +36% ruling text, ~63 tokens/question average, 213 worst case (c016).
#
# So this is a real but narrow win, bought cheaply. Note select_rulings_union()
# defaults to TOP_N + 1, so it moves 4 -> 6 with this change, consistent with its
# documented "a union of queries deserves one more slot" intent.

COSINE_FLOOR = 0.38
# CALIBRATED on the 19-question card eval (2026-07-21). Across the ruling-bearing
# questions the load-bearing ruling's cosine to its question ran 0.41-0.66; 0.38
# sits just under the low end (c012 Lithoform-6 at 0.418, c015 Grist-1 at 0.414)
# with margin for query-embedding wobble, while the top-3 cap keeps a card with
# many rulings from flooding the prompt. 3 questions have a load-bearing ruling
# BELOW this / outside top-3 (c010, c011, c019) -- a genuine semantic-mismatch
# limit of relevance retrieval, not a floor to chase down (lowering it wouldn't
# lift those into the top 3 anyway). See LOG.md.

_cache = KVCache("ruling_emb")
# L3 (docs/plan-l3-sqlite-caches.md): data/cache.db's `ruling_emb` table,
# keyed by ruling_id() (see below) -> JSON list[float] embedding. Frozen once
# written -- embeddings are stable enough and we want reproducible SELECTION.
# Per-op connections fix the old load-whole-dict / dump-whole-dict cache race
# (never run two writers at once -- now moot).
#
# ⚠️ POSITIONAL-KEY HAZARD (bit us 2026-07-24, purged and verified clean;
# RESOLVED 2026-07-24 -- durable fix landed, see below).
# The key USED TO BE oracle_id#INDEX, i.e. a position in a list owned by an
# external data source. When the Scryfall local-bulk merge landed, the local
# store returned each card's rulings in a DIFFERENT ORDER than the live API
# had, so every cached vector stayed bolted to an index whose text had moved:
# 175 of 190 cached embeddings across the card-eval pool (92%) no longer
# matched the text at their index. Selection scored stale vectors while the
# prompt printed whatever text sat at the chosen index. It does NOT self-heal
# -- _card_ruling_embeddings() below only embeds keys that are MISSING and
# never checks that a cached vector still matches its text. Nothing crashed;
# the only thing that caught it was the byte-identity fixture in
# tests/test_prompt_identity.py.
#
# Stopgap at the time was purging the ruling_emb table (1,375 rows) and
# letting it repopulate: re-verified 0/190 mismatched afterwards.
#
# RESOLVED: ruling_id() is now content-derived (a hash of the ruling text,
# not its list position -- see its docstring below), so a data-source reorder
# can no longer move an id and this table no longer needs purging when that
# happens. The old positional rows (key shape oracle_id#<digits>) were
# deleted as a one-off cleanup when this landed, since the new key format
# makes them permanently unreachable -- dead weight, not silently wrong.


def ruling_id(card: Card, i: int) -> str:
    """Stable id for one ruling: oracle_id + a hash of the ruling TEXT at
    index `i` (first 12 hex chars of SHA-256 of the text, stripped of
    leading/trailing whitespace only -- no lowercasing, no punctuation
    stripping, since two rulings differing only in case are genuinely
    different text and should get different ids). The oracle_id prefix keeps
    ids groupable per card and debuggable; it plays no role in collision
    avoidance, which SHA-256 already gives.

    Stable against: reordering a card's rulings list (a data-source change
    like the Scryfall local-bulk merge that returns rulings in a different
    order no longer moves any id) and reprints (oracle_id is cross-printing).
    NOT stable against: an edit to the ruling text itself -- that correctly
    produces a new id, because it IS different text with a different
    embedding.

    Was positional (oracle_id#index) until 2026-07-24, when a data-source
    reorder silently mismatched 92% of the cached embeddings against their
    text -- see the POSITIONAL-KEY HAZARD comment above and DECISIONS.md.
    This is the durable fix."""
    text = card.rulings[i].strip()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{card.oracle_id}#{digest}"


def _card_ruling_embeddings(card: Card) -> np.ndarray:
    """(R, dim) L2-normalized embeddings for card.rulings, cached per
    oracle_id#index. Only uncached rulings hit the API."""
    ids = [ruling_id(card, i) for i in range(len(card.rulings))]
    cached = {rid: _cache.get(rid) for rid in ids}
    missing = [(i, card.rulings[i]) for i, rid in enumerate(ids) if cached[rid] is None]
    if missing:
        # Benign check-then-act race: concurrent requests discovering the same
        # missing ruling will both call embed_documents and _cache.put; last write
        # wins. Duplicate embedding work is accepted; per-key SQLite writes prevent
        # corruption.
        embs = embed_documents([t for _, t in missing], RULING_MODEL)
        for (i, _), vec in zip(missing, embs):
            value = json.dumps(vec.tolist()).encode("utf-8")
            _cache.put(ids[i], value)
            cached[ids[i]] = value
    return np.array([json.loads(cached[rid]) for rid in ids], dtype=np.float32)


def _select_from_scores(scores: np.ndarray, floor: float, top_n: int) -> list[tuple[int, float]]:
    """Shared cap+floor selection: highest score first, stop at the first
    score under `floor` (scores are sorted descending, so that's also every
    remaining one), capped at `top_n`."""
    out: list[tuple[int, float]] = []
    for i in np.argsort(-scores):
        if float(scores[i]) < floor:
            break
        out.append((int(i), float(scores[i])))
        if len(out) >= top_n:
            break
    return out


def select_rulings(card: Card, query: str, floor: float = COSINE_FLOOR,
                   top_n: int = TOP_N) -> list[tuple[int, float]]:
    """Return (ruling_index, cosine) for the card's rulings relevant to `query`:
    those clearing `floor`, capped at `top_n`, highest score first. Empty when
    the card has no rulings or none clear the floor -- i.e. rulings are withheld.
    `query` is the stripped user question (rulings read as plainer English than
    the CR-vocabulary rewrite, so the raw question is the better ruling query)."""
    if not card.rulings:
        return []
    embs = _card_ruling_embeddings(card)     # (R, dim), normalized
    qvec = embed_query(query, RULING_MODEL)  # (dim,), normalized
    scores = embs @ qvec                     # cosine per ruling (both normalized)
    return _select_from_scores(scores, floor, top_n)


def select_rulings_union(card: Card, queries: list[str], floor: float = COSINE_FLOOR,
                         top_n: int = TOP_N + 1) -> list[tuple[int, float]]:
    """MEASUREMENT ONLY -- the rewrite-as-ruling-query eval ARM (docs/plan-l1-
    crossref-expansion.md Part B), not the shipped path. `select_rulings`
    embeds the raw question only; this scores each ruling against EVERY query
    in `queries` (typically [raw_question] + the Haiku rewrite string(s)) and
    keeps the MAX cosine per ruling -- a ruling can clear the floor via
    whichever phrasing (plain English or rules vocabulary) actually matches
    it. `top_n` defaults to TOP_N + 1 (4) rather than TOP_N (3): a union of
    two query angles surfacing one more candidate is the point, but still
    capped so it can't flood the prompt the way an uncapped union could.

    Cost: one extra cached query embedding per rewrite string (ruling
    embeddings themselves are already cached/frozen) -- `queries` should be
    passed already-deduplicated; a caller repeating the raw question inside
    `queries` just wastes one redundant (but cached) embed call."""
    if not card.rulings or not queries:
        return []
    embs = _card_ruling_embeddings(card)  # (R, dim), normalized
    qvecs = [embed_query(q, RULING_MODEL) for q in queries]  # each (dim,), normalized
    all_scores = np.stack([embs @ qv for qv in qvecs], axis=0)  # (Q, R)
    scores = all_scores.max(axis=0)  # (R,) -- best angle per ruling
    return _select_from_scores(scores, floor, top_n)
