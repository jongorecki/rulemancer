# Spec — semantic search over card oracle text ("find me something like this, but...")

**Status: DESIGN ONLY. Rule 0 — nothing gets built until Jon rules on it.**
Written 2026-07-26, after `docs/results-channel-ablation.md` established that the
card oracle text is the load-bearing channel and CR-rule retrieval is ~inert.

## Why this, and why now

Tonight's ablation killed the premise of the existing RAG. Replacing the retrieved
CR rules with rules retrieved for a *different question* cost **3.3 points**
(p=0.50). The model already knows the Comprehensive Rules; handing them to it is
mostly ceremony.

**This proposal is a retrieval problem where retrieval is genuinely necessary.**
No model has memorised which of 38,336 cards has an effect similar to yours at two
mana less. That is not reasoning, it is lookup over a corpus that is large,
arbitrary, and constantly growing. Semantic search is the correct tool, and its
value can be demonstrated rather than assumed.

Jon's framing: *"same or similar effect but [less mana, less money, different
colors, strictly better]."*

## The reason this is a better engineering target than the rules RAG

**The gold standard is computable.** This is the decisive difference, and it goes
directly to the root cause of every defect in `docs/results-adversarial-review.md`:
gold rule sets were asserted by a miner and never validated, so four separate
defects hid behind numbers that looked reasonable.

Here, ground truth can be *derived* from Scryfall data with no human labelling and
no LLM judgement:

1. **Functional reprints** — cards whose oracle text is identical after
   normalising self-references (Scryfall writes the card's own name in its text;
   substitute a placeholder). `Lightning Bolt` / `Chain Lightning` differ in type
   line but a great many pairs are exact. **These MUST retrieve each other.**
   Automatic, verifiable recall gold.
2. **Strictly-better pairs** — identical normalised oracle text, with mana value
   lower or power/toughness higher. Mechanically computable.
3. **Colour-shifted variants** — identical normalised text, different colour
   identity. Mechanically computable.

That gives recall@k against a gold set nobody had to hand-write, which is the
exact property the rules corpus never had.

## Data (all local, already on disk)

- `data/scryfall.db`, table `cards`: **38,336** oracle-level cards, each with
  `card_json` carrying `name`, `oracle_text`, `type_line`, `mana_cost`,
  `mana_value`, `colors`, `color_identity`, `faces`, `layout`, `oracle_id`.
- `rulings` table: 77,999 rows, available as a secondary signal (out of scope for
  v1).
- Embeddings via `voyage-4-large`, the model already used for the rules index
  (`rulesagent.index.embed`), so the pipeline is reused rather than reinvented.

## Query modes (v1)

**Card-anchored:** "cards like `<card>`, but `<constraint>`." Anchor is an
embedding of the anchor card's normalised oracle text; constraints are structured
filters applied over metadata, not expressed in the embedding.

**Text-anchored:** "cards that `<effect description>`." Straight semantic search.

Constraints are **metadata filters, deliberately not semantic**: mana value
(`<`, `<=`, `=`), colours / colour identity (subset, exact, excludes), type line
contains, and "strictly better" as a computed relation. Filtering structurally
rather than hoping the embedding respects "cheaper" is the difference between a
demo and a tool.

**Explicitly out of scope for v1:** price ("less money") — it needs a live pricing
feed, it changes daily, it is not in the local snapshot, and it would make the
eval non-reproducible. Worth doing later; wrong thing to build first.

## Normalisation — where the accuracy actually lives

The ablation's operational lesson was that **mis-resolution is far more expensive
than non-resolution** (wrong card data cost 31 points; missing rules cost 3). The
same asymmetry applies here, so normalisation is the load-bearing code:

- **Self-reference:** replace the card's own name in its oracle text with a
  placeholder, or functional reprints will never match.
- **Multi-face cards:** split (`//`), transform, modal DFCs, adventures. The
  `faces` field exists; a face-aware policy must be chosen and stated, not left
  implicit. **These broke two separate parsers during tonight's analysis alone.**
