# Results — the parametric-knowledge control (no rules, no retrieval, no card data)

**Status: 90 of a planned 150 rows, halted deliberately, not a failed run.**
Generation was stopped twice by design, not by error: once after a background
process died mid-run at row 70 (the 70 rows already on disk were verified
intact and reused, not regenerated), and once by Jon's own call to top up
with a stratified 20-row sample rather than push straight to the remaining
80. Both stops are documented below with exact before/after file checks.

## What the number means, before any table

Arm B (`evals/verdicts_derivability_B_human.json`, 137/150 = 91.3%) hands the
model gold CR rules and full card rulings, retrieval off, and scores whether
it reaches the reference answer. Section 2 of
`docs/spec-gold-sufficiency.md` names the threat that test can't see on its
own: Opus-5 already knows a lot of Magic from training, so a "pass" on arm B
might mean the gold rules did real work, or might mean the model already knew
the answer and the rules were decoration. This control is arm B with rules
set to zero — no gold, no retrieved context, no card data, just the bare
question — to tell those two cases apart, row by row.

**On this sample (n=90, not yet the full 150), 59 of 90 rows -- 65.6% [95% CI
55.3-74.6%] -- are CONFOUNDED: the control got the row right with nothing
but the question, so arm B's "pass" on that row proves nothing about
whether the gold rules were needed.** That is the headline, and it comes
with two important qualifications before it gets quoted anywhere:

1. **It varies enormously by difficulty**, from 86.7% confounded at Level 0
   down to 30% at Corner Case (see the per-level table below) — the eval set
   *can* measure retrieval quality, just mostly at the harder levels.
