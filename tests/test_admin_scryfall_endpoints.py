# Tests for the token-protected Scryfall admin refresh endpoints
# (docs/plan-scryfall-local-bulk.md Sec 5 item 2, Jon's ruling: "background
# task + status poll... ADMIN_TOKEN env-var pattern approved").
#
# Same convention as tests/test_api_debug.py: route functions called
# in-process, no TestClient/lifespan/network. background_tasks is a fake
# double that runs the task inline (synchronously) so the test can assert
# on the resulting status without a real background thread.

from fastapi import HTTPException
import pytest

from rulesagent.api import main


class _InlineBackgroundTasks:
    """Fake BackgroundTasks: runs the task immediately instead of after the
    response is sent, so tests can assert on the resulting status
    synchronously."""

    def add_task(self, func, *args, **kwargs):
        func(*args, **kwargs)


class _RecordingBackgroundTasks:
    """Fake BackgroundTasks that just records what was scheduled, without
    running it -- for asserting the endpoint returns immediately without
    waiting on the refresh."""

    def __init__(self):
        self.calls = []

    def add_task(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))


@pytest.fixture(autouse=True)
def _reset_admin_state(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    main._scryfall_refresh_state.clear()
    main._scryfall_refresh_state.update(main._SCRYFALL_REFRESH_IDLE)
    yield
    main._scryfall_refresh_state.clear()
    main._scryfall_refresh_state.update(main._SCRYFALL_REFRESH_IDLE)


# --- auth --------------------------------------------------------------------


def test_refresh_rejects_missing_token():
    with pytest.raises(HTTPException) as exc:
        main.admin_scryfall_refresh(authorization=None, background_tasks=_RecordingBackgroundTasks())
    assert exc.value.status_code == 401


def test_refresh_rejects_wrong_token():
    with pytest.raises(HTTPException) as exc:
        main.admin_scryfall_refresh(
            authorization="Bearer wrong", background_tasks=_RecordingBackgroundTasks()
        )
    assert exc.value.status_code == 401


def test_refresh_rejects_when_admin_token_not_configured(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        main.admin_scryfall_refresh(
            authorization="Bearer secret-token", background_tasks=_RecordingBackgroundTasks()
        )
    assert exc.value.status_code == 503


def test_status_also_requires_token():
    with pytest.raises(HTTPException) as exc:
        main.admin_scryfall_status(authorization=None)
    assert exc.value.status_code == 401


# --- refresh returns immediately, backgrounded ------------------------------


def test_refresh_schedules_background_task_and_returns_immediately(monkeypatch):
    monkeypatch.setattr(main.refresh_scryfall_bulk, "refresh", lambda: {"card_count": 1})
    bg = _RecordingBackgroundTasks()

    resp = main.admin_scryfall_refresh(authorization="Bearer secret-token", background_tasks=bg)

    assert resp.status == "started"
    assert len(bg.calls) == 1  # scheduled, not run inline


def test_refresh_no_op_when_already_running():
    main._scryfall_refresh_state.update({"status": "running"})
    bg = _RecordingBackgroundTasks()

    resp = main.admin_scryfall_refresh(authorization="Bearer secret-token", background_tasks=bg)

    assert resp.status == "already_running"
    assert bg.calls == []  # doesn't double-schedule


# --- status poll: success / failure paths -----------------------------------


def test_status_reports_success_after_refresh_completes(monkeypatch):
    monkeypatch.setattr(
        main.refresh_scryfall_bulk, "refresh",
        lambda: {"card_count": 30000, "ruling_count": 5000, "name_collisions": 0,
                  "sanity_message": "ok"},
    )
    main.admin_scryfall_refresh(authorization="Bearer secret-token", background_tasks=_InlineBackgroundTasks())

    status = main.admin_scryfall_status(authorization="Bearer secret-token")

    assert status.status == "success"
    assert status.result["card_count"] == 30000
    assert status.error is None
    assert status.started_at is not None
    assert status.finished_at is not None


def test_status_reports_failure_and_the_error_message(monkeypatch):
    def _boom():
        raise RuntimeError("sanity check FAILED, aborting: only 3 cards in store")

    monkeypatch.setattr(main.refresh_scryfall_bulk, "refresh", _boom)
    main.admin_scryfall_refresh(authorization="Bearer secret-token", background_tasks=_InlineBackgroundTasks())

    status = main.admin_scryfall_status(authorization="Bearer secret-token")

    assert status.status == "failed"
    assert "sanity check FAILED" in status.error
    assert status.result is None


def test_status_idle_before_any_refresh_ever_ran():
    status = main.admin_scryfall_status(authorization="Bearer secret-token")

    assert status.status == "idle"
    assert status.started_at is None
    assert status.result is None
    assert status.error is None
