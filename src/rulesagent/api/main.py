"""FastAPI wrapper over RulesAgent (docs/plan-api.md).

Thin -- no RAG logic here. Loads the vector store once at startup, holds one
RulesAgent, and serves an ENRICHED answer (cited rule/glossary text + card data
+ optional debug) plus a Scryfall-proxied card autocomplete for the frontend's
@-picker.

Private demo: no auth / rate-limiting (decision in the plan). A single lock
still serializes answer processing, but not for cache safety anymore -- L3
(docs/plan-l3-sqlite-caches.md) moved every cache to per-key SQLite writes,
so concurrent requests can't corrupt them. The lock's remaining job is
narrower: it guards the `agent.last_*` recorder reads below (another request
could overwrite them between answer() and the reads) until answer() returns
a result object instead of recorder attributes -- its own small slice, not
smuggled into L3.

Run: uv run uvicorn rulesagent.api.main:app --reload
"""

import json
import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import BackgroundTasks, Cookie, FastAPI, Form, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rulesagent.cache import DEFAULT_DB
from rulesagent.demo_auth import (
    COOKIE_MAX_AGE_S, hash_ip, ip_hash_salt, session_secret, sign_session, verify_session,
)
from rulesagent.demo_db import (
    DEFAULT_DEMO_DB, count_queries, daily_spend, get_code_by_id, get_code_by_value, log_event,
)
from rulesagent.generate.answer import GEN_EFFORT, PROMPT_VERSION, RulesAgent
from rulesagent.index.store import VectorStore
from rulesagent.pricing import cost_usd

logger = logging.getLogger(__name__)

REPO = Path(__file__).parent.parent.parent.parent
VECTOR_MODEL = "voyage-4-large"
SCRYFALL_AUTOCOMPLETE = "https://api.scryfall.com/cards/autocomplete"
SCRYFALL_HEADERS = {"User-Agent": "mtg-rules-bot/0.1 (learning project)", "Accept": "application/json"}
DEFAULT_MAX_QUERIES = 25  # used only when a code's max_queries column is NULL

DAILY_BUDGET_USD_DEFAULT = 5.0
# Conservative starting point. Task 12 measures the real $/serve and Jon
# sets DAILY_BUDGET_USD as a Fly secret from that number before the demo
# goes live -- read here at request time (os.environ.get, not a
# module-load-time constant), so changing it needs no redeploy.

UNPRICED_QUERY_ESTIMATE_USD = 0.15
# Fix round 1: an upper-bound STAND-IN for one query whose cost_usd came
# back NULL (a cost-calculation failure -- see _record_query_event), NOT a
# measured figure. Roughly 2.5x the expected ~$0.06/query, so pricing an
# unpriced row at this value errs toward tripping the breaker a little
# early rather than a little late -- the safe direction. Deliberately NOT
# "trip on any NULL row": that treated one transient pricing hiccup as
# grounds to 503 every visitor for the rest of the UTC day, which is far
# too much availability lost for what is actually a small, bounded amount
# of unknown spend (one query, not an unknown number of them). Task 12
# measures the real $/serve and can revisit this constant too.

# scripts/ isn't a package under src/ -- same sys.path-insertion convention
# tests/test_watch_runs.py already uses for evals/watch_runs.py. The admin
# refresh endpoint below must call the SAME shared import function the CLI
# uses (docs/plan-scryfall-local-bulk.md Sec 5 item 2: "not a duplicated
# code path"), so this module needs a real import of it, not a reimplementation.
sys.path.insert(0, str(REPO / "scripts"))
import refresh_scryfall_bulk  # noqa: E402

_state: dict = {}
_lock = threading.Lock()
# Serializes /answer. Cache writes no longer need this (L3: per-key SQLite).
# It stays to guard the `agent.last_*` recorder reads made right after
# answer() -- another concurrent request could overwrite those attributes
# between the call and the reads.

# --- Slice 4: gated demo (docs/superpowers/plans/2026-07-27-gated-demo.md) -
COOKIE_NAME = "rulemancer_demo"
DEMO_DB = DEFAULT_DEMO_DB
# Module-level so tests can monkeypatch.setattr(main, "DEMO_DB", tmp_db) the
# same way _state is monkeypatched elsewhere in this file's test suite.


def _gate_enabled() -> bool:
    """Gating is OFF unless COOKIE_SECRET is configured. Local dev (`python
    run.py`) and the existing test suite never set it, so this whole slice
    is inert there -- only the Fly deployment sets it and becomes gated.
    Reads via demo_auth.session_secret() (call-time, not an import-time
    snapshot) -- Task 4 fix-round-1: this and _require_demo_config below are
    now the ONLY places in this module that read COOKIE_SECRET/IP_HASH_SALT
    from the environment; every other call site goes through them so there
    is exactly one source of truth for demo config, not a raw os.environ
    read scattered per call site."""
    return bool(session_secret())


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


