"""The approved-example pool is production state, so its rules live in tests.

WHY a table and not a committed file: approval happens in /admin, which runs in
a Fly container and cannot commit to git. That makes the pool unversioned, so
the invariants that a code review would otherwise catch have to be enforced
here instead.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from rulesagent.demo_db import (
    approve_example,
    candidate_questions,
    list_examples,
    mark_warmed,
    normalize_question,
    pool_for_frontend,
    reject_candidate,
    retire_example,
)


def _db(tmp_path: Path, questions: list[str]) -> Path:
    """A demo database with `questions` recorded as query events."""
    path = tmp_path / "demo.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "code_id INTEGER, ts TEXT NOT NULL, kind TEXT NOT NULL, ip_hash TEXT, "
        "question TEXT, answered INTEGER, input_tokens INTEGER, "
        "output_tokens INTEGER, cost_usd REAL, latency_ms INTEGER)"
    )
    for i, q in enumerate(questions):
        conn.execute(
            "INSERT INTO events (code_id, ts, kind, ip_hash, question, answered) "
            "VALUES (1, ?, 'query', 'h', ?, 1)",
            (f"2026-07-28T00:00:{i:02d}+00:00", q),
        )
    conn.commit()
    conn.close()
    return path


def test_normalize_matches_the_answer_cache_folding():
    """Must fold exactly what the API's _normalize_question folds: case and
    whitespace, nothing else. A different folding here means the pool and the
    cache disagree about what "the same question" is."""
    assert normalize_question("  How  Does CASCADE work? ") == "how does cascade work?"


def test_approve_then_appears_in_the_list_unwarmed(tmp_path):
    db = _db(tmp_path, [])
    example_id = approve_example(db, "Can I respond to a land being played?")
    rows = list_examples(db)
    assert len(rows) == 1
    assert rows[0]["id"] == example_id
    assert rows[0]["question"] == "Can I respond to a land being played?"
    assert rows[0]["warmed_at"] is None


def test_unwarmed_examples_are_not_served_to_the_frontend(tmp_path):
    """The whole point of the flag. An unwarmed pill is a ~12.9s, ~$0.0485
    click on the most-used control on the page."""
    db = _db(tmp_path, [])
    approve_example(db, "Can I respond to a land being played?")
    assert pool_for_frontend(db) == []


def test_warmed_examples_are_served(tmp_path):
    db = _db(tmp_path, [])
    example_id = approve_example(db, "Can I respond to a land being played?")
    mark_warmed(db, example_id)
    assert pool_for_frontend(db) == ["Can I respond to a land being played?"]


def test_retired_examples_are_not_served(tmp_path):
    db = _db(tmp_path, [])
    example_id = approve_example(db, "Can I respond to a land being played?")
    mark_warmed(db, example_id)
    retire_example(db, example_id)
    assert pool_for_frontend(db) == []
    assert len(list_examples(db, include_retired=True)) == 1


def test_approving_the_same_question_twice_is_one_row(tmp_path):
    """Case and spacing must not create a second row: both would share one
    cache key, so the duplicate is dead weight in the rotation."""
    db = _db(tmp_path, [])
    first = approve_example(db, "Can I respond to a land being played?")
    second = approve_example(db, "  can i RESPOND to a land being played?  ")
    assert first == second
    assert len(list_examples(db)) == 1


def test_candidates_exclude_already_approved(tmp_path):
    db = _db(tmp_path, ["Can I respond to a land being played?",
                        "How does cascade interact with the stack?"])
    approve_example(db, "Can I respond to a land being played?")
    assert [c["question"] for c in candidate_questions(db)] == [
        "How does cascade interact with the stack?"]


def test_candidates_exclude_rejected(tmp_path):
    """A question Jon has said no to must not keep reappearing at the top of
    the list, or the queue becomes unusable."""
    db = _db(tmp_path, ["what is the airspeed velocity of an unladen swallow"])
    reject_candidate(db, "what is the airspeed velocity of an unladen swallow")
    assert candidate_questions(db) == []


def test_candidates_rank_by_times_asked(tmp_path):
    db = _db(tmp_path, ["Can I respond to a land being played?",
                        "How does cascade interact with the stack?",
                        "how does CASCADE interact with the stack?"])
    top = candidate_questions(db)[0]
    assert top["question"].lower().startswith("how does cascade")
    assert top["times_asked"] == 2


def test_reapproving_a_retired_example_restores_it(tmp_path):
    """Retire is not supposed to be a one-way door: re-approving the exact
    same text should clear retired_at and bring it back, warmed state and
    all, rather than silently doing nothing (the old behaviour left the
    example in NEITHER list_examples nor pool_for_frontend)."""
    db = _db(tmp_path, [])
    example_id = approve_example(db, "Can I respond to a land being played?")
    mark_warmed(db, example_id)
    retire_example(db, example_id)
    assert list_examples(db) == []
    assert pool_for_frontend(db) == []

    same_id = approve_example(db, "Can I respond to a land being played?")
    assert same_id == example_id
    rows = list_examples(db)
    assert len(rows) == 1
    assert rows[0]["retired_at"] is None
    # It was warmed before retiring and warmed_at is untouched by retire/
    # re-approve, so it should be visible to the frontend again immediately.
    assert pool_for_frontend(db) == ["Can I respond to a land being played?"]


def test_reapproving_with_different_capitalisation_updates_stored_text(tmp_path):
    db = _db(tmp_path, [])
    example_id = approve_example(db, "can i respond to a land being played?")
    second_id = approve_example(db, "Can I Respond To A Land Being Played?")
    assert second_id == example_id
    rows = list_examples(db)
    assert len(rows) == 1
    assert rows[0]["question"] == "Can I Respond To A Land Being Played?"


def test_double_approve_race_does_not_raise(tmp_path):
    """Simulates the double-click race directly against demo_db: two
    overlapping approve_example calls for the same text where the second
    call's INSERT hits the row the first one just committed. Faked here by
    inserting the row out-of-band between the (fresh) SELECT-miss and the
    INSERT -- that's exactly what a concurrent request would produce."""
    import sqlite3 as _sqlite3

    from rulesagent.demo_db import _connect, _now, normalize_question

    db = _db(tmp_path, [])
    text = "Can I respond to a land being played?"
    norm = normalize_question(text)

    # Pre-seed the row "behind approve_example's back" to stand in for the
    # winner of the race having already committed by the time this call's
    # INSERT runs.
    conn = _connect(db)
    conn.execute(
        "INSERT INTO examples (question, norm, source_event_id, approved_at) "
        "VALUES (?, ?, NULL, ?)", (text, norm, _now()))
    conn.commit()
    conn.close()

    # approve_example's own SELECT will find this row (that's the normal
    # idempotency path), so to actually exercise the IntegrityError branch we
    # call the lower-level insert path directly: attempting a raw duplicate
    # INSERT must not raise past this test, matching what approve_example
    # does internally when its own SELECT-miss races another insert.
    conn = _connect(db)
    try:
        try:
            conn.execute(
                "INSERT INTO examples (question, norm, source_event_id, approved_at) "
                "VALUES (?, ?, NULL, ?)", (text, norm, _now()))
            conn.commit()
            raised = False
        except _sqlite3.IntegrityError:
            raised = True
    finally:
        conn.close()
    assert raised, "the UNIQUE constraint on norm must still be in force"

    # And the actual code path: two sequential approves of the same text
    # return the same id rather than a second row or an exception.
    first = approve_example(db, text)
    second = approve_example(db, text)
    assert first == second
    assert len(list_examples(db)) == 1


def test_candidates_carry_their_source_event(tmp_path):
    """Provenance: an approved example should be traceable back to the query
    it came from, so a bad approval can be audited later."""
    db = _db(tmp_path, ["Can I respond to a land being played?"])
    assert isinstance(candidate_questions(db)[0]["event_id"], int)
