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

import hashlib
import hmac
import html as _html
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
from types import SimpleNamespace
from typing import Literal

import httpx
from fastapi import BackgroundTasks, Cookie, FastAPI, Form, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.responses import JSONResponse as _JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rulesagent.cache import DEFAULT_DB, KVCache
from rulesagent.demo_auth import (
    COOKIE_MAX_AGE_S, hash_ip, ip_hash_salt, session_secret, sign_session, verify_session,
)
from rulesagent.demo_db import (
    DEFAULT_DEMO_DB, code_stats, count_queries, create_code, daily_spend, events_for_code,
    generate_code, get_code_by_id, get_code_by_value, list_codes, log_event, revoke_code,
)
from rulesagent.generate.answer import GEN_EFFORT, PROMPT_VERSION, RulesAgent
from rulesagent.index.store import VectorStore
from rulesagent.pricing import cost_usd

logger = logging.getLogger(__name__)


class JSONResponse(_JSONResponse):
    """`application/json` with an EXPLICIT charset (plan-answer-ui-fixes Fix 2).

    Root-cause note on the em-dash bug this exists to close: every layer
    upstream of the HTTP response was audited and found clean --
    `data/parsed/vector_voyage-4-large.pkl` has 93 chunks with a proper
    U+2014 and zero mojibake, `parser.py` reads the CR with
    `encoding="utf-8-sig"`, Starlette's stock `JSONResponse.render()` already
    calls `json.dumps(..., ensure_ascii=False)` and encodes UTF-8, and a scan
    of 1,335 real production rows in `data/cache.db`'s `queries` table (the
    literal text every /answer response actually sent) found ZERO rows
    containing an escaped-unicode or mojibake pattern. No layer this project
    controls corrupts the character. The one real gap: Starlette only
    auto-appends `; charset=utf-8` to `text/*` media types (see
    `starlette.responses.Response.init_headers`) -- `application/json`
    responses ship with NO charset parameter at all, relying on every
    downstream reader to know "JSON is always UTF-8" per RFC 8259. That is
    normally safe, but this app sits behind a proxy (fly.dev) that a plain
    client doesn't, so an explicit charset costs nothing and removes the one
    channel that was still ambiguous. Shadows the stdlib import so every
    existing `JSONResponse(...)` call site in this module (error pages,
    `/unlock`, `/feedback`, `/answer` via `default_response_class` below)
    gets it for free, with no per-call-site changes."""

    media_type = "application/json; charset=utf-8"


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

MEASURED_MEAN_COST_PER_QUERY_USD = 0.0485
# Task 12's real-pipeline measurement (mean $/query). This is an ESTIMATE for
# budget-planning display on the mint form, not a guarantee -- individual
# queries vary (Task 12 also measured a max of MEASURED_MAX_COST_PER_QUERY_USD
# below). Never used to enforce anything; the daily breaker enforces off
# actual cost_usd.
MEASURED_MAX_COST_PER_QUERY_USD = 0.0648
# Task 12's real-pipeline measurement (max $/query seen). Informs
# MAX_QUERIES_CEILING's rationale below, not itself enforced.

MAX_QUERIES_CEILING = 500
# At $0.0485/query (measured mean), a fat-fingered 2500 instead of 250 is
# roughly $121 of exposure on a single code. The daily budget breaker would
# eventually stop it, but only by taking the WHOLE demo offline for the rest
# of the UTC day -- a bad way to discover a typo. 500 queries is about $24 at
# the measured mean, a defensible ceiling for a single demo code; mint a
# second code if more capacity is genuinely needed.

MAX_QUESTION_CHARS = 2000
# All three existing spend guards (per-code query cap, daily USD budget
# breaker, unlock rate limit) bound the NUMBER of queries -- none bounds the
# SIZE of one, and input tokens scale with what a visitor pastes in. Measured
# every question across the full 1,409-question RulesGuru corpus
# (evals/rulesguru_full.jsonl) plus the other question sets: median 172
# chars, p99 395, longest of all 1,409 was 1,013. Doubled and rounded up
# (1,013 * 2 = 2,026 -> 2,000), so no genuine rules question can ever hit
# this -- it only catches someone pasting a wall of text at the publicly
# reachable /answer endpoint. Enforced server-side (the real guard, checked
# before any model call); the frontend's `maxlength` is a courtesy only,
# trivially bypassed by posting to /answer directly.

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
    contrast, no raw error, never a 500 for an expected condition.

    Consumes the same design tokens as frontend/gate.html and
    admin_login_page (colors_and_type.css's plum palette), not the
    hardcoded greys (#14161a/#e8e8ea) this used to ship -- those made a
    429/403/503 page look like a different, off-brand product next to the
    plum gate. tests/test_design_tokens_no_drift.py guards frontend/index.html
    against redefining --plum-*/--accent inline; this stays consistent with
    that rule by consuming the tokens via the stylesheet link rather than
    redeclaring them here. title/message are always static, developer-
    authored strings (never user input) but are still escaped -- cheap
    insurance against a future call site changing that."""
    safe_title = _html.escape(title)
    safe_message = _html.escape(message)
    html = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title} — Rulemancer</title>
<link rel="stylesheet" href="/colors_and_type.css?v=3">
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; height: 100%; }}
  body {{ background: var(--bg-page); color: var(--fg-primary); font-family: var(--font-sans);
          display: flex; align-items: center; justify-content: center;
          min-height: 100vh; padding: var(--space-5); }}
  .card {{ max-width: 480px; text-align: center; background: var(--bg-card);
           border: 1px solid var(--border-default); border-radius: var(--radius-lg);
           box-shadow: var(--shadow-lg); padding: var(--space-6) var(--space-5); }}
  h1 {{ font-size: var(--fs-xl); margin: 0 0 var(--space-3); color: var(--fg-primary); }}
  p {{ color: var(--fg-secondary); line-height: var(--lh-base); margin: 0; }}
</style></head>
<body data-surface="dark"><div class="card"><h1>{safe_title}</h1><p>{safe_message}</p></div></body></html>"""
    return HTMLResponse(content=html, status_code=status_code)


def _unlock_wants_json(request: Request | None) -> bool:
    """Content negotiation for /unlock ONLY -- a narrower, opt-in-to-JSON
    version of _wants_json_error's path-based fallback (defined later in
    this file; that one is used by the catch-all exception handler across
    every route and must not change here).

    The bug this exists to fix: gate.html's form had no method/action, so
    the WHOLE unlock flow depended on an inline script running successfully.
    Any script failure (extension, CSP, old browser, JS disabled) left the
    button doing nothing with zero feedback. The fix is a real
    method="post" action="/unlock" form -- a native browser submit must
    always land the visitor on the app (redirect) or a readable error page,
    never raw JSON. So JSON is opt-in here, not the default:

    - Accept: application/json  -> JSON (explicit fetch/XHR signal)
    - X-Requested-With: XMLHttpRequest -> JSON (gate.html's fetch() sets
      this itself, rather than relying on a browser's default fetch Accept
      of '*/*', which is ambiguous and shouldn't decide this)
    - anything else, including no request object at all (direct/script
      callers) or a plain browser POST (Accept: text/html,...) -> HTML/303,
      the safe default for an unknown caller.
    """
    if request is None:
        return False
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return True
    if request.headers.get("x-requested-with", "").lower() == "xmlhttprequest":
        return True
    return False


def _unlock_failure_response(
    wants_json: bool, title: str, message: str, status_code: int
) -> HTMLResponse | JSONResponse:
    """Shared failure rendering for /unlock's three failure paths (429 rate
    limit, 403 bad/revoked code -- and anything a future guard adds), so a
    browser POST always gets the friendly styled page and a fetch/XHR caller
    always gets JSON it can parse, with the exact same status code either
    way. Never a raw exception, never unstyled JSON shown to a human."""
    if wants_json:
        return JSONResponse({"ok": False, "detail": message}, status_code=status_code)
    return _friendly_html(title, message, status_code=status_code)


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
    # Fly deploys mount an EMPTY volume on first boot -- the vector pickle is
    # seeded onto it manually after the machine is up (task-14-brief.md Step
    # 4), so the file legitimately does not exist yet the first time this
    # runs. A missing or unreadable store must NOT crash-loop the process:
    # there'd be no running machine left to `fly ssh console` into to seed
    # it -- chicken and egg. So this catches load failure, logs it, and
    # leaves the app serving with _state empty; `agent`/`chunk_map` simply
    # never get set, and /health + every route that needs them (see
    # _require_agent below) treat that as "still starting up", not a 500.
    try:
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
    except Exception:
        logger.exception(
            "vector store failed to load at startup -- serving unready "
            "(agent not in _state) instead of crash-looping; seed the "
            "volume and restart the machine"
        )
    yield
    _state.clear()


def _require_agent() -> RulesAgent:
    """Every route that touches the agent/chunk_map goes through this
    instead of reading `_state["agent"]` directly, so a not-yet-seeded
    deploy (see lifespan above) answers with a clear, friendly 503 instead
    of an unhandled KeyError -- same shape as _require_demo_config's fail
    -closed pattern elsewhere in this module."""
    agent = _state.get("agent")
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Still starting up -- the rules data isn't loaded yet. Try again shortly.",
        )
    return agent


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
    default_response_class=JSONResponse,  # explicit charset -- see class docstring
    openapi_tags=[
        {"name": "answers", "description": "Ask a rules question, get a cited answer."},
        {"name": "cards", "description": "Scryfall-backed card name autocomplete for the @-picker."},
        {"name": "ops", "description": "Health / readiness."},
    ],
)
def _cors_allow_origins() -> list[str]:
    """Wildcard by default (private local demo, unchanged). Locked to one
    origin once DEMO_ORIGIN is set -- the Fly deployment sets it to its own
    https URL, so no other site can call /answer cross-origin using a
    stolen or guessed cookie."""
    origin = os.environ.get("DEMO_ORIGIN")
    return [origin] if origin else ["*"]


