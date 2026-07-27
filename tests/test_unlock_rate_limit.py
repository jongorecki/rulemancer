# Slice 4 Task 8. Directly exercises _check_unlock_rate_limit (unit-level)
# plus the /unlock route end to end for the 429 path.

import pytest
from fastapi import Request

from rulesagent.api import main
from rulesagent.demo_db import create_code


def _fake_request() -> Request:
    scope = {"type": "http", "headers": [], "client": ("203.0.113.9", 12345),
              "method": "POST", "path": "/unlock"}
    return Request(scope)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    main._unlock_attempts.clear()
    yield
    main._unlock_attempts.clear()


def test_allows_up_to_the_limit():
    for _ in range(main.UNLOCK_RATE_LIMIT):
        assert main._check_unlock_rate_limit("ip-a", now=1000.0) is True


def test_blocks_beyond_the_limit():
    for _ in range(main.UNLOCK_RATE_LIMIT):
        main._check_unlock_rate_limit("ip-a", now=1000.0)
    assert main._check_unlock_rate_limit("ip-a", now=1000.0) is False


def test_window_resets_after_the_configured_seconds():
    for _ in range(main.UNLOCK_RATE_LIMIT):
        main._check_unlock_rate_limit("ip-a", now=1000.0)
    assert main._check_unlock_rate_limit("ip-a", now=1000.0) is False
    later = 1000.0 + main.UNLOCK_RATE_WINDOW_S + 1
    assert main._check_unlock_rate_limit("ip-a", now=later) is True


def test_different_ips_have_independent_limits():
    for _ in range(main.UNLOCK_RATE_LIMIT):
        main._check_unlock_rate_limit("ip-a", now=1000.0)
    assert main._check_unlock_rate_limit("ip-b", now=1000.0) is True


def test_unlock_endpoint_returns_429_when_rate_limited(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    create_code(db, "raptor-quill-42", "Test")

    for _ in range(main.UNLOCK_RATE_LIMIT):
        main.unlock(code="wrong-code-00", request=_fake_request())

    resp = main.unlock(code="raptor-quill-42", request=_fake_request())

    assert resp.status_code == 429
