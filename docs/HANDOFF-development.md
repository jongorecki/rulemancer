# Handoff — Rulemancer: packaging + polish (supersedes the prior handoff; git has the old one)

You are picking up **Rulemancer** (package `rulesagent`): a RAG agent over the
MTG Comprehensive Rules with a per-card rulings mini-RAG, a FastAPI backend, and
a shipped chat frontend. Repo: `D:\Job_hunt\mtg-rules-bot`. It's a job-hunt
proof-of-work (applied AI / RAG) — **articulation beats polish**: every decision
must be explainable cold.

## Read these FIRST (source of truth, not this summary)

- `DESIGN.md` — build plan and **Working Rule 0: plan before code**. No
  implementation (yours, Jon's, or a subagent's) until a written plan for the
  slice exists and Jon has reviewed it.
- `DECISIONS.md` — every non-obvious decision with reasoning. Read all of it.
- `LOG.md` — raw build log (failures, surprises, numbers). The last ~10 entries
  are the 2026-07-21/22 session this handoff summarizes.
- `docs/plan-*.md` — per-slice plans (rulings-on-demand, card-enrichment-fields,
  api, card-gold-ablation, 3a/3b, chunk split).
- `docs/API.md` + `docs/openapi.json` — the backend contract the frontend uses.

## How Jon works (respect these)

- **Rule 0: plan before code.** Write the plan, get his review, THEN build.
- **Token economy:** Opus orchestrates/scopes/judges; Sonnet implements against
  an approved spec; Haiku for bulk. Don't flood context with bulk data.
- **Do-not-delegate:** eval questions, gold, grading criteria, reading failures
  are Jon's. Draft for his approval; never finalize gold yourself.
