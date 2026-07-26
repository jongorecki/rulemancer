# Report — out-of-range ruling citations: root cause found, and it is not a product bug

Investigated 2026-07-26 from Jon's batch-1 gold-audit note on `rg1095`: *"cited
ruling #3 is out of range — Rescuer Sphinx has 3 rulings, #0-#2."*

**Three corrections to what we thought:**

1. **It is not a product bug.** Production-path arms emit **0 out-of-range
   citations across 397 checked**. The defect is confined to
   `evals/build_gold_prompts.py`, i.e. the two derivability arms only.
2. **It is far larger than 3 of 15 rows.** In arm B, **83 of the 120 rows that
   cite a ruling (69%)** carry at least one out-of-range citation — 103 of 341
   citations, 30.2%.
3. **Out-of-range is only the visible tip.** *Every* ruling citation in those
   arms is off by one. It is detectable only when the cited index lands past the
   end of the list; a mid-list off-by-one silently points at the neighbouring
   ruling and looks fine.

## Root cause

`RulesAgent.answer()` injects the citation labels, and it does so **after**
selecting rulings and **before** handing cards to the renderer
(`src/rulesagent/generate/answer.py:1941` and `:1948`):

```python
picked.append(card.model_copy(update={"rulings": [
    f"[{card.name} ruling #{i}] {card.rulings[i]}" for i, _ in sel]}))
```

The renderer itself does not label. `_format_cards()` prints whatever string it
is given (`answer.py:1519`):

```python
lines.extend(f"- {r}" for r in c.rulings)
```

`evals/build_gold_prompts.py` imports `build_prompt` **directly** and passes raw
`Card` objects (`build_gold_prompts.py:78`), bypassing `answer()` entirely — that
is deliberate and documented in that file ("WHY FROZEN PROMPTS instead of a new
RulesAgent mode"). So the rulings arrive unlabeled and render as a bare list:

```
Rulings:
- If Rescuer Sphinx somehow enters the battlefield at the same time as...
- If the returned permanent had an ability that would otherwise have...
- You choose whether to return a nonland permanent and which one to...
```

Meanwhile the **system prompt still instructs the model to cite by a label that
is not there**:

> Card rulings in the context are labeled like `"[Card Name ruling #4]"`. When you
> rely on a ruling, put that exact label in the citations field.

Given an instruction to cite labels and no labels to copy, the model does the
only thing available: it counts the bullets and numbers them **1-based**. So the
last ruling of an N-ruling card gets cited as `#N`, which is exactly one past the
end of the 0-based range the label scheme means.

**The defect is that the labelling step lives in `answer()` rather than at the
prompt-construction boundary that every caller shares.** Any code path that
builds a prompt without going through `answer()` inherits a prompt that promises
labels it does not contain.

## The evidence

**1. Index distribution — the 0-based/1-based signature.** Same question set,
same system prompt, same label instruction:

```
gold-only arm (no labels in prompt)      production-path arm (labels present)
  #0     0    <- never                     #0    36    <- modal value
  #1   105                                 #1    30
  #2    66                                 #2    26
  #3    44                                 #3    15
  ...                                      ...
```

**341 citations and not one `#0`.** In the production arm `#0` is the single most
common index at 29% of citations. If the gold arm were reading real 0-based
labels, roughly 99 of its 341 citations would be `#0`. Observing zero is
conclusive.

**2. Direct range validation** against real card data via
`rulesagent.tools.scryfall.get_card`:

```
arm                              cites   out-of-range    rate
derivability_B_goldonly            341        103       30.2%
derivability_C_failures             56         11       19.6%
h2h_opuslow_hard_r1                124          0        0.0%
h2h_opuslow_hard_r2                122          0        0.0%
h2h_sonnet_easy_r1                  71          0        0.0%
h2h_opuslow_easy_r1                 80          0        0.0%
```

**3. Every stored prompt file, labels in the user prompt:**

```
_prompts_derivability_B_goldonly.json    277 ruling blocks,   0 labels
_prompts_derivability_C_goldplusretrieved.json  277 blocks,   0 labels
every other _prompts_*.json               23 ruling blocks,  61-75 labels
```

**4. The 1-based reading picks the right ruling.** On `rg1095` the model cited
`[Rescuer Sphinx ruling #3]`. Read 1-based that is the third bullet — *"You
choose whether to return a nonland permanent and which one to return... No player
may take actions between the time you choose and the time Rescuer Sphinx is on
the battlefield"* — which is precisely the load-bearing ruling for that question.
Read 0-based it is out of range. The model's *reasoning* was right; only its
*index* was wrong. Same for `[Primal Vigor ruling #3]`, which 1-based is the
counters ruling the answer depends on and 0-based is an unrelated token ruling.

## What this does and does not invalidate

**Does not invalidate the 93.3%.** The judge compares answer text against the
reference answer; it does not resolve citation labels. Arm B's accuracy stands as
measured. If anything the arms were mildly handicapped — the model spent effort
satisfying a citation convention that could not be satisfied.

**Does invalidate any analysis keying off arm B/C ruling citations.** Anything
resolving a `ruling #N` label from those two files to ruling text gets the
neighbouring ruling, or nothing. **CR rule citations are unaffected** — rules
render with real `[614.12]` labels in these prompts, and only card rulings lack
them.

**It is why the gold-audit UI looked wrong to a reader.** Jon was comparing cited
indices against the card panel, which renders real 0-based Scryfall rulings. The
mismatch he spotted is real; its cause was upstream of the UI.

## Recommended fix — needs a ruling before any code moves

**Move labelling to the shared boundary rather than patching the one caller.**
Labelling inside `build_prompt()` (or a `label_rulings()` helper it calls) means
every current and future prompt builder gets labels by construction. Patching
only `build_gold_prompts.py` fixes these two arms and leaves the next script free
to reintroduce the same divergence — the same class of defect this repo has hit
before by putting an invariant in a caller instead of at the boundary.

One design constraint: `answer()` labels a **filtered subset** with **original**
Scryfall indices, which a renderer cannot recover from a plain list of strings.
So the helper needs the indices passed explicitly, with the all-rulings case
defaulting to `enumerate`.

**The decision Jon needs to make**, because it is a measurement question and not
just a code question:

- Fixing this **changes the prompt** the derivability arms send. Re-running arm B
  would produce a number not directly comparable to today's 93.3%, and would cost
  roughly what arm B cost ($8.47).
- Not re-running is defensible: the accuracy is judged on answer text and stands.
  The cost is that arm B/C citations remain unusable for any future analysis, and
  the results docs need a footnote saying so.

**Recommendation: fix the boundary, add a range-check guard, do not re-run arm B
yet.** The guard is the durable win — a validator that checks every emitted
`ruling #N` against the card's true ruling count would have caught this the day
arm B ran, instead of surfacing 15 rows at a time through human grading. Re-run
only if we later want arm B's citations as data.

**Not proposed:** changing the label scheme to 1-based. The 0-based index maps to
the gold `oracle_id#index` and to `ruling_id()`; renumbering for the model's
convenience would break that mapping, which is a real dependency (`answer.py:1938`
comment, L8).
