# Spec — semantic search over card oracle text ("find me something like this, but...")

**Status: DESIGN ONLY, decisions RULED, and now split into a $0 phase 0 that gates
the embedding build. Rule 0 — nothing gets built until Jon approves this document
as a whole.** Written 2026-07-26 after
`docs/results-channel-ablation.md` established that card oracle text is the
load-bearing channel and CR-rule retrieval is ~inert. Revised the same day with
Jon's five rulings and with every corpus claim re-measured against
`data/scryfall.db` rather than assumed.

## Why this, and why now

The ablation killed the premise of the existing RAG. Replacing the retrieved CR
rules with rules retrieved for a *different question* cost **3.3 points**
(p=0.50). The model already knows the Comprehensive Rules; handing them to it is
mostly ceremony.

**This proposal is a retrieval problem where retrieval is genuinely necessary.**
No model has memorised which of 33,458 cards has an effect similar to yours at
two mana less. That is not reasoning, it is lookup over a corpus that is large,
arbitrary, and constantly growing. Semantic search is the correct tool, and its
value can be demonstrated rather than assumed.

Jon's framing: *"same or similar effect but [less mana, less money, different
colors, strictly better]"*, extended to *"better effect for the same mana"*,
*"better effect for less mana"*, and *"same or less mana, same effect, plus
other beneficial effects."*

## What this is actually for, in priority order

Jon, on the framing: *"'strictly better' is a super hard topic in magic, and
isn't always agreed on... even 'functional comps' are good to be able to
suggest, either for redundancy or for other things."*

That ordering is the design. In descending order of both value and defensibility:

1. **Functional comps — the headline.** "Give me four more cards that do this."
   Redundancy is a real deckbuilding need, it needs nobody to agree on which card
   is better, and it is the largest computable gold set we have (**3,440 pairs**).
2. **Similar-effect search with structured constraints.** "Extra turn effects in
   golgari." "Counterspells for one mana." Semantic match plus metadata filters.
3. **Dominance, as a label.** "This one is derivably better" attached to results,
   and available as a filter mode. Smaller, sharper, and inherently arguable.

**Dominance is a derivation, not a verdict.** It is computed exactly from
Scryfall fields; it can still disagree with what players think, because format
context, colour pip intensity and deck synergy are outside the data. The system
reports a derivable relation and says which rule produced it. It does not claim
to settle whether one card is better.

## The reason this is a better engineering target than the rules RAG

**The gold standard is computable.** This is the decisive difference, and it goes
directly to the root cause of every defect in `docs/results-adversarial-review.md`:
gold rule sets were asserted by a miner and never validated, so four separate
defects hid behind numbers that looked reasonable.

Here, ground truth is *derived* from local Scryfall data with no human labelling
and no LLM judge. Every count below was measured on 2026-07-26 against
`data/scryfall.db`, excluding non-card layouts and degenerate keys:

| relation | pairs | basis |
|---|---:|---|
| functional comps (identical normalised text) | **3,440** | set equality |
| identical text, cheaper or bigger | **427** | + mana value / power / toughness |
| ability superset (same or less mana) | **2,692** | line-set superset |
| numeric dominance (same template, bigger numbers) | **253** | digit comparison |
| colour-shifted variants | **1,492** | identical text, different colour identity |

Recall@k against a gold set nobody had to hand-write — the exact property the
rules corpus never had.

## Data — measured, not assumed

`data/scryfall.db`, table `cards` (cols: `oracle_id`, `name`, `name_norm`,
`layout`, `card_json`). Corrections to the previous draft, all verified:

- **38,336 rows, but 4,056 (10.6%) are not real cards** — `art_series`, `token`,
  `double_faced_token`, `emblem`, `vanguard`, `scheme`, `planar`, `augment`,
  `host`. **Excluded from the index.** "Find me a card like this" must not return
  an art-series print. 34,280 playable cards remain; 33,458 have usable text.
- **The multi-face key is `faces`, not `card_faces`.** Card JSON has exactly ten
  keys: `name`, `oracle_text`, `type_line`, `mana_cost`, `mana_value`, `colors`,
  `color_identity`, `oracle_id`, `layout`, `faces`.
- **Power and toughness exist only at face level** (`faces[i].power`,
  `faces[i].toughness`) — there is no card-level `power`. Any dominance
  computation must reach into `faces[0]`. This is precisely the shape assumption
  that broke two parsers last session.
