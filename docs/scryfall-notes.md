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
