# Handoff — Rulemancer: v5 graded-out, five plans written, RulesGuru live

**Replaces the prior handoff rather than prepending. Git has every earlier
version (`git log -- docs/HANDOFF-development.md`). This session (2026-07-23)
took the v5 grid from "built, not run" to graded, wrote five forward plans,
and stood up the RulesGuru-134 held-out eval. `docs/OVERNIGHT-STATUS.md` is the
live scratch log with the running-work checklist; this file is the durable map.**

## THE STATE IN ONE SCREEN

- **v5 grid: DONE.** 64 generations, 0 errors, four verified-distinct prompt
  digests. Routed by `judge_v5.py` (frozen judge, 64/64 calls clean).
  **Result: v5 fixed nothing on sonnet.** Report: `docs/report-v5-grid.md`.
- **Two Jon rulings recorded** (`DECISIONS.md`, 2026-07-23): symbol injection
  **ratified as production** (production is cell B, not the labelled cell A);
  RulesGuru gold **accepted as canonical** (its authors are certified judges).
- **Rewriter bakeoff: gpt-5-mini does NOT beat shipped haiku.** Report headline
  moved twice AFTER the run — see "the bakeoff saga" below. Report:
  `docs/report-rewriter-bakeoff.md`.
- **Five forward plans written, all Rule-0 gated on your review.** Four live,
  one shelved. See "the five plans".
- **RulesGuru-134 is live as an instrument.** Three eval arms were running at
  session end (see "what's in flight").

## HOW JON WORKS — respect these exactly (unchanged, still load-bearing)

- **Rule 0: plan before code.** Every one of the five new plans is DESIGN ONLY
  and awaits your review. Nothing from them is built.
- **USE SUBAGENTS.** This session ran ~15 in worktrees. Parallelise only across
  disjoint files; forbid `git add -A`/`git add .` in every agent prompt; demand
  pasted evidence not assertions; tell agents to STOP and report if the spec is
  wrong. Multiple agents did exactly that and were right.
- **Do-not-delegate:** eval questions, gold, grading verdicts, reading failures.
  The judge routes; it never grades.
- **Judge instrument FROZEN:** `judge_bakeoff` prompt + gpt-5-mini. Never reword.
- **Never assert an MTG/model fact from memory.** Ground in the repo's CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. Model pricing via the
  claude-api skill (sonnet-5 = $3/$15 per Mtok, used this session).
- **Billing:** Claude-labour on subscription subagents; API spend for
  product/eval arms only. Jon funded Claude console + OpenRouter this session
  specifically for eval runs.
