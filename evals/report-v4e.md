**STATUS: Task 5 evidence complete.** Judge-compare batch (4 condition-runs x 50
questions, gpt-5-mini judge, 200 calls) finished; `evals/v4_c_reference_*.json`
(the derived condition-C reference, sanity-gated), `evals/judge_v4_summary.json`,
`evals/groundedness_v4.json`, and Jon's grading queue
(`data/parsed/grading_v4_queue.html`, `evals/v4_stable_flip_index.json`) are all
final. **No grading has been done and no go/no-go call is made here** -- the
judge only routes ("this changed"), it never grades ("this is now right/wrong"),
and per task instructions this report stops before that line.

# Prompt-v4 + condition-E -- judge-compare, stable-flip report (Task 5)

Source: `docs/plan-v4e-execution-tasks.md` Task 5. Inputs: Task 1-4's six v4
answer runs (`evals/answers/sonnet_v4_r{1,2}_{rules,cards}.json`,
`evals/answers/gpt-5-mini_v4_r{1,2}.json`), the v3 A/B's graded artifacts
(`evals/judge_v3ab_summary.json`, `evals/verdicts_v3ab.json`,
`evals/verdicts_sonnet-v2_final.json`, `evals/verdicts_gpt-5-mini_final.json`),
and the frozen judge pipeline (`evals/judge_arm_pairs.py`).

Scripts (new, this task, none of which touch the frozen judge or grading UI):
`evals/build_v4_c_reference.py`, `evals/judge_v4.py`, `evals/groundedness_v4.py`,
`evals/build_v4_queue.py`.

**Decision set:** `claude-sonnet-5` (cell: v4) and `openai/gpt-5-mini` (cell: v4
default only). The `effort=high` cell was killed on latency (DECISIONS.md
2026-07-24) and never run -- it is not graded and its absence is not treated as
missing data, per the plan.

---

## 1. Reference derivation -- the most important step, shown in full

Each v4 run is judge-compared against **its arm's graded condition-C (v3)
outcome**, not condition A. That reference does not exist as one file -- it was
derived: **condition-A baseline, with condition C's Jon-graded stable flips
substituted in**, built once per run (r1, r2) since condition C itself has two
runs and a flipped question's graded verdict can differ slightly between them.

- **sonnet**: `evals/judge_v3ab_summary.json` shows **0 stable flips in
  condition C for sonnet** (confirmed by direct read, not assumed) -- so its
  condition-C reference is condition-A's baseline, unchanged, in both runs.
  `verdicts_sonnet-v2_final.json` already bakes in the 2026-07-22 c004
  correct-with-note ruling (checked directly: `c004` reads `"correct"` in that
  file), so no extra step was needed there.
- **gpt-5-mini**: condition C's stable flips are `c011, c014, c015, q012, q017`
  (read from `judge_v3ab_summary.json`). For each, the reference's answer text
  and verdict are gpt-5-mini's actual condition-C run text plus Jon's graded
  verdict from `verdicts_v3ab.json` (id `gpt-5-mini_C_r{run}:{qid}`). Every
  other question keeps its condition-A answer/verdict unchanged.

**Sanity gate (printed by `build_v4_c_reference.py`, all four combinations
checked):**

| Arm | Run | Derived correct-count | Expected | Result |
|---|---|---:|---:|---|
| sonnet | r1 | 46/50 | 46 | **PASS** |
| sonnet | r2 | 46/50 | 46 | **PASS** |
| gpt-5-mini | r1 | 45/50 | 45 | **PASS** |
| gpt-5-mini | r2 | 45/50 | 45 | **PASS** |

The gate passed on both arms and both runs -- the reference is trustworthy to
build the rest of this report on. (Worked arithmetic for gpt-5-mini, showing
why the run-to-run graded-verdict disagreement on `c015` -- r1 graded `wrong`,
r2 graded `partial` -- doesn't change the count: baseline 42/50, and of the 5
flipped ids only `c011`, `c014`, and `q012` newly grade `correct` (+1 each,
baseline was `wrong`/`partial`/`partial`); `c015` grades non-correct either way
(+0); `q017` was already `correct` (+0). Net +3 -> 45, reproduced identically
for r1 and r2.)

