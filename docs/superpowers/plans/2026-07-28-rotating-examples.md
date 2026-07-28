# Rotating Demo Examples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**STATUS: DESIGN ONLY.** Written 2026-07-28 at Jon's request so it exists for
when there is enough demo traffic to draw from. Rule 0 applies: nothing here is
built until Jon rules on it. **Task 4 spends API credits and needs a separate
explicit go-ahead with a ceiling, even after the plan is approved.**

**Revised the same day**, after Jon asked for approval to happen in `/admin`
rather than in a terminal. That is not a UI preference, it moves the pool from a
committed file into production state. See "Why the pool lives in the database"
below before changing it back.

**Goal:** Replace the demo's four hardcoded example questions with a pool of
real questions Jon approves from `/admin`, rotating a few per page load, without
losing the property that makes examples feel good: pre-warmed, so a click is
85ms and $0.00 instead of ~12.9s and ~$0.0485.

**Architecture:** `/admin` already lists every question every visitor has asked.
This adds an **approve** control beside them. Approving writes the question to a
new `examples` table on the Fly volume, in an editable form, so Jon can fix a
typo or strip something personal before it is ever public. The app **injects the
approved, warmed pool into `index.html` at serve time**, so the page needs no
extra request and the client code stays a plain array. Warming stays a
deliberate command-line run, not a button.

**Tech Stack:** Python 3.12 stdlib (`sqlite3`, `json`, `re`), FastAPI with
server-rendered HTML forms (the pattern `/admin` already uses), pytest,
Playwright driven from `file://`, `flyctl ssh console` for production.

## Why the pool lives in the database

The obvious design is a JSON block in `frontend/index.html`, committed to git.
That is what the first draft of this plan did, and approving from `/admin` rules
it out: the admin page runs in a Fly container and cannot commit to a repo.

So the pool is production state, and that has costs worth accepting knowingly:

- **It is not versioned.** Lose the volume, lose the curation. Task 4 adds an
  export command precisely so a backup can be committed on purpose.
- **It is not reviewable in a PR.** The compensating control is that approving
  requires a human click in an authenticated page, and the approve form shows
  the full text and lets it be edited first.
- **Local and production diverge.** A dev machine's `data/demo.db` will have an
  empty pool. The page must render correctly with zero approved examples, which
  Task 3 tests explicitly.

What it buys: curation happens where the data already is, from a phone if
necessary, and "a human approved this string" becomes a row in a table rather
than a convention someone might skip when they are in a hurry.

## Global Constraints

Copied from `CLAUDE.md`, `Token-Economy-Policy.md`, and the gated-demo work.
Every task's requirements implicitly include this section.

- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Open JSON and
  SQLite text with `encoding="utf-8"`; the Windows cp1252 default fails here.
- **Jon runs the app on port 8000. Never bind or kill it.** Use 8947 for render
  checks and stop it when done.
- **Never run the full pytest suite while an eval arm is running.**
- **Verify UI by rendering.** Serve it, open it, look at it.
- **Production reads `/app/data/demo.db` on the Fly volume; local scripts write
  `data/demo.db`.** Anything that must see real data runs inside the container
  via `flyctl ssh console --app rulemancer -C "..."`. This has already bitten
  this project twice.
- **Auth ordering in every admin handler: check auth before touching the
  database or the form values**, matching `admin_mint_code` at `main.py:2300`.
  An unauthenticated POST must change nothing.
- **Spending API credits needs Jon's explicit approval per run, with a
  ceiling.** The standing delegation grant does not cover spend.
- **Commit per task** on master with the `Co-Authored-By: Claude Opus 5
  <noreply@anthropic.com>` trailer.
- **Privacy rule, load-bearing for this feature:** `events.question` is text
  strangers typed into a public box. It may be personal, malformed, or hostile.
  Nothing may reach the pool without a human approving that exact string. No
  automatic promotion, no "approve top 10" bulk action, no heuristic that
  decides a question is safe.
- **Voice for any user-facing copy:** contractions, plain words, no em dashes,
  no corporate filler.

## Prerequisite

**Tasks 1 and 2 are safe to build now.** Tasks 3 and 4 are pointless until there
are enough approved questions to rotate, which needs traffic. As of 2026-07-28
production holds 11 `query` events and 9 distinct questions. Check with:

```bash
flyctl ssh console --app rulemancer -C "python -c \"import sqlite3;c=sqlite3.connect('/app/data/demo.db');print(c.execute(\\\"select count(distinct question) from events where kind='query' and question<>''\\\").fetchone()[0])\""
```

