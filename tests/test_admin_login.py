# Task: browser login for /admin (.superpowers/sdd/2026-07-27-gated-demo/
# task-admin-login-report.md). /admin is protected by _require_admin_token,
# which only reads an Authorization: Bearer header -- unreachable from a
# browser address bar. This adds GET /admin rendering a login form when
# there's no valid auth, and POST /admin/login setting a signed admin
# session cookie distinct from the demo visitor's session cookie.
#
# Same in-process route-function convention as test_admin_demo_view.py /
# test_unlock_endpoint.py: call the FastAPI route functions directly, no
# TestClient/lifespan needed.

from fastapi import HTTPException
import pytest

from rulesagent.api import main
from rulesagent.demo_db import create_code


@pytest.fixture(autouse=True)
def _admin_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    yield db


def test_bearer_header_still_reaches_admin_page():
    """The existing Authorization: Bearer path must keep working unchanged --
    Scryfall admin endpoints and any scripts rely on it."""
    resp = main.admin_demo_view(authorization="Bearer secret-token")
    assert resp.status_code == 200
    body = resp.body.decode()
    assert "Rulemancer" in body
    assert "demo usage" in body.lower()


def test_no_auth_renders_login_form_not_json_error():
    resp = main.admin_demo_view(authorization=None)
    assert resp.status_code == 401
    body = resp.body.decode()
    # A real HTML page, not FastAPI's default JSON error body.
    assert "<form" in body
    assert '"detail"' not in body
    assert "<html" in body.lower()


def test_no_auth_leaks_no_code_label_question_or_count(_admin_env):
    db = _admin_env
    from rulesagent.demo_db import log_event
    code_id = create_code(db, "raptor-quill-42", "Cribl -- Jane R.", max_queries=25)
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="does trample work", cost_usd=0.03)

    resp = main.admin_demo_view(authorization=None)
    body = resp.body.decode()
    assert "raptor-quill-42" not in body
    assert "Cribl" not in body
    assert "does trample work" not in body
    assert "0.03" not in body


def test_wrong_bearer_token_also_renders_login_form():
    resp = main.admin_demo_view(authorization="Bearer wrong-token")
    assert resp.status_code == 401
    body = resp.body.decode()
    assert "<form" in body


def test_wrong_login_token_rerenders_form_with_generic_error_and_sets_no_cookie():
    resp = main.admin_login(token="wrong-token")
    assert resp.status_code == 401
    body = resp.body.decode()
    assert "<form" in body
    assert "set-cookie" not in {k.lower() for k in resp.headers.keys()}
    # Generic error only -- must not reveal how close the guess was.
    assert "wrong-token" not in body


def test_correct_login_token_sets_cookie_and_redirects():
    resp = main.admin_login(token="secret-token")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin"
    set_cookie = resp.headers.get("set-cookie", "")
    assert main.ADMIN_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    # Distinct from the visitor demo cookie name.
    assert main.ADMIN_COOKIE_NAME != main.COOKIE_NAME


def test_admin_cookie_from_login_grants_access_to_admin_page():
    login_resp = main.admin_login(token="secret-token")
    cookie_value = login_resp.headers["set-cookie"].split(f"{main.ADMIN_COOKIE_NAME}=")[1].split(";")[0]

    resp = main.admin_demo_view(authorization=None, admin_session=cookie_value)
    assert resp.status_code == 200
    assert "demo usage" in resp.body.decode().lower()


def test_demo_visitor_session_cookie_does_not_grant_admin(_admin_env):
    """The important one: a demo visitor's own signed session cookie (proof
    of an unlocked access code, nothing more) must never be accepted as an
    admin session, even though both cookies are signed with the same
    COOKIE_SECRET via the same demo_auth machinery. Built the same way
    unlock() builds a real visitor cookie (sign_session(code_id, secret))
    but without going through unlock() itself, so this doesn't consume the
    shared module-level unlock rate limiter that other tests' fake IP also
    shares."""
    db = _admin_env
    code_id = create_code(db, "raptor-quill-42", "Test Person", max_queries=25)
    visitor_cookie = main.sign_session(code_id, "test-secret")

    # Presented as the ADMIN cookie value, the visitor's session must be
    # rejected -- renders the login form, not the dashboard.
    resp = main.admin_demo_view(authorization=None, admin_session=visitor_cookie)
    assert resp.status_code == 401
    assert "<form" in resp.body.decode()


def test_missing_cookie_secret_yields_503_not_unsigned_cookie(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        main.admin_login(token="secret-token")
    assert exc.value.status_code == 503
