# Handoff — the session that measured the number, and found the last conclusion was wrong

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-27 overnight session. The previous handoff's headline was "one channel
carries the system and the CR-rules layer is ~inert." The first half held. The
second half was wrong, and this session proved it for $3.49.**

Suite: **1039 passed** (was 1124 — 85 tests left with the layers engine, see
below). Spend this session: **~$49.25 Anthropic** of $100, **~$13 OpenRouter** of
$45. Everything below is committed.

---

## ⚠️ FIRST, UNLEARN THIS

**1. CR-rule retrieval is NOT inert. It is load-bearing.** On 86 card-free rules
questions, replacing the retrieved rules with rules retrieved for a different
question collapses accuracy from **98.84% to 15.12%** — 83.7 points. The prior
"-3.3 points, p=0.50, ~inert" result was measured on a corpus that is 99.4%
card-interaction questions. **Restate it as "rules are redundant GIVEN card
text."** Remove the cards and the rules become the entire answer.
`docs/results-rules86-placebo.md`.

**2. The collapse is REFUSAL, not error, and that is the better finding.** Given
wrong rules the system declined to answer on **78 of 86 rows (90.7%)** and said
why: *"I can't answer this from the rules provided. The context here contains no
phasing rules at all."* It confabulated on **3 of 86 (3.5%)**, and one of those
three looks like a judge false positive. Under deliberately corrupted retrieval
this system refuses rather than guesses — a measured safety property.

**3. The accuracy metric conflates "refused" with "wrong."** That made the placebo
arm look ~6x worse than it behaved. `answered` is already recorded per row, so
three-way verdicts (correct / incorrect / **declined**) cost nothing to add. **Do
this before the next eval.**

**4. There is now a real headline number: 85.88% on all 1,409 questions**, 95% CI
[83.96%, 87.60%], on the shipped pipeline. Every prior figure was a projection from
311 rows. It beat the 82.8% projection by 3.1 points, because this run reproduces
production's v2 rewrite while the projection's source arms did not.
`docs/results-headline-accuracy.md`.

**5. Never quote 85.88% as three significant figures.** Sampling is ±1.8pp and
judge instability adds ~2-4pp on top. Honest phrasing: **"roughly 86%, ±2pp
sampling and a further ~4pp of instrument variance."**

**6. The judge is now characterised on both sides, and the bias is signed.** False
positives 4.4% (CI to 10.9%); false negatives **0/77, CI [0%, 4.7%]** — including a
census of *all 53* hard-level passed rows. Point estimates say the headline is more
likely an **understatement** than an overstatement.

**7. Jon's judge-panel idea lost and was not adopted.** Panel-vs-human agreement
40% (10/25) against gpt-5-mini's 72%. It is retained only for what it uniquely
does: flagging `REFERENCE_WRONG` (11 of 25 rows, 4 corroborated by Jon's own prior
notes). gpt-5-mini majority-of-3 is the scoring instrument.

**8. The layers tool is gone**, and with it `layer_resolver.py` plus its 76-test
suite — 2,242 lines. It measured exactly zero as a model-facing tool. Recoverable
from git if a deterministic layers checker is ever wanted for another purpose.

**9. The cards/deck-tool work has left this repo.** It is now **Tutormancer** at
`D:\Job_hunt\tutormancer` (Jon's name; "tutor" = search your library and fetch the
card you need). Rulemancer is rules-only from here.

---

## WHAT SHIPPED

**Headline accuracy** (`2543454`) — 1,409 rows, batched, $43.61. Config verified as
*stamped* on every row, not as intended: opus-5 / low / v2 / raw / system_version 3
/ batch / one prompts-cache sha. Per level: 96.1% (L0) → 90.3% (L1) → 84.2% (L2) →
67.9% (L3), Corner Case 71.0%. Refusals only 0.71%; 98.1% of answers cite a CR
rule.

**The rules reversal** (`f515246`) — see above.

**86-row card-free eval set** (`b290fc5`) — `evals/questions_rules86.jsonl`. 31
existing + 55 of 56 drafted overnight. Validated by three blind adversarial
reviewers grading against a questions-only file (blindness enforced by
construction, not instruction). **All four reviewer flags turned out to be reviewer
error, not draft error** — including one where CR 800.4d's own Astral Slide example
uses the exact split the draft drew ("triggers, but it isn't put on the stack").
Dropped `q148` (no CR rule settles it). Gold completeness fixes on q109/q110/q152/
q155.

