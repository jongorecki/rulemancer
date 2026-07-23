# Handoff — Rulemancer: post-lab, prompt-v3 decision pending (supersedes the prior handoff; git has the old one)

You are picking up **Rulemancer** (package `rulesagent`): a RAG agent over the
MTG Comprehensive Rules with a per-card rulings mini-RAG, FastAPI backend,
shipped chat frontend. Repo: `D:\Job_hunt\mtg-rules-bot`. Job-hunt
proof-of-work (applied AI / RAG) — **articulation beats polish**: every
decision must be explainable cold. End goal: public demo on Fly.io.

## Read these FIRST (source of truth, not this summary)

- `DESIGN.md` — build plan and **Working Rule 0: plan before code.** No
  implementation until a written plan exists and Jon has reviewed it.
- `DECISIONS.md` — every non-obvious decision with reasoning.
- `LOG.md` — raw build log (2026-07-22 has two big entries; git log is the
  full trail).
- `docs/plan-prompt-tuning.md` — **THE PENDING DECISION** (see Queue #1).
- `docs/plan-limitations-and-deploy.md` — the roadmap (L1-L8 + Fly.io track).
- `docs/feature-ideas.md` — Jon's approved feature shortlist + evidence.
- `docs/competitive-landscape.md` — six-bot teardown, README positioning raw
  material.
- `.superpowers/sdd/progress.md` — session ledger (task/commit/review trail).

## How Jon works (respect these)

- **Rule 0: plan before code.** Write the plan, get his review, THEN build.
- **Token economy:** Opus orchestrates/judges; Sonnet implements against
  approved specs (subagent-driven: fresh implementer -> fresh-context
  reviewer -> fix loop, evidence not assertions); Haiku for mechanical
  fixes; Fable ONLY for the hardest design work with Jon's explicit OK
  (used once: the prompt-tuning plan).
- **Do-not-delegate:** eval questions, gold, grading criteria, reading
  failures are Jon's. The transitive-grading pipeline extends his reach
  (judge routes same/different; his verdicts transfer); it never grades.
- **Judge instrument is FROZEN:** judge_bakeoff's prompt + gpt-5-mini
  (95% agreement, 0/21 live audit errors). Rewording it invalidates the
  bakeoff AND the transitive pipeline. Do not touch.
- **Commit per slice** on master; end commit messages with the
  Co-Authored-By line. **Verify UI by PIXELS** (screenshots; Jon's screen
  is final — browser pane can't resize, so 375/768 checks are his).
- **SINGLE-WRITER RULE IS RETIRED** (L3 shipped): caches are SQLite/WAL,
  concurrent eval runs + server are safe. Still check `git status` for a
  parallel session's edits before implementing (two sessions collided on
  L3 and converged by luck).
- **NEVER assert an MTG or model fact from memory.** Ground in CR/Scryfall/
  live check. Model pricing: never from memory (claude-api skill).

## State update — 2026-07-23 (READ THIS FIRST; supersedes the 07-22 state below where they conflict)

- **Prompt v3 SHIPPED** (f9a70fe, review approved, verbatim-verified): all
  six §1 bullets + two §2 rewriter bullets from docs/plan-prompt-tuning.md
  (APPROVED with amendments — see its header). answer.py PROMPT_VERSION=3;
  rewrite.py "v2" with **v1 selectable** (rewrite_version param, cache-keyed);
  Part B union togglable (ruling_query_mode="raw"|"union").
- **c004 RULED (flipped)**: sonnet + v4-pro c004 partial→correct-with-note.
  Baselines now sonnet 46/50, v4-pro 44/50 (verdict files updated, notes
  retained; DECISIONS.md has the rubric meaning). §1d's c004 predicted
  flips are off the board.
- **A/B sweep COMPLETE** (Task 2: 9c20ffb, be2a286, 2491c8c, fix b0b9546;
  review Approved): conditions B (gen-v3+rw-v1+raw), C (v3+v2+raw),
  D (v3+v2+union) × 2 runs × 6 arms. 1,798/1,800 rows clean; persistent
  exception gemini-flash-lite D c003 (both runs, provider-side).
  **CRITICAL DISCOVERY**: retrieval embedding (Voyage) is nondeterministic —
  30-34% of questions can draw different chunks between captures. Fixed
  within the A/B by an assemble-once prompt cache
  (evals/answers/_prompts_{B,C,D}.json; both runs share a capture).
  Condition A's prompts were never captured → A-vs-new comparisons carry
  unquantifiable retrieval-draw variance; Task 3 tags affected questions.
- **Task 3 IN FLIGHT** (judge-compare vs A verdicts via frozen pipeline,
  stable-flip intersection, groundedness tripwire, Jon's grading queue +
  evals/report-v3-ab.md). Outputs: evals/judge_pairs_v3ab_*.json.
- **Opus-grader calibrations DONE** (v1: 22805b2 — API, $3.41, a billing
  mistake, see below; v2: b0af49b prep + f5968cc results — in-session
  subagents on Jon's subscription): v1 76.4% / v2 78.3% primary agreement,
  boundary 83.3%→86.7%, vs frozen-judge bar 95%. VERDICT: Opus is an
  audit lens, NOT a delegate grader. Card data fixed the coherent-but-wrong
  class (16 disagreements resolved) but introduced 12 new ones.
- **BILLING RULE (Jon, 2026-07-23)**: batch Claude-labor (grading,
  experiments) runs as in-session subagents on Jon's SUBSCRIPTION, never
  scripted Anthropic API calls; API credits are for the product/eval arms
  only. (Also in workspace memory.)
- **Plans APPROVED by Jon 2026-07-23, implementation pending:**
  - docs/plan-q029-empty-answer-guard.md (BOTH slices + amendment: also
    FLAG answered:true+zero-citations — surfaced, not retried; skip
    PROMPT_VERSION bump; broad except with graceful degrade). Unblocked
    the moment Task 3 lands (generation is done; only judging remains).
  - docs/plan-scryfall-local-bulk.md (fully ruled: threshold 90 tunable,
    measure-first ambiguity guard, refresh window −8/+21 days around set
    release [prerelease = release−7, Jon], no_refresh stays documented
    no-op, admin = background+status-poll+ADMIN_TOKEN, **Scryfall
    licensing SIGNED OFF** — DECISIONS.md). Implement AFTER the A/B
    concludes and its follow-ups settle.
- **New gotchas**: background bash jobs die at ~1hr (kill-and-resume
  cycles; runners need resume logic — Task 2's has it). evals/answers/
  still has no .gitignore entry (discipline-only). gpt-5-mini D r2 +
  repairs used --retry-errors (now model-guarded).
- **Pending Jon after Task 3**: grade the stable-flip queue; v3 go/no-go;
  Part B ship call (D vs C); L2 generator call; RulesGuru-150 (ruled: after
  this A/B).

## State (all of 2026-07-22; commits through ~075d3f6+ — git log is the trail)

- **L3 SQLite caches SHIPPED** (09683fc + 9127491 review fixes): five
  whole-file caches -> data/cache.db (WAL, per-op conns), queries/feedback
  JSONL -> tables, telemetry logs on failure. 6/6 gates incl. byte-identical
  retrieval eval. Deploy blocker #1 cleared.
- **L1 cross-refs SHIPPED** (92fa295..30ac5db): mechanism correct + tested
  (18 TDD tests), organic ranks untouched, last_crossref debug field.
  HONEST NULL RESULT: none of q016/c011/q029 were retrieval gaps (gold was
  already in pool) — generation is the quality frontier. Part B
  (--ruling-query union) MEASURED: 16/25 -> 20/25 load-bearing rulings,
  0 regressions, ships only on Jon's call.
- **Ticker slice** (36f0994): sequential 13-phase turn walk, 2500ms; new
  homepage example (trample+deathtouch). q001 identity flake fixed
  (80d02c7, frozen-store double, 5x green).
- **Six-arm HUMAN-GRADED table** (the L2 evidence; c004 ruling 2026-07-22
  flipped sonnet + v4-pro c004 partial→correct-with-note, see DECISIONS.md):
  sonnet-v2 46/50 · v3.2 43 · v4-pro 44 · v4-flash 42 · gpt-5-mini 42 ·
  gemini 38 (10 wrong — stable-but-wrong). All arms answered from
  byte-identical prompts, so gaps are pure generation. Mechanical
  citation-proxy MISLED on extremes (gpt-5-mini underrated, gemini
  overrated) — proxy is triage only, cards are invisible to it (gold=[]).
- **Transitive grading pipeline SHIPPED** (819bbc7, ae5d5d8, b4deac2;
  review approved): evals/judge_arm_pairs.py routes pairs vs Jon's graded
  reference; 250 -> 56 hand-grades (78% cut); audit 0/21 errors.
  Roll-up: manual wins; >10% audit disagreement = arm falls back manual.
  Adapter evals/build_arm_review.py; combined queue
  evals/build_combined_diff.py (--split fans a combined export back out).
  All verdicts committed: evals/verdicts_*_{manual,final}.json (075d3f6).
- **Sonnet cost estimated** (not measured): ~$0.55-0.85 per 50-run
  (~129k in / ~28k out at $3/$15; tokenizer + adaptive-thinking
  uncertainty). = ~25x v3.2, ~50x v4-flash. Decision dashboard:
  data/parsed/l2-model-decision.html (gitignored, rebuildable from the
  committed verdict files if needed).
- **Fable prompt-tuning plan WRITTEN** (docs/plan-prompt-tuning.md, DRAFT):
  6 surgical system-prompt bullets (~520 tok; F1 card-role, F2 mana
  semantics, F4 multiplayer, F5 assumptions, F7 card-text-overrides,
  F3/F6 clarity) + 2 rewriter bullets + Jon's oracle-text-to-rewriter
  pass-through as its OWN section (structurally sound; cards already
  resolve before rewrite in current code; needs cache-key fingerprint;
  NEW risk: Haiku role-drift; recommended as separate flag/version).
  Predicted flips: 3x c002, 3x c014, 2x c004, v4-flash:c016 (highest
  conf), 3x q014 (hedged). Riskiest: multiplayer bullet vs groundedness
  rule. c012 finding: NO multi-card bug in build_prompt — suspect
  get_card() fuzzy-match or stale scryfall cache entry (fresh tracing
  session needed).
- **Feature shortlist approved** (docs/feature-ideas.md): clarify-then-
  escalate (#1, WotC-patent-validated), legality chip, misconceptions
  gallery, permalinks (post-L3), CR-gap flag, donate link, CR auto-update
  pipeline (#8, gated blue-green design). Rewriter's `clarification` =
  rules-talk translation, NOT a clarifying question.

## THE QUEUE (priority order)

1. **Jon reads docs/plan-prompt-tuning.md and rules on prompt v3.**
   Controller's recommendation on record: adopt the 6+2 wording bullets as
   v3, A/B via the existing harness (re-run arms, transitive judge-compare
   v3 vs v2, hand-grade diffs only); hold oracle-text as its own slice.
2. **Pending Jon micro-decisions:** ~~c004 partial-flips~~ RULED 2026-07-22:
   FLIPPED to correct-with-note (see DECISIONS.md — sonnet 46/50, v4-pro
   44/50 now; verdict files updated, note retained; §1d's c004 predicted
   flips are off the board); L2 generator call (sonnet
   45/50 at ~25x cost vs v3.2 43/50 — may reasonably wait for v3 results);
   Part B union ship; RulesGuru-150 extension (~$10).
3. **Code slices needing plans (Rule 0):** q029 empty-answer guard
   (answered:true + blank text slips _degenerate(); production answer
   path); c012 Scryfall fuzzy-match/stale-cache tracing.
4. **Deploy track (L5):** streaming, per-IP rate limit + budget breaker,
   CORS, Dockerfile, Fly.io (index builds ON host — CR text in a public
   image is redistribution; keys as secrets). Then feature shortlist +
   README (absorb the six-arm table + audit story + competitive landscape;
   draft README exists, deliberately uncommitted).

## Environment & gotchas

- Python via `uv run` / .venv\Scripts\python.exe; PYTHONIOENCODING=utf-8
  everywhere; `.env` has VOYAGE/ANTHROPIC/OPENROUTER keys.
- **Pinned:** voyage-4-large embeddings; generation claude-sonnet-5 (until
  L2 call); rewriter claude-haiku-4-5; judge gpt-5-mini (FROZEN).
- **Jon runs run.py on port 8000 — never bind/kill it.** Test elsewhere.
- Detached background jobs report phantom exit code -1 after completion —
  read the output log tail, not the code (runs print "... DONE" markers).
- Browser pane: resize_window claims success but doesn't resize; file://
  blocked — serve via throwaway `python -m http.server 890x`, kill after.
- OpenRouter backend retries 429s/truncations (d810287) — first-attempt
  reliability still differs per model (ops table in the dashboard).
- evals/answers/ is untracked (big data); verdicts_*.json in evals/ ARE
  tracked. data/parsed/ is gitignored (generated).
- Untracked leftovers Jon may keep/delete: README.md (draft, deliberately
  uncommitted), branding-preview/, design-system/, evals/merge_arm_gap.py
  (parallel session's tool), sh.exe.stackdump (junk), evals/answers/
  gap_*.json (junk artifacts of a stopped run).
- Grading UI: evals/build_grading_ui.py (--in review-format json). Six
  per-arm HTMLs + grading_all_diff.html in data/parsed/. Exports download
  as answer_verdicts.json (browser appends " (N)").
- doc metadata rule, resume rules, token economy live in
  D:\Job_hunt\CLAUDE.md — applies here too.