# Fix-round-1 finding: allow_credentials must NEVER be True while origins are
# wildcarded. Starlette's CORSMiddleware does not send a bare "*" when
# credentials are allowed -- per starlette/middleware/cors.py, if
# allow_all_origins and allow_credentials are both true it reflects the
# caller's own Origin header back verbatim instead
# (`self.allow_explicit_origin(headers, origin)`), paired with
# Access-Control-Allow-Credentials: true. That means literally any origin on
# the internet could make cookie-bearing cross-origin requests -- strictly
# worse than the pre-Task-9 bare "*" (no credentials flag at all). Credentials
# are only safe to allow once origins are locked down to the single
# DEMO_ORIGIN value, so the two settings are derived from the same condition
# and must stay coupled. Do not re-simplify this back to an unconditional True.
_cors_origins = _cors_allow_origins()
_cors_locked = _cors_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=_cors_locked,  # only once origins are locked to DEMO_ORIGIN -- see comment above
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


class CardFaceOut(BaseModel):
    """One printed face, for the card-info panel (plan-answer-ui-fixes Fix 3).

    Mirrors contracts.CardFace, which the pipeline already fetches from
    Scryfall per face -- this is purely a frontend-facing re-export of data
    that was already in memory, not a new fetch."""

    name: str
    mana_cost: str
    type_line: str
    oracle_text: str
    power: str
    toughness: str
    loyalty: str
    defense: str


