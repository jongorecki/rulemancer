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

## Card references: `[brackets]` in the query, `@` is the typing UI (Jon, resolved)

Two separate layers, don't conflate them:

- **`@` is a frontend input affordance, not the query format.** On a keyboard
  (mobile especially — the likely primary surface), typing `@` opens
  autocomplete against card names, the same gesture as tagging someone in social
  apps or Outlook. It only fires on `@` so it never nags mid-sentence during
  normal typing. Once a card is chosen, the UI **drops the `@` and wraps the name
  in `[]`.** This whole layer needs a frontend → **DEFERRED** (the autocomplete
  endpoint works today; the widget waits for a UI / the friend's app).

- **`[Card Name]` is what the pipeline actually parses.** By the time a query
  reaches the agent, cards are `[...]` tokens. Hand-written eval questions use
  the same form: "can I use [Dovescape] to counter a spell while [Dovin's Veto]
  is out?" Deterministic parse, no LLM name-guessing, no "Fog-the-card vs in a
  fog" ambiguity, and brackets delimit multi-word names cleanly.

**Contract:** only `[...]`-referenced cards are looked up. "what does Llanowar
Elves do?" (no brackets) is plain text; "what does [Llanowar Elves] do?" triggers
the lookup.

**Name OR oracle_id, same brackets (Jon's add, verified).** A `[...]` token is
either a card name or a Scryfall `oracle_id` (the stable cross-printing UUID).
Detection is a UUID regex; resolution:
- name → `GET /cards/named?fuzzy=<name>` (typo-tolerant).
- oracle_id → `GET /cards/search?q=oracleid:<uuid>` → take the first printing.
Both verified against Dovin's Veto (same oracle_text either way). This is the
"reference by oracle_id, display by name" the friend's app wants — the data
model carries the id, answers show the resolved name.

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
- **Cache with a TTL (Jon's correction):** disk-cache lookups + rulings to
  `data/parsed/scryfall_cache.json` (gitignored), each entry stamped with
  `fetched_at`. **Rulings get ADDED over time** (WotC issues them after a set
  ships), so a permanent cache would serve stale enrichment — entries older than
  the TTL are re-fetched. Proposed TTL: **7 days** (rulings churn is slow;
  configurable). Keyed by the resolved card name/oracle_id.
- **The TTL-vs-reproducibility tension, and the fix:** a re-fetching cache breaks
  the "eval re-runs are byte-identical" property every other eval here has. Fix:
  the **card eval runs against a frozen fixture** — a committed snapshot of the
  cache (or a `--no-refresh` mode that ignores the TTL) — so eval numbers are
  reproducible, while the **live tool uses the TTL** for freshness. Two modes,
  one cache format. (Confirm the TTL value + whether to commit the fixture vs.
  flag-freeze.)

## 2. The pipeline

Extending the agent (an `enrich`/`route` method above `RulesAgent`, name TBD).
**Order matters — Jon's call: the Scryfall data goes in AFTER the Haiku rewrite,
not before.**

1. **Parse** `[...]` tokens from the question.
2. **Fetch** oracle text + all rulings for each (cached).
3. **Rewrite + retrieve rules** via the existing #3a path, UNCHANGED. The
   rewriter (Haiku) sees the question text only — **NOT** the card oracle text.
   (My v1 draft floated feeding card text to the rewriter; Jon rejected it, and
   he's right: it keeps the rewriter a pure question→rules-vocab translator,
   identical to what #3a measured, instead of a new untested behavior. The rules
   query comes from the question's *shape* — "counter a spell that can't be
   countered" — which the rewriter already handles.)
4. **Assemble the generator prompt in order:** retrieved rules first, THEN the
   Scryfall card data (oracle text + all rulings per card), THEN the question.
   The card data enriches the answer at generation time; it never touches
   retrieval or rewriting.
5. **Generate** into the structured `Answer`. Citations cover both rule numbers
   and card names (same field; "what the answer relied on"). Answers that used
   card data carry the Scryfall attribution.

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

## Decisions for Jon (one left)

1. **Cache TTL = 7 days, and eval reproducibility via a committed cache
   fixture** (vs. a `--no-refresh` flag) — confirm, or set a different TTL. This
   is the only open item; everything else is settled by your answers
   (`[brackets]` query format, name-or-oracle_id lookup, all rulings, Scryfall
   data added after the rewrite, pipeline-first, full enrichment).

## Out of scope (DEFERRED — docs/scryfall-notes.md)

- **The `@` autocomplete UI** — endpoint works and the pipeline parses
  `[brackets]` now, but the `@`-triggered as-you-type dropdown needs a frontend
  (or the friend's app). Parsing + fuzzy/oracle_id resolution is in; the widget
  is later.
- Community nicknames (Gary/Steve/Tim), the bulk-data corpus, and relevance-
  filtering of rulings (all included for now — revisit only if context bloats).
- (Note: oracle_id lookup and display-by-name, previously deferred, are now IN
  scope per Jon's clarification.)
