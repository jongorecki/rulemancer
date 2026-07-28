"""Approval is the human-in-the-loop control, so its auth is tested first.

WHY this file exists separately from test_admin_demo_view.py: these handlers
WRITE. An unauthenticated POST that mints nothing is a nuisance; an
unauthenticated POST that publishes a stranger's text onto the public demo is
the failure this whole feature is shaped to prevent.
"""
from __future__ import annotations

from rulesagent.api import main as api_main
from rulesagent.demo_db import approve_example, list_examples, pool_for_frontend


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


def test_admin_page_shows_candidates_and_the_pool(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    approve_example(db, "How does cascade interact with the stack?")
    html = api_main._admin_page_html()
    assert "How does cascade interact with the stack?" in html
    assert "not warmed yet" in html, (
        "the pool section must say which approved examples are still invisible")
