# Slice 4 Task 9. Unit-tests the origin-list helper directly rather than
# poking CORSMiddleware internals through a live app -- the helper is what
# actually decides the policy; the middleware just consumes its output.

from rulesagent.api import main


def test_defaults_to_wildcard_when_demo_origin_unset(monkeypatch):
    monkeypatch.delenv("DEMO_ORIGIN", raising=False)
    assert main._cors_allow_origins() == ["*"]


def test_locks_to_demo_origin_when_set(monkeypatch):
    monkeypatch.setenv("DEMO_ORIGIN", "https://rulemancer.fly.dev")
    assert main._cors_allow_origins() == ["https://rulemancer.fly.dev"]
