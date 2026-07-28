# Rotating Demo Examples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**STATUS: DESIGN ONLY.** Written 2026-07-28 at Jon's request so it exists for
when there is enough demo traffic to draw from. Rule 0 applies: nothing here is
built until Jon rules on it. **Task 4 spends API credits and needs a separate
explicit go-ahead with a ceiling, even after the plan is approved.**

**Goal:** Replace the demo's four hardcoded example questions with a curated pool
of real questions visitors asked, rotating a few at a time, without ever losing
the property that makes the examples feel good: pre-warmed, so a click is 85ms
and $0.00 instead of ~12.9s and ~$0.0485.

**Architecture:** Three moving parts, deliberately separated by who is trusted.
A **read-only extraction script** turns production `events.question` rows into a
ranked candidate list for Jon to read. **Jon curates** and pastes chosen strings
into a single pool that lives in exactly one place. A **warm step** fills the
answer cache for every pool entry and flips its `warmed` flag, and the frontend
only ever shows entries whose flag is true. Nothing auto-publishes: a stranger's
typed text cannot reach the page without passing through a human.

**Tech Stack:** Python 3.12 stdlib (`sqlite3`, `json`, `re`), pytest, Playwright
(already a dev dependency, driven from `file://` with no server), vanilla JS in
`frontend/index.html`, `flyctl ssh console` for anything touching production.

## Global Constraints

Copied from `CLAUDE.md`, `Token-Economy-Policy.md`, and the gated-demo work.
Every task's requirements implicitly include this section.

- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Open JSON and
  SQLite text with `encoding="utf-8"`; the Windows cp1252 default fails here.
- **Jon runs the app on port 8000. Never bind or kill it.** Use 8947 for render
  checks and stop it when done.
- **Never run the full pytest suite while an eval arm is running.** Run only the
  files covering the change.
- **Verify UI by rendering.** Serve it, open it, look at it. Reading markup is
  not verification.
- **Production reads `/app/data/demo.db` on the Fly volume; `scripts/codes.py`
  and friends write the LOCAL `data/demo.db` by default.** Anything that must
  see real traffic runs inside the container via
  `flyctl ssh console --app rulemancer -C "..."`. This has bitten this project
  twice (the code CLI and the cache warm).
- **Set any Fly secret whose value starts with `/` from PowerShell, not Git
  Bash**, which rewrites POSIX paths into `C:/Program Files/Git/...`.
- **Spending API credits needs Jon's explicit approval per run, with a
  ceiling.** The standing delegation grant does not cover spend.
- **Commit per task** on master with the `Co-Authored-By: Claude Opus 5
  <noreply@anthropic.com>` trailer.
- **Privacy rule for this feature specifically:** `events.question` holds text
  typed by strangers into a public box. It may be personal, malformed, or
  hostile. It is **review material, never publishable output**. No step in this
  plan may write a candidate string into the pool automatically, and no script
  here may print candidate text into a file that gets committed.
- **Voice, if any user-facing copy is added:** contractions, plain words, no em
  dashes, no corporate filler. Jon's register is a millennial who likes Magic
  and memes but is not chronically online.

## Prerequisite

**Do not start until the pool has something to draw from.** As of 2026-07-28
production holds 11 `query` events and 9 distinct questions, which is not enough
to curate 12 good examples from. Task 1 is still safe to build early (it only
reads), but Tasks 2 to 4 are pointless until roughly 60+ distinct questions
exist. Check with:

```bash
flyctl ssh console --app rulemancer -C "python -c \"import sqlite3;c=sqlite3.connect('/app/data/demo.db');print(c.execute(\\\"select count(distinct question) from events where kind='query' and question<>''\\\").fetchone()[0])\""
```

## File Structure