2. **The sample isn't yet proportional to the full corpus** (see
   [Representativeness](#representativeness-the-sample-is-still-not-proportional)).
   The 65.6%/59.5% figures below are the best current estimate, not a
   finished measurement.

## Provenance

| | |
|---|---|
| Questions run | 90 of 150 in `evals/questions_rulesguru150_v3.jsonl` — all 30 Level 0, all 30 Level 1, 10 of 30 Level 2, 10 of 30 Level 3, 10 of 30 Corner Case |
| Model / effort | `claude-opus-5`, effort `high`, max_tokens 32768 — **matches arm B exactly** (confirmed by reading `evals/answers/derivability_B_goldonly.json`'s row 0 before building this arm) |
| Prompt | Custom `CONTROL_SYSTEM` in `evals/build_norules_prompts.py`, `system_version` tag `norules_control` (registered at runtime via monkeypatch in `evals/_run_norules_control.py`, not a source edit) |
| User content | `Question: {stripped question text}` — same bracket-stripped question text every arm's generator sees, nothing else |
| Answers | `evals/answers/norules_control.json` (70 rows) + `evals/answers/norules_control_topup.json` (20 rows, disjoint ids) |
| Judge | `openai/gpt-5-mini`, prompt digest `b54fbdb95565abf8` — **byte-identical to arm B's judge prompt**, confirmed by recomputing the hash of `ablate_gold.JUDGE_SYS` + the RulesGuru scenario addendum and matching it against `verdicts_derivability_B.json`'s recorded digest |
| Verdicts | `evals/verdicts_norules_control.json` (70) + `evals/verdicts_norules_control_topup.json` (20) |
| Compared against | `evals/verdicts_derivability_B_human.json` (137/150, human-verified; `still_incorrect` lists the 13 true failures used as arm B's per-row ground truth here) |

## Why this stopped at 90, not 150 — the two halts

**Halt 1 (unplanned): a background process died at row 70.** Two attempts to
run the full 150 in the background terminated with exit code 127 and empty
stdout logs (the harness appears to kill very-long-lived background bash
processes in this environment; both failures produced zero captured output
even though real work had happened). Before doing anything else, the
existing output was verified rather than assumed: `evals/answers/
norules_control.json` held 70 unique rows, every one carrying `model:
claude-opus-5`, `effort: high`, `system_version: norules_control`, and a
real `usage` block — no partial or corrupted rows. `run_answer_eval.py`'s
resume guard (`_load_resumable()`) reuses those 70 rows byte-for-byte on any
future run with identical CLI flags; it only regenerates (and would
overwrite) if a flag like `--model`/`--effort`/`--system-version`/
`--max-tokens` mismatches. Jon's call at that point: judge the 70 rather
than push further.

**Halt 2 (deliberate): the 70 rows are a biased prefix.**
`questions_rulesguru150_v3.jsonl` is sorted by level, so the first 70 rows
are exactly Level 0 (30) + Level 1 (30) + the first 10 of Level 2 — **zero
Level 3 and zero Corner Case**, the two levels where arm B struggles most and
where the confound is smallest (see below). Jon approved a stratified 20-row
top-up: 10 Level 3 + 10 Corner Case, taking every 3rd question within each
30-question level block (indices 0, 3, 6, ..., 27) rather than the first 10
of each block, specifically because the original 10-question cost pilot had
already been burned once by prefix bias (see [Cost](#cost)). Selected ids:

```
Level 3:       rg1280 rg2599 rg127 rg543 rg608 rg559 rg247 rg1953 rg204 rg725
Corner Case:   rg5193 rg807 rg470 rg289 rg60 rg100 rg1933 rg5539 rg1014 rg1555
```

The top-up was written to a **separate file**
(`evals/answers/norules_control_topup.json`), never to
`norules_control.json`, specifically so a `--qids` subset run could not
trigger the resume guard's mismatch path and silently overwrite the 70
banked rows. Verified before and after: `norules_control.json` was 535,341
bytes / 70 rows immediately before the top-up started and 535,341 bytes / 70
rows immediately after — byte-identical, untouched.

## Cost

```
10-question pilot (all Level 0, first 10 ids in file order)   $0.7570 total = $0.0757/q
  -> naive projection over 150                                 $11.35  (looked safe against the $12 ceiling)

actual cost, 70 rows (L0 x30, L1 x30, L2 x10)                  $7.2971 total = $0.1042/q
  -> same projection re-run over 150                           $15.64  (OVER the $12 ceiling)
     by level: L0 $0.0758/q, L1 $0.1196/q, L2 $0.1434/q -- cost rises with
     level because harder questions produce more output tokens even with
     shorter input (no rules block to begin with), and the pilot's all-L0
     draw undersampled exactly the expensive end of the corpus

20-question stratified top-up (L3 x10, Corner Case x10)
  4-question sub-pilot                                          $0.4694 total = $0.1174/q
  -> projected over 20                                          $2.35  (under the $5 ceiling)
  actual, all 20                                                 $2.4026 total = $0.1201/q

TOTAL Anthropic generation spend, 90 rows                        $9.6997
```

**The lesson repeated here on purpose:** the first pilot was 10 for 10 Level
0 questions because the question file is sorted by level and the pilot took
a raw prefix. That drew the *cheapest* end of the cost distribution and
under-projected the full run by nearly 40% ($11.35 projected vs. an actual
$15.64 rate). The second pilot (this session) deliberately spread across
each level block instead of taking a prefix, and its projection ($2.35 for
20) landed within 2% of the actual ($2.40).

Judge cost (`openai/gpt-5-mini` via OpenRouter, 90 calls) is not separately
metered by `rulesagent.pricing` (that module prices the Anthropic generation
model only); based on this project's established gpt-5-mini judge rates
elsewhere it is on the order of cents, not dollars, and does not materially
change the total against the $12 generation ceiling that governs this task.

## The 2x2, pooled (n=90)

| | arm B RIGHT | arm B WRONG |
|---|---|---|
| **control RIGHT** | 59 — CONFOUNDED | 0 — gold hurt |
| **control WRONG** | 28 — gold did real work | 3 — hard either way |

- **Confounded (control right, arm B right): 59/90 = 65.6%, 95% CI
  [55.3%, 74.6%]** (Wilson interval). These rows can't tell you the gold
  rules did anything — the model reached the reference answer from the bare
  question, no rules attached at all.
- **Gold did real work (control wrong, arm B right): 28/90 = 31.1%.** These
  are the rows where arm B's pass is genuine evidence the supplied rules
  mattered.
- **Gold hurt (control right, arm B wrong): 0/90.** Not observed anywhere in
  this sample — no row where stripping every rule out produced a *better*
  answer than handing gold in.
- **Hard either way (control wrong, arm B wrong): 3/90 = 3.3%** —
  `rg241`-shape rows (all at Level 2, 3, or Corner Case in this sample): the
  model gets it wrong whether or not it's given the rules.

## Per level

| Level | n (sample) | confounded | 95% CI | control wrong / armB right | gold hurt | hard either |
|---|---|---|---|---|---|---|
| 0 | 30 | 26 (86.7%) | [70.3%, 94.7%] | 4 | 0 | 0 |
| 1 | 30 | 21 (70.0%) | [52.1%, 83.3%] | 9 | 0 | 0 |
| 2 | 10 | 4 (40.0%) | [16.8%, 68.7%] | 5 | 0 | 1 |
| 3 | 10 | 5 (50.0%) | [23.7%, 76.3%] | 4 | 0 | 1 |
| Corner Case | 10 | 3 (30.0%) | [10.8%, 60.3%] | 6 | 0 | 1 |

**Easy vs. hard, the actual question this control exists to answer: yes, the
confound is concentrated at the easy end.** Level 0 and Level 1 — the
public-facing, heavily-documented corner of Magic's rules — are 86.7% and
70.0% confounded respectively: on most of those rows, arm B's pass is not
evidence retrieval (or gold) did anything, because the model already knew
the answer cold. Level 2 through Corner Case drop to 30-50% confounded, well
below the easy levels and with confidence intervals that don't overlap
Level 0's. **This means the eval set still measures retrieval quality where
it matters most — at the harder levels — even though a large share of the
easy levels cannot detect it at all.** The L2/L3/Corner Case samples are
only 10 rows each, so those per-level figures carry wide intervals (roughly
±25-30 points) and should be read as directional, not precise.

## Corpus-weighted confounded fraction

Weighting each level's confounded fraction by its share of the full 1,409-
question corpus (`docs/HANDOFF-development.md`'s L0=207, L1=565, L2=406,
L3=162, Corner Case=69):

| Level | corpus share | sample n | confounded fraction |
|---|---|---|---|
| 0 | 207/1409 = 14.7% | 30 | 86.7% |
| 1 | 565/1409 = 40.1% | 30 | 70.0% |
| 2 | 406/1409 = 28.8% | **10** | 40.0% |
| 3 | 162/1409 = 11.5% | **10** | 50.0% |
| Corner Case | 69/1409 = 4.9% | **10** | 30.0% |

**Corpus-weighted confounded fraction: 59.5%.** Nearly 70% of the corpus's
weight sits on Level 1 + Level 2, and Level 2's 40.0% rests on only 10 rows
(95% CI [16.8%, 68.7%] at the row level) — the single biggest source of
uncertainty in this weighted number. Level 1 alone is 40% of the corpus and
already has a full 30-row sample, so it anchors the estimate reasonably
well; Level 2/3/Corner Case together carry nearly half the weight (45.2%) on
30 total rows combined. Treat 59.5% as a reasonable point estimate, not a
tight one.

## Representativeness: the sample is still not proportional

| Level | full corpus (150) | this sample (90) |
|---|---|---|
| 0 | 30 (20.0%) | 30 (33.3%) |
| 1 | 30 (20.0%) | 30 (33.3%) |
| 2 | 30 (20.0%) | 10 (11.1%) |
| 3 | 30 (20.0%) | 10 (11.1%) |
| Corner Case | 30 (20.0%) | 10 (11.1%) |

The stratified top-up fixed the worst problem (zero Level 3 / Corner Case
coverage), but the sample is still over-weighted toward Level 0/1 (33.3%
each vs. a proportional 20%) and under-weighted at Level 2/3/Corner Case
(11.1% each vs. 20%). Since confound rate falls as level rises, this bias
pulls the unweighted pooled figure (65.6%) *upward* relative to a
proportional sample — which is exactly why the corpus-weighted figure
(59.5%, using the real corpus shares rather than this sample's shares) is
the more defensible number to quote, and why even that number should be
treated as provisional until the remaining 60 rows (20 more each of Level 2,
3, and Corner Case) are run.

## Limitations, stated plainly

- **Not a clean single-variable control.** Arm B uses `SYSTEM_V3` verbatim
  (system_version `3`); this arm uses a different system prompt
  (`system_version` tag `norules_control`) because `SYSTEM_V3` repeatedly
  instructs the model to answer *only* from supplied rules and to decline
  when they're insufficient — instructions that make no sense with nothing
  supplied. Adapting the framing was unavoidable, but it means this control
  differs from arm B in **two** things at once: the removal of all rules/
  card data, and the system prompt wording. A failure or pass here cannot be
  attributed to the rules-removal alone with full confidence; it's the best
  approximation available without literally handing the model an
  instruction to ignore its own training.
- **90 of a planned 150.** Level 0/1 are fully sampled (30/30 each); Level
  2/3/Corner Case are 10 of 30 each. The remaining 60 rows were not run —
  this was a deliberate stop for cost and sampling-design reasons, not a
  crash or an abandonment.
- **Zero "gold hurt" rows observed (control right, arm B wrong) in this
  sample** — worth confirming stays at zero (or doesn't) once the full 150
  are in, since spec section 2 flags that cell as the more surprising
  result if it appears.
- **Same judge, verified matching**, not merely asserted: `judge_prompt_
  sha256` in both `evals/verdicts_norules_control.json` and
  `evals/verdicts_norules_control_topup.json` is `b54fbdb95565abf8`,
  identical to arm B's own recorded digest.
- **Kind-matched to arm B by construction**: both arms have
  `retrieved_rule_ids` empty on every row (no retrieval ran in either), so
  `evals/build_metrics_history.py`'s `classify_arm()` labels both `oracle`
  kind — the two are comparable arm-kinds, not a pipeline-vs-oracle
  mismatch of the kind that has burned this project before
  (`docs/HANDOFF-development.md`'s point 5).

## Files

```
evals/build_norules_prompts.py                    prompt builder (CONTROL_SYSTEM + question-only user text)
evals/_run_norules_control.py                     thin wrapper registering system_version "norules_control"
evals/judge_norules_control.py                    judge (openai/gpt-5-mini, arm B's exact judge prompt)
evals/answers/_prompts_norules_control.json       frozen (system, user) prompts, 150 questions
evals/answers/norules_control.json                70 generated rows (L0 x30, L1 x30, L2 x10)
evals/answers/norules_control_topup.json          20 generated rows (L3 x10, Corner Case x10)
evals/verdicts_norules_control.json               70 verdicts, judge_model recorded
evals/verdicts_norules_control_topup.json         20 verdicts, judge_model recorded
docs/results-norules-control.md                   this file
```
