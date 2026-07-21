# Scryfall — future data sources (NOT building yet)

Captured 2026-07-21. These are deferred per the build plan ("No infrastructure
right now — it's procrastination that feels like progress"). The core project
is RAG over the Comprehensive Rules; Scryfall is a later expansion. Written
down so the design intent isn't lost, not as a spec to build now.

## Two distinct uses (don't conflate them)

1. **Scryfall as a TOOL** (planned for the generation phase, days 6-9;
   `tools/scryfall.py`). The agent calls the Scryfall API at query time to
   look up a specific named card's oracle text. Point lookup, not RAG.
2. **Scryfall bulk data as a CORPUS** (bigger, later). The CR has no
   card-specific context, so answering card-level questions needs card data
   indexed as its own retrievable corpus — separate index, separate eval set
   from the rules (see DECISIONS: eval sets stay per-corpus).

## Bulk data (for the corpus use)

Scryfall publishes bulk data files (`/bulk-data` endpoint) with an
`updated_at` timestamp per file. Relevant ones:
- **oracle_cards** — one entry per unique oracle_id (dedupes printings).
  Best fit for "what does this card do" — already English oracle text.
- **rulings** — official per-card rulings. Rich source of interaction Q&A;
  strong candidate for its own RAG corpus + its own eval questions.
- default_cards / all_cards — every printing; more than we need.

## Auto-update design (Jon's intent, 2026-07-21) — for when we build it

- Check the bulk-data endpoint's `updated_at`; only re-pull when it's newer
  than what we have. Store the last-seen timestamp.
- **English cards only** — filter to `lang == "en"` (oracle_cards is already
  effectively this, but assert it).
- **Incremental — only care when new lines are added.** Diff against the
  prior pull by a stable key (oracle_id for cards; oracle_id + ruling text/
  published_at for rulings) and process only new entries, rather than
  re-embedding the whole file each refresh.
- Don't commit the bulk file to the repo (it's large and not ours) — fetch
  at build time, same rule as the CR text.

## Attribution / rate limits (must honor when we use it)

- Follow Scryfall's rate-limit guidance (they ask ~50-100ms between requests;
  bulk files are meant to avoid hammering the API).
- Include Scryfall attribution. Card data is under Wizards' Fan Content
  Policy — relevant if the friend's app ends up commercial (see the master
  plan's "Still open").

## Card-lookup requirements (Jon, 2026-07-21) — for when we build Scryfall

These are firm design requirements for the card-lookup feature, captured now,
built later.

### 1. Autocomplete card selection with a trigger character
- Let users pull up specific cards by name via autocomplete against the card
  database. Because very common words appear on huge numbers of cards, start
  autocomplete from an explicit **trigger character** (Jon's idea: `@`), not
  from every keystroke of free text. So typing `@gray...` begins completing
  card names.
- Scryfall has an autocomplete endpoint (`/cards/autocomplete?q=`), but for a
  fast local experience we can index card names from the `oracle_cards` bulk
  file and complete against that.

### 2. Nicknames
- Support calling the handful of cards that have well-known community
  nicknames by that nickname. Known so far (Jon, the common ones):
  - **Gary** = Gray Merchant of Asphodel
  - **Steve** = Sakura-Tribe Elder
  - **Tim** = Prodigal Sorcerer
- Implement as a small, extensible nickname -> card map; resolve a nickname to
  its real card before lookup.

### 3. Per-card rulings
- Pull individual card rulings from the `rulings_uri` on a card object (and/or
  the `rulings` bulk-data file). This is a distinct data source from oracle
  text and a strong candidate for its own retrievable corpus + eval set later.

### 4. Reference by oracle_id, display by name (friend's app)
- Internally identify a card by its Scryfall **`oracle_id`** (a stable UUID
  that survives reprints), but **always show the card's NAME in the UI**. The
  oracle_id is not human-readable and doesn't contain the name, so it's useless
  as a user-facing label. Store/pass oracle_id; resolve to name for display.
- This matters specifically for the friend's app integration -- keep the ID/
  display separation in the data model from the start.