UNLOCK_RATE_LIMIT = 5
UNLOCK_RATE_WINDOW_S = 900  # 15 minutes
_UNLOCK_RL_MAX_KEYS = 10_000
# In-memory sliding window is safe here because Fly is deployed always-on,
# single shared-cpu-1x machine, no autoscaling (Task 14) -- one process
# holds all the state there is. It resets on redeploy or restart, and it
# does not span machines; that's an accepted trade for not adding a second
# datastore for a demo this size.
#
# Keyed by ip_hash, the same hashed value _client_ip()/hash_ip() already
# produce for event logging. _client_ip() prefers Fly-Client-IP (set by
# Fly's edge, not attacker-controlled) and only falls back to
# X-Forwarded-For -- which a caller can forge -- when Fly-Client-IP is
# absent. In the real Fly deployment that fallback never triggers, so the
# rate limit key is trustworthy there. If this ever runs somewhere
# Fly-Client-IP isn't set, the limit is bypassable by varying
# X-Forwarded-For per request; this code does not change _client_ip's
# fallback chain (it's correct for logging) or claim protection it doesn't
# have in that configuration.
_unlock_attempts: dict[str, list[float]] = {}
_unlock_rl_lock = threading.Lock()


def _prune_unlock_attempts(now: float) -> None:
    """Bound the table's memory. Called while holding _unlock_rl_lock, only
    once _unlock_attempts has grown past _UNLOCK_RL_MAX_KEYS -- an attacker
    who forges a fresh IP header on every request can't be rate limited by
    key (see the fallback-chain note above), but they also can't grow this
    dict without bound: expired entries are dropped first, and if the table
    is still oversized (all keys still within the window), the
    least-recently-active keys are evicted until back under the cap."""
    for k in [k for k, v in _unlock_attempts.items()
              if not [t for t in v if now - t < UNLOCK_RATE_WINDOW_S]]:
        del _unlock_attempts[k]
    if len(_unlock_attempts) > _UNLOCK_RL_MAX_KEYS:
        by_recency = sorted(_unlock_attempts.items(), key=lambda kv: max(kv[1]))
        for k, _ in by_recency[: len(_unlock_attempts) - _UNLOCK_RL_MAX_KEYS]:
            del _unlock_attempts[k]


def _check_unlock_rate_limit(ip_hash: str, now: float | None = None) -> bool:
    """True if this attempt is allowed (and records it), False if the
    15-minute sliding window is already full. Counts EVERY call -- success
    or failure alike, since the check runs before /unlock knows whether the
    code was right -- so a legitimate person who unlocks on their first try
    is never punished, but a fumbled second or third try still counts
    toward the same 5-per-15-minutes budget as a scripted guesser would
    burn through."""
    now = now if now is not None else time.time()
    with _unlock_rl_lock:
        attempts = [t for t in _unlock_attempts.get(ip_hash, []) if now - t < UNLOCK_RATE_WINDOW_S]
        if len(attempts) >= UNLOCK_RATE_LIMIT:
            _unlock_attempts[ip_hash] = attempts
            return False
        attempts.append(now)
        _unlock_attempts[ip_hash] = attempts
        if len(_unlock_attempts) > _UNLOCK_RL_MAX_KEYS:
            _prune_unlock_attempts(now)
        return True


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


def _require_demo_config() -> tuple[str, str]:
    """Fail-closed guard: if COOKIE_SECRET or IP_HASH_SALT isn't configured,
    refuse with 503 rather than passing None into demo_auth's crypto
    functions or silently coercing a missing salt to "" (Task 2 review
    finding, restated by Task 4 fix-round-1: an empty-string salt is not "no
    salt" -- it produces unsalted, reversible sha256-HMAC hashes over the
    ~4B-address IPv4 space, exactly what salting exists to prevent. Never
    "simplify" this back to a `.get(..., "")` default).

    THE single gate for this module's demo-auth config -- every call site
    that touches session_secret()/ip_hash_salt() (unlock() and the gated
    "/" route below; Task 5's /answer) calls this first, so there is one
    place, not one os.environ read per call site, that decides whether the
    demo is configured to serve gated content at all."""
    cookie_secret = session_secret()
    ip_salt = ip_hash_salt()
    if not cookie_secret or not ip_salt:
        raise HTTPException(
            status_code=503,
            detail="demo gating not configured (COOKIE_SECRET/IP_HASH_SALT)",
        )
    return cookie_secret, ip_salt


def _resolve_gated_code(session: str | None) -> dict | None:
    """The `codes` row for a valid signed cookie -- None if the cookie is
    missing, malformed, expired, or points at a code that no longer exists.
    The row is returned even when `revoked_at` is set: /answer needs to tell
    "no valid session" (401) apart from "valid session, code since revoked"
    (403), matching /unlock's own 403-for-revoked convention, so the revoked
    check stays in the caller rather than collapsing both cases into None
    here."""
    secret = session_secret()
    if not secret:
        return None
    code_id = verify_session(session, secret)
    if code_id is None:
        return None
    return get_code_by_id(DEMO_DB, code_id)


