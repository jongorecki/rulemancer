# Plan — Rulings by relevance: pull the specific relevant rulings, ground on them (DRAFT, pending Jon's review)

Working Rule 0 artifact. No build until Jon signs off. A rules+oracle-only spike
is running to calibrate the details (see "Spike" below); the direction here is
already decided by Jon's grounding call.

## The idea (Jon, 2026-07-21)

> "Ignore the per-card rulings unless we specifically need them... While a global
> rulings corpus should be eventually in our plan, retrieved by name of the card,
> I don't think it's something we want to do yet."
>
> "Could we also pull the specific rulings being referenced in the per-card
> rulings to really drive home the RAG? We really need to make sure we don't rely
> on the training data at all whenever possible. We need to stay grounded."

Today `answer.py` dumps **every** ruling a referenced `[card]` has into the prompt
(`_format_cards` joins the whole `rulings` list). Replace that with a **relevance
retrieval over each card's own rulings** — a per-card mini-RAG that pulls the
**specific** rulings relevant to the question and injects only those.

## The key reasoning: grounding rules out confidence-gating

I originally floated a "withhold rulings until the model says it can't answer"
gate (confidence-gated two-pass). **Jon's grounding priority kills that option.**
A confidence gate lets the model answer from its own training on every question
it *feels* sure about, and only reaches for grounded sources when it gives up —
which is exactly the training-data reliance Jon wants to eliminate, and exactly
where a confident-but-wrong answer hides. "Don't rely on training, stay grounded"
is a direct argument *against* letting the model's self-assessed confidence decide
whether grounding gets pulled in.

So the need-signal must come from the **corpus, not the model's gut**: run the
mini-RAG for every referenced card, and include any ruling that clears a
**relevance bar**. This reconciles both of Jon's steers without contradiction:

- **"Don't dump / withhold by default"** — we never inject all rulings. A ruling
  enters only if it's *relevant* to the question. On a card whose rulings are all
  off-topic, none enter (withheld). The target of this steer was the
  indiscriminate dump, not grounding.
- **"Stay grounded, don't rely on training"** — whenever a relevant grounded
  ruling exists, it's surfaced and the answer anchors to it instead of the
  model's memory. Relevance is measured against the ruling text — a grounded
  signal — not the model's confidence.

"Unless we need them" is operationalized as **"unless a ruling is relevant."**
That is the particular answer Jon's grounding question points to.

## What this is NOT (two problems kept separate)

This does **not** make the rules-RAG less redundant on questions the model
*already knows cold* (c001 counterspell, c002 trample/deathtouch, c005 APNAP). On
those, the rules stay redundant regardless of how we handle rulings. Making the
rules-RAG earn its keep is the **separate** task #2 — steering the card eval
toward **c004-shaped** questions whose answer isn't in the card data. This plan
only changes **which** rulings enter the prompt and makes that selection a
measured retrieval step.

## The mechanism (single pass, relevance-driven)

For each referenced card, a genuine per-card mini-RAG:

1. **Corpus:** the card's `rulings` list (already fetched + cached by `get_card`).
   Each ruling comment is one retrievable unit.
2. **Embed** each ruling with the same Voyage model as the rules index
   (`voyage-4-large`, `input_type=document`), cache the vectors keyed by
   `oracle_id + ruling text` (stable across reprints, survives TTL refresh),
   frozen under the same `no_refresh` reproducibility mode as the card cache.
3. **Query:** open sub-decision — the **stripped original question**, the
   **rewrite**, or both. Rulings are plainer English than CR rules, so the
   CR-vocabulary rewrite may be a *worse* query for them than the raw question.
   Lean: retrieve on the stripped original; measure the rewrite as an arm.
4. **Select** the rulings that clear a **relevance bar** — a cosine threshold
   (include everything above it) rather than a fixed top-N, so a card with three
   equally-relevant rulings keeps all three and a card with none keeps zero. A
   top-N cap can backstop pathological cards with many near-duplicate rulings.
   The threshold is calibrated on the card eval, not guessed (see Spike + Metric).
5. **Inject** only the selected rulings, in the same prompt slot as today (after
   rules, before the question).

Single pass, no extra generation call. Brute-force cosine over a
handful-to-dozens of rulings is sub-millisecond — the same "no vector DB"
argument as the main corpus, at even smaller scale.

## Grounding reinforcement (prompt + citations)

To push the "don't lean on training" goal all the way through:

- **Cite the ruling you rely on.** Extend the citation requirement (already
  applied to rules and card names) so that if a provided ruling is load-bearing,
  it must appear in `citations`. This makes ruling use *verifiable* — and it's
  what the rulings-recall metric reads.
- Needs a stable **ruling id** to cite (proposal: `oracle_id#<index>` or a short
  hash of the ruling text). Small addition to the `Card` shape / prompt
  formatting; spec it in the build step.

## Spike (running now — calibrates, doesn't decide direction)

