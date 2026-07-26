# Results — judge error rate, both directions

**Two findings, and the second one is the bigger deal.**

1. **The unmeasured direction looks small.** Of 90 rows the frozen judge PASSED, an independent reference grader found only 4 where the answers materially differ — 4.4% (95% CI 1.7%–10.9%). That grader is demonstrably *stricter* than Jon (finding 2), so treat 4.4% as an **upper bound**: the repo's accuracy numbers are overstated by at most ~4 points from this cause, and probably less.

2. **The reference grader failed validation, and how it failed is the finding.** On the 32 rows Jon has hand-graded, it agreed with the frozen judge **32/32 times** — including all 7 rows Jon overturned as judge errors. It never once said "these answers agree" about a row the judge called `different`. So a stronger model handed the same prompt reproduces the same verdicts on the only rows with ground truth, and **cannot serve as an independent check on this judge's false negatives**. Agreement with Jon: 25/32 = 78.1%, entirely from the rows where Jon and the judge already agreed.

That reopens the question this work started from. `docs/results-gold-audit-batch1.md` reported 5 of arm B's 15 flagged rows as judge false negatives, and that regrade is what lifted arm B from 90.0% to 93.3%. Reading the answer text directly, **3 of those rows state opposite bottom lines** (quoted below). Arm B's 93.3% rests on grading calls that do not survive a second read, and Jon should re-examine them before the number is quoted again.

## What was measured

The judge (`openai/gpt-5-mini`, frozen prompt digest `b54fbdb95565abf8`) returns `same` or `different` per row; `same` counts as correct. It can be wrong in two directions, and until this run only one had been checked:

| Direction | Meaning | Effect on accuracy | Prior evidence |
|---|---|---|---|
| **False negative** | judge said `different`, the answers agree | we UNDERSTATE | 5/15 on arm B (`docs/results-gold-audit-batch1.md`) — now in question |
| **False positive** | judge said `same`, the answers differ | we OVERSTATE | none — never measured before this run |

## Provenance

| | |
|---|---|
| Population | 541 judged rows across 9 arms carrying the frozen judge stamp (435 `same`, 106 `different`) |
| Sampler | `evals/judge_error_prep.py`, seed `20260726`, proportional stratified over (arm × level), largest-remainder allocation |
| Sample | 90 `same` rows + 30 `different` rows + 32 Jon-graded validation rows = 152 graded cells, 152 returned |
| Reference grader | claude-opus-5 (in-session subagents, Claude subscription), blind, given the audited judge's own prompt verbatim (digest `b54fbdb95565abf8` — byte-identical to the judge's, so the only variable changed is the model) |
| Raw verdicts | `evals/judge_error_out/batch_*.jsonl` → `evals/judge_error_results.json` |
| Manifest (never shown to the grader) | `evals/judge_error_manifest.json` |
| Run | 2026-07-26T17:39:50+00:00 |
| API spend | **$0.00**. The Anthropic API path was estimated at $1.03 (160,162 in × $5.00/MTok + 9,120 out × $25.00/MTok, well under the $8 gate) and deliberately not taken — grading ran on subscription subagents, per Jon's standing rule that ancillary Claude-labor never bills the API credits reserved for the product's own eval arms. |

Cells are blind: the grader sees only the question, the reference answer and the candidate answer — never the judge's verdict or reason, the arm, the question id, the level, or Jon's verdict. Validation and sampled rows are shuffled together into 8 mixed batches under opaque `c####` ids, so no batch is identifiable as validation and the `same`/`different` mix cannot be inferred from position.

## Validation — the reference grader vs Jon

Run before anything downstream, on the 32 rows whose answer is already known: the 15 arm-B rows from `docs/results-gold-audit-batch1.md` and the 17 bucket-A rows in `evals/verdicts_opus5_low_bucketA_human.json`. Both are censuses — every row those arms' judge flagged `different`.

| | ref: answers agree | ref: answers differ |
|---|---|---|
| **Jon: judge erred** (answers agree) | 0 | 7 |
| **Jon: judge was right** (answers differ) | 0 | 25 |

**Agreement with Jon: 25/32 = 78.1%** (95% CI 61.2%–89.0%). The frozen judge itself was adopted at a 95% bar; this is well under it.

