# Task: book icon -> rule lookup (2026-07-27-gated-demo follow-up). POST
# /rules/lookup mirrors /answer's gating exactly (same in-process
# route-function convention tests/test_answer_guards.py already uses -- see
# that file's module docstring), but is a local, zero-API-cost dict
# lookup/scan against chunk_map, so it must never write a `query` demo_db
# event (that would inflate quota/budget counters for something that never
# touched the model) and must never touch count_queries()/daily_spend() at
# all.

import pytest
from fastapi import Request

from rulesagent.api import main
from rulesagent.contracts import Chunk
from rulesagent.demo_db import create_code, events_for_code


def _fake_request(cookie: str | None = None) -> Request:
    headers = [(b"cookie", f"{main.COOKIE_NAME}={cookie}".encode())] if cookie else []
    scope = {"type": "http", "headers": headers, "client": ("203.0.113.9", 12345),
             "method": "POST", "path": "/rules/lookup"}
    return Request(scope)


def _chunk(source_id, kind, section, text):
    return Chunk(source_id=source_id, kind=kind, section=section, text=text, embed_text=text)


_CHUNK_MAP = {
    "702.85a": _chunk("702.85a", "rule", "Keyword Abilities",
                       "702.85a Landwalk is a static ability."),
    "702.85b": _chunk("702.85b", "rule", "Keyword Abilities",
                       "702.85b Landwalk represents an evasion ability."),
    "104.3": _chunk("104.3", "rule", "The Game",
                     "104.3 A player still in the game wins."),
    "104.3a": _chunk("104.3a", "rule", "The Game",
                      "104.3a A player still in the game wins the game if..."),
    "104.3b": _chunk("104.3b", "rule", "The Game",
                      "104.3b A player still in the game wins the game if..."),
    "Trample": _chunk("Trample", "glossary", "Glossary",
                       "Trample See rule 702.19, \"Trample.\""),
}


@pytest.fixture(autouse=True)
def _fake_agent(monkeypatch):
    monkeypatch.setitem(main._state, "agent", object())
    monkeypatch.setitem(main._state, "chunk_map", dict(_CHUNK_MAP))


def test_gate_disabled_lookup_works_without_cookie(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    req = main.RuleLookupRequest(query="702.85a")
    resp = main.rules_lookup(req, request=_fake_request())
    assert resp.exact is True
    assert resp.results[0].id == "702.85a"


def test_exact_number_lookup_returns_that_rule(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    req = main.RuleLookupRequest(query="104.3b")
    resp = main.rules_lookup(req, request=_fake_request())
    assert resp.exact is True
    assert len(resp.results) == 1
    assert resp.results[0].id == "104.3b"
    assert resp.results[0].kind == "rule"
    assert "still in the game" in resp.results[0].text


def test_number_with_only_lettered_children_lists_them(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    req = main.RuleLookupRequest(query="702.85")
    resp = main.rules_lookup(req, request=_fake_request())
    # 702.85 has no chunk of its own in this fixture (unlike 104.3, which
    # does) -- exercises the "list the lettered children" branch.
    assert resp.exact is False
    ids = {r.id for r in resp.results}
    assert ids == {"702.85a", "702.85b"}


def test_keyword_search_returns_bounded_list(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    req = main.RuleLookupRequest(query="landwalk")
    resp = main.rules_lookup(req, request=_fake_request())
    assert resp.exact is False
    assert 1 <= len(resp.results) <= main.RULE_LOOKUP_MAX_RESULTS
    assert all("landwalk" in r.text.lower() or "landwalk" in r.id.lower() for r in resp.results)


def test_empty_keyword_rejected_cleanly(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    req = main.RuleLookupRequest(query="   ")
    resp = main.rules_lookup(req, request=_fake_request())
    assert resp.status_code == 400


def test_overlong_keyword_rejected_cleanly(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    req = main.RuleLookupRequest(query="x" * (main.RULE_LOOKUP_MAX_QUERY_CHARS + 1))
    resp = main.rules_lookup(req, request=_fake_request())
    assert resp.status_code == 400


def test_unauthenticated_request_refused_when_gated(monkeypatch):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    req = main.RuleLookupRequest(query="104.3b")
    resp = main.rules_lookup(req, request=_fake_request())
    assert resp.status_code == 401


def test_valid_cookie_lookup_works_when_gated(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")
    req = main.RuleLookupRequest(query="104.3b")

    resp = main.rules_lookup(req, request=_fake_request(cookie=token))

    assert resp.exact is True
    assert resp.results[0].id == "104.3b"


def test_lookup_writes_no_events_and_consumes_no_quota(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import count_queries
    token = sign_session(code_id, "test-secret")

    for _ in range(3):
        req = main.RuleLookupRequest(query="104.3b")
        main.rules_lookup(req, request=_fake_request(cookie=token))

    # No `query` events (which is what the per-code cap and the daily USD
    # budget breaker both count/sum), and in fact no events of ANY kind --
    # this route is deliberately silent in demo_db.
    assert count_queries(db, code_id) == 0
    assert events_for_code(db, code_id) == []


def test_revoked_code_still_refused_for_lookup(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import revoke_code
    revoke_code(db, code_id)
    token = sign_session(code_id, "test-secret")
    req = main.RuleLookupRequest(query="104.3b")

    resp = main.rules_lookup(req, request=_fake_request(cookie=token))

    assert resp.status_code == 403
