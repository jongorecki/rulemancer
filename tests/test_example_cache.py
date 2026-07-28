# Slice: warmed-example cache (.superpowers/sdd/2026-07-27-gated-demo/
# task-caching-report.md, Change 1). Same in-process route-function
# convention as tests/test_answer_guards.py/tests/test_api_debug.py -- a
# fake agent (with a fake store attached, since the cache key needs a
# corpus/index identity) stands in for the real RulesAgent, and
# main._example_cache is monkeypatched to a tmp-path KVCache so tests never
# touch the real data/cache.db.

import pytest
from fastapi import Request

from rulesagent.api import main
from rulesagent.cache import KVCache
from rulesagent.contracts import Answer
from rulesagent.demo_db import create_code, events_for_code


class _FakeStore:
    model = "fake-vector-model"
    chunks = []


class _FakeAgent:
    model = "claude-opus-5"
    effort = "low"
    system_version = 3
    rewrite_version = "v2"

    def __init__(self):
        self.store = _FakeStore()
        self.last_cards = []
        self.last_retrieved = []
        self.last_rewritten = None
        self.last_ruling_selection = {}
        self.last_unresolved_refs = []
        self.last_uncited_success = False
        self.last_fuzzy_fallbacks = []
        self.last_usage = {"input_tokens": 500, "output_tokens": 200,
                            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        self.call_count = 0

    def answer(self, question, history=None):
        self.call_count += 1
        return Answer(text="An honest answer.", tldr="tldr", citations=[],
                       answered=True, suggested_followups=[])


def _fake_request(cookie: str | None = None) -> Request:
    headers = [(b"cookie", f"{main.COOKIE_NAME}={cookie}".encode())] if cookie else []
    scope = {"type": "http", "headers": headers, "client": ("203.0.113.9", 12345),
              "method": "POST", "path": "/answer"}
    return Request(scope)


@pytest.fixture(autouse=True)
def _fake_agent(monkeypatch):
    agent = _FakeAgent()
    monkeypatch.setitem(main._state, "agent", agent)
    monkeypatch.setitem(main._state, "chunk_map", {})
    return agent


@pytest.fixture(autouse=True)
def _isolated_example_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "_example_cache",
                         KVCache("example_answer_cache", db_path=tmp_path / "cache.db"))
    monkeypatch.delenv("COOKIE_SECRET", raising=False)


def _warm(question: str, agent: _FakeAgent) -> None:
    """Populate the cache exactly the way scripts/warm_examples.py does
    (fix round, 2026-07-28): call generate_example_answer() directly -- no
    Request, no HTTP route, no gating -- and store its response. Works
    identically whether or not COOKIE_SECRET is set, unlike the old warm
    path (routing through main.answer()), which crashed in production once
    gating was on because there is no Request to hash a client IP off of
    outside a real HTTP call."""
    resp = main.generate_example_answer(question, agent, {})
    payload = main._response_to_cache_payload(resp, agent)
    main._store_example_cache(question, agent, payload)


def test_cached_first_turn_returns_cached_answer_without_calling_model(_fake_agent):
    q = "If my creature has trample and deathtouch, how much damage can trample over the blocker?"
    _warm(q, _fake_agent)
    calls_after_warm = _fake_agent.call_count
    assert calls_after_warm == 1  # the warm call itself hit the (empty) cache and generated once

    req = main.AnswerRequest(question=q)
    resp = main.answer(req, request=_fake_request())

    assert _fake_agent.call_count == calls_after_warm  # no new model call
    assert resp.answered is True
    assert resp.answer == "An honest answer."


def test_followup_with_history_never_hits_cache(_fake_agent):
    q = "Can I respond to a land being played?"
    _warm(q, _fake_agent)
    calls_after_warm = _fake_agent.call_count

    req = main.AnswerRequest(
        question=q,
        history=[{"role": "user", "content": "Some earlier turn."}],
    )
    main.answer(req, request=_fake_request())

    # A follow-up's answer depends on the transcript -- a cache keyed on
    # question text alone would answer the wrong question, so this must
    # always call the model even though the question text matches a warmed
    # entry byte-for-byte.
    assert _fake_agent.call_count == calls_after_warm + 1