| File | Responsibility |
|---|---|
| `scripts/example_candidates.py` (create) | Read-only. Turns production `events` rows into a ranked, deduplicated candidate list printed for human review. Never writes anything. |
| `tests/test_example_candidates.py` (create) | Guards the extraction and ranking against a temp SQLite fixture. No production access. |
| `frontend/index.html` (modify) | Holds the pool as a strict-JSON `<script type="application/json" id="example-pool">` block, replacing the `EXAMPLES` const at line 100. Renders a rotating subset from it. |
| `scripts/warm_examples.py` (modify) | Reads the pool out of `index.html` instead of carrying its own copy. Warms only entries not already cached. |
| `scripts/check_example_cache.py` (create) | Reports, per pool entry, whether the CURRENT config has a cache hit. Run in the container after any pipeline change. |
| `tests/test_example_pool.py` (create) | Guards the single-source-of-truth property and the pool's shape. |
| `tests/test_example_rotation.py` (create) | Playwright test: only warmed entries render, the count is right, and the selection is stable within a page load. |
| `evals/build_metrics_history.py` (modify) | Flip the `rotating-examples` roadmap row from `open` to `shipped` with real evidence. |

---

### Task 1: Candidate extraction from real traffic

Read-only, no production writes, no spend. Safe to build before there is enough
traffic to use it.

**Files:**
- Create: `scripts/example_candidates.py`
- Test: `tests/test_example_candidates.py`

**Interfaces:**
- Consumes: nothing from earlier tasks. Reads the `events` table defined in
  `src/rulesagent/demo_db.py` (`id, code_id, ts, kind, ip_hash, question,
  answered, input_tokens, output_tokens, cost_usd, latency_ms`).
- Produces: `load_questions(db_path: Path) -> list[dict]` and
  `rank_candidates(rows: list[dict], *, min_len: int = 20, max_len: int = 200)
  -> list[dict]`. Each returned dict has keys `question`, `times_asked`,
  `answered_rate`, `first_ts`, `last_ts`. Task 2 does not import these; a human
  is the interface between them, on purpose.

- [ ] **Step 1: Write the failing test**

```python
"""Candidate extraction reads real traffic, so it gets tested on fake traffic.

WHY read-only and why a human in the middle: `events.question` is text typed by
strangers into a public box. Ranking it is fine; publishing it automatically is
not. These tests pin the filtering rules that decide what a human even gets
shown, and pin that the module has no write path at all.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.example_candidates import load_questions, rank_candidates


def _db(tmp_path: Path, rows: list[tuple]) -> Path:
    """rows are (kind, question, answered) triples."""
    path = tmp_path / "demo.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "code_id INTEGER, ts TEXT NOT NULL, kind TEXT NOT NULL, ip_hash TEXT, "
        "question TEXT, answered INTEGER, input_tokens INTEGER, "
        "output_tokens INTEGER, cost_usd REAL, latency_ms INTEGER)"
    )
    for i, (kind, question, answered) in enumerate(rows):
        conn.execute(
            "INSERT INTO events (code_id, ts, kind, ip_hash, question, answered) "
            "VALUES (1, ?, ?, 'h', ?, ?)",
            (f"2026-07-28T00:00:{i:02d}+00:00", kind, question, answered),
        )
    conn.commit()
    conn.close()
    return path


def test_only_query_events_count(tmp_path):
    db = _db(tmp_path, [
        ("query", "Can I respond to a land being played?", 1),
        ("unlock", "", None),
        ("denied", "", None),
    ])
    rows = load_questions(db)
    assert len(rows) == 1
    assert rows[0]["question"] == "Can I respond to a land being played?"


def test_repeats_collapse_and_count(tmp_path):
    """The same question asked twice is one candidate asked twice, and casing
    or stray whitespace must not split it into two."""
    db = _db(tmp_path, [
        ("query", "How does cascade interact with the stack?", 1),
        ("query", "  how does CASCADE interact with the stack?  ", 1),
    ])
    rows = load_questions(db)
    assert len(rows) == 1
    assert rows[0]["times_asked"] == 2


def test_answered_rate_is_reported(tmp_path):
    db = _db(tmp_path, [
        ("query", "Does deathtouch trample assign one damage per blocker?", 1),
        ("query", "Does deathtouch trample assign one damage per blocker?", 0),
    ])
    assert rank_candidates(load_questions(db))[0]["answered_rate"] == 0.5


def test_ranking_filters_junk_by_length(tmp_path):
    db = _db(tmp_path, [
        ("query", "hi", 1),
        ("query", "x" * 900, 1),
        ("query", "Can I respond to a land being played?", 1),
    ])
    kept = [r["question"] for r in rank_candidates(load_questions(db))]
    assert kept == ["Can I respond to a land being played?"]


def test_ranking_orders_by_times_asked(tmp_path):
    db = _db(tmp_path, [
        ("query", "Can I respond to a land being played?", 1),
        ("query", "How does cascade interact with the stack?", 1),
        ("query", "How does cascade interact with the stack?", 1),
    ])
    assert rank_candidates(load_questions(db))[0]["times_asked"] == 2


def test_module_has_no_write_path():
    """A read-only tool stays read-only. If someone adds an INSERT here later,
    this fails and they have to justify it in review rather than in passing."""
    source = (Path(__file__).resolve().parents[1]
              / "scripts" / "example_candidates.py").read_text(encoding="utf-8")
    upper = source.upper()
    for statement in ("INSERT ", "UPDATE ", "DELETE ", "DROP "):
        assert statement not in upper, (
            f"SQL {statement.strip()} appears in a script that must only read")
    for call in ("write_text(", ".commit()", "open("):
        assert call not in source, (
            f"{call} appears in a script that must not write anything")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_example_candidates.py -v`