## File Structure

| File | Responsibility |
|---|---|
| `src/rulesagent/demo_db.py` (modify) | The `examples` and `example_rejects` tables plus their access functions. Follows the existing `codes`/`events` pattern: schema constants at the top, one function per operation, no ORM. |
| `tests/test_example_pool_db.py` (create) | Guards the schema and every access function against a temp database. |
| `src/rulesagent/api/main.py` (modify) | Three admin POST handlers, the candidate and pool sections of `_admin_page_html`, and serve-time pool injection in the `/` route. |
| `tests/test_admin_example_approval.py` (create) | Guards the admin handlers, especially that an unauthenticated POST approves nothing. |
| `frontend/index.html` (modify) | An empty pool island the server fills, and rotation over it. Replaces the `EXAMPLES` const at line 100. |
| `tests/test_example_rotation.py` (create) | Playwright: renders only what is in the island, right count, stable within a load, and correct when the pool is empty. |
| `scripts/warm_examples.py` (modify) | Reads unwarmed rows from the database instead of a hardcoded list; skips anything already cached. |
| `scripts/check_example_cache.py` (create) | Reports whether each pool row is really in the answer cache under the current config. |
| `scripts/export_examples.py` (create) | Dumps the approved pool to JSON so it can be committed as a backup of unversioned production state. |
| `evals/build_metrics_history.py` (modify) | Flip the `rotating-examples` roadmap row to shipped. |

---

### Task 1: The examples table

No UI, no spend. Pure data layer, testable on a temp database.

**Files:**
- Modify: `src/rulesagent/demo_db.py`
- Test: `tests/test_example_pool_db.py`

**Interfaces:**
- Consumes: the existing `events` table (`id, code_id, ts, kind, ip_hash,
  question, answered, input_tokens, output_tokens, cost_usd, latency_ms`).
- Produces, all in `rulesagent.demo_db`:
  - `normalize_question(text: str) -> str`
  - `approve_example(db_path: Path, question: str, *, source_event_id: int | None = None) -> int`
  - `reject_candidate(db_path: Path, question: str) -> None`
  - `list_examples(db_path: Path, *, include_retired: bool = False) -> list[dict]`
  - `retire_example(db_path: Path, example_id: int) -> None`
  - `mark_warmed(db_path: Path, example_id: int) -> None`
  - `pool_for_frontend(db_path: Path) -> list[str]`
  - `candidate_questions(db_path: Path, *, limit: int = 60) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_example_pool_db.py -v`
Expected: FAIL at import, `ImportError: cannot import name 'approve_example'`.

- [ ] **Step 3: Add the schema**

In `src/rulesagent/demo_db.py`, beside `_CODES_SCHEMA` and `_EVENTS_SCHEMA`:

```python
_EXAMPLES_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS examples ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "question TEXT NOT NULL, "
    "norm TEXT NOT NULL UNIQUE, "        # case/whitespace-folded, dedupe key
    "source_event_id INTEGER, "          # provenance; NULL if hand-written
    "approved_at TEXT NOT NULL, "
    "warmed_at TEXT, "                   # NULL until the answer cache has it
    "retired_at TEXT)"                   # soft delete; history is evidence
)
_EXAMPLE_REJECTS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS example_rejects ("
    "norm TEXT PRIMARY KEY, "
    "rejected_at TEXT NOT NULL)"
)
```

Register both wherever `_CODES_SCHEMA` and `_EVENTS_SCHEMA` are executed, so an
existing production database gains the tables on next open. `CREATE TABLE IF NOT
EXISTS` makes this safe to deploy against the live volume with no migration
step.

- [ ] **Step 4: Add the access functions**

