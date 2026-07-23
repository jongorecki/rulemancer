# Execution tasks — prompt-v3 A/B + Opus-grader calibration

Implements the APPROVED designs in `docs/plan-prompt-tuning.md` (§4 amended,
Jon's rulings 2026-07-22) and `docs/plan-opus-grader-calibration.md`.
Controller decomposition; the two plan docs are the requirements authority.

## Global constraints (bind every task)

- The six §1 bullets and two §2 bullets are applied **verbatim** from
  `docs/plan-prompt-tuning.md` — no rewording, no extra edits to either
  SYSTEM prompt beyond what §1/§2 specify.
- `answer.py` `PROMPT_VERSION`: 2 → 3. `rewrite.py` `PROMPT_VERSION`:
  `"v1"` → `"v2"`; any change to a rewriter SYSTEM text must be reflected
  in the cache key via the version string (the cache serves stale rewrites
  forever otherwise).
- The gpt-5-mini judge prompt and `judge_bakeoff` artifacts are FROZEN —
  no edits, ever.
- Jon runs `run.py` on port 8000 — never bind or kill it; test elsewhere.
- `PYTHONIOENCODING=utf-8` on every Python invocation.
- Never assert an MTG or model fact from memory; ground in code, corpus,
  or live checks.
- Commit per slice on master with the session's Co-Authored-By trailer.
- Detached background jobs report phantom exit code -1 — read the output
  log tail ("... DONE" markers), not the exit code.

## Task 1 — Prompt v3 + rewriter v2 + selectable rewriter version

**Requirements source: `docs/plan-prompt-tuning.md` §1 (all of 1a–1f), §2a,
§2b, §4 items 1–2. Read those sections in full; the bullet texts there are
the exact strings to insert.**

1. `src/rulesagent/generate/answer.py`: apply §1a–1f at the exact insert
   points §1 specifies (the [1]–[11] numbering maps to the current SYSTEM
   bullets). Bump `PROMPT_VERSION` 2 → 3.
2. `src/rulesagent/retrieve/rewrite.py`: keep the current SYSTEM text
   available as version `"v1"`; add the §2a and §2b bullets as version
   `"v2"` (insert points per §2a/§2b). Make the version selectable per
   call/agent config (default `"v2"`), with the selected version string
   flowing into the rewrite cache key exactly as `PROMPT_VERSION` does
   today. Condition B of the A/B runs gen-v3 + rewrite-v1, so v1 must
   remain runnable, byte-identical to today's prompt.
3. Regenerate `tests/fixtures/prompt_identity.json` per `build_prompt`'s
   docstring so the byte-identical-prompt guarantee holds for v3.
4. Confirm (and expose if not already runnable per-invocation) the Part B
   ruling-query union toggle from the L1 slice — condition D needs it ON
   for a full eval run while B/C run with it OFF. Report how it's toggled.
5. TDD where a behavior changes (rewriter version selection, cache-key
   inclusion); full test suite green; report suite counts.

## Task 2 — Run conditions B, C, D (2 runs each, all six arms)

**Requirements source: `docs/plan-prompt-tuning.md` §4 items 3–4.**

1. Conditions: B = gen-v3 + rewrite-v1 + union OFF; C = gen-v3 +
   rewrite-v2 + union OFF; D = gen-v3 + rewrite-v2 + union ON.
2. For each condition: one retrieval/prompt-assembly pass over the 50
   questions (`evals/questions.jsonl` 31 + `evals/cards.jsonl` 19), then
   generation for all six arms — `claude-sonnet-5` native path,
   the five others via `evals/run_openrouter_arm.py` — **twice per arm**
   (two independent generation runs from the same assembled prompts).
   Read `evals/run_answer_eval.py` / `evals/run_openrouter_arm.py` first
   and reuse their existing flow; do not invent a parallel harness.
3. Output naming must encode condition and run:
   `evals/answers/<arm>_<condition>_r<1|2>_*.json` or the existing naming
   scheme extended equivalently — reported explicitly.
4. Record in the run report: the determinism pins actually in force
   (temperature/seed per model, the gpt-5-mini exception), per-run
   failure/retry counts, and rough token/cost totals.
5. Runs are long: run detached, poll the log tail for the DONE marker.

## Task 3 — Judge-compare, stable-flip intersection, morning queue

**Requirements source: `docs/plan-prompt-tuning.md` §4 items 5–7 and §3's
detection column.**

1. For every condition-run, judge-compare against the condition-A verdicts
   on file (`evals/verdicts_*_final.json`) using the existing
   `evals/judge_arm_pairs.py` pipeline unchanged.
2. Stable-flip rule: a flip counts only if both runs of that condition
   agree on it; unstable flips are logged separately, excluded from
   go/no-go arithmetic and from Jon's queue.
3. Groundedness tripwire (§3, row 1c): for every v3 answer with
   `answered: true`, check every citation appears in that prompt's
   provided rule-number set. If the harness already has this check, use
   it; if not, implement it as part of this task. Report the count per
   arm/condition vs the condition-A rate.
4. Build Jon's morning queue with `evals/build_combined_diff.py`
   (question-grouped, stable flips only) and write a summary report:
   per-arm correct-counts per condition vs baselines (sonnet 46, v4-pro
   44, v3.2 43, v4-flash 42, gpt-5-mini 42, gemini 38), predicted-flip
   scorecard from §1/§6 (c004 pair off the board), go/no-go arithmetic,
   tripwire counts, unstable-flip list.

## Task 4 — Opus-grader calibration

**Requirements source: `docs/plan-opus-grader-calibration.md` in full —
it is the complete spec (comparison set, blind inputs, rubric, metrics,
output paths). Model pricing for the cost line comes from current
published pricing, never memory.**
