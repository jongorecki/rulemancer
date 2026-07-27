# Results — which channel is actually answering the questions?

Ran 2026-07-26. Five arms, 120 rows each (`evals/ab_rows.jsonl`: 40 each at level
2, level 3, Corner Case), every arm differing from the baseline in exactly one
channel and byte-identical everywhere else. Judge `openai/gpt-5-mini`, prompt sha
`b54fbdb955` — the same judge as every published arm.

## Result

```
arm                      acc     vs A    paired (A only / arm only)         p
A  baseline            66.7%       -     -                                  -
B  placebo RULES       63.3%    -3.3     12 / 8    (20 discordant)       0.50
R  placebo RULINGS     60.8%    -5.8     14 / 7    (21 discordant)       0.19
K  placebo CARD DATA   35.8%   -30.8     46 / 9    (55 discordant)    4.3e-07
Z  placebo EVERYTHING   3.3%   -63.3     77 / 1    (78 discordant)    5.2e-22
```

"Placebo" means the channel was replaced with the same channel's content from a
*different* question — deranged, seed-fixed, same size and format. Not deletion:
the prompt keeps its shape, only the relevance changes.

| channel | cost when scrambled | significant |
|---|---|---|
| **card oracle text** | **~25-31 points** | **yes, overwhelmingly** |
| card rulings | ~6 points | no (p=0.19) |
| CR rules | ~3 points | no (p=0.50) |

**The card oracle text is the load-bearing channel.** Arm R keeps the oracle text
and swaps only the rulings: it loses 5.8 points and does not reach significance.
Arm K swaps the whole card block including the oracle text: it collapses by 30.8
points. The difference between those two arms is what isolates it.

Meanwhile the CR rules — the entire subject of the retrieval pipeline, the gold
mining, the rewrite/RRF fusion work, and several sessions of eval effort — cost
**3.3 points** when replaced with rules retrieved for an unrelated question, on a
12-8 split across 20 discordant pairs. That is a coin flip.

## Two asymmetries worth keeping

**Wrong rules are ignorable; wrong cards are not.** The model can read an
irrelevant rules block, notice it doesn't apply, and fall back on the card text —
grounding telemetry confirms this directly: it cites CR rules on 97.5% of arm A
rows and only 22.5% of arm B rows. It sees which rules it got. But it cannot
route around a wrong *card*, because the question is *about* that card.

**Wrong information is far worse than missing information.** This is the one
place the experiment's design misleads if read carelessly, so it is stated
plainly here:

> **Arm Z is NOT a parametric-knowledge floor, despite being designed as one.**
> It hands the model the wrong cards, not no cards. The genuine floor is the
> no-rules control from earlier the same day — *empty* context — which scored
> ~59.5% corpus-weighted. Arm Z scored 3.3%.

Read together:

| condition | score |
|---|---|
| empty context (no rules at all) | ~59.5% |
| correct cards + wrong rules | 63.3% |
| everything correct | 66.7% |
| wrong cards | 35.8% |
| wrong cards + wrong rules | 3.3% |

A missing channel degrades gracefully. A *wrong* channel is catastrophic.

## What this implies for the product

1. **Card resolution is the highest-leverage surface, by an order of magnitude.**
   Coverage (is every card named in the question resolved?) and correctness (is
   it the *right* card?) dominate everything in the retrieval stack.
2. **Mis-resolution is the expensive failure, not non-resolution.** Wrong card
   data costs ~31 points. Prefer failing to resolve over resolving wrongly —
   split cards (`Pain // Suffering`), double-faced cards, and apostrophes
   (`Urza's Saga`, `Inventors' Fair`) are the known-hard cases; they broke two
   separate parsers during this session's analysis alone.
3. **The CR-rules retrieval work has a small ceiling.** Whatever remains to be
   won by better rule retrieval is bounded above by roughly 3 points on this
   question set. That does not make it worthless — citations and verifiability
   are product value independent of accuracy — but it is not where accuracy
   lives.

## It also explains a puzzle from the same morning

`docs/results-adversarial-review.md` found gold-rule coverage and correctness
essentially uncorrelated (r=+0.06), and treated it as evidence the *instrument*
was broken. The instrument was fine. It was measuring the channel that doesn't
matter.

## Caveats

- 120 rows, drawn from levels 2/3/Corner Case only — deliberately not
  corpus-representative, because levels 0 and 1 are 87%/70% answerable with no
  rules at all and would dilute any signal.
- All arms run through the frozen-prompt path: no tools attached, and
  `ruling_query_mode=union` rather than the shipped `raw`. Contrasts are clean
  because those are held constant; absolute accuracies are not the product's.
- The derangement was drawn over an eligible subset. `rg1006` has no cards;
  `rg46`/`rg625`/`rg1006` have no rulings. Those rows are byte-identical to arm A
  on that dimension with `borrowed_from=null`, and `evals/analyze_channels.py`
  excludes them per-arm rather than counting them as swapped.
- Judge is one-directionally harsh (7 human corrections across 218 rows, all
  "judge wrong -> human right"), so every arm is biased the same way and the
  *differences* are the robust quantity — which is what is read here.

---

## The layers tool, tested on its home turf — no measurable benefit

Separate experiment, same day. 68 rows: every corpus question whose gold answer
includes a CR 613 layer rule (holdout excluded). Live path (`RulesAgent.answer()`),
`--no-rewrite`, `ruling_query_mode=raw`, same model, one variable — the tool on or
off. This is NOT comparable to the arms above (different row set, different query
mode); read it only against itself.

This experiment had never been run before. Every layers-off arm on disk was
`claude-sonnet-5` and every layers-on arm was `claude-opus-5`, so the tool's value
had never been isolated from the generator.

```
tool fired on 42/68 rows (62%)   [vs 6.7% on a representative hard set]

  layers ON   70.6%
  layers OFF  67.6%

  ALL rows      ON only 6 | OFF only 4 | 10 discordant | p = 0.75
  FIRED rows    ON only 5 | OFF only 3 |  8 discordant | p = 0.73   <- the real test
  NOT-fired     ON only 1 | OFF only 1 |  2 discordant   (noise, as expected)
```

**No benefit, even restricted to the rows where the tool actually ran.**

The internal consistency check is what makes this a real null rather than a
diluted one: rows the tool never touched show 1-1 discordance — exactly the noise
they should be — while fired rows show 5-3. The signal is not hiding in the fired
subset; it is not there.

A first attempt at this on a representative hard set was uninformative and is
recorded because it shows the trap: the arms differed by 6.7 points, which looked
like a result, but the tool had fired on `rg783` while the single discordant row
was `rg6556`. Different rows. The apparent effect was run-to-run noise on a row
the tool never touched. **"Did the intervention touch the rows that moved?" is the
check that separates a finding from an artifact**, and it is cheap.

### Scoreboard after four single-variable tests

| component | cost when scrambled/removed | verdict |
|---|---|---|
| **card oracle text** | **-31 pts, p=4.3e-07** | **carries the system** |
| card rulings | -6 pts, p=0.19 | minor |
| CR rules retrieval | -3 pts, p=0.50 | ~inert |
| layers tool | 0, p=0.73 | ~inert |
| reasoning effort low->high | 0 (n=15) | no effect |