```python
def normalize_question(text: str) -> str:
    """Case and whitespace folding, and nothing else.

    Must stay identical to the API's _normalize_question, which builds the
    answer-cache key. If these two ever disagree about what "the same
    question" means, an approved example can be warmed under one key and
    looked up under another: a permanent silent cache miss, which shows up as
    a slow paid click rather than as an error.
    """
    return " ".join(text.strip().lower().split())


def approve_example(db_path: Path, question: str, *,
                    source_event_id: int | None = None) -> int:
    """Approve `question` as an example. Returns its row id.

    Idempotent on the normalized form: approving the same question twice
    returns the existing row rather than creating a second one that would
    share its cache key.
    """
    norm = normalize_question(question)
    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM examples WHERE norm = ?", (norm,)).fetchone()
        if existing is not None:
            return int(existing["id"])
        cur = conn.execute(
            "INSERT INTO examples (question, norm, source_event_id, approved_at) "
            "VALUES (?, ?, ?, ?)",
            (question.strip(), norm, source_event_id, _now()))
        return int(cur.lastrowid)


def reject_candidate(db_path: Path, question: str) -> None:
    """Remember a no, so the candidate list stops offering it."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO example_rejects (norm, rejected_at) VALUES (?, ?)",
            (normalize_question(question), _now()))


def mark_warmed(db_path: Path, example_id: int) -> None:
    with _connect(db_path) as conn:
        conn.execute("UPDATE examples SET warmed_at = ? WHERE id = ?",
                     (_now(), example_id))


def retire_example(db_path: Path, example_id: int) -> None:
    """Soft delete. The row stays so 'this was public once' stays answerable."""
    with _connect(db_path) as conn:
        conn.execute("UPDATE examples SET retired_at = ? WHERE id = ?",
                     (_now(), example_id))


def list_examples(db_path: Path, *, include_retired: bool = False) -> list[dict]:
    sql = "SELECT * FROM examples"
    if not include_retired:
        sql += " WHERE retired_at IS NULL"
    sql += " ORDER BY approved_at DESC"
    with _connect(db_path) as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def pool_for_frontend(db_path: Path) -> list[str]:
    """Exactly the questions safe to show: approved, warmed, not retired.

    Anything else is either a paid slow click or a question Jon pulled.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT question FROM examples "
            "WHERE warmed_at IS NOT NULL AND retired_at IS NULL "
            "ORDER BY id").fetchall()
    return [r["question"] for r in rows]


def candidate_questions(db_path: Path, *, limit: int = 60) -> list[dict]:
    """Questions visitors asked that are neither approved nor rejected yet,
    most-asked first. Each carries `question`, `times_asked`, `answered_rate`
    and `event_id` (the most recent event it came from, for provenance).

    No content filtering happens here on purpose. Length or keyword rules
    would be a machine deciding what is safe to publish, and the entire point
    of this feature is that a person decides that.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, question, answered FROM events "
            "WHERE kind = 'query' AND question IS NOT NULL AND question <> '' "
            "ORDER BY id").fetchall()
        taken = {r["norm"] for r in conn.execute("SELECT norm FROM examples")}
        taken |= {r["norm"] for r in conn.execute("SELECT norm FROM example_rejects")}

    grouped: dict[str, dict] = {}
    for row in rows:
        norm = normalize_question(row["question"])
        if norm in taken:
            continue
        entry = grouped.setdefault(norm, {
            "question": row["question"].strip(),
            "times_asked": 0, "_answered": 0, "event_id": row["id"],
        })
        entry["times_asked"] += 1
        entry["_answered"] += 1 if row["answered"] else 0
        entry["event_id"] = row["id"]

    out = []
    for entry in grouped.values():
        entry["answered_rate"] = entry["_answered"] / entry["times_asked"]
        entry.pop("_answered")
        out.append(entry)
    out.sort(key=lambda e: (-e["times_asked"], e["question"]))
    return out[:limit]
```

Check `_connect`'s existing usage before writing these: if it is not already a
context manager that commits, follow whatever `create_code` does rather than
introducing a second transaction style.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_example_pool_db.py tests/test_demo_db.py -v`
Expected: PASS. `test_demo_db.py` is included because the new schema constants
run against the same database it exercises.

- [ ] **Step 6: Commit**

```bash
git add src/rulesagent/demo_db.py tests/test_example_pool_db.py
git commit -m "demo: examples table for admin-approved rotating questions

Approval happens in /admin, which runs in a container and cannot commit to
git, so the pool is production state rather than a committed file. Rows
carry provenance (source event), a normalized dedupe key that matches the
answer cache's folding exactly, and separate warmed/retired timestamps so
an approved-but-unwarmed question is invisible rather than slow.

CREATE TABLE IF NOT EXISTS, so the live volume gains the tables on next
open with no migration step.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Approve, edit and reject from /admin

**Files:**
- Modify: `src/rulesagent/api/main.py` (`_admin_page_html` plus three handlers)
- Test: `tests/test_admin_example_approval.py`

**Interfaces:**
- Consumes: every function from Task 1.
- Produces: `POST /admin/examples/approve` (form: `question`, `event_id`),
  `POST /admin/examples/reject` (form: `question`),
  `POST /admin/examples/retire` (form: `example_id`). All three re-render the
  admin page, matching `admin_mint_code`'s pattern exactly.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_admin_example_approval.py -v`
Expected: FAIL, `AttributeError: module has no attribute 'admin_approve_example'`.