_SCRYFALL_REFRESH_IDLE = {
    "status": "idle", "started_at": None, "finished_at": None,
    "result": None, "error": None,
}
_scryfall_refresh_lock = threading.Lock()
_scryfall_refresh_state: dict = dict(_SCRYFALL_REFRESH_IDLE)
# Admin refresh status (docs/plan-scryfall-local-bulk.md Sec 5 item 2, Jon's
# ruling: "background task + status poll"). A separate lock from `_lock`
# above -- this guards a completely different piece of state and there's no
# reason a slow refresh should contend with /answer's lock or vice versa.


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = VectorStore.load(REPO / "data" / "parsed" / f"vector_{VECTOR_MODEL}.pkl")
    # ruling_select on; live Scryfall (fresh rulings). effort=GEN_EFFORT pairs
    # production with the arm GEN_MODEL was actually measured at -- opus-5 at
    # the API's default effort is an unmeasured, costlier arm (see answer.py).
    agent = RulesAgent(store, effort=GEN_EFFORT)
    # chunk_map resolves a rule/glossary citation id -> its full text. The
    # agent is now its one owner (L1, docs/plan-l1-crossref-expansion.md --
    # expand_crossrefs needs the same dict), built once from the store's own
    # chunks; the API just reuses it rather than building a second copy.
    _state["chunk_map"] = agent.chunk_map
    _state["agent"] = agent
    yield
    _state.clear()


API_DESCRIPTION = """
Rulemancer answers Magic: The Gathering rules questions grounded in the
Comprehensive Rules, and enriches card questions with Scryfall oracle text and
the relevant rulings.

**How it works:** a question is rewritten into rules vocabulary, the top rules
are retrieved from the CR (pure-vector RAG), any `[Card Name]` / `[oracle-id]`
tokens are resolved via Scryfall and their rulings relevance-filtered, and a
pinned model writes a cited answer that declines rather than guesses when the
rules don't cover it (`answered=false`).

**Card references:** put a card in square brackets, e.g. `[Fork]` or
`[Grist, the Hunger Tide]`. Use `GET /cards/autocomplete` to power an @-picker.

Private demo — no auth or rate limiting. A single worker + a lock serialize
`/answer` so per-request debug state stays consistent.
"""

app = FastAPI(
    title="Rulemancer API",
    version="1.0.0",
    description=API_DESCRIPTION,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "answers", "description": "Ask a rules question, get a cited answer."},
        {"name": "cards", "description": "Scryfall-backed card name autocomplete for the @-picker."},
        {"name": "ops", "description": "Health / readiness."},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # private demo; tighten to the frontend origin if it goes public
    allow_methods=["*"],
    allow_headers=["*"],
)


class Turn(BaseModel):
    """One prior conversation turn, oldest first. Send the thread so far in
    `history` and the new question in `question` -- follow-ups and corrections
    are then read in context (and cards [bracketed] earlier stay in play)."""

    role: Literal["user", "assistant"]
    content: str


class AnswerRequest(BaseModel):
    question: str  # may contain [Card Name] / [oracle-id] tokens from the @-picker
    history: list[Turn] = []  # prior turns; server keeps the last 12, 4k chars each
    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What if the blocker is 0/3 instead?",
                "history": [
                    {"role": "user", "content": "Does trample get through deathtouch?"},
                    {"role": "assistant", "content": "Yes -- with deathtouch, any "
                     "nonzero damage counts as lethal, so 1 damage per blocker "
                     "satisfies trample's requirement..."},
                ],
            }
        }
    }


class Citation(BaseModel):
    id: str
    kind: str            # "rule" | "glossary" | "card"
    text: str | None     # resolved rule/glossary text; None for a card name


class CardOut(BaseModel):
    name: str
    oracle_id: str       # frontend fetches the card image from Scryfall with this / name
    mana_cost: str
    type_line: str
    oracle_text: str
    rulings_used: list[str]   # only the mini-RAG-selected rulings actually shown to the model


class Debug(BaseModel):
    rewrites: list[str]
    retrieved_rules: list[str]
    selected_ruling_ids: dict
    unresolved_card_refs: list[dict]  # c012 observability (plan-q029-empty-
    # answer-guard.md Plan B): every `[bracket]` ref that failed to resolve
    # this request, {"ref": ..., "reason": "not_found" | "error"} each --
    # mirrors agent.last_unresolved_refs, read the same way rewrites/
    # retrieved_rules/selected_ruling_ids already are.
    uncited_success: bool  # Plan A amendment (plan-q029-empty-answer-guard.md
    # header ruling 1): True when this answer was answered=true but cited
    # nothing -- surfaced (not retried) so an ungrounded "success" is
    # auditable. Mirrors agent.last_uncited_success.
    fuzzy_fallbacks: list[dict]  # docs/plan-scryfall-local-bulk.md Sec 4:
    # "Always flagged, never silent" -- every local fuzzy-fallback event
    # (successful match or refused ambiguous near-tie) from this request's
    # card-ref resolution, each {ref, reason, matched_name, oracle_id,
    # score, candidates}. Mirrors agent.last_fuzzy_fallbacks.


