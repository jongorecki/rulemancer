# Handoff — Rulemancer continued development

You are picking up the **development** of **Rulemancer** (code package
`rulesagent`): a RAG agent over the MTG Comprehensive Rules. Repo:
`D:\Job_hunt\mtg-rules-bot`. It's a job-hunt proof-of-work (applied AI / RAG)
and AI-103 study prep — **articulation beats polish**: every decision must be
explainable cold.

## Read these FIRST (source of truth, not this summary)

- `DESIGN.md` — the build plan and **Working Rule 0: plan before code**. No
  implementation (yours, Jon's, or a subagent's) starts until a written plan for
  the slice exists and Jon has reviewed it.
- `DECISIONS.md` — every non-obvious decision with reasoning. Read all of it.
- `LOG.md` — raw build log (failures, surprises, numbers).
- `docs/plan-*.md` — per-slice plans (3a rewriting, chunk split, 3b scryfall,
  card-gold-ablation).
- `docs/scryfall-notes.md` — deferred card features.
- Project memory (loaded via MEMORY.md): `plan-before-code`,
  `token-economy-orchestration`, `product-name-rulemancer`.

## How Jon works (respect these)

- **Rule 0: plan before code.** Write a plan, get his review, THEN build.
- **Token economy:** you (Opus) orchestrate/scope/judge; delegate implementation
  to Sonnet subagents with an already-approved spec; Haiku for batched
  fetch/filter. Don't flood context with bulk code. BUT: subagents that poll a
  long background job stall — tell them to run things in the FOREGROUND.
- **Jon owns domain calls:** what counts as correct, gold curation, chunking
  judgments. Never finalize gold yourself.
- **Commit per slice.** End commit messages with the Co-Authored-By line.
- **Test your ideas before building** (the "spike" habit) — it has saved days.

## Current state (ALL committed, `git log` for the trail)

- **Parser + chunker:** 3,617 chunks. **47 tests pass** (`uv run python -m pytest -q`).
- **Retrieval:** pure vector `voyage-4-large`. BM25 (32% recall@5) and hybrid
  rejected (measured); rerank situational. recall@5 ~65% baseline vector.
- **Chunking split:** `Chunk.embed_text` (distinctive — drops a parent's
  preamble when the parent has its own chunk) vs `Chunk.text` (complete — for
  generator + citations). Deterministic recall gains at depth.