Expected: FAIL at import, `ModuleNotFoundError: No module named 'scripts.example_candidates'`.

If the import fails because `scripts/` has no `__init__.py`, add an empty one
and note it in the commit; the repo's other script tests import by path, so
follow whichever convention `tests/test_demo_db.py` already uses rather than
inventing a third.

- [ ] **Step 3: Write the script**

```python
"""Rank real demo questions as candidates for the rotating example pool.

READ-ONLY BY DESIGN. This reads `events.question`, which is text strangers
typed into a public box. It ranks and prints; a human picks. Nothing here
writes to the pool, to the database, or to any committed file, because
auto-publishing user input onto a portfolio page is the failure mode this
feature has to avoid.

Run it against PRODUCTION, which is not the local database:

    flyctl ssh console --app rulemancer -C "python scripts/example_candidates.py"

Locally it reads data/demo.db, which is fine for testing the output format and
useless for real candidates.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path("/app/data/demo.db")
MIN_LEN = 20     # shorter than this is "hi" and "test", not a rules question
MAX_LEN = 200    # longer than this reads badly on a pill button


def _normalize(question: str) -> str:
    """Same folding the answer cache uses (`_normalize_question` in the API):
    case and whitespace only. Two visitors typing the same question with
    different capitalisation are one candidate, not two."""
    return " ".join(question.strip().lower().split())


def load_questions(db_path: Path) -> list[dict]:
    """Every distinct question ever asked, with how often and how it went."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT question, answered, ts FROM events "
            "WHERE kind = 'query' AND question IS NOT NULL AND question <> '' "
            "ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    grouped: dict[str, dict] = {}
    for row in rows:
        key = _normalize(row["question"])
        entry = grouped.setdefault(key, {
            "question": row["question"].strip(),  # first spelling seen wins
            "times_asked": 0,
            "_answered": 0,
            "first_ts": row["ts"],
            "last_ts": row["ts"],
        })
        entry["times_asked"] += 1
        entry["_answered"] += 1 if row["answered"] else 0
        entry["last_ts"] = row["ts"]

    out = []
    for entry in grouped.values():
        entry["answered_rate"] = entry["_answered"] / entry["times_asked"]
        entry.pop("_answered")
        out.append(entry)
    return out


def rank_candidates(rows: list[dict], *, min_len: int = MIN_LEN,
                    max_len: int = MAX_LEN) -> list[dict]:
    """Filter obvious junk, then most-asked first.

    Length is the only automatic filter on purpose. Anything cleverer (topic
    detection, profanity, personal data) would be a machine deciding what is
    safe to publish, and the whole point is that a human decides that.
    """
    kept = [r for r in rows if min_len <= len(r["question"]) <= max_len]
    return sorted(kept, key=lambda r: (-r["times_asked"], r["question"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    if not args.db.exists():
        print(f"no database at {args.db}. Inside the container this is "
              f"/app/data/demo.db; locally it is data/demo.db.", file=sys.stderr)
        return 1

    ranked = rank_candidates(load_questions(args.db))
    print(f"{len(ranked)} candidate(s) after filtering. Read them yourself "
          f"before any of these go on a public page.\n")
    for i, row in enumerate(ranked[:args.limit], start=1):
        print(f"{i:3d}. asked {row['times_asked']}x  "
              f"answered {row['answered_rate']:.0%}  {row['question']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_example_candidates.py -v`