**Judge characterisation** (`5ac2bd4`) — `--votes N` majority judging on both judge
scripts (default 1, unchanged). Every vote recorded, not just the winner.
Instability measured *where verdicts are contestable*: h2h hard moved 75.9% →
72.2% between single-pass and majority-of-3. Flips happen at temperature 0, so they
are provider-side nondeterminism.

**Dashboard integrity** (`db46306`) — the headline was being displayed as `oracle`
(an upper bound) because frozen-prompt runs never stamped `retrieved_rule_ids`.
Backfilled from the prompts themselves (19.29 ids/row mean), so it now reads
`pipeline`. Also: `level: "rules"` added to the weight vectors, and a general
content-match tiebreak for verdict→answers joins when two arms share an id set
(fixed 4 arms, moved no accuracy).

**Layers removal** (`f357c4a`), **Tutormancer split** (`cdef3b7`).

**Failure taxonomy** (`docs/results-failure-taxonomy.md`) — 7.4% base failure over
311 rows; level 3 at 42.9%, ~6x base. Corroborated independently by the headline
run's level gradient.

---

## RUNNING WHEN THIS SESSION ENDED

**The fair cross-model comparison — gpt-5-mini on byte-identical prompts.** This is
the comparison the project has never had: every historical cross-model number is
confounded (different retrieval configs, or a different question set, and in one
case gpt-5-mini judging its own family — `report_h2h.py:15-19` admits it).

- 16 parallel shards, `evals/answers/gpt5mini_sh0..15.json`, round-robin id
  assignment so each shard spans all difficulty levels.
- Why sharded: `run_openrouter_arm.py` is fully serial — 158 rows took 2h17m
  (~52s/row). 16 shards brings it to about an hour. It has `--qids`, which is what
  makes sharding possible.
- 161 rows already exist in `evals/answers/gpt5mini_fair_1409.json` from the serial
  attempt; the shards cover only the remaining 1,248.
- **To finish:** merge the 16 shard files plus the 161-row partial into one
  1,409-row answers file, then judge with
  `evals/judge_norules_control.py --answers <merged> --questions
  evals/rulesguru_full_v2.jsonl --votes 3`. Compare against 85.88%.
- Cost so far ~$1.31 + ~$8 projected. OpenRouter, not Anthropic.
- **Gotchas already hit:** `--ruling-query raw` switches the script into a
  diagnostic report mode instead of generating; the default `--cards` set appends
  20 rows the prompt cache does not contain (pass an empty cards file); and the
  output-path guard refuses to mix a run that used a prompts cache with one that
  did not.

---

## NEXT, IN ORDER

1. **Finish and judge the gpt-5-mini comparison** (above). Either outcome is
   publishable: a large gap justifies opus, a small gap says the expensive model
   is not earning its cost on this task.
2. **Three-way verdicts** (correct / incorrect / declined). Cheapest high-value fix
   on the board; `answered` is already recorded.
3. **Make the card-free set harder.** At 98.84% the real arm is near-ceiling, so it
   is a sensitive instrument for *damage* and useless for measuring *gains*.
4. **Attack level 3.** 67.9% on 162 rows, corroborated by the taxonomy. The
   qualitative modes are in `docs/results-failure-taxonomy.md`: wrong
   layer/timestamp stacking, "loses abilities" over-generalised to "gets
   sacrificed", trigger-creation timing, restriction-scope misreads.
5. **Human-grade a sample.** Only **32 rows** in this project have ever carried a
   real human verdict, and all 32 came from rows the judge had already failed. The
   judge's false-negative rate rests entirely on same-family grading.
6. **Persist prompts on every arm, always.** The reason no historical cross-model
   comparison can be verified is that prompts were never written to disk. One line
   of discipline makes "same prompt" checkable instead of arguable.
7. **Do NOT re-buy the full corpus run** to measure an improvement. A 3-point gain
   sits inside judge instability. Fix the instrument first.

Still open from before: cosine floor, second-hop retrieval, rerank-after-rewrite,
the 153 empty-gold rows, the 54+1 mis-encoded conjunctions. Note that **gold-quality
work just became more valuable again**, since rules retrieval turned out to matter
after all.

