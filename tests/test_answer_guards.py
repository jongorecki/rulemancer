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

    def answer(self, question, history=None):
        return Answer(text="An honest answer.", tldr="tldr", citations=[],
                       answered=True, suggested_followups=[])


def _fake_request(cookie: str | None = None) -> Request:
    headers = [(b"cookie", f"{main.COOKIE_NAME}={cookie}".encode())] if cookie else []
    scope = {"type": "http", "headers": headers, "client": ("203.0.113.9", 12345),
              "method": "POST", "path": "/answer"}
    return Request(scope)


@pytest.fixture(autouse=True)
def _fake_agent(monkeypatch):
    monkeypatch.setitem(main._state, "agent", _FakeAgent())
    monkeypatch.setitem(main._state, "chunk_map", {})


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
