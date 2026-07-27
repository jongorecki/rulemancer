# Task: admin code mint/revoke UI (.superpowers/sdd/2026-07-27-gated-demo/
# task-admin-mint-report.md). scripts/codes.py writes to the LOCAL demo.db;
# Fly reads /app/data/demo.db on a mounted volume, a different file -- so a
# code minted on Jon's machine never exists on the live site, and the only
# way to fix that today is SSH. This adds POST /admin/codes/mint and POST
# /admin/codes/revoke so Jon can mint (with a custom query cap) and revoke
# straight from the browser.
#
# Same in-process route-function convention as test_admin_login.py /
# test_admin_demo_view.py: call the FastAPI route functions directly.

import sys
from pathlib import Path

import pytest

from rulesagent.api import main
from rulesagent.demo_db import WORDLIST, create_code, generate_code, list_codes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codes as codes_cli  # noqa: E402


@pytest.fixture(autouse=True)
def _admin_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    yield db


# --- minting -----------------------------------------------------------

def test_mint_creates_code_with_label_and_cap(_admin_env):
    db = _admin_env
    resp = main.admin_mint_code(
        label="Cribl -- Jane R.", max_queries="42", authorization="Bearer secret-token",
    )
    assert resp.status_code == 200
    rows = list_codes(db)
    assert len(rows) == 1
    assert rows[0]["label"] == "Cribl -- Jane R."
    assert rows[0]["max_queries"] == 42


def test_mint_displays_the_new_code_once(_admin_env):
    resp = main.admin_mint_code(
        label="Cribl -- Jane R.", max_queries="25", authorization="Bearer secret-token",
    )
    body = resp.body.decode()
    db = _admin_env
    code = list_codes(db)[0]["code"]
    assert code in body
    assert "minted" in body.lower()


def test_mint_empty_label_rejected(_admin_env):
    db = _admin_env
    resp = main.admin_mint_code(
        label="   ", max_queries="25", authorization="Bearer secret-token",
    )
    assert resp.status_code == 400
    body = resp.body.decode().lower()
    assert "label" in body and "empty" in body
    assert list_codes(db) == []


@pytest.mark.parametrize("bad_cap", ["abc", "25.5", "", "  "])
def test_mint_non_integer_cap_rejected(_admin_env, bad_cap):
    db = _admin_env
    resp = main.admin_mint_code(
        label="Test", max_queries=bad_cap, authorization="Bearer secret-token",
    )
    assert resp.status_code == 400
    assert "whole number" in resp.body.decode().lower()
    assert list_codes(db) == []


def test_mint_zero_cap_rejected(_admin_env):
    db = _admin_env
    resp = main.admin_mint_code(
        label="Test", max_queries="0", authorization="Bearer secret-token",
    )
    assert resp.status_code == 400
    assert "greater than zero" in resp.body.decode().lower()
    assert list_codes(db) == []


def test_mint_negative_cap_rejected(_admin_env):
    db = _admin_env
    resp = main.admin_mint_code(
        label="Test", max_queries="-5", authorization="Bearer secret-token",
    )
    assert resp.status_code == 400
    assert "greater than zero" in resp.body.decode().lower()
    assert list_codes(db) == []


def test_mint_cap_over_ceiling_rejected(_admin_env):
    db = _admin_env
    resp = main.admin_mint_code(
        label="Test", max_queries="2500", authorization="Bearer secret-token",
    )
    assert resp.status_code == 400
    body = resp.body.decode().lower()
    assert str(main.MAX_QUERIES_CEILING) in body
    assert "exceed" in body
    assert list_codes(db) == []


def test_mint_cap_at_ceiling_accepted(_admin_env):
    db = _admin_env
    resp = main.admin_mint_code(
        label="Test", max_queries=str(main.MAX_QUERIES_CEILING), authorization="Bearer secret-token",
    )
    assert resp.status_code == 200
    assert list_codes(db)[0]["max_queries"] == main.MAX_QUERIES_CEILING


def test_unauthenticated_mint_creates_nothing_and_shows_login_form(_admin_env):
    db = _admin_env
    resp = main.admin_mint_code(label="Test", max_queries="25", authorization=None)
    assert resp.status_code == 401
    assert "<form" in resp.body.decode()
    assert list_codes(db) == []


def test_demo_visitor_cookie_cannot_mint(_admin_env):
    db = _admin_env
    code_id = create_code(db, "raptor-quill-42", "Someone", max_queries=25)
    visitor_cookie = main.sign_session(code_id, "test-secret")

    resp = main.admin_mint_code(
        label="Test", max_queries="25", authorization=None, admin_session=visitor_cookie,
    )
    assert resp.status_code == 401
    assert "<form" in resp.body.decode()
    # Only the one pre-existing code, nothing new minted.
    assert len(list_codes(db)) == 1


# --- revoking ------------------------------------------------------------

def test_revoke_marks_only_that_code_revoked(_admin_env):
    db = _admin_env
    keep_id = create_code(db, "raptor-quill-42", "Keep me", max_queries=25)
    revoke_id = create_code(db, "cedar-otter-birch-07", "Revoke me", max_queries=25)

    resp = main.admin_revoke_code(code_id=str(revoke_id), authorization="Bearer secret-token")
    assert resp.status_code == 200

    rows = {r["id"]: r for r in list_codes(db)}
    assert rows[revoke_id]["revoked_at"] is not None
    assert rows[keep_id]["revoked_at"] is None

    body = resp.body.decode()
    assert "status-revoked" in body


def test_unauthenticated_revoke_revokes_nothing(_admin_env):
    db = _admin_env
    code_id = create_code(db, "raptor-quill-42", "Someone", max_queries=25)

    resp = main.admin_revoke_code(code_id=str(code_id), authorization=None)
    assert resp.status_code == 401
    assert "<form" in resp.body.decode()

    row = {r["id"]: r for r in list_codes(db)}[code_id]
    assert row["revoked_at"] is None


def test_demo_visitor_cookie_cannot_revoke(_admin_env):
    db = _admin_env
    code_id = create_code(db, "raptor-quill-42", "Someone", max_queries=25)
    visitor_cookie = main.sign_session(code_id, "test-secret")

    resp = main.admin_revoke_code(code_id=str(code_id), authorization=None, admin_session=visitor_cookie)
    assert resp.status_code == 401

    row = {r["id"]: r for r in list_codes(db)}[code_id]
    assert row["revoked_at"] is None


# --- one shared code generator (no drift between CLI and admin form) -----

def test_admin_and_cli_mint_use_the_same_generator():
    """scripts/codes.py imports generate_code/WORDLIST from rulesagent.demo_db
    -- the same module main.admin_mint_code imports from -- so there is
    exactly one word-triplet generator, not two that could drift."""
    assert codes_cli.generate_code is main.generate_code is generate_code
    assert codes_cli.WORDLIST is WORDLIST


# --- CSRF: pin the admin cookie's SameSite=Lax (already covered by
# test_admin_login.py::test_correct_login_token_sets_cookie_and_redirects,
# repeated here so this test file is self-contained proof for the mint/
# revoke routes' own auth path). A cross-site POST to /admin/codes/mint or
# /admin/codes/revoke can't carry a SameSite=Lax cookie, which is what makes
# an unauthenticated-looking cross-site POST fail _admin_authed the same way
# a bare curl with no auth does.

def test_admin_cookie_is_samesite_lax():
    resp = main.admin_login(token="secret-token")
    set_cookie = resp.headers.get("set-cookie", "")
    assert "samesite=lax" in set_cookie.lower()