Expected: PASS, all six.

- [ ] **Step 5: Run it against production, read the output, change nothing**

```bash
flyctl ssh console --app rulemancer -C "python scripts/example_candidates.py"
```

Expect a short list at first. This step is a smoke test of the SQL against the
real schema, not the curation pass. **Do not paste anything from this output
into a file yet.**

- [ ] **Step 6: Commit**

```bash
git add scripts/example_candidates.py tests/test_example_candidates.py
git commit -m "demo: rank real questions as example candidates, read only

Reads events.question, folds case and whitespace the same way the answer
cache does, filters by length only, and prints for human review. No write
path, and a test fails if one is ever added: auto-publishing strings that
strangers typed into a public box is the thing this feature must not do.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: One pool, one source of truth

Today the four examples exist twice: `frontend/index.html:100` and
`scripts/warm_examples.py:60`. The warm script's own comment says they must stay
byte-identical, which is a comment doing a test's job. A pool of a dozen entries
makes that duplication untenable, so it goes away first.

**Files:**
- Modify: `frontend/index.html` (replace the `EXAMPLES` const at line 100)
- Modify: `scripts/warm_examples.py` (replace its `EXAMPLES` list at line 60)
- Test: `tests/test_example_pool.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `load_pool(index_html: Path) -> list[dict]` in
  `scripts/warm_examples.py`. Each entry is `{"q": str, "warmed": bool}`.
  Task 3 reads the same block from JS; Task 4 calls `load_pool`.

- [ ] **Step 1: Write the failing test**

```python
"""The pool lives in one place, and both readers agree on what it says.

WHY: before this, the four examples were duplicated between index.html and
warm_examples.py, with a comment asking future editors to keep them
byte-identical. The cache key is built from the question text, so a drifted
copy does not error -- it silently misses the cache, and the demo's most
clicked control quietly becomes a ~12.9s, ~$0.0485 call that looks fine in
review.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO / "frontend" / "index.html"
WARM = REPO / "scripts" / "warm_examples.py"

POOL_RE = re.compile(
    r'<script type="application/json" id="example-pool">(.*?)</script>',
    re.DOTALL)


def test_pool_block_exists_and_is_strict_json():
    match = POOL_RE.search(INDEX_HTML.read_text(encoding="utf-8"))
    assert match, "no <script id=\"example-pool\"> block in frontend/index.html"
    pool = json.loads(match.group(1))
    assert isinstance(pool, list) and pool, "the pool must be a non-empty array"


def test_every_entry_has_a_question_and_a_warmed_flag():
    pool = json.loads(POOL_RE.search(
        INDEX_HTML.read_text(encoding="utf-8")).group(1))
    for entry in pool:
        assert isinstance(entry.get("q"), str) and entry["q"].strip(), entry
        assert isinstance(entry.get("warmed"), bool), (
            f"{entry.get('q')!r} has no boolean 'warmed' flag; the frontend "
            f"uses it to decide what is safe to show")


def test_no_duplicate_questions_after_normalising():
    """Two entries differing only in case or spacing share one cache key, so
    one of them is dead weight in the rotation."""
    pool = json.loads(POOL_RE.search(
        INDEX_HTML.read_text(encoding="utf-8")).group(1))
    keys = [" ".join(e["q"].strip().lower().split()) for e in pool]
    assert len(keys) == len(set(keys)), "duplicate questions in the pool"


def test_warm_script_reads_the_pool_instead_of_carrying_a_copy():
    source = WARM.read_text(encoding="utf-8")
    assert "def load_pool(" in source, "warm_examples.py must read the pool"
    assert "EXAMPLES = [" not in source, (
        "warm_examples.py still carries its own copy of the questions")


def test_warm_script_and_frontend_see_the_same_pool():
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from warm_examples import load_pool

    from_script = [e["q"] for e in load_pool(INDEX_HTML)]
    from_html = [e["q"] for e in json.loads(POOL_RE.search(
        INDEX_HTML.read_text(encoding="utf-8")).group(1))]
    assert from_script == from_html
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_example_pool.py -v`
Expected: FAIL. `test_pool_block_exists_and_is_strict_json` fails because there
is no pool block yet, and `test_warm_script_reads_the_pool_instead_of_carrying_a_copy`
fails on the surviving `EXAMPLES = [` list.

