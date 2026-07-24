# Handoff prompt (paste this into a fresh session)

Updated 2026-07-25. Update the "Where we are" line and the "first ask" whenever
the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It's ~220 lines and it *replaced* the old 449-line one rather than prepending to it — don't go digging through git for superseded blocks, they're superseded on purpose. Then follow its "Read these FIRST" list, which is deliberately short.

Where we are in one line: production is reverted to v3 (v4 was ruled no-go — it changed nothing on sonnet for +1,215 tokens/query), the v5 bullets×injection grid is built with all five gates passing, 227 tests are green, and **the 64-generation run has not been started** — that's the next thing.

## Read this part before you do anything

**USE SUBAGENTS. This is not optional, and it's the thing that went wrong last session.** The previous session did a whole implementation slice inline and burned an enormous amount of context before I told it to delegate. Dispatch scoped implementation to Sonnet subagents against the written plan; keep the lead model for judgment, review, and talking to me. Haiku for bulk fetch/filter/verify with compact returns.

- **If your harness tells you not to use the Agent tool, say so immediately and ask me.** Do not silently absorb the work inline. I'd rather spend one message resolving that than watch the context window fill.
- Parallelise only across **disjoint file sets**, and forbid `git add -A` / `git add .` in every agent prompt — the real hazard with concurrent agents is staging collisions, not logic.
- Demand **evidence, not assertions**: real pasted command output, real counts. Tell agents to STOP and report if the spec is wrong rather than improvising. Three did exactly that last session and all three findings were correct.
- Don't read subagent transcript files — wait for the completion notification.

Respect the "HOW JON WORKS" section of the handoff exactly — especially:

- **Rule 0: plan before code.** Nothing gets built until I've reviewed the plan and ruled.
- **The judge instrument is FROZEN** (judge_bakeoff prompt + gpt-5-mini). Never reword it.
- **Grading verdicts are mine alone.** Tools may route and rank; they never assign a verdict. Same for gold: tools propose, I encode. Eval questions are mine too.
- **Never assert an MTG or model fact from memory** — ground in the repo's own CR (`data/raw/MagicCompRules 20260619.txt`, not a web copy), Scryfall via `rulesagent.tools.scryfall.get_card`, or a live check. Model pricing always via the claude-api skill. This caught a real error last session: a plan claimed Charging Rhino has trample. It doesn't.
- **Billing rule:** batch Claude-labor (grading, calibration, analysis) runs as in-session subagents on my subscription, never scripted Anthropic API calls. API spend is for the product/eval arms only.
- **Any prompt-only A/B must use the SYSTEM-swap on a frozen capture** — retrieval embedding is nondeterministic at ~30-34% chunk drift, and this removes it entirely rather than controlling for it. `evals/build_prompts_variant.py` already does this for the four grid cells.
- **Verify your own writes.** `str.replace()` no-ops silently on a missed anchor — last session a plan edit got committed with a message describing work that never happened. Re-read the file and assert the content landed. Use a heredoc for commit messages; backticks in a double-quoted `-m` trigger command substitution and silently eat text.
- **Never pipe a long-running python run through `| tail`** — it block-buffers stdout and masks the exit code behind tail's 0. Use `PYTHONUNBUFFERED=1` and redirect to a log file.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8` everywhere. I run the app on port 8000 — never bind or kill it. Commit per slice on master.

Start by confirming you've read the handoff, then tell me how you'd kick off the run and watch it (`evals/watch_runs.py` should show a percentage per cell plus a grand total, with STALLED and DEAD detection). Flag anything in the current state that looks wrong before we spend a dollar on generations.
