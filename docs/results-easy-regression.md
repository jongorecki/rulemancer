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
sonnet-5 default      r1  76.0%   r2  74.0%    mean 75.0%
delta                                          +14.0 pp
```

The paired record is the stronger evidence, and it is lopsided:

```
paired r1 vs r1   opus wins 8, loses 1
paired r2 vs r2   opus wins 6, loses 0
```

Both opus reps beat both sonnet reps, and the *worst* opus rep (86.0%) beats the
*best* sonnet rep (76.0%) by 10 points. The gap is larger on easy questions
(+14.0pp) than on hard ones (+11.1pp), so the overthinking-simple-questions
failure mode this check existed to find is not merely absent — it runs the other
way.

**Noise, so the gap can be read properly.** Within-arm disagreement is 5 of 50
for opus and 6 of 50 for sonnet (10% and 12%), closely matching the 11%
measured on the hard set. A 14-point gap is well clear of it; a gap smaller than
about 11% would not have been a finding.

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

## Cost mechanism, measured

Output tokens across both reps of each arm — measured, not priced here, since
current per-token rates should be looked up rather than recalled:

```
opus-5 effort low     117,804 output tokens
sonnet-5 default      376,250 output tokens      3.2x
```

That ratio is the mechanism behind the cost result already recorded on the hard
set ($0.0741 vs $0.096, 23% cheaper today and ~48% after sonnet's intro pricing
ends 2026-08-31): sonnet at default effort runs adaptive thinking, and thinking
tokens are output tokens. `effort=low` is what makes that cost expressible.

Input tokens are near-identical (210k vs 227k) and cache reads are effectively
equal, as expected — the prompts are the same.

## How to read this

It **confirms** the switch rather than merely failing to block it. Jon decided
on cost, so a regression would not have reversed the decision — it would have
told us to watch simple questions and pointed at splitting effort by question
difficulty. No such split is needed.

## Provenance

Both sonnet arms were generated unattended and one of them had already stopped
early once: `h2h_sonnet_easy_r1.json` sat at 39 of 50 rows as valid-looking
JSON. Row counts were confirmed at 50/50/50/50 and each arm's recorded
`condition`/`model`/`effort` fields were read back from the files before any of
these numbers were computed. `h2h_opuslow_hard_r2.json` also completed since the
prior handoff (47 -> 54 rows) and moved 72.3% -> 72.2%, changing nothing.

Answers: `evals/answers/h2h_{opuslow,sonnet}_easy_r{1,2}.json`.
Verdicts: `evals/verdicts_h2h_{opuslow,sonnet}_easy_r{1,2}.json`.
