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


def test_unexpected_exception_on_json_api_route_returns_json_not_html(monkeypatch):
    # Fix-round-1: /answer's frontend caller does `await r.json()` -- an HTML
    # body on an unexpected 500 would throw a parse error there instead of
    # showing the friendly message. Task 14: a missing/not-yet-loaded agent
    # (no lifespan run) is no longer this scenario -- that's now a deliberate,
    # friendly 503 via _require_agent() (Fly's empty-volume-on-first-boot
    # case, task-14-brief.md). So force a genuinely unexpected exception a
    # different way: stub `agent` in as a ready-but-broken object, which
    # passes the readiness check but blows up with AttributeError inside
    # agent.answer() deeper in the route -- still not one of the deliberate
    # guard HTTPExceptions. Confirm the JSON API path gets a JSON body with
    # no leaked internals.
    for var in ("COOKIE_SECRET", "IP_HASH_SALT", "DEMO_ORIGIN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setitem(main._state, "agent", object())
    monkeypatch.setitem(main._state, "chunk_map", {})
    client = TestClient(main.app, raise_server_exceptions=False)
    resp = client.post("/answer", json={"question": "what is trample"})

    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert "detail" in body
    assert "AttributeError" not in body["detail"]
    assert "agent" not in body["detail"]


def test_unexpected_exception_on_page_route_still_returns_friendly_html(monkeypatch):
    # A caller that explicitly asks for HTML (a real browser navigation) must
    # still get the friendly page, not a JSON body -- same unexpected
    # exception, different Accept header. Same stub-agent approach as above
    # (see its comment) now that a missing agent is its own deliberate 503.
    for var in ("COOKIE_SECRET", "IP_HASH_SALT", "DEMO_ORIGIN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setitem(main._state, "agent", object())
    monkeypatch.setitem(main._state, "chunk_map", {})
    client = TestClient(main.app, raise_server_exceptions=False)
    resp = client.post(
        "/answer",
        json={"question": "what is trample"},
        headers={"Accept": "text/html,application/xhtml+xml"},
    )

    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "AttributeError" not in body
    assert "<html" in body.lower()
