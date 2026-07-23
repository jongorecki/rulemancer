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
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rulesagent.cache import DEFAULT_DB
from rulesagent.generate.answer import PROMPT_VERSION, RulesAgent
from rulesagent.index.store import VectorStore

logger = logging.getLogger(__name__)

REPO = Path(__file__).parent.parent.parent.parent
VECTOR_MODEL = "voyage-4-large"
SCRYFALL_AUTOCOMPLETE = "https://api.scryfall.com/cards/autocomplete"
SCRYFALL_HEADERS = {"User-Agent": "mtg-rules-bot/0.1 (learning project)", "Accept": "application/json"}

_state: dict = {}
_lock = threading.Lock()
# Serializes /answer. Cache writes no longer need this (L3: per-key SQLite).
# It stays to guard the `agent.last_*` recorder reads made right after
# answer() -- another concurrent request could overwrite those attributes
# between the call and the reads.


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = VectorStore.load(REPO / "data" / "parsed" / f"vector_{VECTOR_MODEL}.pkl")
    agent = RulesAgent(store)  # ruling_select on; live Scryfall (fresh rulings)
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


@app.get("/health", tags=["ops"], summary="Liveness / readiness")
def health() -> dict:
    """`ready` is true once the vector store has loaded at startup."""
    return {"status": "ok", "ready": "agent" in _state}


@app.post(
    "/answer",
    response_model=AnswerResponse,
    tags=["answers"],
    summary="Answer a rules question",
    description="Send a natural-language question (optionally with `[Card Name]` "
    "tokens). Returns the answer, an `answered` flag (false = the rules didn't "
    "cover it), citations with resolved rule/glossary text, the card data used "
    "with its relevance-selected rulings, and a debug panel.",
)
def answer(req: AnswerRequest) -> AnswerResponse:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="empty question")
    agent, chunk_map = _state["agent"], _state["chunk_map"]
    # Bound what a thread can cost: last 12 turns, each clipped to 4k chars.
    history = [{"role": t.role, "content": t.content[:4000]} for t in req.history[-12:]]
    request_id = uuid.uuid4().hex
    t0 = time.monotonic()
    # Hold the lock across answer() AND the reads of its last_* attributes --
    # another request could overwrite them the moment the lock is released.
    with _lock:
        ans = agent.answer(req.question, history=history)
        cards = list(agent.last_cards or [])
        retrieved = list(agent.last_retrieved or [])
        rewritten = agent.last_rewritten
        selection = dict(agent.last_ruling_selection or {})
        unresolved_refs = list(agent.last_unresolved_refs or [])
        uncited_success = bool(getattr(agent, "last_uncited_success", False))
    latency_ms = int((time.monotonic() - t0) * 1000)

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
    def _index() -> FileResponse:
        return FileResponse(_frontend_dir / "index.html",
                            headers={"Cache-Control": "no-cache"})

    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
