**STATUS: COMPLETE.** Judge-compare batch (36 condition-runs x 50 questions,
gpt-5-mini judge) finished; `evals/judge_v3ab_summary.json`,
`evals/groundedness_v3ab.json`, `evals/retrieval_noise_tags.json`,
`evals/v3ab_report_data.json`, and `evals/v3ab_stable_flip_index.json` are
all final. Jon's grading queue is built
(`data/parsed/grading_v3ab_queue.html`). Everything below the go/no-go
line in §6 that depends on the *direction* of a stable flip (wrong->correct
vs correct->wrong) is explicitly marked PENDING JON -- the judge only
routes ("this changed"), it never grades ("this is now right/wrong").

# Prompt-v3 A/B -- Judge-compare, stable-flip, tripwire report (Task 3)

Source: `docs/plan-prompt-tuning.md` §4 items 5-7 + §3 detection column;
`.superpowers/sdd/task-3-brief.md`. Inputs: Task 1's prompt-v3/rewrite-v2
code, Task 2's 36 condition-run answer files (`evals/answers/`), and the
condition-A verdicts already on file (`evals/verdicts_*_final.json` +
`evals/verdicts_deepseek-v3-2.json`).

Scripts (new, this task): `evals/lib_v3ab.py` (shared loader),
`evals/retrieval_noise_v3ab.py`, `evals/groundedness_v3ab.py`,
`evals/judge_v3ab.py`, `evals/build_v3ab_queue.py`,
`evals/compute_v3ab_report_data.py`.

---

## 0. Retrieval-noise caveat (read this first)

Retrieval embedding is nondeterministic (Task 2 measured 30-34% run-to-run
draw variance before its prompt-cache fix). Condition A's prompts were
never captured, so **A's retrieval draw relative to B/C/D is unknowable** --
every A-vs-B/C/D comparison below carries this unquantifiable variance for
any question whose retrieval draw could plausibly differ.

What IS knowable: `evals/retrieval_noise_v3ab.py` diffs the RULES-context
portion of the captured `_prompts_B/C/D.json` user prompts (card-ruling
selection is a separate, expected-to-differ axis -- Part B's union in D is
designed to change it). Classification, all 50 questions:

| Tag | Count | Meaning |
|---|---:|---|
| `identical` | 0 | rules ids match across B, C, and D |
| `expected_rewriter_diff` | 45 | C == D (same rewriter v2); B differs -- explained by the v1->v2 rewriter change (§2a/§2b) |
| `retrieval_noise_suspect` | 5 | C != D on the rules section, even though C and D share rewriter v2 and differ ONLY in `ruling_query_mode` (which by design only touches ruling selection) -- no intended-change explanation, so this reads as embedding draw noise between captures |

**`retrieval_noise_suspect` questions: c002, c007, c011, q009, q028.** Every
flip touching one of these five ids is tagged "retrieval-noise suspect" in
the scorecard and queue below -- worth a second look before attributing the
change to a prompt-wording effect. Notably, **c002 is one of §1's
highest-confidence predicted flips** (three arms), so its landed/not-landed
read in §4 should be weighed with this tag in mind.

Notably 0 questions were fully `identical` across all three captures -- the
v1->v2 rewriter change measurably touched retrieval on every single
question (expected, since it changes the search query text), consistent
with Task 2's 30-34% baseline draw-variance finding rather than
contradicting it.

---

## 1. Judge-compare method

Reused `judge_arm_pairs.py`'s `call_judge()` / `decide_transfer()`
**unchanged** (imported directly, not reimplemented), which itself wraps
`judge_bakeoff.or_judge()` -- the bake-off-validated gpt-5-mini judge
protocol (95% agreement with sonnet) -- verbatim. The only thing this task
changes is the REFERENCE side: instead of the original bake-off's
"every arm vs deepseek-v3.2," here it's "every arm's B/C/D answer vs that
SAME arm's condition-A answer," because the question is "did prompt-v3
change this arm's answer," not "does this arm agree with a reference arm."