Reference files: `evals/v4_c_reference_sonnet_r1.json`,
`_sonnet_r2.json`, `_gpt-5-mini_r1.json`, `_gpt-5-mini_r2.json`.

## 2. Judge-compare method and run

Reused `judge_arm_pairs.py`'s `call_judge()` / `decide_transfer()` **imported
directly, unmodified** -- same call as `judge_v3ab.py` already makes, only the
reference side changed (condition-C-derived instead of condition-A). No
reword, no model substitution.

**Run:** 200 judge calls (2 arms x 2 runs x 50 questions), completed in 116s,
**0 judge errors, 0 exceptions** in either arm (all 50 candidate rows per run
had a non-empty answer to judge, including the `answered:false`/decline rows --
their decline explanation text is still non-empty and gets judged like any
other answer). Per-run files: `evals/judge_pairs_v4_sonnet_r1.json`,
`_sonnet_r2.json`, `_gpt-5-mini_r1.json`, `_gpt-5-mini_r2.json`. Rollup:
`evals/judge_v4_summary.json`.

| Arm | same | different | judge_error | exception |
|---|---:|---:|---:|---:|
| sonnet r1 | 50 | 0 | 0 | 0 |
| sonnet r2 | 50 | 0 | 0 | 0 |
| gpt-5-mini r1 | 47 | 3 | 0 | 0 |
| gpt-5-mini r2 | 46 | 4 | 0 | 0 |

## 3. Stable/unstable flip breakdown

Rule unchanged from the v3 A/B: a flip counts only if **both** runs of the
cell judge "different" against the reference. `judge_v4_summary.json`:

| Arm | no_flip | stable_flip | unstable_flip | judge_error | exception |
|---|---:|---:|---:|---:|---:|
| sonnet | 50 | **0** | 0 | 0 | 0 |
| gpt-5-mini | 45 | **2** | 3 | 0 | 0 |

- **sonnet: zero divergence of any kind** across all 50 questions in both
  runs -- not even an unstable one. This is a cleaner result than the v3 A/B
  produced for sonnet (which had 2-3 unstable flips per condition); here v4
  changed literally nothing the judge could detect in sonnet's answers versus
  its own condition-C outcome.
- **gpt-5-mini stable flips: `c002`, `c011`** (both reference verdict
  `correct` -- `c002` via condition A unchanged, `c011` via the condition-C
  flip). **Unstable: `q008`, `q022`, `q028`** (all reference verdict `correct`
  too).
- **Every one of the 5 touched ids (stable + unstable) for gpt-5-mini had a
  `correct` reference verdict.** No id moved *toward* correct in this
  comparison -- the only possible movement, pending Jon's grading, is away from
  correct or a same-conclusion reword. This bounds gpt-5-mini's v4-default
  ceiling at its condition-C baseline of 45 (see section 7) -- v4 shows no
  evidence of a net gain for gpt-5-mini's default cell in this data, only risk.
- `q008`'s instability is explained by the decline pattern in section 5, not
  independent content drift: r1 answered it, r2 declined it.

## 4. Groundedness re-check

Reused `groundedness_v3ab.py`'s `check_row()` / `citation_kind()` **unmodified
(imported)**, pointed at `cond="v4"` for sonnet + gpt-5-mini only (the v4
decision set), same rule-number/ruling-citation-vs-provided-context check as
the v3 A/B.

**Result: 0 instances / 0 distinct questions flagged**, across 4
condition-runs (200 rows, all `answered:true` rows checked) --
`evals/groundedness_v4.json`.

This is well inside the signed-off v3 level (7 instances / 5 distinct
questions across all 6 v3 arms x 3 conditions x 2 runs, DECISIONS.md
2026-07-24) -- no spike, no discussion trigger needed. Caveat: this slice's
`n` is much smaller (200 answered-true rows here vs. 900 in the v3 batch, and
only 2 of the 6 original arms), so a zero here is a weaker signal than a zero
would be at the v3 batch's scale -- noted for calibration, not as a concern.

