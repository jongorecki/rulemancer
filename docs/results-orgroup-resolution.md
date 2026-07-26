# Results — mechanical resolution of the 25 "needs-Jon" OR-groups

`docs/results-orgroup-repass.md` flagged 25 OR-groups (21 rows) across
`evals/questions_rulesguru150_v3.jsonl` as needing Jon's judgement — the
mixed/unclear category (c) that rule 6's leave-one-out re-pass couldn't
mechanically resolve. This pass applies the test Jon specified for exactly
this situation: **only-one-in**, not leave-one-out.

## The test

An OR-group asserts "any ONE member suffices." For each member `m` of a
flagged group: run `claude-opus-5` gold-only (retrieval OFF, no rewrite,
no tool loop — the same single-shot path `run_answer_eval.
_answer_from_frozen_prompt` uses) with **only `m`** present from that group,
while every OTHER group for that question keeps its full membership intact.
If the model still reaches `answer_gold`, `m` alone establishes that step —
genuine alternative. If **no** member alone suffices, the group is a required
chain wrongly encoded as an OR.

This is the *inverse* of leave-one-out (which tests necessity, not
sufficiency) — `docs/spec-gold-sufficiency.md` frames the OR case as
leave-one-out, but Jon's instruction for this task explicitly supersedes that
for these 25 groups.

## Step 1 — mandatory exclusion check (done before any model calls)

A row can fail the judged answer even with the **complete** gold set. If it
does, no member-level subset of that gold can possibly pass either, so
member-level testing on that row is meaningless — it has to be excluded, not
tested.

Checked all 25 groups against `evals/verdicts_derivability_B_human.json`'s
`final_correct` field (arm B = `claude-opus-5`, gold-only, full gold, the
same config this test reuses):

| row | `final_correct` (full gold) | groups excluded |
|---|---|---|
| `rg494` | **False** (human verdict: `ours-wrong`) | 1 (`701.40a`/`708.2`/`708.2a`/`406.3`) |
| `rg713` | **False** (human verdict: `ours-wrong`) | 2 (`118.12`/`609.1`, and `118.11`/`701.9c`) |
| `rg6556` | **False** (human verdict: `rulesguru-wrong`) | 1 (`702.139a`/`103.2b`/`727.1`/`726.2`) |

**4 of the 25 groups excluded up front** (`rg494`, `rg713`×2, `rg6556`) — the
row itself is unresolved independent of OR/AND structure, so these stay
**INCONCLUSIVE**, not decided, and no credits were spent testing them.

**21 groups (18 rows, 48 members) remained** and were tested.

## Pilot and cost projection

