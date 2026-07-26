# Gold corrections — when a card ruling beats the dataset

**Established 2026-07-25.** RulesGuru gold is written by certified judges and is
treated as canonical (DECISIONS.md, 2026-07-23). This note records the one
documented exception and the corrections made under it.

## The exception

**An official WotC card ruling outranks a RulesGuru gold answer.** This is not
"Jon disagrees with the judges" — that case still resolves in RulesGuru's favour.
It is a *published ruling* contradicting a *dataset answer*, which is objectively
checkable via `rulesagent.tools.scryfall.get_card`.

Caveat on provenance: that contract stores only the ruling **text**, not
`published_at`. So "the ruling postdates the dataset" is a plausible explanation
for these errors but **cannot currently be confirmed** and must not be asserted.
What can be asserted is that the ruling contradicts the gold today.

## Corrections applied

Source: `evals/rulesguru_full.jsonl` (1,409 rows, untouched).
Corrected: **`evals/rulesguru_full_v2.jsonl`** — same 1,409 rows, unedited lines
copied byte-for-byte, exactly **three** rows changed. Edited rows carry a
`gold_corrected` field recording date, authorisation, and reason.

All three rest on **Urza's Saga ruling #1** (Scryfall, verbatim, ASCII
apostrophes):

> "If Urza's Saga loses all of its chapter abilities but is still a Saga, perhaps
> due to a card like Blood Moon, it will immediately be sacrificed."

### rg4023 — Jinx changes Urza's Saga's land type

Jinx reads `Target land becomes the basic land type of your choice until end of
turn`. A *basic* land type is what CR 305.7 keys on to strip abilities granted by
the land's rules text, so the chapter abilities are lost — which the original gold
already conceded in its first sentence before concluding "It is not sacrificed."
The gold contradicted itself against the ruling.

Changed: the final two sentences → the ruling-based conclusion. The layer-4 /
layer-6 analysis was correct and is preserved verbatim.

### rg6634 — Magus of the Moon vs Urza's Saga on chapter 2

Magus of the Moon's oracle text is `Nonbasic lands are Mountains`, byte-identical
to Blood Moon's, and the ruling names Blood Moon explicitly.

Two changes:
1. `an ability to tap for {1}` → `an ability to tap for {C}`. Chapter I grants
   `{T}: Add {C}`; the original was simply wrong on the symbol.
2. The "It is not sacrificed" conclusion → the ruling-based one.

### rg6385 — Magus of the Moon vs Urza's Saga, 2 lore counters

Not from the graded bucket. Found by sweeping all 8 corpus rows mentioning
Urza's Saga and regexing the gold for the specific wrong claim — the audit
method below, applied to a confirmed defect. Mechanically identical to rg6634.
Authorised by Jon 2026-07-25 after the sweep surfaced it.

Two changes:
1. `"{T} add {R}." and no other abilities` → also lists the abilities gained from
   the already-resolved chapter I and II triggers. Those are granted by
   continuous effects rather than the card's rules text, so they survive the
   subtype change per **Urza's Saga ruling #5** ("Urza's Saga gains an ability
   from its first and second chapters. It keeps those abilities for as long as
   it's on the battlefield"). Two lore counters means both had resolved.
   rg6634's gold got this right; rg6385's omitted it.
2. The "It is not sacrificed" conclusion → the ruling #1 conclusion, worded
   identically to rg6634's.

## NOT corrected, deliberately

### rg4854 — disputed, but no ruling to cite

Jon graded Rulemancer correct and RulesGuru wrong: One with the Stars reads
`Enchant creature or enchantment`, and Capenna Express is an `Artifact — Vehicle`
while its crew ability is still on the stack, so it is not a legal target and the
gold's layer-4 timestamp analysis presupposes an illegal cast. One with the Stars
ruling #1 leans the same way ("may enchant a permanent that is only *temporarily*
a creature").

This is rules reasoning, not a published ruling overriding the dataset, so it
falls **outside** the exception above and the gold stands uncorrected. Recorded
here so the disagreement isn't rediscovered from scratch.

## Stale copies — read this before trusting a number

`answer_gold` for these rows is duplicated into derived slices and completed run
artifacts:

```
evals/_h2h_set.jsonl              evals/_layers_union_slice.jsonl
evals/answers/opus5_low_norewrite_costbase.json    (+ layers_slice0_*, h2h_*)
evals/verdicts_opus5_low_bucketA*.json
```

These are **deliberately not updated**. They are inputs to and records of runs
that already happened; rewriting them would change what past runs were measured
against and break comparability with every number quoted so far.

**Rule going forward: cut any new slice from `rulesguru_full_v2.jsonl`.** A slice
cut from the original will silently reintroduce the corrected rows.

## Impact on measured accuracy

Bad gold puts a ceiling on any score. In the 68-row bucket A, 3 of 68 gold
answers were wrong (rg4023, rg6634, rg4854), so the maximum achievable was
~95.6%, not 100%.

It also means the auto-judge's flags decompose two ways, which mean opposite
things about instrument health:

| | count | what it means |
|---|---|---|
| judge error | 2 (rg783, rg1900) | the judge misread agreement |
| gold error | 3 (rg4023, rg4854, rg6634) | the judge was right; the reference was wrong |

Reported as a single 29.4% overturn rate this looked like a broken judge. Split
properly the judge's real error rate is **11.8%**, in line with the earlier 19%
estimate from the sonnet regrade. **Always classify an overturn as judge-error or
gold-error before drawing conclusions about the instrument.**

Note the perverse incentive this creates: Rulemancer cited `[Urza's Saga ruling
#1]` correctly, from `tools/ruling_retrieval.py` working exactly as designed, and
was scored wrong for it.

## Audit method (reusable)

The corpus-wide filter that surfaced these: **rows the auto-judge flagged whose
answer text cites a card ruling** (`[<Card> ruling #<n>]`). Over all verdict files
that is 167 flagged ids, 70 of which cite a ruling — a candidate pool, not a
finding, since most are genuine model errors. Narrowing to a known error pattern
is what produced rg6385: sweep the corpus for rows mentioning the card, then
regex the gold for the specific wrong claim.

The 70-row pool has **not** been reviewed. Reviewing it means reading answers
against rulings, which is judgement work, not a filter.