- **877 multi-face cards, 2.6% of playable** — not the 5-8% previously guessed.
  Layouts: transform 401, adventure 158, split 137, modal_dfc 100, prepare 55,
  flip 26.
- Top-level `oracle_text` on a multi-face card already joins faces with `\n//\n`.
- `rulings`: 77,999 rows. Out of scope for v1.

Embeddings via `voyage-4-large`, the model already used for the rules index
(`rulesagent/index/embed.py:38` `embed_documents`, `:48` `embed_query`), so the
pipeline is reused rather than reinvented.

## RULED DECISIONS

**1. Reminder text: STRIP, with a guard.** Embed stripped oracle text plus type
line and mana cost.

Measured on playable cards (`evals/cards_corpus_probe.py`): 32.0% carry a
parenthetical; mean oracle text falls 167.5 → 135.5 characters when stripped;
stripping **loses zero** functional-twin pairs, gains 644, and takes twin groups
from 922 to 976. `Storm Crow` goes from "Flying (This creature can't be blocked
except by creatures with flying or reach.)" to "Flying".

**Two guards, for two different reasons:**

- **35 cards strip to an empty string**, so the embedded string is
  `type_line | mana_cost | stripped_oracle_text` — a card that strips to nothing
  still has something to embed.
- **Degenerate keys are excluded from computed gold** (normalised key under 20
  characters): **87 groups, 370 cards** — 23 keyed `deathtouch`, 19 `first strike`,
  19 `flying, vigilance`, 17 `forestwalk`, 14 `{t}: add {g}.`. Vanilla creatures
  are trivially functional twins, and leaving them in inflates recall@k with the
  corpus's easiest cases.

**Two measurement traps this section already fell into, recorded so they are not
repeated:** the first pass ran over all 38,336 rows rather than the 34,280
playable ones, which put tokens and art-series prints into the counts and
reported 313 empty-strip cards instead of 35. The second pass judged degeneracy on
the *grouping* key, so reminder text padded vanilla cards past the 20-character
threshold and the comparison reported 1,709 "pairs lost by stripping" — it was
measuring the guard, not the stripping. Degeneracy is now always judged on the
stripped key.

**2. Multi-face: ONE VECTOR PER FACE**, deduped up to the card for display. Costs
877 extra vectors (+2.6%). `Heaven // Earth` is the case that decides it: the two
halves do unrelated things, so a concatenated vector represents neither. The card
stays the unit of the result; the matched face is reported alongside it.

**3. Dominance: ALL FOUR SHAPES, TIERED AND LABELLED.** Every pair carries the
shape that produced it and a confidence tier. **Results are reported per shape and
never pooled into a single number**, so a weak shape can be measured and dropped
without contaminating a strong one.

**4. Query-time exposure: FILTER MODE, PLUS A LABEL ON ALL RESULTS.** `--upgrades`
returns only dominating cards; ordinary similarity results still get tagged when
they dominate the anchor. Measurable against computed gold today, and promoting
the label to a ranking input later is a scoring change, not a redesign.

**5. Integration: STANDALONE v1.** The answer path is untouched. Integration
becomes its own slice, shipped only if an ablation shows it earns its cost.
The precedent is `resolve_layers`: built on reasoning that sounded just as good,
measured at exactly zero, and cost 8.6% per query plus 41% of round trips.

## The dominance relation

A dominates B when A's effect is at least as good, A's cost is no higher, A's body
is no smaller, and at least one of those is strictly better. Colour identity must
match, except in the explicitly colour-shifted relation.

**Shape 1 — identical text (certain).** Normalised oracle text equal, mana value
lower or power/toughness higher. 427 pairs. `Waterknot` (MV 3) over
`Sleep Paralysis` (MV 4).