- [ ] **Step 3: Put the pool in `frontend/index.html`**

Replace the `const EXAMPLES = [...]` block at line 100 with a JSON island in
`<head>`, and a const that reads it. A JSON island rather than a fetch: the
pills are above the fold, and fetching them would pop them in after first paint
for no benefit on a same-origin file this small.

```html
<!-- The example pool. SINGLE SOURCE OF TRUTH: scripts/warm_examples.py parses
     this exact block, so there is no second copy to drift. Strict JSON, not a
     JS literal, so Python can json.loads it without evaluating JavaScript.
     `warmed` is set by scripts/warm_examples.py after a question is actually
     in the answer cache; the frontend shows only warmed entries, so a visitor
     never clicks a pill that costs money and takes ~13 seconds. -->
<script type="application/json" id="example-pool">
[
  {"q": "If my creature has trample and deathtouch, how much damage can trample over the blocker?", "warmed": true},
  {"q": "Can I respond to a land being played?", "warmed": true},
  {"q": "How does cascade interact with the stack?", "warmed": true},
  {"q": "If I copy [Emrakul, the Promised End]'s cast trigger, do I control two turns?", "warmed": true}
]
</script>
```

Then, where `const EXAMPLES` used to be:

```javascript
// Read from the JSON island in <head>. Only warmed questions are eligible:
// an unwarmed one is a cache miss, which is ~12.9s and ~$0.0485 on the most
// clicked control on the page.
const EXAMPLE_POOL = JSON.parse(
  document.getElementById("example-pool").textContent)
  .filter(e => e.warmed)
  .map(e => e.q);
const EXAMPLES = EXAMPLE_POOL;   // Task 3 replaces this with the rotation
```

The four questions above are the current ones, copied exactly. They are already
warmed in production, so this task changes no behaviour at all: same four
strings, same cache keys, same page. That is deliberate, so any breakage here is
attributable to the refactor and not to new content.

- [ ] **Step 4: Make `scripts/warm_examples.py` read the pool**

Delete its `EXAMPLES` list. Add:

```python
import json
import re

INDEX_HTML = REPO / "frontend" / "index.html"

_POOL_RE = re.compile(
    r'<script type="application/json" id="example-pool">(.*?)</script>',
    re.DOTALL)


def load_pool(index_html: Path = INDEX_HTML) -> list[dict]:
    """The example pool, parsed out of frontend/index.html.

    The pool lives in the HTML because that is where the browser needs it, and
    this script follows it rather than keeping a second copy. It used to keep a
    copy, guarded only by a comment asking editors to keep them byte-identical;
    a drifted copy is a silent permanent cache miss, never a loud error.
    """
    match = _POOL_RE.search(index_html.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(
            f"no <script id=\"example-pool\"> block in {index_html}. "
            f"The pool is the single source of truth and this script cannot "
            f"guess it.")
    return json.loads(match.group(1))
```

and change `main()`'s loop header from `for q in EXAMPLES:` to:

```python
    pool = load_pool()
    questions = [entry["q"] for entry in pool]
    ...
    for q in questions:
```

Update the two `len(EXAMPLES)` references in the cost banner and the stop
message to `len(questions)`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_example_pool.py tests/test_frontend_error_detail_surfacing.py -v`
Expected: PASS. The second file is included because it drives `index.html` in a
real browser and will catch a JSON island that breaks page JS.

- [ ] **Step 6: Render-check the demo locally**

```bash
.venv/Scripts/python.exe -m http.server 8947 --directory frontend
```

Open `http://127.0.0.1:8947/`, confirm the four example pills still render and
still read correctly. Stop the server. Never port 8000.

