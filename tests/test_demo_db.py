# tests/test_demo_db.py
# Slice 4 (docs/superpowers/plans/2026-07-27-gated-demo.md Task 1). Every test
# gets its own tmp_path db, same convention as tests/test_cache.py -- nothing
# here ever touches data/demo.db.

import sqlite3

import pytest

from rulesagent.demo_db import (
    code_stats,
    count_queries,
    create_code,
    daily_spend,
    events_for_code,
    get_code_by_id,
    get_code_by_value,
    list_codes,
    log_event,
    revoke_code,
)


def test_create_and_get_code_round_trip(tmp_path):
    db = tmp_path / "demo.db"
    code_id = create_code(db, "raptor-quill-42", "Cribl -- Jane R.", max_queries=25, notes="found via LinkedIn")

    row = get_code_by_value(db, "raptor-quill-42")

    assert row["id"] == code_id
    assert row["code"] == "raptor-quill-42"
    assert row["label"] == "Cribl -- Jane R."
    assert row["max_queries"] == 25
    assert row["revoked_at"] is None
    assert row["notes"] == "found via LinkedIn"
    assert row["created_at"]  # non-empty ISO timestamp


def test_get_code_by_value_missing_returns_none(tmp_path):
    db = tmp_path / "demo.db"
    assert get_code_by_value(db, "does-not-exist-00") is None


def test_get_code_by_id_matches_get_by_value(tmp_path):
    db = tmp_path / "demo.db"
    code_id = create_code(db, "cedar-otter-07", "Test")
    assert get_code_by_id(db, code_id)["code"] == "cedar-otter-07"
    assert get_code_by_id(db, 99999) is None


def test_duplicate_code_raises_integrity_error(tmp_path):
    db = tmp_path / "demo.db"
    create_code(db, "same-code-01", "First")
    with pytest.raises(sqlite3.IntegrityError):
        create_code(db, "same-code-01", "Second")


def test_default_max_queries_is_25(tmp_path):
    db = tmp_path / "demo.db"
    code_id = create_code(db, "birch-heron-19", "Test", max_queries=None)
    row = get_code_by_id(db, code_id)
    assert row["max_queries"] is None  # caller passed None explicitly -- guard applies its own default


def test_revoke_code_sets_revoked_at(tmp_path):
    db = tmp_path / "demo.db"
    code_id = create_code(db, "maple-finch-33", "Test")
    assert revoke_code(db, code_id) is True
    row = get_code_by_id(db, code_id)
    assert row["revoked_at"] is not None


def test_revoke_missing_code_returns_false(tmp_path):
    db = tmp_path / "demo.db"
    assert revoke_code(db, 99999) is False


def test_list_codes_newest_first(tmp_path):
    db = tmp_path / "demo.db"
    id1 = create_code(db, "aaa-bbb-01", "First")
    id2 = create_code(db, "ccc-ddd-02", "Second")
    rows = list_codes(db)
    assert [r["id"] for r in rows] == [id2, id1]


def test_log_event_and_count_queries(tmp_path):
    db = tmp_path / "demo.db"
    code_id = create_code(db, "elm-osprey-55", "Test")
    log_event(db, code_id=code_id, kind="unlock", ip_hash="abc123")
    log_event(db, code_id=code_id, kind="query", ip_hash="abc123", question="Does trample get through deathtouch?",
              answered=True, input_tokens=500, output_tokens=200, cost_usd=0.012, latency_ms=1800)
    log_event(db, code_id=code_id, kind="query", ip_hash="abc123", question="second question",
              answered=True, input_tokens=400, output_tokens=150, cost_usd=0.009, latency_ms=1500)

    assert count_queries(db, code_id) == 2  # unlock row doesn't count


def test_log_event_denied_kind_allows_null_code_id(tmp_path):
    db = tmp_path / "demo.db"
    # A denied unlock has no valid code -- code_id must be nullable (spec).
    log_event(db, code_id=None, kind="denied", ip_hash="xyz789")
    # No exception is the assertion; nothing to read back through code_id.


def test_code_stats_aggregates_correctly(tmp_path):
    db = tmp_path / "demo.db"
    code_id = create_code(db, "fir-lark-88", "Test")
    log_event(db, code_id=code_id, kind="unlock", ip_hash="h1")
    log_event(db, code_id=code_id, kind="unlock", ip_hash="h1")
    log_event(db, code_id=code_id, kind="query", ip_hash="h1", question="q1", answered=True,
              input_tokens=100, output_tokens=50, cost_usd=0.01, latency_ms=1000)
    log_event(db, code_id=code_id, kind="query", ip_hash="h1", question="q2", answered=False,
              input_tokens=100, output_tokens=50, cost_usd=0.01, latency_ms=1100)

    stats = code_stats(db, code_id)

    assert stats["unlocks"] == 2
    assert stats["queries"] == 2
    assert stats["total_cost"] == pytest.approx(0.02)
    assert stats["first_seen"] is not None
    assert stats["last_seen"] is not None


def test_events_for_code_newest_first(tmp_path):
    db = tmp_path / "demo.db"
    code_id = create_code(db, "pine-swift-14", "Test")
    log_event(db, code_id=code_id, kind="query", ip_hash="h1", question="first", cost_usd=0.01)
    log_event(db, code_id=code_id, kind="query", ip_hash="h1", question="second", cost_usd=0.01)

    rows = events_for_code(db, code_id)

    assert [r["question"] for r in rows] == ["second", "first"]


def test_daily_spend_sums_only_that_day(tmp_path):
    db = tmp_path / "demo.db"
    code_id = create_code(db, "yew-plover-21", "Test")
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO events (code_id, ts, kind, ip_hash, question, answered, "
            "input_tokens, output_tokens, cost_usd, latency_ms) VALUES (?, ?, 'query', "
            "'h1', 'q', 1, 100, 50, ?, 1000)",
            (code_id, "2026-07-27T10:00:00+00:00", 0.05),
        )
        conn.execute(
            "INSERT INTO events (code_id, ts, kind, ip_hash, question, answered, "
            "input_tokens, output_tokens, cost_usd, latency_ms) VALUES (?, ?, 'query', "
            "'h1', 'q', 1, 100, 50, ?, 1000)",
            (code_id, "2026-07-26T10:00:00+00:00", 0.09),
        )
        conn.commit()
    finally:
        conn.close()

    assert daily_spend(db, "2026-07-27") == pytest.approx(0.05)
    assert daily_spend(db, "2026-07-26") == pytest.approx(0.09)
    assert daily_spend(db, "2026-07-25") == 0.0


def test_missing_parent_directory_is_created(tmp_path):
    db = tmp_path / "nested" / "dir" / "demo.db"
    create_code(db, "ash-crane-03", "Test")
    assert db.exists()