Generating each of the 5 card questions two ways with the same rule pool:
**(A) rules + oracle only** vs **(B) rules + oracle + all rulings**. What it tells
us:
- Which questions the model answers, declines, or gets **confidently wrong**
  without rulings — the grounding gap, made concrete.
- **c003** is the watch case: its prowess ruling states the timing directly. If
  (A) gets c003's timing wrong or vague and (B) nails it, that's the clean
  demonstration that a *relevant ruling* is doing grounded work the training data
  and CR rules don't.
- A baseline (rules+oracle-only) to compare the new relevance-retrieval build
  against, and a first read on where a sensible relevance threshold sits.

Note the grounding lens on the spike: even a *correct* (A) answer is a grounding
gap if a relevant ruling existed and went unused — so "A got it right" is not a
reason to skip rulings; it's evidence the model was leaning on training.

## Measuring it (rulings-recall — a second measured RAG)

The eval-story payoff, distinct from rules recall@k:
- For a question with a load-bearing ruling (**c003**), gold = that ruling id;
  measure whether the retrieval selected it (and the answer cited it).
- For questions where no ruling is needed (**c001/c002/c005**), correct behavior
  is the mini-RAG selecting **nothing** — a clean negative test that "withheld by
  default" actually holds.
- Reuses the frozen Scryfall cache for reproducibility; ruling embeddings cached
  + frozen the same way.

## Reproducibility (don't repeat the rewrite-noise mistake)

- Ruling embeddings cached + frozen (`no_refresh`), like query embeddings and the
  card cache.
- Generation still has no temperature pin (the #3a lesson): any answer-quality
  number over the card set is a **k-draw mean**, never a single draw. The
  retrieval *selection* (which rulings clear the bar) is deterministic given
  frozen embeddings; the answer *text* varies.
- **Cache-race rule stands:** never run two generation/eval processes at once —
  the ruling-embedding cache is one more load-whole-dict/dump-whole-dict store
  with the same clobber risk.

## Cost

Small. Ruling embeddings: a few cents once, then cached/frozen. No extra
generation call (single pass). The 5-question card set is minutes and cents;
scales linearly.

## Long-term (Jon's call, revised)

The **per-card mini-RAG is the enduring strategy**, not just a stopgap. Jon
prefers it over the global **entity-anchored** design (index every ruling, hard-
filter by card name / `oracle_id` — "metadata-filtered retrieval"). The global
corpus is de-emphasized: if we ever want cross-card ruling retrieval (find the
relevant ruling when the user *didn't* name the card), that's a later, separate
build. I'll update `docs/scryfall-notes.md` to record that the mini-RAG is the
chosen long-term path and the global entity-anchored corpus is parked/downgraded.

## Decisions (made 2026-07-21 — Jon: "you should be able to run all of this")

1. **Relevance bar = cosine threshold WITH a top-N cap (N=3).** Include every
   ruling whose cosine to the query clears a floor, capped at 3 so a
   many-near-duplicate card (a Room's ~25 boilerplate rulings) can't flood the
   prompt. The floor is CALIBRATED during the build against the card eval's
   actual ruling-vs-question cosines (voyage-4-large): pick the value that admits
   the load-bearing ruling on questions that need one (c003 prowess, c006
   Fork-buyback, …) while admitting nothing on the no-ruling questions
   (c001/c002/c004/c005). Read off the data, not guessed.
2. **Ruling-retrieval query = the stripped original question.** Rulings are
   plainer English than CR rules, so the CR-vocabulary rewrite is likely a worse
   query for them. The rewrite stays a measurable arm, not shipped first.
3. **Cite the load-bearing ruling = yes.** Extend the citation requirement so a
   ruling the answer relies on must appear in `citations`. Stable ruling id =
   `oracle_id#<index>` (index into the card's `rulings` list). The rulings-recall
   GOLD (which ruling is load-bearing) is already Jon-authored in each
   cards.jsonl `note`, so the metric's ground truth stays his.
4. **Oracle text stays in by default; only rulings are relevance-gated.**
5. **Long-term = the per-card mini-RAG** (global entity-anchored corpus parked);
   record that in `scryfall-notes.md` during the build.

Implementation: embed each referenced card's rulings with voyage-4-large
(input_type=document), cache the vectors keyed by `oracle_id#<index>`, frozen
under the same `no_refresh` mode as the card cache. Single pass, no extra
generation call; the selected rulings replace the wholesale dump in the same
prompt slot.

## Scope / limits (stated honestly)

- **Per-card only.** Ruling retrieval is scoped to cards the question references
  via `[brackets]`. Cross-card / global ruling retrieval is the deferred, now-
  downgraded corpus.
- **Depends on the enrichment path.** A question with no `[card]` token fetches no
  card and no rulings — unchanged, a no-op.
- The mini-RAG selects among a referenced card's **own** rulings. A ruling on a
  *different*, unreferenced card can't be reached here.