## 5. Decline counts -- the specific watch item

Per-run `answered:false` counts, gpt-5-mini only (sonnet declined 0 questions
in every condition-C and v4 run):

| Run | Declined ids | n |
|---|---|---:|
| Condition C r1 | q008, q011, q014, q016 | 4 |
| Condition C r2 | q011, q014, q016 | 3 |
| **v4 r1** | **q014, q016** | **2** |
| **v4 r2** | **q014, q016, q008, q011** | **4** |

- **q014 and q016 decline in BOTH v4 runs** -- stable, matching the task's
  framing exactly. These are the documented retrieval-gap questions where the
  gold rule is never retrieved; an honest decline there is plausibly *correct*
  under strict grading, not a regression -- Jon's call, not this report's.
- **q008 and q011 decline only in v4 r2** -- unstable, matching the task's
  framing exactly (q008 also drives one of the two unstable content flips in
  section 3).
- **Comparing against condition C:** gpt-5-mini already declined q014/q016 in
  both condition-C runs too -- v4 changed nothing about that pattern. The
  q008/q011 run-to-run inconsistency also already existed in condition C (r1
  declined both, r2 declined neither of them, though r2 did decline q014/q016
  as usual). **Net read: v4 does not appear to have made gpt-5-mini
  meaningfully more or less cautious about declining** -- the decline
  footprint under v4 sits inside the range condition C already showed, not
  outside it.

## 6. Predicted-flip scorecard: c014, c002, c011, c012, q008, q014, q019, q026

`docs/plan-prompt-v4.md` section 6 names these eight ids as "the specific
items to re-check in the diff review" (not a per-bullet predicted-direction
table like the v3 plan had -- v4's plan doesn't commit to a predicted verdict
per id). Anomaly worth flagging: section 2's own bullet-4d text says it
"targets `c019` and `q008`", but section 6's list has `q019`, not `c019` -- a
plan-internal inconsistency, not something this report resolves. Both are
cross-checked below anyway.

| Qid | Bullet (informal) | Sonnet ref verdict | Sonnet v4 stable divergence | gpt-5-mini ref verdict | gpt-5-mini v4 stable divergence |
|---|---|---|---|---|---|
| c014 | 4a mana arithmetic | partial | no (same) | correct (cond-C flip) | no (same) |
| c002 | (v3 1a target, re-checked) | correct | no (same) | correct | **yes -- stable flip** |
| c011 | 4c assumption disclosure | correct | no (same) | correct (cond-C flip) | **yes -- stable flip** |
| c012 | (v3 1d-adjacent, re-checked) | wrong | no (same) | wrong | no (same) |
| q008 | 4d intended-question (per section 6) | correct | no (same) | correct | unstable only (r2) |
| q014 | 4b multiplayer | correct | no (same) | partial | no (same) |
| q019 | (per section 6; section 2 names c019 instead) | correct | no (same) | correct | no (same) |
| q026 | 4e/1f direct-answer-first, quality only | correct | no (same) | correct | no (same) |

**Reading this table:**

- **Sonnet: flat on all 8 named ids, and flat on all 50 questions overall
  (section 3).** v4's flagship fix (4a mana arithmetic) did not move sonnet's
  `c014` off `partial` in this comparison -- worth flagging plainly since c014
  was the headline problem v4 was built to fix. It also didn't regress
  anything.
- **gpt-5-mini: `c014` also stayed flat -- but was already `correct` going
  into v4** (via the condition-C flip), so there was no more room to move on
  this specific id for this arm.
- **The only two named ids that moved for gpt-5-mini (`c002`, `c011`) were
  already `correct`** -- so within this scorecard, v4 shows zero confirmed or
  even *possible* gains, only two candidate losses pending Jon's grading.

## 7. Per-cell correct-counts vs. derived baselines

| Cell | Baseline (derived condition-C) | Stable flips | Floor | Ceiling |
|---|---:|---:|---:|---:|
| sonnet / v4 | 46/50 | 0 | 46 | 46 |
| gpt-5-mini / v4 default | 45/50 | 2 (`c002`, `c011`, both ref `correct`) | 43 | 45 |