- [ ] **Step 7: Commit**

```bash
git add frontend/index.html scripts/warm_examples.py tests/test_example_pool.py
git commit -m "demo: one example pool, read by both the page and the warm script

The four examples lived in two files kept in sync by a comment. The cache
key is built from the question text, so a drifted copy does not error, it
silently misses and turns the most clicked control on the page into a
~12.9s, ~\$0.0485 call. Now there is one JSON island and both readers parse
it. Same four questions, byte for byte: this refactor changes nothing a
visitor sees.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Rotate a subset per page load

**Files:**
- Modify: `frontend/index.html` (the `EXAMPLES` const from Task 2)
- Test: `tests/test_example_rotation.py`

**Interfaces:**
- Consumes: `EXAMPLE_POOL` and the `#example-pool` JSON island from Task 2.
- Produces: `pickExamples(pool, n)` in page JS, and the rendered pills. Task 4
  does not consume these.

- [ ] **Step 1: Write the failing test**

```python
"""Rotation shows a different handful each load, and never an unwarmed one.

Driven in a real headless browser from file://, the same way
tests/test_frontend_error_detail_surfacing.py drives this page: no server, no
port 8000 or 8947, no API spend.
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
    r'<script type="application/json" id="example-pool">(.*?)</script>',
    re.DOTALL)

EXAMPLES_SHOWN = 4


def _pool() -> list[dict]:
    return json.loads(POOL_RE.search(
        INDEX_HTML.read_text(encoding="utf-8")).group(1))


def _pills(page) -> list[str]:
    """The pill labels, minus the decorative sigil the button renders inside a
    span. Read the rendered text rather than data-arg so this checks what a
    visitor actually sees."""
    return [el.inner_text().replace("✦", "").strip()
            for el in page.query_selector_all('[data-action="example"]')]


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def test_shows_exactly_four_pills(browser):
    page = browser.new_page()
    page.goto(INDEX_HTML.resolve().as_uri())
    assert len(_pills(page)) == EXAMPLES_SHOWN
    page.close()


def test_every_rendered_pill_is_a_warmed_pool_entry(browser):
    """The whole point. An unwarmed pill is a slow, paid click."""
    warmed = {e["q"] for e in _pool() if e["warmed"]}
    page = browser.new_page()
    page.goto(INDEX_HTML.resolve().as_uri())
    shown = _pills(page)
    assert set(shown) <= warmed, (
        f"pills not present as warmed pool entries: {set(shown) - warmed}")
    page.close()


def test_selection_is_stable_within_one_page_load(browser):
    """Re-rendering the composer must not reshuffle the pills under someone
    who is reading them."""
    page = browser.new_page()
    page.goto(INDEX_HTML.resolve().as_uri())
    first = _pills(page)
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    page.wait_for_timeout(100)
    assert _pills(page) == first
    page.close()


def test_rotation_varies_across_loads(browser):
    """Skipped until the pool is bigger than what one load shows -- with a
    pool of four and four shown, there is nothing to rotate, and asserting
    variety would be asserting a coin flip."""
    pool = [e for e in _pool() if e["warmed"]]
    if len(pool) <= EXAMPLES_SHOWN:
        pytest.skip(f"pool has {len(pool)} warmed entries, needs more than "
                    f"{EXAMPLES_SHOWN} to rotate")
    seen = set()
    for _ in range(12):
        page = browser.new_page()
        page.goto(INDEX_HTML.resolve().as_uri())
        seen.add(tuple(_pills(page)))
        page.close()
    assert len(seen) > 1, "twelve loads produced the same four pills every time"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_example_rotation.py -v`
Expected: the first three pass already (four entries, all warmed, static), and
`test_rotation_varies_across_loads` SKIPS. That is the correct starting state:
the rotation tests are real but have nothing to bite on until the pool grows.
Confirm the skip reason names the pool size.

- [ ] **Step 3: Implement the rotation**

Replace Task 2's placeholder const:

```javascript
// Show a handful from the pool, chosen fresh per page load. Chosen ONCE at
// module scope, not per render: the composer re-renders on resize and on new
// chats, and reshuffling the pills while someone is reading them is the kind
// of motion that makes a page feel broken rather than alive.
const EXAMPLES_SHOWN = 4;

function pickExamples(pool, n) {
  const eligible = pool.filter(e => e.warmed).map(e => e.q);
  // Fisher-Yates on a copy. Not seeded: variety across loads is the feature,
  // and nothing here needs to be reproducible.
  const shuffled = eligible.slice();
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

Nothing else changes: the render code at `frontend/index.html:551` already maps
over `EXAMPLES`, and `case "example": send(t.dataset.arg)` already sends the
pill's own text.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_example_rotation.py tests/test_example_pool.py -v`
Expected: PASS, with `test_rotation_varies_across_loads` still skipping until
the pool grows past four.

- [ ] **Step 5: Render-check**

Serve `frontend/` on 8947, load it five times, and confirm the pills render,
wrap correctly at 390px, and that clicking one still sends that question. Stop
the server.

- [ ] **Step 6: Commit**

```bash
git add frontend/index.html tests/test_example_rotation.py
git commit -m "demo: rotate example pills from the warmed pool

Picks four warmed questions per page load, once at module scope so a
resize does not reshuffle them mid-read. Only warmed entries are eligible,
so a visitor can never click a pill that costs money and takes ~13s.

The variety test skips while the pool is four deep. It is written now so
it starts working the moment real questions land in the pool.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Curate, warm, verify, ship

**This task spends real API credits and needs Jon's explicit go-ahead with a
ceiling, quoted before the run.** At the measured $0.0485 mean, warming N new
questions costs about `N * 0.0485`; a pool of 12 means 8 new ones, roughly
$0.39. `warm_examples.py` already has a stop-and-report ceiling
(`APPROVED_CEILING_USD`), which must be raised deliberately for the run and
quoted in the commit, not edited quietly.

**Files:**
- Modify: `frontend/index.html` (the pool contents only)
- Modify: `scripts/warm_examples.py` (skip already-warmed entries, raise the ceiling)
- Create: `scripts/check_example_cache.py`
- Modify: `evals/build_metrics_history.py` (roadmap row `rotating-examples`)

**Interfaces:**
- Consumes: `load_pool(index_html: Path) -> list[dict]` from Task 2;
  `rank_candidates` output from Task 1, via Jon reading it.
- Produces: nothing later tasks consume. This is the last task.

- [ ] **Step 1: Get candidates and have Jon curate them**

```bash
flyctl ssh console --app rulemancer -C "python scripts/example_candidates.py --limit 60"
```

Jon picks the ones that go in. Selection criteria, for the conversation rather
than for a filter: it should read like something a person would actually ask, be
answerable from the rules rather than from a judge's discretion, and show off a
different corner of the game from the ones already in the pool. **Do not pick
for him and do not paste candidate text into any file before he has read it.**

- [ ] **Step 2: Add the chosen questions to the pool with `"warmed": false`**

Append to the JSON island in `frontend/index.html`. `false` is not a formality:
Task 3's filter means an unwarmed entry is simply never shown, so the page stays
correct in the window between adding a question and warming it.

- [ ] **Step 3: Make the warm script skip what is already cached**

Re-warming a warmed question costs a full generation for nothing. Add, inside
`main()`'s loop:

```python
        if api_main._lookup_example_cache(q, agent) is not None:
            print(f"[skip] already cached: {q[:60]}")
            continue
