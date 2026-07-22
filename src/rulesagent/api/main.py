"""FastAPI wrapper over RulesAgent (docs/plan-api.md).

Thin -- no RAG logic here. Loads the vector store once at startup, holds one
RulesAgent, and serves an ENRICHED answer (cited rule/glossary text + card data
+ optional debug) plus a Scryfall-proxied card autocomplete for the frontend's
@-picker.

Private demo: no auth / rate-limiting (decision in the plan). A single lock
serializes answer processing so the load-whole-dict/dump-whole-dict caches can't
clobber under concurrent requests -- the atomic-per-key cache fix is the real
solution and stays deferred tech debt.

Run: uv run uvicorn rulesagent.api.main:app --reload
"""

import threading
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rulesagent.generate.answer import RulesAgent
from rulesagent.index.store import VectorStore

REPO = Path(__file__).parent.parent.parent.parent
VECTOR_MODEL = "voyage-4-large"
SCRYFALL_AUTOCOMPLETE = "https://api.scryfall.com/cards/autocomplete"
SCRYFALL_HEADERS = {"User-Agent": "mtg-rules-bot/0.1 (learning project)", "Accept": "application/json"}

_state: dict = {}
_lock = threading.Lock()
# Serializes /answer: RulesAgent.answer writes several whole-file caches, so two
# concurrent calls would clobber them. Single worker + this lock is enough for a
# private demo.


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = VectorStore.load(REPO / "data" / "parsed" / f"vector_{VECTOR_MODEL}.pkl")
    # chunk_map resolves a rule/glossary citation id -> its full text, straight
    # off the store's own chunks (no need to re-parse the CR at startup).
    _state["chunk_map"] = {c.source_id: c for c in store.chunks}
    _state["agent"] = RulesAgent(store)  # ruling_select on; live Scryfall (fresh rulings)
    yield
    _state.clear()


app = FastAPI(title="Rulemancer API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # private demo; tighten to the frontend origin if it goes public
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnswerRequest(BaseModel):
    question: str  # may contain [Card Name] / [oracle-id] tokens from the @-picker


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


class AnswerResponse(BaseModel):
    answer: str
    answered: bool          # False -> the "couldn't ground it" UI state
    citations: list[Citation]
    cards: list[CardOut]
    debug: Debug


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ready": "agent" in _state}


@app.post("/answer", response_model=AnswerResponse)
def answer(req: AnswerRequest) -> AnswerResponse:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="empty question")
    agent, chunk_map = _state["agent"], _state["chunk_map"]
    # Hold the lock across answer() AND the reads of its last_* attributes --
    # another request could overwrite them the moment the lock is released.
    with _lock:
        ans = agent.answer(req.question)
        cards = list(agent.last_cards or [])
        retrieved = list(agent.last_retrieved or [])
        rewritten = agent.last_rewritten
        selection = dict(agent.last_ruling_selection or {})

    citations = []
    for cid in ans.citations:
        chunk = chunk_map.get(cid)
        if chunk is not None:
            citations.append(Citation(id=cid, kind=chunk.kind, text=chunk.text))
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
    )
    return AnswerResponse(
        answer=ans.text, answered=ans.answered,
        citations=citations, cards=cards_out, debug=debug,
    )


@app.get("/cards/autocomplete")
def autocomplete(q: str) -> dict:
    """Proxy Scryfall's autocomplete for the frontend's @-picker. Scryfall wants
    >=2 chars; below that, return nothing rather than hammer it."""
    if len(q.strip()) < 2:
        return {"suggestions": []}
    try:
        r = httpx.get(SCRYFALL_AUTOCOMPLETE, params={"q": q}, headers=SCRYFALL_HEADERS, timeout=10.0)
        if r.status_code != 200:
            return {"suggestions": []}
        return {"suggestions": r.json().get("data", [])}
    except httpx.HTTPError:
        return {"suggestions": []}