- `judge = "same"` -> the candidate answer says the same thing as A's answer
  for that question -> condition-A's verdict **transfers** (correct AND
  wrong both transfer -- the judge routes, it never grades, same semantics
  `judge_arm_pairs.py` already uses).
- `judge = "different"` -> a candidate flip, routed to Jon's queue. This
  does **not** mean wrong -- it only means the content diverged from A;
  Jon still assigns the actual verdict.
- `judge` = error/unparsed after retries -> excluded from both buckets,
  logged as `judge_error`, never silently counted either way.

36 condition-runs x 50 questions, minus the known gemini-flash-lite/D/c003
provider exception (both runs) = up to 1,798 judge calls. Per-condition-run
output: `evals/judge_pairs_v3ab_<arm>_<cond>_r<run>.json` (36 files, same
row shape `judge_arm_pairs.py` already produces). **Actual: 1,798 judge
calls completed in 1,471s (~24.5 min), 0 `judge_error` and 0 unexplained
`exception` rows anywhere** (per `evals/_judge_v3ab_run.log`) -- the only
`exception` in the summary is the known gemini-flash-lite/D/c003 provider
failure (§8), tagged and skipped exactly as designed.

## 2. Stable-flip rule

A question counts as a **stable flip** for an (arm, condition) only if
**both** r1 and r2 independently judge "different" against condition A.
If only one run diverges, it's an **unstable flip** -- generation
variance, not a reliable signal -- logged separately and excluded from
Jon's queue and from the go/no-go arithmetic (task-3 brief item 2;
`docs/plan-prompt-tuning.md` §4.5). Per-arm-condition rollup:
`evals/judge_v3ab_summary.json`.

**c004 is off the board for `sonnet` and `deepseek-v4-pro`** -- Jon's
pre-A/B ruling (2026-07-22, `DECISIONS.md`) already flipped both to
correct-with-note, so a c004 stable flip on either of those two arms is
excluded from the scorecard/queue/arithmetic below; it stays live for the
other four arms. (In the actual data, c004 shows up only as an *unstable*
flip for `deepseek-v4-pro`/D and never as a stable flip for either
off-board arm, so the exclusion never actually had to drop a row -- noted
for completeness.)

## 3. Groundedness tripwire (§3 row 1c)

