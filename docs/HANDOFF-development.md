# Handoff — the session that measured the number, and found the last conclusion was wrong

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-27 overnight session. The previous handoff's headline was "one channel
carries the system and the CR-rules layer is ~inert." The first half held. The
second half was wrong, and this session proved it for $3.49.**

Suite: **1039 passed** (was 1124 — 85 tests left with the layers engine, see
below). Spend this session: **~$49.25 Anthropic** of $100, and OpenRouter down to
**~$26 remaining** of $45 (headline judging, the cross-model generation, four judge
families, and the bake-off). Everything below is committed except the bake-off,
which was still generating — see "RUNNING WHEN THIS SESSION ENDED".

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

## THE FAIR CROSS-MODEL COMPARISON — DONE (`739edf6`)

`docs/results-crossmodel-fair.md`. Both models read ONE frozen prompt cache
(sha256 `61bb33929f734b17…`), same 1,409 questions, same judge prompt digest,
3-vote majority. **The only variable is the model.**

| judge | family | opus-5 low | gpt-5-mini | gap | rows |
|---|---|---:|---:|---:|---:|
| gpt-5-mini, full corpus | favours gpt-5-mini | **85.88%** | **70.05%** | **+15.8** | 1409 |
| Claude panel | favours opus | 87.3% | 68.1% | +19.2 | 72 |
| deepseek-v3.2 | neutral | 87.3% | 70.0% | +17.3 | 150 |
| gemini-2.5-flash-lite | neutral | 75.3% | 59.3% | +16.0 | 150 |

**opus won by 15.8 points under gpt-5-mini's OWN family judge on the full corpus** —
the pre-committed strong-evidence case. Four judges across three families land
within 3.4 points of each other on the gap.

**The mechanism is refusals and is judge-independent:** `answered=False` on
157/1409 gpt-5-mini rows (11.1%) vs opus's 10 (0.7%), both read from the model's own
structured-output field. A decline scores incorrect under every judge, which is why
the graders agree.

**Price does not follow list price.** `openai/gpt-5` lists 2.5x cheaper than opus
($1.25/$10 vs $5/$25) and measures **$0.0377/row against opus's $0.031** — more
expensive. Opus ran batched at 50% off, and gpt-5's thinking tokens bill as output.
The genuinely cheap options are an order of magnitude down.

## RUNNING WHEN THIS SESSION ENDED — the cheap-model bake-off

**Three arms on the 150-row stratified subset** (`evals/_crossjudge_subset.json`,
seed 20260727 — the same ids every judge already used, so results slot straight
into the table above).

| arm | model | prompts cache | out |
|---|---|---|---|
| gpt5 | `openai/gpt-5` | production cache | `evals/answers/bakeoff_gpt5_sh0..5.json` |
| deepseek | `deepseek/deepseek-v3.2` | production cache | `evals/answers/bakeoff_deepseek_sh0..5.json` |
| antirefusal | `openai/gpt-5-mini` | **`_prompts_rulesguru_150_antirefusal.json`** | `evals/answers/bakeoff_antirefusal_sh0..5.json` |

18 parallel `--qids` shards (6 per arm). `run_openrouter_arm.py` is serial at
~25-40s/row, so sharding is the only way these finish in minutes rather than hours.
**21 gpt-5 rows already exist** in `bakeoff_gpt5_150.json` + `bakeoff_gpt5_pilot10.json`
from a killed serial run — preserved, and the shards cover only the remainder.

**TO FINISH — do this when the shards are done:**

1. **Merge per arm.** Adapt `evals/merge_gpt5mini_shards.py` (it already does the two
   things that will otherwise bite you: stamps `answer_gold` from the corpus, which
   `run_openrouter_arm.py` never does, and copies `text` → `answer`, because the
   openrouter path writes `text` while the judge reads `answer`). For gpt5, include
   the two pre-existing partial files.
2. **Judge each arm** with `evals/judge_norules_control.py --votes 3`, using
   `openai/gpt-5-mini` (default) and `deepseek/deepseek-v3.2` (via `--judge`) so the
   numbers are comparable to the table above.
3. **Append to `docs/results-crossmodel-fair.md`** — do not rewrite it. Include per
   arm: accuracy + Wilson CI per judge, the `answered=False` rate, and cost/row,
   alongside opus-5 and gpt-5-mini on the same 150 ids.

**THE TWO QUESTIONS THE BAKE-OFF EXISTS TO ANSWER:**

- **Does an anti-refusal instruction help?** Report the refusal rate AND the accuracy
  change *together*. Fewer refusals with no accuracy gain means the model was
  declining for good reason and the instruction merely converted silence into
  confident errors. That outcome looks like an improvement on a dashboard while
  making the product worse — say so plainly if it happens.
  **Arithmetic done in advance:** refusals are ~11% of rows and ~1/3 of
  gpt-5-mini's losses. Even perfect refusal elimination at its own non-refusal
  accuracy recovers ~8-9 points, landing near 78% — still ~8 points behind opus. So
  this cannot make gpt-5-mini competitive on its own.
- **Is anything meaningfully cheaper actually usable?** deepseek was running at
  **$0.001/row against opus's $0.031** — 30x cheaper — and ~10x faster. If its
  accuracy is anywhere near usable that is a real production conversation.

**Note the anti-refusal arm is NOT byte-identical** to the others (its system text
carries the extra instruction), so it cannot join the "only variable is the model"
comparison. It is a single-variable test against gpt-5-mini's own baseline.

**Gotchas already paid for:** `--ruling-query raw` switches `run_openrouter_arm.py`
into a diagnostic report mode instead of generating; the default `--cards` set
appends ~20 rows the prompt cache lacks (pass an empty cards file); and the
output-path guard refuses to mix a run that used a prompts cache with one that did
not. Shard progress lives in `evals/answers/_progress/bakeoff_*.json` with
`n_done`, `errors` and `cost_so_far` — read that, never the logs, because PowerShell
buffers `*>` until exit so a running job's log looks dead.

---

## NEXT, IN ORDER

1. **Finish the bake-off** (merge, judge, append) — see the section above, which
   has the full procedure and the two questions it answers.
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