- Commit per slice on master; heredoc messages (backticks in `-m` eat text).
- `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Jon runs the app on
  port 8000 — never bind or kill it.

## WHAT'S IN FLIGHT (session end — check these first)

Three eval arms + one build slice were running when this was written. Check
`docs/OVERNIGHT-STATUS.md` and the heartbeats (`evals/watch_runs.py`):

1. **`rulesguru_answers.json`** — sonnet answers over the 150 RulesGuru Qs.
2. **`rulesguru_gpt-5-mini.json`** — gpt-5-mini answers. **NOTE:**
   `run_openrouter_arm.py` appends `cards.jsonl`, so this file has **170 rows**
   (150 rg* + 20 c0xx). Filter to `rg*` ids for RulesGuru analysis; the c0xx
   rows are harmless extras.
3. **RulesGuru retrieval recall pass** (`run_eval.py --match-both`,
   log in scratchpad) — recall@k for all arms over the 134 golded Qs, both
   match bars. Silent until it prints; verify liveness via cache growth.
4. **Retrieved-id logging slice** (agent `ab7f4bdac6c9d7415`, worktree) — adds
   `retrieved_rule_ids` per row to both runners, schema-additive. **DO NOT
   merge until arms 1-3 finish** (it edits the runners they use). Built to be
   merged, then future runs are diagnosable without capture-file archaeology.

### The first analysis to run once the above land — SEQUENCE MATTERS
The miss-partition needs "was gold in the generator's window", and the window is
`TOP_K=15`. **The recall pass canNOT supply this directly:** its per-question
matrix is hardcoded at **hit@5** (`per_q5`, `hit_at(...,5)`) and `KS=(1,5,10,20,
50)` does not even include 15. Crossing the hit@5 matrix against verdicts would
partition at the wrong window — the same recall@5-vs-15 trap that bit the
bakeoff. Do NOT do that.

Correct sequence:
1. Current RulesGuru arms finish → `judge_rulesguru.py` for answer-quality by
   level, and the recall pass for the **overfit check** (does rw-v2 generalise
   off the 31 it was tuned on — recall@10/@20 bracket the window).
2. **Merge the retrieved-id logging slice.**
3. **Re-run the RulesGuru sonnet answer pass WITH logging** (~$0.30, don't ask).
   Each row now carries `retrieved_rule_ids` — the EXACT set the model saw.
4. Cross each graded-wrong row's gold ids against its own `retrieved_rule_ids`:
   gold present = reasoning failure, gold absent = retrieval failure, gold
   present-but-late = the near-miss bucket. **That** is the clean n=134
   partition, at the true window, and it decides rerank-vs-cost-calculator.

(A quick-and-dirty first read from the hit@5 matrix is fine as a preview, but
label it @5 and don't let it drive the rerank/cost-calc decision.)

## THE FIVE PLANS (all Rule-0, your review gates every build)

Priority order you set, dictated by dependency:

1. **Miss-partition diagnostic** (`docs/plan-miss-partition-diagnostic.md`) —
   retrieval-failure vs reasoning-failure split. Largely falls out of the
   RulesGuru cross-ref above; the 31-set is a cross-check. **Gates plan 4.**
2. **Cost-calculator tool** (`docs/plan-cost-calculator-tool.md`) — your
   "incredible idea". Deterministic mana-cost/value calculator as a tool,
   targeting the confirmed c014 reasoning failure. **Its central SDK unknown is
   RESOLVED** by a spike (`docs/spike-tool-use-findings.md`, `7a7e94b`):
   `messages.parse()` + `tools=` don't conflict, one looped call shape, works on
   both Claude and gpt-5-mini. First real tool-use in the codebase.
3. **RulesGuru as instrument** (`docs/plan-rulesguru-as-instrument.md`) — wire
   the 134-Q held-out set in permanently. Mostly plumbing; `judge_rulesguru.py`
   already auto-judges and reports by level. Running it tonight is the first use.
4. **Rerank-after-rewrite** (`docs/plan-rerank-after-rewrite.md`) — rewrite and
   rerank have NEVER been stacked. Recall@50 is 100%, so it's a ranking problem.
   **Gated on plan 1** — worth ~0 if misses are reasoning failures.
5. **Rulings-recall** (`docs/plan-rulings-recall.md`) — **SHELVED by Jon.**
   Diagnosis kept; build nothing (rests on 3 misses, anchor case is frozen).

## THE BAKEOFF SAGA (why the report was edited three times post-run)

The run finished and said gpt-5-mini ties haiku at recall@5. Then three
questions/plans moved the conclusion, none from re-running:
1. **Jon's temperature question** → only haiku is stabilised (`TEMPERATURE_OK`);
   sonnet/gpt-5-mini can't take `temperature=0`. Measured: unstabilised rw1-haiku
   swings 68-77% at recall@5 — the whole band the arms sit in.
2. **Measured** three seeded gpt-5-mini calls → 3 distinct rewrites. It is
   **unstabilisable** as a rewriter; multi-pass is the only meaningful measure.
3. **Writing the rerank plan** → `TOP_K=15`, so recall@5 is the wrong metric.
   At @10/@20 (bracketing the window) **sonnet's lead vanishes** and gpt-5-mini
   is clearly worse. The tempting positive result was a metric artifact.

Lesson, now a pattern: **every defect this session was found by a differential
check (compare against an independent source), never by the test suite.** Four
prompt-cache/digest/equivalence/metric checks caught everything that mattered;
279 unit tests caught none of it. Tests verify the code believes itself;
differential checks verify reality.

## HELD, NOT DONE — needs your decision

- **Scryfall local-bulk** (`worktree-agent-a818653b08eb516a4`, 5 commits, NOT
  merged). Fully built + tested, but the equivalence check caught a real
  regression: **`Valki, God of Lies` resolves today and misses under local
  bulk** (art-series decoy + "Loki" outscoring it inside the ambiguity margin;
  the guard correctly refuses). Needs a per-face-name lookup tier — a decision,
  in `docs/OVERNIGHT-STATUS.md`. Master is verified clean of this branch.
- **c020 phase 2** — its capture correctly contains injection (production is now
  cell B), so `build_prompts_variant.py` gate 3 rightly refused a clean v3
  derivation. c020 is now a cell-B-vs-D comparison; its derivation must be
  redesigned. Plan-level, not an overnight run. The c020 row IS in
  `cards.jsonl`; c002 is marked non-scoring.
- **Rewriter stability** — to measure the real 68-77% spread, pass-index the
  rewrite cache key (bakeoff-only), then run 3-5 passes. Small slice, awaits you.
- **Citation-filter** (`docs/plan-citation-filter.md`) — the mini-plan you asked
  for exists with an evidence table. Needs your call on product-path vs eval-only.

## STILL QUEUED (untouched this session)
`plan-sso.md` (OIDC), `plan-deploy.md` (budget-breaker is the critical slice),
`plan-scryfall-local-bulk.md` Slice C gold discovery, the c011 stale-ruling data
fix (`docs/plan-c011-stale-rulings.md`, diagnosed, frozen). Slice C gold
discovery build spec: `docs/plan-slice-c-gold-discovery-build-spec.md`.

## ENVIRONMENT & GOTCHAS (session-verified)

- **Worktrees lack gitignored data.** `.gitignore` excludes `data/raw/` and
  `evals/answers/`, so a fresh worktree has no CR corpus (46 env-only test
  failures) and no capture/answer files. Seed `data/raw` by hand if an agent
  needs it; agents that only need tracked files don't.
- **The venv editable-install resolves `rulesagent` from the ORIGINAL repo's
  `src/`, not the worktree's**, unless `PYTHONPATH=<worktree>\src` is set. An
  agent can otherwise silently test unmodified code. Put this in every worktree
  agent's prompt.
- **Tests no longer pollute `_progress/`** (fixed this session, `7c68469`).
- Run output files gained `retrieved_rule_ids` (pending merge) and, earlier,
  `prompts_cache`/`prompts_cache_sha256` — consumers access by known key, so
  additive is safe; an exhaustive key-set comparison would break.
- `str.replace()` silently no-ops on a missed anchor — re-read and assert after
  every edit. Never pipe a long run through `| tail` (masks exit code; bit the
  controller once this session on a clobber-guard check).
- ~15 agent worktrees exist at session end; most are merged and prunable. KEEP
  `a818653b08eb516a4` (Scryfall, unmerged) and any still-running agent's.
- Doc-metadata/resume/token-economy rules live in `D:\Job_hunt\CLAUDE.md` and
  `Token-Economy-Policy.md` — they apply here too.
