# Slice 4 Task 9. Unit-tests the origin-list helper directly rather than
# poking CORSMiddleware internals through a live app -- the helper is what
# actually decides the policy; the middleware just consumes its output.
#
# Fix-round-1: also pins the allow_credentials invariant on the REAL
# middleware configuration (not just the helper's return value), because the
# real bug was in how allow_credentials was wired, not in _cors_allow_origins()
# itself. importlib.reload(main) re-executes the module's app.add_middleware()
# call under a controlled env so we can inspect what actually got registered.

import importlib

from rulesagent.api import main


def test_defaults_to_wildcard_when_demo_origin_unset(monkeypatch):
    monkeypatch.delenv("DEMO_ORIGIN", raising=False)
    assert main._cors_allow_origins() == ["*"]


def test_locks_to_demo_origin_when_set(monkeypatch):
    monkeypatch.setenv("DEMO_ORIGIN", "https://rulemancer.fly.dev")
    assert main._cors_allow_origins() == ["https://rulemancer.fly.dev"]


def _cors_middleware_kwargs(app):
    for mw in app.user_middleware:
        if mw.cls.__name__ == "CORSMiddleware":
            return mw.kwargs
    raise AssertionError("CORSMiddleware is not registered on the app")


def test_credentials_off_when_origins_are_wildcarded(monkeypatch):
    # Starlette's CORSMiddleware reflects the caller's own Origin header back
    # (instead of a bare "*") whenever allow_credentials is True -- so
    # wildcard + credentials would let ANY origin make cookie-bearing
    # requests. Must never happen.
    monkeypatch.delenv("DEMO_ORIGIN", raising=False)
    importlib.reload(main)
    try:
        kwargs = _cors_middleware_kwargs(main.app)
        assert kwargs["allow_origins"] == ["*"]
        assert kwargs["allow_credentials"] is False
    finally:
        importlib.reload(main)


def test_credentials_on_and_locked_when_demo_origin_set(monkeypatch):
    monkeypatch.setenv("DEMO_ORIGIN", "https://rulemancer.fly.dev")
    importlib.reload(main)
    try:
        kwargs = _cors_middleware_kwargs(main.app)
        assert kwargs["allow_origins"] == ["https://rulemancer.fly.dev"]
        assert kwargs["allow_credentials"] is True
    finally:
        monkeypatch.delenv("DEMO_ORIGIN", raising=False)
        importlib.reload(main)