class AnswerResponse(BaseModel):
    answer: str
    tldr: str               # the frontend's default "Simple" tab
    answered: bool          # False -> the "couldn't ground it" UI state
    citations: list[Citation]
    cards: list[CardOut]
    suggested_followups: list[str]  # clickable next-question pills
    request_id: str         # join key for POST /feedback + the query log
    debug: Debug


# --- demo telemetry (plan-limitations-and-deploy.md L6/L8, migrated to     -
# --- SQLite tables by L3, docs/plan-l3-sqlite-caches.md) --------------------
# `queries` / `feedback` tables in the SAME data/cache.db the L3 KVCache
# tables live in, replacing the old queries.jsonl / feedback.jsonl append
# stubs. One row per /answer (question + answer + model + PROMPT_VERSION +
# latency) and one per feedback event, joined by request_id.

_QUERIES_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS queries ("
    "request_id TEXT PRIMARY KEY, ts TEXT, question TEXT, history_len INTEGER, "
    "cards TEXT, answered INTEGER, tldr TEXT, text TEXT, citations TEXT, "
    "suggested_followups TEXT, model TEXT, prompt_version TEXT, latency_ms INTEGER)"
)
_FEEDBACK_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS feedback ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, ts TEXT, "
    "verdict TEXT, note TEXT)"
    # request_id is NOT unique here -- a thumbs-down may arrive twice (once
    # bare, once again with the note), so feedback is append-only per request.
)


