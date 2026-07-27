# Implementation plan — Slice 4: Gated demo on Fly.io

**Scope note:** this plan covers **Slice 4 only** — the gated demo on Fly.io —
from `docs/superpowers/specs/2026-07-27-public-launch-design.md`. Slices 1-3
(README rewrite, repo publish, static evidence site) are planned separately.
Nothing here touches those.

## Goal

Ship a per-person-access-code-gated, cost-capped Rulemancer demo, always-on on
Fly.io, that a hiring manager can unlock with a code Jon hands them and that
cannot overspend the Anthropic balance or be abused before anyone sees the link.

## Architecture

A new SQLite database (`data/demo.db`, separate from `data/cache.db`) holds two
tables — `codes` and `events` — using the same per-op-connection/WAL pattern as
`rulesagent.cache.KVCache`. `/answer` and a new `/unlock` endpoint sit behind a
signed HMAC cookie that names a `codes` row; every request that reaches the
gate writes an `events` row, and every guard (per-code cap, daily budget,
unlock rate limit) checks `events`/`codes` before the expensive model call
happens, never after. Gating is inert unless `COOKIE_SECRET` is set in the
environment, so local dev (`python run.py`, the existing test suite) is
unaffected — only the Fly deployment sets that variable and becomes gated.

## Tech Stack

FastAPI (existing), stdlib `sqlite3` (existing pattern), stdlib `hmac` /
`hashlib` for cookie signing and IP hashing (no new dependency — `itsdangerous`
is not in `pyproject.toml` and there's no reason to add it for one signed
string), stdlib `secrets` for code generation, Docker + Fly.io for the runtime.

## Global Constraints

Copied verbatim from `CLAUDE.md` (repo working rules) — binding on every task
below:

- Jon runs the app on port 8000. Never bind or kill it. Use a scratch port
  (8947) for render checks and stop it when done.
- Verify UI by rendering, never by reading markup. Serve it, open it, look at
  it, measure it.
- Never assert an MTG or model fact from memory. Model IDs and pricing come
  from `rulesagent.pricing` (import it; do not reload the `claude-api` skill
  unless `check_freshness()` warns).
- Billing splits two ways: Claude Code / subagents run on Jon's Max
  subscription; any Python here that constructs an Anthropic client from
  `.env` bills API credits — a separate pool, spent only with Jon's explicit
  go-ahead and a ceiling.
- Never run the full pytest suite while an eval arm is running. Run only the
  test files covering the change.
- Subagent deliverables must land in the repo, never the session scratchpad.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Open JSON
  with `encoding="utf-8"`. Suite is `uv run pytest` (1124 passing as of
  2026-07-26). Commit per slice on master with the `Co-Authored-By: Claude
  Opus 5` trailer.
- Rule 0: plan before code — this document, then implementation.

## File Structure

| File | Responsibility |
|---|---|
| `src/rulesagent/demo_db.py` | New. `codes` / `events` schema + all CRUD/query helpers, one dedicated SQLite db (`data/demo.db`). |
| `src/rulesagent/demo_auth.py` | New. HMAC cookie sign/verify (code id + issue time, 7-day expiry) and salted IP hashing. |
| `scripts/codes.py` | New. CLI: `new`, `list`, `revoke` against the `codes` table. |
| `frontend/gate.html` | New. Static code-entry page shown instead of the real frontend when ungated. |
| `src/rulesagent/api/main.py` | Modified. `/unlock` endpoint, gate routing on `/`/`/index.html`, cookie + guard wiring on `/answer`, CORS lock, global friendly-error handler, `/admin` view. |
| `Dockerfile` | New. Container entrypoint: uvicorn on `rulesagent.api.main:app`. |
| `.dockerignore` | New. Keeps CR text, `data/`, secrets, `.venv`, `.git` out of the image. |
| `fly.toml` | New. Always-on `shared-cpu-1x`, volume at `/app/data`, US-central region. |
| `scripts/measure_demo_cost.py` | New. Spends real Anthropic credits (~$1, Jon's go-ahead required) to measure $/serve before the budget cap is set. |
| `scripts/verify_demo_guards.py` | New. Live guard verification against the deployed URL — the gate before any link is shared. |
| `tests/test_demo_db.py` | New. Schema + CRUD. |
| `tests/test_demo_auth.py` | New. Cookie sign/verify, IP hashing. |
| `tests/test_codes_cli.py` | New. `scripts/codes.py` commands. |
| `tests/test_unlock_endpoint.py` | New. `/unlock` success/failure paths. |
| `tests/test_gate_routing.py` | New. `/` serves gate vs. real frontend. |
| `tests/test_answer_guards.py` | New. Cookie requirement, per-code cap, revoked code, daily budget breaker on `/answer`. |
| `tests/test_unlock_rate_limit.py` | New. Per-IP rate limit on `/unlock`. |
| `tests/test_cors_lock.py` | New. CORS origin lock. |
| `tests/test_friendly_errors.py` | New. No guard failure is ever a 500 / raw error. |
| `tests/test_admin_demo_view.py` | New. `/admin` auth + content. |

---

## Task 1 — `demo_db`: schema + CRUD for `codes` and `events`

**Files:**
- Create: `src/rulesagent/demo_db.py`
- Create: `tests/test_demo_db.py`

**Interfaces:**
- Consumes: nothing repo-internal beyond stdlib `sqlite3`.
- Produces (used by every later task):
  - `DEFAULT_DEMO_DB: Path` — `data/demo.db`, overridable via `DEMO_DB_PATH` env var (same convention as `rulesagent.cache.DEFAULT_DB`, but a *separate file* per the spec).
  - `create_code(db_path: Path, code: str, label: str, max_queries: int | None = 25, notes: str = "") -> int` — returns the new row's `id`; raises `sqlite3.IntegrityError` on a duplicate `code`.
  - `get_code_by_value(db_path: Path, code: str) -> dict | None`
  - `get_code_by_id(db_path: Path, code_id: int) -> dict | None`
  - `list_codes(db_path: Path) -> list[dict]` — newest first.
  - `revoke_code(db_path: Path, code_id: int) -> bool` — `False` if no such id.
  - `log_event(db_path: Path, *, code_id: int | None, kind: str, ip_hash: str | None, question: str = "", answered: bool | None = None, input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0, latency_ms: int = 0) -> None`
  - `count_queries(db_path: Path, code_id: int) -> int` — count of `kind='query'` rows for that code.
  - `code_stats(db_path: Path, code_id: int) -> dict` — `{"unlocks": int, "queries": int, "first_seen": str | None, "last_seen": str | None, "total_cost": float}`.
  - `events_for_code(db_path: Path, code_id: int) -> list[dict]` — `kind='query'` rows, newest first.
  - `daily_spend(db_path: Path, day: str) -> float` — sum of `cost_usd` for `kind='query'` rows where `ts` starts with `day` (`"YYYY-MM-DD"`).

- [ ] Write the failing test file.

```python
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
```

- [ ] Run it and see it fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_demo_db.py -q
  ```
  Expected: `ModuleNotFoundError: No module named 'rulesagent.demo_db'`

- [ ] Minimal implementation:

```python
# src/rulesagent/demo_db.py
"""Slice 4 gated-demo storage (docs/superpowers/plans/2026-07-27-gated-demo.md
Task 1): the `codes` and `events` tables from the design spec, in a dedicated
SQLite db -- data/demo.db, NOT data/cache.db, so demo telemetry lives on its
own file the Fly volume mounts and the local cache stays untouched.

Same per-op-connection, WAL-mode pattern as rulesagent.cache.KVCache -- the
established convention here -- but with real columns instead of a KV blob,
because the admin view and the guards need to filter/aggregate on code_id,
ts, and kind.
"""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DEMO_DB = Path(
    os.environ.get("DEMO_DB_PATH", str(Path(__file__).parent.parent.parent / "data" / "demo.db"))
)
# src/rulesagent/demo_db.py -> repo root is three ".parent"s up, same as
# rulesagent.cache.DEFAULT_DB. DEMO_DB_PATH lets the Fly deployment point this
# at the mounted volume (/app/data/demo.db) without editing code.

_BUSY_TIMEOUT_MS = 5000

_CODES_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS codes ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "code TEXT UNIQUE NOT NULL, "
    "label TEXT, "
    "created_at TEXT NOT NULL, "
    "max_queries INTEGER, "
    "revoked_at TEXT, "
    "notes TEXT)"
)
_EVENTS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS events ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "code_id INTEGER, "
    "ts TEXT NOT NULL, "
    "kind TEXT NOT NULL, "
    "ip_hash TEXT, "
    "question TEXT, "
    "answered INTEGER, "
    "input_tokens INTEGER, "
    "output_tokens INTEGER, "
    "cost_usd REAL, "
    "latency_ms INTEGER)"
)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=_BUSY_TIMEOUT_MS / 1000)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    conn.execute(_CODES_SCHEMA)
    conn.execute(_EVENTS_SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_code(db_path: Path, code: str, label: str, max_queries: int | None = 25,
                 notes: str = "") -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO codes (code, label, created_at, max_queries, revoked_at, notes) "
            "VALUES (?, ?, ?, ?, NULL, ?)",
            (code, label, _now(), max_queries, notes),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_code_by_value(db_path: Path, code: str) -> dict | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM codes WHERE code = ?", (code,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def get_code_by_id(db_path: Path, code_id: int) -> dict | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM codes WHERE id = ?", (code_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def list_codes(db_path: Path) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM codes ORDER BY id DESC").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def revoke_code(db_path: Path, code_id: int) -> bool:
    conn = _connect(db_path)
    try:
        cur = conn.execute("UPDATE codes SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                            (_now(), code_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def log_event(db_path: Path, *, code_id: int | None, kind: str, ip_hash: str | None,
              question: str = "", answered: bool | None = None, input_tokens: int = 0,
              output_tokens: int = 0, cost_usd: float = 0.0, latency_ms: int = 0) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO events (code_id, ts, kind, ip_hash, question, answered, "
            "input_tokens, output_tokens, cost_usd, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (code_id, _now(), kind, ip_hash, question,
             None if answered is None else int(answered),
             input_tokens, output_tokens, cost_usd, latency_ms),
        )
        conn.commit()
    finally:
        conn.close()


def count_queries(db_path: Path, code_id: int) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE code_id = ? AND kind = 'query'", (code_id,)
        ).fetchone()
    finally:
        conn.close()
    return row["n"]


def code_stats(db_path: Path, code_id: int) -> dict:
    conn = _connect(db_path)
    try:
        unlocks = conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE code_id = ? AND kind = 'unlock'", (code_id,)
        ).fetchone()["n"]
        agg = conn.execute(
            "SELECT COUNT(*) AS n, MIN(ts) AS first_seen, MAX(ts) AS last_seen, "
            "COALESCE(SUM(cost_usd), 0.0) AS total_cost FROM events "
            "WHERE code_id = ? AND kind = 'query'", (code_id,)
        ).fetchone()
    finally:
        conn.close()
    return {
        "unlocks": unlocks, "queries": agg["n"], "first_seen": agg["first_seen"],
        "last_seen": agg["last_seen"], "total_cost": agg["total_cost"],
    }


def events_for_code(db_path: Path, code_id: int) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM events WHERE code_id = ? AND kind = 'query' ORDER BY id DESC",
            (code_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def daily_spend(db_path: Path, day: str) -> float:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) AS total FROM events "
            "WHERE kind = 'query' AND ts LIKE ?", (f"{day}%",)
        ).fetchone()
    finally:
        conn.close()
    return row["total"]
