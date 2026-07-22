"""Prompt byte-identity guard (docs/plan-openrouter-models.md).

The OpenRouter A/B arms are only meaningful if every backend generates from
the EXACT prompt the pinned Anthropic path sees. The fixture
(tests/fixtures/prompt_identity.json) was captured from the pre-refactor
inline assembly; these tests re-run the full RulesAgent path with a
recording fake client and assert the assembled (system, user) pair is
byte-identical. Needs the local data assets (vector store + warm caches) --
skipped on a clean clone, where the parser/chunker suites still run.
"""
import json
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "prompt_identity.json"
STORE = REPO / "data" / "parsed" / "vector_voyage-4-large.pkl"

pytestmark = pytest.mark.skipif(
    not (FIXTURE.exists() and STORE.exists()),
    reason="needs the local vector store + warm caches (dev machine only)",
)


class _Recorded(Exception):
    pass


class _RecordingClient:
    def __init__(self):
        self.messages = self

    def parse(self, **kwargs):
        self.kwargs = kwargs
        raise _Recorded


class _FrozenStore:
    """A store stand-in whose .search() always returns a fixed, pre-captured
    retrieved list, ignoring the query. Used to remove q001's only source of
    run-to-run flake -- the live path's fresh Voyage query embedding -- while
    everything downstream of retrieval (rewrite cache, build_prompt, the
    final client call) still runs for real. The frozen list itself was
    captured once, offline, from the current code (see git history for the
    one-off capture script; not committed -- same "capture once, freeze it"
    idea as tests/fixtures/prompt_identity.json itself)."""

    def __init__(self, retrieved):
        self._retrieved = retrieved

    def search(self, query, k):
        return self._retrieved[:k]


@pytest.fixture(scope="module")
def baseline():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def store():
    from rulesagent.index.store import VectorStore
    return VectorStore.load(STORE)


def _capture(store, question):
    from rulesagent.generate.answer import RulesAgent
    client = _RecordingClient()
    agent = RulesAgent(store, client=client, card_no_refresh=True)
    with pytest.raises(_Recorded):
        agent.answer(question)
    return client.kwargs


def test_q001_prompt_is_byte_identical(baseline):
    """Rules-only question: the whole assembled request must match a frozen
    capture byte for byte, given a FROZEN retrieved list (tests/fixtures/
    prompt_identity.json's "retrieved"). q001's retrieval sits at a rank
    boundary, so the live path's documented Voyage embedding wobble
    occasionally flips a chunk in the pool -- a retrieval concern, not an
    assembly one. Freezing the retrieved pool removes that flake at the
    source instead of chasing it in the assertion, the way c015 below does
    for a card question (there the retrieval-dependent prefix is skipped
    over; here, for a rules-only question, the entire message IS that
    prefix, so there's nothing stable left to compare against without
    freezing retrieval itself)."""
    from rulesagent.contracts import Chunk, Retrieved

    expect = baseline["q001"]
    retrieved = [
        Retrieved(chunk=Chunk(**r["chunk"]), score=r["score"])
        for r in expect["retrieved"]
    ]
    kw = _capture(_FrozenStore(retrieved), expect["question"])
    assert kw["system"] == expect["system"]
    assert kw["messages"] == expect["messages"]
    assert kw["model"] == expect["model"]
    assert kw["max_tokens"] == expect["max_tokens"]


def test_c015_prompt_identity_outside_retrieval_wobble(baseline, store):
    """Card question: the LIVE path embeds the query fresh per call and
    Voyage embeddings wobble run-to-run (the exact reason the eval froze
    query embeddings -- DECISIONS 2026-07-21), so a boundary-rank rule chunk
    can differ between runs. Assert byte identity for everything the
    assembly owns: the system prompt, the prompt skeleton, and the entire
    card-data + question tail (enrichment, selected rulings, question)."""
    expect = baseline["c015"]
    kw = _capture(store, expect["question"])
    assert kw["system"] == expect["system"]
    new = kw["messages"][0]["content"]
    old = expect["messages"][0]["content"]
    assert new.startswith("Rules context:\n")
    marker = "\n\nCard data:\n"
    assert marker in new and marker in old
    assert new.split(marker, 1)[1] == old.split(marker, 1)[1]


def test_build_prompt_multiturn_shape():
    """The convo_ctx arm: transcript block prepends the user message and the
    system prompt gains exactly the context-reading line. Pure-function test,
    no data assets needed -- so guard it separately from the module skip."""
    from rulesagent.generate.answer import SYSTEM, build_prompt

    sys_single, user_single = build_prompt("q?", [], [], convo_ctx=None)
    sys_multi, user_multi = build_prompt("q?", [], [], convo_ctx="User: hi\nAssistant: hello")

    assert sys_single == SYSTEM
    assert sys_multi.startswith(SYSTEM)
    assert "transcript at the top" in sys_multi
    assert user_multi == ("Conversation so far (for context only):\n"
                          "User: hi\nAssistant: hello\n\n" + user_single)


def test_build_prompt_rewrite_block_appends():
    from rulesagent.generate.answer import build_prompt

    _, base = build_prompt("q?", [], [], convo_ctx=None)
    _, with_rw = build_prompt("q?", [], [], convo_ctx=None, rewrite_queries=["alpha", "beta"])
    assert with_rw.startswith(base)
    assert "- alpha\n- beta" in with_rw
