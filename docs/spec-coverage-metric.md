# Spec — graded retrieval coverage metric

**DRAFT under Rule 0 — design only. Nothing built. Awaiting Jon's ruling.**

## Why

"Gold" is the set of Comprehensive Rules ids a question actually needs cited to
be answerable — the ground truth against which retrieval gets graded. Every
question also carries a `match` field that says what counts as "retrieval found
it": `any` (one gold id is enough), `all` (every gold id must show up), or
`groups` (an AND-of-ORs — several required steps, each of which may have more
than one acceptable phrasing). `hit_at()` in `evals/run_eval.py` turns all three
into a single boolean per question: hit or miss, nothing in between.

That boolean has a real cost, measured today, not hypothetical:

- `evals/rulesguru_full_v2.jsonl` (the full 1,409-question corpus) is
  `match: "any"` on every row, with no exceptions. 745 rows (52.9%) carry 2+
  gold ids, mean 2.75, max 10 (`docs/results-match-semantics.md`). Under `any`,
  retrieving 1 of 10 required rules is a complete retrieval success.
- `docs/results-miss-partition.md` traced the consequence: on the hard eval
  arm, every single row labelled "context ok" was a `match: "any"` row with
  mean gold size 4.13, and accuracy given "context ok" (61.5%) was *lower*
  than accuracy given "retrieval miss" (89.3%) — backwards from what the label
  is supposed to mean. `rg4023` there is the clean case: a 10-id gold list,
  3 incidental ids retrieved, scored a full pass, while the two rules that
  actually decided the ruling were never retrieved.

The label isn't measuring degree of retrieval; it's measuring whether the
retriever got lucky once. This spec replaces the boolean with a **graded
coverage score** — what fraction of the gold ids actually made it into the
retrieved set — so the score no longer depends on which `match` mode a
question happens to carry.

## 1. Definition

**Coverage of a question `q` against a retrieved set `R`:**

```
coverage(q, R) = | normalize(gold(q)) ∩ normalize(R) | / | normalize(gold(q)) |
```

`gold(q)` is the question's flat `gold` list (the union of every id it cites,
regardless of `match` or `gold_groups` structure). `normalize(...)` is the same
`normalize_source_id()` both sides of `hit_at()` already use, so the curly-vs-
straight-apostrophe glossary ids (`City's Blessing` etc.) still match. `R` is
either a ranking's top-`k` chunk ids (live retrieval) or a recorded
`retrieved_rule_ids` list (post-hoc, see §6). Rows with empty gold are excluded
from the denominator — same convention `run_eval.py` already uses for
`n_scored` (line ~300) and `group_coverage()` already uses (returns `None`).

This formula is deliberately **flat over ids, not per-group.** That answers
the question this spec was asked to settle directly, so here's the reasoning,
not just the choice:

The alternative — one point per required *group*, then averaged — already
exists in the codebase. `evals/run_retrieval_diversity.py` has
`group_coverage()` (line 122): `hit = sum(1 for g in groups if any(... in topk
for x in g)); return hit / len(groups)`, where `groups = gold_groups(q)`. It
was built for exactly this spec's stated problem, on the `groups`-mode subset
of the curated 150-question set — and it's a good metric there. But
`gold_groups()` (`run_eval.py` line 158) collapses a `match: "any"` question's
entire gold list into **one** OR-group. Feed a 100%-`any` corpus (the full
1,409-question set, the one with the actual emergency) through
`group_coverage()` and every row still has exactly one group — it's boolean
again, no better than `hit_at()`. Per-group averaging fixes `groups`-mode rows
and does nothing for `any`-mode rows, which is 100% of the corpus this
matters most for. So it can't be *the* fix that makes match mode stop being
load-bearing — it's a different, narrower, still-useful measurement, kept as
is. The flat formula above never calls `gold_groups()` at all, so it can't
inherit that collapse.

