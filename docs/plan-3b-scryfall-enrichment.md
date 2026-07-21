# Plan — #3b: Scryfall card enrichment (DRAFT v2, pending Jon's review)

Working Rule 0 artifact. No code until reviewed. Supersedes the "routing" draft
(v1) — Jon's reframe below turned this from a router into a context-enricher.

## The reframe (Jon, 2026-07-21): enrichment, not routing

v1 had an LLM router pick *card OR rules*. That's wrong. Jon's example —
"can I use @Dovin's Veto to counter a creature spell while @Dovescape is on the
battlefield without @Dovin's Veto getting countered?" — needs the oracle text of
*both* cards AND the rules on countering/timing, together. An either/or router
routes it one way and drops half the answer.

**The right shape: always retrieve the rules, and additionally pull card data
(oracle text + all rulings) for any card the user @-referenced, then hand the
generator everything.** A pure card question is the degenerate case where rules
retrieval just isn't relevant and the card data carries it; a pure rules
question @-references nothing, so nothing extra is fetched. The combined case —
the one that makes this useful — falls out naturally instead of being a mode.

This also **retires the routing/tool-use question entirely.** The `@` trigger
(below) makes card detection deterministic, so there's no classification step to
get wrong.

## Step 0 — reachability spike: DONE, PASSED (2026-07-21)

Ran before building, per the same discipline that saved a day on q016. Results
on Jon's actual example cards:
- `api.scryfall.com` reachable from the sandbox (200; no egress-proxy block).
- Fuzzy named lookup: "dovins veto" → "Dovin's Veto", oracle text intact.
- Rulings endpoint works: Dovin's Veto returns 1 ruling, directly relevant to
  the countering interaction (the CR can't supply this).
- Autocomplete works: `@dove` → ["Dovescape", "Knight of Doves", ...].
- Scryfall sends no rate-limit headers — it relies on client courtesy (~100ms
  spacing), which we honor.

Green light to build.

## `@` card references (Jon's call — deterministic, not LLM extraction)

Users mark specific cards with `@`. That single choice does three things:
1. **Deterministic detection** — parse `@`-tokens; no LLM guessing which words
   are card names, no "Fog the card vs in a fog" ambiguity.
2. **Autocomplete hook** — `@dove` completes to real card names (endpoint
   confirmed working), so users type exact names easily.
3. **Correct resolution** — the `@`-token is fuzzy-resolved against Scryfall, so
   minor typos still land ("@dovins veto" → "Dovin's Veto").

**Contract:** only `@`-referenced cards are looked up. "what does Llanowar Elves
do?" (no `@`) is treated as plain text; "what does @Llanowar Elves do?" triggers
the lookup. Explicit and predictable.

**Open detail — the delimiter for multi-word names.** Card names have spaces
("Dovin's Veto"), so bare `@Dovin's Veto to counter` is ambiguous about where the
name ends. Proposal: **`@[Card Name]` brackets** in questions (and what a live
autocomplete would insert on selection) — unambiguous to parse, and eval
questions Jon hand-writes stay clean. Alternative is greedy longest-match against
the card DB (no brackets, but genuinely ambiguous mid-sentence). Leaning
brackets; Jon's call.

## 1. The tool — `src/rulesagent/tools/scryfall.py`

`get_card(name) -> Card | None` and `get_rulings(card) -> list[str]`.

- **Lookup:** `GET /cards/named?fuzzy=<name>` → `Card` (new in contracts.py:
  `name`, `oracle_text`, `type_line`, `mana_cost`, `oracle_id`, `rulings_uri`).
  404 → None (unknown card), not an exception. Double-faced/split cards join
  `card_faces[]` text so no half-card is dropped.
- **Rulings:** fetch the card's `rulings_uri`; return **all** of them (Jon: "add
  all of them for now"). Each ruling is `{published_at, comment}`; we pass the
  comments as context.
- **Courtesy + attribution:** descriptive `User-Agent` + `Accept` headers,
  ~100ms min spacing between calls, "Card data from Scryfall" surfaced on answers
  that used it (Fan Content Policy — only matters if the friend's app goes
  commercial, per the master plan's "Still open").
- **Reproducibility:** disk-cache lookups + rulings to
  `data/parsed/scryfall_cache.json` (gitignored) keyed by resolved card name, so
  the card eval makes zero network calls on re-run — the same frozen-fixture
  property every other eval here has. Card oracle text/rulings for a printing are
  stable, so no invalidation needed (tracking new sets is the deferred bulk use).

## 2. The pipeline

Extending the agent (an `enrich`/`route` method above `RulesAgent`, name TBD):

1. **Parse** `@[...]` tokens from the question.
2. **Fetch** oracle text + all rulings for each (cached).
3. **Retrieve rules** via the existing #3a path — rewrite the question into rules
   vocabulary, then vector-retrieve top-15. (The rewriter can even use the card
   oracle text to write a sharper rules query — e.g. "@Dovin's Veto can't be
   countered" → a query about countering uncounterable spells. MVP: feed card
   text to the rewriter as context; measure if it helps.)
4. **Generate** with everything — retrieved rules + each card's oracle text +
   rulings — into the structured `Answer`. Citations cover both rule numbers and
   card names (same field; it's "what the answer relied on").

## 3. Eval — small first, Jon authors later

Per the per-corpus rule, card+rules questions get their own set with gold
spanning cards and rules. **Jon writes them, later, from watching the pipeline
run** (his call: "write the pipeline now so I can easily write questions later …
these can get super complex — Magic is Turing-complete — so I may crowdsource
some"). The first set stays small on purpose; the combination space explodes
fast, so we prove the pipeline on a handful (Dovin's Veto/Dovescape as the
template) before scaling.

Metrics when the set exists: card-resolution accuracy (did `@X` resolve to the
right card), and answer faithfulness against oracle text + rulings + rules
(Jon grades, same method as the rules answers).

## Decisions for Jon

1. **`@[Card Name]` bracket delimiter** for multi-word names in questions (and
   what autocomplete inserts) — yes, or prefer bare `@` with greedy matching?
2. Everything else is settled by your four answers (deterministic `@`, all
   rulings, pipeline-first, full enrichment). Nothing else blocks.

## Out of scope (DEFERRED — docs/scryfall-notes.md)

- **The autocomplete *dropdown* UX** — the endpoint works and the pipeline parses
  `@`-tokens now, but a live as-you-type dropdown needs a frontend we don't have
  yet (or the friend's app). Parsing + fuzzy resolution is in; the UI widget is
  later.
- Community nicknames (Gary/Steve/Tim), reference-by-`oracle_id` / display-by-
  name for the friend's app, the bulk-data corpus, and relevance-filtering of
  rulings (we include all for now — revisit only if context bloat shows up).
