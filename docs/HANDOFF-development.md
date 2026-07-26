# Handoff — the session that corrected itself twice

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-26 session, which shipped both queued rulings, measured the judge in the
direction nobody had checked, built a decision dashboard — and, in the middle of
all that, published a correction that was itself wrong and had to be reversed.
The reversal is the most useful thing in this document.**

Suite: **645 passed, exit 0.** Commits, in order: `373c4aa` `372965b` `ad53532`
`44c7852` `ab8b8c5` `b11f1cd` `3bfd0c8` `6ab8b67` `eb16810` `4c6d489` `5e3a64b`
`a0b423e` (+ the roadmap commit, below).

---

## ⚠️ FIRST, UNLEARN THIS

**1. Arm B is 91.3%, not 93.3%, and not 90.0%.** 137/150.
`evals/verdicts_derivability_B_human.json`, two overturns applied (`rg1718`,
`rg851`). If you see 93.3% quoted as an accuracy anywhere, it is stale — that
number is now **the ceiling**, not the score.

**2. The judge's false-negative rate on the flagged side is 2 of 15, not 5.**
The "a third of the failures were the judge" finding was wrong. Three of the five
rows graded "they say the same thing" state the **opposite bottom line** from the
reference answer. Jon adjudicated 2026-07-26: **the gold is correct on all
three.** The judge is less broken than the intervening docs said.

**3. The "gold was incomplete" category is REAL, and so are the ceiling and the
single-id heuristic.** All three were withdrawn mid-session and have been
reinstated. Arm C's passes on `rg7215`, `rg549`, `rg811` were **retrieval
genuinely closing a gap** — its answers match gold's bottom line where arm B's
contradict it. This is the most direct causal evidence the project has that
retrieval is the bottleneck: three questions we got *wrong* with gold alone and
*right* once retrieval supplied the missing rule.

**4. The out-of-range ruling citations were NOT a product bug.** Production emits
**0 out-of-range citations across 397 checked**. The defect was confined to
`evals/build_gold_prompts.py` and hit 69% of citing rows in the derivability
arms. Fixed at the boundary; see below.

**5. Sharing a question set does NOT make two arms comparable.** They must also
be the same **kind** of experiment. An oracle arm (retrieval off, gold handed in)
is not on the same scale as a pipeline arm, even on identical questions.

---

## WHAT SHIPPED

