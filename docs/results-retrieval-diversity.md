# Results — retrieval diversity: MMR is refuted, multi-query is the win

Run 2026-07-25 against `evals/questions_rulesguru150_v3.jsonl`, pool 200,
zero API spend (cache-only). Raw numbers: `evals/retrieval_diversity_results.json`.
Harness: `evals/run_retrieval_diversity.py`. Spec: `docs/spec-retrieval-diversity.md`.

**All four `lambda = 1.0` self-tests passed** — MMR at pure relevance reproduced
each base arm at every k, so the relevance term is right and the rest of the
table means something.

## Read the baseline row first

**`rw1` is what production runs today**, not `vector`. `generate/answer.py` sets
`REWRITE_MODEL = "claude-haiku-4-5"`, `REWRITE_N = 1`, and `RulesAgent.__init__`
defaults `rewrite=True`. So the live system already rewrites the question once
before retrieving; the raw-question `vector` arm is a reference point, not the
status quo. Any recommendation has to beat **`rw1`**.

| arm | `groups`@15 | `any`@15 | `all`@15 | overall@15 | coverage@15 |
|---|---|---|---|---|---|
| vector (raw question) | 11.4% | 54.5% | 0.0% | 26.0% | 37.1% |
| **rw1 — PRODUCTION** | **16.5%** | **60.0%** | **6.2%** | **31.3%** | **44.4%** |
| mq (n=3, RRF-fused) | 20.3% | 65.5% | 6.2% | 35.3% | 46.8% |
| hybrid | 11.4% | 56.4% | 0.0% | 26.7% | 37.0% |
| hybrid+rw1 | 16.5% | 60.0% | 6.2% | 32.0% | 40.3% |
| hybrid+mq | 19.0% | 56.4% | 6.2% | 31.3% | 39.5% |
| best MMR arm | 12.7% | 58.2% | 0.0% | 26.7% | 37.3% |

1. **MMR does not work here. Every lambda below 1.0 is flat or worse**, and
   `lambda = 0.3` is destructive (−15 questions flipped from hit to miss at
   k=15). This was the leading hypothesis and it is dead. See the mechanism
   below — it fails for a structural reason, not a tuning one.
2. **Most of the query-rewriting gain is already banked.** Raw question ->
   one rewrite is +5.1pp on `groups`@15 (11.4% -> 16.5%); production has had
   that since Plan #3a.
3. **Going n=1 -> n=3 is a small, unproven gain.** `groups`@15 16.5% -> 20.3%
   (**+3.8pp**), `any`@15 60.0% -> 65.5%, overall@15 31.3% -> 35.3%. Paired at
   k=15 it is **+10 / −4** (net +6 of 150). That is **below the ~7pp bar fixed
   before the run**, and 10-of-14 discordant pairs is not significant. Direction
   is favourable; the evidence is not conclusive.
4. **n=1 is better at the very top, n=3 better deeper.** `groups`@5: rw1 8.9% vs
   mq 3.8%; `groups`@50: rw1 30.4% vs mq 35.4%. RRF over three rankings spreads
   mass down the list — it buys depth at some cost to precision at rank 1-5.
   At the production `TOP_K=15` the fused arm is ahead, but only just.
5. **Hybrid is neutral to harmful.** It moves `groups`@15 not at all over the
   corresponding non-hybrid arm, and `hybrid+mq` (19.0%) is *worse* than `mq`
   alone (20.3%). Adding BM25 dilutes the fusion.
6. **`all` questions remain broken.** Best arm is 6.2% (1 of 16). Nothing in this
   factorial fixes them.

Note also that multi-query is **already built** — `rewrite_query(n=3)` +
`rrf_fuse`, live in `run_eval.py` as the `vec+rw3-*` arms. Switching it on in
production is a one-line change (`REWRITE_N = 1` -> `3`), not an implementation.

## Why MMR fails — measured, not assumed

MMR assumes redundancy looks like similarity: penalise candidates resembling
what you already picked, and you make room for something new. That assumption is
**false for the Comprehensive Rules**, because the rules a multi-rule question
needs together are near neighbours of each other (613.3 and 613.7a are both
layers rules by construction).

Cosine between CR chunks:

```
gold pairs ACROSS required groups   n=145    mean=0.637   median=0.633   p90=0.798
gold pairs WITHIN one OR-group      n=231    mean=0.693   median=0.694   p90=0.893
random corpus pairs                 n=19998  mean=0.451   median=0.450   p90=0.566

50/145 (34%) of cross-group gold pairs sit above the 99th percentile of random pairs (0.681)
```

Rules that must co-occur are far more similar to each other than two random
rules. The diversity penalty therefore demotes **precisely the second rule the
question needs**. Turning diversity up (lower lambda) makes it worse, which is
exactly the monotone damage the table shows.

This does not refute MMR generally. It refutes MMR *on a corpus whose relevant
documents are topically clustered by design*, which the CR is.

## Recommendation

**Do not add MMR. Do not add BM25.** Both are settled by this run.

**`REWRITE_N = 1` -> `3` is a judgement call, not a clear win.** It is +3.8pp on
the headline metric with favourable paired flips, and it costs 3x the rewrite
output and 3x the query embeddings per question. The pre-registered bar was 7pp
and it did not clear it. Three ways to resolve that, in order of cost:

1. **Widen the sample.** The 150 held-out questions give ~3.4pp of sampling
   error at these rates. The corpus has 1,409 rows; retrieval scoring is free
   once rewrites are cached, so the limit is rewrite/embedding calls for the
   other 1,259, not compute.
2. **Try n=2.** The n=1-vs-n=3 gap may be mostly the first extra query. n=2
   would cost less and is a cell nobody has measured.
3. **Accept it on direction.** +10/−4 with a coherent mechanism is weak evidence
   but not no evidence, and the change is one line and trivially revertible.

Whatever is chosen, **the cost baseline has to be re-measured.** The opus-5
$0.0741/question figure was taken with `--no-rewrite`, so it does not include
even today's n=1 rewrite, let alone n=3.

**This experiment says nothing about answer quality.** It measures rules landing
in the window. Whether better retrieval converts into better answers is the open
question, and the way to settle it is Jon's rg6626 idea: hand generation the gold
rules directly and see whether it then answers correctly. That bounds what any
retrieval work can buy, and it should probably come before spending more on
retrieval tuning.

## Discrepancy worth recording

This run's baseline `groups`@15 is **11.4% (9/79)**; the previous session
reported **10.1% (8/79)**. One question's difference, same direction, same
retriever. Most likely the vector index append (606.5 and 119.1d were added
after that number was taken). It does not affect any conclusion here — every arm
is measured against the same baseline in the same run — but the two numbers are
not interchangeable and the older one should not be quoted alongside these.

## What this run does not cover

- Weighted fusion (only RRF was used, to keep one free parameter in the design).
- `n` other than 3 rewrites, and rewriters other than haiku v2.
- Reranking (already measured in `run_eval.py`).
- Raising `TOP_K`, deliberately: at effort low, input is ~55% of cost.