- **Query rewriting (#3a):** `src/rulesagent/retrieve/rewrite.py`,
  `claude-haiku-4-5`, **temperature=0**, `PROMPT_VERSION="v1"`, always-on.
  recall@5 ~**70%** (honest MEAN of 5 draws; the noise floor is ~1 question).
  KEY LESSON: rewrites are LLM output = non-deterministic; the "frozen query
  embeddings" reproducibility fix didn't cover the rewrite TEXT. temp=0 cut the
  run-to-run swing from ~9pts to ~1 question. Do NOT quote single-draw numbers.
- **Generation:** `RulesAgent` in `src/rulesagent/generate/answer.py`,
  `claude-sonnet-5`, top-15, structured `Answer{text, citations, answered}`
  (the `answered` flag is the groundedness guard). `max_tokens=8192` (raised
  from 4096 after empty-output crashes on hard questions; a `ValidationError`
  catch degrades to an honest non-answer). System prompt REQUIRES every rule
  mentioned to appear in `citations` (fixed an empty-citations groundedness bug).
- **Answer accuracy: 31/31 correct** (Jon hand-graded, zero hallucinations).
  Grading UI: `evals/build_grading_ui.py` → `data/parsed/grading.html` (open in
  a browser, grade, Export → `answer_verdicts.json`). Verdicts in
  `evals/answer_verdicts.json`.
- **Scryfall enrichment (#3b):** `src/rulesagent/tools/scryfall.py`. Questions
  carry `[Card Name]` or `[oracle_id]` tokens → fuzzy `/cards/named` or
  `/cards/search?q=oracleid:` → oracle text + **all** rulings injected into the
  generator prompt AFTER the rules, before the question (Jon's ordering; rewriter
  never sees card data). `@` is the deferred autocomplete UI; the pipeline parses
  `[brackets]`. Cache: 7-day TTL + `no_refresh` freeze for eval reproducibility.
  Verified live on the Dovin's Veto / Dovescape combined question.
- **Card eval set:** `evals/cards.jsonl` — 5 questions adapted from TheJudge's
  fixtures (`github.com/ChrisMiho/TheJudge`, a friend's app).
- **Gold by ablation:** `evals/ablate_gold.py` — holds card data fixed, removes
  each cited rule, judges if the answer holds (3 trials, majority; judge =
  **Haiku**, validated at 99% agreement with sonnet-5).
- **`match` field extended to `"groups"`** (AND-of-ORs, via `gold_groups`) for
  mixed gold. any/all are degenerate cases and score identically.

## THE FINDING that drives next work (read carefully)

Ablation showed the **rules-RAG was REDUNDANT on 4 of 5 card questions** — remove
every retrieved CR rule and the answer still held, because the card oracle text +
Scryfall rulings + the model's own knowledge of common interactions answered
them. Only **c004** (SBA timing, not in the card text) genuinely needed rules.

This is a **risk to the whole point of the project** (demonstrating a working
RAG). Jon's response: *"we still want to make sure we're pulling the relevant
rulings from the RAG because that's what this whole thing is supposed to show —
the skills to build a working RAG setup."*

## Immediate next tasks (in priority order)

1. **Plan: rulings via RAG relevance-retrieval.** Jon wants card rulings pulled
   by RELEVANCE (a retrieval step over a card's rulings, or rulings as a
   retrievable corpus) instead of the current wholesale-dump of all rulings.
   This (a) demonstrates RAG skill on rulings, (b) makes the RAG do real work on
   card questions, (c) avoids context bloat. **Confirm the exact interpretation
   with Jon first** (rules-RAG relevance vs rulings-as-RAG-corpus — likely the
   latter), then WRITE A PLAN (Rule 0), get review, then build.
2. **Steer the card eval toward c004-shaped questions** — ones whose answer is
   NOT already in the card data, so the rules-RAG is actually exercised. Jon
   writes / crowdsources these (do-not-delegate eval curation). Magic is
   Turing-complete; expect gnarly ones.
3. **Finalize card gold.** c004 is done (groups). c001/c002/c003/c005 currently
   have empty rules-gold (ablation found rules redundant) — Jon decides whether
   to keep them as answer-faithfulness-only tests or replace them.
4. **Build the card-eval harness** (not built yet): card-resolution accuracy +
   rules recall via `run_eval.hit_at` (now groups-aware) + answer faithfulness
   (Jon grades, reuse the grading UI). Frozen Scryfall cache = reproducible.

Then **#4 packaging (Days 10-14):** public repo, README leading with the measured
numbers and the "what I got wrong first" arc (the rewrite-reproducibility catch;
the chunk split that HURT the very question it targeted; retrieval-miss ≠
answer-wrong on q016; the RAG-redundancy finding above), a one-command run for a
stranger, a cheap deployed demo. Lead with **Rulemancer** branding. If time
slips, keep the eval numbers, cut the demo.

## Environment & gotchas

- Python via `uv run`; `.env` (gitignored) has `VOYAGE_API_KEY` +
  `ANTHROPIC_API_KEY`.
- **Pinned models** (reproducible evals): embeddings `voyage-4-large`,
  generation `claude-sonnet-5`, rewriter/judge `claude-haiku-4-5`.
- **Windows:** `PYTHONIOENCODING=utf-8` for console; read/write JSON with
  `encoding="utf-8"` (cp1252 chokes on the CR's curly quotes).
- `data/raw/` and `data/parsed/` are **gitignored** (CR text + caches). Don't
  commit them.
- Generating all 31 answers takes >120s — run as a background command.
- **CACHE RACE (real bug, not yet fixed):** the query-embedding, rerank, rewrite,
  and scryfall caches each load-whole-dict then dump-whole-dict, so **two
  cache-writing processes running concurrently clobber each other**. NEVER run
  two eval/generation processes at once. Proper fix (atomic write / lock /
  per-key files) is deferred tech debt.
- Runs: `uv run python evals/run_eval.py` (retrieval), `.../run_answer_eval.py`
  (answers), `.../ablate_gold.py` (gold ablation).
- Verify Tracker-style/data edits by RE-READING the file, not by asserting.
