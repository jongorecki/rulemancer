# Report — v5 grid: bullets x injection, cost beside accuracy

Run 2026-07-23. 64 generations, 16 files, **0 errors**. Four verified-distinct
prompt digests, both runs of each cell agreeing. Frozen judge, imported
unchanged; 64/64 judge calls, 0 exceptions, 0 judge errors.

**Verdicts are Jon's. Nothing below assigns one.** The judge routes; the three
rows it could not transfer are listed as pending, not guessed.

## The design, and why the question set looks lopsided

Phase 1 ran each arm against **its own misses**, so baseline verdicts are
wrong/partial by construction. A *fix* appears as a stable flip that Jon then
grades correct. Two rows are the opposite case — c011 and c002 were **correct**
at v3 and were v4's two regressions — so a flip there is a probable *break*.

- sonnet: c012 (wrong), c014 (partial), c015 (partial)
- gpt-5-mini: c004 (wrong), c012 (wrong), c015 (wrong), c011 (**correct**)
- monitored, non-scoring: c002 (**correct**)

## Cost beside accuracy — per Jon's ruling #10

Cost is measured, from `build_prompts_variant.py`'s own char accounting and the
plan's per-question-type breakdown. Tokens are the ~4-chars/token convention.

| cell | prompt | cost vs v3, card q | cost vs v3, rules q | sonnet: misses fixed | gpt-5-mini: scoring flips |
|---|---|---|---|---|---|
| **A** | v3 (control) | 0 | 0 | **0 of 3** | 0 stable |
| **B** | v3 + injection | **+93 tok** | **0 tok** | **0 of 3** | 1 stable -> c011 *(pending)* |
| **C** | v4nl | +510 tok | +510 tok | **0 of 3** | 2 stable -> c011, c015 *(pending)* |
| **D** | **v5 candidate** | **+603 tok** | **+509 tok** | **0 of 3** | **0 stable** |

Measured average input chars per query across all 50 captured questions:
A 14,338 · B 14,434 · C 16,378 · D 16,473.

## What the table says

**On sonnet — the production model — nothing happened.** Every one of the three
misses transferred unchanged in all four cells. No variant fixed anything, and
no variant broke anything. **Sonnet requires no grading from Jon at all.**

This is the second time the same result has appeared. v4 was a measured no-op on
sonnet: 46 -> 46, zero judge-detectable divergence across all 50 questions and
both runs. Cell C here *is* v4-minus-legend and reproduces that null. Cell D adds
the injected definitions on top and also changes nothing.

**c014 never moved, again.** The plan predicted this was the decisive case:
*"if v5 also misses c014, that is confirmatory and the symbol work is finished
either way."* v4 got the model to state the cost breakdown correctly and still
conclude wrong. The bottleneck is multi-step reasoning about cost modification,
not notation — and no amount of symbol documentation addresses that.

**On gpt-5-mini, the only movement is in the cheap and mid cells, not the
candidate.** Cell D produced zero scoring flips. Cells B and C moved c011 —
which was correct at v3 — so those are probable regressions rather than gains,
pending Jon's read.

## Jon's grading queue — 3 scoring rows, 2 monitored

| arm | cell | qid | v3 verdict | why it matters |
|---|---|---|---|---|
| gpt-5-mini | B | c011 | correct | probable regression from injection alone |
| gpt-5-mini | C | c011 | correct | probable regression from v4's bullets |
| gpt-5-mini | C | c015 | wrong | possible fix |
| gpt-5-mini | B | c002 | correct | **monitored, non-scoring** |
| gpt-5-mini | D | c002 | correct | **monitored, non-scoring** |

Unstable flips (r1 and r2 disagreed) are excluded from the arithmetic and the
queue per the unchanged stable-flip rule: sonnet A (c015), gpt-5-mini A, B, C
(one each).

## What is NOT concluded here

The v5 go/no-go is Jon's and is not made in this document. What the data
supports stating plainly:

- Cell D bought **zero** scoring changes on either arm at +603/+509 tokens per
  query, with no prompt caching on either path, so that cost is paid in full.
- Cell B is free on rules questions and +93 tokens on card questions, and it is
  the only cheap arm that moved anything — in what looks like the wrong
  direction.
- The one honest caveat on scope: phase 1 deliberately ran only the misses, so
  this measures *repair*, not *regression across the whole set*. A variant that
  fixed nothing here could still have broken something among the 44 questions
  not run. v4's full-set run found zero divergence on sonnet, which is
  reassuring for cells C and D but is not the same as having measured it.

## Related finding, filed separately

Symbol injection is **already live in production, ungated** (`answer.py:792-795`;
`PROMPT_VERSION` selects the SYSTEM text only). Production today is v3 bullets
plus injection — **cell B, not the cell A this report calls the control.** The
grid itself is unaffected, having run from a capture frozen before that shipped.
See `docs/OVERNIGHT-STATUS.md`. It needs a ruling, and it blocks c020.
