# Plan — rerank after rewrite: the untested combination

**DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Awaiting Jon's review.**

Source files read for grounding: `evals/run_eval.py`, `src/rulesagent/generate/answer.py`,
`src/rulesagent/retrieve/rewrite.py`, `src/rulesagent/retrieve/rerank.py`,
`src/rulesagent/contracts.py`, `evals/rulesguru.jsonl`, `evals/_rewriter_bakeoff_pass1.log`,
`docs/report-rewriter-bakeoff.md`, `docs/plan-rewriter-model-bakeoff.md`,
`docs/plan-3a-query-rewriting.md`, `docs/plan-l3-sqlite-caches.md`.

## The finding that motivates this

The rewriter bakeoff (`evals/_rewriter_bakeoff_pass1.log`, run 2026-07-23, report at
`docs/report-rewriter-bakeoff.md`) measured this for the shipped arm `vec+rw1-haiku`
over 31 questions:

| @1 | @5 | @10 | @20 | @50 |
|---|---|---|---|---|
| 45% | 71% | 87% | 94% | **100%** |

Recall@50 is 100%. The gold chunk is in the candidate pool for every question in this
set. The system retrieves the right thing and then fails to *rank* it into the window
the generator actually reads. That is a **ranking** problem, not a **retrieval-coverage**
problem, and the distinction matters because it points effort at reranking/prompt-window
size rather than at retrieval recall work (bigger `DEPTH`, more rewrites, a different
embedding model).

## The untested combination

The same log has reranker arms and rewrite arms, but only as **separate** arms:

| arm | recall@5 |
|---|---|
| `rerank:rerank-2.5` | 71% |
| `rerank:rerank-2.5-lite` | 68% |
| `vec+rw1-haiku` (shipped) | 71% |

Every reranker arm reranks the **plain-vector** candidate pool. Every rewrite arm feeds
its fused ranking **directly** to the generator with no reranking stage. Nobody has
measured **rewrite -> retrieve top-50 -> rerank -> top-k**. The harness already reranks
a pool of 50 (`RERANK_POOL = 50`, `evals/run_eval.py:40`) — big enough to hold the gold
for effectively every question at this recall@50, so stacking is plausible on the numbers
already in hand, just never built.

## 1. How the two existing arm types are actually built (file:line)

### Rewrite arms

- `evals/run_eval.py:157-158` — `rewrite_arm_name(label, n)` returns `f"vec+rw{n}-{label}"`.
  This is the ONLY place arm names for rewrite configs are constructed; every dict that
  scores an arm (`hits`, `per_q5`, `top_gen_k`, `individual_by_arm`) is keyed off this
  string, and `docs/report-rewriter-bakeoff.md`'s tables are transcribed from these same
  keys.
- `evals/run_eval.py:222-233` — one `rewrite_query()` call per `(question, label, n)`,
  building `rewrites: dict[(q.id, label, n), RewrittenQuery]`. This is a pure text-generation
  step; no retrieval happens here.
- `evals/run_eval.py:248-256` — `rewrite_rankings(q_id, label, n)`: looks up the cached
  rewrites, runs `vstore.search_vec()` **once per rewrite string** at `DEPTH = 100`
  (`run_eval.py:37`), and RRF-fuses them (`rrf_fuse`) if `n > 1`. Returns `(fused, individual)`
  — `individual` is kept so the `+orig` variant (`run_eval.py:333-357`) can re-fuse without
  re-searching.
- `evals/run_eval.py:307-313` — inside the per-question loop, for every `(label, n)` in
  `REWRITE_MODELS x REWRITE_NS`: computes `fused, individual = rewrite_rankings(...)`,
  stores `rankings[arm] = fused` (an **unranked-by-rerank, RRF-ordered** `list[Retrieved]`
  of up to `DEPTH`-ish candidates after fusion), and caches `individual_by_arm[(q.id, arm)]`.
  **This is the seam**: `fused` is the exact object a stacked rerank stage would take a
  `[:RERANK_POOL]` slice of.

### Rerank arms

- `evals/run_eval.py:40-41` — `RERANK_POOL = 50`, `RERANK_MODELS = ("rerank-2.5", "rerank-2.5-lite")`.
- `evals/run_eval.py:117-138` — `cached_rerank(query, candidates, model, cache, chunk_map)`:
  keys the on-disk cache by `json.dumps([model, query, list(pool_ids)])` where `pool_ids`
  are the `source_id`s of the **candidates actually passed in** — the key is derived from
  the pool's contents, not from which retriever produced it. This matters: swap in a
  rewrite-arm's fused pool instead of the plain-vector pool and the cache key changes
  automatically (different `pool_ids` most of the time), so there is **no collision risk**
  with the existing plain-vector rerank cache entries — no cache-schema change needed for
  this seam.
