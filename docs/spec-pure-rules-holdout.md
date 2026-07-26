# Spec — Pure-rules held-out eval set, remaining scope

**Status: proposal only, per Rule 0. Nothing below is decided; it's the
options for Jon to rule on.** The mechanical scaffolding (join/validate/build
script, schema conformance, dedupe, gold-id-exists check, held-out guard,
tests) is DONE and described in the session report, not here. This document
is only about the part that's left: producing more approved question/gold
pairs beyond batch 1's 8, which requires an LLM to draft and Jon to judge —
exactly the part the task that produced this doc was told not to do.

## 1. Why this set exists (recap)

Every other eval question in this repo either IS a card question (RulesGuru,
1,409 rows, 98% reference a card) or was hand-written by Jon on a set the
rewriter prompt was tuned on (`evals/questions.jsonl`, 31 rows). Neither can
cleanly measure CR-rule retrieval: a card question can be answered from the
card's own oracle text without the retriever finding anything, and the tuned
set can't detect overfitting to itself. `docs/report-rulesguru-holdout.md`
measured this directly — of RulesGuru's 150-question holdout, only about 3
questions are ones where CR-rule retrieval is actually load-bearing rather
than redundant with the card text. The pure-rules set exists to be the
instrument that isn't confounded this way, and two live rulings
(`purerules-eval`'s dependents in `evals/_metrics_history.json`, the Lever 3
rewriter-model decision) are blocked on it existing at a usable size.

## 2. What "generalizing a card question into a rules question" means

This is not a new definition — it's what batch 1 already did, made explicit so
the next batches (whoever drafts them) apply the same test instead of
redriving it ad hoc. Four steps:

1. **Find the mechanism inside the judge's own gold answer.** RulesGuru's
   human-written `answer_gold` already states *why* — which CR rules apply,
   in what layer, in what order, and why one effect wins over another. That
   sentence is the thing being tested; the specific cards are just the
   vehicle.
2. **Replace every named card with a generic, unnamed permanent/spell/effect
   whose ONLY stated properties are the ones the mechanism needs.** No card
   name, no Scryfall lookup possible, no keyword the model could recognize
   and answer from independent of retrieval. If the mechanism needs "a
   creature with no abilities gets +2/+2," the question says exactly that
   instead of naming Muraganda Petroglyphs.
3. **The rewritten gold must be a paraphrase, never a new ruling.** Same CR
   citations, same logical structure, restated in the generic scenario's
   terms. `DECISIONS.md` (2026-07-24) is explicit that derived gold does NOT
   inherit RulesGuru gold's authority — see
   `rulesguru-gold-authority.md` in memory — precisely because it's a
   restatement of judge-authored reasoning, not an independent ruling.
4. **Selection gate: only generalize a source question whose gold ALREADY
   states the mechanism explicitly.** If the gold's conclusion depends on a
   fact that only exists on the specific card (a printed power/toughness, an
   arithmetic result not derivable from the rules text alone), the question
   can't be generalized without silently inventing content the original gold
   never stated. This is why `rg1989` was cut in batch 1: *"Gold states
   '-1/1' but the arithmetic does not follow from the rules content alone
   without reading the specific cards' printed power/toughness."*

Level/complexity/tags/CR-id citations carry over unchanged from the source
row — they describe the interaction's difficulty and category, which
paraphrasing doesn't change.

## 3. Three worked examples from batch 1 (real data, already approved)

**Example A — devotion + type-layer dependency (`pr001` from `rg5800`)**

- Source (named cards): *"Alex controls [Karametra, God of Harvests], and
  then casts [Opalescence]. Their devotion to white is 2. Is Karametra, God
  of Harvests a creature? If so, what is its power and toughness?"*
