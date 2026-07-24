# Handoff prompt (paste this into a fresh session)

Updated 2026-07-24. Update the "Where we are" line and the "first ask" whenever
the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff rather than prepending — don't dig through git for superseded blocks. It opens with "THE ONE THING TO DO FIRST" and a short strategy section; read those, then the two docs it names (`docs/report-costtool-validation.md` and `docs/plan-combat-damage-tool.md`).

Where we are in one line: the **tool era has begun** — the first agent tool (`calculate_cost`) is shipped and proven on c014/Trinisphere, but validation found a **~21% empty-output reliability defect on the tool-loop path** (vs ~0% baseline), and **fixing that is the first task** before we build the next tools on the same machinery.

## The first ask

**Fix the cost-tool-loop reliability defect.** Use systematic-debugging: reproduce the empty-output / `stop_reason=error` case first (run c014 or the 5 fired qids through `RulesAgent.answer()` repeatedly), find the root cause (prime suspects: the large `calculate_cost` tool-result payload colliding with the final `messages.parse` turn, or the tool round-trip nesting inside the existing 2-attempt retry loop), fix the cause not the symptom, and verify the empty-output rate drops with real repeated runs. Then we continue the tool roadmap (combat-damage tool is planned and next). Details in `docs/report-costtool-validation.md`.

## Read this part before you do anything

**USE SUBAGENTS.** Dispatch scoped implementation to Sonnet subagents against the written plan; keep the lead model for judgment, review, and talking to me. Haiku for bulk fetch/filter/verify with compact returns. Last session ran ~18 agents this way.

- **If your harness tells you not to use the Agent tool, say so immediately and ask me.** Don't silently absorb the work inline.
- Parallelise only across **disjoint file sets**; forbid `git add -A` / `git add .` in every agent prompt — the real hazard with concurrent agents is staging collisions.
- **Worktree agents MUST set `PYTHONPATH=<worktree>\src`** or they silently test the ORIGINAL repo's code and believe it's their own. `data/raw/` and `evals/answers/` are gitignored (absent in worktrees) — seed `data/raw` by hand if an agent needs the CR corpus.
- Demand **evidence, not assertions**: real pasted output, real counts. Tell agents to STOP and report if the spec is wrong. Many did last session and were right.
- Don't read subagent transcript files — wait for the completion notification.

Respect the "HOW JON WORKS" section of the handoff exactly — especially:

- **Rule 0: plan before code.** Nothing gets built until I've reviewed the plan and ruled. (The reliability FIX above is a bug-fix on already-approved code, so systematic-debugging applies, not a fresh Rule-0 plan — but a NEW tool needs a plan.)
- **The judge instrument is FROZEN** (judge_bakeoff prompt + gpt-5-mini). Never reword it.
- **Grading verdicts are mine alone.** Tools route and rank; they never assign a verdict. Gold: tools propose, I encode. Eval questions are mine. (Exception on record: RulesGuru gold is accepted as canonical because its authors are certified judges — see DECISIONS.md.)
- **Never assert an MTG or model fact from memory** — ground in the repo CR (`data/raw/MagicCompRules 20260619.txt`), Scryfall via `rulesagent.tools.scryfall.get_card`, or a live check. Model pricing via the claude-api skill.
- **Billing:** batch Claude-labour as in-session subagents on my subscription, never scripted Anthropic API calls. API spend is for product/eval arms only.
- **Any prompt-only A/B uses the SYSTEM-swap on a frozen capture** (`evals/build_prompts_variant.py`) — retrieval is nondeterministic, this removes it rather than controlling for it.
- **Verify your own writes.** `str.replace()` no-ops silently on a missed anchor — re-read and assert. Heredoc for commit messages (backticks in a double-quoted `-m` eat text). **Never pipe a long run through `| tail`** (masks the exit code) — use `PYTHONUNBUFFERED=1` + a log file. **A single favourable run is not a rate** — aggregate before claiming reliability (this bit us: one clean cost-tool run read as "reliable" before the 21% aggregate showed up).
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. I run the app on port 8000 — never bind or kill it. Commit per slice on master.

Two things waiting on me, not you: my manual regrade of the 42 auto-judge disagreements (I'm partway — when I send you the exported `{id,verdict,note}` JSON, fold it into a corrected accuracy number), and the held Scryfall merge (complete on its branch, a deliberate reconciliation — see the handoff's Scryfall block).

Start by confirming you've read the handoff, then tell me your plan for reproducing and fixing the reliability defect. Flag anything in the current state that looks wrong.
