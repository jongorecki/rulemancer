# Plan — fix the limitations + deploy a public demo

Jon's direction (2026-07-22): don't just document the limitations, plan the
fix for each. End state: Rulemancer hosted on the internet where anyone can
demo it from a link, no install.

Each limitation below gets: the fix, why this shape, and its verification.
Deployment gets its own section since it turns #2 and #3 from "documented
debt" into blockers.

---

## L1. Multi-hop questions miss (q016 / c010 / c011 / c019 class)

**The fix: deterministic cross-reference expansion at retrieval time.**

The CR is full of explicit "see rule 704.5" pointers, and the parser
preserved them as text. After vector retrieval returns top-15, scan those
chunks' text for rule references (`rule \d+(\.\d+[a-z]?)?` plus bare
`\d{3}\.\d+[a-z]?` patterns), resolve them against the chunk map, and append
up to 5 referenced chunks the pool didn't already contain. No LLM call, no
new variance, no new cost — the document's own link structure does the hop.

Why this shape first: q016's diagnosis was exactly "a thematic query lands on
the casting-process family; the answer is one reference away." An LLM-driven
second-hop query is the fallback if measurement says structural expansion
isn't enough — not the starting point.

The rulings half of the ceiling (c010/c019: the load-bearing ruling is
phrased too differently from the question) gets the already-deferred
**rewrite-as-ruling-query arm**: select rulings against the Haiku rewrite
(which speaks rules language) alongside the raw question, take the union.
One extra cached embedding per question.

**Verify:** the 4 known misses re-run end-to-end (did the answering rule /
ruling reach the pool?); full retrieval eval for regressions (the bar:
aggregate recall holds, zero new per-question regressions); answer eval on
the affected questions, Jon grades.

## L2. Generation draw variance

**The fix is already in flight: the OpenRouter lab is the decision engine.**

The degenerate-retry (shipped, 5/5) treats the symptom. The lab treats the
cause: if a temp=0+seed arm matches sonnet-5 on Jon's grading AND the 3x3
variance spot-check shows byte-stable draws, the generator becomes
configurable (`GEN_BACKEND`), with the switch being Jon's call off the
graded table. If nothing matches sonnet's quality, we keep sonnet + retry
and the README reports the measured tradeoff instead of an apology.

Deployment tie-in: a DeepSeek-class generator is ~20x cheaper per answer,
which changes the economics of a public demo (L5).

**Verify:** graded A/B table + variance report, already specced in
plan-openrouter-models.md.

## L3. Whole-file caches / single worker (DEPLOY BLOCKER)

**The fix: move the four caches to SQLite (stdlib), one db, WAL mode.**

Scryfall, rewrite, ruling-emb, and query-emb caches are all
load-whole-dict/dump-whole-dict today — that's why the API serializes every
request behind one lock. Replace with a small `KVCache` class over sqlite3:
`get(key) -> bytes|None`, `put(key, bytes)`, per-cache table, WAL mode for
concurrent readers + single-writer atomicity. Each existing cache module
keeps its public function signatures; only the storage swaps. One-time
migration script reads the existing pkl/json and writes rows.

Why SQLite over per-key files: atomicity for free, one artifact to mount on
a host, no filename-hashing edge cases, stdlib. (It also mirrors the
Cardomancer stack, which makes the ecosystem story cleaner.)

After the swap the API's global lock stops being a *correctness*
requirement. We may still keep a small concurrency limit for cost control,
but that becomes a knob, not a bug.

**Verify:** migration preserves every existing entry (count + spot-check);
eval reproducibility unchanged (frozen-cache reads return identical values);
a concurrency smoke test (two parallel /answer calls, no corruption, both
correct); full test suite.

## L4. The stale 31/31 grade

**The fix: fold the re-grade into the lab's grading session.**

The sonnet-5 arm of the A/B IS the re-grade: regenerate all 50 questions on
the current shipped config in the same run as the OpenRouter arms, and Jon
grades them side by side in the grading UI (same rubric: faithfulness to
cited text). One grading session closes both the stale-grade limitation and
the A/B comparison instead of two separate passes.

**Verify:** fresh verdicts file for the shipped config; README number
updated with the current grade.

## L5. Public deployment (new)

**Target: a shareable URL where a stranger can ask questions with zero
install.**

### Blockers, in dependency order

1. **L3 first.** Concurrent strangers + whole-file caches = corruption.
2. **Token streaming.** A public visitor watching a blank screen for 40-60s
   will assume it's broken. Stream the answer text (SSE from FastAPI, the
   Answer's structured fields resolved at end-of-stream); the frontend
   renders progressively. This also retires the non-streaming timeout class
   for good.
3. **Abuse + cost guards.** Per-IP rate limit (slowapi or a tiny middleware:
   N answers/hour), a global daily budget breaker (count generation calls,
   hard-stop with a friendly "demo budget hit, come back tomorrow" message),
   CORS tightened to the deployed origin, and the generator model choice
   from L2 (at DeepSeek-class pricing, a full day of abuse costs less than
   a sandwich; at sonnet pricing it needs a tighter cap).
4. **Secrets + data at the host.** API keys as host-side env secrets. The
   INDEX is built on the host at deploy time (one-time fetch of the CR +
   embed run, free tier), NOT baked into a public image — a public Docker
   image containing the full CR text is redistribution, which the repo has
   deliberately avoided. Deploy script = fetch CR, build index, start.

### Hosting candidates (Jon picks)

