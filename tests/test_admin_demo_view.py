# Slice 4 Task 11. Same in-process route-function convention as
# tests/test_admin_scryfall_endpoints.py.

from fastapi import HTTPException
import pytest

from rulesagent.api import main
from rulesagent.demo_db import create_code, log_event


@pytest.fixture(autouse=True)
def _admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    monkeypatch.setenv("DAILY_BUDGET_USD", "5.00")


def test_requires_admin_token():
    """Behavior change (browser-login task): no auth used to raise
    HTTPException(401) straight to a JSON error body -- unreachable from a
    browser address bar. It now renders the login form at 401 instead. See
    tests/test_admin_login.py for the full coverage of that path."""
    resp = main.admin_demo_view(authorization=None)
    assert resp.status_code == 401
    assert "<form" in resp.body.decode()


def test_require_admin_token_constant_time_compare_still_gates_correctly():
    """_require_admin_token now compares with hmac.compare_digest instead of
    `!=` (constant-time, since it also gates /admin, which renders every
    code/label/question). Prove the swap didn't break the gate: right token
    passes, wrong token -- including one that shares a long prefix with the
    real token, the case a naive `!=` timing side-channel would leak -- is
    still rejected, and a non-str header never raises TypeError."""
    main._require_admin_token("Bearer secret-token")  # correct: no raise

    with pytest.raises(HTTPException) as exc:
        main._require_admin_token("Bearer secret-tokeX")  # wrong, shares prefix
    assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        main._require_admin_token("Bearer wrong")
    assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        main._require_admin_token(None)
    assert exc.value.status_code == 401


def test_wrong_token_rejected_and_leaks_nothing(monkeypatch, tmp_path):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    create_code(db, "raptor-quill-42", "Cribl -- Jane R.", max_queries=25)

    resp = main.admin_demo_view(authorization="Bearer wrong-token")
    assert resp.status_code == 401
    body = resp.body.decode()
    # Renders the login form now (browser-login task), not a raised
    # HTTPException/JSON error -- and still must not leak any code/label
    # data through the rejection.
    assert "<form" in body
    assert "raptor-quill-42" not in body
    assert "Cribl" not in body


def test_renders_code_label_and_stats(monkeypatch, tmp_path):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Cribl -- Jane R.", max_queries=25)
    log_event(db, code_id=code_id, kind="unlock", ip_hash="h")
    log_event(db, code_id=code_id, kind="query", ip_hash="h",
              question="Does <script>alert(1)</script> trample work?", answered=True, cost_usd=0.03)

    resp = main.admin_demo_view(authorization="Bearer secret-token")
    body = resp.body.decode()

    assert "Cribl -- Jane R." in body
    assert "raptor-quill-42" in body
    assert "1" in body  # unlocks or queries count appears somewhere
    # Question text is escaped, not rendered as live markup:
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


def test_shows_remaining_quota(monkeypatch, tmp_path):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=25)
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=0.01)
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q2", cost_usd=0.01)

    resp = main.admin_demo_view(authorization="Bearer secret-token")

    assert "23" in resp.body.decode()  # 25 - 2 used = 23 remaining


def test_shows_global_daily_spend_against_cap(monkeypatch, tmp_path):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q", cost_usd=1.23)

    resp = main.admin_demo_view(authorization="Bearer secret-token")
    body = resp.body.decode()

    assert "1.23" in body
    assert "5.00" in body


def test_daily_spend_matches_breaker_arithmetic_with_unpriced_rows(monkeypatch, tmp_path):
    """The number on the page must be computed the SAME way Task 7's
    breaker computes it: priced SUM(cost_usd) plus each NULL-cost row
    priced at UNPRICED_QUERY_ESTIMATE_USD. A plain daily_spend() call
    alone silently drops NULL rows (SQL SUM ignores NULLs) and would
    under-report real spend relative to what the breaker enforces."""
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="priced", cost_usd=1.00)
    # cost_usd left at its default (0.0) counts as priced $0 in this schema;
    # simulate a genuine unpriced row the way _record_query_event does when
    # cost calculation fails: cost_usd=None.
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="unpriced", cost_usd=None)

    today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).date().isoformat()
    expected = main._todays_spend(db, today)
    assert expected == pytest.approx(1.00 + main.UNPRICED_QUERY_ESTIMATE_USD)

    resp = main.admin_demo_view(authorization="Bearer secret-token")
    body = resp.body.decode()
    assert f"{expected:.2f}" in body


def test_no_codes_yet_renders_without_error(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DEMO_DB", tmp_path / "demo.db")
    resp = main.admin_demo_view(authorization="Bearer secret-token")
    assert resp.status_code == 200
    assert "no code" in resp.body.decode().lower()


def test_code_with_no_events_renders_row_not_vanish(monkeypatch, tmp_path):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    create_code(db, "never-touched-1", "Untouched", max_queries=25)

    resp = main.admin_demo_view(authorization="Bearer secret-token")
    body = resp.body.decode()

    assert "never-touched-1" in body
    assert "Untouched" in body
    # No timestamp available -- must render a placeholder, not raise/crash.
    assert resp.status_code == 200


def test_questions_sorted_newest_first(monkeypatch, tmp_path):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="first question", cost_usd=0.01)
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="second question", cost_usd=0.01)

    resp = main.admin_demo_view(authorization="Bearer secret-token")
    body = resp.body.decode()

    assert body.index("second question") < body.index("first question")


def test_ip_hash_never_rendered(monkeypatch, tmp_path):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    log_event(db, code_id=code_id, kind="query", ip_hash="deadbeefcafebabe0123456789", question="q",
              cost_usd=0.01)

    resp = main.admin_demo_view(authorization="Bearer secret-token")
    body = resp.body.decode()

    assert "deadbeefcafebabe0123456789" not in body
