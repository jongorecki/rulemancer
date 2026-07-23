# Handoff prompt (paste this into a fresh session)

Written 2026-07-23 evening. Update the "Where we are" line and the "first ask"
whenever the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full — start with the "SESSION-END STATE — 2026-07-23 evening" block at the top, which is authoritative and supersedes everything below it. Follow its "Read these FIRST" list before doing anything.

Where we are in one line: prompt v3 is shipped and adopted as the interim production prompt, the v3 A/B is fully run and graded (sonnet 46/50, gpt-5-mini 45/50 at ~8x cheaper), and SIX Rule 0 plans are drafted and awaiting my review — nothing is running and nothing is approved to build.

The six plans: docs/plan-prompt-v4.md (fully ruled, ready), docs/plan-condition-e-reasoning.md (gates the deferred L2 model switch), docs/plan-rewriter-model-bakeoff.md, docs/plan-scryfall-local-bulk.md (approved, sequenced later), docs/plan-sso.md (OIDC next), docs/plan-deploy.md (budget breaker is the critical slice).

Respect the "How Jon works" section of the handoff exactly — especially:
- **Rule 0: plan before code.** Nothing gets built until I've reviewed the plan and ruled.
- **The judge instrument is FROZEN** (judge_bakeoff prompt + gpt-5-mini). Never reword it.
- **Grading verdicts are mine alone.** Tools may route and rank; they never assign a verdict.
- **Never assert an MTG or model fact from memory** — ground in the CR, Scryfall, or a live check. Model pricing always via the claude-api skill.
- **Billing rule:** batch Claude-labor (grading, calibration, analysis) runs as in-session subagents on my subscription, never scripted Anthropic API calls. API spend is for the product/eval arms only.
- **Subagent-driven implementation** with fresh-context reviews (implementer → reviewer → fix loop, evidence not assertions). Commit per slice on master.
- **Any new A/B must use the assemble-once prompt cache** — retrieval embedding is nondeterministic (~30-34% chunk drift).

Start by confirming you've read the handoff, then give me your one-paragraph recommendation on which of the six plans to implement first and why, so I can rule on sequencing.
