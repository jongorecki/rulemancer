# Plan — #3b: Scryfall card tool + tool-routing (DRAFT, pending Jon's review)

Working Rule 0 artifact. No code until reviewed. MVP only — the richer card
features live in docs/scryfall-notes.md and stay DEFERRED (see "Out of scope").

## What this adds, in one sentence

The rules bot can currently only answer from the Comprehensive Rules. This adds
a second source — a specific card's oracle text from Scryfall — and a router
that decides, per question, whether it's a *rules* question (retrieve the CR) or
a *card* question (look the card up).

## The split that matters (why a router at all)

"How does trample work?" is a rules question — answered from rule 702.19.
"What does Llanowar Elves do?" is a card question — answered from that card's
oracle text, which is nowhere in the CR. Feeding a card question to the rules
retriever returns nothing useful; feeding a rules question to Scryfall finds no
card. The router picks the right source. Getting that decision right is the
whole feature.

## Step 0 — the reachability spike (do FIRST, gates everything)

Same discipline that saved a day on q016: **before building anything, confirm
the environment can even reach the Scryfall API.** The Anthropic and Voyage
SDKs work here, but those hosts may be allowlisted; a raw HTTPS call to
`api.scryfall.com` might be blocked at the sandbox egress (this exact failure —
"403 from proxy after CONNECT" — is documented for self-constructed URLs in the
*other* project on this machine).

The spike: two requests — fetch one known card (`GET /cards/named?exact=Llanowar
Elves`) and one fuzzy (`?fuzzy=llanowar elf`) — and print the status, the
`oracle_text`, and the rate-limit headers.

- Reachable → build the tool as below.
- Blocked → the plan changes fundamentally (mock/fixture the tool for the eval,
  or defer #3b until an environment that can reach it). Report and stop rather
  than building a tool that can't run.

One script, two requests. It decides whether the rest is real.

## 1. The tool — `src/rulesagent/tools/scryfall.py`

`get_card(name: str) -> Card | None`

- **Lookup:** `GET https://api.scryfall.com/cards/named?fuzzy=<name>` (fuzzy
  handles partial names and minor typos; exact is a fallback for disambiguation
  later — deferred). 404 → return None (unknown card), not an exception.
- **Returns** a small typed `Card` (new in contracts.py): `name` (the resolved
  canonical name), `oracle_text`, `type_line`, `mana_cost`. Double-faced / split
  cards carry their text in `card_faces[]` — the tool joins those so the MVP
  doesn't silently drop half a card.
- **Rate limit + courtesy (Scryfall's published guidance):** a descriptive
  `User-Agent` and `Accept` header on every request; ~100ms min spacing between
  calls; disk cache (below) so we never re-hit for a name we've seen.
- **Attribution:** the tool result carries a "Card data from Scryfall" note that
  the answer surfaces. Card data is under Wizards' Fan Content Policy — relevant
  only if the friend's app goes commercial (master plan's "Still open"), not for
  this build.

### Reproducibility: cache card lookups to disk

Like the query-embedding, rerank, and rewrite caches: card lookups are cached to
`data/parsed/scryfall_cache.json` keyed by the normalized query name. The card
eval then makes zero network calls on a re-run and is byte-reproducible — same
property every other eval in this repo has. (Cache invalidation isn't a concern:
oracle text for a given printing is stable; we're not tracking new sets here,
that's the deferred bulk-corpus use.)

## 2. Routing — native LLM tool-use (Jon's lean)

**Mechanism: give the model the Scryfall tool and let its tool-call *be* the
routing decision.** One LLM call with `get_card` defined as a tool:

- Model calls `get_card(name=...)` → it's a card question, AND the model has
  already extracted the card name for us. Routing and name-extraction in one
  step — a clean, demonstrable tool-use loop (and exactly the agent/tool-use
  material AI-103 covers).
- Model doesn't call the tool → it's a rules question → hand off to the existing
  rewrite → retrieve → generate pipeline unchanged.

This is genuinely "LLM tool-use for routing," not a keyword heuristic. The
keyword alternative (`@` triggers, "what does X do" patterns) is rejected for
the same reason we reject tuned thresholds elsewhere: it's brittle and it's a
worse interview answer than "the model decides, and here's the measured
accuracy."

### Dispatch after routing

- **Card path:** execute `get_card`, feed the oracle text back as context, model
  writes the final `Answer` citing the card by name.
- **Rules path:** the existing `RulesAgent.answer()` untouched.
- **MVP keeps it either/or.** "How does trample work on *Rampaging Baloths*?"
  genuinely needs both sources; that's a real case but it's multi-hop, and
  bolting it on now bloats the MVP. Noted, deferred.

### Router model

Routing is a cheap classification-shaped task, so the rewriter's logic applies:
propose `claude-haiku-4-5` for the router, but **measure it against
claude-sonnet-5 on the card eval** rather than assuming — a wrong route is a
wrong answer, so if Haiku mis-routes we pay for Sonnet. Pinned either way, for
reproducible evals. Generation stays `claude-sonnet-5`.

## 3. Eval — its own set, its own metrics (per-corpus rule)

DECISIONS already established eval sets stay scoped to their corpus: card
questions get their OWN set with gold pointing at cards, never mixed into the
rules `questions.jsonl` (a card question has no gold rule, so it would corrupt
recall@k).

**Jon authors the card eval set (do-not-delegate — it's eval curation).** What
it needs, roughly 12–20 questions:
- Clear card questions ("what does <card> do?") → gold = card name.
- Clear rules questions (reuse a few from the rules set) → gold = "rules path".
- A few deliberately ambiguous or adversarial ones (a card whose name is a rules
  word — e.g. "Counterspell", "Fog", "Flash") to stress the router.

**Metrics:**
- **Routing accuracy** — did it pick card-vs-rules correctly? The headline.
- **Card-name extraction** — when it routed to card, did it pull the right name?
- **Card-answer faithfulness** — does the answer match the oracle text? (Jon
  grades, same faithfulness method as the rules answers.)

## 4. Integration + contract

- A thin router layer above `RulesAgent` (a `MtgAgent` or `RulesAgent.route()` —
  name TBD) so the rules pipeline stays self-contained and separately testable.
- `Answer.citations` holds the card name on the card path (it's "what the answer
  relied on" — same field meaning, no new field needed for the MVP).
- New `Card` model in contracts.py; new `scryfall_cache.json` gitignored under
  data/parsed (don't commit card data, same rule as the CR text).

## Decisions for Jon

1. **Routing = native tool-use** (model given `get_card`, its tool-call is the
   route + name extraction)? I lean yes — it's your stated lean and the cleaner
   demo. Confirm vs. a separate classify-then-dispatch call.
2. **Router model** — measure haiku vs sonnet, default to whichever the card
   eval says (I lean sonnet as the safe default since a mis-route is a wrong
   answer)? Or just pin sonnet and skip the A/B for the MVP?
3. **Card eval set** — you author ~12–20 questions (clear card, clear rules, a
   few adversarial name-collision ones). How many, and do you want to write them
   now or after the tool exists so you can see it fail live?
4. **Run the Step 0 reachability spike now?** It's 2 requests, answers the
   biggest unknown (can we hit Scryfall from here at all), and I can run it
   without waiting on anything.

## Out of scope (DEFERRED — docs/scryfall-notes.md)

@-autocomplete, community nicknames (Gary/Steve/Tim), per-card rulings via
`rulings_uri`, reference-by-`oracle_id` / display-by-name for the friend's app,
the bulk-data corpus, and multi-source ("card + rules") answers. All real, all
captured, none in the MVP.
