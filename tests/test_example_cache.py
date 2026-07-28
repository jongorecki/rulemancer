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


def _warm(question: str, agent: _FakeAgent, cookie: str | None = None) -> None:
    """Populate the cache exactly the way scripts/warm_examples.py does:
    call the real route once and store its response."""
    req = main.AnswerRequest(question=question)
    resp = main.answer(req, request=_fake_request(cookie=cookie))
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
    _warm(q, agent, cookie=token)  # this warm call itself counts as query #1

    req = main.AnswerRequest(question=q)
    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True
    events = events_for_code(db, code_id)  # newest first
    assert len(events) == 2  # the warm call's event, then this cache-hit's event
    assert events[0]["cost_usd"] == 0.0
    assert events[0]["cost_usd"] is not None