- `evals/run_eval.py:302-306` — the only call site: `cached_rerank(q.question, vec[:RERANK_POOL], m, rerank_cache, chunk_map)`
  for each `m in RERANK_MODELS`, where `vec` is the plain-vector top-`DEPTH` ranking
  (`run_eval.py:295`). **The query string passed to the reranker is always the original
  question, never a rewrite.** The candidate pool is always the plain-vector ranking,
  never a rewrite-arm's fused ranking. Both of those are the two things this plan's build
  changes.
- `src/rulesagent/retrieve/rerank.py:26-37` — `rerank(query, candidates, model, top_k=None)`
  wraps Voyage's `client.rerank()`; it is retriever-agnostic — it has no idea whether
  `candidates` came from plain vector search or a rewrite fusion, so no source change is
  needed there either.

## 2. What exactly gets built

One new arm, added at the same seam as the rewrite arms (`run_eval.py:307-313`, inside
the per-question loop, right after `rankings[arm] = fused` is assigned for the shipped
control):

```
stacked_pool = fused[:RERANK_POOL]                      # fused = vec+rw1-haiku's ranking
rankings["vec+rw1-haiku+rerank:rerank-2.5"] = cached_rerank(
    query_text, stacked_pool, "rerank-2.5", rerank_cache, chunk_map
)
```

scoped to **the shipped control only** (`vec+rw1-haiku`) crossed with **both existing
reranker models** (`rerank-2.5`, `rerank-2.5-lite`) — 2 new arms, not a full
rewrite-arm x reranker-model cartesian product (6 x 2 = 12 arms; see Non-goals). This
mirrors the precedent already in the file: the `+orig` variant (`run_eval.py:338`) is
computed only for `best_arm = max(rw_arm_names, key=...)`, a single derived arm layered
on top of the winner, not every combination.

**`query_text` is an open design decision, not a detail to wave past** — the reranker's
own docstring (`rerank.py:1-4`) says it "rereads the query against each candidate's full
text TOGETHER," so what string plays "the query" changes what gets scored:

| option | what it scores | risk |
|---|---|---|
| **(a) `q.question`** (recommended default) | the user's real information need vs. each rewrite-sourced candidate | reranker never sees the CR-vocabulary phrasing that got these candidates retrieved in the first place — plausible but untested that this still works well |
| (b) the primary rewrite string (`rw.queries[0]`) | the CR-vocabulary query vs. its own candidates | closer to what the rewrite step already optimized for; but `rewrite_rankings()` only returns the fused ranking, not "the" rewrite when `n>1` — needs a tie-break rule |
| (c) rerank once per rewrite string, RRF-fuse the reranked lists | most thorough | multiplies reranker calls by `n` (n=1 for the shipped control, so this collapses to (b) exactly for `vec+rw1-haiku` — not a real cost difference at n=1, but does not generalize to the `rw3` arms if this is ever extended there) |

Recommendation: **(a)**, because at n=1 there is exactly one rewrite string and it is
very close in meaning to the original question by construction (the rewrite prompt is a
translation task, not a rephrasing-away-from-intent task — `rewrite.py:1-16`), and because
(a) is what a production call would actually have available cheaply (the user's real
question, not a cache of which rewrite string produced which candidate). This is
Jon's call to confirm, not a default to build silently.

