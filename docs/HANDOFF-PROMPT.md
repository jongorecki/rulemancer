# Handoff prompt (paste this into a fresh session)

Updated 2026-07-24. Update the "Where we are" line and the "first ask" whenever
the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full — start with the "SESSION-END STATE — 2026-07-24" block at the top, which is authoritative and supersedes everything below it, including the 07-23 block. Follow its "Read these FIRST" list before doing anything.

Where we are in one line: prompt v4 was planned, built, run and graded end to end — it **failed its own go criterion** (sonnet 46→46 with zero divergence, gpt-5-mini 45→43, and c014 never moved despite the whole notation legend being built for it) — condition E is closed on latency rather than accuracy, and a new four-slice plan is drafted and awaiting my review.

**The one open decision, and it blocks everything else:** master currently ships `PROMPT_VERSION = 4`, the failed candidate. It costs +1,215 tokens/query, buys the production model (sonnet) nothing, and drops gpt-5-mini to a 3-answer gap — which trips my own pre-commitment that a gap ≥3 pins sonnet and mothballs the ~8x cheaper generator. The controller's recommendation on record is to revert production to v3 and carry v4's content into the v5 candidate. I have not ruled.

The new plan: **docs/plan-v5-and-gold-discovery.md** — three independently-approvable slices. (A) selective symbol injection as the v5 candidate — scan the cards and question for symbols and inject only those definitions, pure code, no model call. (B) the miss matrix: run **only each arm's missed questions** across three prompt variants — v3, v4, and **v4-minus-legend** (v4's other bullets with the per-symbol definitions removed, since those get injected programmatically) — which both isolates what caused v4's regression and gives Slice A its baseline; c002 also gets a de-keyworded variant because naming "trample"/"deathtouch" may be steering retrieval toward keyword-definition rules. (C) automated gold-rule discovery, because I don't want to rebuild gold by hand. Still queued behind those: the rewriter bakeoff, Scryfall local-bulk (approved), SSO OIDC, and the deploy track whose critical slice is the budget breaker.

Respect the "How Jon works" section of the handoff exactly — especially:
- **Rule 0: plan before code.** Nothing gets built until I've reviewed the plan and ruled.
- **The judge instrument is FROZEN** (judge_bakeoff prompt + gpt-5-mini). Never reword it.
- **Grading verdicts are mine alone.** Tools may route and rank; they never assign a verdict. Same for gold: tools propose, I encode.
- **Never assert an MTG or model fact from memory** — ground in the CR (use the repo's own `data/raw/MagicCompRules 20260619.txt`, not a web copy), Scryfall, or a live check. Model pricing always via the claude-api skill.
- **Billing rule:** batch Claude-labor (grading, calibration, analysis) runs as in-session subagents on my subscription, never scripted Anthropic API calls. API spend is for the product/eval arms only.
- **Subagent-driven implementation** with fresh-context reviews (implementer → reviewer → fix loop, evidence not assertions). Commit per slice on master.
- **Any prompt-only A/B must use the SYSTEM-swap on a frozen capture** (see the handoff's "THE METHOD THAT MADE THIS WORK") — retrieval embedding is nondeterministic at ~30-34% chunk drift, and this method removes it entirely rather than controlling for it.
- **Verify agent self-reports against the filesystem and process table**, and never pipe a long-running python run through `| tail` — both cost us 40 minutes this session. The handoff's "OPERATIONAL LESSONS" section has the details.

Start by confirming you've read the handoff, then give me your recommendation on the v4 go/no-go with the reasoning, since that gates everything else.
