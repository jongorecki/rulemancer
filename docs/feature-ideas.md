# Feature ideas — approved shortlist (Jon, 2026-07-22)

Source: a research sweep of the MTG rules-tool landscape (evidence appendix
below). Jon reviewed the full candidate list and picked the set here. Per
Working Rule 0, NOTHING on this list gets built without its own plan doc
reviewed by Jon first. Sequencing: all of these sit BEHIND the main queue
(arm-run verify → sonnet re-grade → L3 SQLite → L1 cross-refs); the
frontend-only items can ride any quiet-tree gap.

## The shortlist

### 1. Clarify → then escalate to a real judge (Jon's refinement)

When the bot can't answer (`answered: false`), don't jump straight to an
escalation link. First ask the user a clarifying question — see if added
context gets us to an answerable state. Only after clarification still
fails does the UI show an "ask a real judge" link to
https://chat.magicjudges.org/mtgrules/ (24/7 human judge chat).

NOTE on the rewriter (Jon, 2026-07-22): the Haiku `clarification` output is
NOT a clarifying question — it's a translation of whatever the user typed
into actual rules vocabulary. It does not drive this feature's clarify
step; that needs its own mechanism. Related parked idea (later, not part
of this feature): show the user that rules-talk translation and confirm
"is this what you meant?" — a cheap trust surface once the core flow works.

### 2. Legality chip on discussed cards

Scryfall card responses already carry the `legalities` field. Surface a
banned/restricted chip on cards the answer references. Cheap (S) — data is
already fetched; this is display only. Evidence: standalone banlist
checkers are widely used (https://mtgcommander.net/index.php/banned-list/).

### 3. Misconceptions example gallery

Curate the starter pills (and possibly a dedicated gallery) around famous
confidently-wrong rules beliefs — deathtouch+trample is already our lead
example. Doubles as demo content: a visitor who gets one wrong is instantly
sold. Evidence: example galleries are a known onboarding/trust pattern;
real-world consequences of rules misconceptions are documented at
https://outsidetheasylum.blog/rules-issues/.

### 5. Shareable answer permalinks

Per-answer URLs so a Rulemancer answer can settle a Discord/Reddit rules
argument. Judge-community bots live on linked rulings (judgebot:
https://github.com/bra1n/judgebot). Depends on L3 — SQLite gives us the
answer storage; do not build before L3 lands.

### 6. "Undefined in the CR" flag

For questions that hit the CR's documented contradictions/undefined zones
(catalog: https://outsidetheasylum.blog/rules-issues/), refuse WITH the
reason — "the CR does not cleanly define this" beats a confident guess.
Hardest-to-fake credibility feature on the list; likely needs a small
curated list of known-broken interactions to detect against.

### 7. Donate / "buy me a coffee" link (Jon's addition)

A small, unobtrusive donate link on the page for the public deploy.
Placement/provider TBD in its own mini-plan (footer next to the WotC/
Scryfall attribution is the obvious spot).

## Considered and NOT picked (with why, for the record)

- **Per-answer CR-version line** — not picked in this round.
- **Confidence indicator** — anti-feature risk (fake precision trains users
  to ignore it); our answered/hedge behavior already carries the signal.
- **Quiz/practice mode** — pivots the product from Q&A to study tool (M/L).
- **Decklist upload** — L effort, integration flex we don't need.
- **IPG/MTR corpora, REL-aware answers** — new documents, real scope creep.
- **Commander mode** — partial value comes free via Scryfall; a dedicated
  mode is UI surface without demo payoff.
- **Multi-source ruling aggregation, version diffing** — M+ effort, weaker
  demo story than what was picked.

## Evidence appendix (research agent, 2026-07-22)

### Landscape

- RulesGuru.org — judge/player study DB of ~1,487 rules questions; filter
  by difficulty/topic/format, public API, procedural question generation
  (https://rulesguru.org/, https://github.com/KingSupernova31/RulesGuru).
  Already the source of our external 150-question eval set.
- chat.magicjudges.org — 24/7 live judge chat; the human-escalation tier
  (https://chat.magicjudges.org/mtgrules/).
- judgebot (Discord) — !card/!ruling/!legal/!cr/!ipg/!mtr commands; treats
  CR vs IPG vs MTR as distinct citable documents
  (https://github.com/bra1n/judgebot).
- Judgy — free AI MTG rules assistant, thin public info
  (https://askjudgy.com/).
- MTG Agents ("Nissa") — AI assistant citing CR + Scryfall + RulesGuru +
  StackExchange, deck upload; markets itself against "hallucinating generic
  chatbots" (https://mtg-agents.com/). Direct competitor; study their
  positioning for the README.
- Yawgatog / Academy Ruins — CR change-diff trackers
  (https://yawgatog.com/resources/rules-changes/).
- Scryfall rulings — labels each ruling "Official (WotC)" vs
  "Scryfall-added" (https://scryfall.com/docs/api/rulings).
- boggs.tech fine-tuning study — plain fine-tuned LLMs still misinterpret
  card interactions; hallucination not fixed by training alone
  (https://boggs.tech/posts/large-language-models-for-magic-the-gathering/).
  Validates the RAG+citations thesis; README material.

### Anti-features (what destroys trust in rules answers)

- Answering confidently without grounding (boggs.tech study above).
- Fake-precision confidence numbers — always-90%+ scores train users to
  ignore them (https://aiuxplayground.com/pattern/confidence-score/).
- Presenting the CR as complete/consistent — it demonstrably isn't
  (https://outsidetheasylum.blog/rules-issues/).
- Letting rulings go stale without indicating what changed or when —
  WotC's own multi-platform ruling sprawl already causes contradicting,
  silently-outdated answers (same source).
