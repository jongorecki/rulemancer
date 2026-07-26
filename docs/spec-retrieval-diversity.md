# Spec — retrieval diversity: MMR x hybrid x multi-query

**Ruled by Jon 2026-07-25: cleared to build** ("lets try it and see what happens.
Local resources are basically free right now"). Separate harness approved;
multi-query pinned to haiku.

## Why

The v2/v3 relabel showed retrieval is healthy at finding *one* relevant rule and
close to non-functional at getting two or three *distinct* ones into the window.
At production `TOP_K=15`:

| mode | n | groups that must ALL hit | @15 |
|---|---|---|---|
| `any` | 55 | 1.0 | 58.2% |
| `groups` | 79 | 2.4 | **10.1%** |
| `all` | 16 | 2.2 | **0.0%** |

That is a diversity problem, not a ranking problem. Cosine similarity clusters
near-duplicates (`613.3` / `613.7a` / `613.8a` eat the window together), which is
exactly what starves a multi-rule question.

**Do not just raise TOP_K.** At effort low, input tokens are ~55% of cost, so
15 -> 100 could double cost/question and erase opus-low's cost advantage.

## What already exists (this is mostly not a new build)

- **hybrid BM25+vector** — `retrieve/hybrid.py` (`rrf_fuse`, `weighted_fuse`,
  `Hybrid`), live as `hybrid-RRF` / `hybrid-wt0.5` arms in `run_eval.py`.
- **multi-query** — `rewrite_query(n=3)` + `rrf_fuse` over the per-rewrite
  rankings, live as the `vec+rw{n}-{label}` arms.
- **MMR** — does not exist. The only genuinely new component.

Note the gap this exposes: the existing multi-query arms fuse **vector-only**
rankings and never touch BM25, so **hybrid+MQ has never been measured.**

## Scope

### New: `src/rulesagent/retrieve/mmr.py`

```python
def mmr_select(candidates: list[Retrieved], vecs: np.ndarray,
               k: int, lambda_: float) -> list[Retrieved]
```

`vecs` is `(M, dim)`, row-aligned with `candidates`, L2-normalised (which
`VectorStore.embeddings` already guarantees, so doc-doc cosine is a dot product).

Greedy: take the highest-relevance candidate, then repeatedly take the argmax of

```
lambda * rel[i]  -  (1 - lambda) * max_{j in selected} cos(i, j)
```

**Relevance is min-max normalised within the pool before mixing.** RRF scores sit
around `1/61`; cosine sits around `0.3-0.8`. Mixed raw, `lambda` would mean
something different on a hybrid arm than a vector arm and the sweep would measure
the scale mismatch instead of the diversity trade-off.

Ties break by input order. Pure function: no I/O, no API, no global state.

### New: `evals/run_retrieval_diversity.py`

**Zero edits to `run_eval.py`** — it is the instrument that produced every
retrieval number quoted so far, and it picks its comparison baseline dynamically
(`best_arm`), so adding arms to it would silently change what past runs are
compared against. The new harness imports `load_questions`, `hit_at`,
`gold_groups`, `query_vectors`, `DEPTH`, `VECTOR_MODEL` from it.

Eight cells, `{vector, hybrid-RRF} x {no MQ, MQ} x {no MMR, MMR}`:

```
1  vector                 baseline
2  hybrid                 BM25 + vector, RRF
3  mq                     haiku n=3, RRF over the 3 rankings
4  hybrid + mq            NEVER MEASURED
5  vector + mmr
6  hybrid + mmr
7  mq + mmr
8  hybrid + mq + mmr
```

MMR selects from the depth-100 pool the arm already produces, so it is a
selection stage appended to the pipeline, orthogonal to fusion.

Hybrid uses **RRF, not weighted** — RRF is parameter-free, so the factorial
carries only one free parameter (`lambda`) instead of two. Weighted-vs-RRF is a
separate question `run_eval.py` already sweeps.

Questions: `evals/questions_rulesguru150_v3.jsonl` (v3, not v2).

### Spend guard

`--cache-only`, **on by default**. Rewrite and query-embedding lookups must hit
`data/cache.db`; a miss raises and names the offending question ids rather than
silently calling the API.

Rationale: Claude Code runs on Jon's Max subscription, but any Python in this
repo that constructs an Anthropic client bills **API credits**. MMR and hybrid
are pure local math and cost nothing. Multi-query is the one arm that must call a
model, and it is pinned to a single config (haiku, n=3) that is already cached —
which also keeps the matrix at 8 cells rather than 8 x 6.

Measured cache state at spec time: `query_emb` 150/150 of the v3 questions,
`rewrite` 145/150 with at least one entry.

## Metrics

- **recall@k at k = 5, 15, 50, 200**, reported overall AND split by match mode.
  The split is the point; the aggregate hides that `groups` is the broken half.
- **group coverage @15** — mean fraction of required gold groups present in the
  top-15. NEW. At 10.1% we are near a floor where binary hit/miss can stay flat
  while retrieval genuinely improves: going from 1-of-3 to 2-of-3 groups on forty
  questions would otherwise register as nothing.
- **regressions vs baseline**, listed per arm, never averaged away — the same
  zero-flip bar `run_eval.py` already applies.
- **lambda sweep**: 1.0, 0.7, 0.5, 0.3.

## Success criteria (fixed BEFORE running)

Headline: **`groups` recall@15**, currently 10.1%.

Retrieval here is deterministic — frozen query vectors, deterministic BM25,
cached rewrites — so there is no run-to-run noise. The only uncertainty is
sampling across the 79 `groups` questions: at p ~ 0.10 the standard error is
~3.4pp, so **a real win must clear roughly 7pp (2 SE).** Below that, group
coverage is the tiebreaker. Paired flips are reported in both directions, since
every arm sees identical questions and paired counts are more sensitive than
comparing two percentages.

## Tests — `tests/test_mmr.py`

- **`lambda = 1.0` reproduces the input ranking's top-k exactly.** The
  load-bearing self-test: if this fails the relevance term is wrong and every
  other number is meaningless.
- `lambda = 0` with three identical vectors + one distinct picks the distinct one
  second.
- `k > pool` returns the whole pool without crashing; empty pool returns empty.
- Same input twice gives identical output (determinism).
- Ties break by input order.

## Explicitly out of scope

**This measures rules landing in the window, not answers getting better.** Zero
generation spend means zero evidence about answer quality; an arm could win on
recall and change nothing downstream.

The follow-up that closes that gap is Jon's rg6626 idea — hand generation the
gold rules directly and see whether it then answers correctly. That bounds how
much any retrieval improvement can buy, and it is the natural next spec. It costs
generation spend, so it is deliberately not bundled here.

Also out of scope: raising `TOP_K`, weighted-vs-RRF tuning, re-embedding the
corpus, and the Voyage reranker (already measured in `run_eval.py`).
