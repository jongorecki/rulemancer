# Competitive landscape — AI MTG rules bots (researched 2026-07-22)

Two research passes (Sonnet agents, evidence-required contract). Raw
material for the README's positioning section. Snapshot date matters:
this space is tiny and moving.

## Ranking by usability + correctness evidence (as of 2026-07-22)

1. **MTG Agents / "Nissa"** (mtg-agents.com) — the real competitor. Free
   web+Discord, multi-agent RAG over CR + MTG wiki + Scryfall + RulesGuru
   + Stack Exchange, a checker agent extracts sources, cites rule numbers.
   ~200 weekly / ~1,000 regular users after front-paging the MTG
   subreddits. Published SELF-eval: ~90% correct on 45 questions,
   LLM-as-judge, not third-party audited
   (https://medium.com/@fkrempl/evaluating-a-multi-agent-system-for-magic-the-gathering-rules-questions-d206044deef1).
   Also ships a deck-builder agent (Karn) with intent routing.
2. **MTJudge** (mtjudge.app) — free open beta, no login, card→Oracle→CR
   pipeline with CR-section citations. No evals, no visible users. Honest
   site copy: "AI can make mistakes... always double-check with a judge."
3. **MTG Judge** (mtg-judge.com) — free, no signup, CR+Scryfall grounding,
   "not always correct" disclaimer, user-facing dispute button feeding
   improvement. No evals.
4. **MagicJudge (iOS)** — freemium app, 3.9/5 from 19 ratings. The ONLY
   concrete third-party correctness complaint found anywhere in this
   space: wrong info + STALE DATA after new sets ("abandoned"), plus a
   billing dispute (https://apps.apple.com/us/app/magicjudge/id6738770397).
5. **GPT-store "MTG Judge" GPTs** — prompt-engineered over base GPT, no
   disclosed retrieval, behind ChatGPT accounts. Aggregator ratings only.
6. **Judgy** (askjudgy.com) — unfetchable JS shell, zero documentation,
   zero community mentions. **eliso7/rulebot** — unreleased (0 stars).

**Rulemancer's position:** #1 on correctness EVIDENCE (50 hand-graded +
150 external RulesGuru + variance runs + judge chosen by bakeoff — more
rigorous than the market leader's entire self-eval), last on usability
until deployed. L3 -> Fly.io is the whole ballgame.

## Key findings

- **No organic Reddit presence for ANY bot.** Name searches across
  r/mtgrules, r/magicTCG, r/EDH found no threads. Nobody has mindshare;
  the default competitor is "post to r/mtgrules / ask a judge."
- **Nobody publishes rigorous evals.** Best is MTG Agents' 45-question
  self-judged set. Our eval discipline is the differentiator — the README
  should show the table, not claim the virtue.
- **The one real-world correctness complaint is STALENESS** (MagicJudge,
  wrong after new sets). Freshness signaling (CR-version line per answer)
  is cheap and evidence-backed — declined in the 2026-07-22 shortlist
  round but worth revisiting pre-deploy.
- **WotC patented confidence-gated answer-or-clarify** (compute
  confidence; either answer or ask a clarifying follow-up) — exactly
  feature #1 on our shortlist, which no live bot has
  (https://draftsim.com/mtg-ai-assistant-wotc/). Validation of the idea;
  the demo is free/noncommercial, but worth remembering the patent exists.
- **Vendors self-disclose fallibility** in their own copy (MTJudge, MTG
  Judge) — trust is the known pain point in this category.
- **Dispute/feedback loops** (MTG Judge button) — we already have this
  (thumbs + note -> feedback log).

## What they have that we don't (and current stance)

- Multi-source retrieval beyond CR+rulings (Nissa: RulesGuru, Stack
  Exchange) — considered, not picked (scope).
- Companion deck-builder agent + intent routing (Nissa) — out of scope for
  a rules-bot demo.
- Native mobile app / offline packaging (MagicJudge, Judge Orbit) — out of
  scope.
- Confidence-gated clarify-before-answer — on OUR shortlist (#1); nobody
  has shipped it.
