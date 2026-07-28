# Query-embedding cache (task-caching-report.md Change 2). A latency
# optimization only -- embed_query() costs ~$0.000005/call, essentially
# nothing next to a ~$0.0485 generation call, so these tests check call
# counts and correctness, not cost.

import numpy as np
import pytest

from rulesagent.cache import KVCache
from rulesagent.contracts import Chunk
from rulesagent.index import store as store_mod
from rulesagent.index.store import VectorStore


def _make_store() -> VectorStore:
    chunks = [
        Chunk(source_id="100.1", kind="rule", section="Game Concepts",
              text="Rule one.", embed_text="Rule one."),
        Chunk(source_id="100.2", kind="rule", section="Game Concepts",
              text="Rule two.", embed_text="Rule two."),
    ]
    embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    return VectorStore(model="test-model", chunks=chunks, embeddings=embeddings)


@pytest.fixture(autouse=True)
def _isolated_query_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(store_mod, "_query_emb_cache",
                         KVCache("query_emb", db_path=tmp_path / "cache.db"))


def _counting_embed_query(monkeypatch):
    calls = {"n": 0}

    def _fake(query: str, model: str) -> np.ndarray:
        calls["n"] += 1
        return np.array([1.0, 0.0], dtype=np.float32)

    monkeypatch.setattr(store_mod, "embed_query", _fake)
    return calls


def test_repeated_search_same_query_embeds_once(monkeypatch):
    calls = _counting_embed_query(monkeypatch)
    vs = _make_store()

    vs.search("Does trample get through deathtouch?", k=1)
    vs.search("Does trample get through deathtouch?", k=1)
    vs.search("Does trample get through deathtouch?", k=1)

    assert calls["n"] == 1


def test_different_query_text_embeds_again(monkeypatch):
    calls = _counting_embed_query(monkeypatch)
    vs = _make_store()

    vs.search("question A", k=1)
    vs.search("question B", k=1)

    assert calls["n"] == 2


def test_search_returns_correct_results_from_cached_vector(monkeypatch):
    _counting_embed_query(monkeypatch)
    vs = _make_store()

    first = vs.search("Does trample get through deathtouch?", k=1)
    second = vs.search("Does trample get through deathtouch?", k=1)

    assert first[0].chunk.source_id == second[0].chunk.source_id == "100.1"
    assert first[0].score == pytest.approx(second[0].score)


def test_search_vec_never_calls_embed_query(monkeypatch):
    """The eval harness passes an already-embedded, cached vector via
    search_vec() for reproducibility (docstring: repeated live embed_query()
    calls for the same text can return slightly different vectors, wobbling
    ranks at the top-k boundary). This cache sits only in front of search()'s
    own embed_query() call -- search_vec() must remain a pure function of the
    vector it's given, calling embed_query() zero times."""
    calls = _counting_embed_query(monkeypatch)
    vs = _make_store()

    qvec = np.array([0.0, 1.0], dtype=np.float32)
    result = vs.search_vec(qvec, k=1)

    assert calls["n"] == 0
    assert result[0].chunk.source_id == "100.2"
