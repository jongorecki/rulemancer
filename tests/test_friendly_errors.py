# Slice 4 Task 10. Exercises the handler function directly -- FastAPI
# exception handlers are plain callables, so no TestClient/ASGI transport is
# needed to verify the body shape (matches this repo's route-function-direct
# testing convention throughout slice 4).

import asyncio

from fastapi.testclient import TestClient

from rulesagent.api import main


def test_deliberate_http_exception_passes_through_with_its_own_status_and_message(monkeypatch):
    # Guard clauses (Tasks 6-8) raise HTTPException with specific status codes
    # and messages -- the global Exception handler must not swallow those into
    # a generic 500. /admin/scryfall/status calls _require_admin_token() first
    # thing, which raises 401 with a specific detail when the token is wrong.
    monkeypatch.setenv("ADMIN_TOKEN", "correct-token")
    client = TestClient(main.app, raise_server_exceptions=False)
    resp = client.get("/admin/scryfall/status", headers={"Authorization": "Bearer wrong-token"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing or invalid admin token"


def test_unhandled_exception_returns_friendly_html_not_a_stack_trace():
    resp = asyncio.run(main._unhandled_exception_handler(None, RuntimeError("db connection reset")))

    assert resp.status_code == 500
    body = resp.body.decode()
    assert "db connection reset" not in body  # no raw exception text leaked to the client
    assert "<html" in body.lower()


def test_handler_is_registered_on_the_app():
    assert Exception in main.app.exception_handlers