- **Commit per slice**; end commit messages with the Co-Authored-By line.
- **Spike before building** — it has repeatedly saved days.
- **NEVER assert an MTG or model fact from memory.** This session logged THREE
  confident memory errors (Extort color identity, Tibalt-cascade, Gogo's
  ability) — each corrected only by pulling the actual CR/Scryfall data. The
  flagship finding: the RAG itself corrected both Jon AND the model on
  Tibalt-cascade (cascade rule 702.85a's resulting-mana-value clause). Ground
  everything; verify by running/rendering, not asserting.

## Current state (ALL committed through `b50af2a`; `git log` for the trail)

- **Retrieval:** pure vector voyage-4-large over 3,617 chunks (embed_text/text
  split). recall@5: 68% base / ~70% with the always-on Haiku rewriter (temp=0,
  quote MEANS, never single draws). Hybrid/rerank measured and rejected.
- **Generation:** claude-sonnet-5 pinned, top-15, structured Answer{text,
  citations, answered}. max_tokens 16384 + retry-once-on-empty (do NOT raise the
  cap — 32768 trips the SDK's non-streaming timeout). System prompt includes the
  "a provided ruling is self-sufficient grounding" line (fixed c015's hedge).
  31/31 rules answers graded correct PRE-prompt-change (re-grade pending, below).
- **Card enrichment:** layout-first, per-face (CardFace: cost/type/P-T/loyalty/
  defense/colors), whole-card layout + mana value + color identity. Scryfall
  cache schema 2 (old entries auto-refetch). Fixed the c011 modal-DFC and c014
  guessed-cost misses.
- **Rulings mini-RAG** (`tools/ruling_retrieval.py`): per-card, top-3 rulings
  above a 0.38 cosine floor (calibrated on real data), replacing the dump.
  Head-to-head: answer quality HELD while ruling context collapsed (35→6, 22→3).
  Load-bearing ruling selected on 12/15; c010/c011/c019 are the semantic-mismatch
  ceiling (rules-RAG carried them anyway).
- **Card eval set:** `evals/cards.jsonl`, 19 questions, all grounded. Gold:
  c004 (groups), c011 = ["702.85a"] (true rules-RAG test), c014 = [] (ruling-
  carried). Each note names the load-bearing ruling (prose — needs structuring,
  below). Ablation harness has `--ids` scoping; judge agreement Haiku-vs-sonnet
  94-99%.
- **API** (`api/main.py`): POST /answer (enriched: cited rule TEXT, cards +
  selected rulings, debug; accepts `history` for multi-turn), GET
  /cards/autocomplete (Scryfall proxy), /health. Single worker + lock (cache
  race). OpenAPI enriched; spec exported.
- **Frontend** (`frontend/`): real implementation of Jon's Claude Design mockup
  (project "Rulesmancer chat interface", via the DesignSync tool) — plum/teal
  brand, wordmark font bundled, welcome/chat states, cited-rules drawer with
  real CR text, @-card picker → [brackets], theme toggle, localStorage history,
  conversation memory end-to-end. `uv run python run.py` serves everything.
- **Conversation memory:** history flows through generator + rewriter +
  card-carryover, gated so the single-turn eval path is byte-identical.

## THE TO-DO LIST (priority order)

1. **#4 Packaging (~1 focused day).** README leading with the measured numbers
   and the "what I got wrong first" arc: BM25 32% → vector 65% → rewrite ~70%
   (and the 77%-was-a-lucky-draw catch); the chunk split that hurt its target
   question; retrieval-miss ≠ answer-wrong (q016); rules-RAG-redundant-on-cards
   ablation; the Tibalt-cascade RAG-corrects-its-builders story; the mini-RAG
   context-cut-with-quality-held result. Repo hygiene: LICENSE, `.env.example`,
   Scryfall/WotC fan-content attribution, confirm data/ gitignored, uv.lock.
   **Font license check:** `frontend/fonts/CitadelOfBlackrose.ttf` is a dafont
   face (likely personal-use-only) — verify before the repo goes public; swap to
   the Cormorant fallback if needed. `run.py` is already the one-command run.
   Also check for a newer CR revision than data/raw's June 2026 file.
2. **Card-eval harness + rulings-recall metric.** Structure each question's
   load-bearing ruling id (`oracle_id#<index>`, currently prose in the notes —
   Jon confirms) and measure `agent.last_ruling_selection` against it; card-
   resolution accuracy; answer faithfulness via `evals/build_grading_ui.py`.
3. **Full re-grade.** The system prompt changed after the 31/31 grade (trust-
   the-ruling line). Regenerate all answers, Jon re-grades via the grading UI.
4. **Outside judge (Jon requested).** Validate a non-Claude judge for the
   ablation/eval harness via OpenRouter (pin the model, allow_fallbacks:false —
   DESIGN's standing rule). Candidates by current pricing: DeepSeek V3.2
   (~$0.14/$0.28 per 1M), Gemini 2.5 Flash-Lite (~$0.10/$0.40), GPT-5-mini
   (~$0.40 in). Method: re-run the ablation agreement tally with the candidate
   beside sonnet-5's verdicts; adopt at ≥95% agreement (Haiku's bar was 94-99%).
   Bonus for the README: a non-Claude judge removes Claude-judging-Claude
   family bias.
5. **Follow-up rewrite mis-anchor** (LOG 2026-07-22): the conversational rewrite
   chased an earlier turn's topic (commander) instead of the follow-up's
   (reanimation). Improve the context instruction in `retrieve/rewrite.py`;
   verify on the Grist/Animate Dead thread in the LOG entry.
6. **Weak-draw variance:** sonnet-5 sometimes returns a parseable-but-weak
   truncated answer (answered=false) that the retry can't catch. Consider one
   retry when answered=false AND citations empty AND text suspiciously short —
   carefully, without defeating the honest-decline guard.
7. **Deferred debt (in DECISIONS/plans):** atomic per-key caches (REQUIRED
   before any concurrency/public exposure), token streaming, auth/rate-limiting
   if public, `image_uri` in responses if the frontend wants it, cite-ruling-by-
   id, rewrite-as-ruling-query arm, multi-hop retrieval (q016/c010/c011/c019
   class), 714.3b → q029 gold (old pending Jon call), rule-drawer
   parent/siblings via a /rules/{id} endpoint, follow-up suggestions.
8. **Eval curation (Jon-owned, ongoing):** more c004-shaped rules-RAG questions;
   unused drafted pool: Ice Cauldron, Illusionary Mask, Lich's Mirror, Splinter
   Twin, Emrakul variants.

## Environment & gotchas

- Python via `uv run`; `.env` (gitignored) has VOYAGE_API_KEY + ANTHROPIC_API_KEY.
- **Pinned models:** embeddings voyage-4-large; generation claude-sonnet-5;
  rewriter/judge claude-haiku-4-5.
- **Windows:** PYTHONIOENCODING=utf-8; JSON with encoding="utf-8".
- **CACHE RACE:** every cache (scryfall, ruling_emb, rewrite, query_emb) is
  load-whole-dict/dump-whole-dict. NEVER run two generation/cache-writing
  processes at once. The API serializes with a lock; evals are your problem.
- Generation runs >120s go in background commands.
- **Jon may have `run.py` live on port 8000.** Never bind or kill his instance —
  test on another port. Static files hot-reload on refresh; Python changes need
  him to restart.
- The browser pane may deny new localhost origins; verify with curl and by
  driving JS on already-open tabs.
- The frontend design source is Jon's Claude Design project ("Rulesmancer chat
  interface", id dea3fd19-0005-4f4c-a60c-cf709dfed7c5) via the DesignSync tool.