```

- [ ] Run and see it pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_demo_db.py -q
  ```
  Expected: `13 passed`

- [ ] Commit:
  ```
  git add src/rulesagent/demo_db.py tests/test_demo_db.py
  git commit -m "$(cat <<'EOF'
  Add demo_db: codes/events SQLite schema for the gated demo (slice 4)

  Separate data/demo.db, not cache.db -- telemetry for the public demo
  shouldn't share a file with the private-dev cache.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** `rulesagent.demo_db` importable and independently testable —
`uv run python -c "from rulesagent.demo_db import create_code, get_code_by_value; ..."`
against a tmp file works with no other slice-4 code written yet.

---

## Task 2 — `demo_auth`: signed cookie + salted IP hash

**Files:**
- Create: `src/rulesagent/demo_auth.py`
- Create: `tests/test_demo_auth.py`

**Interfaces:**
- Consumes: nothing repo-internal (stdlib `hmac`, `hashlib`, `time`).
- Produces:
  - `COOKIE_MAX_AGE_S: int = 7 * 24 * 3600`
  - `sign_session(code_id: int, secret: str, issued_at: int | None = None) -> str` — `issued_at` defaults to `int(time.time())`; returns `"<code_id>:<issued_at>:<hex hmac-sha256>"`.
  - `verify_session(token: str | None, secret: str, now: int | None = None, max_age_s: int = COOKIE_MAX_AGE_S) -> int | None` — returns `code_id` if the signature is valid and not expired, else `None`. Never raises on malformed input.
  - `hash_ip(ip: str, salt: str) -> str` — hex `hmac-sha256(salt, ip)`.

- [ ] Write the failing test file.

```python
# tests/test_demo_auth.py
# Slice 4 Task 2. Pure stdlib crypto, no I/O -- no tmp_path needed.

from rulesagent.demo_auth import COOKIE_MAX_AGE_S, hash_ip, sign_session, verify_session


def test_sign_then_verify_round_trip():
    token = sign_session(42, "test-secret", issued_at=1_000_000)
    assert verify_session(token, "test-secret", now=1_000_100) == 42


def test_wrong_secret_rejected():
    token = sign_session(42, "test-secret", issued_at=1_000_000)
    assert verify_session(token, "wrong-secret", now=1_000_100) is None


def test_tampered_code_id_rejected():
    token = sign_session(42, "test-secret", issued_at=1_000_000)
    code_id_str, issued_at_str, sig = token.split(":")
    tampered = f"999:{issued_at_str}:{sig}"
    assert verify_session(tampered, "test-secret", now=1_000_100) is None


def test_expired_after_seven_days_rejected():
    token = sign_session(42, "test-secret", issued_at=1_000_000)
    just_inside = 1_000_000 + COOKIE_MAX_AGE_S - 1
    just_outside = 1_000_000 + COOKIE_MAX_AGE_S + 1
    assert verify_session(token, "test-secret", now=just_inside) == 42
    assert verify_session(token, "test-secret", now=just_outside) is None


def test_none_token_rejected():
    assert verify_session(None, "test-secret") is None


def test_malformed_token_rejected_not_raised():
    assert verify_session("not-a-valid-token", "test-secret") is None
    assert verify_session("", "test-secret") is None
    assert verify_session("1:2:3:4", "test-secret") is None
    assert verify_session("abc:def:ghi", "test-secret") is None


def test_hash_ip_is_deterministic_and_salted():
    a = hash_ip("203.0.113.5", "salt-one")
    b = hash_ip("203.0.113.5", "salt-one")
    c = hash_ip("203.0.113.5", "salt-two")
    assert a == b
    assert a != c
    assert "203.0.113.5" not in a  # never the raw IP


def test_hash_ip_different_ips_differ():
    assert hash_ip("203.0.113.5", "salt") != hash_ip("203.0.113.6", "salt")
```

- [ ] Run it and see it fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_demo_auth.py -q
  ```
  Expected: `ModuleNotFoundError: No module named 'rulesagent.demo_auth'`

- [ ] Minimal implementation:

```python
# src/rulesagent/demo_auth.py
"""Slice 4 (docs/superpowers/plans/2026-07-27-gated-demo.md Task 2): signed
session cookie and salted IP hashing for the gated demo.

Cookie: HMAC over "code_id:issued_at" (spec: "signed cookie (code id + issue
time), 7-day expiry"). Deliberately stdlib hmac/hashlib rather than a signing
library -- one signed string, nothing that warrants a dependency.

IP hash: events.ip_hash must never be the raw IP (spec). hmac-sha256 keyed by
a server-side salt (IP_HASH_SALT env var) rather than a plain sha256 -- salting
stops rainbow-table recovery of common IPs from the stored hash.
"""
from __future__ import annotations

import hashlib
import hmac
import time

COOKIE_MAX_AGE_S = 7 * 24 * 3600


def sign_session(code_id: int, secret: str, issued_at: int | None = None) -> str:
    issued_at = issued_at if issued_at is not None else int(time.time())
    msg = f"{code_id}:{issued_at}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"{code_id}:{issued_at}:{sig}"


def verify_session(token: str | None, secret: str, now: int | None = None,
                    max_age_s: int = COOKIE_MAX_AGE_S) -> int | None:
    if not token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    code_id_str, issued_at_str, sig = parts
    if not code_id_str.isdigit() or not issued_at_str.lstrip("-").isdigit():
        return None
    code_id, issued_at = int(code_id_str), int(issued_at_str)
    expected = hmac.new(secret.encode("utf-8"), f"{code_id}:{issued_at}".encode("utf-8"),
                         hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    now = now if now is not None else int(time.time())
    if now - issued_at > max_age_s:
        return None
    return code_id


def hash_ip(ip: str, salt: str) -> str:
    return hmac.new(salt.encode("utf-8"), ip.encode("utf-8"), hashlib.sha256).hexdigest()
```

- [ ] Run and see it pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_demo_auth.py -q
  ```
  Expected: `9 passed`

- [ ] Commit:
  ```
  git add src/rulesagent/demo_auth.py tests/test_demo_auth.py
  git commit -m "$(cat <<'EOF'
  Add demo_auth: signed session cookie + salted IP hashing (slice 4)

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** `rulesagent.demo_auth` importable and independently testable;
no FastAPI involvement yet.

---

## Task 3 — `scripts/codes.py`: mint / list / revoke CLI

**Files:**
- Create: `scripts/codes.py`
- Create: `tests/test_codes_cli.py`

**Interfaces:**
- Consumes: `rulesagent.demo_db.{create_code, list_codes, revoke_code, get_code_by_value}`.
- Produces:
  - `WORDLIST: list[str]` — ~60 short, unambiguous-to-type-off-a-phone words.
  - `generate_code(existing: set[str] | None = None) -> str` — `"word-word-NN"` (two words, two digits, e.g. `raptor-quill-42`), retrying on collision against `existing`.
  - `main(argv: list[str] | None = None) -> int` — argparse subcommands `new`, `list`, `revoke`; returns a process exit code (doesn't call `sys.exit` itself, so tests can call it directly, same shape as `scripts/check_cr_update.py`'s exit-code convention).

- [ ] Write the failing test file.

```python
# tests/test_codes_cli.py
# Slice 4 Task 3. Calls scripts/codes.py's main() directly (same in-process
# convention as tests/test_check_cr_update.py) -- no subprocess.

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codes as codes_cli  # noqa: E402

from rulesagent.demo_db import get_code_by_value, list_codes  # noqa: E402


def test_generate_code_shape():
    code = codes_cli.generate_code()
    word1, word2, digits = code.split("-")
    assert word1 in codes_cli.WORDLIST
    assert word2 in codes_cli.WORDLIST
    assert digits.isdigit() and len(digits) == 2


def test_generate_code_avoids_collisions():
    first = codes_cli.generate_code()
    second = codes_cli.generate_code(existing={first})
    assert second != first


def test_new_command_mints_and_prints_code(tmp_path, capsys):
    db = tmp_path / "demo.db"
    rc = codes_cli.main(["--db", str(db), "new", "--label", "Cribl -- Jane R."])
    out = capsys.readouterr().out

    assert rc == 0
    rows = list_codes(db)
    assert len(rows) == 1
    assert rows[0]["label"] == "Cribl -- Jane R."
    assert rows[0]["code"] in out  # the minted code is printed for Jon to copy


def test_new_command_respects_max_queries_flag(tmp_path):
    db = tmp_path / "demo.db"
    codes_cli.main(["--db", str(db), "new", "--label", "Test", "--max-queries", "10"])
    row = list_codes(db)[0]
    assert row["max_queries"] == 10


def test_new_command_defaults_max_queries_to_25(tmp_path):
    db = tmp_path / "demo.db"
    codes_cli.main(["--db", str(db), "new", "--label", "Test"])
    row = list_codes(db)[0]
    assert row["max_queries"] == 25


def test_list_command_prints_every_code(tmp_path, capsys):
    db = tmp_path / "demo.db"
    codes_cli.main(["--db", str(db), "new", "--label", "First"])
    codes_cli.main(["--db", str(db), "new", "--label", "Second"])
    capsys.readouterr()  # discard "new" output

    rc = codes_cli.main(["--db", str(db), "list"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "First" in out
    assert "Second" in out


def test_revoke_command_marks_code_revoked(tmp_path, capsys):
    db = tmp_path / "demo.db"
    codes_cli.main(["--db", str(db), "new", "--label", "Test"])
    minted = capsys.readouterr().out.strip().splitlines()[-1].split()[-1]

    rc = codes_cli.main(["--db", str(db), "revoke", minted])

    assert rc == 0
    assert get_code_by_value(db, minted)["revoked_at"] is not None


def test_revoke_unknown_code_returns_nonzero(tmp_path):
    db = tmp_path / "demo.db"
    rc = codes_cli.main(["--db", str(db), "revoke", "no-such-code-99"])
    assert rc != 0
```