- [ ] **Step 3: Write the handlers**

Place them next to `admin_mint_code` (`main.py:2300`) and copy its shape: auth
first, validate second, write third, re-render always.

```python
@app.post(
    "/admin/examples/approve", tags=["ops"],
    summary="Approve a visitor's question as a rotating demo example",
    description="Admin-gated (Bearer or admin session cookie, same as GET /admin). Stores "
    "the SUBMITTED text, which may be an edited version of what the visitor typed. Approved "
    "examples are invisible on the demo until warmed -- see scripts/warm_examples.py.",
    include_in_schema=False,
)
def admin_approve_example(
    question: str = Form(...),
    event_id: str = Form(default=""),
    authorization: str | None = Header(default=None),
    admin_session: str | None = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
) -> HTMLResponse:
    # Auth before anything else, matching admin_mint_code: an unauthenticated
    # POST must publish nothing. This is the single most important line in
    # the feature -- it is what makes "a human approved this" true.
    if not _admin_authed(authorization, admin_session):
        return _admin_login_page()

    text = question.strip()
    if not text:
        return HTMLResponse(
            content=_admin_page_html(error="an example cannot be empty"),
            status_code=400)
    if len(text) > MAX_QUESTION_CHARS:
        return HTMLResponse(
            content=_admin_page_html(
                error=f"an example must be under {MAX_QUESTION_CHARS} characters"),
            status_code=400)

    try:
        source = int(event_id) if event_id.strip() else None
    except ValueError:
        source = None

    approve_example(DEMO_DB, text, source_event_id=source)
    return HTMLResponse(content=_admin_page_html())


@app.post(
    "/admin/examples/reject", tags=["ops"],
    summary="Dismiss a question so it stops appearing as a candidate",
    include_in_schema=False,
)
def admin_reject_candidate(
    question: str = Form(...),
    authorization: str | None = Header(default=None),
    admin_session: str | None = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
) -> HTMLResponse:
    if not _admin_authed(authorization, admin_session):
        return _admin_login_page()
    reject_candidate(DEMO_DB, question)
    return HTMLResponse(content=_admin_page_html())


@app.post(
    "/admin/examples/retire", tags=["ops"],
    summary="Pull an approved example off the demo",
    include_in_schema=False,
)
def admin_retire_example(
    example_id: str = Form(...),
    authorization: str | None = Header(default=None),
    admin_session: str | None = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
) -> HTMLResponse:
    if not _admin_authed(authorization, admin_session):
        return _admin_login_page()
    try:
        retire_example(DEMO_DB, int(example_id))
    except ValueError:
        return HTMLResponse(
            content=_admin_page_html(error="bad example id"), status_code=400)
    return HTMLResponse(content=_admin_page_html())
```

- [ ] **Step 4: Add the two sections to `_admin_page_html`**

Follow the existing table markup in that function rather than inventing new
styling. Two sections:

**Candidates.** For each row from `candidate_questions(DEMO_DB)`: the question
in a `<textarea name="question">` (editable before approval, which is the point),
its `times_asked` and `answered_rate`, a hidden `event_id`, an **Approve**
submit, and a separate small form posting the same text to `/admin/examples/reject`.

**Pool.** For each row from `list_examples(DEMO_DB)`: the question, when it was
approved, and either a warmed timestamp or the literal text `not warmed yet`
(the test asserts that string), plus a **Retire** submit. Above the table, a one
line count of how many are approved but unwarmed, with the exact command to fix
it:

```
3 approved and not warmed yet. They stay hidden until you run:
flyctl ssh console --app rulemancer -C "python scripts/warm_examples.py"
```

Every question rendered into this page must go through the same escaping the
page already uses for labels and questions (`_html.escape`, `main.py:284`).
These strings are attacker-controlled by definition.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_admin_example_approval.py tests/test_admin_demo_view.py tests/test_demo_auth.py -v`
Expected: PASS. The last two are included because this task edits the shared
admin page template and the auth path they both cover.

- [ ] **Step 6: Render-check the admin page**

Run the app locally on 8947 with `ADMIN_TOKEN` and `COOKIE_SECRET` set from
PowerShell, seed two fake query events into the local `data/demo.db`, and load
`/admin`. Confirm the candidate textarea is editable, Approve moves the row into
the pool section, the unwarmed count is right, and Reject makes a candidate stay
gone after a refresh. Stop the server.

- [ ] **Step 7: Commit**

```bash
git add src/rulesagent/api/main.py tests/test_admin_example_approval.py
git commit -m "admin: approve, edit and reject demo example candidates

