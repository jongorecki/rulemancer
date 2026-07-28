# Plan — what to explore next to move opus-5's accuracy

**Written 2026-07-27 after the prompt-lever work concluded. Design only, Rule 0 —
nothing here is built until Jon rules on it.**

This exists because the obvious lever is now closed. Prompt engineering was tested
on the cheap model and the transferable conclusion is that **there is nothing to
port to opus.** What follows is where the remaining accuracy actually lives, ranked
by evidence rather than by how easy it is to try.

## First, what is already ruled out, and why

**Do NOT add the anti-refusal instruction to the production path.**

| | opus-5 | gpt-5-mini |
|---|---:|---:|
| declines (`answered=False`) | **0.7%** (10/1409) | 11.1% (157/1409) |
| accuracy | 85.88% | 70.05% → 75.02% with the instruction |

The instruction bought gpt-5-mini +5.0 points because it had an 11.1% decline rate
to recover. Opus's entire addressable upside is **0.7 points** — smaller than the
±2-4 points of judge instability measured in `results-judge-stability.md`, so the
effect would be unmeasurable even if real.

**And it targets a property worth keeping.** `results-rules86-placebo.md` showed
opus declining on 90.7% of rows when handed rules retrieved for a *different*
question, and confabulating on only 3.5%. That refusal reflex is what makes 85.88%
trustworthy rather than merely high. "Do not decline for lack of context" is aimed
directly at it.

**Do NOT add procedural scaffolding.** Tested on gpt-5-mini over the same 150 rows:
accuracy 76.0% → 72.0% (gpt-5-mini judge) or 76.0% → 76.0% (deepseek judge), i.e.
flat to 4 points worse, while declines rose 6.7% → 10.0%. The two instructions
fight: anti-refusal says don't decline, scaffold hands the model a procedure for
discovering that no provided rule governs. Separately, opus already cites a CR rule
on **98.1%** of answers unprompted, so the instruction tells it to do what it does.

**A prediction that failed, recorded because it was testable.** The scaffold was
chosen because gpt-5-mini's gap to opus was widest at levels 1-2 (12.2 and 13.8
points) and narrowest at level 3 (5.6) — the signature of process failure rather
than a capability ceiling. Procedure did not recover those losses, so the
mid-difficulty gap is more likely genuine capability. Don't re-derive that
argument; it was tried.

## Where the accuracy actually is

From `results-headline-accuracy.md`, all 1,409 questions, production config:

| level | accuracy | n | gap to level 0 |
|---|---:|---:|---:|
| 0 | 96.14% | 207 | — |
| 1 | 90.27% | 565 | −5.9 |
| 2 | 84.24% | 406 | −11.9 |
| **3** | **67.90%** | **162** | **−28.2** |
| Corner Case | 71.01% | 69 | −25.1 |

**Level 3 plus Corner Case is 231 rows (16.4% of the corpus) carrying 124 of the
199 total failures — 62% of all errors in 16% of the questions.** Independently
corroborated: `results-failure-taxonomy.md` found level 3 failing at 42.9% against
a 7.4% base rate on a separate 311-row sample.

## The named failure modes (from `results-failure-taxonomy.md`)

Qualitative, from reading actual failed answers. These are the things to attack:

1. **Wrong layer/timestamp stacking** — the largest bucket. Drops or miscombines
   type-changing effects instead of applying them in timestamp order (CR 613).
2. **"Loses abilities" over-generalised into "gets sacrificed"** — a recurring
   Saga misconception (rg4023, rg6634), not random noise.
3. **Trigger-creation and ordering timing** — a delayed trigger not yet created
   treated as existing (rg1049); an assumed trigger that isn't there (rg1802); a
   missed controller ordering choice (rg6456).
4. **Restriction-scope misreads** — conflating "can't cast spells" with "can't
   activate abilities" under Teferi, Time Raveler (rg6743).
5. **Over-cautious refusal** — declining a flavour-named question the reference
   expected answered (rg6547). Rare on opus (0.7%) but it exists.

**Caveat carried from the taxonomy:** the Layers / Type-changing / Dependency tag
signal is confounded with the "hard" arm having been curated as hard. It says what
to look at, not what is proven.

