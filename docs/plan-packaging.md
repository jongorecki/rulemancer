# Plan — #1 Packaging: README + repo hygiene (~1 focused day)

The repo's job (Jon's framing, 2026-07-22): a portfolio piece for ALL his job
interviews — any technical reader skims it for 90 seconds, or clones it and
has it running in one command. Not written at one specific audience.
Articulation beats polish — the README IS the interview answer, written down.

## Part 1 — README.md

Structure, in order:

1. **What it is, 3 sentences.** RAG agent over the MTG Comprehensive Rules
   (3,617 chunks) + per-card rulings mini-RAG + Scryfall enrichment, FastAPI
   backend, chat frontend. One command to run. Built as an applied-AI
   proof-of-work; every decision logged in DECISIONS.md.
1b. **Why MTG (Jon's addition):** (a) a dataset he has deep domain expertise
   in from years of playing — which is what let him curate honest eval gold
   and catch the model being confidently wrong; (b) the Comprehensive Rules
   are genuinely complex — a 300-page formal spec full of cross-references,
   exceptions, and layered interactions; (c) the architecture transfers
   directly: any org with a dense rulebook-shaped corpus (compliance docs,
   insurance policy, internal procedures, other games' rulesets) is the same
   problem with different text. Sibling project: **Cardomancer** (his
   card-sorting machine — OpenCV + image hashing + embeddings) lives in the
   same ecosystem: hardware that identifies the cards, an agent that answers
   what the cards do. Link it.
2. **The numbers table** (headline, near the top):
   - Retrieval recall@5: BM25 32% → vector (voyage-4-large) 65% → +query
     rewriting ~70% (5-draw mean, temp=0)
   - Answer faithfulness: 31/31 rules questions graded correct (pre-prompt-
     change grade; re-grade pending, stated as such)
   - Ruling mini-RAG: context cut 35→6 / 22→3 / 18→3 rulings with zero
     correctness lost; load-bearing ruling selected 12/15
   - Judge agreement Haiku-vs-sonnet: 94–99%
3. **"What I got wrong first" arc** (the differentiator — most portfolio RAG
   repos only show wins):
   - Hybrid retrieval made it WORSE (32% BM25 dragging fusion down) — measured,
     rejected, kept the code and the reasoning
   - The 77% rewrite number was a lucky draw — temp=0 + 5-draw mean showed ~70%;
     reporting one sample of a noisy variable is how eval numbers lie
   - The chunk split HURT its own target question (q016 rank 16→84) and was
     kept anyway — the honest tradeoff, documented
   - Retrieval-miss ≠ answer-wrong: q016 answered correctly via rules the gold
     didn't list — single-gold recall undercounts multi-path questions
   - The ablation that showed the rules-RAG was REDUNDANT on 4 of 5 card
     questions — and how the eval set was rebuilt because of it
   - **Tibalt-cascade:** the RAG corrected both its builders — two confident
     humans+model wrong on pre-errata memory, one grounded rule right
     (702.85a). The reason the project exists, in one story.
4. **Architecture sketch** — pipeline diagram in text (question → rewrite →
   vector top-15 → card enrichment + ruling mini-RAG → sonnet-5 structured
   answer with citations → enriched API response). Link each stage to its
   plan doc / DECISIONS entry.
5. **Quickstart** — the honest build-from-scratch path: clone, `uv sync`,
   `.env` from `.env.example` (VOYAGE_API_KEY + ANTHROPIC_API_KEY), fetch CR
   txt into data/raw, parse + chunk + embed (Makefile targets — VERIFY each
   command actually works from a clean data/ before writing it down), then
   `uv run python run.py`. State costs: embedding the corpus ≈ free tier,
   answers ≈ cents.
6. **Evals** — how to run them, what each measures (recall@k vs answer
   faithfulness vs ablation-derived gold), the do-not-delegate philosophy.
7. **Limitations, stated plainly** — multi-hop ceiling (q016/c010/c011/c019
   class), sonnet-5 draw variance (mitigated by degenerate-retry, not gone),
   single-worker cache constraint, private-demo posture (no auth).
8. **Attribution footer** — WotC Fan Content Policy statement + "Card data
   from Scryfall" + unofficial/not-endorsed line.

Voice: Jon's — plain, direct, numbers first, no AI-tells. Draft goes to Jon
for review before commit; he owns the final read.

## Part 2 — Repo hygiene (state verified 2026-07-22)

| Item | State | Action |
|---|---|---|
| LICENSE | missing | MIT (Jon's call, 2026-07-22). Code only; CR text + card data stay unredistributed (already gitignored) |
| .env.example | exists | add OPENROUTER_API_KEY, commented optional — Jon's .env already has it; used by the upcoming outside-judge eval (to-do #4), not by the app |
| data/ gitignored | verified clean | none |
| uv.lock | currently IGNORED | commit it (reproducible installs for an app repo); remove from .gitignore |
| CR revision | 20260619 = current official (checked 2026-07-22) | none |
| Font | see Part 3 | decision below |
| Scryfall/WotC attribution | in answers already | add to README footer + LICENSE-adjacent NOTICE if needed |

## Part 3 — Font decision (blocker for going public)

Checked on dafont (2026-07-22): Citadel of Blackrose is **donationware, €2
per project** ("once you've paid €2, you're free to use for one project").
That license covers USING the font; it does not grant REDISTRIBUTION of the
TTF, which is what committing it to a public repo does.

**Decision (Jon, 2026-07-22): option A** — render the wordmark to an SVG
once, ship the image, drop the TTF from the repo. Keeps the exact look; the
font is a design tool, not a shipped asset. The €2 donation for strict
per-project compliance is Jon's to make separately.

## Part 4 — one-key config via OpenRouter: checked, rejected

Jon asked whether embeddings could run through the OpenRouter key to
simplify configuration. Checked live (2026-07-22): OpenRouter now HAS an
/embeddings endpoint, but its model list (27 models: OpenAI, Google,
Qwen, Mistral, BGE, E5...) has NO Voyage models. Consolidating would mean
switching embedding MODELS, not keys — invalidating every measured
retrieval number and forcing a corpus re-embed + full eval re-run. Rejected
for packaging; noted in DECISIONS.md. A cross-embedding-model A/B is a
possible future README result, on its own merits.

## Order of work

1. Font decision (Jon) → implement it
2. Hygiene items (LICENSE choice from Jon, uv.lock, attribution)
3. README draft → Jon reviews → revise → commit
4. Clean-clone quickstart verification (the "stranger runs it" test) — run the
   documented commands in a scratch checkout before calling packaging done

## Verification

- Quickstart commands executed successfully from a fresh clone (scratch dir),
  fresh data/ build included.
- Every number in the README traced to a DECISIONS/LOG entry (no memory).
- No personal-use-restricted assets tracked in git.
- `git ls-files data/` still empty; uv.lock tracked; LICENSE present.
