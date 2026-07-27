# Slice 4 Task 4. Same in-process convention as tests/test_admin_scryfall_
# endpoints.py: route functions called directly, no TestClient/lifespan.

import pytest
from fastapi import HTTPException, Request

from rulesagent.api import main
from rulesagent.demo_db import get_code_by_value, log_event


class _FakeClient:
    host = "203.0.113.9"


def _fake_request(headers: dict | None = None) -> Request:
    scope = {
        "type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": ("203.0.113.9", 12345), "method": "POST", "path": "/unlock",
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _demo_env(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    monkeypatch.setattr(main, "DEMO_DB", db)
    from rulesagent.demo_db import create_code
    create_code(db, "raptor-quill-42", "Test Person", max_queries=25)
    yield db


def test_unlock_valid_code_sets_cookie_and_returns_ok(_demo_env):
    resp = main.unlock(code="raptor-quill-42", request=_fake_request())

    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert main.COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie


def test_unlock_logs_an_unlock_event(_demo_env):
    main.unlock(code="raptor-quill-42", request=_fake_request())
    row = get_code_by_value(_demo_env, "raptor-quill-42")
    from rulesagent.demo_db import code_stats
    assert code_stats(_demo_env, row["id"])["unlocks"] == 1


def test_unlock_invalid_code_returns_friendly_403(_demo_env):
    resp = main.unlock(code="not-a-real-code-00", request=_fake_request())
    assert resp.status_code == 403
    assert b"<html" in resp.body.lower() or b"<!doctype" in resp.body.lower()


def test_unlock_invalid_code_logs_denied_event(_demo_env):
    main.unlock(code="not-a-real-code-00", request=_fake_request())
    # code_id is None for a denied unlock (spec) -- verified via a direct
    # query since there's no code row to hang code_stats off of.
    import sqlite3
    conn = sqlite3.connect(_demo_env)
    try:
        row = conn.execute("SELECT kind, code_id FROM events WHERE kind = 'denied'").fetchone()
    finally:
        conn.close()
    assert row == ("denied", None)


def test_unlock_revoked_code_returns_friendly_403(_demo_env):
    row = get_code_by_value(_demo_env, "raptor-quill-42")
    from rulesagent.demo_db import revoke_code
    revoke_code(_demo_env, row["id"])

    resp = main.unlock(code="raptor-quill-42", request=_fake_request())

    assert resp.status_code == 403


def test_unlock_missing_cookie_secret_returns_503(_demo_env, monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        main.unlock(code="raptor-quill-42", request=_fake_request())
    assert exc.value.status_code == 503


def test_unlock_missing_ip_hash_salt_returns_503(_demo_env, monkeypatch):
    monkeypatch.delenv("IP_HASH_SALT", raising=False)
    with pytest.raises(HTTPException) as exc:
        main.unlock(code="raptor-quill-42", request=_fake_request())
    assert exc.value.status_code == 503