/admin already lists every question every visitor asked; this adds the
controls next to them. The candidate field is a textarea, not a hidden
input, so a typo or something personal can be fixed before the string is
ever public.

Auth is checked before the form values in all three handlers, matching
admin_mint_code. An unauthenticated POST that mints nothing is a nuisance;
one that publishes a stranger's text on the demo is the failure this
feature exists to prevent.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Serve the pool and rotate it

**Files:**
- Modify: `src/rulesagent/api/main.py` (the `/` route at `main.py:2434`)
- Modify: `frontend/index.html` (the `EXAMPLES` const at line 100)
- Test: `tests/test_example_rotation.py`

**Interfaces:**
- Consumes: `pool_for_frontend(db_path) -> list[str]` from Task 1.
- Produces: an `#example-pool` JSON island in the served HTML, and
  `pickExamples(pool, n)` in page JS.

- [ ] **Step 1: Write the failing tests**

```python
"""Rotation shows a handful per load, only from the served pool.

Driven in a real headless browser from file://, like
tests/test_frontend_error_detail_surfacing.py: no server, no port 8000 or
8947, no API spend. The island is written into the file fixture directly,
which is exactly what the server does at serve time.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO / "frontend" / "index.html"
POOL_RE = re.compile(
    r'(<script type="application/json" id="example-pool">)(.*?)(</script>)',
    re.DOTALL)
EXAMPLES_SHOWN = 4


def _page_with_pool(tmp_path: Path, pool: list[str]) -> Path:
    """index.html with the island filled, the way the server fills it."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    filled = POOL_RE.sub(
        lambda m: m.group(1) + json.dumps(pool) + m.group(3), html)
    out = tmp_path / "index.html"
    out.write_text(filled, encoding="utf-8")
    return out


def _pills(page) -> list[str]:
    """Rendered pill labels, minus the decorative sigil span."""
    return [el.inner_text().replace("✦", "").strip()
            for el in page.query_selector_all('[data-action="example"]')]


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def test_index_ships_an_empty_island():
    """The committed file must not carry questions: the pool is production
    state now, and a stale committed copy would be a second source of truth."""
    match = POOL_RE.search(INDEX_HTML.read_text(encoding="utf-8"))
    assert match, "no #example-pool island in frontend/index.html"
    assert json.loads(match.group(2)) == []


def test_renders_only_served_questions(browser, tmp_path):
    pool = [f"Question number {i} about the stack?" for i in range(10)]
    page = browser.new_page()
    page.goto(_page_with_pool(tmp_path, pool).as_uri())
    shown = _pills(page)
    assert len(shown) == EXAMPLES_SHOWN
    assert set(shown) <= set(pool)
    page.close()


def test_empty_pool_renders_no_pills_and_does_not_break(browser, tmp_path):
    """A dev machine has an empty pool. The page must be fine, not broken."""
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(_page_with_pool(tmp_path, []).as_uri())
    assert _pills(page) == []
    assert errors == [], f"JS errors with an empty pool: {errors}"
    page.close()


def test_small_pool_shows_all_of_it(browser, tmp_path):
    page = browser.new_page()
    page.goto(_page_with_pool(tmp_path, ["Only one question?"]).as_uri())
    assert _pills(page) == ["Only one question?"]
    page.close()


def test_selection_is_stable_within_one_load(browser, tmp_path):
    """Re-rendering must not reshuffle pills under someone reading them."""
    pool = [f"Question number {i} about the stack?" for i in range(10)]
    path = _page_with_pool(tmp_path, pool)
    page = browser.new_page()
    page.goto(path.as_uri())
    first = _pills(page)
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    page.wait_for_timeout(100)
    assert _pills(page) == first
    page.close()


def test_rotation_varies_across_loads(browser, tmp_path):
    pool = [f"Question number {i} about the stack?" for i in range(10)]
    path = _page_with_pool(tmp_path, pool)
    seen = set()
    for _ in range(12):
        page = browser.new_page()
        page.goto(path.as_uri())
        seen.add(tuple(_pills(page)))
        page.close()
    assert len(seen) > 1, "twelve loads produced the same four pills every time"
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_example_rotation.py -v`
Expected: FAIL, no `#example-pool` island exists yet.

- [ ] **Step 3: Add the island and the rotation to `frontend/index.html`**

In `<head>`, before the main script:

```html
<!-- Filled by the server at serve time from the approved, warmed pool
     (rulesagent.demo_db.pool_for_frontend). Ships EMPTY on purpose: the pool
     is production state on the Fly volume, and a committed copy would be a
     second source of truth that goes stale. An empty island is a valid page
     with no example pills, which is what a dev machine correctly shows. -->
<script type="application/json" id="example-pool">[]</script>
```

