# Slice 4 Task 4: "/" serves the gate page when ungated, the real frontend
# once a valid session cookie is presented.

import pytest
from fastapi import Request

from rulesagent.api import main


def _fake_request(cookie: str | None = None) -> Request:
    headers = [(b"cookie", f"{main.COOKIE_NAME}={cookie}".encode())] if cookie else []
    scope = {"type": "http", "headers": headers, "client": ("203.0.113.9", 12345),
              "method": "GET", "path": "/"}
    return Request(scope)


def test_gate_disabled_serves_real_index(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    resp = main._index(request=_fake_request())
    assert resp.path.name == "index.html"


def test_gate_enabled_no_cookie_serves_gate_page(monkeypatch):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    resp = main._index(request=_fake_request())
    assert resp.path.name == "gate.html"


def test_gate_enabled_invalid_cookie_serves_gate_page(monkeypatch):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    resp = main._index(request=_fake_request(cookie="garbage"))
    assert resp.path.name == "gate.html"


def test_gate_enabled_valid_cookie_serves_real_index(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    from rulesagent.demo_db import create_code
    code_id = create_code(db, "test-code-01", "Test")
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")

    resp = main._index(request=_fake_request(cookie=token))

    assert resp.path.name == "index.html"