class CardOut(BaseModel):
    name: str
    oracle_id: str       # frontend fetches the card image from Scryfall with this / name
    mana_cost: str
    type_line: str
    oracle_text: str
    rulings_used: list[str]   # only the mini-RAG-selected rulings actually shown to the model
    layout: str = ""      # Scryfall layout ("normal", "modal_dfc", "transform", ...) --
    # the frontend uses this to decide how to present multiple faces (e.g. a
    # modal DFC's two faces are alternatives; a transform card's back is what
    # the front becomes). See contracts.Card.layout for the full rationale.
    power: str = ""        # top-level convenience for a single-faced card;
    toughness: str = ""    # blank when the card has more than one face --
    loyalty: str = ""      # read per-face from `faces` instead, since a
    defense: str = ""      # double-faced card's two faces can differ.
    faces: list[CardFaceOut] = []   # one entry per printed face (always >=1);
    # the source of truth for multi-faced cards. Single-faced cards also get
    # exactly one entry here, so the frontend can iterate `faces` uniformly.


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
    there's no way for a caller to future-date a session and dodge expiry.

    Content-negotiates via _unlock_wants_json (see there for the "why"): a
    plain browser form POST gets a 303 to "/" on success and the friendly
    styled page on failure -- it must work with JavaScript disabled or
    broken, since that's the actual front door of the demo. gate.html's own
    fetch() call marks itself explicitly (Accept: application/json +
    X-Requested-With: XMLHttpRequest) and keeps getting JSON either way, so
    the no-full-navigation enhancement still works when JS runs fine. Status
    codes (200/303/403/429/503) are unchanged by which branch renders them."""
    cookie_secret, ip_salt = _require_demo_config()
    ip_hash = hash_ip(_client_ip(request), ip_salt)
    wants_json = _unlock_wants_json(request)
    if not _check_unlock_rate_limit(ip_hash):
        log_event(DEMO_DB, code_id=None, kind="denied", ip_hash=ip_hash)
        return _unlock_failure_response(
            wants_json,
            "Too many attempts",
            "Too many tries too fast. Wait 15 minutes and try again, or ask Jon for help.",
            status_code=429,
        )
    row = get_code_by_value(DEMO_DB, code.strip())
    if row is None or row["revoked_at"] is not None:
        log_event(DEMO_DB, code_id=None, kind="denied", ip_hash=ip_hash)
        return _unlock_failure_response(
            wants_json,
            "Code not recognized",
            "That access code doesn't work. Double-check it, or ask Jon for a fresh one.",
            status_code=403,
        )
    log_event(DEMO_DB, code_id=row["id"], kind="unlock", ip_hash=ip_hash)
    token = sign_session(row["id"], cookie_secret)
    if wants_json:
        resp = JSONResponse({"ok": True})
    else:
        # Native form submit: land the visitor on the app, never show them
        # raw JSON. 303 (not 302) so a refresh of "/" re-GETs instead of
        # re-POSTing the code.
        resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE_S, httponly=True,
                     samesite="lax", secure=True)
    return resp


@app.get("/health", tags=["ops"], summary="Liveness / readiness")
def health() -> dict:
    """`ready` is true once the vector store has loaded at startup. Stays
    "status": "ok" even when not ready -- the process is alive and serving,
    it just hasn't finished loading the store (or, on a fresh Fly volume
    before Step 4's seeding, the store file doesn't exist yet)."""
    return {"status": "ok", "ready": "agent" in _state}


# --- warmed-example cache (docs/.superpowers/sdd/2026-07-27-gated-demo/
# task-caching-report.md, Change 1) ------------------------------------------
# The frontend's four clickable example questions (frontend/index.html's
# EXAMPLES) get clicked more than anything else on the demo, are identical
# every time, and each currently costs a full opus-5 generation -- the
# measured $/query is ~$0.0485 and essentially all of it is this call. Serve
# a pre-warmed answer on a first turn instead of regenerating it.
#
# Lives in the same data/cache.db as every other L3 cache (rulesagent.cache
# .KVCache), a separate table so it never collides with ruling_emb/rewrite
# keys. Module-level so tests can monkeypatch.setattr(main, "_example_cache",
# KVCache(..., db_path=tmp_path)) the same way tests/test_ruling_retrieval.py
# already does for its own module-level _cache.
_example_cache = KVCache("example_answer_cache")


def _normalize_question(question: str) -> str:
    """Lowercased, whitespace-collapsed question text -- the cache key's
    notion of "the same question," independent of a visitor retyping an
    example with different casing or incidental whitespace."""
    return " ".join(question.strip().lower().split())


def _corpus_fingerprint(store) -> str:
    """Sha256 over the embedding model name plus every chunk's source_id
    (sorted, so the store's own list order never matters) -- an identity for
    "this build of the index." Follows the repo's existing config-stamp
    pattern rather than inventing a new one: evals/progress.py's
    prompts_cache_sha256() hashes a cache's actual content (sort_keys=True
    JSON) instead of trusting an author-declared version field that can go
    stale. Changes whenever the corpus is rebuilt with a different rule set
    or a different embedding model -- either would change what a fresh
    answer looks like, so either must invalidate a cached one."""
    ids = sorted(c.source_id for c in getattr(store, "chunks", []))
    canonical = json.dumps({"model": getattr(store, "model", None), "ids": ids},
                            sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _example_cache_key(question: str, agent) -> str | None:
    """Cache key for the warmed-example lookup, or None to mean "don't even
    try the cache." None is returned when `agent` is a test double missing
    `.store` (e.g. tests/test_api_debug.py's _FakeAgent) -- those existing
    tests must keep behaving exactly as before this feature existed, not
    crash on a missing attribute or silently cache under an incomplete
    identity.

    Folds in everything that changes the answer: normalized question text,
    generator model + effort, system-prompt version, rewrite version, and the
    corpus/index identity. Miss any one of these and a stale answer could
    survive a model/prompt/corpus change -- exactly the honesty trap this
    cache exists to avoid (a demo visitor seeing an answer the CURRENT
    pipeline would not produce)."""
    store = getattr(agent, "store", None)
    if store is None:
        return None
    config = {
        "q": _normalize_question(question),
        "model": getattr(agent, "model", None),
        "effort": getattr(agent, "effort", None),
        "system_version": getattr(agent, "system_version", None),
        "rewrite_version": getattr(agent, "rewrite_version", None),
        "corpus_fingerprint": _corpus_fingerprint(store),
    }
    canonical = json.dumps(config, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _lookup_example_cache(question: str, agent) -> dict | None:
    """The stored payload for `question` under the CURRENT config, or None on
    a miss (including "couldn't build a key" and "cached JSON was
    corrupt")."""
    key = _example_cache_key(question, agent)
    if key is None:
        return None
    raw = _example_cache.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _store_example_cache(question: str, agent, payload: dict) -> None:
    """Write `payload` (see _response_to_cache_payload) under the current
    config's key. Used only by the manual warming script
    (scripts/warm_examples.py) -- never called from a request path."""
    key = _example_cache_key(question, agent)
    if key is None:
        return
    _example_cache.put(key, json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _response_to_cache_payload(resp: "AnswerResponse", agent) -> dict:
    """The storable shape for a live AnswerResponse -- everything the
    /answer route needs to reconstruct one on a cache hit, minus
    `request_id` (a fresh id is minted per hit, cached or not)."""
    return {
        "answer": resp.answer,
        "tldr": resp.tldr,
        "answered": resp.answered,
        "citations": [c.model_dump(mode="json") for c in resp.citations],
        "cards": [c.model_dump(mode="json") for c in resp.cards],
        "suggested_followups": resp.suggested_followups,
        "debug": resp.debug.model_dump(mode="json"),
        "model": agent.model,
        "prompt_version": PROMPT_VERSION,
    }


def _record_query_event(code_row: dict, question: str, ans, agent, usage: dict,
                         latency_ms: int, request: Request, ip_salt: str,
                         cached: bool = False) -> None:
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
    over), and the final insert always runs with whatever was recovered.

    `cached=True` (a warmed-example hit -- see the cache section above): no
    model call was made, so there is no usage to price. cost is set
    EXPLICITLY to 0.0, never left at the None/NULL default -- NULL means
    "unpriced" to _unpriced_query_count/_todays_spend below, which price
    every NULL row at UNPRICED_QUERY_ESTIMATE_USD ($0.15) as a deliberately
    high stand-in. A free hit recorded as NULL would look like the most
    expensive query of the day instead of the cheapest."""
    input_tokens, output_tokens, cost, ip_hash = 0, 0, None, None
    if cached:
        cost = 0.0
    else:
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


def _todays_spend(db_path: Path, day: str) -> float:
    """Single source of truth for "how much has today cost so far": priced
    SUM(cost_usd) plus each NULL-cost row priced at UNPRICED_QUERY_ESTIMATE_USD
    -- see _unpriced_query_count's docstring for why a bare daily_spend() call
    alone silently drops unpriced rows. Both the /answer budget breaker
    (Task 7) and the /admin usage view (Task 11) call THIS function instead
    of re-deriving the sum themselves, so the number that trips the breaker
    and the number shown to Jon can never drift apart.
    """
    priced = daily_spend(db_path, day)
    unpriced = _unpriced_query_count(db_path, day)
    return priced + unpriced * UNPRICED_QUERY_ESTIMATE_USD


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

    agent = _require_agent()
    chunk_map = _state["chunk_map"]
    # Bound what a thread can cost: last 12 turns, each clipped to 4k chars.
    history = [{"role": t.role, "content": t.content[:4000]} for t in req.history[-12:]]
    request_id = uuid.uuid4().hex
    t0 = time.monotonic()
    # Warmed-example cache lookup (see the section above _record_query_event)
    # -- ONLY on a first turn (history empty). A follow-up's answer depends
    # on the transcript, so a cache keyed on question text alone would return
    # an answer to the wrong question for any history-bearing request. This
    # is a plain lookup, not inside `_lock`: it touches no shared counters,
    # only KVCache's own per-op SQLite connection.
    cached_payload = None if history else _lookup_example_cache(req.question, agent)
    # Hold the lock across the cap check, answer() call, the reads of its
    # last_* attributes, AND the `query` event write -- see the Task 6 note
    # above for why the cap check and event write must be inside this same
    # critical section (closing the check-then-spend race), and the
    # pre-existing reason the last_* reads must stay inside it too: another
    # request could overwrite them the moment the lock is released.
    with _lock:
        # Input-length guard: the three checks below (cap, budget, and this
        # one) all sit inside the same critical section and all run before
        # agent.answer() -- the cap/budget guards bound how many queries a
        # code can spend, this one bounds how much a SINGLE query can cost by
        # rejecting an oversized question before it ever reaches the model.
        # Applies whether or not the demo is gated (code_row may be None):
        # an ungated deployment's /answer is just as publicly reachable and
        # just as billable per character sent. See MAX_QUESTION_CHARS'
        # comment for the 2,000-char derivation.
        if len(req.question.strip()) > MAX_QUESTION_CHARS:
            if code_row is not None:
                ip_hash = hash_ip(_client_ip(request), ip_salt)
                # Never store the full oversized text -- the point of this
                # guard is to avoid handling it. 200 chars is enough to spot
                # the pattern (paste vs. typo) in the admin panel.
                log_event(
                    DEMO_DB, code_id=code_row["id"], kind="denied", ip_hash=ip_hash,
                    question=req.question.strip()[:200] + " …[truncated, over length limit]",
                )
            return _question_too_long_response(request)
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
            # NULL-cost rows (a cost-calculation failure in a prior
            # request) are never invisible spend here -- see
            # _unpriced_query_count's docstring. Fix round 1: each is
            # priced at UNPRICED_QUERY_ESTIMATE_USD (a deliberately-high
            # stand-in) and folded into the total, rather than tripping the
            # breaker outright on the mere presence of a gap -- one failed
            # cost calculation is bounded, known-small spend (one query),
            # not "unknown spend of unknown size", so it doesn't justify
            # halting the whole demo for the rest of the UTC day.
            # _todays_spend is the SAME function /admin uses -- see its
            # docstring for why that sharing matters.
            spent = _todays_spend(DEMO_DB, today)
            if spent >= budget:
                ip_hash = hash_ip(_client_ip(request), ip_salt)
                log_event(DEMO_DB, code_id=code_row["id"], kind="denied", ip_hash=ip_hash)
                return _friendly_html(
                    "The demo is resting for today",
                    "This demo hit its daily budget. It'll be back tomorrow -- "
                    "or ping Jon directly.",
                    status_code=503,
                )
        if cached_payload is not None:
            # Warmed-example hit: no model call, so this is where the two
            # code paths diverge. The cap/budget/length guards above already
            # ran unchanged -- a cached hit still counts toward the code's
            # query cap, it just costs $0.00 instead of ~$0.0485. See
            # _record_query_event's `cached=True` docstring for why cost is
            # explicit 0.0, never left NULL.
            latency_ms = int((time.monotonic() - t0) * 1000)
            if code_row is not None:
                _record_query_event(
                    code_row, req.question,
                    SimpleNamespace(answered=cached_payload["answered"]),
                    agent, {}, latency_ms, request, ip_salt, cached=True,
                )
            _log_row("queries", {
                "request_id": request_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "question": req.question[:4000],
                "history_len": 0,
                "cards": [c["name"] for c in cached_payload["cards"]],
                "answered": cached_payload["answered"],
                "tldr": cached_payload["tldr"],
                "text": cached_payload["answer"],
                "citations": [c["id"] for c in cached_payload["citations"]],
                "suggested_followups": cached_payload["suggested_followups"],
                "model": cached_payload.get("model", agent.model),
                "prompt_version": cached_payload.get("prompt_version", PROMPT_VERSION),
                "latency_ms": latency_ms,
            })
            return AnswerResponse(
                answer=cached_payload["answer"], tldr=cached_payload["tldr"],
                answered=cached_payload["answered"],
                suggested_followups=cached_payload["suggested_followups"],
                request_id=request_id,
                citations=[Citation(**c) for c in cached_payload["citations"]],
                cards=[CardOut(**c) for c in cached_payload["cards"]],
                debug=Debug(**cached_payload["debug"]),
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
            layout=c.layout,
            # Top-level power/toughness/loyalty/defense are a convenience for
            # the common single-faced case only -- populated when there's
            # exactly one face, blank otherwise (the two faces of a DFC can
            # have different stats, so `faces` below is the real source of
            # truth the frontend must read for anything multi-faced).
            power=c.faces[0].power if len(c.faces) == 1 else "",
            toughness=c.faces[0].toughness if len(c.faces) == 1 else "",
            loyalty=c.faces[0].loyalty if len(c.faces) == 1 else "",
            defense=c.faces[0].defense if len(c.faces) == 1 else "",
            faces=[
                CardFaceOut(
                    name=f.name, mana_cost=f.mana_cost, type_line=f.type_line,
                    oracle_text=f.oracle_text, power=f.power, toughness=f.toughness,
                    loyalty=f.loyalty, defense=f.defense,
                )
                for f in c.faces
            ],
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


# --- Browser login for /admin (.superpowers/sdd/2026-07-27-gated-demo/
# task-admin-login-report.md). _require_admin_token below only reads an
# Authorization: Bearer header -- a browser can't send a custom header from
# the address bar, so GET /admin was unreachable except via curl/scripts.
# This adds a signed admin session COOKIE as a second way in, alongside the
# bearer header (which keeps working unchanged for scripts and the Scryfall
# refresh/status endpoints below).

ADMIN_COOKIE_NAME = "rulemancer_admin_session"
# Deliberately a different NAME than COOKIE_NAME ("rulemancer_demo") -- a
# demo visitor's cookie and an admin session cookie must never be
# interchangeable, and giving them different names is half of that (a
# visitor's cookie is never even looked up under this name).
ADMIN_COOKIE_MAX_AGE_S = 4 * 3600  # 4 hours -- short-lived; login again after.
ADMIN_SESSION_MARKER = 0
# The other half of "never interchangeable": this reuses demo_auth's
# sign_session/verify_session machinery (same HMAC, same COOKIE_SECRET)
# rather than inventing a second signing scheme, but signs the sentinel
# "code id" 0 instead of a real code row id. demo_db.create_code inserts
# into a SQLite INTEGER PRIMARY KEY AUTOINCREMENT column, whose rowids start
# at 1 and are never reused or 0 -- so no real demo code can ever sign as
# marker 0, and a genuine visitor session cookie (which signs their real,
# positive code_id) can never verify as an admin session. Symmetrically, if
# an admin cookie ever ended up read as a demo session, verify_session would
# hand back code_id=0, and get_code_by_id(DEMO_DB, 0) returns None (row 0
# doesn't exist) -- same as no session at all, not a privilege leak.


def _admin_bearer_ok(authorization: str | None) -> bool:
    """The existing Bearer-token check as a boolean instead of a raise, so
    /admin can fall through to the login form on failure instead of a bare
    401 JSON error. Identical comparison to _require_admin_token (same
    constant-time hmac.compare_digest) -- this does not change what counts
    as a valid bearer header, only what happens when it's missing/wrong."""
    token = os.environ.get("ADMIN_TOKEN")
    if not token or not isinstance(authorization, str):
        return False
    return hmac.compare_digest(authorization, f"Bearer {token}")


def _verify_admin_session(token: str | None, secret: str) -> bool:
    code_id = verify_session(token, secret, max_age_s=ADMIN_COOKIE_MAX_AGE_S)
    return code_id == ADMIN_SESSION_MARKER


def _admin_authed(authorization: str | None, admin_session: str | None) -> bool:
    """The exact same either-Bearer-or-cookie check admin_demo_view already
    does, factored out so the mint/revoke POST routes below gate identically
    -- one auth decision, not a second copy that could drift out of sync.
    A demo visitor's own signed session cookie fails this the same way it
    fails admin_demo_view (test_demo_visitor_session_cookie_does_not_grant_admin):
    it verifies fine as a *visitor* session but never as ADMIN_SESSION_MARKER."""
    if _admin_bearer_ok(authorization):
        return True
    secret = session_secret()
    cookie_val = admin_session if isinstance(admin_session, str) else None
    return bool(secret and _verify_admin_session(cookie_val, secret))


def _validate_label(label: str) -> str | None:
    """Same rule scripts/codes.py's _cmd_new already applies: non-empty
    after stripping. Returns an error message, or None if valid."""
    if not label or not label.strip():
        return "Label can't be empty -- Jon needs to know who holds this code."
    return None


def _validate_max_queries(raw: str) -> tuple[int | None, str | None]:
    """Parses and validates the query cap from the mint form. Returns
    (value, error) -- exactly one is None. Rejects non-integers (including
    things like "25.5" that Python's int() would also reject), zero,
    negatives, and anything over MAX_QUERIES_CEILING (see that constant's
    comment for why the ceiling exists). Deliberately NOT `max_queries: int
    = Form(...)` on the route -- FastAPI's own int-coercion 422 is a bare
    JSON error, not the friendly re-rendered form with a clear message this
    needs."""
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None, "Max queries must be a whole number."
    if value <= 0:
        return None, "Max queries must be greater than zero."
    if value > MAX_QUERIES_CEILING:
        est = MAX_QUERIES_CEILING * MEASURED_MEAN_COST_PER_QUERY_USD
        return None, (
            f"Max queries can't exceed {MAX_QUERIES_CEILING} (about ${est:.2f} "
            "at the measured mean cost per query). Mint a second code if you "
            "need more capacity."
        )
    return value, None


def _require_admin_login_config() -> tuple[str, str]:
    """Fail-closed guard for POST /admin/login, same shape as
    _require_admin_token / _require_demo_config: refuse with 503 rather than
    checking a token against nothing or signing a cookie with a missing
    secret. Both ADMIN_TOKEN (what's being checked) and COOKIE_SECRET (what
    signs the resulting cookie) must be configured -- never fall back to an
    unsigned cookie."""
    token = os.environ.get("ADMIN_TOKEN")
    secret = session_secret()
    if not token or not secret:
        raise HTTPException(
            status_code=503,
            detail="admin login not configured (ADMIN_TOKEN/COOKIE_SECRET)",
        )
    return token, secret


def _admin_login_page(error: bool = False, status_code: int = 401) -> HTMLResponse:
    """The browser-facing login form -- rendered whenever a request has
    neither a valid Bearer header nor a valid admin session cookie, and
    re-rendered (with a generic error) after a wrong token. Same dark,
    token-styled surface as admin_demo_view's dashboard and
    frontend/gate.html's visitor gate (same colors_and_type.css tokens) --
    the whole point is that this is reachable and readable from a plain
    browser visit, not a JSON error. Never includes any code, label,
    question, or count -- that data only exists past a successful login,
    and this function never touches the demo DB."""
    msg_html = (
        '<p id="msg" role="alert">That token didn&#39;t work. Check it and try again.</p>'
        if error else
        '<p id="msg" role="status" aria-live="polite"></p>'
    )
    aria_invalid = "true" if error else "false"
    border = "var(--status-red)" if error else "var(--border-default)"
    # Same wordmark-as-SVG-paths treatment as frontend/gate.html (the
    # Citadel of Blackrose face isn't self-hosted -- see gate.html's own
    # comment) and the same plum palette. The sigil here is deliberately
    # restrained versus the visitor gate's full pipeline diagram: a single
    # static ring + core, no route tracing, no animation at all -- this is
    # an internal page, so "related but plainer" (task brief) rather than
    # the demo showpiece.
    wordmark_svg = (
        '<svg viewBox="-0.88 -76.76 534.00 91.41" fill="currentColor" role="img" '
        'aria-label="Rulemancer"><path d="M200 326V102Q200 75 202.0 59.0Q204 43 211.5 32.5'
        'Q219 22 232.5 15.0Q246 8 270 0H85Q113 12 119.0 33.0Q125 54 125 77V204V457Q125 486 '
        '114.0 507.5Q103 529 70 534L76 543Q92 535 106.5 527.0Q121 519 133 512Q130 528 128.0 '
        '547.0Q126 566 120.0 582.5Q114 599 102.0 610.0Q90 621 68 621Q54 621 44.0 618.5Q34 616 '
        '27.0 609.5Q20 603 14.0 591.5Q8 580 2 561Q1 565 1 573Q1 604 23.0 618.0Q45 632 76.5 '
        '636.0Q108 640 143.5 638.0Q179 636 207 636Q203 630 197.0 620.5Q191 611 184 600Q235 '
        '620 286.0 632.0Q337 644 390 644Q429 644 465.5 636.0Q502 628 530.0 611.5Q558 595 '
        '574.5 570.0Q591 545 591 510Q591 477 575.0 447.0Q559 417 533.5 392.5Q508 368 475.5 '
        '350.5Q443 333 411 325Q423 312 437.0 300.5Q451 289 460 275Q478 246 496.0 206.0Q514 '
        '166 533.0 129.0Q552 92 573.5 66.5Q595 41 621 41Q648 41 682 73Q688 78 693.0 84.5Q698 '
        '91 705 94Q686 50 648.5 25.0Q611 0 563 0Q533 0 511.0 18.5Q489 37 471.5 65.0Q454 93 '
        '440.0 127.0Q426 161 414 192Q395 240 378.0 267.0Q361 294 337.5 307.0Q314 320 281.5 '
        '323.0Q249 326 200 326ZM200 353Q226 351 253.5 351.0Q281 351 309 347Q325 344 342 '
        '344Q399 344 439.5 375.5Q480 407 500 468Q504 480 506.0 490.5Q508 501 508 512Q508 540 '
        '494.5 562.0Q481 584 459.5 599.5Q438 615 410.0 623.0Q382 631 354 631Q321 631 289.5 '
        '621.5Q258 612 225 597Q206 588 198.5 571.0Q191 554 191 532Q191 488 194.5 443.5Q198 '
        '399 200 353Z" transform="translate(0.00 0) scale(0.11765 -0.11765)"/><path d="M276 '
        '384Q314 399 351.5 413.5Q389 428 427 444Q422 363 415.0 276.0Q408 189 408 115Q408 42 '
        '463 42Q472 42 482.5 45.5Q493 49 503 49H508Q480 26 446.5 9.0Q413 -8 377 -8Q365 -8 '
        '358.5 -2.0Q352 4 349.5 13.0Q347 22 346.5 33.5Q346 45 346 56Q346 70 346.5 85.0Q347 '
        '100 347 117Q325 96 305.5 75.0Q286 54 265.5 37.5Q245 21 222.0 10.5Q199 0 171 0Q114 0 '
        '83.0 34.0Q52 68 52 130Q52 151 54.0 174.0Q56 197 58.0 220.5Q60 244 62.0 266.5Q64 289 '
        '64 308Q64 328 61.0 339.5Q58 351 50.5 357.5Q43 364 30.0 367.0Q17 370 -4 375Q0 385 9.5 '
        '395.0Q19 405 32.0 412.5Q45 420 59.5 424.5Q74 429 87 429Q113 429 126.5 409.0Q140 389 '
        '140 359Q140 336 138.0 310.0Q136 284 134.0 257.0Q132 230 130.0 203.5Q128 177 128 '
        '153Q128 136 131.5 119.0Q135 102 144.0 88.5Q153 75 169.0 66.0Q185 57 209 57Q229 57 '
        '246.0 65.5Q263 74 280 87Q324 122 339.0 172.0Q354 222 354 276Q354 299 352.0 315.0Q350 '
        '331 342.0 343.0Q334 355 318.5 364.5Q303 374 276 384Z" transform="translate(80.47 0) '
        'scale(0.11765 -0.11765)"/><path d="M188 63Q172 55 155.0 44.0Q138 33 120.5 23.0Q103 '
        '13 86.0 6.0Q69 -1 53 -1Q34 -1 23.5 11.0Q13 23 8.0 43.5Q3 64 2.0 92.0Q1 120 1 153Q-1 '
        '244 -1.5 332.5Q-2 421 -10 510Q-15 567 -44.5 594.0Q-74 621 -122 621Q-117 627 -91.5 '
        '627.5Q-66 628 -31.0 627.5Q4 627 42.0 625.5Q80 624 110 626Q86 601 78.5 564.0Q71 527 '
        '71 485Q71 400 68.0 315.5Q65 231 65 146Q65 128 67.5 111.0Q70 94 75.5 80.5Q81 67 90.5 '
        '59.0Q100 51 115 51Q135 51 150.5 58.0Q166 65 183 73Q185 71 185.5 68.5Q186 66 188 63Z" '
        'transform="translate(137.06 0) scale(0.11765 -0.11765)"/><path d="M77 189Q89 126 '
        '131.5 92.0Q174 58 231 58Q267 58 307.0 72.0Q347 86 386 116Q349 55 300.5 27.5Q252 0 '
        '188 0Q150 0 116.0 13.5Q82 27 55.5 52.5Q29 78 13.5 115.5Q-2 153 -2 200Q-2 250 19.0 '
        '293.5Q40 337 73.5 369.0Q107 401 149.0 419.5Q191 438 232 438Q252 438 277.5 432.0Q303 '
        '426 325.5 413.0Q348 400 363.5 380.5Q379 361 379 333Q379 309 364.0 288.0Q349 267 320 '
        '257Q259 237 198.5 221.5Q138 206 77 189Q105 205 143.5 219.0Q182 233 216.5 249.0Q251 '
        '265 275.0 284.5Q299 304 299 331Q299 347 291.0 361.5Q283 376 269.5 387.0Q256 398 '
        '238.5 404.0Q221 410 202 410Q169 410 144.5 393.5Q120 377 104.5 352.5Q89 328 81.5 '
        '298.5Q74 269 74 242Q74 216 77 189Z" transform="translate(156.12 0) scale(0.11765 '
        '-0.11765)"/><path d="M135 440V334Q156 351 178.5 368.5Q201 386 224.0 400.5Q247 415 '
        '270.5 424.0Q294 433 318 433Q348 433 369.5 411.5Q391 390 412 346Q427 362 443.5 '
        '377.5Q460 393 479.0 405.5Q498 418 519.5 426.0Q541 434 566 434Q591 434 613.0 '
        '424.0Q635 414 651.5 397.5Q668 381 678.0 358.0Q688 335 688 310Q688 288 682.0 '
        '263.5Q676 239 667.5 214.5Q659 190 650.0 165.0Q641 140 636 116Q619 45 619 -25Q619 '
        '-95 678 -95Q705 -95 730.0 -83.0Q755 -71 785 -54Q768 -84 738.5 -100.0Q709 -116 677 '
        '-116Q651 -116 628.5 -106.5Q606 -97 589.5 -81.0Q573 -65 564.0 -43.0Q555 -21 555 '
        '3Q555 23 560.0 44.5Q565 66 572.5 88.5Q580 111 587.0 134.0Q594 157 599 178Q603 198 '
        '606.0 219.5Q609 241 609 263Q609 315 585.5 345.5Q562 376 520 376Q498 376 477.5 '
        '367.0Q457 358 441.5 342.0Q426 326 417.0 305.5Q408 285 408 263Q408 218 409.5 '
        '171.0Q411 124 413 78Q414 50 427.0 31.0Q440 12 471 7H278Q296 17 307.0 31.5Q318 46 '
        '323.5 64.0Q329 82 330.5 102.0Q332 122 332 143Q332 168 331.5 191.5Q331 215 331 '
        '239Q331 256 332.0 274.0Q333 292 333 309Q333 344 313.0 361.5Q293 379 265 379Q238 379 '
        '213.0 367.5Q188 356 169.0 336.5Q150 317 138.5 291.0Q127 265 127 235Q127 201 129.0 '
        '167.0Q131 133 133 98Q134 66 147.0 42.0Q160 18 193 5H0Q24 8 36.0 18.5Q48 29 53.5 '
        '43.5Q59 58 59.5 75.5Q60 93 60 111Q60 159 59.5 207.0Q59 255 59 303Q59 326 48.5 '
        '345.5Q38 365 3 367Q37 386 68.0 403.0Q99 420 135 440Z" transform="translate(203.06 0) '
        'scale(0.11765 -0.11765)"/><path d="M44 292Q38 306 30.5 326.0Q23 346 16.0 366.0Q9 386 '
        '4.0 402.5Q-1 419 -1 425V427L0 428Q1 428 3 426Q15 412 24.5 406.5Q34 401 46 401Q56 401 '
        '77.5 405.0Q99 409 126.5 414.5Q154 420 184.5 424.0Q215 428 244 428Q290 428 316.5 '
        '415.0Q343 402 356.5 382.0Q370 362 373.0 337.5Q376 313 376 289Q376 263 376.5 '
        '237.0Q377 211 377 185Q377 166 376.0 147.0Q375 128 375 108Q375 79 385.5 67.0Q396 55 '
        '415 55Q427 55 440.5 59.0Q454 63 471 73Q448 37 416.0 18.5Q384 0 349 0Q331 0 323.0 '
        '7.5Q315 15 311.5 28.0Q308 41 307.5 58.0Q307 75 305 95Q279 74 256.5 56.5Q234 39 '
        '212.0 26.0Q190 13 167.0 6.0Q144 -1 116 -1Q63 -1 31.5 25.5Q0 52 0 99Q0 123 10.0 '
        '141.5Q20 160 36.5 174.0Q53 188 73.5 199.5Q94 211 114 222Q138 235 171.0 249.5Q204 '
        '264 233.5 280.0Q263 296 283.5 313.5Q304 331 304 351Q304 360 294.5 366.0Q285 372 '
        '272.5 376.0Q260 380 246.5 381.5Q233 383 225 383Q186 383 149.0 370.0Q112 357 77 '
        '340Q66 335 59.5 320.5Q53 306 44 292ZM296 291Q266 275 229.0 258.5Q192 242 159.5 '
        '223.0Q127 204 105.5 181.5Q84 159 84 132Q84 112 92.0 95.5Q100 79 113.0 67.0Q126 55 '
        '142.0 48.5Q158 42 174 42Q207 42 233.0 56.0Q259 70 277.5 92.5Q296 115 305.5 143.0Q315 '
        '171 315 199Q315 244 296 291Z" transform="translate(287.06 0) scale(0.11765 '
        '-0.11765)"/><path d="M225 2H33Q57 11 65.5 34.0Q74 57 74 87Q74 139 72.0 191.0Q70 243 '
        '67 295Q64 349 2 349Q39 368 72.5 384.5Q106 401 142 420V314Q170 341 192.0 362.5Q214 '
        '384 234.0 398.5Q254 413 274.0 420.5Q294 428 320 428Q343 428 366.0 422.5Q389 417 '
        '407.0 404.5Q425 392 436.0 372.5Q447 353 447 325Q447 318 447.0 312.5Q447 307 445 '
        '301Q438 270 428.5 234.5Q419 199 410.0 162.5Q401 126 394.5 91.0Q388 56 388 25Q388 '
        '-19 400.5 -42.0Q413 -65 440 -65Q459 -65 476.5 -54.0Q494 -43 523 -17Q506 -51 482.5 '
        '-71.5Q459 -92 427 -92Q404 -92 386.5 -79.5Q369 -67 357.5 -48.5Q346 -30 340.0 '
        '-7.5Q334 15 334 36Q334 62 337.0 93.5Q340 125 344.0 158.0Q348 191 351.0 223.0Q354 '
        '255 354 282Q354 324 331.0 348.5Q308 373 270 373Q243 373 219.5 361.0Q196 349 179.0 '
        '328.5Q162 308 152.0 282.5Q142 257 142 230Q142 167 140.0 127.5Q138 88 143.5 63.5Q149 '
        '39 167.0 25.5Q185 12 225 2Z" transform="translate(338.12 0) scale(0.11765 '
        '-0.11765)"/><path d="M397 118Q367 55 313.5 28.0Q260 1 195 1Q153 1 117.0 15.0Q81 29 '
        '54.5 55.5Q28 82 13.5 120.5Q-1 159 -1 207Q-1 249 13.5 288.5Q28 328 55.5 359.0Q83 390 '
        '122.0 408.5Q161 427 210 427Q231 427 252.5 424.0Q274 421 296 421Q319 421 343.5 '
        '422.5Q368 424 394 426Q378 378 362.5 333.0Q347 288 330 241H314Q294 292 286.5 '
        '322.0Q279 352 270.0 368.0Q261 384 244.0 388.5Q227 393 189 393Q165 393 142.5 '
        '385.0Q120 377 102.0 360.5Q84 344 73.0 317.5Q62 291 62 254Q62 212 76.0 174.5Q90 137 '
        '115.0 109.0Q140 81 174.0 64.5Q208 48 249 48Q291 48 328.0 65.0Q365 82 397 118Z" '
        'transform="translate(394.47 0) scale(0.11765 -0.11765)"/><path d="M77 189Q89 126 '
        '131.5 92.0Q174 58 231 58Q267 58 307.0 72.0Q347 86 386 116Q349 55 300.5 27.5Q252 0 '
        '188 0Q150 0 116.0 13.5Q82 27 55.5 52.5Q29 78 13.5 115.5Q-2 153 -2 200Q-2 250 19.0 '
        '293.5Q40 337 73.5 369.0Q107 401 149.0 419.5Q191 438 232 438Q252 438 277.5 432.0Q303 '
        '426 325.5 413.0Q348 400 363.5 380.5Q379 361 379 333Q379 309 364.0 288.0Q349 267 320 '
        '257Q259 237 198.5 221.5Q138 206 77 189Q105 205 143.5 219.0Q182 233 216.5 249.0Q251 '
        '265 275.0 284.5Q299 304 299 331Q299 347 291.0 361.5Q283 376 269.5 387.0Q256 398 '
        '238.5 404.0Q221 410 202 410Q169 410 144.5 393.5Q120 377 104.5 352.5Q89 328 81.5 '
        '298.5Q74 269 74 242Q74 216 77 189Z" transform="translate(442.94 0) scale(0.11765 '
        '-0.11765)"/><path d="M3 372Q35 390 68.0 408.0Q101 426 137 446Q135 420 134.5 '
        '395.5Q134 371 132 344Q150 359 167.0 374.5Q184 390 200.0 402.5Q216 415 232.5 '
        '422.5Q249 430 267 430Q285 430 302.0 423.0Q319 416 331.5 404.0Q344 392 351.5 '
        '377.0Q359 362 359 346Q359 328 351.5 313.5Q344 299 331.5 284.5Q319 270 303.0 '
        '255.5Q287 241 270 225Q278 256 285.0 277.5Q292 299 292 320Q292 346 277.5 361.5Q263 '
        '377 240 377Q213 377 194.0 365.5Q175 354 163.0 336.0Q151 318 144.5 295.5Q138 273 '
        '135.0 252.0Q132 231 131.5 213.5Q131 196 131 187Q131 145 133.0 113.5Q135 82 144.0 '
        '59.5Q153 37 170.5 22.5Q188 8 219 0H-8Q15 7 28.0 20.5Q41 34 47.5 52.0Q54 70 55.5 '
        '90.0Q57 110 57 131V244Q57 266 57.0 288.5Q57 311 52.5 329.0Q48 347 36.5 358.5Q25 370 '
        '3 372Z" transform="translate(489.88 0) scale(0.11765 -0.11765)"/></svg>'
    )
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rulemancer admin -- log in</title>
<link rel="stylesheet" href="/colors_and_type.css?v=3">
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; height: 100%; }}
  body {{ position: relative; display: flex; align-items: center; justify-content: center;
          min-height: 100vh; padding: var(--space-5); font-family: var(--font-sans);
          overflow-x: hidden; }}
  .admin-sigil {{ position: fixed; inset: 0; width: 100%; height: 100%; z-index: 0;
          pointer-events: none; opacity: .28; }}
  .admin-login-card {{ position: relative; z-index: 1; max-width: 380px; width: 100%;
          background: var(--bg-card); border: 1px solid var(--border-default);
          border-radius: var(--radius-lg); box-shadow: var(--shadow-lg);
          padding: var(--space-6) var(--space-5); text-align: center; }}
  .admin-wordmark {{ margin: 0 0 var(--space-2); display: flex; justify-content: center; }}
  .admin-wordmark svg {{ width: min(220px, 60vw); height: auto; display: block; color: var(--accent); }}
  .sub {{ color: var(--fg-secondary); font-size: var(--fs-sm); line-height: var(--lh-base);
          margin: 0 0 var(--space-5); }}
  form {{ display: flex; flex-direction: column; gap: var(--space-3); }}
  label {{ text-align: left; font-size: var(--fs-sm); font-weight: var(--fw-medium); color: var(--fg-secondary); }}
  input[type=password] {{ width: 100%; padding: 0.75rem 1rem; font-size: var(--fs-base);
          font-family: var(--font-mono); background: var(--bg-elevated);
          border: 1px solid {border}; border-radius: var(--radius-md); color: var(--fg-primary); }}
  input[type=password]::placeholder {{ color: var(--fg-subtle); }}
  input[type=password]:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px;
          border-color: var(--accent); }}
  /* plum-500, not --accent (plum-400) -- --fg-on-garnet on plum-400 measures
     3.60:1, below AA's 4.5:1 for normal text; plum-500 measures 5.16:1.
     Same brand token family, no new color introduced. */
  button {{ width: 100%; padding: 0.75rem 1rem; font-size: var(--fs-base); font-weight: var(--fw-semibold);
          font-family: var(--font-sans); background: var(--plum-500); color: var(--fg-on-garnet, #fff);
          border: none; border-radius: var(--radius-md); cursor: pointer; transition: background var(--t-fast); }}
  button:hover {{ background: var(--plum-600); }}
  button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  /* status-red on bg-card alone is 4.37:1, just under AA; mixing in 20%
     white (still derived from the token) brings it to ~5.7:1. */
  #msg {{ margin: var(--space-3) 0 0; font-size: var(--fs-sm); min-height: 1.2em;
          color: color-mix(in srgb, var(--status-red) 80%, white); }}
