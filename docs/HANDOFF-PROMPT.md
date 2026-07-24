# Handoff prompt (paste this into a fresh session)

Updated 2026-07-24 (session 2). Update the "Where we are" line and the "first
ask" whenever the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff rather than prepending — don't dig through git for superseded blocks. It opens with "THE ONE THING TO DO FIRST" (plan the layer-system tool) and a short strategy section; read those. Also skim the shelved combat plan's **§11 build-prep research** in `docs/plan-combat-damage-tool.md` — it's why combat was shelved and it carries the loop-gating trap and the CR-grounding lesson that both apply to the layers plan you'll write.

Where we are in one line: the **cost tool is shipped and reliability-hardened** (cap-exhaustion killed, malformed-answer guard added — empty-output 0/24 vs ~29%), Jon's RulesGuru regrade is folded in (**75.3%** held-out), combat-damage is **shelved** (plan complete but only ~7 real assignment questions in the corpus), and the **next tool is the layer-system resolver (CR 613) — Jon ruled it the next lever — which needs a plan.**

## The first ask

**Plan the layer-system resolver tool (CR 613).** This is a NEW tool → **Rule 0: write `docs/plan-layer-system-tool.md` (design only), and don't build anything until I've reviewed it and ruled.** I ruled layers the next tool over combat (combat's ROI is thin — only ~7 real assignment questions in the whole corpus; layers recurred on four of my regrade misses and targets the weakest tier, Corner Case 50% — see DECISIONS.md). The plan must:

- **Ground in CR 613** from `data/raw/MagicCompRules 20260619.txt` — never from memory (grounding caught three wrong CR citations in the combat plan this session).
- Use my regrade layers misses as the seed validation set: **rg3868, rg807, rg811, rg633** — read their questions/gold.
- **Scope the deterministic sub-computation carefully — this is the hard part and the whole question.** Layers (CR 613) is a 7-layer + sublayer + dependency + timestamp system, not arithmetic like cost/combat. Prove there's a *bounded, deterministic* computation the tool can own; if there genuinely isn't, say so — that reopens the slot rather than forcing a tool-shaped answer onto a non-tool-shaped problem.
- Account for the **loop-gating trap**: the tools-off terminal round (commit 1dfe6d4) is keyed to `use_cost_tool` (`answer.py` ~1452/1475/1507); a layers trigger must broaden that gating or it reinherits the cap-exhaustion bug, and `TOOL_ROUND_CAP` likely needs raising.

Combat is shelved — its plan (incl. §11 research) stays in `docs/plan-combat-damage-tool.md` for later.

Heads up: the account **API usage cap is hit until 2026-08-01** (I can raise it sooner) — every live sonnet-5 eval/harness/product-arm run 400s until then. Planning doesn't need it; building/validation will.

## Read this part before you do anything

**USE SUBAGENTS.** Dispatch scoped implementation to Sonnet subagents against the written plan; keep the lead model for judgment, review, and talking to me. Haiku for bulk fetch/filter/verify with compact returns.

- **If your harness tells you not to use the Agent tool, say so immediately and ask me.** Don't silently absorb the work inline.
- Parallelise only across **disjoint file sets**; forbid `git add -A` / `git add .` in every agent prompt — the real hazard with concurrent agents is staging collisions.
- **A subagent running a long (~15 min) live harness must POLL its log in-turn until done — not background it and return a "standing by" placeholder.** That bit us repeatedly this session; be explicit in the prompt.
- **Worktree agents MUST set `PYTHONPATH=<worktree>\src`** or they silently test the ORIGINAL repo's code. `data/raw/` and `evals/answers/` are gitignored (absent in worktrees) — run on master when the CR corpus / vector store / eval data are needed.
- Demand **evidence, not assertions**: real pasted output, real counts. Tell agents to STOP and report if the spec is wrong. Many did this session and were right.
- Don't read subagent transcript files — wait for the completion notification. (Reading a harness's own *log* on disk is fine.)

Respect the "HOW JON WORKS" section of the handoff exactly — especially:

- **Rule 0: plan before code.** Nothing gets built until I've reviewed the plan and ruled. A bug-fix on approved code uses systematic-debugging; a NEW tool needs a plan and a ruling.
- **The judge instrument is FROZEN** (judge_bakeoff prompt + gpt-5-mini). Never reword it.
- **Grading verdicts are mine alone; reading failures is not delegated** — the lead reads the garbled/failed outputs itself. Tools route and rank; they never assign a verdict. (Exception on record: RulesGuru gold is canonical because its authors are certified judges — see DECISIONS.md.)
- **Never assert an MTG or model fact from memory** — ground in the repo CR (`data/raw/MagicCompRules 20260619.txt`), Scryfall via `rulesagent.tools.scryfall.get_card`, or a live check. Model pricing via the claude-api skill. (This session, grounding caught three wrong CR citations in the combat plan.)
- **Billing:** batch Claude-labour as in-session subagents on my subscription. API spend is for product/eval arms only — and is currently capped (above).
- **Verify your own writes.** `str.replace()` no-ops silently on a missed anchor — re-read and assert. Heredoc for commit messages. **Never pipe a long run through `| tail`** (masks the exit code) — use `PYTHONUNBUFFERED=1` + a log file. **A single favourable run is not a rate** — aggregate before claiming reliability.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. I run the app on port 8000 — never bind or kill it. Commit per slice on master with the `Co-Authored-By: Claude Opus 4.8` trailer.

Waiting on me, not you: the **held Scryfall merge** (complete on its branch — but the `answer.py` conflict is now THREE-way after this session's reliability fix; keep all three), and the **lever decisions** (v5 go/no-go, L2 generator, rewriter-on-the-retrieval-side). See the handoff's HELD / STILL QUEUED blocks.

Start by confirming you've read the handoff, then give me your plan for the layer-system tool — grounded in CR 613 and my regrade layers misses, and honest about whether layer resolution is genuinely tool-shaped. Don't build until I rule.
