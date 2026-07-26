# Spec — cosine floor: restoring a calibrated similarity signal RRF threw away

**Status: unruled.** Rule 0 applies — this is design only, nothing below is built.

## What a "cosine floor" is, concretely

Every chunk and every query gets embedded into the same vector space
(`src/rulesagent/index/embed.py`, Voyage, L2-normalized). Because both sides are
unit-length, the similarity between a query and a chunk is just their dot
product — that's `VectorStore.search_vec`'s whole implementation:

```python
# src/rulesagent/index/store.py:53-55
scores = self.embeddings @ qvec  # (N,)
ranked = np.argsort(-scores)[:k]
```

`scores` here is cosine similarity, one real number per chunk, roughly 0
(unrelated) to 1 (near-identical). A **cosine floor** is a minimum value a
chunk's score has to clear to be allowed into the final retrieved set — "if a
chunk isn't even weakly aligned with what was asked, don't hand it to the
model, no matter what rank some other process gave it."

That last clause is the whole point of this spec: **something else in the
pipeline already gives every surviving chunk a rank, and that rank is no
longer cosine similarity.**

## The problem, in concrete terms

Production runs multi-query retrieval: `REWRITE_N = 3`
(`src/rulesagent/generate/answer.py:160`) means every question gets rewritten
three ways by Haiku, each rewrite is embedded and searched independently to
depth `REWRITE_FUSION_DEPTH = 100`, and the three rankings are combined with
**Reciprocal Rank Fusion**:

```python
# src/rulesagent/retrieve/hybrid.py:24-32
def rrf_fuse(rankings: list[list[Retrieved]], k_rrf: int = 60) -> list[Retrieved]:
    scores: dict[str, float] = defaultdict(float)
    ...
    for ranking in rankings:
        for rank, r in enumerate(ranking, start=1):
            scores[r.chunk.source_id] += 1.0 / (k_rrf + rank)
    ...
```

RRF is deliberately rank-only — it never looks at `r.score` (the real cosine
value `search_vec` computed). That's a good design for combining BM25 and
vector rankings, whose raw scores live on incomparable scales. But it has a
side effect nobody asked for: **a chunk's real similarity to the question is
discarded the moment it goes through fusion.**

Concretely, a chunk that limps in at rank ~95 of 100 on two of the three
rewrites (cosine maybe 0.28 — barely above noise) accumulates
`2/(60+95) ≈ 0.0129` in RRF score. A chunk that scores a strong 0.70 cosine
but only shows up in one rewrite's ranking at rank 3 accumulates
`1/(60+3) ≈ 0.0159`. Those numbers are close enough that ranking position in
the final fused top-15 comes down to *how many rewrites happened to mention
it at all*, not how relevant it actually is. Before `REWRITE_N` went from 1 to
3, this couldn't happen — a single query's cosine score *was* the rank.
That's the "calibrated similarity signal" the change quietly removed.

This is very likely the mechanism behind the **38% chunk churn** multi-query
introduced (measured against the single-query baseline; see
`evals/run_eval.py`'s existing "Retrieved-set churn" report,
`evals/run_eval.py:427-450`, which already diffs `dropped`/`added`
chunk-ID sets between an arm and the baseline at the same k). Some of that
churn is the intended win — a genuinely relevant chunk that only one
paraphrase's wording could reach. Some of it is noise let in because RRF
can't tell the difference. The floor is a way to tell the difference back
apart, using a signal (`embeddings @ qvec`) the pipeline already computed and
threw away.

## Where exactly this sits — real call sites

`RulesAgent.answer()` has three retrieval paths
(`src/rulesagent/generate/answer.py:1996-2007`):

```python
if self.rewrite:
    if len(rewritten.queries) == 1:
        retrieved = self.store.search(rewritten.queries[0], self.k)          # (A)
    else:
        rankings = [self.store.search(q, REWRITE_FUSION_DEPTH) for q in rewritten.queries]
        retrieved = rrf_fuse(rankings)[: self.k]                             # (B) -- production
else:
    retrieved = self.store.search(question, self.k)                          # (C)
```

- **(A)** and **(C)** call `VectorStore.search` -> `search_vec` directly, so
  `Retrieved.score` on the result IS still real cosine. No problem exists on
  these paths today.
- **(B)** is what production actually runs (`REWRITE_N = 3`). This is where
  the signal is lost: `rankings` (three lists of up to 100 `Retrieved`, each
  with a real cosine `.score`) go into `rrf_fuse`, and what comes out the
  other end has RRF scores in the `.score` field, not cosine.

Right after that block, `retrieved` is handed to cross-reference expansion:

```python
# src/rulesagent/generate/answer.py:2008-2014
# Cross-ref expansion (L1): a pure post-ranking step -- runs AFTER
# retrieval/rewrite/fusion have already produced the organic top-k...
retrieved = expand_crossrefs(retrieved, self.chunk_map, debug=crossref_debug)
```