**Arm-naming and report-code compatibility (constraint #2 from the task):**
`rewrite_arm_name()` (`run_eval.py:157-158`) only builds the six `vec+rw{n}-{label}`
names; it is not reused for this new arm, and does not need to be — the plan proposes a
literal new name, `f"{rewrite_arm_name(label, n)}+rerank:{model}"` e.g.
`"vec+rw1-haiku+rerank:rerank-2.5"`, following the same slash-free discipline the comment
at `run_eval.py:46-49` documents (a `/` in an arm name corrupts the dict keys the report
code — and `docs/report-rewriter-bakeoff.md`'s tables — key off). Both `rerank-2.5` and
`rerank-2.5-lite` are already slash-free (used bare as `RERANK_MODELS` today), so this
holds with no further encoding. One cosmetic-only wrinkle: the per-question hit@5 matrix
printer truncates the **column header** to 16 characters (`run_eval.py:390`,
`name[:16]`), so `"vec+rw1-haiku+re"` is what prints there — the full name is still the
real dict key everywhere else (the `hits`/`per_q5` tables, the summary rows), so this is
a display-only truncation, not a data problem, but it means the printed matrix header
alone won't disambiguate `rerank-2.5` from `rerank-2.5-lite` without widening that column
or shortening the name (e.g. an abbreviation table) — flagged so it isn't a surprise at
build time, not proposing a fix now.

`method_names` / `matrix_names` (`run_eval.py:260-265`) need the two new names appended
before the `hits`/`per_q5`/`top_gen_k` dicts are initialized (`run_eval.py:277-288`),
same as any other arm.

## 3. The evaluation instrument: n=31 is too small for this

One question is `1/31 = 3.2` percentage points. The reranker arms in the existing log sit
within a 3-point band of the rewrite arms (68-71% vs 71-77%) — smaller than a single
question. A stacked arm's apparent gain or loss over `vec+rw1-haiku`'s 71% could be
1-2 questions moving, which is not distinguishable from noise at this n (this is the same
caveat `docs/report-rewriter-bakeoff.md`'s "The caveat that governs everything above"
section already raised for the rewrite-model bakeoff, and it applies here with the same
force).

`evals/rulesguru.jsonl` carries 150 questions with human-written gold; 134 of them have a
non-empty `gold` list of CR rule ids (verified by reading the file: `150` total lines,
`16` with `gold: []`, `134` with real ids — the empty-gold rows are already handled by
`run_eval.py`'s existing `n_scored` denominator logic at `run_eval.py:267-268`, unchanged
by this plan). Per `src/rulesagent/contracts.py:161-162`, a `gold` id must be a chunk
`source_id` — the field name the task called out (`Chunk.source_id`, `contracts.py:105`,
not `rule_id`) is confirmed by reading the schema directly. This plan proposes running the
stacked arm against `evals/rulesguru.jsonl` (134 scored questions, ~4.3x today's n) rather
than re-deriving that decision here — **`docs/plan-rulesguru-as-instrument.md`, being
written in parallel, is the authority on how that set gets adopted as the eval instrument**
(loader changes, `--questions` flag usage, any known label-noise caveats). This plan only
asserts that whichever arms get compared, they should be compared **on the same instrument**,
and 134 questions resolves the "is a 2-3 point gap noise" problem far better than 31 does —
it does not eliminate it (see Cost, below, for what a 134-question pass costs).

## 4. The variance problem, measured, not hypothetical

Two separate findings already on record, both directly relevant to whether a rerank
result here can be trusted from one pass:

**(a) The rewrite cache replays, it doesn't re-measure.** Rewrites are cached in
persistent SQLite keyed `[model, version, n, question]` (`rewrite.py:159-167`, the actual
key construction at `rewrite.py:197`) — **no pass index**. `docs/report-rewriter-bakeoff.md`
already establishes that invoking `run_eval.py` repeatedly replays the cached rewrite for
`vec+rw1-haiku` byte-for-byte; passes 2 and 3 are identical to pass 1. A rerank arm built
on top of `fused` inherits this: for a fixed candidate pool, `rerank.py`'s underlying
Voyage call is itself deterministic (`run_eval.py:121-122`'s comment on `cached_rerank`:
"Voyage's reranker is deterministic, so a cached result is identical to a fresh one"), so
**the reranker adds zero additional variance of its own** — every measured swing between
runs of the stacked arm would come from the upstream rewrite step re-sampling, and the
persistent cache prevents that re-sampling from ever happening unless the cache is
deliberately bypassed.

**(b) Only the shipped rewriter is stabilised, and even that stabilisation is not proven
to be complete.** `rewrite.py:34` — `TEMPERATURE_OK = {"claude-haiku-4-5"}`. Only the
shipped haiku rewriter runs at `temperature=0`; the code comment at `rewrite.py:252-259`
records the measured consequence of **not** having that pin: *"without it, rw1-haiku
recall@5 swung 68-77% across clean re-runs because each run drew different rewrites."*
That is a 9-point band on the exact headline metric this plan would use to judge a rerank
gain. Temperature=0 is documented as cutting, **not eliminating**, that variance (same
comment) — the residual swing of the *stabilised* shipped path has never been measured,
because the only way to measure it is to bypass the persistent cache and draw multiple
independent rewrite passes, which nobody has done.

**What this means concretely for this plan:** a rerank-after-rewrite delta smaller than
the known 9-point band is not safely attributable to reranking from a single pass — it
could be within the rewrite step's own noise, even under `temperature=0`, since that
residual is unmeasured rather than known-zero. `docs/report-rewriter-bakeoff.md`'s "What
would settle this" #1 already proposes the fix this plan would also need: add a pass
index to the **rewrite** cache key for bakeoff/experiment runs (leaving the embedding and
rerank caches alone, since those are not the variance source). This plan does not
re-propose that change — it names it as a **shared prerequisite** should Jon want a
result trustworthy below a 9-point gap, and notes that the reranker itself, being
deterministic, does not add to the multi-pass cost once the rewrite cache is defeated
(the rerank leg of a repeat pass is either a fresh legitimate rerank of a genuinely
different candidate pool — cheap, see Cost — or a cache hit on an unchanged pool, free).

## 5. The generator window: reranking might move a metric without moving an answer

`TOP_K = 15` (`src/rulesagent/generate/answer.py:32`, "pure-vector top-15 (raised from
10: near-miss rules like a multiplayer clause at rank ~13 were just outside the old
window)") is the number of chunks the generator's prompt actually contains — confirmed by
reading `RulesAgent.answer()`: the rewrite path retrieves `rrf_fuse(rankings)[: self.k]`
(`answer.py:1143`, `self.k` defaults to `TOP_K`) and `build_prompt()` -> `_format_context()`
(`answer.py:745-746`) renders exactly that list, in that order, as `[id] text` blocks —
nothing downstream re-ranks or re-selects from within it before it reaches the model.

Recall@10 is 87% and recall@20 is 94% (`vec+rw1-haiku`, current log) — so recall@15 sits
between them, plausibly near 90%, meaning **the gold chunk is already inside the
generator's actual window on roughly 9 of 10 questions before any reranking happens.**
Reranking a 50-candidate pool can only help an answer on the minority of questions where
the gold currently sits at rank 16-50 (outside `TOP_K`) and the rerank step promotes it to
rank <=15. For every question where the gold is already inside the top 15, reranking can
only reorder *within* a window the generator already fully receives — and because
`_format_context()` preserves rank order in the prompt, that reordering is not provably a
no-op (position within a list can bias which facts an LLM weighs), but it is a much
weaker, unmeasured, second-order effect compared to a chunk crossing the window boundary.

**The plan states plainly, per the task's requirement:** an improvement in
recall@5/recall@10 from stacking reranking after rewriting can happen entirely through
reshuffling chunks that were already inside `TOP_K = 15` — a real move on a retrieval
metric that corresponds to **zero** change in what the generator reads, and therefore
zero possible change in the answer. Recall@5 in particular is almost entirely insulated
from `TOP_K`; a recall@5 win says nothing about whether anything crossed the rank-15
boundary at all.

**How to tell the two apart before spending on it (proposed, not yet built):**

1. Add `15` to the eval's `KS` tuple (`run_eval.py:36`, currently `(1, 5, 10, 20, 50)`)
   for this comparison specifically, so recall@`TOP_K` is a first-class number instead of
   interpolated between @10 and @20 by eye.
2. Reuse the existing "retrieved-set churn" report (`run_eval.py:395-421`) — already
   built for exactly this question (comparing the plain-vector top-`GEN_TOP_K` set against
   the best rewrite arm's top-`GEN_TOP_K` set) — pointed at `vec+rw1-haiku`'s top-15 vs the
   stacked arm's top-15, per question. Its `dropped`/`added` id lists directly answer "did
   anything actually cross the window boundary" on a per-question basis, which is the fact
   that determines whether the generator could possibly answer differently.
3. Only for questions where the churn report shows a real `added`/`dropped` id (gold
   crossing the boundary, in either direction) does re-running the generator and comparing
   answers make sense. That is a small, targeted set — not a full 31- or 134-question
   regeneration pass — and is the honest way to check whether a retrieval-metric win is
   also an answer win, without paying for a full generation + judge pass this plan has not
   scoped or costed.

## 6. Cost

**Reranker calls per question per arm:** exactly 1 (`cached_rerank()` is one Voyage
`rerank()` call per `(query, pool)` pair, `rerank.py:26-37`; `RERANK_POOL = 50` sets the
pool size, not the call count). Cost per call is priced per input token across the query
plus all 50 candidate chunk texts (`docs/embedding-providers.md:19`: `rerank-2.5`
$0.05/M tokens, `rerank-2.5-lite` $0.02/M tokens). Chunk text length was not measured
precisely in this pass (no `data/parsed` in this worktree to sample from — gitignored,
absent per the environment note) — `docs/plan-chunk-context-split.md:32-52` gives the one
corpus-wide figure on record, median **parent** text of 55 chars with a fat tail (up to
several hundred), which is a different field than a full chunk's `text` (own text + parent
context) and so only a loose proxy. **Recommend a free pre-flight check before greenlighting
spend:** summing `len(c.text)` (or a real tokenizer count) over one built chunk set costs
nothing and would replace this estimate with a real number before any paid call is made.

Bounding it anyway on the loose proxy (50 candidates x ~150-400 chars each, call it
150-400 tokens/chunk at a rough 1:1 char:token overestimate for safety, plus a short
query) puts one call at roughly 8K-20K input tokens, i.e. **$0.0004-$0.001 per call**
at `rerank-2.5` pricing, **cents-not-dollars territory** for the arm sizes this plan
actually proposes:

| pass | new reranker calls | rough cost |
|---|---|---|
| 2 stacked arms x 31 questions (n=31 instrument) | 62 calls | under $0.10 |
| 2 stacked arms x 134 questions (rulesguru instrument) | 268 calls | under $0.30 |
| + a second multi-pass run to size the variance band (§4) | pool composition may repeat across passes if the upstream rewrite didn't change -> cache hits, free; a genuinely new rewrite pool re-pays the rerank call | additive, small |

Every number in this section is dollars-per-experiment, not per-question-in-production —
`cached_rerank()`'s cache means a re-run against an unchanged candidate pool makes zero
new calls (`run_eval.py:131-134`), same discipline as every other arm in this harness.

**Billing note (per the user's standing billing preference):** these would be real Voyage
API calls, part of the product's own retrieval pipeline being evaluated — not
analysis/writing labor — so metered API spend is the correct and expected billing path
here if this plan is approved, the same distinction `docs/plan-rewriter-model-bakeoff.md`'s
own cost section draws for its rewriter calls. Nothing about this plan should route
through subscription Claude-Code subagents as a cost-avoidance measure; that preference
governs Claude-labor, not the product's own reranker/embedding spend.

## 7. Non-goals

- **Not** the full rewrite-arm x reranker-model cartesian product (12 arms: 6 rewrite arms
  x 2 reranker models). Scoped to the shipped control (`vec+rw1-haiku`) x both existing
  reranker models, 2 arms, mirroring the `+orig` precedent of layering one derived arm on
  the winner rather than re-running everything.
- **Not** a change to `TOP_K` / `GEN_TOP_K` in `answer.py`. If §5's churn analysis shows
  the window itself is the binding constraint (i.e. most misses sit just past rank 15
  regardless of reranking), that is a separate, follow-up plan, not this one.
- **Not** a change to the rewrite cache's key schema (the pass-index fix from
  `docs/report-rewriter-bakeoff.md` §"What would settle this"). Named as a prerequisite
  for a below-9-point-confident result, not re-designed or re-decided here.
- **Not** adopting `evals/rulesguru.jsonl` as the eval instrument — that decision and its
  mechanics belong to `docs/plan-rulesguru-as-instrument.md`. This plan only assumes
  whichever instrument is chosen is used consistently across the arms being compared.
- **Not** a generation-quality pass (re-running the generator + judge on questions where
  the retrieved set changes). §5 proposes the churn-based way to identify a small
  candidate set for that follow-up; running it is out of scope for this plan.
- **Not** a change to `src/rulesagent/generate/answer.py`'s production retrieval path.
  This is an eval-harness-only experiment (`evals/run_eval.py`); shipping a
  rerank-after-rewrite stage to production is a separate decision gated on this
  experiment's result.

## 8. What would change Jon's mind

- **A recall@`TOP_K`=15 gain (not recall@5) exceeding the ~9-point known noise band**,
  ideally corroborated by the churn report showing real ids crossing the window boundary
  on a meaningful fraction of questions — that is the number that says "the generator
  would actually see something different," not just "the retrieval metric moved."
- **Consistency across both instruments** (n=31 and rulesguru n=134), or at minimum a
  rulesguru-scale result given how close the arms already sit at n=31.
- **A negative or flat result is also actionable**: if recall@15 doesn't move but
  recall@5 does, that's direct evidence the ranking problem this plan opened with is being
  fixed in a region the generator never reads at `TOP_K=15` today — which would argue for
  spending effort on raising `TOP_K` instead of on reranking, a different plan.
- **Cost staying in the cents-to-low-dollars range** measured in §6 holding up once real
  chunk-token counts replace the loose estimate — if the real number is materially higher,
  that reopens the scoping conversation before any call is made.