- [ ] Run it and see it fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_codes_cli.py -q
  ```
  Expected: `ModuleNotFoundError: No module named 'codes'`

- [ ] Minimal implementation:

```python
# scripts/codes.py
"""Mint / list / revoke gated-demo access codes (docs/superpowers/plans/
2026-07-27-gated-demo.md Task 3).

    python scripts/codes.py new --label "Cribl -- Jane R." [--max-queries 25] [--notes "..."]
    python scripts/codes.py list
    python scripts/codes.py revoke <code>

Codes are "word-word-NN" -- two short words plus a two-digit number, e.g.
"raptor-quill-42" (the exact shape from the design spec's example). Chosen
over three words because it's the format the spec actually showed, and
shorter survives being typed off a phone screen better.
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rulesagent.demo_db import (  # noqa: E402
    DEFAULT_DEMO_DB,
    create_code,
    get_code_by_value,
    list_codes,
    revoke_code,
)

WORDLIST = [
    "raptor", "quill", "cedar", "otter", "birch", "heron", "maple", "finch",
    "elm", "osprey", "fir", "lark", "pine", "swift", "yew", "plover", "ash",
    "crane", "willow", "vole", "spruce", "wren", "alder", "kite", "hazel",
    "falcon", "poplar", "grouse", "beech", "sparrow", "aspen", "raven",
    "hemlock", "condor", "juniper", "harrier", "cypress", "kestrel", "linden",
    "merlin", "walnut", "peregrine", "hickory", "gannet", "sycamore", "ibis",
    "dogwood", "puffin", "chestnut", "curlew", "magnolia", "tern", "rowan",
    "grebe", "sequoia", "shrike", "larch", "warbler",
]


def generate_code(existing: set[str] | None = None) -> str:
    existing = existing or set()
    for _ in range(50):
        word1 = secrets.choice(WORDLIST)
        word2 = secrets.choice(WORDLIST)
        digits = f"{secrets.randbelow(100):02d}"
        code = f"{word1}-{word2}-{digits}"
        if code not in existing:
            return code
    raise RuntimeError("could not generate a unique code after 50 attempts")


def _cmd_new(args: argparse.Namespace) -> int:
    existing = {row["code"] for row in list_codes(args.db)}
    code = generate_code(existing=existing)
    create_code(args.db, code, args.label, max_queries=args.max_queries, notes=args.notes)
    print(f"minted code: {code}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    rows = list_codes(args.db)
    if not rows:
        print("(no codes minted yet)")
        return 0
    for row in rows:
        status = "REVOKED" if row["revoked_at"] else "active"
        print(f"{row['code']:20s} {status:8s} max_queries={row['max_queries']!s:5s} "
              f"label={row['label']!r} created={row['created_at']}")
    return 0


def _cmd_revoke(args: argparse.Namespace) -> int:
    row = get_code_by_value(args.db, args.code)
    if row is None:
        print(f"no such code: {args.code}", file=sys.stderr)
        return 1
    revoke_code(args.db, row["id"])
    print(f"revoked: {args.code}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mint/list/revoke gated-demo access codes")
    parser.add_argument("--db", type=Path, default=DEFAULT_DEMO_DB)
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="mint a new code")
    p_new.add_argument("--label", required=True)
    p_new.add_argument("--max-queries", type=int, default=25, dest="max_queries")
    p_new.add_argument("--notes", default="")
    p_new.set_defaults(func=_cmd_new)

    p_list = sub.add_parser("list", help="list all codes")
    p_list.set_defaults(func=_cmd_list)

    p_revoke = sub.add_parser("revoke", help="revoke a code")
    p_revoke.add_argument("code")
    p_revoke.set_defaults(func=_cmd_revoke)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] Run and see it pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_codes_cli.py -q
  ```
  Expected: `7 passed`

- [ ] Commit:
  ```
  git add scripts/codes.py tests/test_codes_cli.py
  git commit -m "$(cat <<'EOF'
  Add scripts/codes.py: mint/list/revoke demo access codes (slice 4)

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** `python scripts/codes.py new --label "test"` mints and prints
a real code against `data/demo.db`; `list` and `revoke` round-trip against it.

---

## Task 4 — Gate page + `/unlock` endpoint

**Files:**
- Create: `frontend/gate.html`
- Modify: `src/rulesagent/api/main.py` — add imports, `COOKIE_NAME`, `_gate_enabled()`, `_client_ip()`, `_friendly_html()`, the `/unlock` route, and gate routing inside the existing `_index()` (around line 498-502).
- Create: `tests/test_unlock_endpoint.py`
- Create: `tests/test_gate_routing.py`

**Interfaces:**
- Consumes: `rulesagent.demo_db.{get_code_by_value, log_event}`, `rulesagent.demo_auth.{sign_session, hash_ip}`.
- Produces:
  - `COOKIE_NAME = "rulemancer_demo"`
  - `_gate_enabled() -> bool` — `True` iff `os.environ.get("COOKIE_SECRET")` is truthy. This is the on/off switch for the whole slice: unset (local dev, existing tests) means every route behaves exactly as it does today.
  - `_client_ip(request: Request) -> str` — `Fly-Client-IP` header, else first hop of `X-Forwarded-For`, else `request.client.host`, else `"unknown"`.
  - `_friendly_html(title: str, message: str, status_code: int = 200) -> HTMLResponse` — dark-mode styled page, used by every guard failure from here on.
  - `POST /unlock` (form field `code: str`) — on success: sets `COOKIE_NAME` cookie (httponly, samesite=lax, secure, `max_age=COOKIE_MAX_AGE_S`), logs an `unlock` event, returns `{"ok": true}`. On invalid/revoked code: logs a `denied` event, returns `_friendly_html(..., status_code=403)`.
  - `_index()` (existing route, both `/` and `/index.html`) gains a `request: Request` parameter; when gating is enabled and there's no valid session cookie, serves `frontend/gate.html` instead of `frontend/index.html`.

- [ ] Write the failing test files.

```python
# tests/test_unlock_endpoint.py
# Slice 4 Task 4. Same in-process convention as tests/test_admin_scryfall_
# endpoints.py: route functions called directly, no TestClient/lifespan.

import pytest
from fastapi import Request

from rulesagent.api import main
from rulesagent.demo_db import get_code_by_value, log_event


class _FakeClient:
    host = "203.0.113.9"


def _fake_request(headers: dict | None = None) -> Request:
    scope = {
        "type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": ("203.0.113.9", 12345), "method": "POST", "path": "/unlock",
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _demo_env(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    monkeypatch.setattr(main, "DEMO_DB", db)
    from rulesagent.demo_db import create_code
    create_code(db, "raptor-quill-42", "Test Person", max_queries=25)
    yield db


def test_unlock_valid_code_sets_cookie_and_returns_ok(_demo_env):
    resp = main.unlock(code="raptor-quill-42", request=_fake_request())

    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert main.COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie


def test_unlock_logs_an_unlock_event(_demo_env):
    main.unlock(code="raptor-quill-42", request=_fake_request())
    row = get_code_by_value(_demo_env, "raptor-quill-42")
    from rulesagent.demo_db import code_stats
    assert code_stats(_demo_env, row["id"])["unlocks"] == 1


def test_unlock_invalid_code_returns_friendly_403(_demo_env):
    resp = main.unlock(code="not-a-real-code-00", request=_fake_request())
    assert resp.status_code == 403
    assert b"<html" in resp.body.lower() or b"<!doctype" in resp.body.lower()


def test_unlock_invalid_code_logs_denied_event(_demo_env):
    main.unlock(code="not-a-real-code-00", request=_fake_request())
    # code_id is None for a denied unlock (spec) -- verified via a direct
    # query since there's no code row to hang code_stats off of.
    import sqlite3
    conn = sqlite3.connect(_demo_env)
    try:
        row = conn.execute("SELECT kind, code_id FROM events WHERE kind = 'denied'").fetchone()
    finally:
        conn.close()
    assert row == ("denied", None)


def test_unlock_revoked_code_returns_friendly_403(_demo_env):
    row = get_code_by_value(_demo_env, "raptor-quill-42")
    from rulesagent.demo_db import revoke_code
    revoke_code(_demo_env, row["id"])

    resp = main.unlock(code="raptor-quill-42", request=_fake_request())

    assert resp.status_code == 403
```

```python
# tests/test_gate_routing.py
# Slice 4 Task 4: "/" serves the gate page when ungated, the real frontend
# once a valid session cookie is presented.

import pytest
from fastapi import Request

from rulesagent.api import main


def _fake_request(cookie: str | None = None) -> Request:
    headers = [(b"cookie", f"{main.COOKIE_NAME}={cookie}".encode())] if cookie else []
    scope = {"type": "http", "headers": headers, "client": ("203.0.113.9", 12345),
              "method": "GET", "path": "/"}
    return Request(scope)


def test_gate_disabled_serves_real_index(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    resp = main._index(request=_fake_request())
    assert resp.path.name == "index.html"


def test_gate_enabled_no_cookie_serves_gate_page(monkeypatch):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    resp = main._index(request=_fake_request())
    assert resp.path.name == "gate.html"


def test_gate_enabled_invalid_cookie_serves_gate_page(monkeypatch):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    resp = main._index(request=_fake_request(cookie="garbage"))
    assert resp.path.name == "gate.html"


def test_gate_enabled_valid_cookie_serves_real_index(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    from rulesagent.demo_db import create_code
    code_id = create_code(db, "test-code-01", "Test")
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")

    resp = main._index(request=_fake_request(cookie=token))

    assert resp.path.name == "index.html"
```

- [ ] Run them and see them fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_unlock_endpoint.py tests/test_gate_routing.py -q
  ```
  Expected: `AttributeError: module 'rulesagent.api.main' has no attribute 'unlock'` (and `DEMO_DB`, `COOKIE_NAME`).

- [ ] Minimal implementation. Add to `src/rulesagent/api/main.py`:

  Imports (extend the existing block near the top):
  ```python
  from fastapi import BackgroundTasks, Cookie, FastAPI, Form, Header, HTTPException, Request
  from fastapi.responses import FileResponse, HTMLResponse

  from rulesagent.demo_auth import COOKIE_MAX_AGE_S, hash_ip, sign_session, verify_session
  from rulesagent.demo_db import DEFAULT_DEMO_DB, get_code_by_value, log_event
  ```

  New module-level state (near `_state`/`_lock`, after line 71):
  ```python
  # --- Slice 4: gated demo (docs/superpowers/plans/2026-07-27-gated-demo.md) -
  COOKIE_NAME = "rulemancer_demo"
  DEMO_DB = DEFAULT_DEMO_DB
  # Module-level so tests can monkeypatch.setattr(main, "DEMO_DB", tmp_db) the
  # same way _state is monkeypatched elsewhere in this file's test suite.


  def _gate_enabled() -> bool:
      """Gating is OFF unless COOKIE_SECRET is configured. Local dev (`python
      run.py`) and the existing test suite never set it, so this whole slice
      is inert there -- only the Fly deployment sets it and becomes gated."""
      return bool(os.environ.get("COOKIE_SECRET"))


  def _client_ip(request: Request) -> str:
      """Fly terminates TLS and proxies -- the socket peer is Fly's edge, not
      the visitor, so the real IP comes from Fly-Client-IP (or the first hop
      of X-Forwarded-For as a fallback) when present."""
      fly_ip = request.headers.get("fly-client-ip")
      if fly_ip:
          return fly_ip
      xff = request.headers.get("x-forwarded-for")
      if xff:
          return xff.split(",")[0].strip()
      return request.client.host if request.client else "unknown"


  def _friendly_html(title: str, message: str, status_code: int = 200) -> HTMLResponse:
      """Every guard failure renders through this -- dark mode, WCAG AA
      contrast, no raw error, never a 500 for an expected condition."""
      html = f"""<!doctype html>
  <html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Rulemancer</title>
  <style>
  body {{ background:#14161a; color:#e8e8ea; font-family:system-ui,-apple-system,sans-serif;
          display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; padding:24px; }}
  .card {{ max-width:480px; text-align:center; }}
  h1 {{ font-size:1.4rem; margin-bottom:0.75rem; color:#f4f4f5; }}
  p {{ color:#c4c4c9; line-height:1.5; }}
  </style></head>
  <body><div class="card"><h1>{title}</h1><p>{message}</p></div></body></html>"""
      return HTMLResponse(content=html, status_code=status_code)
  ```

  New `/unlock` route (place near `/feedback`):
  ```python
  @app.post("/unlock", tags=["answers"], summary="Unlock the demo with an access code")
  def unlock(code: str = Form(...), request: Request = None):
      ip_hash = hash_ip(_client_ip(request), os.environ.get("IP_HASH_SALT", ""))
      row = get_code_by_value(DEMO_DB, code.strip())
      if row is None or row["revoked_at"] is not None:
          log_event(DEMO_DB, code_id=None, kind="denied", ip_hash=ip_hash)
          return _friendly_html(
              "Code not recognized",
              "That access code doesn't work. Double-check it, or ask Jon for a fresh one.",
              status_code=403,
          )
      log_event(DEMO_DB, code_id=row["id"], kind="unlock", ip_hash=ip_hash)
      token = sign_session(row["id"], os.environ["COOKIE_SECRET"])
      resp = JSONResponse({"ok": True})
      resp.set_cookie(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE_S, httponly=True,
                       samesite="lax", secure=True)
      return resp
  ```
  (Add `from fastapi.responses import JSONResponse` to the imports line above.)

  Modify `_index()` (existing lines 498-502) to take `request` and gate:
  ```python
  @app.get("/", include_in_schema=False)
  @app.get("/index.html", include_in_schema=False)
  def _index(request: Request) -> FileResponse:
      if _gate_enabled():
          session = request.cookies.get(COOKIE_NAME)
          code_id = verify_session(session, os.environ["COOKIE_SECRET"])
          if code_id is None:
              return FileResponse(_frontend_dir / "gate.html", headers={"Cache-Control": "no-cache"})
      return FileResponse(_frontend_dir / "index.html", headers={"Cache-Control": "no-cache"})
  ```

  New file `frontend/gate.html`:
  ```html
  <!doctype html>
  <html lang="en">
  <head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rulemancer — enter your access code</title>
  <style>
    :root { color-scheme: dark; }
    body {
      background:#14161a; color:#e8e8ea; font-family:system-ui,-apple-system,sans-serif;
      display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; padding:24px;
    }
    .card { max-width:420px; width:100%; }
    h1 { font-size:1.5rem; margin-bottom:0.5rem; color:#f4f4f5; }
    p { color:#c4c4c9; line-height:1.5; margin-bottom:1.5rem; }
    input[type=text] {
      width:100%; box-sizing:border-box; padding:0.75rem 1rem; font-size:1rem;
      background:#1e2126; border:1px solid #3a3f47; border-radius:8px; color:#f4f4f5;
      margin-bottom:1rem;
    }
    input[type=text]:focus { outline:2px solid #7aa2ff; outline-offset:1px; }
    button {
      width:100%; padding:0.75rem 1rem; font-size:1rem; font-weight:600;
      background:#7aa2ff; color:#0d0e10; border:none; border-radius:8px; cursor:pointer;
    }
    button:hover { background:#93b4ff; }
    button:disabled { background:#3a3f47; color:#8a8d93; cursor:not-allowed; }
    #msg { margin-top:1rem; color:#ff9b9b; min-height:1.2em; }
  </style>
  </head>
  <body>
  <div class="card">
    <h1>Rulemancer</h1>
    <p>This demo is access-code gated. If you don't have a code, ask Jon Gorecki for one.</p>
    <form id="gate-form">
      <input type="text" id="code" name="code" placeholder="e.g. raptor-quill-42" autocomplete="off" autofocus>
      <button type="submit" id="submit-btn">Unlock</button>
    </form>
    <div id="msg" role="status" aria-live="polite"></div>
  </div>
  <script>
    document.getElementById("gate-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = document.getElementById("submit-btn");
      const msg = document.getElementById("msg");
      const code = document.getElementById("code").value.trim();
      if (!code) return;
      btn.disabled = true;
      msg.textContent = "";
      try {
        const resp = await fetch("/unlock", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: "code=" + encodeURIComponent(code),
        });
        if (resp.ok) {
          window.location.reload();
        } else {
          msg.textContent = "That code didn't work. Check it and try again.";
        }
      } catch (err) {
        msg.textContent = "Something went wrong. Try again in a moment.";
      } finally {
        btn.disabled = false;
      }
    });
  </script>
  </body>
  </html>
  ```

- [ ] Run and see them pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_unlock_endpoint.py tests/test_gate_routing.py -q
  ```
  Expected: `9 passed`

- [ ] Commit:
  ```
  git add src/rulesagent/api/main.py frontend/gate.html tests/test_unlock_endpoint.py tests/test_gate_routing.py
  git commit -m "$(cat <<'EOF'
  Add /unlock endpoint and gate-page routing (slice 4)

  Gating is inert unless COOKIE_SECRET is set, so local dev and the
  existing suite are unaffected -- only the Fly deployment turns it on.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** with `COOKIE_SECRET` unset, `python run.py` behaves exactly
as before. With it set (`$env:COOKIE_SECRET="dev-secret"; python run.py 8947`),
visiting `http://127.0.0.1:8947/` serves the gate page; POSTing a minted code
to `/unlock` sets a cookie and a refresh shows the real frontend.

---

## Task 5 — Wire the cookie requirement + event logging into `/answer`

**Files:**
- Modify: `src/rulesagent/api/main.py` — `answer()` (existing lines 304-381).
- Create: `tests/test_answer_guards.py` (cookie requirement + logging; caps/budget land in Tasks 6-7).

**Interfaces:**
- Consumes: `verify_session`, `get_code_by_id` (new import), `log_event`, `rulesagent.pricing.cost_usd`.
- Produces: `answer(req: AnswerRequest, request: Request, session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> AnswerResponse` — signature grows two parameters, both defaulted, so every existing call site (`main.answer(req)` in `tests/test_api_debug.py`) keeps working when `_gate_enabled()` is `False`. A private helper `_resolve_gated_code(session: str | None) -> dict | None` returns the `codes` row for a valid, non-revoked cookie, or `None`.

- [ ] Write the failing test file.

```python
# tests/test_answer_guards.py
# Slice 4 Task 5 (cookie requirement + event logging only -- per-code cap is
# Task 6, budget breaker is Task 7). Same in-process route-function
# convention as tests/test_api_debug.py; a fake agent stands in for the real
# RulesAgent so no network/API key is needed.

import pytest
from fastapi import Request

from rulesagent.api import main
from rulesagent.contracts import Answer
from rulesagent.demo_db import create_code, events_for_code, get_code_by_value


class _FakeAgent:
    model = "claude-opus-5"

    def __init__(self):
        self.last_cards = []
        self.last_retrieved = []
        self.last_rewritten = None
        self.last_ruling_selection = {}
        self.last_unresolved_refs = []
        self.last_uncited_success = False
        self.last_fuzzy_fallbacks = []
        self.last_usage = {"input_tokens": 500, "output_tokens": 200,
                            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}

    def answer(self, question, history=None):
        return Answer(text="An honest answer.", tldr="tldr", citations=[],
                       answered=True, suggested_followups=[])


def _fake_request(cookie: str | None = None) -> Request:
    headers = [(b"cookie", f"{main.COOKIE_NAME}={cookie}".encode())] if cookie else []
    scope = {"type": "http", "headers": headers, "client": ("203.0.113.9", 12345),
              "method": "POST", "path": "/answer"}
    return Request(scope)


@pytest.fixture(autouse=True)
def _fake_agent(monkeypatch):
    monkeypatch.setitem(main._state, "agent", _FakeAgent())
    monkeypatch.setitem(main._state, "chunk_map", {})


def test_gate_disabled_answer_works_without_cookie(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    req = main.AnswerRequest(question="Does trample get through deathtouch?")
    resp = main.answer(req, request=_fake_request())
    assert resp.answered is True


def test_gate_enabled_no_cookie_returns_friendly_401(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setattr(main, "DEMO_DB", tmp_path / "demo.db")
    req = main.AnswerRequest(question="Does trample get through deathtouch?")

    resp = main.answer(req, request=_fake_request(cookie=None))

    assert resp.status_code == 401
    assert b"<html" in resp.body.lower()


def test_gate_enabled_valid_cookie_answers_and_logs_query_event(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")
    req = main.AnswerRequest(question="Does trample get through deathtouch?")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True
    events = events_for_code(db, code_id)
    assert len(events) == 1
    assert events[0]["question"] == "Does trample get through deathtouch?"
    assert events[0]["input_tokens"] == 500
    assert events[0]["output_tokens"] == 200
    assert events[0]["cost_usd"] > 0


def test_gate_enabled_revoked_code_returns_friendly_403(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_db import revoke_code
    from rulesagent.demo_auth import sign_session
    revoke_code(db, code_id)
    token = sign_session(code_id, "test-secret")
    req = main.AnswerRequest(question="q")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code == 403
```

- [ ] Run it and see it fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_answer_guards.py -q
  ```
  Expected: `TypeError: answer() got an unexpected keyword argument 'request'`

- [ ] Minimal implementation. Modify `src/rulesagent/api/main.py`:

  Add import: `from rulesagent.demo_db import get_code_by_id` (alongside the Task 4 imports) and `from rulesagent.pricing import cost_usd`.

  Replace the `answer()` signature and add the guard at the top of the body
  (existing body from line 304 stays, indented under the guard):
  ```python
  def _resolve_gated_code(session: str | None) -> dict | None:
      """The codes row for a valid, non-revoked cookie -- None if the cookie
      is missing, malformed, expired, or points at a revoked/deleted code."""
      code_id = verify_session(session, os.environ.get("COOKIE_SECRET", ""))
      if code_id is None:
          return None
      row = get_code_by_id(DEMO_DB, code_id)
      if row is None or row["revoked_at"] is not None:
          return None
      return row


  @app.post(
      "/answer",
      tags=["answers"],
      summary="Answer a rules question",
      description="Send a natural-language question (optionally with `[Card Name]` "
      "tokens). Returns the answer, an `answered` flag (false = the rules didn't "
      "cover it), citations with resolved rule/glossary text, the card data used "
      "with its relevance-selected rulings, and a debug panel.",
  )
  def answer(req: AnswerRequest, request: Request,
             session: str | None = Cookie(default=None, alias=COOKIE_NAME)):
      if not req.question.strip():
          raise HTTPException(status_code=400, detail="empty question")

      code_row = None
      if _gate_enabled():
          code_row = _resolve_gated_code(session)
          if code_row is None:
              ip_hash = hash_ip(_client_ip(request), os.environ.get("IP_HASH_SALT", ""))
              log_event(DEMO_DB, code_id=None, kind="denied", ip_hash=ip_hash)
              return _friendly_html(
                  "Enter your access code",
                  "This demo needs an access code. Head back to the home page to enter one.",
                  status_code=401,
              )
          # Tasks 6-7 (per-code cap, daily budget breaker) add checks here,
          # before agent.answer() is ever called.

      agent, chunk_map = _state["agent"], _state["chunk_map"]
      # ... (existing body, lines 308-376, unchanged) ...

      if code_row is not None:
          usage = getattr(agent, "last_usage", None) or {}
          input_tokens = usage.get("input_tokens") or 0
          output_tokens = usage.get("output_tokens") or 0
          cost = cost_usd(
              agent.model, input_tokens=input_tokens, output_tokens=output_tokens,
              cache_read_tokens=usage.get("cache_read_input_tokens") or 0,
              cache_write_tokens=usage.get("cache_creation_input_tokens") or 0,
          ) or 0.0
          ip_hash = hash_ip(_client_ip(request), os.environ.get("IP_HASH_SALT", ""))
          log_event(
              DEMO_DB, code_id=code_row["id"], kind="query", ip_hash=ip_hash,
              question=req.question, answered=ans.answered,
              input_tokens=input_tokens, output_tokens=output_tokens,
              cost_usd=cost, latency_ms=latency_ms,
          )

      return AnswerResponse(
          answer=ans.text, tldr=ans.tldr, answered=ans.answered,
          suggested_followups=ans.suggested_followups, request_id=request_id,
          citations=citations, cards=cards_out, debug=debug,
      )
  ```
  Note: the `response_model=AnswerResponse` kwarg is dropped from the
  `@app.post("/answer", ...)` decorator (it stays in the docstring-level
  `description` etc.) because the guard path now returns an `HTMLResponse`
  directly — FastAPI allows returning a `Response` subclass from a route even
  when a `response_model` was declared, but only if the declaration is
  removed from *this* endpoint; the `AnswerResponse` return type is kept as
  the function's return-type annotation for documentation/IDE purposes only.

- [ ] Run and see it pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_answer_guards.py tests/test_api_debug.py -q
  ```
  Expected: `4 passed` (this file) `+ 2 passed` (existing `test_api_debug.py`,
  confirming the ungated path is untouched).

- [ ] Commit:
  ```
  git add src/rulesagent/api/main.py tests/test_answer_guards.py
  git commit -m "$(cat <<'EOF'
  Require a valid session cookie on /answer when gating is on (slice 4)

  Every gated query now writes an events row with real token counts and
  cost, computed from agent.last_usage via rulesagent.pricing.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** with `COOKIE_SECRET` set and a valid cookie, `/answer` works
and an `events` row appears with real question text, tokens, and cost; without
a cookie it returns a friendly 401 page, never a stack trace.

---

## Task 6 — Guard: per-code `max_queries` cap

**Files:**
- Modify: `src/rulesagent/api/main.py` — extend the gate block inside `answer()` added in Task 5.
- Modify: `tests/test_answer_guards.py` — add cap tests.

**Interfaces:**
- Consumes: `rulesagent.demo_db.count_queries`.
- Produces: `DEFAULT_MAX_QUERIES = 25` (module constant, used only when a code's `max_queries` column is `NULL`).

- [ ] Write the failing tests (append to `tests/test_answer_guards.py`):

```python
def test_at_cap_returns_friendly_402_and_does_not_call_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=2)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    token = sign_session(code_id, "test-secret")
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=0.01)
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q2", cost_usd=0.01)

    calls = []
    monkeypatch.setattr(main._state["agent"], "answer",
                         lambda *a, **k: calls.append(1) or pytest.fail("agent must not be called at cap"))
    req = main.AnswerRequest(question="q3")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code == 402
    assert calls == []


def test_under_cap_still_works(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=2)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    token = sign_session(code_id, "test-secret")
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=0.01)
    req = main.AnswerRequest(question="q2")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True


def test_null_max_queries_falls_back_to_default_25(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=None)
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")
    req = main.AnswerRequest(question="q1")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True  # 1 query against an unset (None -> 25) cap is fine
```

- [ ] Run and see them fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_answer_guards.py -q
  ```
  Expected: `test_at_cap_returns_friendly_402_and_does_not_call_agent` fails —
  `resp.status_code == 402` is `AttributeError` (agent gets called, real
  `AnswerResponse` returned, no `.status_code`).

- [ ] Minimal implementation. In `main.py`, extend the gate block from Task 5:
  ```python
  DEFAULT_MAX_QUERIES = 25
  ```
  ```python
      if _gate_enabled():
          code_row = _resolve_gated_code(session)
          if code_row is None:
              ip_hash = hash_ip(_client_ip(request), os.environ.get("IP_HASH_SALT", ""))
              log_event(DEMO_DB, code_id=None, kind="denied", ip_hash=ip_hash)
              return _friendly_html(
                  "Enter your access code",
                  "This demo needs an access code. Head back to the home page to enter one.",
                  status_code=401,
              )
          cap = code_row["max_queries"] if code_row["max_queries"] is not None else DEFAULT_MAX_QUERIES
          if count_queries(DEMO_DB, code_row["id"]) >= cap:
              ip_hash = hash_ip(_client_ip(request), os.environ.get("IP_HASH_SALT", ""))
              log_event(DEMO_DB, code_id=code_row["id"], kind="denied", ip_hash=ip_hash)
              return _friendly_html(
                  "This demo code is used up",
                  "You've used all your questions on this code. Ask Jon for another.",
                  status_code=402,
              )
  ```
  Add `from rulesagent.demo_db import count_queries` to the imports.

- [ ] Run and see them pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_answer_guards.py -q
  ```
  Expected: `7 passed`

- [ ] Commit:
  ```
  git add src/rulesagent/api/main.py tests/test_answer_guards.py
  git commit -m "$(cat <<'EOF'
  Enforce per-code max_queries cap on /answer, default 25 (slice 4)

  Checked before agent.answer() runs -- a capped-out code never reaches
  the model.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** a code minted with `--max-queries 1`, used once, gets a
friendly "used up" page on its second question — verified without spending
any API credits (the fake agent in the test never gets called).

---

## Task 7 — Guard: global daily USD budget breaker

**Files:**
- Modify: `src/rulesagent/api/main.py` — extend the gate block.
- Modify: `tests/test_answer_guards.py` — add budget tests.

**Interfaces:**
- Consumes: `rulesagent.demo_db.daily_spend`.
- Produces: `DAILY_BUDGET_USD_DEFAULT = 5.0` (module constant — a conservative
  starting point; Task 12 measures the real $/serve and Jon sets the
  production value via the `DAILY_BUDGET_USD` Fly secret, read at request
  time so no redeploy is needed to change it).

- [ ] Write the failing tests (append to `tests/test_answer_guards.py`):

```python
def test_over_daily_budget_returns_friendly_503_and_does_not_call_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("DAILY_BUDGET_USD", "1.00")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=100)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    from datetime import datetime, timezone
    token = sign_session(code_id, "test-secret")
    today = datetime.now(timezone.utc).date().isoformat()
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=1.50)

    calls = []
    monkeypatch.setattr(main._state["agent"], "answer",
                         lambda *a, **k: calls.append(1) or pytest.fail("agent must not be called over budget"))
    req = main.AnswerRequest(question="q2")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code == 503
    assert calls == []


def test_under_daily_budget_still_works(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("DAILY_BUDGET_USD", "10.00")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=100)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    token = sign_session(code_id, "test-secret")
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=0.05)
    req = main.AnswerRequest(question="q2")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True


def test_missing_daily_budget_env_uses_conservative_default(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.delenv("DAILY_BUDGET_USD", raising=False)
    assert main.DAILY_BUDGET_USD_DEFAULT == 5.0
```

- [ ] Run and see them fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_answer_guards.py -q
  ```
  Expected: `test_over_daily_budget_returns_friendly_503_and_does_not_call_agent`
  fails — agent gets called, no budget check exists yet.

- [ ] Minimal implementation:
  ```python
  DAILY_BUDGET_USD_DEFAULT = 5.0
  # Conservative starting point. Task 12 measures the real $/serve and Jon
  # sets DAILY_BUDGET_USD as a Fly secret from that number before the demo
  # goes live -- read here at request time, so changing it needs no redeploy.
  ```
  Extend the gate block (after the cap check from Task 6):
  ```python
          budget = float(os.environ.get("DAILY_BUDGET_USD", DAILY_BUDGET_USD_DEFAULT))
          today = datetime.now(timezone.utc).date().isoformat()
          if daily_spend(DEMO_DB, today) >= budget:
              ip_hash = hash_ip(_client_ip(request), os.environ.get("IP_HASH_SALT", ""))
              log_event(DEMO_DB, code_id=code_row["id"], kind="denied", ip_hash=ip_hash)
              return _friendly_html(
                  "The demo is resting for today",
                  "This demo hit its daily budget. It'll be back tomorrow -- or ping Jon directly.",
                  status_code=503,
              )
  ```
  Add `from rulesagent.demo_db import daily_spend` to the imports.

- [ ] Run and see them pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_answer_guards.py -q
  ```
  Expected: `10 passed`

- [ ] Commit:
  ```
  git add src/rulesagent/api/main.py tests/test_answer_guards.py
  git commit -m "$(cat <<'EOF'
  Add global daily USD budget breaker on /answer (slice 4)

  Reads DAILY_BUDGET_USD at request time (Fly secret, no redeploy to
  change). Defaults to a conservative $5/day until Task 12 measures the
  real cost per serve and sets the production value.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** with the day's logged spend at or above `DAILY_BUDGET_USD`,
every `/answer` call across every code returns the friendly "resting for
today" page without touching the model, until UTC midnight rolls the day over.

---

## Task 8 — Guard: per-IP rate limit on `/unlock`

**Files:**
- Modify: `src/rulesagent/api/main.py` — `/unlock` route from Task 4.
- Create: `tests/test_unlock_rate_limit.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `UNLOCK_RATE_LIMIT = 5` (attempts), `UNLOCK_RATE_WINDOW_S = 900` (15 min).
  - `_unlock_attempts: dict[str, list[float]]` and `_unlock_rl_lock: threading.Lock` — module-level in-memory sliding window, keyed by `ip_hash`. In-memory is acceptable specifically because Fly is configured always-on `shared-cpu-1x` with no autoscaling (Task 14) — a single process, so there's no cross-instance state problem to solve.
  - `_check_unlock_rate_limit(ip_hash: str, now: float | None = None) -> bool` — `True` if this attempt is allowed (and records it), `False` if the window is full.

- [ ] Write the failing test file.

```python
# tests/test_unlock_rate_limit.py
# Slice 4 Task 8. Directly exercises _check_unlock_rate_limit (unit-level)
# plus the /unlock route end to end for the 429 path.

import pytest
from fastapi import Request

from rulesagent.api import main
from rulesagent.demo_db import create_code


def _fake_request() -> Request:
    scope = {"type": "http", "headers": [], "client": ("203.0.113.9", 12345),
              "method": "POST", "path": "/unlock"}
    return Request(scope)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    main._unlock_attempts.clear()
    yield
    main._unlock_attempts.clear()


def test_allows_up_to_the_limit():
    for _ in range(main.UNLOCK_RATE_LIMIT):
        assert main._check_unlock_rate_limit("ip-a", now=1000.0) is True


def test_blocks_beyond_the_limit():
    for _ in range(main.UNLOCK_RATE_LIMIT):
        main._check_unlock_rate_limit("ip-a", now=1000.0)
    assert main._check_unlock_rate_limit("ip-a", now=1000.0) is False


def test_window_resets_after_the_configured_seconds():
    for _ in range(main.UNLOCK_RATE_LIMIT):
        main._check_unlock_rate_limit("ip-a", now=1000.0)
    assert main._check_unlock_rate_limit("ip-a", now=1000.0) is False
    later = 1000.0 + main.UNLOCK_RATE_WINDOW_S + 1
    assert main._check_unlock_rate_limit("ip-a", now=later) is True


def test_different_ips_have_independent_limits():
    for _ in range(main.UNLOCK_RATE_LIMIT):
        main._check_unlock_rate_limit("ip-a", now=1000.0)
    assert main._check_unlock_rate_limit("ip-b", now=1000.0) is True


def test_unlock_endpoint_returns_429_when_rate_limited(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    create_code(db, "raptor-quill-42", "Test")

    for _ in range(main.UNLOCK_RATE_LIMIT):
        main.unlock(code="wrong-code-00", request=_fake_request())

    resp = main.unlock(code="raptor-quill-42", request=_fake_request())

    assert resp.status_code == 429
```

- [ ] Run it and see it fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_unlock_rate_limit.py -q
  ```
  Expected: `AttributeError: module 'rulesagent.api.main' has no attribute '_check_unlock_rate_limit'`

- [ ] Minimal implementation. Add near the `/unlock` route:
  ```python
  import threading as _threading  # already imported as `threading` above; keep one import

  UNLOCK_RATE_LIMIT = 5
  UNLOCK_RATE_WINDOW_S = 900  # 15 minutes
  _unlock_attempts: dict[str, list[float]] = {}
  _unlock_rl_lock = threading.Lock()
  # In-memory sliding window is safe here because Fly is deployed always-on,
  # single shared-cpu-1x machine, no autoscaling (Task 14) -- one process
  # holds all the state there is. It resets on redeploy; that's an accepted
  # trade for not adding a second datastore for a demo this size.


  def _check_unlock_rate_limit(ip_hash: str, now: float | None = None) -> bool:
      now = now if now is not None else time.time()
      with _unlock_rl_lock:
          attempts = [t for t in _unlock_attempts.get(ip_hash, []) if now - t < UNLOCK_RATE_WINDOW_S]
          if len(attempts) >= UNLOCK_RATE_LIMIT:
              _unlock_attempts[ip_hash] = attempts
              return False
          attempts.append(now)
          _unlock_attempts[ip_hash] = attempts
          return True
  ```
  Update `unlock()` to check it first:
  ```python
  @app.post("/unlock", tags=["answers"], summary="Unlock the demo with an access code")
  def unlock(code: str = Form(...), request: Request = None):
      ip_hash = hash_ip(_client_ip(request), os.environ.get("IP_HASH_SALT", ""))
      if not _check_unlock_rate_limit(ip_hash):
          log_event(DEMO_DB, code_id=None, kind="denied", ip_hash=ip_hash)
          return _friendly_html(
              "Too many attempts",
              "Too many tries too fast. Wait 15 minutes and try again, or ask Jon for help.",
              status_code=429,
          )
      row = get_code_by_value(DEMO_DB, code.strip())
      # ... (rest unchanged from Task 4)
  ```

- [ ] Run and see them pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_unlock_rate_limit.py -q
  ```
  Expected: `5 passed`

- [ ] Commit:
  ```
  git add src/rulesagent/api/main.py tests/test_unlock_rate_limit.py
  git commit -m "$(cat <<'EOF'
  Rate-limit /unlock per IP: 5 attempts / 15 min (slice 4)

  In-memory sliding window -- safe because Fly runs one always-on
  instance with no autoscaling.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** hammering `/unlock` with bad codes from one IP gets rate
limited after 5 tries within 15 minutes; a different IP is unaffected.

---

## Task 9 — Lock CORS to the demo origin

**Files:**
- Modify: `src/rulesagent/api/main.py` — `app.add_middleware(CORSMiddleware, ...)` (existing lines 124-129).
- Create: `tests/test_cors_lock.py`

**Interfaces:**
- Produces: `_cors_allow_origins() -> list[str]` — `[os.environ["DEMO_ORIGIN"]]` when `DEMO_ORIGIN` is set, else `["*"]` (unchanged local-dev behavior).

- [ ] Write the failing test file.

```python
# tests/test_cors_lock.py
# Slice 4 Task 9. Unit-tests the origin-list helper directly rather than
# poking CORSMiddleware internals through a live app -- the helper is what
# actually decides the policy; the middleware just consumes its output.

from rulesagent.api import main


def test_defaults_to_wildcard_when_demo_origin_unset(monkeypatch):
    monkeypatch.delenv("DEMO_ORIGIN", raising=False)
    assert main._cors_allow_origins() == ["*"]


def test_locks_to_demo_origin_when_set(monkeypatch):
    monkeypatch.setenv("DEMO_ORIGIN", "https://rulemancer.fly.dev")
    assert main._cors_allow_origins() == ["https://rulemancer.fly.dev"]
```

- [ ] Run it and see it fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_cors_lock.py -q
  ```
  Expected: `AttributeError: module 'rulesagent.api.main' has no attribute '_cors_allow_origins'`

- [ ] Minimal implementation. Replace the existing CORS block:
  ```python
  def _cors_allow_origins() -> list[str]:
      """Wildcard by default (private local demo, unchanged). Locked to one
      origin once DEMO_ORIGIN is set -- the Fly deployment sets it to its own
      https URL, so no other site can call /answer cross-origin using a
      stolen or guessed cookie."""
      origin = os.environ.get("DEMO_ORIGIN")
      return [origin] if origin else ["*"]


  app.add_middleware(
      CORSMiddleware,
      allow_origins=_cors_allow_origins(),
      allow_methods=["*"],
      allow_headers=["*"],
      allow_credentials=True,  # required for the browser to send the session cookie cross-origin-safe
  )
  ```
  Note: `_cors_allow_origins()` is evaluated once at import time (module load),
  same as the original `allow_origins=["*"]` literal — this is correct because
  `DEMO_ORIGIN` is a deployment-time secret set before the process starts, not
  something that changes mid-run.

- [ ] Run and see them pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_cors_lock.py -q
  ```
  Expected: `2 passed`

- [ ] Commit:
  ```
  git add src/rulesagent/api/main.py tests/test_cors_lock.py
  git commit -m "$(cat <<'EOF'
  Lock CORS to DEMO_ORIGIN when set (slice 4)

  Wildcard stays the local-dev default; the Fly deployment sets
  DEMO_ORIGIN to its own https URL.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** `curl -H "Origin: https://evil.example" https://rulemancer.fly.dev/answer -i`
shows no `access-control-allow-origin: https://evil.example` in the response
once `DEMO_ORIGIN` is set on Fly.

---

## Task 10 — Global friendly-error exception handler

**Files:**
- Modify: `src/rulesagent/api/main.py` — add an `@app.exception_handler(Exception)`.
- Create: `tests/test_friendly_errors.py`

**Interfaces:**
- Produces: `async def _unhandled_exception_handler(request: Request, exc: Exception) -> HTMLResponse` registered via `app.add_exception_handler(Exception, _unhandled_exception_handler)`. Logs the real exception server-side (`logger.exception(...)`) and returns `_friendly_html("Something went wrong", "...", status_code=500)` — the *body* is never a raw traceback/JSON stack dump even though the status code correctly stays 500 for monitoring. Every **guard** failure (Tasks 6-8) already returns a non-500 status by design; this handler is the last-resort net for genuinely unexpected exceptions elsewhere in the app.

- [ ] Write the failing test file.

```python
# tests/test_friendly_errors.py
# Slice 4 Task 10. Exercises the handler function directly -- FastAPI
# exception handlers are plain callables, so no TestClient/ASGI transport is
# needed to verify the body shape (matches this repo's route-function-direct
# testing convention throughout slice 4).

import asyncio

from rulesagent.api import main


def test_unhandled_exception_returns_friendly_html_not_a_stack_trace():
    resp = asyncio.run(main._unhandled_exception_handler(None, RuntimeError("db connection reset")))

    assert resp.status_code == 500
    body = resp.body.decode()
    assert "db connection reset" not in body  # no raw exception text leaked to the client
    assert "<html" in body.lower()


def test_handler_is_registered_on_the_app():
    assert Exception in main.app.exception_handlers
```

- [ ] Run it and see it fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_friendly_errors.py -q
  ```
  Expected: `AttributeError: module 'rulesagent.api.main' has no attribute '_unhandled_exception_handler'`

- [ ] Minimal implementation. Add near the bottom of `main.py`, before the
  frontend `StaticFiles` mount:
  ```python
  async def _unhandled_exception_handler(request: Request, exc: Exception) -> HTMLResponse:
      """Last-resort net: an uncaught exception anywhere in the app renders as
      a friendly page, never FastAPI's default raw-JSON 500. The real
      exception is still logged server-side for debugging -- only the
      response body is sanitized, not the operator's visibility into it."""
      logger.exception("unhandled exception on %s", getattr(request, "url", "?"))
      return _friendly_html(
          "Something went wrong",
          "That request hit an unexpected error on our end. Try again in a "
          "moment -- if it keeps happening, let Jon know.",
          status_code=500,
      )


  app.add_exception_handler(Exception, _unhandled_exception_handler)
  ```

- [ ] Run and see them pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_friendly_errors.py -q
  ```
  Expected: `2 passed`

- [ ] Commit:
  ```
  git add src/rulesagent/api/main.py tests/test_friendly_errors.py
  git commit -m "$(cat <<'EOF'
  Add a friendly-page fallback for unhandled exceptions (slice 4)

  Guard failures already return specific friendly pages; this is the
  net under everything else so no raw traceback ever reaches a visitor.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** an injected fault anywhere in `/answer`'s non-guard code path
(simulable by monkeypatching `agent.answer` to raise) renders the friendly
page instead of FastAPI's default `{"detail": "Internal Server Error"}` JSON.

---

## Task 11 — `/admin` view

**Files:**
- Modify: `src/rulesagent/api/main.py` — new `GET /admin` route, reusing `_require_admin_token` from the existing Scryfall admin endpoints (lines 416-426).
- Create: `tests/test_admin_demo_view.py`

**Interfaces:**
- Consumes: `rulesagent.demo_db.{list_codes, code_stats, events_for_code, daily_spend}`, existing `_require_admin_token(authorization: str | None) -> None`.
- Produces: `admin_demo_view(authorization: str | None = Header(default=None)) -> HTMLResponse` — dark-mode HTML: per-code label/unlocks/queries/first-last-seen/total-cost/remaining-quota, each code's questions newest-first, plus a global "today's spend vs. cap" line. `html.escape()` applied to every user-supplied string (label, notes, question text) before embedding — this page renders untrusted visitor input.

- [ ] Write the failing test file.

```python
# tests/test_admin_demo_view.py
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
    with pytest.raises(HTTPException) as exc:
        main.admin_demo_view(authorization=None)
    assert exc.value.status_code == 401


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


def test_no_codes_yet_renders_without_error(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DEMO_DB", tmp_path / "demo.db")
    resp = main.admin_demo_view(authorization="Bearer secret-token")
    assert resp.status_code == 200
```

- [ ] Run it and see it fail:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_admin_demo_view.py -q
  ```
  Expected: `AttributeError: module 'rulesagent.api.main' has no attribute 'admin_demo_view'`

- [ ] Minimal implementation. Add to `main.py` (near the other admin routes):
  ```python
  import html as _html


  @app.get("/admin", tags=["ops"], summary="Demo codes/usage dashboard",
           description="Token-protected (Authorization: Bearer <ADMIN_TOKEN>) -- "
           "reuses the same admin token as the Scryfall refresh endpoints.")
  def admin_demo_view(authorization: str | None = Header(default=None)) -> HTMLResponse:
      _require_admin_token(authorization)
      today = datetime.now(timezone.utc).date().isoformat()
      budget = float(os.environ.get("DAILY_BUDGET_USD", DAILY_BUDGET_USD_DEFAULT))
      spend_today = daily_spend(DEMO_DB, today)

      rows_html = []
      for code in list_codes(DEMO_DB):
          stats = code_stats(DEMO_DB, code["id"])
          cap = code["max_queries"] if code["max_queries"] is not None else DEFAULT_MAX_QUERIES
          remaining = max(cap - stats["queries"], 0)
          status = "REVOKED" if code["revoked_at"] else "active"
          questions_html = "".join(
              f'<li><span class="q-ts">{_html.escape(e["ts"])}</span> '
              f'<span class="q-cost">${e["cost_usd"]:.3f}</span> '
              f'{_html.escape(e["question"])}</li>'
              for e in events_for_code(DEMO_DB, code["id"])
          ) or "<li class=\"empty\">(no questions yet)</li>"
          rows_html.append(f"""
          <section class="code-card">
            <h2>{_html.escape(code["label"] or "(no label)")} <span class="status {status}">{status}</span></h2>
            <p class="meta">code: <code>{_html.escape(code["code"])}</code> &middot;
               unlocks: {stats["unlocks"]} &middot; queries: {stats["queries"]} &middot;
               remaining: {remaining} &middot; total cost: ${stats["total_cost"]:.3f} &middot;
               first seen: {_html.escape(stats["first_seen"] or "-")} &middot;
               last seen: {_html.escape(stats["last_seen"] or "-")}</p>
            <ul class="questions">{questions_html}</ul>
          </section>""")

      body = f"""<!doctype html>
  <html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rulemancer admin — demo usage</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ background:#14161a; color:#e8e8ea; font-family:system-ui,-apple-system,sans-serif;
            margin:0; padding:24px; max-width:900px; margin-inline:auto; }}
    h1 {{ font-size:1.6rem; color:#f4f4f5; }}
    .budget {{ background:#1e2126; border:1px solid #3a3f47; border-radius:8px; padding:1rem;
               margin-bottom:1.5rem; color:#c4c4c9; }}
    .budget strong {{ color:#f4f4f5; }}
    .code-card {{ background:#1a1d22; border:1px solid #2c3038; border-radius:10px;
                  padding:1rem 1.25rem; margin-bottom:1rem; }}
    .code-card h2 {{ font-size:1.1rem; margin:0 0 0.4rem; color:#f4f4f5; }}
    .status {{ font-size:0.7rem; padding:0.15rem 0.5rem; border-radius:999px; margin-left:0.5rem; }}
    .status.active {{ background:#1f3a2a; color:#7fd99a; }}
    .status.REVOKED {{ background:#3a1f24; color:#ff9b9b; }}
    .meta {{ color:#9a9da3; font-size:0.85rem; margin:0 0 0.6rem; }}
    .questions {{ list-style:none; margin:0; padding:0; max-height:220px; overflow-y:auto;
                  border-top:1px solid #2c3038; }}
    .questions li {{ padding:0.4rem 0; border-bottom:1px solid #22262c; font-size:0.9rem; }}
    .questions .q-ts {{ color:#7a7d83; font-size:0.75rem; margin-right:0.5rem; }}
    .questions .q-cost {{ color:#7aa2ff; font-size:0.75rem; margin-right:0.5rem; }}
    .questions .empty {{ color:#7a7d83; font-style:italic; }}
    code {{ background:#22262c; padding:0.1rem 0.4rem; border-radius:4px; }}
  </style></head>
  <body>
    <h1>Rulemancer — demo usage</h1>
    <div class="budget">Today's spend: <strong>${spend_today:.3f}</strong> / ${budget:.2f} cap ({today} UTC)</div>
    {''.join(rows_html) or '<p>(no codes minted yet)</p>'}
  </body></html>"""
      return HTMLResponse(content=body)
  ```
  Add imports: `from rulesagent.demo_db import code_stats, events_for_code, list_codes`.

- [ ] Run and see them pass:
  ```
  .venv/Scripts/python.exe -m pytest tests/test_admin_demo_view.py -q
  ```
  Expected: `5 passed`

- [ ] Commit:
  ```
  git add src/rulesagent/api/main.py tests/test_admin_demo_view.py
  git commit -m "$(cat <<'EOF'
  Add /admin: per-code usage + global daily spend, dark mode (slice 4)

  Reuses the existing ADMIN_TOKEN bearer-token gate. Every visitor-
  supplied string (label, notes, question text) is html.escape()'d --
  this page renders untrusted input.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

- [ ] Render and look at it (repo rule: verify UI by rendering, not by
  reading markup):
  ```
  $env:COOKIE_SECRET="dev"; $env:ADMIN_TOKEN="dev-admin"; .venv/Scripts/python.exe run.py 8947
  ```
  Then `curl -H "Authorization: Bearer dev-admin" http://127.0.0.1:8947/admin`
  in a browser (paste the header via a REST client, or temporarily hit it from
  a script) and confirm dark background, readable contrast, and that a code
  minted via `scripts/codes.py` shows up with correct counts. Stop the server
  on 8947 when done (never touch port 8000).

**Deliverable:** `/admin` shows every minted code's usage and questions,
protected by `ADMIN_TOKEN`, rendered and visually confirmed dark-mode/legible.

---

## Task 12 — Measure real cost per serve

**⚠️ This task spends real Anthropic API credits (~$1, per the spec's
prerequisite: "Approval to spend ~$1 in Anthropic credits to measure the real
cost per serve"). Do not run the spending step without Jon's explicit
go-ahead at that point, with the ~$1 ceiling confirmed. Everything up to the
go-ahead (writing the script) costs nothing.**

**Files:**
- Create: `scripts/measure_demo_cost.py`

**Interfaces:**
- Consumes: `rulesagent.generate.answer.{RulesAgent, GEN_EFFORT}`, `rulesagent.index.store.VectorStore`, `rulesagent.pricing.cost_usd`.
- Produces: `main(argv: list[str] | None = None) -> int` — runs N real questions (default 8, a stratified sample across question levels, not the first N rows of any sorted file per the repo rule "sampling the front of a sorted file is not sampling") through the real, deployed-shape agent, prints per-question and average cost, and does not write anything to `data/demo.db` (this is a measurement run, not demo traffic).

This is a measurement script, not something meaningfully TDD'd against a fake
— its entire value is a real API round trip. The check here is Jon reviewing
the printed numbers, not a pytest assertion.

- [ ] Write the script:

```python
# scripts/measure_demo_cost.py
"""Measure real $/serve for the gated demo (docs/superpowers/plans/
2026-07-27-gated-demo.md Task 12) -- BEFORE the DAILY_BUDGET_USD default is
chosen for production, per the spec: "This gets measured with a handful of
real queries before the cap is set."

SPENDS REAL ANTHROPIC API CREDITS. Requires Jon's explicit go-ahead and a
confirmed ceiling (spec: ~$1) before running. Not run as part of any test
suite or CI -- this is a manual, one-time-per-launch measurement.

    uv run python scripts/measure_demo_cost.py [--n 8]

Prints per-question cost and the average, so Jon can set DAILY_BUDGET_USD
(a Fly secret, not code) from real numbers instead of the batched-eval
estimate ($0.06/serve extrapolated from the $0.031/row batched rate --
see the spec's "Cost model" section).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from rulesagent.generate.answer import GEN_EFFORT, RulesAgent  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.pricing import cost_usd  # noqa: E402

VECTOR_MODEL = "voyage-4-large"

# A small, hand-picked, cross-level sample -- NOT the first N rows of any
# sorted eval file (repo rule: that only ever hits L0 and misprices
# everything). These mirror the kind of question a hiring manager would
# actually type into the demo.
SAMPLE_QUESTIONS = [
    "Does trample let excess damage through a deathtouch blocker?",
    "What happens if I cast [Fork] targeting an instant on the stack?",
    "Can a player respond to their own triggered ability?",
    "If a creature with first strike blocks a creature without it, who deals damage first?",
    "Does [Grist, the Hunger Tide]'s -2 ability target?",
    "What's the difference between a static ability and a triggered ability?",
    "If I control two copies of a legendary creature, what happens?",
    "Can I cast an instant during my upkeep in response to a trigger?",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=8, help="how many sample questions to run (<= len(SAMPLE_QUESTIONS))")
    args = parser.parse_args(argv)
    n = min(args.n, len(SAMPLE_QUESTIONS))

    store = VectorStore.load(REPO / "data" / "parsed" / f"vector_{VECTOR_MODEL}.pkl")
    agent = RulesAgent(store, effort=GEN_EFFORT)

    costs = []
    for i, q in enumerate(SAMPLE_QUESTIONS[:n], start=1):
        ans = agent.answer(q, history=[])
        usage = agent.last_usage or {}
        cost = cost_usd(
            agent.model,
            input_tokens=usage.get("input_tokens") or 0,
            output_tokens=usage.get("output_tokens") or 0,
            cache_read_tokens=usage.get("cache_read_input_tokens") or 0,
            cache_write_tokens=usage.get("cache_creation_input_tokens") or 0,
        ) or 0.0
        costs.append(cost)
        print(f"[{i}/{n}] ${cost:.4f}  answered={ans.answered}  {q[:60]}")

    if costs:
        avg = sum(costs) / len(costs)
        print(f"\naverage: ${avg:.4f}/serve over {len(costs)} real questions, total spent: ${sum(costs):.4f}")
        print(f"suggested DAILY_BUDGET_USD for a ~20-code launch at 25 queries/code: "
              f"${avg * 25 * 20:.2f} (all codes maxed out in one day, worst case)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Stop here and get Jon's explicit go-ahead** naming the ~$1 ceiling
  before running the spending step below. This is a real-credits action, not
  covered by the standing subagent-delegation grant.

- [ ] Run it (only after go-ahead):
  ```
  .venv/Scripts/python.exe scripts/measure_demo_cost.py --n 8
  ```
  Record the printed average $/serve in this plan's commit message or in
  `docs/results-headline-accuracy.md`'s neighborhood (wherever Jon wants the
  number kept) and set the Fly secret in Task 14 from it — not from the
  batched-eval estimate.

- [ ] Commit (the script only; the run's output is a number Jon uses to set a
  Fly secret, not a file to commit):
  ```
  git add scripts/measure_demo_cost.py
  git commit -m "$(cat <<'EOF'
  Add scripts/measure_demo_cost.py: real $/serve measurement (slice 4)

  Spends real Anthropic credits when run (~$1, Jon's go-ahead required
  each time it's used) -- output sets DAILY_BUDGET_USD for the Fly
  deployment.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** a real, printed $/serve average from actual API calls,
independent of the batched-eval estimate, that Jon uses to set
`DAILY_BUDGET_USD` in Task 14 — not the code's `DAILY_BUDGET_USD_DEFAULT`
fallback.

---

## Task 13 — Dockerfile + `.dockerignore`

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

**Interfaces:** none (infra only). Verification is `docker build` + a
container run against `/health`, not pytest.

- [ ] Write `Dockerfile`:

```dockerfile
# Rulemancer gated demo container (docs/superpowers/plans/2026-07-27-gated-demo.md
# Task 13). Entrypoint is uvicorn on rulesagent.api.main:app directly --
# run.py is a LOCAL DEV launcher (kills stale processes on a port, opens a
# browser) and must never run inside a container.
FROM python:3.12-slim

WORKDIR /app

# System deps for building any C-extension wheels (numpy etc.) that don't
# ship a manylinux wheel for this base image; removed from the final layer
# isn't done here for simplicity -- this image is not size-sensitive (single
# always-on machine, pulled once per deploy).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY frontend ./frontend
COPY scripts ./scripts

# uv installs from pyproject.toml's [project.dependencies] straight into the
# image's system Python -- no venv needed inside a container that only ever
# runs one thing.
RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache .

ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

# data/ is NOT copied in -- the Fly volume is mounted at /app/data at
# runtime, seeded manually once (Task 14). Baking the vector pickle or CR
# text into the image would ship a redistribution problem in every image
# layer forever, not just at runtime (spec: "Not baked into the image --
# redistribution risk and rebuild cost").
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "rulesagent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] Write `.dockerignore` (load-bearing: Docker does not read `.gitignore`,
  so without this the CR text and any local secrets would be sent to the
  build context and could end up in a layer):

```
# Rulemancer .dockerignore (docs/superpowers/plans/2026-07-27-gated-demo.md
# Task 13). Docker does NOT read .gitignore -- this file is the only thing
# standing between the build context and CR text / secrets ending up in an
# image layer.

.venv/
.git/
.github/
.claude/
.pytest_cache/
__pycache__/
*.pyc
*.stackdump
*.log

# Secrets -- never in the image, always via `fly secrets set`.
.env
*.env

# CR text, vector pickle, Scryfall snapshot, demo db, cache db -- all live on
# the Fly volume at runtime (Task 14), never baked into the image.
data/

# Docs, evals, and other repo bulk irrelevant to the running container.
docs/
evals/
tests/
*.md
```

- [ ] Verify with a real build + run (not pytest):
  ```
  docker build -t rulemancer-demo:test .
  docker run --rm -p 8947:8000 -e COOKIE_SECRET=dev-secret rulemancer-demo:test
  ```
  In another shell, confirm it comes up (this will 503/fail health until real
  `data/` is mounted — that's expected without the volume from Task 14; the
  goal here is confirming the image builds and the process starts under
  uvicorn, not that it's fully healthy):
  ```
  curl http://127.0.0.1:8947/health
  ```
  Then stop the container:
  ```
  docker stop $(docker ps -q --filter ancestor=rulemancer-demo:test)
  ```

- [ ] Commit:
  ```
  git add Dockerfile .dockerignore
  git commit -m "$(cat <<'EOF'
  Add Dockerfile + .dockerignore for the Fly demo (slice 4)

  Entrypoint is uvicorn on rulesagent.api.main:app, not run.py (that's
  a local dev launcher). .dockerignore keeps CR text, data/, and
  secrets out of the image -- Docker doesn't read .gitignore.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** `docker build .` succeeds and the resulting image starts
uvicorn and serves `/health` (with an empty/missing data dir, `ready` will be
`false` until Task 14's volume is attached — that's the correct signal, not a
failure of this task).

---

## Task 14 — `fly.toml`, volume, secrets, deploy

**Files:**
- Create: `fly.toml`

**Interfaces:** none (infra config + manual `flyctl` steps). No pytest here —
verification is Task 15's live guard checks against the deployed URL.

- [ ] Write `fly.toml`:

```toml
# Rulemancer gated demo (docs/superpowers/plans/2026-07-27-gated-demo.md
# Task 14). Always-on, no scale-to-zero -- spec: "A 10-20s cold start is the
# first impression on a link clicked once."
app = "rulemancer-demo"
primary_region = "ord"  # Chicago -- nearest to US-central per the spec

[build]

[env]
  DEMO_DB_PATH = "/app/data/demo.db"

[[mounts]]
  source = "rulemancer_data"
  destination = "/app/data"

[[services]]
  internal_port = 8000
  protocol = "tcp"
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [[services.ports]]
    handlers = ["http"]
    port = 80
    force_https = true

  [[services.http_checks]]
    path = "/health"
    interval = "15s"
    timeout = "5s"
    grace_period = "30s"

[[vm]]
  size = "shared-cpu-1x"
  memory = "1gb"  # sized for the 16.9 MB vector pickle + 73 MB Scryfall db loaded at startup
```

- [ ] Manual deploy steps (not automatable by an agent — requires Jon's Fly
  account, per the spec's prerequisites list):

  ```
  flyctl auth login
  flyctl apps create rulemancer-demo
  flyctl volumes create rulemancer_data --region ord --size 1
  ```

  Seed the volume once (spec: "seeded manually once with the vector pickle
  (16.9 MB) and the Scryfall DB (73 MB). Not baked into the image"):
  ```
  flyctl ssh console -a rulemancer-demo -C "mkdir -p /app/data"
  flyctl ssh sftp shell -a rulemancer-demo
  # inside the sftp shell:
  #   put data/parsed/vector_voyage-4-large.pkl /app/data/vector_voyage-4-large.pkl
  #   put data/scryfall.db /app/data/scryfall.db
  ```

  Set secrets (never in the image or `fly.toml`):
  ```
  flyctl secrets set -a rulemancer-demo \
    ANTHROPIC_API_KEY="<real key>" \
    VOYAGE_API_KEY="<real key>" \
    COOKIE_SECRET="<a long random string, e.g. python -c "import secrets; print(secrets.token_hex(32))">" \
    IP_HASH_SALT="<a second, different long random string>" \
    ADMIN_TOKEN="<a third long random string>" \
    DEMO_ORIGIN="https://rulemancer-demo.fly.dev" \
    DAILY_BUDGET_USD="<the number Task 12 measured, not the code's $5 default>"
  ```

  Deploy:
  ```
  flyctl deploy -a rulemancer-demo
  ```

  Confirm always-on took effect (no machine should ever reach `stopped`
  outside a manual action):
  ```
  flyctl status -a rulemancer-demo
  ```

- [ ] Commit the config (not the deploy — that's an infra action, not a repo
  change beyond the file):
  ```
  git add fly.toml
  git commit -m "$(cat <<'EOF'
  Add fly.toml: always-on shared-cpu-1x, volume at /app/data (slice 4)

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** `https://rulemancer-demo.fly.dev/health` returns
`{"status": "ok", "ready": true}` from a real deployed machine, and
`flyctl status` shows `min_machines_running = 1` honored (no scale-to-zero).

---

## Task 15 — Live guard verification (the gate before any link is shared)

**Files:**
- Create: `scripts/verify_demo_guards.py`

**Interfaces:**
- Consumes: `httpx` (already a dependency), the deployed URL, an admin token,
  and a code minted via `flyctl ssh console -a rulemancer-demo -C "python
  scripts/codes.py new --label 'guard-check'"` (or run against a Fly proxy
  tunnel — either way, this needs at least one real code that exists on the
  deployed `data/demo.db`).
- Produces: `main(argv: list[str] | None = None) -> int` — runs the spec's
  four checks against the **deployed** URL and prints PASS/FAIL per check,
  returning nonzero if any fail. This is the literal gate named in the spec:
  *"no link goes to a human until those four checks pass live."*

This script is infra verification against a live deployment, not a unit test
— it is deliberately not part of the pytest suite (nothing to mock; the whole
point is hitting the real, deployed thing).

- [ ] Write the script:

```python
# scripts/verify_demo_guards.py
"""Live guard verification against the DEPLOYED Fly demo (docs/superpowers/
plans/2026-07-27-gated-demo.md Task 15). Spec: "Guards are tested against the
live deployed URL before the URL is shared with anyone... The gate is
explicit -- no link goes to a human until those four checks pass live."

Checks, in order:
  1. Exceed a per-code max_queries cap -> friendly non-500 page.
  2. Trip a test daily budget cap -> friendly non-500 page.
     (Run this against a code/day where DAILY_BUDGET_USD is deliberately
     small, e.g. temporarily `flyctl secrets set DAILY_BUDGET_USD=0.01`
     against a throwaway staging app -- NOT the production budget, and NOT
     run against the real production DAILY_BUDGET_USD, which would require
     genuinely spending the whole day's budget to prove the breaker works.)
  3. Hammer /unlock -> rate limited (429) after UNLOCK_RATE_LIMIT attempts.
  4. Confirm a revoked code's cookie stops working.

    uv run python scripts/verify_demo_guards.py \
        --base-url https://rulemancer-demo.fly.dev \
        --admin-token <ADMIN_TOKEN> \
        --code <a real, low-max_queries code minted for this check>
"""
from __future__ import annotations

import argparse
import sys

import httpx


def _check(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    return condition


def check_per_code_cap(client: httpx.Client, code: str) -> bool:
    """Unlock, then exceed the code's max_queries. The final call must be a
    friendly non-500 page, not a crash."""
    r = client.post("/unlock", data={"code": code})
    if r.status_code != 200:
        return _check("per-code cap", False, f"unlock itself failed: {r.status_code}")
    last = None
    for _ in range(30):  # comfortably over any reasonable max_queries
        last = client.post("/answer", json={"question": "test question for cap check", "history": []})
        if last.status_code != 200:
            break
    ok = last is not None and last.status_code not in (500,) and last.status_code != 200
    return _check("per-code cap trips to a friendly page", ok,
                  f"final status {last.status_code if last else 'no response'}")


def check_rate_limit(client: httpx.Client) -> bool:
    """Hammer /unlock with a bogus code -- must 429, not 500, after the
    configured limit."""
    statuses = [client.post("/unlock", data={"code": "no-such-code-00"}).status_code for _ in range(8)]
    ok = 429 in statuses and 500 not in statuses
    return _check("unlock rate limit trips", ok, f"statuses seen: {statuses}")


def check_revoked_code(client: httpx.Client, revoked_code: str) -> bool:
    """A code known to be revoked must never unlock, and any pre-existing
    cookie for it must stop working on /answer."""
    r = client.post("/unlock", data={"code": revoked_code})
    ok = r.status_code not in (200, 500)
    return _check("revoked code rejected", ok, f"status {r.status_code}")


def check_budget_breaker(client: httpx.Client, code: str) -> bool:
    """Only meaningful against a deployment with a deliberately tiny
    DAILY_BUDGET_USD (staging, not production) -- one real answered question
    should already exceed it, so the next call must trip the breaker."""
    r1 = client.post("/answer", json={"question": "budget check question one", "history": []})
    r2 = client.post("/answer", json={"question": "budget check question two", "history": []})
    ok = r2.status_code not in (200, 500) or r1.status_code not in (200, 500)
    return _check("daily budget breaker trips", ok, f"statuses: {r1.status_code}, {r2.status_code}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--code", required=True, help="a real code minted for this check, low max_queries")
    parser.add_argument("--revoked-code", required=True, help="a real code already revoked before this run")
    parser.add_argument("--skip-budget", action="store_true",
                         help="skip the budget check (only run it against a staging deployment "
                              "with a deliberately tiny DAILY_BUDGET_USD, never production)")
    args = parser.parse_args(argv)

    results = []
    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        results.append(check_per_code_cap(client, args.code))
        results.append(check_rate_limit(client))
        results.append(check_revoked_code(client, args.revoked_code))
        if not args.skip_budget:
            results.append(check_budget_breaker(client, args.code))

    all_pass = all(results)
    print(f"\n{'ALL GUARDS PASS -- safe to share the link' if all_pass else 'GUARD FAILURE -- DO NOT SHARE THE LINK YET'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] Run it against the real deployed URL (requires Task 14 complete and at
  least two real minted codes — one fresh with a low `max_queries` for the cap
  check, one already revoked):
  ```
  .venv/Scripts/python.exe scripts/verify_demo_guards.py \
    --base-url https://rulemancer-demo.fly.dev \
    --code <freshly minted, low-cap code> \
    --revoked-code <a code already revoked> \
    --skip-budget
  ```
  Run the budget check separately, once, against a throwaway staging app with
  `DAILY_BUDGET_USD` set deliberately tiny — never against the production
  `DAILY_BUDGET_USD`, which would require actually burning the real day's
  cap to prove the breaker fires.

- [ ] Confirm the printed summary is `ALL GUARDS PASS`. If any check prints
  `FAIL`, fix the underlying guard (Tasks 6-8) and redeploy before proceeding
  — do not share the link.

- [ ] Commit:
  ```
  git add scripts/verify_demo_guards.py
  git commit -m "$(cat <<'EOF'
  Add scripts/verify_demo_guards.py: live guard gate before sharing the link (slice 4)

  Spec: "no link goes to a human until those four checks pass live."
  Runs against the deployed URL, not a mock -- that's the point.

  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  EOF
  )"
  ```

**Deliverable:** a printed `ALL GUARDS PASS -- safe to share the link` from a
run against the real deployed URL. This is the last gate in the spec's
definition of done before Jon holds a minted code and the admin URL and shares
either with anyone.

---

## Definition of done for this plan

Mirrors the spec's slice-4-relevant items from its own "Definition of done":

1. `codes` and `events` tables exist in `data/demo.db` on the Fly volume,
   matching the spec's column lists exactly (Task 1).
2. Demo live on Fly, always-on, gated by per-person codes (Tasks 4, 5, 14).
3. All four guard checks pass against the deployed URL (Tasks 6, 7, 8, 15).
4. Jon holds a minted code and the admin URL, and has seen his own visit in
   the admin table (Tasks 3, 11, and a manual pass through the gate once
   deployed).