- **Sonnet is trivially flat** -- 0 stable flips (in fact 0 divergence of any
  kind), so the no-go-1 rule (no net sonnet regression) cannot possibly fire
  on this evidence; there is nothing here for Jon to even grade for sonnet.
- **gpt-5-mini's range is 43-45** -- both stable flips touch previously-correct
  questions, so the ceiling is flat at the baseline (45) and the floor is
  45 minus 2 if both grade away from correct. **There is no scenario in this
  data where gpt-5-mini's v4-default count exceeds its condition-C baseline of
  45.** Confirming the actual floor-vs-ceiling outcome requires Jon's grading
  of the 2-question queue (section 8).
- **The condition-E `effort=high` gate** ("does gpt-5-mini reach >=46?") was
  never run (killed on latency, DECISIONS.md 2026-07-24) -- moot for that
  reason, but note additionally that even the *default*-effort v4 cell shows
  no upward room over 45 in this comparison, so the L2 generator-switch
  question continues to rest entirely on gpt-5-mini's default-effort
  performance, unchanged from before this slice.

## 8. Jon's grading queue

Built with `evals/build_v4_queue.py` (same pattern as `build_v3ab_queue.py`,
adapted for v4's 2-arm x 1-condition shape; `build_grading_ui.py` used
unmodified via subprocess). **Stable flips only** -- the 3 unstable ids
(`q008`, `q022`, `q028`) are excluded from the queue and from all arithmetic
above, per the stable-flip rule, and are listed for visibility only in
sections 3/9.

- **Output:** `data/parsed/review_v4_queue.json` +
  `data/parsed/grading_v4_queue.html`
- **2 stable-flip (arm, question) pairs, 4 rows** (one row per run per pair):
  `gpt-5-mini/v4 r1 vs derived-C:correct -- c002`,
  `gpt-5-mini/v4 r2 vs derived-C:correct -- c002`,
  `gpt-5-mini/v4 r1 vs derived-C:correct -- c011`,
  `gpt-5-mini/v4 r2 vs derived-C:correct -- c011`.
- Stable-flip index (machine-readable, for any downstream tooling):
  `evals/v4_stable_flip_index.json`.
- Sonnet contributes 0 rows -- nothing to grade for that arm.

## 9. Unstable-flip list (excluded from arithmetic and the queue, logged for visibility)

| Arm | Unstable ids | Reference verdict | Note |
|---|---|---|---|
| gpt-5-mini | q008 | correct | Also the unstable decline (section 5) -- r1 answered, r2 declined; the "different" judge verdict on this id may just be reflecting the decline vs. a full answer, not independent content drift |
| gpt-5-mini | q022 | correct | No decline involved in either run |
| gpt-5-mini | q028 | correct | No decline involved in either run; this was a `retrieval_noise_suspect`-adjacent id in the v3 A/B's own analysis (worth a second look if it recurs) |

Sonnet: none.

## 10. Measured prompt size (repeating the plan's flagged number, not the stale estimate)

