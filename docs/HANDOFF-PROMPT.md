# Handoff prompt (paste this into a fresh session)

Updated 2026-07-25 (session 6). Update the "first ask" and the counts whenever
the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff
rather than prepending — don't dig through git for superseded blocks. It opens
with three things to unlearn, then "THE ONE THING TO DO FIRST."

## The headline finding, so you don't re-derive it

The eval was measuring the easy half of the problem. All 1,409 RulesGuru rows
are labelled `match: "any"` while 83 of the held-out 150 carry several gold ids,
so a question needing three rules scored a pass on one. Re-labelled with real
structure, at production TOP_K=15: **`any` questions 58.2%, `groups` 10.1%,
`all` 0.0%.** Retrieval is fine at finding one rule and near-useless at getting
two or three distinct ones into the window.

Recall before and after the relabel is **not comparable** — matching the old
rate needs 5-8x the depth. Don't report the drop as a regression.

## The first ask

**Grade the 68-row bucket-A arm and settle the model question.** The run is done
(`evals/answers/opus5_low_norewrite_costbase.json`, opus-5 @ effort low, no
rewriter, $0.0741/question, 0 truncations). An auto-judge run was still in
flight at handoff time → `evals/verdicts_opus5_low_bucketA.json` via
`evals/judge_rulesguru.py`. Check it finished; re-run if not. **Bring Jon the
disagreements to read, not a grade.**

Jon graded the first 10 at **9/10**, against sonnet's 63.0%/66.7% on the same
population at 31% higher cost. If that holds at 68 it's outside the noise floor.

Also check on a subagent that was sharpening over-broad "header" gold →
`evals/gold_proposals_headers.jsonl`. Neither job mutates existing eval files.

## Then, the highest-value work

The **retrieval-diversity experiment**, which Jon asked for: MMR, hybrid
BM25+vector, and multi-query — separately and in every combination (7 arms +
baseline). All retrieval-only, so **zero generation spend**, measured against
`evals/questions_rulesguru150_v2.jsonl`. MMR first: cosine similarity clusters
near-duplicates, which is exactly what starves a groups question.

**Do not just raise TOP_K.** At effort low, input is ~55% of cost.

## Before you believe anything about billing

Claude Code and its subagents run on Jon's **Claude Max subscription**. But
`mtg-rules-bot/.env` holds `ANTHROPIC_API_KEY`, so any Python in this repo that
constructs an Anthropic client bills **API credits**. Mining and analysis are
done BY subagents using their own Read/Grep tools — never by a script that calls
the SDK. `hasExtraUsageEnabled` is on, so heavy use can spill into paid overage.

## Read this before you do anything

USE SUBAGENTS. Opus on the subscription for mining/analysis, Sonnet for scoped
implementation against a written spec. Lead keeps judgment, review, and talking
to Jon.

- If your harness tells you not to use the Agent tool, say so immediately rather
  than absorbing the work inline.
- **Verify agents' claims yourself.** Every batch this session was
  independently re-validated; it's cheap and it's caught real things.
- Tell agents to STOP and report if the spec is wrong.
- Don't read subagent transcript files — wait for the completion notification.
- Parallelise only across disjoint file sets; forbid `git add -A` / `git add .`.

Respect the "HOW JON WORKS" section of the handoff exactly — especially:

- Rule 0: plan before code. A NEW tool needs a spec and a ruling.
- The judge instrument is FROZEN (judge_bakeoff prompt + gpt-5-mini). Never
  reword it.
- Grading verdicts are Jon's alone; reading failures is not delegated. Jon ruled
  that mined *retrieval* gold may be accepted without per-item review (the
  questions carry judge-authored answers, so the model traces rather than
  decides) — that does **not** extend to `answer_gold`.
- Never assert an MTG or model fact from memory. Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check.
- **Verify by rendering** — screenshot UI in a browser, don't inspect markup.
  Serve over `http.server`; Jon runs the app on port 8000, never bind or kill it.
- Verify your own writes; `str.replace()` no-ops silently on a missed anchor.
  Never pipe a long run through `| tail` (masks the exit code; a trailing `echo`
  does too). A single favourable run is not a rate.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Suite is
  `uv run pytest` (554 passing). Commit per slice on master with the
  `Co-Authored-By: Claude Opus 5` trailer.

## The one lesson to carry forward

Every recurring defect here is the same shape: **a value that looks like an
identity but is really a position.** This session found three more —
`--no-rewrite` vs `--rewrite-version none` (two switches, one behaviour), card
ruling labels being 0-based so `ruling #4` is the fifth ruling, and rule numbers
themselves, which a CR renumber would silently repoint.
`docs/spec-cr-update-check.md` proposes content fingerprinting as the fix, the
same move `ruling_id()` already made.

Related: **check an invariant against reality before asserting it.** A naive
consecutive-subrule-letter check flags 19 healthy rules, because the CR skips
`l` and `o`.

## Waiting on Jon, not you

`docs/spec-cr-update-check.md` (unruled), whether to mine the remaining 1,259
corpus rows (~4.6M subagent tokens), and the legality-gate prompt idea — which
should be **sized first** from the 34 confirmed-wrong misses in
`rulesguru_disagreement_verdicts.json`, and must not land during the model
bakeoff.

## Queued and unblocked

The model bakeoff — deepseek-v4-flash ($0.09/$0.18, native effort, accepts
temperature), gpt-5-mini Flex ($0.125/$1.00), sonnet-5 @ low as the single
anchor (Jon: sonnet only at low), opus-5 @ low. Every prior gpt-5-mini number
was measured with `"reasoning": null`, so its 15-point deficit is untested.

**Grok is excluded on Jon's moral grounds. Do not reintroduce it.**

Start by confirming you've read the handoff, then check the two in-flight jobs
and tell Jon what the 68-row grade says.