| Option | Cost | Fit |
|---|---|---|
| Hugging Face Spaces (Docker) | free | Made for ML demos; public link; sleeps on idle (first visitor waits ~30s for wake + store load); no custom domain on free |
| Fly.io | ~$3-5/mo | Always-on small VM, custom domain, volumes for the SQLite caches; slightly more ops |
| Render (free tier) | free | Spins down aggressively on idle; cold starts worse than HF |
| Home server | $0 | Explicitly deferred by DESIGN.md ("that's September") — listed for completeness |

Recommendation: **HF Spaces for the shareable demo now** (free, zero
maintenance, the sleep-wake tradeoff is acceptable for a portfolio link),
with Fly.io as the upgrade path if it gets real traffic or needs a domain.

### Packaging slice

`Dockerfile` (uv-based, one stage) + a `deploy/` doc with the host setup:
env secrets, the index-build-on-first-boot step, health check. The
Dockerfile also strengthens the repo's "stranger runs it" story
independent of hosting.

### Host decision (Jon, 2026-07-22): Fly.io

Always-on small VM, a volume for the SQLite file, custom domain possible.
HF Spaces dropped (sleep-on-idle is wrong for sharing with testers).

## L6. Demo telemetry: query log + feedback buttons (Jon, 2026-07-22)

**Goal:** every public query is reviewable later without Jon sitting
through 30-second answers live, and visitors can flag wrong answers.

- **Query log:** a `queries` table in the same SQLite file L3 introduces —
  request id (uuid, returned in the /answer response), timestamp, question,
  history length, resolved cards, answer text/citations/answered, model,
  latency, token usage/cost, hashed client IP (rate limiting + abuse only),
  feedback fields (below). The demo footer discloses that questions are
  logged.
- **Feedback:** thumbs-up / thumbs-down on every answer; thumbs-down opens
  an optional one-line "what's wrong?" box. POST /feedback {request_id,
  verdict, note} updates the query row. No accounts, no friction.
- **Review loop:** flagged + sampled queries feed Jon's grading UI — public
  usage becomes eval-curation raw material (to-do #8's future pipeline).

## L7. TL;DR / simple-vs-full answer (Jon, 2026-07-22)

**Chosen shape (recommend): a structured `tldr` field, rendered as tabs.**

- `Answer` gains `tldr: str` — one or two plain sentences a player can act
  on, generated alongside the full text (system prompt gains the
  instruction). Structured beats prose-appended: the frontend can tab it,
  the eval can grade it, and the OpenRouter arms inherit it automatically
  since their schema derives from the same contract.
- Frontend: each answer renders "Simple" / "Full" tabs — Simple = tldr
  (+ the answered-state badge), Full = current text + citations drawer.
  Simple is the default tab for the public demo.
- **Sequencing consequence:** a prompt/schema change reworder ALL answers,
  and the lab's sonnet arm doubles as the re-grade. So the tldr change
  lands BEFORE the arms run, and one grading session covers the re-grade,
  the A/B, and the new field. Building it now also fits the calendar: the
  arms are blocked on the RulesGuru session finishing anyway.
- The prompt-identity fixture is intentionally regenerated after the
  prompt change (the change is the point; the fixture guards against
  UNINTENDED drift).

## L8. The schema-window batch (approved 2026-07-22)

Everything that changes the prompt or Answer schema rides ONE batch, so
Jon's single grading session covers the re-grade + the A/B + every new
field. Batch contents:

1. **tldr + Simple/Full tabs** (L7).
2. **suggested_followups**: `Answer.suggested_followups: list[str]` — 2-3
   short next questions; frontend renders clickable pills that send the
   question. Guides demo visitors; every click is another logged query.
3. **Cite rulings by id**: selected rulings are labeled in the prompt
   (`[<Card Name> ruling #<orig-index>] <text>`, original Scryfall index,
   both mini-RAG and dump-all paths) and the system prompt instructs citing
   that label in citations. Enabler for the to-do #2 rulings-recall metric
   (cited label maps to the gold `oracle_id#index`); makes the citations
   drawer precise.
4. **Feedback + logging stub now** (SQLite migration stays in L3):
   `/answer` returns `request_id`; every request appends a row to
   `data/logs/queries.jsonl` (question, history_len, cards, answer fields,
   model, PROMPT_VERSION, latency); `POST /feedback {request_id, verdict:
   up|down, note?}` appends to `data/logs/feedback.jsonl` (joined by id in
   L3). `PROMPT_VERSION` constant lives with SYSTEM in answer.py and bumps
   on every prompt change — feedback across deploys stays interpretable.
5. **Rewrite mis-anchor fix** (to-do #5, no re-grade cost): sharpen the
   conversational-rewrite context instruction in retrieve/rewrite.py —
   earlier turns resolve REFERENCES only; the rewrite targets what the
   FINAL question asks. Single-turn rewrite prompt untouched (eval path).
   Live verification on the Grist thread queues behind the quiet tree.

Explicitly deferred out of the batch: card images/mana symbols (#9),
streaming, /rules/{id} drawer, answer permalinks.

Verification for the batch: compile + full test suite; fixture regen
(intended-change protocol); frontend checked in-browser; live end-to-end
smokes + arm runs wait for the quiet tree.

## Sequencing (recommendation)

1. **Now (in flight):** OpenRouter lab harness -> run arms -> Jon grades
   (L2 + L4 close together).
2. **Next slice:** L3 SQLite caches (the deploy blocker with no
   dependencies).
3. **Then:** streaming (L5.2), guards (L5.3), Dockerfile.
4. **Then:** deploy to the chosen host; smoke the public link.
5. **Parallel/anytime:** L1 cross-ref expansion (pure quality, no deploy
   dependency).
6. **Last:** README absorbs the lab table + the demo link, and to-do #9
   (card images/mana symbols) makes the public demo prettier whenever it
   lands.