Per `docs/plan-v4e-execution-tasks.md`'s own measured-after-Task-1 section:
**v3 SYSTEM 5,189 chars -> v4 SYSTEM 10,045 chars, +4,856 chars ~= +1,215
tokens**, against the **~+360 tokens** `docs/plan-prompt-v4.md` section 4
originally budgeted before ruling #6 (Scryfall's full Colors-and-Costs
symbology, hybrid families, `{C/P}`/`{H}`/`{L}`/`{Y}`/`{Z}`, and the
mana-value counting rule) was layered on. The prompt roughly doubled versus
what was priced. This report's own answer files confirm the shape:
`_prompts_v4.json`'s system string is 10,045 chars for all 50 questions
(verified directly, matching the plan's number), and its average
per-question user block is **9,149.5 chars** -- so a typical v4 call sends
roughly **19,195 chars of combined system+user input**, more than the SYSTEM
string alone.

## 11. Cost per cell

**gpt-5-mini / v4 default -- measured, from the run files' own `summary`
field** (no estimation needed):

| Run | n | answered | parse_failures | total_cost |
|---|---:|---:|---:|---:|
| r1 | 50 | 48 | 0 | $0.29207705 |
| r2 | 50 | 46 | 0 | $0.26739225 |
| **Cell total** | 100 | 94 | 0 | **$0.5595** |

**sonnet / v4 -- no usage field in either run file** (confirmed directly:
`sonnet_v4_r1_rules.json` row keys have no `usage`; same for the cards file
and both r2 files). Rather than invent a number, here is a clearly-labeled
**rough estimate** built from character counts and current sonnet pricing
(pulled from the claude-api skill, not memory: **`claude-sonnet-5`, intro
pricing through 2026-08-31 is $2.00/$10.00 per MTok input/output**, standard
pricing $3.00/$15.00):

- Input per question ~= system (10,045 chars, measured) + avg user (9,149.5
  chars, measured) ~= 19,195 chars ~= **~4,800 tokens** at a ~4 chars/token
  rule of thumb (NOT a real tokenizer count -- no `count_tokens` call was made
  for this estimate, per the constraint against scripted API calls outside
  the eval/judge billing path).
- Output per question ~= 1,701 chars (r1 avg, measured) / 1,771 chars (r2
  avg, measured) ~= **~425-445 tokens** at the same rule of thumb.
- **Confirmed: no prompt caching was used** -- `run_answer_eval.py` sends no
  `cache_control` anywhere (checked directly), so every one of the 100
  sonnet calls paid full input price; there is no cache-read discount to
  subtract.
- Rough per-question cost: (4,800 x $2 + 435 x $10) / 1,000,000 ~= **$0.014**.
  Per 50-question run ~= **$0.70**; **cell total (2 runs) ~= $1.40**.

**This sonnet figure is a labeled estimate, not a measured cost** -- it
should not be quoted as precisely as the gpt-5-mini figures above, which come
straight from the run files' own recorded `usage`/`cost` fields.

## 12. Self-review

- **Sanity gate is the load-bearing check and it passed on all 4
  combinations** (section 1) -- the reference-derivation logic reproduces the
  published 46/45 baselines exactly, including the arithmetic showing why the
  r1-vs-r2 graded-verdict disagreement on gpt-5-mini's `c015` doesn't move
  the count either way.
- **Frozen artifacts respected:** `call_judge()`/`decide_transfer()` imported
  from `judge_arm_pairs.py` unmodified; `check_row()`/`citation_kind()`
  imported from `groundedness_v3ab.py` unmodified; `build_grading_ui.py`
  invoked as an unmodified subprocess. No edit touched
  `judge_bakeoff.py`, any `verdicts_*.json`, or
  `answer.py`/`openrouter_backend.py`.
- **What this report does NOT claim:** it does not assign a verdict to
  either stable flip (`c002`, `c011` for gpt-5-mini) -- only that the judge
  detected divergence from the derived condition-C reference on both runs.
  It does not make the go/no-go call, and it does not decide anything about
  the L2 generator switch or condition-E's dead `effort=high` cell beyond
  restating its already-recorded latency verdict.
- **Residual risk / things worth a second look in the queue:** (1) sonnet's
  complete lack of divergence (0/50, not even unstable) is either a
  genuinely clean no-op for this arm or a sign the judge is under-sensitive
  to sonnet's wording style specifically -- nothing in this task's evidence
  distinguishes the two, and it's worth Jon eyeballing a couple of sonnet's
  v4 vs condition-C answer pairs directly even though there's no queue row
  forcing him to; (2) both of gpt-5-mini's stable flips, and all 3 unstable
  ones, land on already-correct questions -- so this slice's evidence is
  asymmetric (downside-only, no observed upside) even though it's a small
  sample (5 of 50 ids touched at all); (3) the plan's own section 2/6
  inconsistency on `c019` vs `q019` (noted in section 6) is worth a one-line
  correction to `docs/plan-prompt-v4.md` whenever that document is next
  touched, though fixing it wasn't in scope here.

---

**Then stop, per task instructions:** no grading was performed, no go/no-go
call was made, nothing was committed.
