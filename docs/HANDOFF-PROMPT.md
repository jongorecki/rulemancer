# Handoff prompt (paste this into a fresh session)

Updated 2026-07-26 (session 11). Update the "first ask" and the counts whenever
the state moves; the rest is stable.

---

We're continuing work on Rulemancer, the MTG rules RAG bot at
D:\Job_hunt\mtg-rules-bot.

First: read docs/HANDOFF-development.md in full. It *replaced* the prior handoff
rather than prepending — don't dig through git for superseded blocks. It opens
with seven things to unlearn, because last session took the pipeline apart one
component at a time and found that most of it does nothing.

## The headline findings, so you don't re-derive them

**One channel carries the system, and it is not the one the roadmap was about.**
Five single-variable arms, 120 rows each, one channel scrambled per arm:

```
card oracle text     -31 pts   p=4.3e-07   <- carries the system
card rulings          -6 pts   p=0.19
CR rules retrieval    -3 pts   p=0.50      <- ~inert
layers tool            0       p=0.73      <- ~inert
reasoning effort       0       (n=15)
```

**Wrong information is catastrophic; missing information is cheap.** Wrong cards
cost 31 points, missing rules cost 3. Card *mis*-resolution is the expensive
failure mode, which is why the @-mention design is an accuracy safeguard, not a
UX convenience.

**Retrieval is GOOD at the question type the corpus barely contains.** 87.5% gold
coverage on card-free rules questions vs 29.4% on card questions. But **99.4% of
the corpus is card-interaction questions**, so "rules don't matter" may really be
"rules are redundant GIVEN card text."

**Batch API works** (1m47s for 2 rows, halves cost, resume attaches instead of
resubmitting). **Prompt caching with batch is net negative — keep it off.**

**The fabrication canary is 0 on every arm.** The bot does not invent citations.

## The first ask

**Build the cards RAG — `docs/spec-cards-rag.md`. That is the next feature, and
it needs Jon's ruling on four open decisions first (end of the spec).**

It is a retrieval problem where retrieval is genuinely necessary: no model has
memorised which of 38,336 cards has a similar effect at two mana less. And its
gold standard is **computable** (functional reprints, strictly-better pairs,
colour-shifted variants derive from Scryfall), so evaluation needs no human
labelling, no LLM judge, and costs $0 — the exact property whose absence caused
every defect in results-adversarial-review.md.

Then, in order: review the overnight expansion queue
(`evals/_rules_expansion_draft.jsonl`) and run real-vs-placebo rules on the full
card-free set (~$2 batched, settles inert-vs-redundant); remove the layers tool
(zero benefit, saves 8.6%/query and 41% of round trips); harden card resolution;
fix the short-chunk retrieval defect.

**Do NOT buy the $73-91 full corpus run.** It measures a corpus that is 99.4% one
question type through a one-directionally harsh judge.

## Before you believe anything about billing

Claude Code and its subagents run on Jon's Claude subscription. But
`mtg-rules-bot/.env` holds `ANTHROPIC_API_KEY`, so any Python in this repo that
constructs an Anthropic client bills **API credits** — a separate pool, and the
subscription upgrade did NOT change that. ~$38 of an $88 balance remains.
Anything spending credits gets an explicit ask with a hard ceiling and a pilot
checkpoint, however small. **An arm's cost per question does not transfer to a
different kind of arm.**

## Read this before you do anything

**Explain things properly.** Jon: *"you just need to explain things a little
better so I can understand and be a partner here instead of an observer."*
Define jargon at first use, lead with what a thing means, show examples.

- **Rule 0: plan before code.** A new tool needs a spec and a ruling.
- **Complete $0 work without asking** — but split local compute (genuinely free)
  from "$0 in credits" (free only on a subscription subagent).
- **Verify agents' claims against the underlying data before relaying them.**
  Last session that caught four agent errors and two of my own wrong numbers.
- **Check whether the rows that moved are the rows the intervention touched.**
  This converted an apparent 6.7-point layers effect into noise in one query.
- **Subagent deliverables must land in the repo, never the session scratchpad.**
- **Never run the full pytest suite while an eval arm is running** — it races
  `evals/answers/_progress/` and gives false failures.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. For pricing import
  `rulesagent.pricing` — do NOT load the claude-api skill.
- **Verify by rendering** for UI. **Jon runs the app on port 8000 — never bind or
  kill it.** Use 8947 and stop it after.
- Python is `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Open JSON with
  `encoding="utf-8"`. Suite is `uv run pytest` (**1124 passing**). Commit per
  slice on master with the `Co-Authored-By: Claude Opus 5` trailer.
- Do not use `nohup ... &` inside a backgrounded call — the child dies with its
  parent shell.

## The one lesson to carry forward

**You cannot know which part of a system is doing the work until you take each
part away, one at a time, and watch what happens.**

Four components had been built, tuned and documented for months. Ablation took a
day and showed one carried the system and three were close to free. None of the
prior reasoning was stupid — it was unfalsifiable, because nothing had ever been
removed to see if it mattered.

Start by confirming you've read the handoff, then open the dashboard
(`evals/metrics_history.html`, rebuild with `python evals/build_metrics_history.py`).