The shape matters more than the percentage. The whole top-right cell is empty: the reference grader said `different` on every single validation row, so it reproduced the frozen judge exactly. Its measured agreement with Jon is not evidence that it grades like Jon — it is evidence that it grades like the judge, and it only scores as high as it does because Jon agreed with the judge on the other 25 rows.

Translating Jon's verdicts into the judge's question needed care, and the translation is recorded in `evals/judge_error_prep.py`:

- On arm B, `ambiguous` means *either* "the answers do not actually conflict" *or* "the rules do not settle it" — only the first is a judge error, and `final_correct` separates them (rg5863 is ambiguous but not a judge error: an open rules-precedence question).
- On bucket A, Jon overturned 5 rows to `correct` but only **2** are judge errors; the other 3 are **gold** errors (rg4023 and rg6634 contradicted by the Urza's Saga ruling, rg4854 an illegal play the rulings don't state). The answers genuinely differ there — the judge was right and the gold was wrong. Counting those as judge errors would have inflated the FN rate by half.

### The 7 rows in dispute

Jon marked each of these a judge error — the answers agree, the judge was wrong to flag them. The reference grader called all of them `different`. Each row's opening line is quoted verbatim from the verdict file, because on several of them the disagreement is settleable by reading, without needing any rules knowledge:

| Arm | Q | Gold's bottom line | Candidate's bottom line | Jon's note |
|---|---|---|---|---|
| `derivability_B` | rg1718 | 0. Their entire draw step is skipped. Andi will be the starting player in the new game. Because they is the starting player they'll skip their first d... | Direct answer: In a two-player game, Andi draws zero cards during their first turn. In a game with three or more players, Andi draws two cards (their ... | the answers are the same. more out of range errors though. |
| `derivability_B` | rg549 | Any color. Quirion Explorer checks to see what mana Crumbling Vestige could produce if any of its abilities were to resolve at that time. That include... | Quirion Explorer produces no mana. Anderson can still tap it — the ability can be activated and it resolves — but it adds nothing to Anderson's mana p... | answers say the same thing. we have another "cited rule out of range" issue though. |
| `derivability_B` | rg7215 | Tapped. When applying an enters-the-battlefield replacement effect, the game considers the characteristics of the permanent as it would exist on the b... | Minas Tirith enters untapped. | IMPORTANT!!!!!!! they say the same thing. This isn't a disagreement. |
| `derivability_B` | rg811 | It's a 4/4 black Frog with trample and "At the beginning of your upkeep, sacrifice a creature", but no other abilities. Wayward Angel receives a new t... | **Wayward Angel ends up as a face-up, black 4/4 Creature — Frog named Wayward Angel with flying, vigilance, trample, and "At the beginning of your upk... | both answers are saying the same thing. |
| `derivability_B` | rg851 | Lust for War cannot legally enchant anything, so it will be put directly into its owners graveyard. | Lust for War will resolve and enter the battlefield attached to Gilded Sentinel, but it will immediately fall off and go to Amos's graveyard — it neve... | our rulings say basically the same thing, but 303.4i is the operative rule here in that it |
| `opus5_low_bucketA` | rg1900 | It is a 2/2 colorless face-down creature with no abilities. It is face-down because the topmost object is face-down, and this status defines its chara... | The result is a single face-down mutated permanent that is a 2/2 colorless creature with no name, no card types beyond creature, no mana cost, and no ... |  |
| `opus5_low_bucketA` | rg783 | It's a 2/2 artifact creature with no abilities. Applying Titania's Song would cause Bludgeon Brawl to no longer apply (since Soldevi Digger would be a... | Soldevi Digger ends up as a colorless 2/2 artifact creature — Equipment with no abilities at all. | i'm considering this correct even though it says its an equipment with no abilities becaus |

Three of these read as flat contradictions on their face — **rg7215** ("Tapped" vs "enters untapped"), **rg549** ("Any color" vs "produces no mana"), and **rg811** (gold: trample and the upkeep sacrifice "but no other abilities"; candidate: also flying, vigilance and Threshold). A fourth, **rg1718**, matches the gold's `0` in two-player but adds a divergent multiplayer branch the gold does not have. The other three (**rg851**, **rg783**, **rg1900**) are genuine close calls about framing versus substance, and Jon's reading of them is defensible — one of the graders independently flagged rg851 as borderline for the same reason Jon did.

This is surfaced for Jon to adjudicate, not resolved here. But it has a consequence either way: **the 5/15 false-negative finding, and arm B's 93.3%, are not safe to quote until those rows are re-read.**

## False-negative rate (judge said `different`, answers agree)

Two independent standards, bracketing the answer rather than pretending to a point estimate:

- **Jon's standard**, census of 32 flagged rows across arm B and bucket A: 7/32 = 21.9% (95% CI 11.0%-38.8%). Human ground truth, no model involved — but see the disputed rows above.
- **The reference grader's standard**, 30 rows sampled from the 74 flagged rows in the other seven arms: 2/30 = 6.7% (95% CI 1.8%-21.3%).

The two are far enough apart (21.9% vs 6.7%) that the gap is mostly a disagreement about where the "same core ruling" line sits, not sampling noise. The population-weighted figure used in the correction arithmetic below — 11.3% over all 106 flagged rows, census where Jon graded and sample elsewhere — sits between them and inherits both problems.

## False-positive rate (judge said `same`, answers differ)

**4/90 = 4.4% (95% CI 1.7%-10.9%)**, from a stratified sample of 435 passed rows. There is no prior measurement to compare against — this is the first time anyone has looked.

The four are worth reading individually, because none is a wild miss:

| Arm | Q | Level | Why the reference grader split them |
|---|---|---|---|
| `derivability_B` | rg137 | 1 | Reference rules definitively that neither Scarwood Goblin returns; candidate declines to commit and leaves the outcome branching on whether Adriel controls a creature. |
| `h2h_opuslow_hard_r1` | rg1128 | 3 | Reference's subtype list is Vedalken Wizard Saproling Forest, while the candidate additionally gives Realmwright the Island land type from its own ability. |
| `h2h_sonnet_easy_r1` | rg6461 | 1 | Reference requires the legend-rule state-based action first, so Noah may have to bin Thespian's Stage and get no token, while the candidate dismisses the legend rule and rules Marit Lage is created. |
| `opus5_low_bucketA` | rg4238 | Corner Case | Reference keeps the granted 'enchant creature put onto the battlefield with Dance of the Dead' ability so a later leaves-the-battlefield event forces a sacrifice of Viashino Warrior, while the candidate says all Dance of the Dead text is gone and no sacrifice can ever follow. |

| Level | FP / sampled |
|---|---|
| 0 | 0/6 |
| 1 | 2/31 |
| 2 | 0/36 |
| 3 | 1/11 |
| Corner Case | 1/6 |

| Arm | FP / sampled |
|---|---|
| `derivability_B` | 1/28 |
| `h2h_opuslow_easy_r1` | 0/10 |
| `h2h_opuslow_easy_r2` | 0/9 |
| `h2h_opuslow_hard_r1` | 1/8 |
| `h2h_opuslow_hard_r2` | 0/8 |
| `h2h_sonnet_easy_r1` | 1/8 |
| `h2h_sonnet_easy_r2` | 0/8 |
| `opus5_low_bucketA` | 1/11 |

**Why this is an upper bound.** The grader that produced it is the same one that refused to call a single one of Jon's 7 overturned rows an agreement. A grader biased toward `different` will over-report false positives, not under-report them. Under Jon's more lenient reading of "same core ruling", the true FP rate is at or below 4.4%.

## What this does to the headline numbers

Each arm's published accuracy is re-read from its own verdict file at report time (mtimes in the table), then corrected as

```
corrected = [ n_same x (1 - FP)  +  n_different x FN ] / n
```

with FP = 4.4% and FN = 11.3%. Because FP is an upper bound, the corrected column is a **floor** — the true value sits between it and the published number. The range spans the FP confidence interval only; it does not propagate the reference grader's own error, which is larger than the arithmetic.

| Arm | n | same/diff | Published | Corrected (floor) | Range (FP CI) | Source file (mtime UTC) |
|---|---|---|---|---|---|---|
| `derivability_B` | 150 | 135/15 | 90.0% | **87.1%** | 81.3%–89.6% | `evals/verdicts_derivability_B.json` (2026-07-26T05:17:19+00:00) |
| `h2h_opuslow_hard_r1` | 54 | 41/13 | 75.9% | **75.3%** | 70.4%–77.3% | `evals/verdicts_h2h_opuslow_hard_r1.json` (2026-07-26T07:11:05+00:00) |
| `h2h_opuslow_hard_r2` | 54 | 39/15 | 72.2% | **72.1%** | 67.5%–74.1% | `evals/verdicts_h2h_opuslow_hard_r2.json` (2026-07-26T14:03:41+00:00) |
| `h2h_opuslow_easy_r1` | 50 | 46/4 | 92.0% | **88.8%** | 82.9%–91.3% | `evals/verdicts_h2h_opuslow_easy_r1.json` (2026-07-26T13:53:38+00:00) |
| `h2h_opuslow_easy_r2` | 50 | 43/7 | 86.0% | **83.8%** | 78.2%–86.1% | `evals/verdicts_h2h_opuslow_easy_r2.json` (2026-07-26T13:57:43+00:00) |
| `h2h_sonnet_easy_r1` | 50 | 39/11 | 78.0% | **77.0%** | 72.0%–79.1% | `evals/verdicts_h2h_sonnet_easy_r1.json` (2026-07-26T15:05:37+00:00) |
| `h2h_sonnet_easy_r2` | 50 | 37/13 | 74.0% | **73.6%** | 68.9%–75.6% | `evals/verdicts_h2h_sonnet_easy_r2.json` (2026-07-26T15:09:40+00:00) |
| `opus5_low_bucketA` | 68 | 51/17 | 75.0% | **74.5%** | 69.7%–76.5% | `evals/verdicts_opus5_low_bucketA.json` (2026-07-26T00:04:48+00:00) |

Every "Published" figure above is the **raw judge accuracy** straight from the verdict file — for `derivability_B` that is 90.0%, not the 93.3% quoted elsewhere, which additionally folds in Jon's hand-regrade of the flagged side. The two arm-specific paragraphs below handle that difference explicitly.

**Arm B's 93.3%.** That published figure is 135/150 passed plus Jon's 5-row regrade of the flagged side (`docs/results-derivability.md`) = 93.3%. Two things pull on it in opposite directions, and both are live:

- Applying only the FP correction to its 135 passed rows, keeping Jon's 5 regraded rows, gives **89.3%** — the regrade's +3.3pt gain roughly cancelled.
- If the 3 flat-contradiction rows above are re-read as genuine disagreements, the regrade drops from 5 rows to 2 and the base falls to 91.3% before any FP correction.

Either way it is not 93.3%. The honest statement today is that arm B sits in the high 80s, with **89.3%** the best single estimate.

**The opus-low hard mean, 74.1%.** Published 75.9% (r1) and 72.2% (r2), mean 74.1%. Corrected mean: **73.7%** — essentially unmoved. The two corrections nearly cancel on this arm because it has a large flagged side (13 and 15 rows), so the FN credit offsets the FP debit. The hard-set number is the most robust of the headline figures.

## Limits — read these before quoting anything above

1. **The reference grader is not a reference.** It agreed with the audited judge on 32/32 validation rows and with Jon on 25/32. Every rate here inherits that, and the confidence intervals do not include it — they are sampling error only. The FP rate should be read as a bound, not a measurement.
2. **Same prompt, different model, same answers.** The grader was given the judge's prompt verbatim so that only the model varied. On the evidence, the prompt — not the model's capability — is what determines where the `same` / `different` line falls. A genuinely independent check needs a different *criterion*, or a human, not a bigger model.
3. **The FP direction still has no human ground truth.** Nobody has hand-graded a passed row. The four flagged above are the entire evidence base and are the cheapest, highest-value thing to put in front of Jon next.
4. **`derivability_C` contributes no `same` rows** — it has only 4 in the whole arm, and proportional allocation rounded it to zero. The FP rate covers 8 of the 9 arms.
5. **The judge is nondeterministic** (~1 flip per 100 rows on re-judging). That is a third error source, separate from the two measured here, and is not folded into these numbers.
6. **Correction is arithmetic, not a re-grade.** Applying a population rate to one arm assumes that arm's error rate matches the population's. The per-arm FP counts above are small; do not read a single arm's cell as its own rate.

## What would actually settle this

Jon hand-grades a blind mixed set — the 4 flagged passed rows above, the 7 disputed validation rows, and ~30 fresh passed rows he has not seen — without knowing which is which. That produces the one thing missing from every number here: human ground truth on the direction that has never had any, and a re-read of the arm-B calls that the 93.3% depends on.

## Reproducing

```
uv run python evals/judge_error_prep.py       # sample + batches (seeded, no API calls)
#   ... grade evals/judge_error_batches/*.md with Opus subagents ...
uv run python evals/judge_error_metrics.py    # rates + this report
```
