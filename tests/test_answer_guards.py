# Slice 4 Task 5 (cookie requirement + event logging only -- per-code cap is
# Task 6, budget breaker is Task 7). Same in-process route-function
# convention as tests/test_api_debug.py; a fake agent stands in for the real
# RulesAgent so no network/API key is needed.

import pytest
from fastapi import Request

from rulesagent.api import main
from rulesagent.contracts import Answer
from rulesagent.demo_db import create_code, events_for_code, get_code_by_value


class _FakeAgent:
    model = "claude-opus-5"

    def __init__(self):
        self.last_cards = []
        self.last_retrieved = []
        self.last_rewritten = None
        self.last_ruling_selection = {}
        self.last_unresolved_refs = []
        self.last_uncited_success = False
        self.last_fuzzy_fallbacks = []
        self.last_usage = {"input_tokens": 500, "output_tokens": 200,
                            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        self.call_count = 0  # fix round 1 finding 1: rejection tests assert
        # this stays 0 -- a refactor that moved a guard's `return` below the
        # agent.answer() call would spend money on unauthenticated requests
        # while every status-code-only assertion kept passing.

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


def test_gate_disabled_answer_works_without_cookie(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    req = main.AnswerRequest(question="Does trample get through deathtouch?")
    resp = main.answer(req, request=_fake_request())
    assert resp.answered is True


def test_gate_enabled_no_cookie_returns_friendly_401(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    monkeypatch.setattr(main, "DEMO_DB", tmp_path / "demo.db")
    req = main.AnswerRequest(question="Does trample get through deathtouch?")

    resp = main.answer(req, request=_fake_request(cookie=None))

    assert resp.status_code == 401
    assert b"<html" in resp.body.lower()


def test_gate_enabled_valid_cookie_answers_and_logs_query_event(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")
    req = main.AnswerRequest(question="Does trample get through deathtouch?")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True
    events = events_for_code(db, code_id)
    assert len(events) == 1
    assert events[0]["question"] == "Does trample get through deathtouch?"
    assert events[0]["input_tokens"] == 500
    assert events[0]["output_tokens"] == 200
    assert events[0]["cost_usd"] > 0


def test_gate_enabled_revoked_code_returns_friendly_403(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_db import revoke_code
    from rulesagent.demo_auth import sign_session
    revoke_code(db, code_id)
    token = sign_session(code_id, "test-secret")
    req = main.AnswerRequest(question="q")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code == 403


# --- Fix round 1, finding 1 -------------------------------------------------
# The real specification of this task: every rejection path must return
# before agent.answer() is ever invoked, expressed as an assertion on a
# call counter rather than just on the HTTP status code.


@pytest.mark.parametrize("case", ["no_cookie", "malformed_cookie", "expired_cookie",
                                   "wrong_key_cookie", "revoked_code"])
def test_rejections_never_call_the_model(monkeypatch, tmp_path, _fake_agent, case):
    import time as time_mod

    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import revoke_code

    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")

    if case == "no_cookie":
        token = None
    elif case == "malformed_cookie":
        token = "not-a-valid-session-token"
    elif case == "expired_cookie":
        stale_issued_at = int(time_mod.time()) - main.COOKIE_MAX_AGE_S - 3600
        token = sign_session(code_id, "test-secret", issued_at=stale_issued_at)
    elif case == "wrong_key_cookie":
        token = sign_session(code_id, "a-different-secret")
    else:  # revoked_code
        revoke_code(db, code_id)
        token = sign_session(code_id, "test-secret")

    req = main.AnswerRequest(question="Does trample get through deathtouch?")
    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code in (401, 403)
    assert _fake_agent.call_count == 0


# --- Fix round 1, finding 2 -------------------------------------------------
# Once the model call has succeeded, real money is already spent -- a
# failure anywhere in the post-call bookkeeping (cost calc, ip hashing,
# enrichment) must still leave a `query` event row behind, and must not
# turn a successful answer into a 500 for the caller.


def test_post_call_cost_calc_failure_still_writes_query_event_and_answers(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")
    req = main.AnswerRequest(question="Does trample get through deathtouch?")

    def _boom(*a, **kw):
        raise RuntimeError("pricing table exploded")

    monkeypatch.setattr(main, "cost_usd", _boom)

    resp = main.answer(req, request=_fake_request(cookie=token))

    # The model already answered -- a bookkeeping failure must not surface
    # as a 500 to the caller.
    assert resp.answered is True

    events = events_for_code(db, code_id)
    assert len(events) == 1
    assert events[0]["question"] == "Does trample get through deathtouch?"
    assert events[0]["input_tokens"] == 500
    assert events[0]["output_tokens"] == 200
    # cost_usd is genuinely unknown here -- recorded as a visible gap
    # (None/NULL), never a fabricated number.
    assert events[0]["cost_usd"] is None