- Generalized: *"A permanent is an enchantment with a static ability saying
  it isn't a creature as long as your devotion to its color is less than
  five, and your devotion is currently two. A second enchantment then
  resolves whose static ability says every non-Aura enchantment you control
  is a creature with power and toughness each equal to its mana value. Is
  the first permanent a creature, and if so what are its power and
  toughness?"*
- What changed: Karametra's specific devotion threshold (seven, from its
  actual oracle text) and Opalescence's specific effect are both stated
  directly in the question instead of requiring the reader to know either
  card. The gold's CR citations (613.1d, 613.4b, 613.7) and its timestamp-
  ordering reasoning are unchanged.

**Example B — intrinsic ability vs. layer-6 removal (`pr003` from `rg222`)**

- Source: *"Nickolas controls [Dryad Arbor]. Aniya casts [Overwhelming
  Splendor], enchanting Nickolas. After it resolves, can Nickolas tap the
  Dryad Arbor for {G}?"*
- Generalized: *"You control a permanent that is both a land with a basic
  land type and a creature. An opponent resolves an effect saying creatures
  you control lose all abilities and have base power and toughness 1/1. Can
  you still tap that permanent for mana of the color its basic land type
  produces?"*
- What changed: the fact that a basic land type's mana ability is intrinsic
  rather than printed (CR 305.6) is stated as the general rule it is,
  instead of requiring the reader to know Dryad Arbor is a land-creature and
  infer that its mana ability comes from being a Forest, not from printed
  text.

**Example C — layer ordering across a source-ability removal (`pr008` from
`rg6682`)**

- Source: *"Ariana controls [Painter's Servant] naming 'blue.' Nico casts
  [Dress Down]. What color are Painter's Servant and Dress Down?"*
- Generalized: *"A creature has a static ability making all cards and
  permanents a single chosen color. An opponent then resolves an enchantment
  whose static ability says all creatures lose all abilities. What color is
  the creature, and what color is the opponent's enchantment?"*
- What changed: this is the CR 613.6 principle the project's own regrade
  found the production model getting wrong three times — an effect that has
  already applied in an earlier layer keeps applying even after the ability
  that generated it is removed in a later layer. The generalized version
  keeps that exact structure (layer 5 color effect, then layer 6 ability
  removal) without Painter's Servant's or Dress Down's specific wording.

## 4. What's left, sized

The source pool batch 1 drew from is `evals/_layers_union_slice.jsonl`, 68
RulesGuru rows that cite CR 613 (the layers rule). Batch 1 triaged 10 of
them: 8 approved as-is, 2 deliberately excluded (`rg1989` — see above,
`rg87` — near-duplicate of `rg5800`, dropped). **58 of the 68 have not been
looked at.**

