# Plan — Gold by ablation: measure which rules a card query actually needs (DRAFT, pending Jon's review)

Working Rule 0 artifact. No code until reviewed.

## The idea (Jon, 2026-07-21)

Don't guess the rules-gold for a card question, and don't rubber-stamp what got
retrieved (circular). **Measure it:** hold the card data fixed, remove retrieved
rules one at a time, and see which ones the model actually needs to still answer
correctly. The minimal set of rules that keeps the answer correct IS the gold.

## What's fixed vs. what we ablate (Jon's scope call)

- **FIXED context (never ablated):** each `[card]`'s oracle text + all its
  Scryfall rulings. The pipeline always supplies these, so gold-discovery holds
  them constant.
- **ABLATED:** the retrieved CR rules (the generator's top-15 pool). Rules are
  what the RAG retrieves and what recall@k scores, so they're the variable.

A consequence worth stating up front: because rulings are always present, a rule
may test as *unnecessary* precisely because a ruling already covers it (c003's
prowess ruling literally says "goes on the stack on top of the spell... resolves
before it"). That's not a bug — it's the honest answer to "what must the RAG
retrieve to complement the card enrichment." If ablation finds a question needs
ZERO rules (rulings answer it alone), that question is a poor test of *rules*
retrieval — useful curation signal, not a failure.

## The correctness signal (the thing ablation can't do without)

To ask "does this subset still answer correctly," something must define correct.
Two options, defaulting to the cheaper:

1. **Default — the confirmed full-pool answer as the reference.** Generate the
   answer with the FULL rule pool + card data. Jon confirms it's correct (once,
   via the grading UI already built). Then the LLM-judge scores each ablated
   answer by **agreement with that reference** ("same conclusion?"). No separate
   reference-writing; reuses the grading flow. Risk: if the full answer is subtly
   wrong, we'd find the minimal set to reproduce a wrong answer — so Jon's
   one-time confirm of the full answer is load-bearing.
2. **Stricter — Jon writes a one-line reference** (the correct conclusion) per
   query. More work, fewer assumptions. Available per-question when he wants it.

The judge is an LLM-judge (pinned model), scoring correct/incorrect + a reason;
Jon spot-checks its verdicts.

## The search — leave-one-out, then group-out for redundancy

Brute force over 2^15 subsets is out. Two cheap passes:

1. **Leave-one-out (finds necessary / match=all members).** For each rule R in
   the pool: remove R, regenerate, judge vs the reference. If the answer breaks
   without R, R is **necessary**. Rules where removal breaks the answer are the
   match=all core.
2. **Group-out (finds match=any alternatives — the leave-one-out blind spot).**
   Leave-one-out alone MISSES redundant alternatives: if A and B each answer the
   question, removing A alone still works (B covers it) and removing B alone
   works (A covers it), so neither flags as necessary — yet one of them is
   required. Fix: take the rules that leave-one-out found individually-removable,
   remove them *as a group*, and regenerate. If that breaks the answer, the
   group contains alternatives → **match=any** over them. (Can bisect the group
   if it's large; for a 15-rule pool it's small.)

Output per query: the necessary set (match=all) + any alternative groups
(match=any), written as the gold in `cards.jsonl`.

## Generation noise (the #3a lesson, applied)

claude-sonnet-5 has no temperature pin, so a single ablated run can flip on
noise, not on the removed rule. So each subset is generated **3 times** and
judged by majority. A rule only counts as "necessary" if removing it breaks the
answer in a majority of trials. Borderline rules (2-1 splits) get flagged for
Jon rather than auto-decided. This is the same "don't trust one draw" discipline
that caught the rewrite non-determinism.

## Cost

Per query: (~15 leave-one-out + ~1 group-out + 1 full) subsets x 3 trials
x 1 generation each ~= 50 generations. Five queries ~= 250 generations, a few
minutes and a few cents (cached rewrites/embeddings/cards make everything but
generation free). Scales linearly with the eval set; still cheap.

## What it produces

For each card query in `cards.jsonl`: an empirically-grounded `gold` (rule ids)
+ `match` (any/all), plus a short provenance note ("gold by ablation: N trials,
these rules necessary, these alternative"). Reusable for the whole growing card
set, and re-runnable to re-validate gold if the retriever or prompt changes.

## Decisions for Jon

1. **Reference = confirmed full-pool answer (default) or you write one-liners?**
   I lean the former — you confirm the 5 full answers you've basically already
   seen, and the judge scores agreement. Less work, and it reuses the grading UI.
2. **Trials per subset = 3** (majority)? Or more for tighter noise control at
   more cost?
3. **Judge model** — claude-sonnet-5 (consistency with generation) or a cheaper
   judge? I lean sonnet for judgment reliability; it's few calls.

## Scope / limits (stated honestly)

- Ablation finds necessary rules **among those retrieved** (the top-15). A rule
  that's genuinely required but never retrieved (the q016 case) won't be
  discovered by ablation — it's not in the pool to remove. Those remain your
  judgment call, and they're exactly the retrieval-miss cases the recall eval is
  meant to expose. Ablation sets gold from what's reachable; retrieval-misses
  are a separate, already-handled concern.
- This measures rules-gold. Card-resolution accuracy and answer faithfulness
  (the other card-eval metrics) are unchanged and graded as before.