def _log_row(table: str, row: dict) -> None:
    """Best-effort INSERT into `queries` or `feedback` -- telemetry must
    never break an answer, so any failure (locked db, schema hiccup) is
    swallowed here exactly as the old JSONL append's `except OSError` did."""
    try:
        conn = sqlite3.connect(DEFAULT_DB, timeout=5.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            if table == "queries":
                conn.execute(_QUERIES_SCHEMA)
                conn.execute(
                    "INSERT OR REPLACE INTO queries (request_id, ts, question, "
                    "history_len, cards, answered, tldr, text, citations, "
                    "suggested_followups, model, prompt_version, latency_ms) "
                    "VALUES (:request_id, :ts, :question, :history_len, :cards, "
                    ":answered, :tldr, :text, :citations, :suggested_followups, "
                    ":model, :prompt_version, :latency_ms)",
                    {
                        **row,
                        "cards": json.dumps(row["cards"], ensure_ascii=False),
                        "answered": int(row["answered"]),
                        "citations": json.dumps(row["citations"], ensure_ascii=False),
                        "suggested_followups": json.dumps(
                            row["suggested_followups"], ensure_ascii=False
                        ),
                    },
                )
            else:  # "feedback"
                conn.execute(_FEEDBACK_SCHEMA)
                conn.execute(
                    "INSERT INTO feedback (request_id, ts, verdict, note) "
                    "VALUES (:request_id, :ts, :verdict, :note)",
                    row,
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("telemetry write failed: %r", e)


class FeedbackIn(BaseModel):
    request_id: str
    verdict: Literal["up", "down"]
    note: str = ""          # optional "what's wrong?" free text


@app.post("/feedback", tags=["answers"], summary="Thumbs up/down on an answer")
def feedback(fb: FeedbackIn) -> dict:
    """Visitor feedback on an answer, joined to the query log by request_id.
    A thumbs-down may arrive twice: once bare, once again with the note."""
    _log_row("feedback", {
        "request_id": fb.request_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "verdict": fb.verdict,
        "note": fb.note[:2000],
    })
    return {"ok": True}


@app.post("/unlock", tags=["answers"], summary="Unlock the demo with an access code")
def unlock(code: str = Form(...), request: Request = None):
    """Validates an access code and mints a session cookie. Fails closed
    (503) if COOKIE_SECRET/IP_HASH_SALT aren't configured -- see
    _require_demo_config. A wrong/revoked/quota-exhausted code all look
    identical from the outside (generic 403 + a `denied` event): the
    endpoint must never reveal WHY a code failed. issued_at is never taken
    from the request -- sign_session's default is the server clock, so
    there's no way for a caller to future-date a session and dodge expiry."""
    cookie_secret, ip_salt = _require_demo_config()
    ip_hash = hash_ip(_client_ip(request), ip_salt)
    if not _check_unlock_rate_limit(ip_hash):
        log_event(DEMO_DB, code_id=None, kind="denied", ip_hash=ip_hash)
        return _friendly_html(
            "Too many attempts",
            "Too many tries too fast. Wait 15 minutes and try again, or ask Jon for help.",
            status_code=429,
        )
    row = get_code_by_value(DEMO_DB, code.strip())
    if row is None or row["revoked_at"] is not None:
        log_event(DEMO_DB, code_id=None, kind="denied", ip_hash=ip_hash)
        return _friendly_html(
            "Code not recognized",
            "That access code doesn't work. Double-check it, or ask Jon for a fresh one.",
            status_code=403,
        )
    log_event(DEMO_DB, code_id=row["id"], kind="unlock", ip_hash=ip_hash)
    token = sign_session(row["id"], cookie_secret)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE_S, httponly=True,
                     samesite="lax", secure=True)
    return resp


@app.get("/health", tags=["ops"], summary="Liveness / readiness")
def health() -> dict:
    """`ready` is true once the vector store has loaded at startup."""
    return {"status": "ok", "ready": "agent" in _state}


def _record_query_event(code_row: dict, question: str, ans, agent, usage: dict,
                         latency_ms: int, request: Request, ip_salt: str) -> None:
    """Write the one `query` event for a gated call that has ALREADY reached
    and returned from the model -- real money is already spent by the time
    this runs. Fix round 1 finding 2: a failure in cost calculation, IP
    hashing, or the insert itself must never (a) silently drop the row --
    Task 7's daily budget breaker reads this table, and an under-counted
    table trips the breaker late, which is the expensive direction to fail
    in -- or (b) turn an otherwise-successful answer into a 500 for the
    caller. So every step here is independently guarded and falls back to
    the best value it still has (never a fabricated estimate -- an unknown
    cost/token figure stays None/0 and is visible as a gap, not papered
    over), and the final insert always runs with whatever was recovered."""
    input_tokens, output_tokens, cost, ip_hash = 0, 0, None, None
    try:
        input_tokens = usage.get("input_tokens") or 0
        output_tokens = usage.get("output_tokens") or 0
    except Exception as e:
        logger.warning("query event: failed reading token usage: %r", e)
    try:
        cost = cost_usd(
            agent.model, input_tokens=input_tokens, output_tokens=output_tokens,
            cache_read_tokens=usage.get("cache_read_input_tokens") or 0,
            cache_write_tokens=usage.get("cache_creation_input_tokens") or 0,
        )
    except Exception as e:
        logger.warning("query event: cost calculation failed: %r", e)
    try:
        ip_hash = hash_ip(_client_ip(request), ip_salt)
    except Exception as e:
        # Never fall back to a raw IP here -- an unknown hash stays None.
        logger.warning("query event: ip hashing failed: %r", e)
    try:
        log_event(
            DEMO_DB, code_id=code_row["id"], kind="query", ip_hash=ip_hash,
            question=question, answered=getattr(ans, "answered", None),
            input_tokens=input_tokens, output_tokens=output_tokens,
            cost_usd=cost, latency_ms=latency_ms,
        )
    except Exception as e:
        logger.warning("query event: log_event insert failed: %r", e)


def _unpriced_query_count(db_path: Path, day: str) -> int:
    """Count today's `query` events with cost_usd IS NULL -- rows where
    _record_query_event's cost-calculation step failed (docstring above:
    "an unknown cost/token figure stays None/0 and is visible as a gap, not
    papered over"). `daily_spend`'s SUM(cost_usd) *silently skips* NULL
    rows (SQL SUM ignores NULLs, and COALESCE only kicks in when there are
    zero rows at all) -- so real, already-spent money can be sitting in the
    table and never show up in the budget total.

    Fix round 1: the caller no longer trips the breaker on the mere
    *existence* of a NULL row (that made one transient cost-calc failure
    503 every visitor for the rest of the UTC day -- too much availability
    lost for what is a small, bounded amount of unknown spend). Instead the
    caller prices each NULL row at UNPRICED_QUERY_ESTIMATE_USD, a
    deliberately-high stand-in, and adds `count * estimate` to the known
    SUM(cost_usd) total -- conservative without being fatal.

    A tiny direct query, not routed through demo_db.py: daily_spend's
    signature is a committed Task-1 interface and isn't extended here.
    """
    conn = sqlite3.connect(db_path, timeout=5)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'query' AND cost_usd IS NULL "
            "AND ts LIKE ?",
            (f"{day}%",),
        ).fetchone()
    finally:
        conn.close()
    return row[0]