Zooming out one level, `evals/rulesguru_full.jsonl` (1,409 rows total) has
114 rows tagged `Layers` — the 68-row 613-citing slice is a subset of that.
Jon's 2026-07-24 standing grant also removed the earlier constraint that
drafting stay inside the CR-613 slice specifically ("*you can pull from
whichever questions you need*"), and separately noted the set is meant to be
large enough to double as supervised rewriter-training signal, not just a
measurement instrument — "*nothing should be built on this until it is much
larger than 8 pairs*," without naming a target number.

## 5. Options for producing the rest

All three options use the **same mechanism batch 1 already used and Jon
already approved 8/8 with zero edits**: a Sonnet-tier subagent drafts a batch
of candidates into the same `purerules_candidates.json` shape, `evals/
build_purerules_approval_ui.py` renders them for review, Jon approves/
rewrites/cuts in the browser UI, `data/parsed/purerules_decisions.json` is
exported, and the (now-built) `evals/build_purerules_holdout.py` folds
approved rows into `evals/purerules.jsonl`. **This runs entirely on Jon's
Claude subscription — zero Anthropic API credits, same as batch 1** — so
there is no dollar cost to estimate; the real cost is subagent turns (which
are cheap and parallelizable) and Jon's review time (the bounded resource,
per `DECISIONS.md`'s own throughput note).

**Option 1 — Finish the sourced slice only (68-row CR-613 pool, 58 remaining)**
- Batch 1's demonstrated yield: 8 approved / 10 examined = 80%. At that
  rate, the remaining 58 rows yield roughly **45-47 more pairs** (~53-55
  total).
- Mechanism/cost: ~3 more drafting batches (58 rows / ~20 per batch, per the
  standing grant's batch-size guidance) + 3 bulk review passes for Jon.
  Lowest-risk option: every row is already known to cite CR 613 and already
  passed the "gold states the mechanism explicitly" screen once, at the
  slice-selection stage.
- Trade-off: caps out around 55 questions, all in one rule family (layers).
  May or may not be enough for the "training signal" ambition — Jon hasn't
  set that number.

**Option 2 — Widen to the full `Layers`-tagged pool (114 rows)**
- Adds the ~46 layers-tagged rows outside the 613-specific slice (some may
  cite adjacent sections rather than 613 itself, but are still layers
  interactions, which is the family batch 1 already validated generalizes
  cleanly).
- Mechanism/cost: same as Option 1, plus roughly 2-3 more batches for the
  additional 46 rows. Gets the total toward roughly 90-95 pairs at the same
  80% yield assumption, still one rule family, closer to whatever "much
  larger than 8" turns out to mean.
- Trade-off: still bounded to layers; doesn't test whether the CR-rule-
  retrieval gap generalizes to other rule families (triggered abilities,
  state-based actions, timing/priority), which is exactly what would make
  the held-out set representative of the whole corpus rather than of one
  mechanic.

**Option 3 — Pull from the full 1,409-row corpus per the standing grant**
- Widest pool, and the one the 2026-07-24 grant explicitly authorizes
  ("pull from whichever questions you need").
- Mechanism/cost: same drafting/review loop, but the yield rate is
  **unproven outside layers** — other rule families' gold text may describe
  outcomes ("here's what happens") without stating the general principle
  the way CR 613's dependency/timestamp language does, which is exactly the
  shape of gold that gets a candidate cut (the `rg1989` failure mode). Before
  drafting, this option needs a scoping pass per candidate rule-family tag to
  check whether that family's gold is rules-heavy enough to be worth
  drafting from at all — extra work Options 1-2 don't need, since the 613
  slice was already pre-selected for exactly this property.
- Trade-off: best long-run representativeness, worst near-term cost
  predictability (more batches likely to hit a lower approval rate, so more
  subagent-and-review cycles per net approved pair than Options 1-2).

**Considered and not recommended: programmatic templating instead of LLM
drafting.** CR 613's dependency/timestamp rules do have a recurring shape
that could in principle be turned into a small slot-filling generator
(deterministic, zero marginal cost, fully reproducible). It's set aside here
because (a) it's a real engineering project — a small domain-specific
grammar over layer rules — not a quick script, (b) generated scenarios would
still need the same human "does this say the same thing" review batch 1
already does by hand, so it relocates cost rather than removing it, and (c)
it doesn't generalize past the layers family either, so it doesn't solve
Option 3's actual gap. Flagged here in case Jon wants to weigh it against
Option 1/2's subagent-batch cost directly, but not carried forward as a
recommended option.

## 6. The actual open decision

Jon needs to rule on **how big this set should get and from how wide a
pool**, which is really two linked calls: (1) whether ~55 layers-only
questions (Option 1) is enough to unblock the two waiting rulings, or whether
the set needs to be big enough to double as rewriter-training signal per his
own 2026-07-24 note (in which case Option 2 or 3, and a target number); and
(2) whether it's worth spending the extra scoping effort Option 3 requires
to get rule-family coverage beyond layers, or whether staying inside the
proven layers slice is the right trade for now. Nothing here spends API
credits regardless of which option is picked — the cost is subagent batches
and Jon's review time, both of which scale linearly and predictably with
whichever option he picks.