Replacing `const EXAMPLES = [...]` at line 100:

```javascript
// Show a handful, chosen fresh per page load. Chosen ONCE at module scope,
// not per render: the composer re-renders on resize and on new chats, and
// reshuffling pills while someone is reading them makes a page feel broken
// rather than alive.
const EXAMPLES_SHOWN = 4;

function pickExamples(pool, n) {
  // Fisher-Yates on a copy. Not seeded: variety across loads is the feature.
  const shuffled = pool.slice();
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled.slice(0, Math.min(n, shuffled.length));
}

const EXAMPLE_POOL = JSON.parse(
  document.getElementById("example-pool").textContent);
const EXAMPLES = pickExamples(EXAMPLE_POOL, EXAMPLES_SHOWN);
```

The render code at `main.py`-served `index.html:551` already maps over
`EXAMPLES`, and `case "example": send(t.dataset.arg)` already sends the pill's
own text, so nothing else changes.

- [ ] **Step 4: Fill the island at serve time**

The `/` route currently returns a `FileResponse` (`main.py:2451`). It has to
become an `HTMLResponse` so the island can be filled. Keep the gate check and
the `Cache-Control: no-cache` header exactly as they are.

```python
_POOL_ISLAND_RE = re.compile(
    r'(<script type="application/json" id="example-pool">)(.*?)(</script>)',
    re.DOTALL)


def _index_html_with_pool() -> str:
    """index.html with the approved, warmed pool injected.

    Injected server-side rather than fetched by the client so the pills are
    present in first paint. A fetch would pop them in after load, on content
    that sits above the fold.

    Read per request rather than cached: this file is already served with
    no-cache, the pool changes whenever Jon approves something in /admin, and
    a stale in-process cache would mean approving a question appears to do
    nothing until the machine restarts.
    """
    html = (_frontend_dir / "index.html").read_text(encoding="utf-8")
    pool = json.dumps(pool_for_frontend(DEMO_DB))
    return _POOL_ISLAND_RE.sub(lambda m: m.group(1) + pool + m.group(3), html)
```

and in the `/` handler, replace both `FileResponse(_frontend_dir / "index.html", ...)`
returns with:

```python
        return HTMLResponse(content=_index_html_with_pool(),
                            headers={"Cache-Control": "no-cache"})
```

Leave `gate.html`'s `FileResponse` alone: the gate has no pool and no reason to
be re-read and rewritten on every locked-out request.

- [ ] **Step 5: Add a serve-time test**

```python
def test_served_index_contains_the_warmed_pool(tmp_path, monkeypatch):
    """The injection is what makes any of this reach a visitor."""
    from rulesagent.api import main as api_main
    from rulesagent.demo_db import approve_example, mark_warmed

    db = tmp_path / "demo.db"
    monkeypatch.setattr(api_main, "DEMO_DB", db)
    example_id = approve_example(db, "Can I respond to a land being played?")
    mark_warmed(db, example_id)

    html = api_main._index_html_with_pool()
    assert "Can I respond to a land being played?" in html
    assert '<script type="application/json" id="example-pool">[]' not in html
```

Put it in `tests/test_example_rotation.py` and run the file again.

- [ ] **Step 6: Run everything this touched**

Run: `.venv/Scripts/python.exe -m pytest tests/test_example_rotation.py tests/test_frontend_error_detail_surfacing.py tests/test_demo_auth.py -v`
Expected: PASS. The auth file matters because the `/` route's gate branch was
edited.

- [ ] **Step 7: Render-check with a real pool**

Seed three approved-and-warmed rows into the local `data/demo.db`, run the app
on 8947, load it five times, confirm the pills change between loads and wrap
correctly at 390px. Then set the pool empty and confirm the page still looks
deliberate rather than broken. Stop the server.

- [ ] **Step 8: Commit**

