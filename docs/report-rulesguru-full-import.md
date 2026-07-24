# Report — full RulesGuru import (1,409 questions) and what it does to the strategy

Fetched 2026-07-24. `evals/rulesguru_full.jsonl` — all 1,409 distinct questions
the public RulesGuru API returns (exhaustive, confirmed by id-wraparound). Same
schema as the frozen `evals/rulesguru.jsonl` (the 150 stay untouched). Fetch
script: `evals/fetch_rulesguru_full.py`. (This report is written by the lead;
the harness blocks subagents from writing report `.md` files.)

## The numbers

- **1,409 questions.** Level: 0→207, 1→565, 2→406, 3→162, Corner Case→69.
  Complexity: Simple→1,296, Intermediate→101, Complicated→12.
- **Card presence: 0 cards→9, 1→97, 2→635, 3+→668.** **99.4% reference at
  least one named card.**
- **Pure-rules (0-card) questions: 9.** All 9 carry valid gold. IDs: rg476,
  rg1006, rg1125, rg5482, rg5643, rg5658, rg5752, rg5832, rg6032. They cluster
  on CR 103.x (mulligans, starting life, 2HG/Commander setup).
- **Cost-tagged: 199** (Costs 109, Mana 62, Alt Costs 37, Numbers/symbols 42,
  Additional Costs 12; union 199). Disjoint from the 9 pure-rules.

## The finding that changes the plan

Jon's idea was to "pull a pure-rules held-out set" from RulesGuru to test
whether the CR-rule RAG earns its keep. **That set does not exist.** Nine
pure-rules questions in the entire live pool is not a measurable eval — one miss
is an 11-point swing. And this isn't a sampling artifact of the earlier 150; it
is the shape of the whole 1,409-question bank. **RulesGuru cannot answer "does
the CR-rule RAG earn its keep," at any sample size, because it is a card-scenario
question bank by construction.**

## Why this sharpens the strategy rather than just blocking it

Put this beside the held-out report's premise 2 (on card questions the model
answers from the card's oracle text, not the retrieved CR rules). Together:

1. Real MTG rules questions are **almost always about specific card
   interactions** — 99.4% here. Abstract pure-rules questions ("who has
   priority?") are rare *in practice*, not just in our eval.
2. On those card questions, **oracle text carries the answer**, and the CR-rule
   RAG is supporting cast.

So the "retrieval coverage" lever the held-out report floated is **weaker than
it looked**: better CR-rule retrieval mostly helps the ~0.6% pure-rules slice.
The levers that actually move the product are the ones that serve card-scenario
reasoning:

- **Reasoning quality on card interactions** — exactly what the **cost-calculator**
  targets (the c014 / Trinisphere arithmetic failures). This finding *raises* its
  priority relative to where the held-out report left it.
- **Card-data quality** — getting each card's oracle text right and resolvable.
  Which is precisely what the **Scryfall local-bulk + per-face-lookup** work
  (Jon just approved) delivers. Also well-aimed.

Coverage/rerank of the CR-rule RAG remains real but is now clearly the *third*
priority, not the first — the opposite of where the ranking-vs-coverage framing
started the night.

## What the 1,409 set IS good for

- A **much larger held-out answer-quality eval** (card-based — which is the real
  domain). The 150-question 72%/57% result can be extended to ~1,400 for a
  tighter number, at a real but bounded generation+judge cost.
- **Cost-calculator validation:** 199 cost-tagged questions, a genuine test set
  for the calculator beyond c014 alone.
- **Training data** (Jon's stated future use).

## Caveats recorded

- **The API re-randomizes on refetch:** player names and sometimes a
  functionally-equivalent card substitution change per request (rg6328's "Bog
  Glider" → "Aang's Journey" on this fetch). So `rulesguru_full.jsonl` is a
  frozen **snapshot** — the committed file is stable, but a refetch will not be
  byte-identical. `gold`/`level`/`complexity`/`tags`/`submitter` are stable; the
  templated `question`/`cards`/`answer_gold`/`url` vary. Retrieval scoring (uses
  `gold`) is unaffected; exact-text matching against a past fetch is not
  reproducible. Verified the frozen 150 still match on the stable fields.
- Gold-id CR-corpus validity was not checked in the fetch worktree (`data/raw/`
  absent there); worth a one-line check on master before the full set is used
  for scoring.
- The 97 one-card questions are a larger-but-noisier pure-rules-ish tier, but
  separating "card is load-bearing" from "card is flavor" needs triage that
  wasn't done. Flagged, not guessed.
