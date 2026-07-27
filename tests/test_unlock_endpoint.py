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
    # _unlock_attempts is module-level state keyed by hashed IP -- every
    # test in this file uses the same fake client IP (203.0.113.9), so
    # without a reset, unlock() calls from earlier tests in the same run
    # accumulate and trip UNLOCK_RATE_LIMIT for later ones (same convention
    # as tests/test_unlock_rate_limit.py's _reset_rate_limiter fixture).
    main._unlock_attempts.clear()
    yield db
    main._unlock_attempts.clear()


def test_unlock_valid_code_fetch_style_returns_json_and_sets_cookie(_demo_env):
    # gate.html's own fetch() call -- marks itself with both headers (see
    # _unlock_wants_json in main.py) so it keeps the JSON/no-full-reload
    # path even when the browser's default fetch Accept is ambiguous.
    resp = main.unlock(
        code="raptor-quill-42",
        request=_fake_request({"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}),
    )

    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/json")
    set_cookie = resp.headers.get("set-cookie", "")
    assert main.COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie


def test_unlock_valid_code_browser_post_returns_303_and_sets_cookie(_demo_env):
    # No-JS front door: a native <form method="post" action="/unlock">
    # submit sends Accept: text/html,... (browsers' real default for a
    # navigation) and no fetch marker. It must land the visitor on the app
    # via a redirect, never show raw JSON to a human.
    resp = main.unlock(
        code="raptor-quill-42",
        request=_fake_request({"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}),
    )

    assert resp.status_code == 303
    assert resp.headers.get("location") == "/"
    set_cookie = resp.headers.get("set-cookie", "")
    assert main.COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie


def test_unlock_valid_code_no_signal_at_all_defaults_to_303(_demo_env):
    # An unknown caller with no Accept header and no fetch marker (e.g. a
    # plain curl POST) gets the safe default: HTML/redirect, not JSON. This
    # is the fix for the reported bug -- the old code always returned JSON
    # here regardless of caller, so a script failure on the visitor's
    # machine left the gate silently broken.
    resp = main.unlock(code="raptor-quill-42", request=_fake_request())

    assert resp.status_code == 303
    assert resp.headers.get("location") == "/"


def test_unlock_cookie_attributes_unchanged(_demo_env):
    resp = main.unlock(
        code="raptor-quill-42",
        request=_fake_request({"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}),
    )
    set_cookie = resp.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    assert "Path=/" in set_cookie


def test_unlock_logs_an_unlock_event(_demo_env):
    main.unlock(code="raptor-quill-42", request=_fake_request())
    row = get_code_by_value(_demo_env, "raptor-quill-42")
    from rulesagent.demo_db import code_stats
    assert code_stats(_demo_env, row["id"])["unlocks"] == 1


def test_unlock_invalid_code_browser_post_returns_friendly_html(_demo_env):
    resp = main.unlock(code="not-a-real-code-00", request=_fake_request())
    assert resp.status_code == 403
    assert b"<html" in resp.body.lower() or b"<!doctype" in resp.body.lower()
    # Styled with the plum design tokens, not the old hardcoded greys --
    # never raw/unstyled JSON shown to a human.
    assert b"colors_and_type.css" in resp.body


def test_unlock_invalid_code_fetch_style_returns_json(_demo_env):
    resp = main.unlock(
        code="not-a-real-code-00",
        request=_fake_request({"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}),
    )
    assert resp.status_code == 403
    assert resp.headers.get("content-type", "").startswith("application/json")


def test_unlock_rate_limited_browser_post_returns_friendly_429(_demo_env):
    import time
    from rulesagent.demo_auth import hash_ip

    # The rate limiter keys on the hashed client IP -- _fake_request() always
    # uses 203.0.113.9, so hash that same value to pre-trip the limiter.
    real_ip_hash = hash_ip("203.0.113.9", main.ip_hash_salt())
    with main._unlock_rl_lock:
        main._unlock_attempts[real_ip_hash] = [time.time()] * (main.UNLOCK_RATE_LIMIT + 5)

    resp = main.unlock(code="raptor-quill-42", request=_fake_request())
    assert resp.status_code == 429
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
