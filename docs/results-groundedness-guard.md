# Results — the groundedness guard does not guard

Found 2026-07-26 while running the retrieval A/B pilot. Analysis below is all
local computation over files already on disk. Zero API spend.

## What the guard is supposed to be

`src/rulesagent/contracts.py`, on the `answered` field:

> True if the provided rules were sufficient to answer. False triggers the
> low-confidence path: the bot says it can't answer from the rules it was given
> rather than hallucinating. **This is the groundedness guard.**

That is the product's stated defence against answering from parametric memory
when retrieval has failed.

## What actually happens

**Arm B of the pilot handed the model a rules block containing nothing relevant
to the question asked** — 15 questions, each given the rules retrieved for a
*different* question. Result:

```
answered = True   on 15 of 15 rows
answered = False  on  0 of 15 rows
```

The guard never fired. Not once, against a context that was 100% irrelevant by
construction.

It is not an artifact of the small sample. Across **every** answer file on disk:

```
1,752 recorded generations, 52 arms
  answered=False ever returned:   17   (0.97%)
```

The decline path is effectively dead product-wide.

## Root cause — two separate defects

**1. The guard is advisory. It cannot decline anything.**
The only code that inspects this condition (`answer.py` ~line 2385) is:

```python
if parsed.answered and not parsed.citations:
    logger.warning("answered=true with no citations (ungrounded success): %r", ...)
    self.last_uncited_success = True
```

It logs a warning and sets a flag. **It never flips `answered` to False, never
suppresses the answer, and nothing downstream consumes `last_uncited_success`.**
Whether the bot declines is left entirely to the model's own self-report inside
its structured output. There is no enforcement anywhere.

**2. The condition it checks is the wrong one.**
`not parsed.citations` is an *emptiness* test over a field that deliberately
mixes four different kinds of thing: CR rule numbers, glossary terms, card names,
and card-ruling labels like `Archive Trap ruling #2`. So a row that cites **zero
CR rules** but names one card ruling passes the check and looks grounded.

That is exactly what arm B did. Mean citations per row was 7.0 — the rows were
not silent, they were citing card rulings and card names while ignoring the
rules block entirely.

## The useful part: a working signal already exists, unwired

Counting only **CR rule-number** citations cleanly separates a relevant context
from an irrelevant one:

| condition | rows citing zero CR rules |
|---|---|
| corpus-wide baseline (1,752 generations, all arms) | **4.6%** |
| arm A — real retrieved rules | **6.7%** (1/15) |
| arm B — irrelevant rules | **86.7%** (13/15) |

A 4.6% baseline against 86.7% under induced retrieval failure is a strong
detector, and it needs no new model call — it is computable from the response the
product already produces.

**The bot does notice.** When the rules are useless it quietly stops citing them
and answers from its own knowledge. The information is right there in the output;
nothing reads it.

## Proposed fix — DESIGN ONLY, Rule 0, not implemented

Two changes, deliberately separable so they can be evaluated independently:

1. **Make the check specific.** Replace `not parsed.citations` with a test for
   zero *CR rule-number* citations, since that is the field element that
   represents a grounding claim. Card and ruling citations should not satisfy a
   rules-grounding check.
2. **Decide what enforcement means.** Options, in increasing severity: surface a
   "low grounding" state to the caller; re-ask once with the flag made explicit;
   or actually flip to the decline path. **This needs Jon's ruling** — flipping to
   decline trades accuracy for honesty, and on a corpus where the model is right
   ~60% of the time without any rules at all, that trade is not obviously correct
   and must be measured, not assumed.

**Do not implement 2 without measuring it.** Forcing declines would reduce
accuracy on exactly the rows the model currently gets right from memory. Whether
that is the product we want is a judgement call, not an engineering one.

## A limitation of the experiment that produced this — recorded, not buried

**The placebo swapped only the CR rules block.** Card oracle text and card rulings
remained correct for the question being asked. So arm B was not "no useful
information" — it was "no useful *rules*, with accurate card data and rulings
still present."

Two consequences:

- Arm B's 66.7% accuracy is partly explained by that retained card data, and MTG
  card rulings are frequently decisive on their own.
- The A−B contrast measures **the value of relevant CR rules given correct card
  data**, which is narrower than "the value of retrieval." The spec claimed the
  broader thing. That is a flaw in the design as written in
  `docs/spec-retrieval-value-ab.md`, found by running it.

The guard finding above is unaffected — if anything the retained card data makes
it stronger, since the model had *more* legitimate grounding available than a
pure no-context arm and still never declined.