**Worked example**, a real `groups` row from `questions_rulesguru150_v3.jsonl`,
`rg93` — *"Avery casts Sram's Expertise. As it resolves, they'd like to tap the
tokens it created to cast Collective Effort escalated twice. Can they?"*:

```
gold        = ["118.9d", "601.2b", "608.2c", "608.2g", "702.120a"]   (5 ids)
gold_groups = [["608.2c"], ["702.120a"], ["118.9d", "601.2b", "608.2g"]]
```

Say retrieval surfaces `608.2c` and `118.9d`, nothing else. Three different
numbers, three different questions, from the identical retrieval result:

| metric | value | question it answers |
|---|---:|---|
| `hit_at()` | **0 (miss)** | were *all three* required groups satisfied? (group 2, `702.120a`, wasn't — so no) |
| `group_coverage()` | **2/3 = 66.7%** | what fraction of the required *steps* were touched? |
| **coverage (this spec)** | **2/5 = 40%** | what fraction of the *cited evidence* landed in context? |

None of the three is wrong; they measure different things. Coverage is the
one that stays meaningful on a `match: "any"` row where no group structure
was ever curated.

**How coverage relates to `hit_at()`, by mode** (worth being precise about,
since it's not the same relationship in all three cases):

- **`all`** — `gold_groups()` returns one singleton group per id, identical to
  the flat list. `hit_at() == True` iff `coverage == 1.0`, exactly. Coverage is
  a strict generalization here: same pass/fail line, graded below it.
- **`any`** — `hit_at()` needs 1 id; `coverage == 1.0` needs *every* id. This is
  the fix working as intended: an `any` row that's secretly several required
  facts (which `docs/results-match-semantics.md` says is likely true for a lot
  of the full corpus) can no longer look fully retrieved on the strength of
  one incidental hit.
- **`groups`** — `hit_at()` needs one member per OR-group; `coverage == 1.0`
  needs the full id union, including every synonym inside a legitimate
  multi-member OR. This makes coverage a **strictly harder ceiling than
  `hit_at()` on legitimate OR rows** — `docs/results-orgroup-repass.md` counted
  26 of 105 groups as legitimate (every member independently sufficient,
  mostly a numbered rule paired with its own glossary entry). On those 26
  rows, a retrieval that fully satisfies every AND-step via one alternative
  each can still show coverage under 100%, because the unused alternates
  count against it. That's a real, acknowledged cost of using one
  mode-invariant formula instead of one that respects OR-structure — accepted
  because the 105-group re-pass also found 54 of those same 105 groups
  (43 rows) were **mis-encoded conjunctions**, not legitimate alternatives, so
  a formula that trusts the OR-structure is wrong more often, on this
  question set, than one that doesn't.

## 2. Where it sits in the code

`gold_groups()` and `hit_at()` (`evals/run_eval.py` lines 158–177) are **kept
alongside, unchanged, not replaced.** Reasons: `hit_at()` is still the correct
answer to a different question ("was every AND-requirement satisfied") that
coverage doesn't answer; it's imported by `evals/run_retrieval_diversity.py`
(per `docs/spec-retrieval-diversity.md`: "Zero edits to `run_eval.py`"); and
§3 below requires both numbers to keep being reportable through a transition.

New, added beside `hit_at()`:

```python
def coverage_at(q: EvalQuestion, ranking: list[Retrieved], k: int) -> float | None:
    """Fraction of q.gold present in ranking[:k]. None for empty gold (excluded
    from any mean, same convention as group_coverage() in
    run_retrieval_diversity.py). Flat over q.gold -- does not call
    gold_groups() -- so it applies identically regardless of match mode."""
```

used in `main()`'s per-question loop (lines 325–360) alongside the existing
`hit_at()` accumulation, printed as an additional table next to the recall@k
comparison (lines 393–398) — not instead of it.

Also new, for post-hoc recompute with no `Retrieved` ranking object at all:

```python
def coverage_from_ids(gold: list[str], retrieved_ids: list[str]) -> float | None:
    """Same formula, operating on plain id lists -- lets coverage be
    recomputed from evals/answers/*.json's recorded retrieved_rule_ids
    without re-running retrieval."""
```

`evals/run_retrieval_diversity.py`'s own `group_coverage()` is untouched — it
keeps answering its own (narrower, `groups`-mode-only) question. A future pass
could import `coverage_at`/`coverage_from_ids` there to print both side by
side across the diversity matrix; that's a natural follow-on, not part of
this spec.

## 3. Backwards compatibility

**Nothing published is invalidated.** `hit_at()` and `gold_groups()` are
untouched byte-for-byte, so every existing recall@k / hit@k number in
`docs/results-retrieval-diversity.md`, `docs/results-miss-partition.md`, and
the run_eval.py comparison table still means exactly what it always meant: a
boolean hit rate under each question's own `match` rule. Those numbers are not
wrong — they're incomplete, and several of the docs that quote them already
say so in their own limits sections (`docs/results-match-semantics.md`
explicitly notes its finding "un-interprets" part of
`docs/results-miss-partition.md`'s conditionals, without needing that doc
rewritten). Coverage doesn't retroactively correct anything; it's a better
instrument for what gets measured next.

**During the transition:** every place recall/hit@k is printed or reported
should print coverage alongside it, not swap it in — `run_eval.py`'s
comparison table gains a coverage@k section under the existing recall@k
section; any new `docs/results-*.md` that quotes a headline retrieval number
reports both, labelled plainly ("boolean hit under `match`" vs. "fraction of
gold retrieved"). No existing doc needs a correction or a retraction. Once
coverage has a few real runs behind it and Jon has seen how it moves relative
to the boolean numbers, whether to keep reporting both or promote coverage to
the sole headline is his call, not a default this spec makes for him.

## 4. What this does not fix

Coverage is a better ruler. It does not change what's being measured against:

- **Match-mode curation.** The full corpus's `match` field is still 100%
  `any` with no per-question review (`docs/results-match-semantics.md`).
  Coverage sidesteps needing that curated — it doesn't call `gold_groups()` —
  but it does not curate it. `hit_at()` on that corpus is still exactly as
  uncurated as before.
- **Gold content correctness.** `docs/results-miss-partition.md` found 90 of
  202 scored rows were "miss, correct" — the model answered right without the
  flagged gold at all (over-specified gold). Coverage can be dragged down by
  an unnecessary gold id exactly as easily as `hit_at()` could be inflated by
  one.
- **The OR-group structural defect.** `docs/results-orgroup-repass.md`: 54 of
  105 `gold_groups` sub-groups in the curated 150-set encode a required chain
  as if it were an alternative. Coverage's flat formula doesn't consult
  `gold_groups()`, so it is neither helped nor hurt by whether those 54 groups
  get split — but it is computed against the same flat `gold` union either
  way, and that union doesn't change under the proposed corrections (per
  `docs/results-orgroup-repass.md`: "The flat `gold` union is unaffected
  either way \[...\] only the AND/OR structure changes"). **A coverage score
  over a wrong gold set is still wrong.** This makes retrieval *measurable*,
  not *correct* — if a gold list cites a rule that shouldn't be there, or is
  missing the one that should, coverage will report a clean, confident,
  wrong number just as fluently as `hit_at()` did.
- **Answer quality.** Same explicit boundary `docs/spec-retrieval-diversity.md`
  already draws: this measures whether rules land in the retrieved window, not
  whether the generated answer gets better. `docs/results-miss-partition.md`'s
  own finding that hard-question accuracy is sometimes *lower* with gold
  present is a reasoning-failure question coverage cannot touch.
- **The sufficiency problem.** `docs/results-miss-partition.md`'s `rg614`
  worked example: one of three gold ids was present, and it was the wrong one
  to answer the question alone. Coverage will report that row at 33% — an
  honest number, but "33% present" still doesn't say *which* third mattered.
  Presence isn't sufficiency; coverage is a presence metric, same as `hit_at()`
  was, just graded.

## 5. Dashboard

Today `run_eval.py` prints one recall% per method per `k` — a single collapsed
number. Two changes:

**Report a distribution, not just a mean.** `docs/spec-retrieval-diversity.md`
already made this case for `group_coverage()`: at a low mean, "we are near a
floor where binary hit/miss can stay flat while retrieval genuinely improves
\[...\] going from 1-of-3 to 2-of-3 groups on forty questions would otherwise
register as nothing." The same floor effect applies to flat coverage's mean —
a fat tail of near-zero rows dragging a mean down looks identical, at the mean
level, to a uniform middling score across every row, and those are very
different retrieval-health pictures. Show percentiles (p10/p25/median/p75/p90)
or a histogram alongside the mean.

**Report coverage against `k`, as a curve, not one fixed point.** Coverage is
already defined at every `k` in `KS = (1, 5, 10, 20, 50)`; a coverage-vs-`k`
curve shows how fast partial credit accumulates as the window grows, which a
discrete recall@k table cannot show at all — it only has step points, no
growth-rate signal between them.

**Regressions.** `run_eval.py` already reports zero-flip regressions per arm
(lines 458–468) for `hit_at()`; coverage's equivalent isn't a flip count, it's
a per-question delta. Report a delta histogram per arm vs. the pure-vector
baseline (rows that got worse, and by how much), not just a boolean flip list
— a coverage regression can be real (0.60 → 0.20) without ever crossing a
hit/miss boundary the flip-count method would notice.

## 6. Validation — the cheapest possible path

**Confirmed directly, not assumed:** `evals/answers/derivability_B_goldonly.json`
already carries, per row, for all 150 rows of `questions_rulesguru150_v3.jsonl`
(its `match` distribution matches v3 exactly: 79 `groups` / 55 `any` / 16
`all`), both `gold` (the flat list) **and** `retrieved_rule_ids` in the same
row. One row was read directly to confirm the shape:

```
rg93: {"match": "groups",
       "gold": ["118.9d","601.2b","608.2c","608.2g","702.120a"],
       "retrieved_rule_ids": []}
```

(`retrieved_rule_ids` is empty for this particular row because
`derivability_B_goldonly` is a gold-only condition that skips retrieval by
design — a property of that arm, not a data gap.)

That means the **primary metric needs zero new model calls and zero re-run
arms** — `coverage_from_ids(row["gold"], row["retrieved_rule_ids"])` computes
directly from fields already sitting in every row of every answers file that
records `retrieved_rule_ids` (21 files under `evals/answers/` do, confirmed by
grep). No join is even needed for the primary number, since `gold` is
duplicated onto every answer row already.

The **optional secondary per-group diagnostic** (§1's `group_coverage()`-style
number, only meaningful on `match: "groups"` rows) needs one more thing:
`gold_groups`, which is **not** stored per-row in the answer files (confirmed:
no answer-row schema seen carries a `gold_groups` key). That's a free, local,
zero-API join back to `questions_rulesguru150_v3.jsonl` by `id` — the same
file every arm's questions came from — not a blocker, just a second read
worth naming honestly rather than implying it's as free as the primary
metric.

## Explicitly out of scope

Re-curating `match` on the full corpus (`match-semantics-curation`,
tracked separately). Re-running the OR-group re-pass at full-corpus scale
(`or-group-repass`'s own scale-up, also tracked separately). Any change to
`answer_gold`, canonical gold, or question files — this spec touches
measurement code only. Wiring `coverage_at`/`coverage_from_ids` into
`run_retrieval_diversity.py`'s matrix — a natural follow-on, not required to
ship this.

## Open questions for Jon

1. Once coverage has real numbers behind it, does it replace `hit_at()` as the
   headline, or do both stay permanently (e.g. coverage as the primary trend
   line, `hit_at()` kept as a stricter secondary gate)?
2. Should the per-group diagnostic (§1, §6) be built now alongside the flat
   metric, or deferred until `or-group-repass` actually lands (so it isn't
   reporting a number everyone already expects to move)?
