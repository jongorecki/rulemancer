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


def test_candidates_carry_their_source_event(tmp_path):
    """Provenance: an approved example should be traceable back to the query
    it came from, so a bad approval can be audited later."""
    db = _db(tmp_path, ["Can I respond to a land being played?"])
    assert isinstance(candidate_questions(db)[0]["event_id"], int)
