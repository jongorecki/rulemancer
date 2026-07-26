# Easy-set regression check — opus-low does not regress on simple questions

Closes the one caveat that was still open when Jon ruled on `GEN_MODEL` on
2026-07-26. Completed 2026-07-26.

## The question this answers

A model that reasons better on hard questions can be *worse* on simple ones by
overthinking them. Bucket A is the hardest slice we own, so nothing in the
+11.1pp hard-set result could reveal that. This is the check that could.

The easy set (`evals/_easy50.jsonl`) is 50 questions, 31 at level 1 and 19 at
level 2, disjoint from bucket A and from the v3 150, mean reference answer 271
chars against bucket A's 388.

## Result: no regression. Opus-low is better on easy questions than on hard ones.

Same 50 questions, rewrite v2, ruling raw, system v3, max_tokens 32768,
prompt caching on, frozen judge `b54fbdb95565abf8` (gpt-5-mini via OpenRouter).
Model and effort are the only differences — sonnet runs at the API's default
effort, opus at `effort=low`.

```
opus-5  effort low    r1  92.0%   r2  86.0%    mean 89.0%
sonnet-5 default      r1  78.0%   r2  74.0%    mean 76.0%
delta                                          +13.0 pp
```

The paired record is the stronger evidence, and it is lopsided:

```
paired r1 vs r1   opus wins 8, loses 1
paired r2 vs r2   opus wins 6, loses 0
```

Both opus reps beat both sonnet reps, and the *worst* opus rep (86.0%) beats the
*best* sonnet rep (78.0%) by 8 points. The gap is larger on easy questions
(+13.0pp) than on hard ones (+9.3pp), so the overthinking-simple-questions
failure mode this check existed to find is not merely absent — it runs the other
way.

**Noise, so the gap can be read properly.** Within-arm disagreement is 5 of 50
for opus and 6 of 50 for sonnet (10% and 12%), closely matching the 11%
measured on the hard set. A 13-point gap is well clear of it; a gap smaller than
about 11% would not have been a finding.

### ⚠️ The judge is not deterministic — sonnet r1 was 76.0% on first judging

This section first recorded sonnet r1 at **76.0%**. Re-judging the *same answers*
with the *same frozen instrument* (`b54fbdb95565abf8`) returned **78.0%**:
`rg6461` flipped from `different` to `same`. One question in fifty, from the
judge alone, with no change to any input.

**So ~2% of the measured accuracy on any arm is judge nondeterminism**, on top of
the model's own 10-12% within-arm variance. That is small next to the 13-point
gap here — Jon's call 2026-07-26 was to record it and not re-test, since it does
not change the outcome — but it sets a floor on what any single-rep comparison
can resolve, and it compounds the false-negative problem found by the gold audit
(`docs/results-gold-audit-batch1.md`): the judge is both systematically strict on
equivalent phrasings *and* noisy run to run.

Two practical consequences: a difference under ~2pp between arms is not a
finding even at the same n, and any published accuracy should name the judging
run that produced it, because re-judging will not reproduce it exactly.

## The failure sets say more than the percentages

```
missed by BOTH opus reps      3   rg1802 rg4440 rg5628
missed by BOTH sonnet reps    9   the same 3, plus 6 more
missed by all four arms       3   rg1802 rg4440 rg5628
sonnet-only, both reps        4   rg1663 rg1679 rg253 rg3787
```

Opus's easy-set errors are almost entirely a fixed core of three questions;
everything else it misses appears in one rep only, which is noise. Sonnet misses
that same core plus a consistently wider spread.

**The three missed by every arm of both models are gold-error candidates, not
model failures.** They are the same shape as the 11 unreachable questions in
`docs/results-derivability.md`, and they belong in the audit pool
(`docs/spec-gold-audit-ui.md`, batch 2) rather than in a model comparison.

## Cost: opus-low is CHEAPER on hard questions and DEARER on easy ones today

Priced at current published rates — opus-5 $5/$25 per MTok; sonnet-5 $3/$15 with
**introductory $2/$10 through 2026-08-31**. Cache writes bill at 1.25x input,
cache reads at 0.10x, and `input_tokens` is only the uncached remainder, so all
four components are counted.

```
per question          opus-5 low   sonnet @ intro   sonnet @ standard
hard set (n=54)         $0.06445      $0.08571          $0.12856
                                      opus -24.8%       opus -49.9%
easy set (n=50)         $0.05153      $0.04724          $0.07086
                                      opus +9.1%        opus -27.3%
```

The hard-set result reproduces the figure the switch was decided on (23% cheaper
today, ~48% after 8/31), so that number holds. **The easy set flips it: until
2026-08-31, opus-low costs ~9% MORE per easy question than sonnet.**

**Why, and it is not noise.** Output tokens per question:

```
              opus-low    sonnet
hard set        1,211      7,184     5.9x
easy set        1,178      3,763     3.2x
```

Opus at `effort=low` emits a nearly constant ~1,200 output tokens whatever the
difficulty; sonnet's output scales with the problem, because adaptive thinking
spends in proportion to hardness. All of opus's saving comes from capping
output, so it is worth more the harder the traffic. On easy questions there is
less thinking to save, and opus's input rate — 2.5x sonnet's under intro pricing
— is not offset, since input is ~4.2K tokens per question on either model and is
the larger half of the bill.

**So the cost answer depends on the traffic mix, and it is not a single number.**
After 2026-08-31 opus-low is cheaper on both sets. Before then it is cheaper on
hard traffic and dearer on easy, so a mixed workload sits somewhere near break-
even. The quality case is unaffected and is the stronger one either way: +9.3pp
hard, +13.0pp easy.

A token-ratio alone would have hidden this. Opus costs more per token than
sonnet, so 3.2x fewer output tokens does not by itself establish which is
cheaper — it has to be priced.

## How to read this

On quality it **confirms** the switch rather than merely failing to block it. A
regression would not have reversed the decision — it would have told us to watch
simple questions and pointed at splitting effort by question difficulty. No such
split is needed for quality.

On cost the framing needs qualifying. "A cost decision with supporting quality
evidence" is accurate for hard traffic, and for all traffic after 2026-08-31.
For the next five weeks on easy traffic it is closer to a quality decision at
roughly flat cost. Nothing here argues for reverting: opus-low wins on quality
on both sets, and on cost everywhere once intro pricing ends.

## Provenance

Both sonnet arms were generated unattended and one of them had already stopped
early once: `h2h_sonnet_easy_r1.json` sat at 39 of 50 rows as valid-looking
JSON. Row counts were confirmed at 50/50/50/50 and each arm's recorded
`condition`/`model`/`effort` fields were read back from the files before any of
these numbers were computed. `h2h_opuslow_hard_r2.json` also completed since the
prior handoff (47 -> 54 rows) and moved 72.3% -> 72.2%, changing nothing.

Answers: `evals/answers/h2h_{opuslow,sonnet}_easy_r{1,2}.json`.
Verdicts: `evals/verdicts_h2h_{opuslow,sonnet}_easy_r{1,2}.json`.