@app.post(
    "/answer",
    tags=["answers"],
    summary="Answer a rules question",
    description="Send a natural-language question (optionally with `[Card Name]` "
    "tokens). Returns the answer, an `answered` flag (false = the rules didn't "
    "cover it), citations with resolved rule/glossary text, the card data used "
    "with its relevance-selected rulings, and a debug panel.",
)
def answer(req: AnswerRequest, request: Request = None,
           session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> AnswerResponse:
    # `response_model=AnswerResponse` is dropped from the decorator above --
    # the guard path below returns an HTMLResponse directly, and FastAPI only
    # allows returning a Response subclass from a route when no response_model
    # is declared on *that* route. The -> AnswerResponse annotation stays for
    # docs/IDE purposes only. `request` defaults to None (like unlock()'s own
    # `request: Request = None`) so tests/test_api_debug.py's bare
    # `main.answer(req)` -- called with gating off, where request is never
    # touched -- keeps working unchanged.
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="empty question")

    code_row = None
    if _gate_enabled():
        _cookie_secret, ip_salt = _require_demo_config()
        # `session` is FastAPI-injected (a real str or None) when this route
        # runs through the app, but the test suite calls answer() directly
        # (tests/test_api_debug.py's convention) without ever passing
        # `session`, leaving it as the Cookie(...) field-info sentinel --
        # same reason _index() above reads request.cookies.get(COOKIE_NAME)
        # rather than trusting a DI-only parameter. Prefer a real injected
        # string; otherwise fall back to reading the cookie off the request
        # directly, which works identically in-app and in a direct call.
        token = session if isinstance(session, str) else (
            request.cookies.get(COOKIE_NAME) if request is not None else None
        )
        code_row = _resolve_gated_code(token)
        if code_row is None:
            ip_hash = hash_ip(_client_ip(request), ip_salt)
            log_event(DEMO_DB, code_id=None, kind="denied", ip_hash=ip_hash)
            return _friendly_html(
                "Enter your access code",
                "This demo needs an access code. Head back to the home page to enter one.",
                status_code=401,
            )
        if code_row["revoked_at"] is not None:
            ip_hash = hash_ip(_client_ip(request), ip_salt)
            log_event(DEMO_DB, code_id=code_row["id"], kind="denied", ip_hash=ip_hash)
            return _friendly_html(
                "Access code no longer valid",
                "This access code has been revoked. Ask Jon for a fresh one.",
                status_code=403,
            )
        # Task 6, fix round 1 finding 1: the cap check moved from here
        # (outside any lock) to INSIDE `_lock` below, immediately before
        # agent.answer() and with the `query` event write also inside the
        # same `with` block. Reading the count and calling the model were
        # previously two separate uncoordinated steps, so two concurrent
        # requests on the same code could both read the same pre-spend
        # count, both pass, and both call the model -- a race window as
        # wide as the model's latency (seconds), not a few instructions.
        # Folding the check + call + event-write into one critical section
        # makes them atomic with respect to each other: a second request
        # blocked on `_lock` only gets to re-check the count after the
        # first request's `query` event is already committed, so it always
        # sees the up-to-date count. This adds no new contention beyond
        # what `_lock` already serializes (the model call itself); the
        # count_queries() read and log_event() write are cheap compared to
        # the model call already inside the lock, and unrelated codes are
        # unaffected because this is the same single global `_lock` that
        # already serialized every /answer call before Task 6.

    agent, chunk_map = _state["agent"], _state["chunk_map"]
    # Bound what a thread can cost: last 12 turns, each clipped to 4k chars.
    history = [{"role": t.role, "content": t.content[:4000]} for t in req.history[-12:]]
    request_id = uuid.uuid4().hex
    t0 = time.monotonic()
    # Hold the lock across the cap check, answer() call, the reads of its
    # last_* attributes, AND the `query` event write -- see the Task 6 note
    # above for why the cap check and event write must be inside this same
    # critical section (closing the check-then-spend race), and the
    # pre-existing reason the last_* reads must stay inside it too: another
    # request could overwrite them the moment the lock is released.
    with _lock:
        if code_row is not None:
            cap = code_row["max_queries"] if code_row["max_queries"] is not None else DEFAULT_MAX_QUERIES
            if count_queries(DEMO_DB, code_row["id"]) >= cap:
                ip_hash = hash_ip(_client_ip(request), ip_salt)
                log_event(DEMO_DB, code_id=code_row["id"], kind="denied", ip_hash=ip_hash)
                return _friendly_html(
                    "This demo code is used up",
                    "You've used all your questions on this code. Ask Jon for another.",
                    status_code=402,
                )
            # Task 7: the global daily USD budget breaker. Read INSIDE the
            # same `with _lock:` critical section as the cap check and
            # `agent.answer()` call, for the identical race reason spelled
            # out in the Task 6 note above -- without the lock, two
            # concurrent requests across *any* codes could both read
            # yesterday's-fine total, both pass, and both call the model,
            # pushing spend past budget by however much the model call
            # costs. Folding it into the same critical section as the
            # per-code cap costs nothing extra: the lock is already held
            # for the model call, and this is one more cheap read before it.
            budget = float(os.environ.get("DAILY_BUDGET_USD", DAILY_BUDGET_USD_DEFAULT))
            today = datetime.now(timezone.utc).date().isoformat()
            # UTC day boundary throughout: demo_db._now() stamps every
            # event's `ts` as a UTC isoformat string (see demo_db.py), and
            # `daily_spend`/`_unpriced_query_count` both LIKE-match against
            # a UTC date string here -- write and read agree on the same
            # calendar day, so there's no local-vs-UTC skew at midnight.
            priced_spent = daily_spend(DEMO_DB, today)
            # NULL-cost rows (a cost-calculation failure in a prior
            # request) are never invisible spend here -- see
            # _unpriced_query_count's docstring. Fix round 1: each is
            # priced at UNPRICED_QUERY_ESTIMATE_USD (a deliberately-high
            # stand-in) and folded into the total, rather than tripping the
            # breaker outright on the mere presence of a gap -- one failed
            # cost calculation is bounded, known-small spend (one query),
            # not "unknown spend of unknown size", so it doesn't justify
            # halting the whole demo for the rest of the UTC day.
            unpriced_count = _unpriced_query_count(DEMO_DB, today)
            spent = priced_spent + unpriced_count * UNPRICED_QUERY_ESTIMATE_USD
            if spent >= budget:
                ip_hash = hash_ip(_client_ip(request), ip_salt)
                log_event(DEMO_DB, code_id=code_row["id"], kind="denied", ip_hash=ip_hash)
                return _friendly_html(
                    "The demo is resting for today",
                    "This demo hit its daily budget. It'll be back tomorrow -- "
                    "or ping Jon directly.",
                    status_code=503,
                )
        ans = agent.answer(req.question, history=history)
        usage_snapshot = dict(getattr(agent, "last_usage", None) or {})
        cards = list(agent.last_cards or [])
        retrieved = list(agent.last_retrieved or [])
        rewritten = agent.last_rewritten
        selection = dict(agent.last_ruling_selection or {})
        unresolved_refs = list(agent.last_unresolved_refs or [])
        uncited_success = bool(getattr(agent, "last_uncited_success", False))
        fuzzy_fallbacks = list(getattr(agent, "last_fuzzy_fallbacks", []) or [])
        latency_ms = int((time.monotonic() - t0) * 1000)
        if code_row is not None:
            # Fix round 1 finding 2 (unchanged): the model call above has
            # already cost real money, so the `query` event must get
            # written NOW, before any of the enrichment below runs --
            # citations/cards_out/debug building, cost calculation, or IP
            # hashing raising must never cost an event row (Task 7's daily
            # budget breaker reads this table; an under-counted table
            # trips it late, which is the expensive failure mode) and must
            # never turn a successful model call into a 500 for the
            # caller. _record_query_event is fully self-guarding. It now
            # also runs inside `_lock` (finding 1) so its commit is
            # visible to the next request's cap check before that request
            # can proceed past the lock.
            _record_query_event(code_row, req.question, ans, agent, usage_snapshot,
                                 latency_ms, request, ip_salt)

    # Labeled rulings shown to the model, for resolving ruling citations:
    # each card ruling string starts with its "[Name ruling #N]" label.
    ruling_by_label = {}
    for c in cards:
        for r in c.rulings:
            if r.startswith("[") and "]" in r:
                ruling_by_label[r[: r.index("]") + 1]] = r

    citations = []
    for cid in ans.citations:
        chunk = chunk_map.get(cid)
        label = cid if cid.startswith("[") else f"[{cid}]"
        if chunk is not None:
            citations.append(Citation(id=cid, kind=chunk.kind, text=chunk.text))
        elif label in ruling_by_label:
            # A ruling cited by its prompt label -- resolve the full text so
            # the drawer can show it (L8 cite-by-label).
            citations.append(Citation(id=cid, kind="ruling",
                                      text=ruling_by_label[label]))
        else:
            citations.append(Citation(id=cid, kind="card", text=None))

    cards_out = [
        CardOut(
            name=c.name, oracle_id=c.oracle_id, mana_cost=c.mana_cost,
            type_line=c.type_line, oracle_text=c.oracle_text, rulings_used=c.rulings,
        )
        for c in cards
    ]
    debug = Debug(
        rewrites=rewritten.queries if rewritten else [],
        retrieved_rules=[r.chunk.source_id for r in retrieved],
        selected_ruling_ids=selection,
        unresolved_card_refs=unresolved_refs,
        uncited_success=uncited_success,
        fuzzy_fallbacks=fuzzy_fallbacks,
    )
    _log_row("queries", {
        "request_id": request_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "question": req.question[:4000],
        "history_len": len(history),
        "cards": [c.name for c in cards],
        "answered": ans.answered,
        "tldr": ans.tldr,
        "text": ans.text,
        "citations": ans.citations,
        "suggested_followups": ans.suggested_followups,
        "model": agent.model,
        "prompt_version": PROMPT_VERSION,
        "latency_ms": latency_ms,
    })
    return AnswerResponse(
        answer=ans.text, tldr=ans.tldr, answered=ans.answered,
        suggested_followups=ans.suggested_followups, request_id=request_id,
        citations=citations, cards=cards_out, debug=debug,
    )