**Judge false-negative/positive measurement** (`3bfd0c8`) —
`docs/results-judge-error-rate.md`, `evals/judge_error_prep.py`,
`evals/judge_error_metrics.py`. **False positives — the direction never before
checked — are ≤4.4%** (4/90, CI 1.7–10.9%), an upper bound rather than a point
estimate because the reference grader failed validation: opus-5 handed the
judge's own prompt returned `different` on 32/32 validation rows, so a stronger
model on the same prompt reproduces the judge instead of checking it. Re-scored
against corrected ground truth its agreement with Jon is 28/32 (87.5%), not the
78.1% first reported — three of the rows it was penalised for are rows where it
was right and the human label was wrong. **$0.00 API credits** (ran on
subscription subagents, per Jon's standing billing preference).

**Level-weighted scoring** (`372965b`) — `evals/weighted_score.py`, 53 tests.
Jon's ruling: flat L0–L3, **Corner Case ×0.5**. Zero API. No conclusion flips;
largest move 1.5pp. Arm B: 91.3% flat / 92.6% weighted. Handles both
`by_level_counts` shapes (`{same,different}` auto, `{correct,n}` human-merged
with fractional `correct`) and raises on a third rather than guessing.

**Ruling labels moved to the prompt boundary** (`b11f1cd`) — `label_rulings()`
now applies inside `build_prompt()`, which every builder routes through, so a
future prompt builder cannot reintroduce the defect by not knowing it had to.
**Idempotent by necessity:** `answer()` must still label its filtered subset
because it holds the original Scryfall indices a renderer cannot recover from a
filtered list; the second pass leaves those alone. Without idempotence a subset
labelled `#2,#5` would be positionally renumbered to `#0,#1` — a quieter, worse
version of the same bug that the range check would no longer catch.
`tests/test_ruling_labels.py` (10 tests) holds it. Production prompts are
byte-identical (`tests/test_prompt_identity.py` unchanged).

**Human-verdict merge** (`373c4aa`) — `evals/merge_human_verdicts.py`. Writes a
derived file, never edits the judge's raw output in place, because measuring
judge error needs the original verdict beside the human one row by row. Overturn
ids are passed **explicitly**, never derived from the grading vocabulary — six
rows were graded `ambiguous` but only some were approved.

**The metrics dashboard** — `evals/build_metrics_history.py` →
`evals/metrics_history.html`. Built across `44c7852`, `6ab8b67`, `5e3a64b`,
`a0b423e`. Sections: decision panel, head-to-head, cost-vs-accuracy dominance,
per-level, config matrix, reproducibility/noise floor, timeline of steps, full
arm table, and the roadmap (below). Everything regenerates from the verdict
files — when arm B moved 93.3% → 91.3% the whole page followed with no code
change.

---

## THE STATE OF THE NUMBERS

```
arm B (oracle: gold handed in, retrieval OFF)   137/150 = 91.3%   auto 90.0%
ceiling with perfect retrieval                  140/150 = 93.3%
production, opus-5/low                          ~75-82% auto-judged
full-run projection over 1,409 questions        80.3%  [71.7-86.8%]   $73-91

opus-5/low vs sonnet-5, easy 50    89.0% vs 76.0%   +13.0pp,  27% cheaper
opus-5/low vs sonnet-5, hard 54    74.1% vs 64.8%   +9.3pp,   50% cheaper
```

Sonnet is **strictly dominated** on both sets — worse *and* pricier, emitting
~3× the output tokens. Both gaps clear their sets' noise floors (±6.0, ±3.7pp).

**The largest open uncertainty: L0 has never been run through the pipeline.**
Zero L0 rows across all 10 pipeline arms. It is 207 of 1,409 questions (~15%),
and the corpus's *easiest* slice (not its largest — L1 is 565), so the 80.3%
projection likely reads low. An L0-only arm costs ~$11 and is the cheapest
uncertainty reduction available before committing to the full run.

---

## NEXT SESSION, IN ORDER

1. **Run an L0-only pipeline arm** (~$11, 207 questions). Largest single source
   of uncertainty in the full-run projection; either firms up the interval or
   exposes it.
2. **Batch 2 of the gold audit** — the full-data rows (`rg1802`, `rg4440`,
   `rg5628`, plus h2h/costbase). Build with `--provenance run`. **Grade the
   bottom line before the reasoning** — see the lesson below; that is exactly
   what went wrong in batch 1.
3. **Then decide the full run.** At $73–91 it is not a cost decision. The judge
   is now measured; the remaining question is L0 coverage.
4. **Spec the cosine floor** — free at runtime (`scores = embeddings @ qvec` is
   one in-process matmul), cuts the 38% chunk churn multi-query introduced,
   restores a calibrated signal that RRF removed.
5. **Second-hop retrieval** — Jon's own proposal from his q016 grading note. The
   `rg241` finding stands: all four CR rules in his derivation are already
   indexed, but hops 2–3 have no resemblance to the question, so question-side
   rewriting cannot reach them however good the rewrites.
6. Still open from before: double-mine for stability (0.54 run-to-run overlap),
   re-pass v3's 105 conjunctive OR-groups, resume mining (809 rows).

The dashboard's roadmap section carries the full inventory with status, cost,
dependencies, and what each moves.

---

## HOW JON WORKS (unchanged, load-bearing)

- **Explain things properly.** Define jargon at first use, lead with what a thing
  means, show a concrete example. He is a partner, not an observer.
- **Rule 0: plan before code.** Every `plan-*.md` / `spec-*.md` is design-only
  until he rules.
- **Subagents: he authorised them this session** ("these sound like they could
  run in parallel") — **and he had to point it out, which is the wrong way
  round.** Items 1-5 were independent from the start and ran serially through one
  context window before anyone said so. The harness forbids the Agent tool unless
  he asks; the correct response is to ask **at the moment the parallel structure
  appears**, not to flag the restriction once and treat it as settled. Check for
  independence at the *planning* step — `superpowers:dispatching-parallel-agents`
  and `superpowers:subagent-driven-development` are built for exactly this and
  were both skipped. See the Context economy section of `CLAUDE.md`.
- **Verify agents' claims yourself, and verify the right thing.** Every agent
  result this session was checked against the underlying data before being
  relayed; two had real errors in framing that only showed up that way.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. **Model IDs and pricing
  come from the claude-api skill.**
- **Verify by rendering** for UI. **Jon runs the app on port 8000 — never bind or
  kill it.** Use a scratch port and stop it after.
- **Billing splits two ways.** Claude Code and its subagents run on his Max
  subscription; any Python here that constructs an Anthropic client from `.env`
  bills **API credits**. His standing preference: batch Claude-labor onto
  subscription subagents, never the credits reserved for eval arms.
- Commit per slice on master, heredoc messages,
  `Co-Authored-By: Claude Opus 5`. `.venv/Scripts/python.exe`,
  `PYTHONIOENCODING=utf-8`. Suite is `uv run pytest`.
- Never pipe a long run through `| tail`; PowerShell `*>` buffers until exit, so
  a running job's log looks dead — check the output artifact.

---

## THE LESSON TO CARRY

Previous sessions: *a value that looks like an identity but is really a position*
(the ruling-index bug); *a claim inherited and repeated without being checked*;
*a number is a snapshot of a file at a time, not a fact*.

This session: **anything used as ground truth is an experiment subject,
including a person.**

The sequence is worth understanding, because every step was locally reasonable.
An audit of the LLM judge produced human labels. Those labels were applied to a
published result — withdrawing a category, a ceiling and a heuristic — **without
anyone checking the labels against the answer text.** The audit was rigorous
about the instrument it set out to audit and applied none of that rigour to the
instrument that replaced it. Three of five labels were wrong, the withdrawal was
wrong, and the original result had been right all along.

The check costs one minute: **read the reference answer's first sentence next to
ours.** `rg7215` was "Tapped." against "Minas Tirith enters untapped."

The corollary, and the reason this keeps recurring in different clothes: when the
thing you are measuring *with* changes — LLM judge to human grader, one question
set to another, one arm kind to another — the safeguards do not follow it
automatically. You have to move them. The same failure showed up a third time in
the dashboard, where sharing a question set was treated as sufficient for
comparability until Jon pointed out we were differencing an oracle arm against a
pipeline arm.