```

`_lookup_example_cache` returns the stored payload under the CURRENT config, so
a skip means a real hit under the exact key a visitor's click will build, not a
guess.

- [ ] **Step 4: Write the cache checker**

```python
"""Report which pool questions are actually in the answer cache right now.

WHY THIS EXISTS SEPARATELY from the `warmed` flag in the pool: the flag is a
claim committed to a file, and the cache key folds in the generator model,
effort, system-prompt version, rewrite version and corpus fingerprint. Change
any of those and every warmed answer silently stops matching -- the flag still
says true, and every pill quietly becomes a paid ~13s call. This is how you
find out, and it costs nothing to run.

    flyctl ssh console --app rulemancer -C "python scripts/check_example_cache.py"
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from rulesagent.api import main as api_main  # noqa: E402
from rulesagent.generate.answer import GEN_EFFORT, RulesAgent  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from warm_examples import VECTOR_MODEL, load_pool  # noqa: E402


def main() -> int:
    store = VectorStore.load(REPO / "data" / "parsed" / f"vector_{VECTOR_MODEL}.pkl")
    agent = RulesAgent(store, effort=GEN_EFFORT)

    stale = 0
    for entry in load_pool():
        hit = api_main._lookup_example_cache(entry["q"], agent) is not None
        if entry["warmed"] and not hit:
            stale += 1
            print(f"STALE  flag says warmed, cache misses: {entry['q'][:70]}")
        elif hit and not entry["warmed"]:
            print(f"ready  cached but flagged unwarmed: {entry['q'][:70]}")
        else:
            print(f"{'ok    ' if hit else 'cold  '} {entry['q'][:70]}")

    if stale:
        print(f"\n{stale} entry(s) claim to be warmed and are not. Re-run "
              f"scripts/warm_examples.py, or flip their flag to false.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Get the go-ahead, then warm in the container**

Quote the exact number first: count the unwarmed entries, multiply by $0.0485,
and state the ceiling being set. Then, with Jon's yes:

```bash
flyctl ssh console --app rulemancer -C "python scripts/warm_examples.py"
```

**Inside the container, not locally.** The running app reads the cache on the
Fly volume; a local run warms a database nobody serves from. This exact mistake
has already happened once on this project.

- [ ] **Step 6: Flip the flags and verify against production**

Set `"warmed": true` for each question the run reported warming, then:

```bash
flyctl ssh console --app rulemancer -C "python scripts/check_example_cache.py"
```

Expected: every pool entry prints `ok`, exit 0. Then load
`https://rulemancer.jongorecki.com` in a browser, unlock, and click a rotated
example. It must return in well under a second. **curl is not enough here:** the
thing being verified is what a visitor experiences, and this project has already
shipped a bug that every test and every curl check passed straight through.

- [ ] **Step 7: Update the roadmap row**

In `evals/build_metrics_history.py`, change the `rotating-examples` row's
`status` from `"open"` to `"shipped"`, replace `tells_us` with the real
before/after click data if any exists, and add evidence entries for
`scripts/example_candidates.py`, `scripts/check_example_cache.py` and this plan
doc. Keep `metric.basis` honest: it stays `"unknown"` unless click-rate was
actually measured, in which case it becomes `"measured"` with a `cite`.

Run: `.venv/Scripts/python.exe -m pytest tests/test_roadmap_inventory.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/index.html scripts/warm_examples.py scripts/check_example_cache.py evals/build_metrics_history.py
git commit -m "demo: fill the example pool with real questions and warm them

Questions picked by Jon from ranked demo traffic, warmed inside the
container so the cache lands on the Fly volume rather than a local file
nobody serves from. The warm script now skips entries already cached, so
re-running it is free instead of a full regeneration each time.

check_example_cache.py exists because the pool's `warmed` flag is a claim
in a file while the real cache key folds in model, effort, prompt version
and corpus fingerprint. Any pipeline change silently invalidates every
warmed answer while the flag still reads true.

Spend for this run: \$X.XX against a \$Y.YY approved ceiling.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## What this plan deliberately does not do

- **No automatic selection.** Nothing promotes a question to the pool without
  Jon reading it. Ranking is automated; publishing is not. That is the whole
  privacy posture, and a "just take the top 12 by count" shortcut would discard
  it while looking like an optimisation.
- **No per-visitor personalisation.** The rotation is random per load, not
  based on anything about the visitor. There is no profile to build and no
  reason to build one.
- **No new telemetry.** Measuring whether rotated examples get clicked more can
  be done off the existing `query` event stream. A click-tracking endpoint
  would be new surface area on a publicly reachable app for a question nobody
  has asked yet.
- **No pool in a separate file.** It would be one more thing to keep in sync
  with the page, which is the exact problem Task 2 exists to delete.
- **No auto-warm on deploy.** Warming spends money, and money spends on Jon's
  say-so, not on a push.