@app.get("/cards/autocomplete", tags=["cards"], summary="Card name autocomplete")
def autocomplete(q: str) -> dict:
    """Proxy Scryfall's autocomplete for the frontend's @-picker. Scryfall wants
    >=2 chars; below that, return `{"suggestions": []}` rather than hammer it."""
    if len(q.strip()) < 2:
        return {"suggestions": []}
    try:
        r = httpx.get(SCRYFALL_AUTOCOMPLETE, params={"q": q}, headers=SCRYFALL_HEADERS, timeout=10.0)
        if r.status_code != 200:
            return {"suggestions": []}
        return {"suggestions": r.json().get("data", [])}
    except httpx.HTTPError:
        return {"suggestions": []}


# --- Scryfall local-bulk admin (docs/plan-scryfall-local-bulk.md Sec 5     -
# --- item 2, Jon's ruling: background task + status poll, ADMIN_TOKEN      -
# --- env-var pattern) -------------------------------------------------------


class AdminRefreshResponse(BaseModel):
    status: str  # "started" | "already_running"


class AdminStatusResponse(BaseModel):
    status: str  # "idle" | "running" | "success" | "failed"
    started_at: str | None
    finished_at: str | None
    result: dict | None
    error: str | None


def _require_admin_token(authorization: str | None) -> None:
    """Bearer-token gate, matching the existing os.environ.get(...) key
    pattern (openrouter_backend.py's OPENROUTER_API_KEY). Fails CLOSED: if
    ADMIN_TOKEN isn't configured at all, every request is refused (503) --
    never silently wide open. A configured token that doesn't match, or a
    missing/malformed header, is a 401."""
    token = os.environ.get("ADMIN_TOKEN")
    if not token:
        raise HTTPException(status_code=503, detail="admin endpoint not configured (no ADMIN_TOKEN)")
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="missing or invalid admin token")