`expand_crossrefs` adds chunks by following explicit rule cross-references,
not similarity — those chunks never had a cosine score to floor against, and
shouldn't be asked to clear one. **The floor has to run on the organic
top-`k` before line 2014, not after** — the same ordering constraint the
crossref-expansion comment already documents for itself.

## Proposed shape (design only)

A pure function, same discipline as `mmr_select` in
`docs/spec-retrieval-diversity.md` (no I/O, no API, no global state,
deterministic):

```python
def floor_filter(
    retrieved: list[Retrieved],
    cos_max: dict[str, float],   # source_id -> best real cosine seen for it
    floor: float,
    min_keep: int = 1,
) -> list[Retrieved]:
    ...
```

Called once, right after the `if self.rewrite: ... else: ...` block (after
line 2007, before line 2008's crossref-expansion comment), so it sees every
path's output uniformly and its output is what crossref expansion consumes.

**Where does `cos_max` come from?** Two ways to get it, both effectively
free — this is an open decision (see below), not a settled implementation
detail:

- **Option A — capture it at the call site, don't touch `hybrid.py`.**
  Before calling `rrf_fuse(rankings)`, walk the same `rankings` list once and
  record `max(r.score for ranking in rankings for r in ranking with that
  source_id)` per chunk. `rankings` already holds real cosine scores (that's
  what `search_vec` put there) — this is a few dict updates over data already
  in memory, zero new matmuls, zero new embedding calls, and zero changes to
  `hybrid.py` (a shared module other call sites and tests depend on). For
  paths (A)/(C) above, `cos_max` is trivially `{id: r.score for r in
  retrieved}` since there's only one ranking and it's never been through RRF.
- **Option B — extend `rrf_fuse` itself** (e.g. a
  `rrf_fuse_with_cosine` variant) to return the max source cosine alongside
  the fused list, so `run_eval.py` and `evals/run_retrieval_diversity.py` get
  the same signal for free in their own arms. More invasive: it's a shared
  module other harnesses already import and test against.

Either way, note the phrase from the roadmap item this spec answers — "free
at runtime because `scores = embeddings @ qvec` is one in-process matmul" —
describes *reusing a query vector that's already been embedded* for this
question's own multi-query search. Nothing here calls Voyage or Anthropic an
extra time; it's arithmetic over numbers the pipeline computed anyway.

## What happens when the floor would empty the result set

A floor that's too aggressive (or a genuinely out-of-scope question) could
leave zero chunks above threshold. Returning an empty retrieved set is worse
than today's behavior — `build_prompt` has never had to handle "no rules at
all," and the generator's own honesty guard (`Answer.answered = False`,
`contracts.py:346-349`) exists precisely to say "the provided rules don't
cover this" — it needs *something* to look at and decline, not nothing.

Proposed guard: `min_keep` (default 1) — if fewer than `min_keep` chunks
clear the floor, keep the single highest-cosine candidate regardless of
whether it clears it, and let the generator's existing groundedness guard
decide whether that's enough to answer from. This never regresses relative
to today (worst case: one weak chunk, same as an unlucky top-1 today) and
never sends the model an empty context.

## Calibration — not a guessed number