```bash
git add src/rulesagent/api/main.py frontend/index.html tests/test_example_rotation.py
git commit -m "demo: serve the approved pool into the page and rotate it

The island ships empty and the server fills it per request from the
approved, warmed rows. Server-side rather than a client fetch so the pills
are in first paint; re-read per request so approving something in /admin
takes effect immediately instead of at the next restart.

The / route becomes an HTMLResponse to do this. gate.html stays a
FileResponse: no pool, no reason to rewrite it on every locked request.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Warm, verify, back up, ship

**This task spends real API credits and needs Jon's explicit go-ahead with a
ceiling, quoted before the run.** Warming N approved questions costs about
`N * $0.0485`. `warm_examples.py`'s `APPROVED_CEILING_USD` must be raised
deliberately for the run and the number quoted in the commit, never edited
quietly.

**Why warming is not a button in `/admin`:** every other spend path in this
project requires an explicit per-run go-ahead with a ceiling, and a button in a
browser erodes exactly that. `/admin` instead shows the unwarmed count and the
exact command, so the UI reports the need and a human still authorises the
spend.

**Files:**
- Modify: `scripts/warm_examples.py`
- Create: `scripts/check_example_cache.py`
- Create: `scripts/export_examples.py`
- Modify: `evals/build_metrics_history.py`

**Interfaces:**
- Consumes: `list_examples`, `mark_warmed`, `pool_for_frontend` from Task 1.
- Produces: nothing later tasks consume.

- [ ] **Step 1: Point the warm script at the database**

Delete its `EXAMPLES` list. Warm every approved, unretired row with no
`warmed_at`, skip anything already in the cache, and record success:

```python
import os  # noqa: E402  (add beside the existing imports)

from rulesagent.demo_db import list_examples, mark_warmed  # noqa: E402

# Same env var the app reads, so a container run hits /app/data/demo.db and a
# local run hits data/demo.db. Getting this wrong warms a database nobody
# serves from, which is a real mistake this project has already made once.
DEMO_DB = Path(os.environ.get("DEMO_DB_PATH", REPO / "data" / "demo.db"))


def pending(db_path: Path = DEMO_DB) -> list[dict]:
    """Approved, not retired, not yet warmed."""
    return [r for r in list_examples(db_path) if r["warmed_at"] is None]
```

and in `main()`, replacing the loop over `EXAMPLES`:

```python
    rows = pending()
    print(f"{len(rows)} approved example(s) awaiting warm. "
          f"Estimated ~${0.0485 * len(rows):.2f} at the measured mean. "
          f"Approved ceiling for this run: ${APPROVED_CEILING_USD:.2f}.")

    for row in rows:
        q = row["question"]
        if total >= APPROVED_CEILING_USD:
            print(f"\nSTOPPING at ${total:.4f}, ceiling ${APPROVED_CEILING_USD:.2f}.")
            return 1
        if api_main._lookup_example_cache(q, agent) is not None:
            # Already cached under the CURRENT key -- a real hit, not a guess.
            mark_warmed(DEMO_DB, row["id"])
            print(f"[skip] already cached: {q[:60]}")
            continue
        ...                      # existing generate + store block, unchanged
        mark_warmed(DEMO_DB, row["id"])
```

`mark_warmed` goes **after** the cache store, never before: a row flagged warmed
whose answer is not actually cached is exactly the state that puts a slow paid
pill on the page.

**Raised by the final review of Tasks 1 and 2 (2026-07-28):** `mark_warmed` sets
`warmed_at` unconditionally and silently no-ops on an id that does not exist
(`rowcount == 0`). It is the only gate keeping an unwarmed example off the public
page, so when this task wires it up, also assert `cur.rowcount == 1` there and
fail loudly if it is not. A warm run that silently marks nothing, or marks the
wrong row, currently looks identical to a successful one.

- [ ] **Step 2: Write the cache checker**

```python
"""Report which approved examples are really in the answer cache right now.

WHY SEPARATE from the warmed_at column: that column is a claim, and the cache
key folds in generator model, effort, system-prompt version, rewrite version
and corpus fingerprint. Change any one of those and every warmed answer
silently stops matching, while warmed_at still reads like a date. Then every
pill quietly becomes a paid ~13s call and nothing errors. This is how you find
out, and it costs nothing to run.

    flyctl ssh console --app rulemancer -C "python scripts/check_example_cache.py"
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from rulesagent.api import main as api_main  # noqa: E402
from rulesagent.demo_db import list_examples  # noqa: E402
from rulesagent.generate.answer import GEN_EFFORT, RulesAgent  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from warm_examples import DEMO_DB, VECTOR_MODEL  # noqa: E402


def main() -> int:
    store = VectorStore.load(REPO / "data" / "parsed" / f"vector_{VECTOR_MODEL}.pkl")
    agent = RulesAgent(store, effort=GEN_EFFORT)

    stale = 0
    for row in list_examples(DEMO_DB):
        hit = api_main._lookup_example_cache(row["question"], agent) is not None
        flagged = row["warmed_at"] is not None
        if flagged and not hit:
            stale += 1
            print(f"STALE  flagged warmed, cache misses: {row['question'][:70]}")
        elif hit and not flagged:
            print(f"ready  cached but not flagged: {row['question'][:70]}")
        else:
            print(f"{'ok    ' if hit else 'cold  '} {row['question'][:70]}")

    if stale:
        print(f"\n{stale} example(s) claim to be warmed and are not. They are "
              f"live on the demo as slow, paid clicks. Re-run "
              f"scripts/warm_examples.py.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Write the export, so unversioned state has a backup**

```python
"""Dump the approved example pool to JSON so it can be committed.