</style>
</head>
<body data-surface="dark">
<svg class="admin-sigil" viewBox="0 0 480 480" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false" role="presentation">
  <g fill="none">
    <circle cx="240" cy="240" r="200" stroke="var(--plum-400)" stroke-width="1" opacity=".5" />
    <circle cx="240" cy="240" r="150" stroke="var(--teal-300)" stroke-width="1" stroke-dasharray="2 8" opacity=".35" />
    <circle cx="240" cy="240" r="34" fill="var(--bg-page)" stroke="var(--teal-500)" stroke-width="1.6" opacity=".6" />
    <path d="M240 216 L258 240 L240 264 L222 240 Z" stroke="var(--teal-300)" stroke-width="1" opacity=".5" />
  </g>
</svg>
<div class="admin-login-card">
  <h1 class="admin-wordmark">{wordmark_svg}</h1>
  <p class="sub">Enter the admin token to view the demo dashboard.</p>
  <form method="post" action="/admin/login">
    <label for="token">Admin token</label>
    <input type="password" id="token" name="token" placeholder="admin token"
           autocomplete="off" autofocus aria-invalid="{aria_invalid}" />
    <button type="submit">Log in</button>
  </form>
  {msg_html}
</div>
</body></html>"""
    return HTMLResponse(content=body, status_code=status_code)


@app.post("/admin/login", tags=["ops"], summary="Log into /admin with the admin token",
          include_in_schema=False)
def admin_login(token: str = Form(...)):
    """Constant-time compare against ADMIN_TOKEN (matches _require_admin_token's
    hmac.compare_digest pattern); on success, signs and sets ADMIN_COOKIE_NAME
    and 303-redirects to /admin. On failure, re-renders the login form with a
    generic error and sets no cookie -- never reveals how close the guess
    was. Token arrives in the POST form body, never a query parameter: a
    query string lands in browser history, server access logs, and any
    Referer header sent to third parties; a form body does none of that."""
    expected, secret = _require_admin_login_config()
    if not hmac.compare_digest(token, expected):
        return _admin_login_page(error=True, status_code=401)
    signed = sign_session(ADMIN_SESSION_MARKER, secret)
    resp = RedirectResponse(url="/admin", status_code=303)
    resp.set_cookie(ADMIN_COOKIE_NAME, signed, max_age=ADMIN_COOKIE_MAX_AGE_S,
                     httponly=True, samesite="lax", secure=True)
    return resp


def _require_admin_token(authorization: str | None) -> None:
    """Bearer-token gate, matching the existing os.environ.get(...) key
    pattern (openrouter_backend.py's OPENROUTER_API_KEY). Fails CLOSED: if
    ADMIN_TOKEN isn't configured at all, every request is refused (503) --
    never silently wide open. A configured token that doesn't match, or a
    missing/malformed header, is a 401."""
    token = os.environ.get("ADMIN_TOKEN")
    if not token:
        raise HTTPException(status_code=503, detail="admin endpoint not configured (no ADMIN_TOKEN)")
    # hmac.compare_digest instead of `!=`: a plain string comparison
    # short-circuits on the first differing byte, so its timing leaks how
    # much of the prefix was correct -- a real risk now that this same gate
    # gates /admin, which renders every code/label/question, in a public
    # repo. compare_digest raises TypeError on mixed str/bytes, so guard
    # `authorization` being None (missing header) or any non-str value
    # explicitly rather than letting a malformed header turn an auth check
    # into a 500.
    expected = f"Bearer {token}"
    if not isinstance(authorization, str) or not hmac.compare_digest(authorization, expected):
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


def _fmt_ts(ts: str | None) -> str:
    """events.ts / codes.created_at are UTC isoformat strings (demo_db._now).
    Trim to minute precision for the page; keep the raw string as a
    fallback so a malformed value never raises."""
    if not ts:
        return "–"
    try:
        return ts.replace("T", " ")[:16] + " UTC"
    except Exception:
        return ts


@app.get(
    "/admin", tags=["ops"], summary="Demo codes/usage dashboard",
    description="Accepts EITHER Authorization: Bearer <ADMIN_TOKEN> (unchanged, for scripts "
    "and the Scryfall refresh endpoints) OR a signed admin session cookie set by POST "
    "/admin/login. No valid auth renders a browser-friendly login form (401) instead of a "
    "JSON error -- see .superpowers/sdd/2026-07-27-gated-demo/task-admin-login-report.md. "
    "Per code: unlocks, queries, first/last seen, total cost, remaining quota, and every "
    "question asked (newest first). Plus today's global spend against the daily budget cap.",
)
def admin_demo_view(
    authorization: str | None = Header(default=None),
    admin_session: str | None = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
) -> HTMLResponse:
    # Bearer path first, unchanged from before -- scripts and the Scryfall
    # admin endpoints depend on this exact check still working. Only if that
    # fails do we look at the cookie; only if BOTH fail do we render the
    # login form. Neither branch below (nor _admin_login_page) ever touches
    # list_codes/code_stats/events_for_code, so no code, label, question, or
    # count can leak into an unauthenticated response.
    # Same DI-vs-direct-call guard as answer()'s `session` param above
    # (main.py:690): FastAPI injects a real str|None when this route runs
    # through the app, but the test suite calls admin_demo_view() directly
    # without ever passing admin_session, leaving it as the Cookie(...)
    # field-info sentinel rather than None -- _admin_authed handles that.
    if not _admin_authed(authorization, admin_session):
        return _admin_login_page()

    return HTMLResponse(content=_admin_page_html())


def _admin_page_html(minted: dict | None = None, error: str | None = None) -> str:
    """Builds the /admin dashboard body -- codes table, per-code question
    detail, and (Task: admin mint/revoke) the mint form and per-row revoke
    control. Shared by admin_demo_view (plain GET) and the mint/revoke POST
    handlers below, so there is exactly one page template, not three
    near-copies that could drift. `minted` is the just-created code dict
    (shown once, prominently) after a successful mint; `error` is a
    validation message re-rendered after a rejected mint. Neither parameter
    ever carries anything that wasn't already going to be in the page --
    this function still never touches list_codes/code_stats/events_for_code
    until the caller has already confirmed auth."""
    today = datetime.now(timezone.utc).date().isoformat()
    budget = float(os.environ.get("DAILY_BUDGET_USD", DAILY_BUDGET_USD_DEFAULT))
    # Same function the /answer breaker calls (_todays_spend, defined above)
    # -- this number and the one that trips the breaker can never disagree.
    spend_today = _todays_spend(DEMO_DB, today)
    pct = min(spend_today / budget, 1.0) if budget > 0 else 0.0
    over = spend_today >= budget

    codes = list_codes(DEMO_DB)

    summary_rows = []
    detail_sections = []
    for code in codes:
        stats = code_stats(DEMO_DB, code["id"])
        cap = code["max_queries"] if code["max_queries"] is not None else DEFAULT_MAX_QUERIES
        remaining = max(cap - stats["queries"], 0)
        status = "revoked" if code["revoked_at"] else "active"
        label = _html.escape(code["label"] or "(no label)")
        code_val = _html.escape(code["code"])
        # A code that's never been unlocked or queried still has 0/0/None --
        # code_stats() never raises on that, and first/last seen fall back to
        # the "–" placeholder from _fmt_ts. The row renders, it doesn't
        # vanish.
        # Revoke control: a tiny same-origin POST form per row, gated by the
        # exact same admin auth (_admin_authed) as every other admin action
        # -- the button carries no privilege of its own, the cookie/bearer
        # check on the route does. Disabled once already revoked so a
        # double-click can't matter either way (revoke_code's own WHERE
        # revoked_at IS NULL already makes a second revoke a no-op).
        revoke_btn = (
            '<span class="already-revoked">revoked</span>' if status == "revoked" else
            f'<form method="post" action="/admin/codes/revoke" class="revoke-form">'
            f'<input type="hidden" name="code_id" value="{code["id"]}" />'
            f'<button type="submit" class="btn-revoke">Revoke</button></form>'
        )
        summary_rows.append(f"""
        <tr>
          <td>{label}</td>
          <td><code>{code_val}</code></td>
          <td><span class="status status-{status}">{status}</span></td>
          <td>{stats["unlocks"]}</td>
          <td>{stats["queries"]}</td>
          <td>{remaining}</td>
          <td>${stats["total_cost"]:.2f}</td>
          <td>{_fmt_ts(stats["first_seen"])}</td>
          <td>{_fmt_ts(stats["last_seen"])}</td>
          <td>{revoke_btn}</td>
        </tr>""")

        events = events_for_code(DEMO_DB, code["id"])
        # events_for_code ORDER BY id DESC -- ids are a single-writer
        # autoincrement, so id order and chronological (ts) order agree;
        # newest-first here is a real timestamp ordering, not a string sort.
        if events:
            questions_html = "".join(
                f'<li><span class="q-ts">{_fmt_ts(e["ts"])}</span>'
                f'<span class="q-cost">${(e["cost_usd"] or 0.0):.3f}</span>'
                f'<span class="q-text">{_html.escape(e["question"] or "")}</span></li>'
                for e in events
            )
        else:
            questions_html = '<li class="empty">No questions asked yet.</li>'
        detail_sections.append(f"""
        <section class="code-card">
          <h3>{label} <span class="code-tag"><code>{code_val}</code></span></h3>
          <ul class="questions">{questions_html}</ul>
        </section>""")

    if not codes:
        table_body = (
            '<tr><td colspan="10" class="empty-row">No codes minted yet. '
            'Mint one below.</td></tr>'
        )
        details_html = ""
    else:
        table_body = "".join(summary_rows)
        details_html = "\n".join(detail_sections)

    # Mint-form pieces (Task: admin mint/revoke). default_est is the
    # no-JS-fallback estimate for the form's default cap (25); the <script>
    # below recomputes it live as the operator edits the number field, using
    # the SAME MEASURED_MEAN_COST_PER_QUERY_USD constant so the two numbers
    # can never disagree.
    default_cap = 25
    default_est = default_cap * MEASURED_MEAN_COST_PER_QUERY_USD
    ceiling_est = MAX_QUERIES_CEILING * MEASURED_MEAN_COST_PER_QUERY_USD

    minted_html = ""
    if minted is not None:
        # Shown once -- this response is the only place the plaintext code
        # is ever displayed after creation; list_codes/admin table rows only
        # ever show it again as the same already-minted value, ie it isn't
        # "secret" past this point in the sense of being unguessable, but
        # there's no second reveal-it-big moment. Monospace, large, high
        # contrast, and set apart from the table so Jon can read it aloud or
        # paste it into an email without misreading a character.
        m_code = _html.escape(minted["code"])
        m_label = _html.escape(minted["label"])
        minted_html = f"""
        <div class="minted-banner" role="status">
          <p>New code minted for <strong>{m_label}</strong> -- copy it now, it won't be shown this large again:</p>
          <p class="minted-code">{m_code}</p>
        </div>"""

    error_html = ""
    if error:
        error_html = f'<p class="form-error" role="alert">{_html.escape(error)}</p>'

    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rulemancer admin -- demo usage</title>
<link rel="stylesheet" href="/colors_and_type.css">
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: var(--space-5); max-width: 1100px; margin-inline: auto; }}
  h1 {{ font-family: var(--font-wordmark); font-size: var(--fs-2xl); font-weight: var(--fw-semibold);
        color: var(--fg-primary); margin: 0 0 var(--space-4); }}
  h3 {{ font-size: var(--fs-lg); font-weight: var(--fw-semibold); color: var(--fg-primary);
        margin: 0 0 var(--space-3); display: flex; align-items: center; gap: var(--space-2);
        flex-wrap: wrap; }}
  .budget {{ background: var(--bg-card); border: 1px solid var(--border-default);
             border-radius: var(--radius-lg); padding: var(--space-4) var(--space-5);
             margin-bottom: var(--space-5); }}
  .budget-line {{ display: flex; justify-content: space-between; align-items: baseline;
                  gap: var(--space-3); flex-wrap: wrap; color: var(--fg-secondary);
                  font-size: var(--fs-sm); margin-bottom: var(--space-2); }}
  .budget-line strong {{ color: var(--fg-primary); font-size: var(--fs-lg); }}
  .budget-line .cap-over {{ color: var(--status-red); font-weight: var(--fw-semibold); }}
  .meter {{ height: 8px; border-radius: var(--radius-pill); background: var(--bg-muted);
            overflow: hidden; }}
  .meter-fill {{ height: 100%; border-radius: var(--radius-pill);
                 background: {"var(--status-red)" if over else "var(--sigil)"}; }}
  h2 {{ font-size: var(--fs-lg); font-weight: var(--fw-semibold); color: var(--fg-primary);
        margin: var(--space-6) 0 var(--space-3); }}
  .table-scroll {{ overflow-x: auto; border: 1px solid var(--border-default);
                   border-radius: var(--radius-lg); background: var(--bg-card); }}
  table {{ border-collapse: collapse; width: 100%; min-width: 720px; font-size: var(--fs-sm); }}
  th, td {{ text-align: left; padding: var(--space-3) var(--space-4);
            border-bottom: 1px solid var(--border-default); white-space: nowrap; }}
  th {{ color: var(--fg-secondary); font-weight: var(--fw-medium); font-size: var(--fs-xs);
        text-transform: uppercase; letter-spacing: var(--ls-wide); }}
  tr:last-child td {{ border-bottom: none; }}
  .empty-row {{ color: var(--fg-subtle); font-style: italic; white-space: normal; }}
  .status {{ font-size: var(--fs-xs); padding: 0.15rem 0.6rem; border-radius: var(--radius-pill);
             font-weight: var(--fw-medium); }}
  .status-active {{ background: rgba(76,175,124,0.15); color: var(--status-green); }}
  .status-revoked {{ background: rgba(224,80,80,0.15); color: var(--status-red); }}
  .code-card {{ background: var(--bg-card); border: 1px solid var(--border-default);
                border-radius: var(--radius-lg); padding: var(--space-4) var(--space-5);
                margin-bottom: var(--space-4); }}
  .code-tag code {{ font-size: var(--fs-xs); font-weight: var(--fw-regular); }}
  code {{ background: var(--bg-muted); color: var(--fg-primary); padding: 0.1rem 0.4rem;
          border-radius: var(--radius-sm); font-family: var(--font-mono); }}
  .questions {{ list-style: none; margin: 0; padding: 0; max-height: 260px; overflow-y: auto; }}
  .questions li {{ display: flex; align-items: baseline; gap: var(--space-3);
                   padding: var(--space-2) 0; border-bottom: 1px solid var(--border-default);
                   flex-wrap: wrap; }}
  .questions li:last-child {{ border-bottom: none; }}
  .questions .q-ts {{ color: var(--fg-subtle); font-size: var(--fs-xs); flex-shrink: 0; }}
  .questions .q-cost {{ color: var(--sigil); font-size: var(--fs-xs); flex-shrink: 0; }}
  .questions .q-text {{ color: var(--fg-primary); font-size: var(--fs-sm); }}
  .questions .empty {{ color: var(--fg-subtle); font-style: italic; }}
  .btn-revoke {{ padding: 0.35rem 0.75rem; font-size: var(--fs-xs); font-weight: var(--fw-medium);
                 font-family: var(--font-sans); background: transparent; color: var(--status-red);
                 border: 1px solid var(--status-red); border-radius: var(--radius-md);
                 cursor: pointer; transition: background var(--t-fast); white-space: nowrap; }}
  .btn-revoke:hover {{ background: rgba(224,80,80,0.12); }}
  .btn-revoke:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  .already-revoked {{ color: var(--fg-subtle); font-size: var(--fs-xs); font-style: italic; }}
  .revoke-form {{ margin: 0; }}
  .mint-card {{ background: var(--bg-card); border: 1px solid var(--border-default);
                border-radius: var(--radius-lg); padding: var(--space-4) var(--space-5);
                margin-bottom: var(--space-5); }}
  .mint-form {{ display: flex; gap: var(--space-4); align-items: flex-end; flex-wrap: wrap; }}
  .mint-field {{ display: flex; flex-direction: column; gap: var(--space-1); }}
  .mint-field label {{ font-size: var(--fs-sm); font-weight: var(--fw-medium); color: var(--fg-secondary); }}
  .mint-field input {{ padding: 0.6rem 0.85rem; font-size: var(--fs-base); font-family: var(--font-mono);
                        background: var(--bg-elevated); border: 1px solid var(--border-default);
                        border-radius: var(--radius-md); color: var(--fg-primary); min-width: 0; }}
  #mint-label {{ font-family: var(--font-sans); min-width: 220px; }}
  #mint-cap {{ width: 8ch; }}
  .mint-field input:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px;
                                      border-color: var(--accent); }}
  .cap-estimate {{ color: var(--fg-secondary); font-size: var(--fs-xs); align-self: center; }}
  .mint-submit {{ padding: 0.65rem 1.1rem; font-size: var(--fs-base); font-weight: var(--fw-semibold);
                  font-family: var(--font-sans); background: var(--plum-500); color: var(--fg-on-garnet, #fff);
                  border: none; border-radius: var(--radius-md); cursor: pointer;
                  transition: background var(--t-fast); }}
  .mint-submit:hover {{ background: var(--plum-600); }}
  .mint-submit:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  .form-error {{ margin: var(--space-3) 0 0; font-size: var(--fs-sm);
                 color: color-mix(in srgb, var(--status-red) 80%, white); }}
  .minted-banner {{ background: var(--bg-card); border: 2px solid var(--sigil);
                     border-radius: var(--radius-lg); padding: var(--space-4) var(--space-5);
                     margin-bottom: var(--space-5); }}
  .minted-banner p {{ margin: 0 0 var(--space-2); color: var(--fg-secondary); font-size: var(--fs-sm); }}
  .minted-code {{ font-family: var(--font-mono); font-size: var(--fs-2xl); font-weight: var(--fw-semibold);
                  color: var(--fg-primary); background: var(--bg-muted); border-radius: var(--radius-md);
                  padding: var(--space-3) var(--space-4); user-select: all; letter-spacing: var(--ls-wide);
                  word-break: break-all; }}
  @media (max-width: 600px) {{
    body {{ padding: var(--space-3); }}
    h1 {{ font-size: var(--fs-xl); }}
    .mint-form {{ flex-direction: column; align-items: stretch; }}
  }}
</style>
</head>
<body data-surface="dark">
  <h1>Rulemancer -- demo usage</h1>
  <div class="budget">
    <div class="budget-line">
      <span>Today's spend ({today} UTC)</span>
      <strong class="{'cap-over' if over else ''}">${spend_today:.2f} / ${budget:.2f}</strong>
    </div>
    <div class="meter"><div class="meter-fill" style="width:{pct * 100:.1f}%"></div></div>
  </div>

  {minted_html}

  <h2>Mint a code</h2>
  <div class="mint-card">
    <form method="post" action="/admin/codes/mint" class="mint-form">
      <div class="mint-field">
        <label for="mint-label">Label</label>
        <input type="text" id="mint-label" name="label" placeholder="Cribl -- Jane R."
               autocomplete="off" required />
      </div>
      <div class="mint-field">
        <label for="mint-cap">Max queries (1-{MAX_QUERIES_CEILING}, ceiling is about ${ceiling_est:.2f})</label>
        <input type="number" id="mint-cap" name="max_queries" value="{default_cap}"
               min="1" max="{MAX_QUERIES_CEILING}" step="1" required />
      </div>
      <span class="cap-estimate" id="cap-estimate">about ${default_est:.2f} at ${MEASURED_MEAN_COST_PER_QUERY_USD}/query (measured mean)</span>
      <button type="submit" class="mint-submit">Mint code</button>
    </form>
    {error_html}
  </div>
  <script>
    (function () {{
      var MEAN_COST = {MEASURED_MEAN_COST_PER_QUERY_USD};
      var CEILING = {MAX_QUERIES_CEILING};
      var input = document.getElementById('mint-cap');
      var out = document.getElementById('cap-estimate');
      function update() {{
        var n = parseInt(input.value, 10);
        if (!isFinite(n) || n <= 0) {{
          out.textContent = 'enter a whole number from 1 to ' + CEILING;
          return;
        }}
        var est = (n * MEAN_COST).toFixed(2);
        out.textContent = 'about $' + est + ' at $' + MEAN_COST + '/query (measured mean)'
          + (n > CEILING ? ' -- exceeds the ' + CEILING + '-query ceiling (about $' + (CEILING * MEAN_COST).toFixed(2) + ')' : '');
      }}
      input.addEventListener('input', update);
      update();
    }})();
  </script>

  <h2>Codes</h2>
  <div class="table-scroll">
    <table>
      <thead><tr>
        <th>Label</th><th>Code</th><th>Status</th><th>Unlocks</th><th>Queries</th>
        <th>Remaining</th><th>Total cost</th><th>First seen</th><th>Last seen</th><th>Actions</th>
      </tr></thead>
      <tbody>{table_body}</tbody>
    </table>
  </div>

  <h2>Questions by code</h2>
  {details_html or '<p class="empty-row">Nothing to show yet.</p>'}
</body></html>"""
    return body


@app.post(
    "/admin/codes/mint", tags=["ops"], summary="Mint a new demo access code",
    description="Admin-gated (Bearer or admin session cookie, same as GET /admin). Generates "
    "a code via the shared word-triplet generator, validates label and max_queries, and "
    "re-renders the admin page -- 200 with the new code shown once on success, 400 with a "
    "validation message on rejection, or the login form (401) with nothing minted if "
    "unauthenticated.",
    include_in_schema=False,
)
def admin_mint_code(
    label: str = Form(...),
    max_queries: str = Form(...),
    authorization: str | None = Header(default=None),
    admin_session: str | None = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
) -> HTMLResponse:
    # Auth first, before touching the DB or even parsing the form fields
    # further -- an unauthenticated POST must mint nothing (mirrors GET
    # /admin's ordering, and test_demo_visitor_session_cookie_does_not_grant_admin's
    # coverage that a visitor's own signed cookie fails this the same way).
    if not _admin_authed(authorization, admin_session):
        return _admin_login_page()

    label_error = _validate_label(label)
    cap_value, cap_error = _validate_max_queries(max_queries)
    error = label_error or cap_error
    if error:
        return HTMLResponse(content=_admin_page_html(error=error), status_code=400)

    # Same collision-avoidance the CLI uses (scripts/codes.py _cmd_new):
    # check against every code that already exists before generating.
    existing = {row["code"] for row in list_codes(DEMO_DB)}
    code = generate_code(existing=existing)
    clean_label = label.strip()
    create_code(DEMO_DB, code, clean_label, max_queries=cap_value)
    minted = {"code": code, "label": clean_label}
    return HTMLResponse(content=_admin_page_html(minted=minted))


@app.post(
    "/admin/codes/revoke", tags=["ops"], summary="Revoke a demo access code",
    description="Admin-gated (Bearer or admin session cookie, same as GET /admin). Revokes "
    "exactly the one code_id posted -- demo_db.revoke_code's own WHERE id = ? scoping means "
    "no other code is ever touched. Unauthenticated POST revokes nothing.",
    include_in_schema=False,
)
def admin_revoke_code(
    code_id: str = Form(...),
    authorization: str | None = Header(default=None),
    admin_session: str | None = Cookie(default=None, alias=ADMIN_COOKIE_NAME),
) -> HTMLResponse:
    if not _admin_authed(authorization, admin_session):
        return _admin_login_page()

    try:
        cid = int(code_id)
    except (TypeError, ValueError):
        return HTMLResponse(content=_admin_page_html(error="Invalid code."), status_code=400)

    revoke_code(DEMO_DB, cid)
    return HTMLResponse(content=_admin_page_html())


# JSON API routes -- the frontend's own fetch() calls hit these without ever
# setting an explicit Accept header (browsers default fetch to "*/*"), so we
# can't rely on Accept alone to tell an API call from a page navigation.
_JSON_API_PATHS = {
    "/answer", "/unlock", "/feedback", "/cards/autocomplete",
    "/admin/scryfall/refresh", "/admin/scryfall/status", "/health",
}


def _wants_json_error(request: Request | None) -> bool:
    """Fix-round-1: the catch-all was returning HTML for every unexpected
    500, including on JSON API routes like /answer -- a fetch() caller that
    does `await r.json()` gets a parse error instead of a usable message.
    Content-negotiate: an explicit `Accept: application/json` always wins;
    otherwise fall back to path -- known JSON API routes get JSON unless the
    caller explicitly asked for HTML (a real browser navigation sends
    `Accept: text/html,...`). Page routes (/, /index.html, static assets)
    aren't in the set, so they keep getting the friendly HTML page."""
    if request is None:
        return False
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return True
    if "text/html" in accept:
        return False
    path = request.url.path if getattr(request, "url", None) is not None else ""
    return path in _JSON_API_PATHS


def _question_too_long_response(request: Request | None) -> HTMLResponse | JSONResponse:
    """The refusal for a question over MAX_QUESTION_CHARS -- content-
    negotiated the same way every other JSON API response on this route is
    (`_wants_json_error`, the general-purpose negotiator this module already
    uses for /answer's own catch-all 500s; "/answer" is in _JSON_API_PATHS,
    so the frontend's fetch() caller -- which never sets an explicit Accept
    header -- still gets JSON back here, same as it does today for any other
    /answer failure). A plain browser POST (Accept: text/html) gets the
    styled page instead, same convention as _unlock_failure_response."""
    message = (
        f"That question is too long ({MAX_QUESTION_CHARS} characters max). "
        "Trim it down and try again."
    )
    if _wants_json_error(request):
        return JSONResponse({"detail": message}, status_code=413)
    return _friendly_html("Question too long", message, status_code=413)


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> HTMLResponse | JSONResponse:
    """Last-resort net: an uncaught exception anywhere in the app renders as
    a friendly page (or, for JSON API callers, a friendly JSON body), never
    FastAPI's default raw-JSON stack dump. The real exception is still
    logged server-side for debugging -- only the response body is
    sanitized, not the operator's visibility into it. Neither branch's
    message ever includes the exception text, a file path, an env value, an
    access code, or a raw IP -- both use the same literal, static string."""
    logger.exception("unhandled exception on %s", getattr(request, "url", "?"))
    message = (
        "That request hit an unexpected error on our end. Try again in a "
        "moment -- if it keeps happening, let Jon know."
    )
    if _wants_json_error(request):
        return JSONResponse(status_code=500, content={"detail": message})
    return _friendly_html("Something went wrong", message, status_code=500)


app.add_exception_handler(Exception, _unhandled_exception_handler)


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