5-call pilot (`claude-opus-5`, `effort=high`, `max_tokens=32768`, matching
arm B exactly — confirmed by reading `evals/answers/derivability_B_goldonly.json`
row 0's stamped config): **$0.3345 / 5 = $0.0669/call measured** via
`rulesagent.pricing.cost_usd()`, not estimated. Projected for all 48:
**~$3.21**, under the $5 ceiling. Ran the remaining 43.

## Verdicts — 20 legitimate OR, 1 conjunction, 0 further inconclusive

Judge: **`openai/gpt-5-mini`** — the exact judge arm B's derivability
verdicts used. Confirmed by hash, not assumed: `judge_rulesguru.
RULESGURU_JUDGE_SYS` (same system prompt + player-naming convention line)
hashes to `b54fbdb95565abf8`, matching `judge_prompt_sha256` recorded in
`evals/verdicts_derivability_B_human.json`'s summary exactly.

### LEGITIMATE OR — 20 groups (at least one member alone reproduced `answer_gold`)

| row | level | group | per-member verdict | control-arm overlap |
|---|---|---|---|---|
| rg101 | 0 | 202.3 / 202.3d | both same | yes |
| rg1232 | 1 | 709.3 / 709.3a | both same | yes |
| rg127 | 3 | 613.1d / 205.1a | both same | yes |
| rg1702 | 1 | 305.7 / 305.6 | both same | yes |
| rg1835 | 0 | 107.3a / 601.2b | both same | yes |
| rg1933 | Corner Case | 303.4d / 701.3b | both same | no |
| rg1933 | Corner Case | 730.2i / 729.2a | both same | no |
| rg2163 | 2 | 204.2 / 204.1 | both same | no |
| rg2599 | 3 | 727.1 / 726.4 | both same | yes |
| rg3327 | 0 | 115.10a / 115.10 / 115.1 | all three same | yes |
| rg3509 | 0 | 702.37a / 702.37c / 708.2a | all three same | yes |
| rg3518 | 2 | 601.2b / 107.4f | both same | yes |
| rg470 | Corner Case | 727.1 / 726.1 | both same | no |
| rg6475 | 2 | 608.2c / 608.1 | both same | no |
| rg6475 | 2 | 701.19a / 614.8 / 701.19b | all three same | no |
| rg6583 | 0 | 117.7 / 608.1 / 405.2 / 405.5 | all four same | yes |
| rg725 | 3 | 800.4g / 608.2d | both same | no |
| rg7282 | 0 | 603.3d / 601.2c | both same | yes |
| rg7282 | 0 | 702.11c / 702.11d | both same | yes |
| rg851 | Corner Case | 303.4g / 303.4i / 608.3e | 303.4g different, 303.4i and 608.3e same | no |

`rg851`: not every member was independently sufficient (`303.4g` alone
scored `different`), but `303.4i` and `608.3e` each alone reproduced
`answer_gold`, which already meets the LEGITIMATE-OR bar ("at least one
member suffices"). Worth a human note anyway: `303.4g`/`303.4i` are adjacent
Aura-legality rules and the repass doc already flagged their scope as
close — this is consistent with that, not a new problem.

### CONJUNCTION — 1 group (no member alone sufficed)

| row | level | group | evidence |
|---|---|---|---|
| rg60 | Corner Case | 702.26k / 702.26b | **neither** member alone reached `answer_gold` |

Question: a phased-out Angel of Sanctions' owner leaves the game — does the
card it exiled come back? `answer_gold`: no, phased-out permanents are
treated as nonexistent so no leaves-the-battlefield event is seen.

- `702.26k` alone (plus the intact singleton group `800.4a`): model answered
  Rotted Hystrix **returns** — wrong. It correctly tracked that the token
  leaves the game via 800.4a, but without 702.26b's general "phased-out =
  treated as nonexistent" framing, it inferred that leaving the game counts
  as the token leaving the battlefield, which is the wrong inference.
- `702.26b` alone: same wrong "it returns" conclusion, for the mirror reason
  — it has the general "nonexistent" framing but not 702.26k's game-leaving
  clause, so it never connects the token's exit from the game to the
  original permanent's zone-change silence.

This is a real, evidence-based flip from `docs/results-orgroup-repass.md`'s
own worked example #3, which read `702.26k` as "already the whole answer" on
a human textual reading. Empirically, the model needs **both** citations
together to avoid the wrong inference — meaning this group is a genuine
required chain, not padding. **Proposed fix: split into two required
singleton groups**, joining the 54 mis-encoded-conjunction groups already
found in the repass. Full transcripts in
`evals/verdicts_orgroup_onlyone_members.json` (`test_id` `rg60__702_26k`,
`rg60__702_26b`).

### INCONCLUSIVE — 4 groups (excluded up front, arm B fails even with full gold)

`rg494` (1 group), `rg713` (2 groups), `rg6556` (1 group) — see Step 1. These
are **not decided by this test** and are **not** among the 21 resolved
below; they need a different fix (the RulesGuru answer or the model's
reasoning is wrong on the whole row, independent of OR/AND structure) before
an OR-group verdict on them would mean anything.

## Queue impact

- **21 of Jon's 25 flagged groups are now mechanically decided**: 20
  confirmed as legitimate OR (no change needed), 1 (`rg60`) reclassified as
  mis-encoded conjunction (joins the 54 already found — total mis-encoded
  conjunctions across both passes: **55**).
- **4 of the 25 remain genuinely open** (`rg494`, `rg713`×2, `rg6556`) —
  not an OR/AND question at all; the row fails arm B even with complete
  gold, so it needs a correctness call on the row itself first.

## The parametric-knowledge confound — read this before trusting the 20

**State this plainly: 20 out of 21 tested groups scoring "legitimate OR" is
a suspiciously lopsided result, and the most likely explanation isn't that
the corpus mostly has clean ORs here — it's that `claude-opus-5` at
`effort=high` already knows a fair amount of Magic rules text from training,
so feeding it just one citation is often enough to let it reconstruct (or
guess) the right answer even when that citation alone doesn't logically
entail it.** A member "sufficing" in this test conflates two different
things: (a) the rule genuinely contains the whole fact, and (b) the rule is
merely a plausible-looking anchor that lets the model's own prior knowledge
fill the rest in. This test cannot tell those apart on its own.

A **no-rules control arm** (retrieval off, no gold, no rules context at all —
just the bare question) is running right now on this same 150-question set
specifically to size this confound, per the coordinator's note. As of this
write-up it has **70 rows complete** (`evals/answers/norules_control.json`)
plus a growing 20-row stratified top-up (`evals/answers/
norules_control_topup.json`, at 5 rows when last checked — it is actively
being written by another process and was only read, never touched, here).

**Overlap with the rows tested in this pass**: of the 18 rows behind the 21
tested groups, **11 rows already have a completed no-rules control answer**
(as of this check — the control arm is still growing): `rg101`, `rg1232`,
`rg127`, `rg1702`, `rg1835`, `rg2599`, `rg3327`, `rg3509`, `rg3518`, `rg6583`,
`rg7282`. That covers **12 of the 21 tested groups** (`rg7282` contributes
two). For those 12, once the no-rules verdict for the same row is in hand,
it becomes possible to check whether the model reached the right answer with
*zero* rules at all — if it did, that specific "legitimate OR" verdict here
is under real suspicion of being parametric knowledge wearing a citation,
not a genuine alternative-derivation. The other 9 groups (`rg1933`×2,
`rg2163`, `rg470`, `rg6475`×2, `rg725`, `rg851`, and `rg60` itself) have no
control-arm data yet as of this check.

**Do not read the 20/1 split as "the corpus is basically fine here."** It is
the honest output of a test known to have this confound, on a model that
plausibly already knows a lot of these individual rulings. The right next
step, once the no-rules control arm finishes, is to cross the two: any
"legitimate OR" verdict here where the no-rules control *also* got that row
right is much weaker evidence of a real OR than one where the no-rules
control failed and only the single-citation version succeeded.

## Judge and generation provenance

- Generation: `claude-opus-5`, `effort=high`, `max_tokens=32768`,
  `system_version=3` (production default `SYSTEM`), no retrieval/rewrite,
  no tool loop — config confirmed against
  `evals/answers/derivability_B_goldonly.json` row 0, byte-identical to arm
  B except which gold ids are in context.
- Judge: `openai/gpt-5-mini` via OpenRouter, `judge_rulesguru.
  judge_with_reason()` verbatim (same `RULESGURU_JUDGE_SYS`, verified by
  sha256 match against arm B's recorded `judge_prompt_sha256`
  `b54fbdb95565abf8`).
- Card rulings: union mode (all rulings on every referenced card), same as
  arm B — no filtering.

## Cost

- **Generation (measured, not estimated)**: $3.2687 across 48 calls,
  computed from each call's real `usage` via `rulesagent.pricing.cost_usd
  ("claude-opus-5", ...)`. Pilot: 5 calls / $0.3345 ($0.0669/call). Full 48:
  $3.2687.
- **Judge (48 calls, `openai/gpt-5-mini` via OpenRouter)**: not metered by
  `rulesagent.pricing` (Anthropic-only) and `judge_rulesguru.
  judge_with_reason()` doesn't surface per-call usage, so this is an
  estimate, not a measurement — flagged as such rather than presented as
  precise. Comparable gpt-5-mini judge/answer calls elsewhere in this repo
  (`docs/OVERNIGHT-STATUS.md`: ~$0.33/40 short calls ≈ $0.008/call) put 48
  judge calls at roughly **$0.25–0.45**.
- **Total this task: ~$3.5–3.7**, under the $5 ceiling. (Real number is the
  generation figure, $3.2687, plus a small, non-precise judge cost on top.)

## Files

- `evals/answers/orgroup_onlyone_members.json` — 48 rows, one per
  (flagged group, member): the modified gold id set actually fed to the
  model, the generated answer, citations, `usage`, and `cost_usd`.
- `evals/verdicts_orgroup_onlyone_members.json` — 48 judged verdicts,
  `{"entries": [...], "summary": {"judge_model": "openai/gpt-5-mini",
  "judge_prompt_sha256": "b54fbdb95565abf8", ...}}` — paired with the
  answers file above per the `verdicts_X.json` <-> `answers/X.json`
  convention `evals/build_metrics_history.py` expects, judge model recorded
  so the dashboard doesn't flag it `[crit]` unattributable.
- This document: `docs/results-orgroup-resolution.md`.
- **Nothing in `evals/questions_rulesguru150_v3.jsonl` was modified.** Only
  `rg60`'s proposed split is new information beyond
  `evals/orgroup_repass_proposed_corrections.jsonl`; it is a proposal here,
  same as the other 54 — Jon rules on it before any gold changes.