The diversity results report a cosine distribution (`docs/results-retrieval-
diversity.md`'s "gold pairs" vs "random corpus pairs" table), but that's
**chunk-to-chunk** similarity, measured for MMR's diversity penalty. It's the
wrong distribution to copy a threshold from here — this floor is
**query-to-chunk** similarity, a different signal with a different scale, and
using the doc-doc numbers directly would be exactly the kind of unearned
precision this repo's standing lesson warns about.

The right calibration source is already on disk: the existing "Retrieved-set
churn" report (`evals/run_eval.py:427-450`) already identifies, per question,
which chunks are `added` by the multi-query fused arm relative to the
single-query baseline — that's the churn set. For every chunk in that set,
its real cosine score is recoverable (it's exactly `cos_max` above, computed
from data the eval harness already produces under `--cache-only`, zero new
calls). Split that set in two:

1. **Churned chunks that are gold** (multi-query correctly found something
   the baseline missed) — the floor must not cut these.
2. **Churned chunks that are noise** (not gold for that question, adding
   nothing but occupying a window slot) — these are the floor's actual
   target.

Sweep candidate floors (e.g. 0.25 / 0.30 / 0.35 / 0.40 — round numbers as
sweep points, not as a prediction of the right answer) and pick the highest
value that cuts a real fraction of group (2) while producing **zero paired
regressions** on group (1), using the same zero-regression bar
`docs/spec-retrieval-diversity.md`'s Success Criteria already applies. If no
floor value cuts noise without also touching gold, that's a real (negative)
result, not a failed calibration — it says RRF's damage isn't cleanly
separable by cosine alone, and is worth knowing either way.

## Metric that decides whether it worked

Same headline as the sibling retrieval-diversity work, so results are
directly comparable: **`groups`@15 recall**, currently 20.3% for the `mq`
(fused, n=3) arm per `docs/results-retrieval-diversity.md`. Success is
`groups`@15 at or above that number (floor must not cost recall) **and** a
measurable drop in chunk churn against the single-query baseline (the 38%
figure), reported the same paired, never-averaged-away way. A floor that
holds recall flat while shrinking churn is a clean win even without moving
the headline number, because it means the same useful chunks now arrive with
fewer noise chunks crowding the window — which is exactly the condition that
made `groups`@50 outperform `groups`@15 in the diversity results (mass
spread too thin at the top).

## Deciding experiment, and its cost

Add this as one more arm to `evals/run_retrieval_diversity.py`'s existing
harness rather than building a new one — the floor composes with every
existing cell (`mq + floor`, `hybrid + mq + floor`, etc.) the same way MMR
did. The harness already runs `--cache-only` by default and the 2026-07-25
run already confirmed cache coverage for the v3 150-question set: `query_emb`
150/150, `rewrite` 145/150. A cosine-floor sweep needs no new embeddings and
no new rewrites — it's pure thresholding over scores those cached arms
already produced.

**Cost estimate: $0.00 in Anthropic or Voyage API spend.** Basis: the
harness's own cache-only guard raises rather than silently calling out on a
miss, and every input the floor needs (per-rewrite cosine scores) is a
byproduct of runs already on disk. Wall-clock cost is milliseconds — the
`VectorStore` docstring's own claim (`store.py:1-6`) that a ~3,600-chunk
brute-force matmul is fast enough to not need a vector DB applies here
unchanged, since this adds no new matmul the search didn't already do under
Option A above.

If Jon wants this validated beyond the 150-question v3 set (e.g. filling the
145/150 rewrite gap, or extending to more of the 1,409-question corpus), each
additional question needs one Haiku rewrite call (~$0.0005/question per the
`REWRITE_N` comment in `answer.py:139-145`) and one Voyage query embedding.
Voyage isn't in `rulesagent.pricing` (that module only prices Anthropic
models) — it's a separate, small, non-Anthropic cost, worth naming plainly
rather than folding into "free."

## Rollback

Same pattern this codebase already uses for `effort`, `cache_prompt`, and
`REWRITE_N` itself: a module constant with a default that reproduces today's
behavior byte-for-byte when off, e.g. `COSINE_FLOOR: float | None = None` in
`answer.py`, threaded as a `RulesAgent.__init__` parameter
(`cosine_floor: float | None = None`) the same way `effort`/`cache_prompt`
are — so eval harnesses can A/B it without a code edit, and turning it off in
production is the same one-line revert already used for `REWRITE_N`.

## Tests (mirroring `tests/test_mmr.py`'s pattern)

- `floor = 0.0` (or `None`) reproduces the input list exactly — the
  load-bearing self-test; if this fails, the filter logic itself is wrong.
- A floor above every candidate's score returns exactly `min_keep` items
  (the single best), never zero.
- Same input twice gives identical output (determinism).
- Survivors keep their original relative order — filtering only, no
  re-ranking.
- `cos_max` lookup is a pure dict pass, no I/O, no global state.

## Explicitly out of scope

- Reranking (Voyage reranker — already measured separately in
  `run_eval.py`).
- Raising `TOP_K` (input-token cost argument already settled against this in
  the diversity spec).
- Hybrid BM25 (`docs/results-retrieval-diversity.md` already found hybrid
  neutral-to-harmful; not reopened here).
- MMR (already refuted on this corpus; not reopened here).
- Changing `rrf_fuse`'s public signature for every caller (only relevant if
  Option B below is chosen, and even then it should stay additive).

## Open decisions for Jon

1. **Where `cos_max` comes from:** Option A (capture at the `answer.py` call
   site, zero change to the shared `hybrid.py` module) vs. Option B (extend
   `rrf_fuse` so `run_eval.py` and the diversity harness get the same signal
   for free, at the cost of touching code other tests depend on).
2. **Empty-result behavior:** always keep the single best candidate
   regardless of the floor (recommended above) vs. genuinely allow an empty
   retrieved set and teach `build_prompt`/the generator to handle "no rules
   at all" as a distinct case vs. disable the floor per-question and fall
   back to the unfiltered fused top-k with a log line.
3. **Threshold source:** derive it empirically from the gold-vs-noise split
   of the existing churn report (recommended above, needs the sweep run to
   actually happen) vs. ship a placeholder round number now and recalibrate
   once real data comes back.
4. **Scope of the floor:** apply only to the `REWRITE_N > 1` fused path
   (where the problem is proven to originate) vs. apply uniformly to all
   three retrieval paths for one code path instead of three, even though
   paths (A)/(C) already carry real cosine and arguably don't need it.
5. **Gating:** land it behind a constructor parameter now (so it's
   eval-harness A/B-able before touching production) vs. a bare module
   constant only, decided later whether to expose it as a parameter.