For every B/C/D `answered:true` answer, every citation that's a rule
number or a "... ruling #N" label was checked against that question's
provided-context bracket set, parsed straight from `_prompts_<cond>.json`'s
user text (`evals/groundedness_v3ab.py`). Bare card-name citations (e.g.
gpt-5-mini frequently cites `"Counterspell"` directly, legitimate under the
new §1e card-text-overrides bullet -- "name the specific text" -- since the
card IS in the Card data block) are tracked separately as
`other_citations` and excluded from the count; they aren't a rule-number
claim and would otherwise flood the check with noise unrelated to the
actual F4/§1c risk this tripwire targets (a model stating a plausible-
sounding rule number that wasn't actually retrieved for this question).

**Condition A's prompts were never captured** (Task 2/3 brief), so this
exact check cannot be replayed on A -- B/C/D rates only, per the brief's
explicit fallback.

**Result: 5 distinct questions flagged** across all 6 arms x 3 conditions
x 2 runs (900 answered:true rows checked): `c016, q012, q014, q016, q028`.
7 total instances:

| Arm | Cond | Run | Qid | Ungrounded citation(s) |
|---|---|---|---|---|
| deepseek-v4-pro | D | 1 | q016 | `601.2f-h` |
| gemini-flash-lite | B | 1, 2 | q014 | `702.7`, `702.4` |
| gpt-5-mini | C | 1 | q028 | `601.2` |
| gpt-5-mini | D | 1 | q028 | `601.2` |
| sonnet | B | 1 | q012 | `701.21` |
| sonnet | C | 2 | c016 | `904.6d` |

**Go/no-go read (§4.7):** the criterion is "no-go if > 1-2 distinct
questions flagged across all arms." **5 > 2, so this criterion is
TRIGGERED on a literal reading.** Context for judgment: the rate is low
(7 instances / 900 answered:true rows, <1%) and it is **not concentrated
on the §1c-targeted combat/multiplayer pattern** -- only `q014` (gemini-
flash-lite, combat/priority) matches that specific risk; the other four
(`q012` sonnet, `q016` deepseek-v4-pro, `q028` gpt-5-mini x2, `c016`
sonnet) are scattered across unrelated question types and arms. Because
condition A's rate is unmeasurable (prompts never captured), it's not
possible to say whether this is *new* drift introduced by prompt-v3 or a
pre-existing habit these arms already had -- flagging that limitation
explicitly rather than calling it either a clean pass or a proven
regression. **Recommend Jon's explicit sign-off on this trigger** rather
than auto-treating it as a blocking no-go, given the low rate and weak
correlation with the specific bullet (§1c) the check exists to guard.

## 4. Predicted-flip scorecard

Table source: `docs/plan-prompt-tuning.md` §1/§6, with the c004 pair
excluded per the brief. "Stable divergence detected" is a
necessary-but-not-sufficient signal for "the predicted flip landed" --
confirming the *direction* (e.g. wrong to correct, not just "changed")
requires Jon's grading of the queue. Full detail:
`evals/v3ab_report_data.json` -> `predicted_flip_scorecard`.

**Predicted flips landing as a stable divergence: 6/11 (55%).**

| Bullet | Arm | Qid | A verdict | Prediction | Stable divergence (B/C/D) | Landed? | Note |
|---|---|---|---|---|---|---|---|
| 1a | deepseek-v4-flash | c002 | wrong | flip, high | B yes, C yes, D no | **yes** | retrieval-noise-suspect id |
| 1a | gemini-flash-lite | c002 | wrong | flip, high | B yes, C yes, D yes | **yes** | retrieval-noise-suspect id |
| 1a | deepseek-v3-2 | c002 | wrong | flip, high | unstable only (B,D) | no | retrieval-noise-suspect id |
| 1a | deepseek-v4-pro | c002 | correct | no change | flat (unstable D only) | n/a | as predicted |
| 1a | gpt-5-mini | c002 | correct | no change | stable D yes (unexpected) | n/a | **unexpected stable divergence on a "no change" arm** -- retrieval-noise-suspect id, worth a look in the queue |
| 1a | sonnet | c002 | correct | no change | flat | n/a | as predicted |
| 1b | gemini-flash-lite | c014 | wrong | flip, high | B yes (C,D unstable) | **yes** | |
| 1b | gpt-5-mini | c014 | partial | flip, moderate | B yes, C yes (D unstable) | **yes** | |
| 1b | deepseek-v3-2 | c014 | partial | flip, moderate | B yes, C yes, D yes | **yes** | |
| 1b | sonnet | c014 | partial | untested at plan time | flat | -- | no divergence; consistent with no-go-1 clear |
| 1b | deepseek-v4-flash | c014 | partial | untested at plan time | B yes, C yes, D yes | -- | same c014 pattern as v3-2/gpt-5-mini even though untested at plan time |
| 1c | deepseek-v4-pro | q014 | partial | flip, moderate | flat | no | |
| 1c | gemini-flash-lite | q014 | partial | flip, moderate | B yes, C yes, D yes | **yes** | |
| 1c | gpt-5-mini | q014 | partial | flip, moderate | unstable D only | no | |
| 1d | sonnet | c004 | correct | off the board | flat | n/a | excluded per ruling |
| 1d | deepseek-v4-pro | c004 | correct | off the board | unstable D only | n/a | excluded per ruling |
| 1d | deepseek-v3-2 | c004 | wrong | flip, low confidence | flat | no | lowest-confidence prediction; didn't land |
| 1e | deepseek-v4-flash | c016 | wrong | flip, high | unstable B only | no | **the plan's highest-confidence single-arm prediction ("exact match to Jon's note") did not reach stable** |
| 1f | deepseek-v4-flash | q026 | correct | quality only | B yes (D unstable) | n/a | already correct; stable divergence anyway -- read-back candidate for wording quality, not a correctness risk |
| 1f | gpt-5-mini | q026 | correct | quality only | flat | n/a | as predicted (Jon's exemplar stays put) |
| 1f | deepseek-v3-2 | q008 | wrong | quality only, low conf. | flat | n/a | didn't move |

Two points worth flagging to Jon explicitly:

1. **1e's c016/deepseek-v4-flash prediction was the plan's single most
   confident call** ("wrong -> correct, exact match to Jon's note") and it
   only reached *unstable* (one run flipped, one didn't) -- worth a look
   at both runs' actual text in the queue before concluding the bullet
   under-delivered; generation variance on this one question could be
   masking a real effect.
2. **gpt-5-mini/c002/D** diverged (stably) despite being predicted flat
   ("already correct pre-v3") -- and c002 is a `retrieval_noise_suspect`
   id, so this is plausibly retrieval draw noise rather than a prompt
   effect, but it's an unexplained stable divergence on a "no change
   expected" cell and belongs in the queue read-back.

## 5. Per-arm correct-counts vs baselines

**Confirmed counts require Jon's grading of the stable-flip queue** -- a
"different" judge verdict doesn't reveal the new verdict, only that
something changed. What's computable now is the **floor** (worst case:
every stable flip that touched a previously-correct question grades away
from correct) and **ceiling** (best case: every stable flip that touched a
non-correct question grades to correct), per condition, against the
post-c004-ruling baseline:

| Arm | Baseline | Cond B (floor-ceiling) | Cond C (floor-ceiling) | Cond D (floor-ceiling) | Stable flips (B/C/D) |
|---|---:|---:|---:|---:|---:|
| sonnet | 46/50 | 46-46 | 46-46 | 46-46 | 0 / 0 / 0 |
| deepseek-v4-pro | 44/50 | 43-45 | 44-44 | 44-44 | 2 / 0 / 0 |
| deepseek-v3-2 | 43/50 | 40-44 | 39-45 | 40-44 | 4 / 6 / 4 |
| deepseek-v4-flash | 42/50 | 40-44 | 40-44 | 41-43 | 4 / 4 / 2 |
| gpt-5-mini | 42/50 | 41-45 | 41-46 | 40-44 | 4 / 5 / 4 |
| gemini-flash-lite | 38/50 | 30-42 | 32-42 | 33-44 | 12 / 10 / 11 |

Reading this table: **sonnet has zero stable flips in every condition** --
its 46/50 baseline cannot move on stable-flip grounds alone (§6 no-go-1 is
therefore trivially clear, not just narrowly clear). `gemini-flash-lite`
has by far the widest floor-ceiling spread (12-point swing in condition B)
-- consistent with the predicted-outcome table's call that it's "the
weakest at holding multi-instruction prompts together" and carries the
most variance of any arm. `deepseek-v4-pro` is the tightest non-incumbent
arm (0 stable flips in C and D).

## 6. Go/no-go arithmetic (§4.7)

- **No-go 1 (sonnet regression):** *"no-go if sonnet drops net correct vs
  46/50 baseline on stable flips (c004 off the board)."* **CLEAR.** Sonnet
  has 0 stable flips in B, C, or D (only 2-3 unstable per condition, which
  are excluded from this arithmetic by rule). There is nothing here that
  could move sonnet's count even in the worst case.

- **No-go 2 (groundedness spike):** *"no-go if > 1-2 distinct questions
  flagged across all arms."* **TRIGGERED on a literal reading** (5 > 2;
  §3 detail above). Rate is low (<1% of answered rows) and scattered
  across arms/question-types rather than concentrated on the §1c
  combat/multiplayer risk pattern the check targets -- **recommend Jon's
  explicit sign-off rather than auto-blocking** on this trigger.

- **Go (net increase + predicted flips):** *">=3 of 5 non-incumbent arms
  net +1 correct, AND >=half of predicted flips land."* **PENDING JON.**
  All 5 non-incumbent arms have a nonzero *ceiling* (best case,
  unconfirmed): deepseek-v3-2 +1 to +2 net, deepseek-v4-pro +0 to +1,
  deepseek-v4-flash +0 to +2, gpt-5-mini +0 to +4, gemini-flash-lite -4 to
  +6 (widest variance) -- but ceiling-only tells us the upside is
  *possible* per arm, not that any arm actually nets +1. The
  predicted-flip half of this criterion reads 6/11 (55%) landing as a
  stable divergence, clearing the "half" bar **on the loosest possible
  reading** (divergence detected, not confirmed direction) -- Jon's
  grading of the 72-triple queue is required before this criterion can be
  called either way.

- **Conditional go (qualitative wins, flat counts):** *"flat counts but
  q026-style / 1c-1d-style honest-scoping wins."* q026 (§1f target)
  diverged stably for `deepseek-v4-flash` (already correct -> stable
  divergence, likely a wording/clarity change rather than a correctness
  change) and stayed flat for `gpt-5-mini` (already Jon's exemplar, as
  predicted). The 1c/1d honest-scoping questions (q014, c004) are the
  same rows already tallied in §4's scorecard, not a separate signal --
  their qualitative-win read-back is part of the same queue pass.

**Overall read:** nothing here is a hard-blocking regression -- no-go-1 is
clean and structurally cannot move (sonnet's stable-flip count is zero
everywhere). No-go-2 is technically triggered by the letter of the rule
but weak by rate and correlation; it's a judgment call, not an automatic
kill. The "go" criterion's correct-count half genuinely cannot be
evaluated without Jon grading the stable-flip queue -- this report
supplies the arithmetic and the floor/ceiling bounds, not the final
verdict. **Recommendation: this is Jon's call to make from the queue,**
with the note that the downside risk (sonnet) is already ruled out and
the only live blocking question is whether the groundedness trigger and
the queue's actual grades clear the "go" bar.

## 7. Unstable-flip list

Excluded from Jon's queue and from all arithmetic above by rule (§2) --
listed here for visibility only, in case a pattern across conditions is
worth a second look later (not actionable now):

| Arm | Cond | Unstable-flip ids |
|---|---|---|
| deepseek-v3-2 | B | c002, c011, c012, c019, q017 |
| deepseek-v3-2 | C | c015, c018, q011 |
| deepseek-v3-2 | D | c002, c005, c011, c012, q014, q017 |
| deepseek-v4-pro | B | c011, c017, q011 |
| deepseek-v4-pro | C | c017, q008, q017 |
| deepseek-v4-pro | D | c002, c004, c012, c014, c015, c016, c017, q011, q016, q018, q022, q026, q029 |
| deepseek-v4-flash | B | c012, c016, q025, q030 |
| deepseek-v4-flash | C | c011, c013, c015, q008, q022, q031 |
| deepseek-v4-flash | D | c010, c011, c015, c019, q013, q024, q026 |
| gemini-flash-lite | B | (none) |
| gemini-flash-lite | C | c004, c009, c014, q024, q030 |
| gemini-flash-lite | D | c004, c006, c014, q017 |
| gpt-5-mini | B | c002, c015, q025 |
| gpt-5-mini | C | c002, q008, q022 |
| gpt-5-mini | D | c014, c015, q008, q014, q017 |
| sonnet | B | c011, q020, q021 |
| sonnet | C | q002, q011, q020 |
| sonnet | D | c015, q022 |

Notable outlier: **deepseek-v4-pro/D has 13 unstable flips** (vs. 0 stable
flips in that same cell) -- the widest instability-to-stability ratio in
the whole matrix. Since D adds the Part B ruling-query union on top of C,
and C had only 3 unstable/0 stable for this same arm, this reads as the
union introducing generation variance for this arm specifically rather
than a wording effect -- worth a caveat if D (Part B union) is evaluated
for ship-readiness independent of the rest of prompt-v3.

## 8. Known exception

`gemini-flash-lite`, condition D, question `c003`, both runs: persistent
provider-side truncation (`parse: Unterminated string starting at: line 2
column 11`), already documented in Task 2's report as unresolved after 5+
retries across both files. Carried through this pipeline as an explicit
`exception` tag (`known_provider_error`) at every stage -- never judged,
never counted as a silent wrong answer, never crashes `judge_v3ab.py` or
the tripwire check (both skip exception rows explicitly). No other
`exception` or `judge_error` rows appeared anywhere in the 1,798-call
batch (§1).

## 9. Judge-run cost (rough estimate)

`or_judge()`/`call_judge()` don't return token usage (frozen, not
modified for this task), so this is a rough token-count estimate, not a
measured dollar figure. Sampled 300 real (question, condition-A answer,
candidate answer) triples: average ~2,683 characters combined -> ~811
input tokens/call including the judge system prompt. At up to ~1,798
calls (36 x 50, minus the 2 known-exception rows that skip judging) and
gpt-5-mini's ~$0.25/M input rate: **~$0.36 in input cost**. Output is a
single word by instruction, but gpt-5-mini is a reasoning model with no
visibility into hidden reasoning-token spend here; bounding it between a
bare one-word reply (~20 tokens) and a generously reasoning-heavy reply
(~200 tokens) at ~$2/M output gives **~$0.07-$0.72**. **Total rough
estimate: ~$0.4-$1.1** for the full judge-compare batch -- cheap
regardless of where in that range the true figure lands. Wall-clock:
1,471s (~24.5 min) for the full 36-condition-run batch at ~10-way
concurrency, per `evals/_judge_v3ab_run.log`.

