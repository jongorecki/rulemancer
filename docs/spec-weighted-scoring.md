# Spec — level-weighted scoring

> **RULED AND BUILT, 2026-07-26.** Jon ruled **flat across L0-L3, Corner Case
> 0.5** — Scheme B below, named `corner-half`. Shipped as
> `evals/weighted_score.py` with `tests/test_weighted_score.py`. The
> "Recommended" framing further down is preserved as the argument that led to the
> ruling; it is no longer a proposal. Measured results are in
> [What it actually did](#what-it-actually-did).

Requested 2026-07-26 off two gold-audit notes:

> rg842 — *"I wouldn't consider this one part of scoring too strongly... it's more
> important that we get the level 3 questions right than it is we get the corner
> cases right, but we should try for both."*
>
> rg1208 — *"major corner case. never would happen in game. not super important to
> me to get right."*

## Three facts that constrain the design

**1. The question set is already stratified, so weighting is not a bias fix.**
`questions_rulesguru150_v3.jsonl` is exactly **30 questions each at L0, L1, L2,
L3, and Corner Case**. Flat scoring therefore already gives every level exactly
20% of the total. Weighting does not correct a sampling imbalance — there is
none. It expresses a judgment about what we *value*, and should be argued on
those terms.

**2. Only ratios matter.** A weighted score normalizes by the weighted
denominator, so multiplying every weight by a constant changes nothing. During
sensitivity testing, `(1, 2, 3, 4 | corner 1)` and `(0.5, 1, 1.5, 2 | corner
0.5)` produced byte-identical scores because the second is the first halved.
**Specify a scheme as ratios**, and treat two schemes that differ by a scale
factor as the same scheme.

**3. Corner Case is a category, not the top rung of the difficulty ladder.**
This is the crux. Corner Case is the *hardest* slice we own, but Jon values it
*least* — because it is unrealistic ("never would happen in game"), not because
it is hard. So a pure difficulty ramp gets his stated preference backwards at
the top end. Corner Case has to be discounted on its own axis, independently of
where difficulty is weighted.

## The choice this actually turns on

Two defensible purposes give opposite weightings, and the spec cannot pick for
Jon:

| Purpose | What it weights up | Rationale |
|---|---|---|
| **Product quality** — how well do we serve real askers? | L0-L2 | Common questions dominate real traffic; a wrong answer to an easy question costs more trust than a wrong answer to a hard one |
| **Capability demonstration** — how good is the bot at Magic? | L3 | Hard questions are what distinguishes this from a search box |

Both agree Corner Case is worth less. They disagree about whether L3 should
outweigh L1.

## Candidate schemes and what they do

Measured on the arms already judged (zero API — see Implementation):

```
                              flat     A: 1,2,3,4 | C=1     B: flat | C=0.5
opus-low hard (mean of 2)     74.1%          72.4%               74.8%
easy gap (opus - sonnet)     +13.0pp        +14.3pp             +13.0pp
```

**No conclusion flips under any scheme**; the largest movement is ~2pp on the
hard set. The easy set is unaffected by Corner Case weighting because it
contains only L1 and L2.

**Recommended: Scheme B — flat across L0-L3, Corner Case 0.5.**

It implements exactly what Jon said and nothing more. Scheme A additionally
asserts that L3 is four times as valuable as L0, which he never claimed, and
which the product-quality reading argues against — a bot that fumbles L1
questions is worse in practice than one that fumbles L3. B is also the smallest
change from the current numbers, so historical comparisons stay legible.

If Jon wants difficulty emphasis as well, the honest form is a shallow ramp with
the corner discount kept separate, e.g. `L0 1.0, L1 1.0, L2 1.25, L3 1.5,
Corner 0.5` — not a steep 1:4 ladder.

## What weighting does NOT do

- **It does not fix the judge.** The gold audit found the judge marking
  semantically equivalent answers as different, and re-judging found ~2% run-to-
  run nondeterminism (`docs/results-easy-regression.md`). Weighting re-scores the
  same verdicts; a false negative at L3 just counts for more. Do not let a
  weighted number look like a measurement improvement.
- **It does not change paired records.** `opus wins 8, loses 1` is a per-question
  count and stays unweighted. Weighting a win/loss record would need its own
  justification; this spec does not propose it.
- **It slightly reduces effective n.** Under B, 30 corner cases at 0.5 take the
  weighted denominator from 150 to 135, so confidence intervals widen a little.
  Not material at these gap sizes, but it is a real cost of discounting.

## Implementation

**Zero API.** Every verdict file already carries `by_level_counts`, so this is
arithmetic over JSON we have already paid for — a re-scoring pass, never a
re-run. All historical arms can be re-scored, so weighted and flat numbers stay
comparable across the whole history.

1. `evals/weighted_score.py` (new, small): reads one or more `verdicts_*.json`,
   applies a named weight vector, prints flat and weighted side by side.
2. Weight vectors live in **one module-level dict** with a name per scheme, the
   same shape as `VERDICT_SETS` in `build_grading_ui.py`. Adding a scheme is a
   dict entry, not a code change.
3. **The weight vector is written into any output that carries a weighted
   score**, alongside the scheme name. A weighted accuracy without its weights
   is exactly the kind of number-with-an-unchecked-claim this repo keeps getting
   caught by; a reader must be able to reproduce it from the artifact.
4. Reports quote **flat first, weighted second**, never weighted alone. The flat
   number is what every prior result is stated in.

## Testing

- A flat weight vector reproduces the existing accuracy exactly (guards the
  arithmetic against the summary the judge already computed).
- Scaling every weight by a constant leaves the score unchanged (locks in fact 2
  above, which already fooled one sensitivity run).
- A level present in the verdicts but absent from the weight vector is an error,
  not a silent default to 1.0 — a typo'd level name must fail loudly rather than
  quietly reweighting.
- Round-trip: the emitted weight vector re-scores to the emitted number.

## What it actually did

Re-scored across every arm carrying `by_level_counts`, `corner-half` vs flat
(read from the files 2026-07-26, after the derivability rescore landed):

```
                                        flat   corner-half    delta
derivability B  auto                    90.0%      91.5%      +1.5pp
derivability B  human-corrected         91.3%      92.6%      +1.3pp
opus5-low bucketA  auto                 75.0%      75.6%      +0.6pp
opus5-low bucketA  human-corrected      82.4%      83.2%      +0.9pp
h2h opus-low hard r1                    75.9%      76.2%      +0.3pp
h2h opus-low hard r2                    72.2%      73.3%      +1.1pp
h2h opus-low easy r1 / r2         92.0% / 86.0%   unchanged    0.0pp
h2h sonnet easy   r1 / r2         78.0% / 74.0%   unchanged    0.0pp
h2h gpt5-mini (judge bakeoff)           52.8%      52.2%      -0.6pp
```

**No conclusion flips, exactly as predicted.** Largest movement is 1.5pp. The
easy set is untouched because it contains only L1 and L2 — no Corner Case rows to
discount. The opus-low hard mean moves 74.1% -> 74.8%, reproducing this spec's
own sensitivity figures from an independent implementation.

`h2h_verdicts_gpt5mini.json` moves **down**, which is the useful sanity check:
weighting is not a way of making numbers bigger. It moves whichever way an arm's
corner-case performance sits relative to its own average.

Two implementation facts the spec did not anticipate:

- **`by_level_counts` has two shapes.** Auto files store `{same, different}`;
  human-merged files store `{correct, n}`, with `correct` as a **float** because
  partial credit is possible. `normalize_counts()` handles both and raises on an
  unrecognised third rather than guessing — a wrong guess silently halves or
  doubles a denominator.
- **Flat re-scoring is now a repo-wide regression test.** `test_weighted_score.py`
  asserts a flat vector reproduces `summary.accuracy` for *every* verdict file
  matching `evals/*verdicts*.json`, so a malformed or drifted summary in any
  future arm fails the suite instead of being discovered later.

## Out of scope

No change to the judge, the question set, the level labels, or any published
flat number. No weighting of paired comparisons. No new eval runs.