- **Reminder text** in parentheses: strip or keep? It is rules-redundant but
  semantically informative. Decide explicitly and record the decision.
- **Apostrophes and unicode**: `normalize_source_id` already exists for the curly
  vs ASCII apostrophe trap. Reuse it; do not re-solve it.

## Evaluation — with the controls this project learned the hard way

1. **Recall@k against computed gold** (functional reprints, strictly-better,
   colour-shifted). Report k=1, 5, 10, 20.
2. **A PLACEBO CONTROL, mandatory.** Re-run retrieval with the embedding index
   deranged — each card's vector swapped for another card's. Recall must collapse
   to chance. **If it does not, the metric is measuring something other than
   semantic similarity, and we would rather find that out on day one than after
   building on it.** This is the single most valuable habit from tonight, and it
   costs nothing here because retrieval is local.
3. **Baseline comparison:** BM25 over oracle text. If lexical search matches the
   embeddings, embeddings are not earning their cost. The rules index already has
   BM25 (`rulesagent.index.bm25`) — reuse it.
4. **Noise floor:** embedding search is deterministic, so run-to-run noise is
   zero. State that explicitly, because it means small differences here ARE real,
   unlike everything measured tonight.
5. **Report the whole distribution, not just means.** Stratify by card complexity
   (oracle text length) and by whether the card is multi-face — the known-hard
   cases must not be averaged away.

## Cost

- **Indexing:** ~38,336 cards. Oracle text plus type line is roughly 100 tokens
  per card, so ~4M tokens, one time. **Voyage pricing is NOT in
  `rulesagent.pricing` and must be looked up and added before any spend** — do not
  estimate it from memory. Re-embedding is only needed when Scryfall refreshes.
- **Query time: $0 in Anthropic credits.** Search is a local matmul against a
  stored index plus one query embedding. No generation call is required for the
  core feature, which is the cheapest thing this project has proposed all day.
- **Evaluation: $0.** Gold is computed, retrieval is local, no judge needed.

That last point deserves emphasis: unlike every experiment run today, **this one
can be iterated on for free.**

## Scope

**In (v1):** index build + refresh, card-anchored and text-anchored search,
structured filters (mana value, colours, type), computed-gold eval harness with
the placebo control and BM25 baseline, a CLI.

**Out (v1):** price filters, a UI, integration into the answer path, ruling-text
search, deck-building or format-legality logic, "strictly better" as a *ranking*
signal rather than a filter.

## Risks

- **"Similar" is underdefined.** Functionally identical cards are objectively
  similar; "similar in spirit" is a judgement call. v1 measures only the
  objective part and must not claim more.
- **Computed gold measures the easy case.** Functional reprints are the cases
  where any method works. Good recall there is necessary, not sufficient — say so
  in the writeup rather than presenting it as proof the system is good.
- **Multi-face cards are ~5-8% of the corpus and are where mistakes cluster.**
  Stratify results so they cannot hide inside an average.
- **Reindex drift:** a Scryfall refresh changes the corpus. Stamp the index with
  the snapshot date and refuse to serve a query against a stale index silently.

## Open decisions for Jon

1. **Reminder text** — strip or keep in the embedded string?
2. **Multi-face policy** — one vector per face, or one per card with faces
   concatenated?
3. **Is "strictly better" a filter or a ranking signal?** Filter is simpler and
   verifiable; ranking is more useful and much harder to evaluate.
4. **Does this stay standalone, or eventually feed the answer path?** Standalone
   is a cleaner portfolio piece and a cleaner experiment. Integration is more
   product value and more risk.

## Why it is worth building

It is a retrieval system whose value can be *proven* rather than assumed, on a
corpus no model can memorise, with a ground truth that requires no human labelling
and no LLM judge, evaluable at zero marginal cost, using infrastructure this repo
already has.

It is also the honest answer to "the RAG didn't matter": build the one where it
does, and measure it the way tonight taught us to.
