# Report — RulesGuru held-out results overturn three working premises

Run 2026-07-24. First evaluation of Rulemancer on an **external, judge-authored**
question set (RulesGuru-150, gold by certified MTG judges). Everything before
this was measured on Jon's own 31-question set, which the rewriter prompt was
also tuned on — so this is the first non-circular measurement.

## Headline numbers

**Answer quality (auto-judged, frozen judge, Jon spot-checks disagreements):**

| tier | sonnet | gpt-5-mini |
|---|---|---|
| Level 0 | 93% | 77% |
| Level 1 | 87% | 63% |
| Level 2 | 67% | 60% |
| Level 3 | 63% | 50% |
| Corner Case | 50% | 37% |
| **overall** | **72% (108/150)** | **57% (86/150)** |

Monotonic across difficulty for both — which validates the difficulty labels and
the judge at once. Sonnet wins every tier; 3:1 pairwise (33 sonnet-right/mini-
wrong vs 11 the other way).

## Premise 1 OVERTURNED — retrieval "is a ranking problem, coverage is solved"

The shipped retrieval (`vec+rw1-haiku`), held-out vs the tuned 31-set:

| | @1 | @5 | @10 | @20 | @50 |
|---|---|---|---|---|---|
| Jon-31 (tuned) | 45% | 71% | 87% | 94% | **100%** |
| RulesGuru-134 (held-out) | 12% | 35% | 43% | 51% | **63%** |

On the tuned set, recall@50 = 100% — the basis for "the gold is always in the
pool, so it's just a ranking problem," which is the entire premise of
`plan-rerank-after-rewrite.md`. **On held-out data recall@50 is 63%**: for ~37%
of questions the gold rule is absent from the top 50 entirely. You cannot rerank
a chunk that was never retrieved. The ranking framing was an artifact of the
tuned set.

## Premise 2 OVERTURNED — retrieval hit predicts answer correctness

It barely does. Sonnet answered **108/150 correctly, but the gold rule was in the
top-5 for only 33 of them.** Even at recall@10 (~65 questions have gold), sonnet
is right on more questions than have the gold retrieved at all. **At least ~40
correct answers happen with the gold rule outside the generator's window.**

Cause, measured: of the 75 questions sonnet got right with gold absent@5, **74
(99%) have cards.** RulesGuru is 147/150 card questions (2.51 cards avg), and for
card questions the model answers from the **card's own oracle text** (enriched
via Scryfall), not the retrieved CR rules. This is exactly what c002's `ablation`
field already recorded: *"trample/deathtouch common enough that the model answers
from the keyword oracle text alone; retrieved rules redundant."*

## Premise 3 COMPLICATED — "the miss-partition cleanly splits retrieval vs reasoning"

Preliminary partition of sonnet's 42 misses (at hit@5, a proxy — the true window
is TOP_K=15, pending the assemble-only tweak): 28 gold-absent, 14 gold-present-
but-wrong. But given premise 2, "gold absent" does not cleanly mean "retrieval
failure" — the model may still answer from oracle text, and "gold present, wrong"
is the cleaner reasoning-failure signal (14 questions). The dichotomy is muddier
than the plan assumed because correctness is multi-sourced (parametric knowledge
+ oracle text + retrieved rules), not retrieved-rules-driven.

## What this means for the levers (Jon decides; nothing chosen here)

- **Rerank-after-rewrite:** its premise (coverage solved, ranking is the problem)
  is false on held-out data. Reranking cannot help the 37% of questions whose
  gold never enters the pool. **Weakened.**
- **Cost-calculator:** targets gold-present reasoning failures — the minority (14
  of 42, and card-math is a further subset). Real but small. Its value is
  unchanged and modest; it was never going to be the main lever.
- **The under-measured lever — retrieval COVERAGE** (chunking, embedding,
  rewriter quality getting the right chunk into the pool at all). Held-out
  coverage is low, and **sonnet-as-rewriter substantially improves it**: @10 56%
  vs haiku 43%, @50 75% vs 63% — a real held-out gain the 31-set dismissed as
  2-question noise. The rewriter question is live again, but on the *retrieval*
  side (where sonnet helps), not the generation side (where it is the same
  answer at 8x the cost).

## The measurement gap this exposes

RulesGuru is a strong END-TO-END answer-quality instrument but a **poor
CR-rule-retrieval instrument**, because 98% of its questions have cards and
oracle text confounds the retrieval signal. The place where CR-rule retrieval is
actually load-bearing — pure rules questions with no card to lean on — is
**3 questions** in RulesGuru. Properly testing whether the CR-rule RAG earns its
keep needs a held-out *pure-rules* set, which does not exist yet.

## Honest caveats

- Auto-judge numbers, not Jon's grades; disagreements logged (sonnet 42,
  gpt-5-mini 64). A 15-point monotonic gap survives judge noise.
- The judge is gpt-5-mini, so family bias would inflate gpt-5-mini's 57%, not
  sonnet's 72% — the answer-quality gap is conservative.
- RulesGuru is `match: "any"` (looser); real coverage on a strict bar is worse.
- The miss-partition is at hit@5; the clean @15 partition needs the assemble-only
  tweak (persist the retrieved ids it already computes but discards).
