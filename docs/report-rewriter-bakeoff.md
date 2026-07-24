# Report — rewriter model bakeoff, phase 1 (retrieval only)

Run 2026-07-23 overnight. Retrieval-only, per `docs/plan-rewriter-model-bakeoff.md`.
Jon's ruling on scope: **add `openai/gpt-5-mini` only**; the shipped
`claude-haiku-4-5` control and the existing sonnet arm come along because
`run_eval.py` has no per-arm selector.

## READ THIS FIRST — what was NOT measured

**This is ONE pass. Stability was not measured, and the plan's 3-pass
requirement could not be met as written.**

Rewrites are cached in persistent SQLite (`KVCache`, key
`[model, version, n, question]` — no pass index) and query embeddings are cached
by string. Invoking `run_eval.py` three times replays the cache; passes 2 and 3
would be byte-identical to pass 1, and the plan's "recall@5 mean with the
observed range" would report **range = 0**. That reads as perfect stability and
actually means a deterministic cache.

The caching is deliberate, not a defect — `query_vectors()`'s own docstring says
Voyage returns slightly different vectors on repeated calls and the cache exists
so the eval is reproducible. Defeating it is a methodology decision reserved for
Jon (see "What would settle this").

## Results — recall@k, 31 questions, voyage-4-large, 3617 chunks

| retriever | @1 | **@5** | @10 | @20 | @50 |
|---|---|---|---|---|---|
| `vec+rw1-haiku` **(shipped control)** | **45%** | **71%** | **87%** | **94%** | **100%** |
| `vec+rw3-haiku` | 45% | 74% | 87% | 87% | 97% |
| `vec+rw1-sonnet` | 35% | **77%** | 87% | 94% | 97% |
| `vec+rw3-sonnet` | 39% | 74% | 87% | 97% | 100% |
| **`vec+rw1-gpt5mini`** | 39% | **71%** | 81% | 81% | 90% |
| **`vec+rw3-gpt5mini`** | 29% | **71%** | 77% | 87% | 100% |
| voyage-4-large (no rewrite) | 29% | 68% | 84% | 87% | 94% |

Regressions vs the pure-vector baseline at hit@5 — lower is better:

| arm | regressed questions |
|---|---|
| `vec+rw1-sonnet` | 1 — q003 |
| `vec+rw1-haiku` (control) | 2 — q003, q019 |
| **`vec+rw1-gpt5mini`** | **3 — q003, q025, q030** |

Clarification rate (bar: <= 5 of 31) — every arm passes: haiku 0/31, sonnet
1/31 (q020), gpt5mini 1/31 (q016).

## Finding

**gpt-5-mini does not beat the shipped haiku rewriter.** It ties exactly at
recall@5 (71% vs 71%), is worse at every other depth measured (@1, @10, @20,
@50), and regresses one more question than the control against the pure-vector
baseline. Nothing here supports switching the rewriter.

That is a clean negative on the plan's own framing, which called gpt-5-mini
"Jon's headline pick — reasons about rules well, cheap." The plan also warned
about exactly this outcome: *"rewriting is not a reasoning task, it's a
translation task"*, and a reasoning model *"asked to 'rewrite this into CR
vocabulary' may over-think."* The measurement is consistent with that warning.

## THE CONFOUND — the control is variance-stabilised and the candidates are not

Raised by Jon, 2026-07-23: *"are we using the same prompt between haiku and
gpt-5-mini for the rewriter? it could impact data."*

**The prompt is identical** — verified in code, not assumed. `system_text` and
the user `content` are both built ONCE before the backend branch in
`rewrite.py`, and both branches consume them; both land on the same `_Rewrites`
schema; nothing extra is appended on the OpenRouter path (unlike
`judge_bakeoff.py`, which had to add a one-word-verdict instruction for
OpenRouter judges). Same prompt, same `n`, same schema.

**But the sampling is not identical, and this is the bigger issue.**
`rewrite.py:33` — `TEMPERATURE_OK = {"claude-haiku-4-5"}`. Only haiku gets
`temperature=0`. Sonnet and gpt-5-mini both reject sampling params, so both run
at default sampling. The code comment states the measured consequence:

> "temperature=0 cuts (does not eliminate) the run-to-run variance in the
> rewrites -- **measured: without it, rw1-haiku recall@5 swung 68-77% across
> clean re-runs** because each run drew different rewrites."

**68-77% is the entire band every arm in this bakeoff landed in (71-77%).** So
the control arm is variance-suppressed while both candidate arms are single
draws from a distribution roughly as wide as the differences being reported.

This is not a defect introduced by the new OpenRouter path — it is forced, since
those models reject the parameter. But it means:

- **gpt-5-mini's tie at recall@5 is one sample**, not a level.
- **Sonnet's apparent 6-point lead is one sample**, and cannot be read as a win.
- The single-pass limitation below is therefore *worse* than "no stability
  measurement": for two of three arms there is a **known, measured** instability
  of about 9 points, and this run cannot see it.

The one claim that survives: gpt-5-mini is at or below the control at **every
depth measured** (@1, @5, @10, @20, @50) and regresses more questions. A
consistent direction across five depths is harder to produce by sampling noise
than a single-metric difference — but it is still one draw.

## The caveat that governs everything above

**n = 31. One question is 3.2 percentage points.** So `vec+rw1-sonnet`'s
apparent 6-point lead over the control is **2 questions**.

And the plan itself defines that magnitude as noise:

> "A candidate whose recall@5 is 74/77/71 across three clean runs is noise."

The observed spread across all six rewrite arms here is 71-77 — precisely that
band. **So the sonnet arm's apparent win is NOT actionable from this data**, and
saying otherwise would be reading a single pass as if it were a mean.

What the data does support, more weakly than a 3-pass run would: gpt-5-mini
shows no gain at the headline metric and consistent small losses at every other
depth, which is a harder pattern to explain away as noise than a single-metric
difference would be.

## Cost

Marginal spend was **62 gpt-5-mini rewrite calls** plus embeddings for the new
rewrite strings. Every haiku and sonnet rewrite was already cached, so the
control arms cost nothing to include. Cents, not dollars.

## What would settle this

1. **A real multi-pass spread** requires defeating the rewrite cache. Cheapest
   honest option: add a pass index to the **rewrite** cache key for bakeoff runs
   only, leaving the embedding cache alone — rewrite variation is the thing
   being measured. Bypassing both also re-pays every Voyage call. This matters
   more than it did before the confound above was noticed: for the two arms that
   cannot take `temperature=0`, repeat passes are not a nicety, they are the
   only way to see a number that means anything.
2. **A bigger n.** At 31 questions no rewriter comparison can resolve a
   2-question difference, with or without repeat passes.
3. **Decide what a fair comparison even is.** The shipped path is stabilised at
   `temperature=0` and the candidates structurally cannot be. Two defensible
   framings: compare each arm at *its own best available setting* (what this run
   did — control stabilised, candidates not), or compare all arms *unstabilised*
   by dropping `temperature=0` from the haiku eval arm, which is apples-to-apples
   but throws away a property the shipped path actually has. The first answers
   "should we switch?", the second answers "which rewriter is better?" They are
   different questions and this run only addresses the first.

## Status

Instrument merged to master: `rewrite_query()` now takes a `backend` parameter,
default `"anthropic"` and byte-for-byte unchanged, with an OpenRouter path for
non-Anthropic rewriter arms. `REWRITE_MODELS` carries a slash-free `gpt5mini`
label. 267 tests green at merge.

No rewriter change is recommended. The decision is Jon's.