## Candidate experiments, ranked

### 1. Three-way verdicts — do this first, it is nearly free
Correct / incorrect / **declined** instead of collapsing a refusal into "wrong".
`answered` is already recorded per row, so this is arithmetic over existing files,
no generation and no judging. Cost **$0**.

Why first: `results-rules86-placebo.md` showed the current metric making a
well-behaved system look ~6x worse than it behaves. Every number downstream is
distorted by it, including the level-3 figure this plan is about.

### 2. Partition the level-3 failures by named mode
Take the 52 level-3 failures and 20 Corner Case failures from
`verdicts_headline_full_votes3.json` and classify each against the five modes
above. Cost **$0** (subscription grading, or hand grading). Deliverable: counts per
mode, so effort goes at the biggest bucket rather than the most memorable one.

**This is the gating experiment.** Everything below is a guess until it exists.

### 3. Targeted retrieval for CR 613 (layers) interactions
If layer/timestamp stacking is the largest mode, the question is whether the model
had the right rules in context and misapplied them, or never received them. Both
are recoverable from the run: `retrieved_rule_ids` is now backfilled on every row
(`backfill_retrieved_rule_ids.py`), so you can check whether 613.x rules were
present on the rows that failed for layer reasons.

- **If the rules were present** → a reasoning failure. Prompting is unlikely to fix
  it (see the scaffold result), but a deterministic layers checker might. Note the
  old `layer_resolver.py` engine and its 76 tests are recoverable from git
  (`f357c4a`) — it measured zero as a *model-facing tool*, which is a different
  claim from "useless as a verifier over the model's answer."
- **If the rules were absent** → a retrieval failure, and the fix is in the index.

Cost: **$0** to determine which, from files already on disk.

### 4. A harder card-free set
`results-rules86-placebo.md`: the real arm scores **98.84%**, near ceiling. That
set is a sensitive instrument for *damage* and useless for measuring *gains* — it
cannot show an improvement because there is no headroom. Building a harder card-free
set is a prerequisite for measuring any level-3 work. Subscription labour, **$0** in
credits; the drafting-plus-blind-review pattern from `b290fc5` worked and caught
four reviewer errors.

### 5. Human-grade a plain random sample
All human verdicts to date are stratified toward rows the judge already failed or
rows curated as hard — **never a plain random draw**. So the judge's error rates rest
on samples chosen by the judge itself. A 100-row random sample, hand-graded, would
put a real error bar under 85.88%. Cost **$0** in credits, real cost in Jon's time
or a subscription panel.

### 6. Optional: document the refusal safety property under opus + anti-refusal
Not recommended as a change, worth having as a record. Run opus against the rules86
**scrambled** cache with the anti-refusal instruction appended, 86 rows, and see
whether confabulation rises above the measured 3.5%.

Cost **~$2.67** Anthropic. My prediction: it rises. Value: turns "the instruction
would erode a safety property" from an argument into a number.

## What NOT to spend money on

- **Re-buying the full corpus run to measure an improvement.** A 3-point gain sits
  inside judge instability (~2-4 points). Fix the instrument (item 1) and build a
  set with headroom (item 4) before buying another 1,409-row run.
- **More prompt variants on opus.** Two were tested on the cheap model; one worked
  only because it addressed a failure opus does not have, and the other was flat to
  negative.
- **Cheaper models for production.** Settled: `results-crossmodel-fair.md`.
  gpt-5-mini 75.02% at 3.9x cheaper, deepseek 52.0% at 36x cheaper, gpt-5 ~83% at
  1.4x *more* expensive than batched opus.

## The through-line

Every measurable win tonight came from measuring a specific named failure and
addressing that one thing — refusals at 11.1%, rules retrieval on a card-free
distribution, a mislabelled dashboard panel. Every intervention justified by a
plausible general argument (procedural scaffolding, gpt-5 as the cheap option,
reasoning effort as a free lever) either did nothing or backfired.

So: **item 2 before items 3-6.** Find out what the level-3 failures actually are
before choosing what to build.