---

## MISTAKES I MADE, so you don't trust them

Four of my own measurements were wrong, all the same shape — **counting over the
wrong population** — and each one changed a number I had already reported:

- **"313 cards strip to empty"** → 35. The first count ran over all 38,336 rows
  including tokens and art-series prints; the index population is 34,280.
- **"Judge stability is 0.48%"** → ~2-4%. Measured on `l0_opuslow` at 97.1%
  accuracy where nothing is contestable, instead of the arms that motivated it.
- **"0% false negatives"** → true but weak: 20 of 30 audited rows were level 0. The
  hard-level census (all 53) is the result worth quoting.
- **"3,597 card refs, zero unresolved"** → 9 unresolved. `lookup_face_name` and
  `fuzzy_lookup` return a **tuple**, so a failed lookup returns `(None, None)`,
  which is truthy — my probe counted every junk token as resolved. The real
  failures are 9 planeswalker loyalty costs (`[+1]`, `[-2]`) that
  `parse_card_refs` over-captures. Corrected in the Tutormancer spec, the roadmap
  text, and Jon's memory.

And **five guards caught five more before they cost anything**: the config-stamp
check refused a pilot built at `rewrite=none/union`; the roadmap test caught the
split-repo collision; the rewrite-warmth assertion prevented a `v2`-stamped cache
holding unrewritten queries; the prompts-cache identity check refused to merge two
experiments into one `--out`; and the `--cards` default would have generated 1,429
rows against a 1,409-row cache.

---

## HOW JON WORKS (load-bearing)

- **Explain things properly.** Define jargon at first use, lead with what a thing
  means, show a concrete example. He is a partner, not an observer.
- **Rule 0: plan before code.** Every `plan-*.md` / `spec-*.md` is design-only
  until he rules.
- **Complete $0 work without asking.** Split local compute (free) from "$0 in
  credits" (free only on a subscription subagent).
- **Anything spending API credits gets an explicit ask** with a ceiling and a pilot
  checkpoint. He has ~$50 Anthropic and ~$32 OpenRouter left.
- **Verify agents' claims against the underlying data before relaying them.** This
  session that caught a reviewer reaching the opposite conclusion from the CR's own
  worked example, and a "1039 passed" that was true when measured and stale by the
  time I checked (a concurrent commit had broken two tests).
- **Subagent deliverables land in the repo, never the scratchpad.**
- **Do not run the full pytest suite while generation is running** — it races
  `evals/answers/_progress/` and produces failures that look real. This bit us
  again tonight.
- **Never assert an MTG or model fact from memory.** Ground in
  `data/raw/MagicCompRules 20260619.txt` or Scryfall. For pricing import
  `rulesagent.pricing`; do not load the claude-api skill.
- **Jon runs the app on port 8000 — never bind or kill it.** Use 8947.
- Python `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`, JSON
  `encoding="utf-8"`. Commit per slice on master with the `Co-Authored-By: Claude
  Opus 5` trailer.
- **Do not stop a turn to "wait" for a background job.** Two agents burned ~200K
  tokens tonight ending their turns to wait. Block inside one turn by polling the
  output artifact — and never poll a log, because PowerShell buffers `*>` until
  exit so a running job's log looks dead.
- **The resume is the point.** This work is job-search evidence. The defensible
  claim is the methodology, not the percentage.

---

## THE LESSON TO CARRY

Previous sessions: *a value that looks like an identity but is really a position*;
*a claim inherited without being checked*; *anything used as ground truth is an
experiment subject*; *an instrument that has never been tested is not a
measurement*; *you cannot know which part of a system does the work until you take
each part away*.

This session: **you cannot know what an ablation means until you run it on more
than one distribution.**

The channel ablation's method was sound and its arithmetic was right. Its
conclusion was still wrong, because an ablation only tells you what a channel
contributes *on the distribution you tested it on*. Rules looked inert on a corpus
where 99.4% of questions carry cards. The fix was not a better statistical test —
it was building an 86-question card-free set so the same method could ask the same
question somewhere the answer could differ. That cost $3.49 and overturned a
finding that had been shaping the roadmap.

The corollary, earned four times tonight: **before believing a number, ask which
population it was computed over.** Every single one of my own errors was a correct
calculation over the wrong rows.