def _run_scryfall_refresh() -> None:
    """The background task body -- calls the SAME shared import function the
    CLI (scripts/refresh_scryfall_bulk.py __main__) and the calendar trigger
    use, not a duplicated code path."""
    with _scryfall_refresh_lock:
        _scryfall_refresh_state.update({
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None, "result": None, "error": None,
        })
    try:
        summary = refresh_scryfall_bulk.refresh()
    except Exception as e:
        logger.warning("scryfall admin refresh failed: %r", e)
        with _scryfall_refresh_lock:
            _scryfall_refresh_state.update({
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            })
        return
    with _scryfall_refresh_lock:
        _scryfall_refresh_state.update({
            "status": "success",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "result": summary,
        })


@app.post(
    "/admin/scryfall/refresh", tags=["ops"], summary="Trigger a Scryfall bulk-data refresh",
    description="Token-protected (Authorization: Bearer <ADMIN_TOKEN>). Kicks off a real "
    "download+rebuild+atomic-swap in the background and returns immediately -- poll "
    "GET /admin/scryfall/status for the result. A no-op (no second background task) "
    "if a refresh is already running.",
)
def admin_scryfall_refresh(
    background_tasks: BackgroundTasks, authorization: str | None = Header(default=None),
) -> AdminRefreshResponse:
    _require_admin_token(authorization)
    with _scryfall_refresh_lock:
        if _scryfall_refresh_state["status"] == "running":
            return AdminRefreshResponse(status="already_running")
    background_tasks.add_task(_run_scryfall_refresh)
    return AdminRefreshResponse(status="started")


@app.get(
    "/admin/scryfall/status", tags=["ops"], summary="Poll the last/current Scryfall refresh",
    description="Token-protected (Authorization: Bearer <ADMIN_TOKEN>).",
)
def admin_scryfall_status(authorization: str | None = Header(default=None)) -> AdminStatusResponse:
    _require_admin_token(authorization)
    with _scryfall_refresh_lock:
        state = dict(_scryfall_refresh_state)
    return AdminStatusResponse(**state)


# Serve the frontend from the same process (mounted LAST so the API routes and
# /docs win the match first). One `uv run python run.py` then serves everything;
# the guard keeps the bare API working if frontend/ is ever absent.
_frontend_dir = REPO / "frontend"
if _frontend_dir.is_dir():
    # index.html is the cache-busting entry point (docs/plan-cache-busting.md):
    # it always REVALIDATES (no-cache != no-store -- the browser keeps a copy
    # but must check freshness first), so a plain refresh picks up upgrades.
    # Everything index.html references carries a ?v= it controls, so assets
    # stay cache-friendly while never going stale. Registered before the
    # mount, so these explicit routes win the "/" match.
    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    def _index(request: Request) -> FileResponse:
        # Task 4 fix-round-1: was a bare os.environ["COOKIE_SECRET"], which
        # KeyErrors (surfaces as an unhandled 500) the moment COOKIE_SECRET
        # is set but IP_HASH_SALT isn't -- a real, reachable misconfiguration,
        # not just a hypothetical. _require_demo_config() is now the single
        # gate for this module's demo-auth crypto, called on every path that
        # touches it, this one included -- so a partial config (one var set,
        # the other missing) refuses closed (503) here too, not just in
        # /unlock.
        if _gate_enabled():
            cookie_secret, _ip_salt = _require_demo_config()
            session = request.cookies.get(COOKIE_NAME)
            code_id = verify_session(session, cookie_secret)
            if code_id is None:
                return FileResponse(_frontend_dir / "gate.html", headers={"Cache-Control": "no-cache"})
        return FileResponse(_frontend_dir / "index.html",
                            headers={"Cache-Control": "no-cache"})

    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