The pool lives on the Fly volume because /admin cannot commit to git. That
makes it the one piece of curated content in this project with no version
history. This is the seatbelt:

    flyctl ssh console --app rulemancer -C "python scripts/export_examples.py" > docs/evidence/example-pool-backup.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from rulesagent.demo_db import list_examples  # noqa: E402
from warm_examples import DEMO_DB  # noqa: E402

rows = [
    {"question": r["question"], "approved_at": r["approved_at"],
     "warmed": r["warmed_at"] is not None}
    for r in list_examples(DEMO_DB)
]
print(json.dumps(rows, indent=2, ensure_ascii=False))
```

- [ ] **Step 4: Approve a real batch in `/admin`**

Open `https://rulemancer.jongorecki.com/admin`, read the candidates, edit
anything that needs it, approve the good ones. Aim for at least 10 so the
rotation has something to rotate. **Jon does this. Do not approve on his
behalf.**

- [ ] **Step 5: Quote the cost, get the go-ahead, then warm in the container**

State the exact number first: unwarmed count times $0.0485, and the ceiling
being set. Then, with Jon's yes:

```bash
flyctl ssh console --app rulemancer -C "python scripts/warm_examples.py"
```

**Inside the container, not locally.** The running app reads the cache on the
volume; a local run warms a database nobody serves from. This exact mistake has
already happened once on this project.

- [ ] **Step 6: Verify against production, in a browser**

```bash
flyctl ssh console --app rulemancer -C "python scripts/check_example_cache.py"
```

Expected: every row `ok`, exit 0. Then open `https://rulemancer.jongorecki.com`,
unlock, reload a few times to see the rotation, and click a rotated pill. It
must come back in well under a second. **curl is not enough:** what is being
verified is what a visitor experiences, and this project has already shipped a
bug that every test and every curl check passed straight through.

- [ ] **Step 7: Back up the pool**

```bash
flyctl ssh console --app rulemancer -C "python scripts/export_examples.py" > docs/evidence/example-pool-backup.json
```

- [ ] **Step 8: Update the roadmap row**

In `evals/build_metrics_history.py`, set the `rotating-examples` row's `status`
to `"shipped"`, add evidence entries for the new scripts and the admin
handlers, and keep `metric.basis` at `"unknown"` unless click-rate was actually
measured.

Run: `.venv/Scripts/python.exe -m pytest tests/test_roadmap_inventory.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add scripts/ evals/build_metrics_history.py docs/evidence/example-pool-backup.json
git commit -m "demo: warm approved examples from the database, plus checker and backup

warm_examples.py now reads approved rows instead of a hardcoded list, skips
anything already cached, and sets warmed_at only AFTER the answer is stored:
a row flagged warmed whose answer is not cached is precisely the state that
puts a slow paid pill on the page.

check_example_cache.py exists because warmed_at is a claim while the real
cache key folds in model, effort, prompt version and corpus fingerprint. Any
pipeline change invalidates every warmed answer while the column still reads
like a date.

export_examples.py backs up the pool, which is the only curated content here
with no version history, because /admin cannot commit to git.

Spend for this run: \$X.XX (fill from the run output) against a \$Y.YY
approved ceiling.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## What this plan deliberately does not do

- **No bulk approve.** "Approve top 10" would delete the only control that
  makes publishing strangers' text safe, while looking like a convenience.
- **No automatic content filtering.** No length rule, no keyword list, no model
  judging whether a question is appropriate. A machine deciding what is safe to
  publish is the thing being avoided, not a feature that was skipped.
- **No warm button in `/admin`.** Spending is a per-run decision with a
  ceiling. The page reports the need and shows the command.
- **No per-visitor personalisation.** Rotation is random per load. There is no
  profile to build.
- **No new telemetry.** Whether rotated examples get clicked more is answerable
  from the existing `query` event stream. A click-tracking endpoint would be new
  public surface for a question nobody has asked yet.
- **No hard delete.** Retire is a timestamp. "Was this ever public?" stays
  answerable.
