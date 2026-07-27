# Handoff prompt (paste this into a fresh session)

Updated 2026-07-27 (session 12). Update the "first ask" and the counts whenever
the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules bot at
D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff
rather than prepending — don't dig through git for superseded blocks. It opens with
nine things to unlearn, because last session measured the first real corpus-wide
accuracy number AND overturned the previous session's headline conclusion.

## The headline findings, so you don't re-derive them

**There is now a measured accuracy number, not a projection.**
**85.88% on all 1,409 questions**, 95% CI [83.96%, 87.60%], on the shipped pipeline
(opus-5 / low / rewrite v2 / ruling raw / no layers tool). Per level: 96.1% (L0) →
90.3% (L1) → 84.2% (L2) → **67.9% (L3)**, Corner Case 71.0%. Cost $43.61 batched.

**Never quote it to three digits.** Sampling is ±1.8pp and judge instability adds
~2-4pp. Say "roughly 86%, ±2pp sampling plus ~4pp instrument variance."

**CR-rule retrieval is NOT inert — that was a corpus artifact.** On 86 card-free
rules questions, scrambling the retrieved rules collapses accuracy 98.84% → 15.12%
(-83.7 points). The old "-3.3 points, p=0.50" was measured where 99.4% of questions
carry cards. Restate as **"rules are redundant GIVEN card text."**

**The collapse is refusal, not error.** Given wrong rules the system declined on
90.7% of rows and said why; it confabulated on 3.5%. That is a measured safety
property, and it means the accuracy metric conflates "refused" with "wrong."

**The judge is characterised on both sides.** False positives 4.4% (CI to 10.9%),
false negatives 0/77 with CI [0%, 4.7%] including a census of all 53 hard-level
passes. Net: the headline is more likely an understatement.

## The first ask

**Finish the fair gpt-5-mini cross-model comparison.** 16 parallel shards were
generating when the session ended — `evals/answers/gpt5mini_sh0..15.json`, plus 161
rows in `gpt5mini_fair_1409.json` from an earlier serial attempt. Merge all of it
into one 1,409-row answers file and judge it:

```
python evals/judge_norules_control.py --answers <merged> \
  --questions evals/rulesguru_full_v2.jsonl \
  --out evals/verdicts_gpt5mini_fair_votes3.json --votes 3 --workers 8
```

Compare against 85.88%. **This is the comparison the project has never had** —
every historical cross-model number is confounded (different retrieval configs, or
a different question set, and in one case gpt-5-mini judging its own family, which
`report_h2h.py:15-19` admits). This one reads the byte-identical frozen prompt
cache, so the only variable is the model.

Then, in order: three-way verdicts (correct / incorrect / **declined** — `answered`
is already recorded, so this is nearly free); make the card-free set harder (98.84%
is near-ceiling and can't measure gains); attack level 3 at 67.9%; human-grade a
sample, because only 32 rows in this project have ever carried a human verdict and
all 32 came from rows the judge already failed.

**Do NOT re-buy the full corpus run to measure an improvement.** A 3-point gain
sits inside judge instability. Fix the instrument first.

## Before you believe anything about billing

Claude Code and its subagents run on Jon's subscription. But `mtg-rules-bot/.env`
holds `ANTHROPIC_API_KEY`, so any Python here that constructs an Anthropic client
bills **API credits** — a separate pool. Judging bills **OpenRouter**, a third pool.
Remaining after last session: **~$50 Anthropic, ~$32 OpenRouter**. Anything
spending credits gets an explicit ask with a hard ceiling and a pilot checkpoint,
however small. **An arm's cost per question does not transfer to a different kind of
arm** — the production-config run cost 11% more per row than projected because v2
rewrites produce longer prompts.

## Read this before you do anything

**Explain things properly.** Jon: *"you just need to explain things a little better
so I can understand and be a partner here instead of an observer."* Define jargon at
first use, lead with what a thing means, show examples.

- **Rule 0: plan before code.** A new tool needs a spec and a ruling.
- **Complete $0 work without asking** — but split local compute (genuinely free)
  from "$0 in credits" (free only on a subscription subagent).
- **Before believing a number, ask which population it was computed over.** Four of
  last session's own measurements were correct arithmetic over the wrong rows.
- **Verify agents' claims against the underlying data before relaying them.** Last
  session that caught a reviewer contradicting the CR's own worked example, and a
  green test suite that had gone red from a concurrent commit.
- **Subagent deliverables must land in the repo, never the session scratchpad.**
- **Never run the full pytest suite while generation is running** — it races
  `evals/answers/_progress/` and gives false failures.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. For pricing import
  `rulesagent.pricing` — do NOT load the claude-api skill.
- **Verify by rendering** for UI. **Jon runs the app on port 8000 — never bind or
  kill it.** Use 8947 and stop it after.
- **Don't end a turn to "wait" for a background job.** Poll the output artifact
  inside one turn — never the log, because PowerShell buffers `*>` until exit so a
  running job's log looks dead.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Open JSON with
  `encoding="utf-8"`. Suite is `uv run pytest` (**1039 passing** — 85 tests left
  with the deleted layers engine). Commit per slice on master with the
  `Co-Authored-By: Claude Opus 5` trailer.
- **The cards/deck work is gone from this repo.** It is Tutormancer at
  `D:\Job_hunt\tutormancer`. Rulemancer is rules-only.
- **The resume is the point.** This is job-search evidence, and the defensible
  claim is the methodology, not the percentage.

## The one lesson to carry forward

**You cannot know what an ablation means until you run it on more than one
distribution.**

The previous session's method was sound and its arithmetic was right. Its
conclusion was still wrong, because an ablation only tells you what a channel
contributes on the distribution you tested. Rules looked inert on a corpus where
99.4% of questions carry cards. Building an 86-question card-free set let the same
method ask the same question where the answer could differ — and it cost $3.49 to
overturn a finding that had been shaping the roadmap.

Start by confirming you've read the handoff, then open the dashboard
(`evals/metrics_history.html`, rebuild with `python evals/build_metrics_history.py`
— 44 arms, 16 question sets).