**Shape 2 — ability superset (text-only).** A's ability-line set is a strict
superset of B's, cost no higher, body no smaller. 2,692 pairs.
`Goblin Chainwhirler` over `Halberdier`. **Named honestly: a superset detects
extra text, not extra benefit.** An added line can be a drawback ("When this
creature dies, you lose 2 life"), so this tier is labelled `text-only` and its
recall is reported separately.

**Shape 3 — numeric dominance (needs the cost rule).** Texts identical once digits
are blanked, and A's numbers dominate B's. 253 pairs.

**The direction rule is mandatory, and its absence produced a real false
positive.** A first pass ranked `Bold Impaler` [2,2,0] above `Bellows Lizard`
[1,1,0] on the template `{#}{R}: this creature gets +#/+# until end of turn` —
but that leading number is the *activation cost*, where bigger is worse. Rule:
**digits inside `{}` are costs and invert direction.** Done right, this shape
gives `Flametongue Kavu` (4 damage) over `Corrupt Eunuchs` (2 damage) at equal
mana value.

**Shape 4 — mana production (partial order).** Population: 1,756 cards carry a
`{T}: Add ...` clause; 148 are 2-mana creatures. Compare produced mana under a
written-down partial order:

- **Quantity:** `{C}{C}` > `{C}`.
- **Flexibility:** "any color" > "one mana of any color" > "`{G}` or `{U}`" > "`{G}`".
- **INCOMPARABLE** (the rule must be allowed to answer "neither"): different fixed
  colours such as `{C}` vs `{G}`, and any clause carrying a "spend this mana only
  on..." restriction. Corpus shape counts: 920 produce one fixed symbol, 415 two,
  238 say "any color", 44 say "one color".

**Known limits, stated rather than hidden:**

- **Mana value flattens colour intensity.** `{R}{R}{R}` and `{3}` are both mana
  value 3, but triple-red is much harder to cast. Every "cheaper" claim inherits
  this.
- **Mechanical dominance is not community consensus.** Price and play rate encode
  real judgment and are the obvious later cross-check, but they drift daily and
  are not in the local snapshot, so they can sanity-check the computed relation
  and must never be its ground truth. Using them as gold would make the eval
  non-reproducible.

## Scryfall oracle tags — and why they force a phase 0

Jon flagged that Scryfall added tag data. Verified against the live API rather
than from memory: `oracle_tags` (17.4 MB) and `art_tags` (38.9 MB) are their own
bulk-data types, refreshed daily. **Tags are NOT fields on the card object** and
are absent from `oracle_cards` / `default_cards` / `all_cards`; oracle tags join
to cards on `oracle_id`, art tags on `illustration_id`. Search syntax exposes them
as `otag:` / `oracletag:` / `function:`. Slugs and labels are explicitly not
stable — track the tag `id` UUID.

Measured against our indexable corpus:

- **4,499 oracle tags**, of which 3,578 have a parent — a hierarchy, not a flat
  keyword list.
- **99.4% coverage** (34,073 of 34,280 indexable cards), median 6 tags per card,
  mean 6.6, max 46.
- **The `weight` field is unusable:** 229,303 taggings are `median`, 600
  `very_strong`, 1 `strong`. Do not design around it.
- Largest tags are functional: `activated ability` 9,041, `triggered ability`
  7,906, `spot removal` 4,991, `evasion` 4,577, `removal-destroy` 1,712.

**This is human-curated ground truth, which makes it both valuable and an
experiment subject.** Scryfall moderates Tagger data but states plainly it cannot
guarantee freedom from error or abuse, and recommends downstream apps be able to
disable individual tags. So tags may be used as a gold *source* and as a baseline,
but any number derived from them needs the same validation pass we would give any
other instrument — the standing lesson applies.

**The finding that changes the build order.** The `extra turn` tag contains exactly
**64 cards** — the same 64 a plain regex scan finds, with the same 2 golgari.
Which means test case 3 is answered *exactly* by a tag filter plus a colour
filter, with no embeddings involved. Generalising:

| capability | cheapest mechanism that actually works |
|---|---|
| functional comps | text equality — no embeddings |
| "all extra turn effects in golgari" | tag filter + colour filter — no embeddings |
| dominance / upgrade finding | metadata relation — no embeddings |
| "cards that do `<arbitrary description>`" | **embeddings** |

**PHASE 0, therefore, and it is mandatory: build the cheap baselines first and make
the embedding index earn its place.** Tag filtering, text equality and BM25 are all
local and cost nothing, so this is measurable before any indexing spend. If
embeddings only beat the baselines on free-text description search, that is still a
real reason to build them — but it is a far smaller claim than "we need a vector
index," and finding it out first is exactly what the channel ablation would have
saved months by doing.

Phase 0 deliverable: recall@k for tag-filter, text-equality and BM25 retrieval
against the same computed gold, on the same stratification. Phase 1 (the embedding
index) is justified by that table or it is not built.

## Retrieval modes — two, not one

**Mode A: top-k similarity.** "Cards like `<card>`" or "cards that
`<effect description>`." Ranked list, k configurable.

**Mode B: exhaustive filter-then-rank.** "**All** the extra turn effects in
golgari." Filter to the legal candidate set, rank everything in it, return
everything above a similarity threshold. No fixed k.

**Filters are applied BEFORE ranking, never after, and this is not an
optimisation — it is correctness.** Measured: 64 cards mention "extra turn", and
exactly **2** are golgari colour identity (`Temporal Extortion`, `Seedtime`) —
3.1%. A top-20 semantic search followed by a colour filter returns an empty list
while both cards sit in the corpus.

Filters, all structural rather than semantic: mana value (`<`, `<=`, `=`), colours
and colour identity (subset / exact / excludes), type line contains, and the
dominance relation as a computed filter.

**Out of scope for v1:** price ("less money") — it needs a live feed, changes
daily, is absent from the local snapshot, and would make the eval
non-reproducible. Worth doing later; wrong thing to build first.

## Normalisation — where the accuracy actually lives

The ablation's operational lesson was that **mis-resolution is far more expensive
than non-resolution** (wrong cards cost 31 points, missing rules cost 3). The same
asymmetry governs here, so normalisation is the load-bearing code:

- **Self-reference:** replace the card's own name in its oracle text with a
  placeholder, including the short form before a comma (`Urza, Lord High Artificer`
  → also match `Urza`), or functional reprints never match.
- **Reminder text:** stripped, per decision 1, with the guard.
- **Multi-face:** per face, per decision 2, reading `faces` and not `card_faces`.
- **Apostrophes and unicode:** `normalize_source_id`
  (`rulesagent/contracts.py:361`) already handles the curly vs ASCII apostrophe
  trap. Reuse it; do not re-solve it.

## Evaluation — with the controls this project learned the hard way

1. **Recall@k against computed gold**, reported at k=1, 5, 10, 20, **per relation
   shape, never pooled.**
2. **A PLACEBO CONTROL, mandatory.** Re-run retrieval against a deranged index —
   each card's vector swapped for another's. Recall must collapse to chance. If it
   does not, the metric is measuring something other than semantic similarity, and
   day one is when we want to find that out. It costs nothing: retrieval is local.
3. **Three baselines, not one** — all local, all free, all run in phase 0 before
   any embedding exists: **BM25** over oracle text (`BM25Index`,
   `rulesagent/index/bm25.py:22`, already built), **text equality** on the
   normalised key, and **tag filtering** on the 4,499-tag oracle taxonomy. If any
   of them matches the embeddings on a capability, the embeddings are not earning
   their cost for that capability, and the spec says so in the writeup rather than
   reporting the embedding number alone.
4. **Noise floor is zero.** Embedding search is deterministic, so unlike every
   arm measured during the ablation, small differences here are real. State it
   explicitly.
5. **Stratify** by oracle-text length and by multi-face status (877 cards, 2.6%),
   so the known-hard cases cannot be averaged away.
6. **Degenerate exclusions are part of the eval contract**, not a preprocessing
   detail — recall computed over vanilla twins is a number about nothing.

## Acceptance test cases

Concrete, checkable, and drawn from real corpus rows:

1. **Functional comp:** `Sleep Paralysis` returns `Castaway's Despair` and the
   rest of its twin group.
2. **Dominance, shape 1:** `Waterknot` is labelled strictly better than
   `Sleep Paralysis` (MV 3 vs 4, identical text, same colours).
3. **Exhaustive filtered search:** "all extra turn effects in golgari" returns
   `Temporal Extortion` and `Seedtime` — both of them, not a top-k slice that
   happens to miss them.
4. **Dominance, shape 4:** a 2-mana 1/1 producing `{C}{C}` is labelled better than
   a 2-mana 1/1 producing `{C}` (`Soldevi Machinist` / `H.E.R.B.I.E., Lovable
   Robot` shape), and `{C}` vs `{G}` at equal stats returns **incomparable**.
5. **Placebo:** every one of the above collapses to chance on the deranged index.

## What this enables, and how it makes the system better

**Standalone (v1, shipping):**

- **Redundancy search.** "Four more cards that do this" — the deckbuilding
  question functional comps answer directly.
- **Budget and colour substitution.** "Like this, but cheaper" / "but in these
  colours" — the 1,492 colour-shifted pairs are exactly this relation.
- **Upgrade finding.** "What strictly beats this" as a filter, with the derivation
  shown so the user can disagree with it.
- **Exhaustive effect search.** "All the X effects in colours Y" — a question that
  is tedious by hand and that no model can answer reliably from memory.

**How it could improve the answer path (LATER, and gated on measurement):**

- **Resolution failure is NOT a live problem on the eval corpus, and this was
  measured after the rest of this section was drafted.** Across
  `evals/rulesguru_full_v2.jsonl`: 1,399 of 1,409 rows carry a bracket ref,
  **3,597 refs total, zero unresolved** — 95.83% on exact name, 4.17% on face name,
  and the rapidfuzz tier never fires. So "a card index would rescue unresolved
  refs" is worth approximately nothing here, and the earlier draft of this bullet
  claiming otherwise was wrong.
  **What that does and does not mean.** The corpus is RulesGuru-derived, so its
  questions name cards exactly, in brackets, by construction. It cannot measure
  what a real user typing a misspelled or described card does. The honest position
  is that there is *no evidence* resolution failure is a live defect, not that it
  cannot happen in production. It also reframes the 31-point card channel: that
  number measures how much the answer *depends* on correct card data, not a defect
  that is currently firing.
  Two consequences worth carrying: the 150 face-name resolutions (4.17%) mean the
  DFC/split path is genuinely exercised and earns its keep, and roadmap item 3b
  ("harden card resolution") is insurance against a production failure mode that
  the current instruments cannot see — still defensible, but its value is
  unmeasured rather than demonstrated.
- **"Is there a cheaper version of this card"** becomes answerable at all. Today
  the bot cannot answer it, because card data is pre-assembled from the refs in
  the question (`answer.py:1501`) and there is no mechanism to look sideways.
- **The integration must be ablated before it ships.** Two arms, identical but for
  card-similarity availability, ship only if the arm with it wins. `resolve_layers`
  is why: it was reasoned into existence just as plausibly and measured zero.
- **If it ships, it fits the tool pattern**, not prompt pre-assembly. Card data is
  pre-assembled today because the refs are known up front; a similarity query is
  conditional on what the model decides it needs, which is the `_TOOL_DISPATCH`
  pattern (`answer.py:1415`) that `calculate_cost` and `resolve_layers` already
  use.

## Synergy and combos — a different mechanism, deliberately v2

Jon: *"could we use it to find combos/synergy too? if we wanted a business use
case, being able to find cards that combo with a card that's coming out can be a
big money-maker."*

**Straight similarity search will not find combos, and it is important to say why
rather than discover it after building.** Similarity retrieves cards that do the
*same* thing. Combo pieces do *complementary* things. "Untap target creature" and
"{T}: Draw a card" are a combo and are semantically far apart — searching for one
surfaces other untap effects, not the payoff that makes it worth doing. Every
functional-comp result in v1 is, by construction, a card you would play *instead
of* the anchor, not *alongside* it.

**What does work is the same index with a synthesised complement query.** Two
steps: work out what the anchor card *needs* ("a creature with a tap ability that
does something worth repeating"), then semantic-search for text describing that.
The index is the substrate; the intelligence sits in generating the complement
query. That is a legitimate and cheap division of labour — one model call to write
a query, then local retrieval.

**Tags do not solve this either, and it is worth knowing before anyone assumes
otherwise.** There are 272 `synergy-*` oracle tags, but they are thematic
categories rather than two-card interactions: `synergy-flying` (116 cards),
`synergy-token-creature` (111), `synergy-mountain` (90). **Zero tags contain
"combo".** So tags substantially improve *thematic* synergy search — "cards that
make flying better" becomes a lookup — and leave two-card combo discovery exactly
where it was.

**Part of it is mechanically derivable.** Many combos are produce/consume pairs
over predicates already present in the text:

- untap effects ↔ cards with `{T}:` abilities
- "whenever you gain life" ↔ "you gain life"
- "sacrifice a creature" ↔ "when this creature dies"
- mana production ↔ activation costs cheaper than what is produced

Extracting produce/consume predicates across 33,458 cards yields a *candidate*
synergy graph without any LLM in the loop. Candidates, not combos — whether a pair
actually wins the game is a judgement the data does not contain.

**The honest problem is evaluation, and it is the reason this is not in v1.**
There is no computable gold for synergy. Human-curated combo databases exist
(Commander Spellbook and similar) and are far better ground truth than an LLM
judge, but importing one means the eval depends on an external instrument — and the
standing lesson of this project is that **anything used as ground truth is an
experiment subject.** It would need its own validation pass before any number
derived from it is quotable. v1's whole selling point is that it can be measured
for free and iterated for free; putting an unmeasurable feature inside it would
spend that property on the first slice.

**The business case has a real and defensible edge, though, and it is worth
recording now.** A card announced today has oracle text today, and no model's
weights know it. Indexing that text makes "what already-printed cards combo with
this new card" answerable immediately, on a corpus that postdates the model's
training. That is a genuine timeliness advantage rather than a marketing claim,
and it applies to the v1 similarity search too — "what does this new card
functionally replace" is answerable the day the card is revealed.

**Sequencing:** v1 ships similarity, filters and dominance on computable gold.
Synergy becomes its own spec with its own Rule 0 ruling, naming the complement-
query mechanism, the produce/consume predicate set, and an evaluation source that
has been validated before it is trusted.

## Cost

- **Indexing: ~1.36M tokens.** Measured: 33,458 cards + 882 extra faces = 34,340
  embeddable units, 5,435,287 characters (`evals/cards_corpus_probe.py`).
- **`voyage-4-large` is $0.12 per 1M tokens, and the first 200M tokens are free
  per account** (verified against docs.voyageai.com/docs/pricing on 2026-07-26,
  32,000-token context limit). So indexing is **$0** against the free allowance,
  or **~$0.16** if that allowance is already spent.
- **Voyage is a different vendor from Anthropic.** This does not touch the ~$38
  Anthropic API balance. It still gets an explicit go-ahead before any call.
- **`rulesagent.pricing` has no voyage entry** (CHECKED_ON 2026-07-26). Adding one
  is a prerequisite slice, so the number lives in the cache rather than in this
  document.
- **Query time: $0 in Anthropic credits.** A local matmul plus one query
  embedding. No generation call in the core feature.
- **Evaluation: $0.** Computed gold, local retrieval, no judge. Unlike every
  experiment run during the ablation, **this one can be iterated on for free.**

## Scope

**Phase 0 (first, $0, gates phase 1):** oracle-tag ingest (daily bulk file, joined
on `oracle_id`), the computed-gold sets for all four dominance shapes, and
recall@k for the three cheap baselines — text equality, tag filter, BM25 — on the
agreed stratification.

**Phase 1 / v1 (only if phase 0 justifies it):** embedding index build and refresh
(per face, stripped text, non-cards excluded), card-anchored and text-anchored
search, both retrieval modes with pre-filtering, structured filters, all four
dominance shapes with tiers and an incomparable verdict, the placebo control, and a
CLI.

**Out (v1):** price filters, a UI, any change to the answer path, ruling-text
search, deck-building or format-legality logic, dominance as a ranking signal.

## Risks

- **"Similar" is underdefined.** Functionally identical cards are objectively
  similar; "similar in spirit" is a judgement call. v1 measures the objective part
  and must not claim more.
- **Computed gold measures the easy case.** Functional reprints are where any
  method works. Good recall there is necessary, not sufficient, and the writeup
  must say so rather than present it as proof the system is good.
- **Multi-face cards are where mistakes cluster** (877 cards, 2.6%). Stratify so
  they cannot hide inside an average.
- **Shape 2 over-claims by construction.** Extra text is not extra benefit. Its
  tier label carries that, and its recall is never pooled with shape 1's.
- **Reindex drift.** A Scryfall refresh changes the corpus. Stamp the index with
  the snapshot date and refuse to serve a query against a stale index silently.

## Why it is worth building

A retrieval system whose value can be *proven* rather than assumed, on a corpus no
model can memorise, with a ground truth that needs no human labelling and no LLM
judge, evaluable at zero marginal cost, on infrastructure this repo already has.

It is also the honest answer to "the RAG didn't matter": build the one where it
does, and measure it the way the ablation taught us to.