def test_changed_config_stamp_misses_cache(_fake_agent):
    q = "How does cascade interact with the stack?"
    _warm(q, _fake_agent)
    calls_after_warm = _fake_agent.call_count

    # Simulate a generator-effort change between the warm run and this
    # request -- same question text, different pipeline config. A stale hit
    # here would show a visitor an answer the CURRENT config would not
    # produce.
    _fake_agent.effort = "high"

    req = main.AnswerRequest(question=q)
    main.answer(req, request=_fake_request())

    assert _fake_agent.call_count == calls_after_warm + 1


def test_cached_hit_writes_query_event_with_cost_zero_not_null(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")

    agent = main._state["agent"]
    q = "If I copy [Emrakul, the Promised End]'s cast trigger, do I control two turns?"
    _warm(q, agent)  # bypasses code_row entirely -- writes no event of its own

    req = main.AnswerRequest(question=q)
    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True
    events = events_for_code(db, code_id)
    assert len(events) == 1  # only this cache-hit's event -- warming wrote none
    assert events[0]["cost_usd"] == 0.0
    assert events[0]["cost_usd"] is not None


# --- fix round, 2026-07-28: warming crashed in production once gating was
# on, because the old warm path called main.answer(req) with no Request --
# fine locally where COOKIE_SECRET is unset (gating off, the branch that
# needs a Request never runs), fatal in production where it does. The fix
# is generate_example_answer(): an operator entry point that runs the same
# agent/generation + response-building logic as /answer, but never touches
# Request, gating, guards, or telemetry at all.


def test_generate_example_answer_works_when_gated_and_no_request(monkeypatch, tmp_path):
    """The exact crash this fix round exists to close: gating ON (as in
    production), no Request object anywhere in the call. Must not raise."""
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    agent = main._state["agent"]

    resp = main.generate_example_answer("Can I respond to a land being played?", agent, {})

    assert resp.answered is True
    assert resp.answer == "An honest answer."


def test_generate_example_answer_writes_no_query_event_and_consumes_no_quota(
    monkeypatch, tmp_path,
):
    """Warming must be invisible to a demo code's quota and to the usage
    history /admin shows -- it is an operator action against the cache, not
    demo traffic, even when a real gated code exists."""
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=1)
    agent = main._state["agent"]

    main.generate_example_answer("How does cascade interact with the stack?", agent, {})

    assert events_for_code(db, code_id) == []
    from rulesagent.demo_db import count_queries
    assert count_queries(db, code_id) == 0  # quota untouched


def test_store_and_lookup_both_derive_the_key_via_the_shared_function(monkeypatch):
    """_store_example_cache (what the warm script calls) and
    _lookup_example_cache (what /answer calls) must both go through
    _example_cache_key rather than each computing a key some other way --
    if they ever drifted apart, warming would populate an entry the request
    path can never read, and every visitor would silently keep paying full
    price with no error anywhere. Proven by spying on the shared function
    itself, not by inference from "warm then hit worked" (a coincidental
    match could also produce that)."""
    calls = []
    real_key_fn = main._example_cache_key

    def _spy(question, agent):
        calls.append(question)
        return real_key_fn(question, agent)

    monkeypatch.setattr(main, "_example_cache_key", _spy)
    agent = main._state["agent"]
    q = "Does trample get through deathtouch?"

    main._store_example_cache(q, agent, {"answer": "x", "tldr": "x", "answered": True,
                                          "citations": [], "cards": [],
                                          "suggested_followups": [], "debug": {
                                              "rewrites": [], "retrieved_rules": [],
                                              "selected_ruling_ids": {},
                                              "unresolved_card_refs": [],
                                              "uncited_success": False,
                                              "fuzzy_fallbacks": [],
                                          }})
    main._lookup_example_cache(q, agent)

    assert calls == [q, q]  # both call sites went through the same function
