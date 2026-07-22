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
from pathlib import Path

import numpy as np

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

CACHE_PATH = Path(__file__).parent.parent.parent.parent / "data" / "parsed" / "ruling_emb_cache.json"
# oracle_id#index -> embedding (list[float]). Frozen once written -- embeddings
# are stable enough and we want reproducible SELECTION. Same load-whole-dict /
# dump-whole-dict shape as the other caches, so it's SUBJECT TO THE CACHE RACE:
# never run two ruling-embedding-writing processes at once.

_cache: dict | None = None


def _get_cache() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    return _cache


def _save_cache() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(_cache), encoding="utf-8")


def ruling_id(card: Card, i: int) -> str:
    """Stable id for one ruling: oracle_id + its index in the card's rulings
    list. Survives reprints (oracle_id is cross-printing) and is what the
    rulings-recall gold points at."""
    return f"{card.oracle_id}#{i}"


def _card_ruling_embeddings(card: Card) -> np.ndarray:
    """(R, dim) L2-normalized embeddings for card.rulings, cached per
    oracle_id#index. Only uncached rulings hit the API."""
    cache = _get_cache()
    ids = [ruling_id(card, i) for i in range(len(card.rulings))]
    missing = [(i, card.rulings[i]) for i, rid in enumerate(ids) if rid not in cache]
    if missing:
        embs = embed_documents([t for _, t in missing], RULING_MODEL)
        for (i, _), vec in zip(missing, embs):
            cache[ids[i]] = vec.tolist()
        _save_cache()
    return np.array([cache[rid] for rid in ids], dtype=np.float32)


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
