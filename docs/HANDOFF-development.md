# Handoff — Rulemancer: model lab, demo polish, road to public deploy (supersedes the prior handoff; git has the old one)

You are picking up **Rulemancer** (package `rulesagent`): a RAG agent over the
MTG Comprehensive Rules with a per-card rulings mini-RAG, a FastAPI backend,
and a shipped chat frontend. Repo: `D:\Job_hunt\mtg-rules-bot`. It's a
job-hunt proof-of-work (applied AI / RAG) — **articulation beats polish**:
every decision must be explainable cold. End goal now in scope: a public demo
on Fly.io anyone can use from a link.

## Read these FIRST (source of truth, not this summary)

- `DESIGN.md` — build plan and **Working Rule 0: plan before code**. No
  implementation (yours, Jon's, or a subagent's) until a written plan for the
  slice exists and Jon has reviewed it.
- `DECISIONS.md` — every non-obvious decision with reasoning. Read all of it.
- `LOG.md` — raw build log. (2026-07-22 entries may lag the commits — git log
  for the real trail.)
- `docs/plan-limitations-and-deploy.md` — THE ROADMAP (L1-L8: every known
  limitation with its approved fix, Fly.io deploy track, the L8 batch spec).
- `docs/plan-openrouter-models.md` — the model lab (generation A/B + judge).
- `docs/plan-rulesguru-import.md` — the 150-question external eval set.
- `docs/API.md` + `docs/openapi.json` — backend contract (pre-L8; the spec
  export needs a refresh, it lacks tldr/followups/request_id/feedback).

## How Jon works (respect these)

- **Rule 0: plan before code.** Write the plan, get his review, THEN build.
- **Token economy:** Opus orchestrates/scopes/judges; Sonnet implements
  against an approved spec; Haiku for bulk. Subagent delegation is Jon's
  standing preference for scoped implementation work.
- **Do-not-delegate:** eval questions, gold, grading criteria, reading
  failures are Jon's. The RulesGuru auto-judge extends his reach; it does
  not replace his ownership of "what counts as correct."
- **Commit per slice**; end commit messages with the Co-Authored-By line.
- **NEVER assert an MTG or model fact from memory.** Ground in the CR,
  Scryfall, or a live check. This has burned confident claims repeatedly
  (Tibalt-cascade is the flagship story — it's in the draft README).
- **Verify UI by PIXELS.** DOM metrics pass while pixels are broken (the
  wordmark symbol/use bug proved it). Screenshots at 375/768/1280 in BOTH
  themes, or say plainly it is unverified. Jon's screen is the final gate.
- **SINGLE WRITER RULE:** never run two generation/cache-writing processes
  at once — Jon sometimes has parallel Claude sessions in this repo (one
  imported RulesGuru today while this session ran the lab; a transient
  rewrite-cache EOFError was observed THREE times). Whole-file caches
  corrupt. Check `git status` for another session's live edits before
  running anything that generates or writes caches. L3 (SQLite) fixes this
  properly and is the next major slice.

## Current state (commits through `a1df551` + `a27c4e0`; git log is the trail)

- **Engine:** pure vector voyage-4-large over 3,617 chunks; always-on Haiku
  rewriter (temp=0); generation claude-sonnet-5 pinned, top-15, structured
  Answer{text, tldr, citations, answered, suggested_followups}. Multi-turn:
  history as a transcript INSIDE the single user message (real prose turns
  destabilized structured output ~50% -> fixed, 5/5) + degenerate-draw retry.
- **PROMPT_VERSION = 2** (constant in generate/answer.py): tldr,
  suggested_followups, rulings labeled "[Card Name ruling #N]" (original
  Scryfall index, both mini-RAG and dump paths) and cited by that label.
  Bump the constant on ANY prompt/schema change and note it there.
- **prompt build:** `build_prompt()` extracted, byte-identity guarded by
  tests/fixtures/prompt_identity.json + tests/test_prompt_identity.py.
  Intended prompt changes = regenerate the fixture (capture script pattern
  is in the test file; c015's retrieval wobbles at a boundary rank —
  the test asserts only what assembly owns).
- **API:** /answer returns tldr, suggested_followups, request_id; appends
  to data/logs/queries.jsonl (model + PROMPT_VERSION + latency stamped);
  POST /feedback (up/down + optional note) -> feedback.jsonl. index.html
  served Cache-Control: no-cache (stale-page class of bugs closed).
- **Frontend:** Simple/Full tabs (Simple=tldr default; pre-upgrade saves
  degrade gracefully), follow-up pills that submit, thumbs feedback wired
  to /feedback, chat bubbles (user accent-tinted right, bot bordered
  bubble), fluid inline wordmark (NO symbol/use — it clip-rendered),
  overlay flyout under 720px, static capability pills flattened to text.
  **Jon has NOT yet visually confirmed the responsive pass** — the browser
  pane's screenshot compositor died mid-verification (4 real screenshots +
  DOM assertions exist; his refresh is the final check).