## 10. Self-review

- **Scope check against the brief:** all four numbered items in
  `.superpowers/sdd/task-3-brief.md` are addressed -- stable-flip
  intersection (§2, §5, §7), Jon's grading queue
  (`data/parsed/grading_v3ab_queue.html`, 72 stable-flip triples, 144
  rows), groundedness tripwire (§3), and the summary report with
  correct-counts/scorecard/go-no-go/tripwire/unstable-list (§4-§7).
- **Frozen artifacts respected:** nothing in this task edited
  `judge_arm_pairs.py`, `judge_bakeoff.py`, or any `verdicts_*.json` --
  confirmed by re-reading `evals/judge_v3ab.py`'s import (`call_judge`/
  `decide_transfer` imported unchanged) and by never writing to a
  `verdicts_*` path anywhere in this task's scripts.
- **c004 exclusion actually verified, not just asserted:** checked
  directly against `judge_v3ab_summary.json` that c004 never appears in
  `stable_flip` for `sonnet` or `deepseek-v4-pro` in any condition (it
  only shows up once, as an *unstable* flip for `deepseek-v4-pro`/D) --
  the exclusion rule in `build_v3ab_queue.py` and
  `compute_v3ab_report_data.py` had nothing to actually drop, which is
  worth stating plainly rather than leaving it implied.
- **Known limitation carried through honestly:** condition A's prompts
  were never captured, so the groundedness tripwire and the
  retrieval-noise diff are both B/C/D-only measurements -- flagged in
  §0, §3, and repeated here rather than buried in one place.
- **What this report does NOT claim:** it does not assert a final
  correct-count per arm/condition (floor-ceiling bounds only, §5), and it
  does not make the go/no-go call (§6) -- both require Jon's grading of
  `data/parsed/grading_v3ab_queue.html`'s 72 stable-flip triples
  (144 rows, two per triple). That grading pass is the one remaining
  step before this A/B can be closed out.
- **Residual risk:** the 1e/c016/deepseek-v4-flash miss (§4) and the
  deepseek-v4-pro/D instability spike (§7) are the two findings most
  worth a second look in the queue before Jon forms his overall read --
  both are called out explicitly above rather than left for him to
  notice unprompted.