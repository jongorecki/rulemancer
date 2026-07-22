"""Per-card ruling relevance retrieval -- a mini-RAG over each [card]'s own
rulings (docs/plan-rulings-on-demand.md).

Replaces the wholesale ruling dump. Embed a card's rulings, keep only the few
most relevant to the question. WITHHOLD by default: if nothing clears the
relevance floor, no rulings are included and the rules-RAG + oracle text stand
alone. The grounding call (Jon): the need-signal comes from the corpus
(relevance to the question), not from the model's self-assessed confidence --
which is why this always runs rather than gating on a low-confidence answer.
"""

import json

import numpy as np

from rulesagent.cache import KVCache
from rulesagent.contracts import Card
from rulesagent.index.embed import embed_documents, embed_query

RULING_MODEL = "voyage-4-large"  # same embedding space as the rules index
TOP_N = 3
# Cap the number of rulings included, so a card carrying ~25 near-duplicate
# mechanic-boilerplate rulings (a Duskmourn Room) can't flood the prompt even if
# several clear the floor.

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
# keyed by oracle_id#index -> JSON list[float] embedding (matches the old
# format). Frozen once written -- embeddings are stable enough and we want
# reproducible SELECTION. Per-op connections fix the old load-whole-dict /
# dump-whole-dict cache race (never run two writers at once -- now moot).


def ruling_id(card: Card, i: int) -> str:
    """Stable id for one ruling: oracle_id + its index in the card's rulings
    list. Survives reprints (oracle_id is cross-printing) and is what the
    rulings-recall gold points at."""
    return f"{card.oracle_id}#{i}"


def _card_ruling_embeddings(card: Card) -> np.ndarray:
    """(R, dim) L2-normalized embeddings for card.rulings, cached per
    oracle_id#index. Only uncached rulings hit the API."""
    ids = [ruling_id(card, i) for i in range(len(card.rulings))]
    cached = {rid: _cache.get(rid) for rid in ids}
    missing = [(i, card.rulings[i]) for i, rid in enumerate(ids) if cached[rid] is None]
    if missing:
        embs = embed_documents([t for _, t in missing], RULING_MODEL)
        for (i, _), vec in zip(missing, embs):
            value = json.dumps(vec.tolist()).encode("utf-8")
            _cache.put(ids[i], value)
            cached[ids[i]] = value
    return np.array([json.loads(cached[rid]) for rid in ids], dtype=np.float32)


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
    out: list[tuple[int, float]] = []
    for i in np.argsort(-scores):
        if float(scores[i]) < floor:
            break
        out.append((int(i), float(scores[i])))
        if len(out) >= top_n:
            break
    return out