- **OpenRouter lab (docs/plan-openrouter-models.md):**
  `generate/openrouter_backend.py` (pinned model, allow_fallbacks:false,
  temp=0+seed=42 where accepted — gpt-5-mini rejects temperature — strict
  Answer json_schema, served model/provider/cost recorded).
  `evals/run_openrouter_arm.py` (--model/--questions/--variance; captures
  the byte-identical prompt via a recording fake client, zero Anthropic
  calls). `evals/judge_agreement.py` (any OR model vs stored sonnet
  verdicts). **Outside judge DECIDED: gpt-5-mini at 95% agreement**
  (judge_bakeoff.py, commit 538cc5f).
- **Arms in flight:** a background run of 5 arms x (full 50-question set +
  variance 3x3) was launched 2026-07-22 (~an hour): deepseek-v4-pro,
  deepseek-v4-flash, deepseek-v3.2, gemini-2.5-flash-lite, gpt-5-mini.
  Outputs: evals/answers/openrouter_<slug>.json + variance_<slug>.json.
  **CHECK COMPLETENESS FIRST** (50 rows/arm; v4-flash upstream 429s are
  expected as honest error rows — the backend is single-shot no-retry;
  re-run failed questions if needed). Known already: v4-flash shows
  draw variance even at temp=0+seed — temp-0 determinism is NOT a given;
  the variance reports are decision data, not a formality.
- **RulesGuru set (other session, commit a27c4e0):** evals/rulesguru.jsonl,
  150 questions, human gold answers + citation gold; fetch script;
  judge_rulesguru.py auto-judges via gpt-5-mini; run_eval --match-both
  (any 40% vs all 16% @5 best-arm — a much harder set). Smoke: 2 real bot
  errors in 5.
- **Packaging done:** MIT LICENSE (+WotC/Scryfall notices), uv.lock
  committed, SVG wordmark (Citadel TTF removed — donationware, no
  redistribution), name standardized Rulemancer, branding/ committed,
  Makefile targets real, index builder defaults to voyage-4-large only.
  **README.md drafted but deliberately UNCOMMITTED** — twice voice-tuned
  (Claude-tell research applied: no kickers, no negative parallelism, no
  bold-led lists); it waits to absorb the lab table + demo link.

## THE QUEUE (priority order)

1. **Verify the arm run** (see above), re-run gaps. Then Jon's pending
   green-light: extend all arms + sonnet over the RulesGuru 150 with
   auto-judging (~$10 total incl. sonnet) — his hand-grading stays capped
   at the curated 50.
2. **Sonnet re-grade arm** on prompt v2 via run_answer_eval.py (current,
   post-RulesGuru form) — this IS the L4 re-grade.
3. **Live verification batch** (server restart + quiet tree): L8 smoke
   (tabs/pills/thumbs -> log rows land), Jon's visual pass on the
   responsive UI, Grist-thread rewrite mis-anchor check (LOG 2026-07-22
   thread; fix is committed but unverified live).
4. **Jon's grading session:** curated 50 x 6 arms in the grading UI
   (evals/build_grading_ui.py may need a small adapter for arm-output
   format). Output: L2 generator decision (cost/variance/quality) + L4
   closed + the README table.
5. **L3 SQLite caches** (deploy blocker #1; also migrates queries/feedback
   JSONL stubs to tables). Then **streaming**, **guards** (per-IP rate
   limit, daily budget breaker, CORS), **Dockerfile**, **Fly.io deploy**
   (index builds ON the host — a public image with CR text is
   redistribution; keys as host secrets).
6. **L1 cross-ref expansion** (multi-hop: follow "see rule X" refs in
   retrieved chunks, append <=5; then the rewrite-as-ruling-query arm) —
   parallel-anytime quality slice.
7. **To-do #9 card display** (hover card images — never Secret Lair unless
   only printing, most common English; real mana symbols via Scryfall
   symbology) — pre-deploy polish, needs its own plan.
8. **README finish**: absorb lab table + RulesGuru numbers + demo link,
   then the clean-clone "stranger runs it" test, then commit. Also decide
   branding-preview/ + design-system/ (loose, uncommitted).

## Environment & gotchas

- Python via `uv run`; `.env` has VOYAGE_API_KEY + ANTHROPIC_API_KEY +
  OPENROUTER_API_KEY. Windows: PYTHONIOENCODING=utf-8 everywhere.
- **Pinned:** embeddings voyage-4-large; generation claude-sonnet-5 (until
  the L2 decision); rewriter claude-haiku-4-5; judge gpt-5-mini (bakeoff).
- **Jon runs run.py on port 8000** — never bind/kill it; test on another
  port (run.py auto-kills ITS OWN stale instance per-port). Static files
  hot-serve; Python changes need HIS restart. index.html is no-cache now.
- Generation runs >120s go in background commands. Eval/gen runs are
  SEQUENTIAL (single writer rule above).
- The live answer path embeds queries FRESH (Voyage wobble) — only the
  eval path has frozen query embeddings. Don't chase phantom retrieval
  diffs (the identity-test docstrings explain).
- Browser pane may deny new localhost origins, and its screenshot
  compositor can die (pane must be visibly displayed to composite) —
  verify with curl + driving JS, and say when pixels are unverified.
- doc metadata rule, resume rules, etc. live in D:\Job_hunt\CLAUDE.md
  (project-wide, applies here too).
