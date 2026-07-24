# Plan — Rulings-recall: the hard-cutoff retrieval-recall gap behind c011

**DRAFT under Rule 0 — DESIGN ONLY. Nothing built.**

**JON'S RULING 2026-07-23: SHELVED.** Diagnosis kept on record, build nothing.
Rationale: it rests on 3 known misses (c010/c011/c019) with no formal metric,
and c011 — its anchor case — is frozen evidence, so fixing retrieval so that
c011 passes would be fitting to a single point. The cheapest candidate (cross-
signal with the CR RAG) is also near-dead: 0 of 190 measured rulings cite a CR
rule number. Revisit only if more ruling-recall misses surface, or if a rulings
gold instrument gets built for other reasons. Not deleted — the distribution
finding (median 8 rulings/card, 89% of ruling-bearing eval cards exceed TOP_N=3)
is real and worth keeping.

## 0. Scope note

Written after tonight's `docs/plan-c011-stale-rulings.md`, which diagnosed c011's
"old ruling, not updated one" grading note as a stale-data / prompt-sensitivity
problem, and in doing so re-surfaced a *separate*, already-documented finding: the
per-card ruling mini-RAG's hard cutoff doesn't reach c011's load-bearing ruling at
all, regardless of data freshness. This plan is that second problem, taken on its
own. No code was written or touched. Every ruling-count number below came from a
live, read-only Scryfall fetch (`api.scryfall.com`, public rulings endpoint) done
in this session — no `get_card()` call, no cache write, no paid model or embedding
API call. `evals/cards.jsonl`, verdict files, and prompt files were only read.

## 1. The finding, quoted

`src/rulesagent/tools/ruling_retrieval.py`:

```python
# lines 20-34
RULING_MODEL = "voyage-4-large"  # same embedding space as the rules index
TOP_N = 3
# Cap the number of rulings included, so a card carrying ~25 near-duplicate
# mechanic-boilerplate rulings (a Duskmourn Room) can't flood the prompt even if
# several clear the floor.

COSINE_FLOOR = 0.38
# CALIBRATED on the 19-question card eval (2026-07-21). Across the ruling-bearing
# questions the load-bearing ruling's cosine to its question ran 0.41-0.66; 0.38
# sits just under the low end (c012 Lithoform-6 at 0.418, c015 Grist-1 at 0.414)
# with margin for query-embedding wobble, while the top-3 cap keeps a card with
# many rulings from flooding the prompt. 3 questions have a load-bearing ruling
# BELOW this / outside top-3 (c010, c011, c019) -- a genuine semantic-mismatch
# limit of relevance retrieval, not a floor to chase down (lowering it wouldn't
# lift those into the top 3 anyway). See LOG.md.
```

Selection itself, `select_rulings` (lines 84-96), scores every one of a card's
rulings against the query and keeps the top `TOP_N` that clear `COSINE_FLOOR`:

```python
def select_rulings(card: Card, query: str, floor: float = COSINE_FLOOR,
                   top_n: int = TOP_N) -> list[tuple[int, float]]:
    ...
    embs = _card_ruling_embeddings(card)     # (R, dim), normalized
    qvec = embed_query(query, RULING_MODEL)  # (dim,), normalized
    scores = embs @ qvec                     # cosine per ruling (both normalized)
    return _select_from_scores(scores, floor, top_n)
```

`_select_from_scores` (lines 70-81) sorts descending, stops at the first score
under `floor`, and caps at `top_n` — a **hard, fixed cutoff per card**, independent
of how many rulings that card actually has.

Every constant that governs this: `TOP_N = 3`, `COSINE_FLOOR = 0.38`,
`RULING_MODEL = "voyage-4-large"`. Nothing else is tunable at this layer.

**c011's specific miss**, confirmed today against live Scryfall (Valki, God of
Lies, oracle rulings, fetched read-only this session): ruling index 17 —

> "The mana value of a modal double-faced card is based on the characteristics of
> the face that's being considered. On the stack and battlefield, consider
> whichever face is up. In all other zones, consider only the front face."

— is Valki's load-bearing ruling for c011 (`evals/run_openrouter_arm.py:88`,
`LOAD_BEARING_RULINGS = {..., "c011": {"Valki, God of Lies": [17]}, ...}`, sourced
from `cards.jsonl`'s c011 `note`). Under `select_rulings`'s raw-question mode
(today's shipped default), it doesn't clear the top-3 cosine cutoff — this is
exactly what the code comment above already documents, and what
`docs/plan-c011-stale-rulings.md` §1 re-confirms as "a separate, already-documented
retrieval-recall gap that happens to share a question id" with tonight's
stale-ruling diagnosis. **c010 and c019 carry the identical shape** — a real
load-bearing ruling that exists in the card's data and is withheld anyway, per the
same code comment.

## 2. The measured ruling-count distribution

Every card referenced anywhere in `evals/cards.jsonl` (30 unique names, one live
Scryfall `/cards/named` + `/rulings` fetch each, read-only, this session):

| stat | all 30 cards | cards with ≥1 ruling (19) |
|---|---|---|
| min | 0 | 2 |
| median | 4.5 | 8 |
| mean | 6.33 | 10.0 |
| max | 27 (Teferi's Protection) | 27 |

Full sorted list (all 30): `0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 4, 4, 5, 5, 5, 5,
7, 8, 8, 9, 14, 14, 15, 16, 18, 22, 27`.

Per-card: Animate Dead 5, Awaken the Woods 0, Banishing Light 8, Charging Rhino 0,
Clone 8, Counterspell 0, Divination 0, Doubling Season 5, Emrakul, the Promised
End 18, Fiend Hunter 4, Final Fortune 2, Flooded Strand 0, Fork 15, Gogo, Master of
Mimicry 14, Grist, the Hunger Tide 5, Grizzly Bears 0, Lightning Bolt 0, Lithoform
Engine 16, Mimic Vat 14, Monastery Swiftspear 4, Phyrexian Arena 0, Shardless Agent
9, Skullbriar, the Walking Grave 7, Stampeding Rhino 0, Sundial of the Infinite 5,
Teferi's Protection 27, Trinisphere 2, Valki, God of Lies 22, Vampire Nighthawk 0,
Voltaic Key 0.

**Read honestly, this is a bimodal, curated distribution, not a random sample —
and that matters for how much weight to put on it:**

- **11/30 cards (37%) have zero rulings.** These are almost entirely
  `evals/cards.jsonl`'s c001-c005/c020 cohort — cards Jon and the pipeline
  deliberately picked as *weak* rules-RAG tests (Counterspell, Divination, Grizzly
  Bears, Lightning Bolt, etc.), per DECISIONS.md's own note on why that set was
  replaced: *"the rulings-on-demand spike showed the old 5-question set was a thin
  testbed -- 4 of 5 referenced cards had ZERO rulings."* TOP_N/COSINE_FLOOR are
  structurally irrelevant to these; there's nothing to cut off.
- **19/30 cards (63%) carry at least one ruling**, and this is the cohort
  (`c006`-`c019`) DECISIONS.md records was deliberately built *because* it's
  ruling-dense: *"pulled Scryfall's rulings bulk file and found... the true
  high-ruling cards are new-keyword mechanic cards... plus complex singletons"*
  and selected specifically for cards with load-bearing, card-specific rulings.
  **Among exactly this cohort — the one the eval was built to stress rulings
  retrieval on — median is 8 and mean is 10, both well above `TOP_N=3`.**
- **17/19 ruling-bearing cards (89%) carry more rulings than `TOP_N=3`.** The cap
  isn't a rare edge case triggered by one outlier card (a "Duskmourn Room," per the
  code comment's own example) — it binds on the overwhelming majority of the cards
  this eval set was purpose-built to exercise.
- Even a **doubled** cap (`TOP_N=6`) would still bind on 11/19 (58%) of these
  cards.
- Concretely, on Valki (22 rulings, c011's card): rulings 13-21 (9 of the 22) are
  generic modal-DFC-layout boilerplate — "there is a single triangle icon in the
  top left corner," "a modal double-faced card can't be transformed," etc. — the
  same reminder text any modal DFC ships with. Ruling 17 (load-bearing) sits
  *inside* that boilerplate block, competing on cosine similarity against eight
  near-duplicate neighbors before ever reaching the top 3.
- **CR rule-number citations inside rulings: checked and absent.** Scanned all 190
  rulings across the 19 ruling-bearing cards for a `\d{3}\.\d+[a-z]?`-shaped CR
  rule number (e.g. "702.85a") appearing in the ruling text itself: **0/190
  matched.** WotC's rulings are written in plain English for players, not as CR
  cross-references. This is load-bearing evidence against one of the candidate
  directions below (§3.4) — flagged there.

**Conclusion the data itself argues:** on the *deliberately weak* rules-RAG cards
the hard cutoff is a non-issue (nothing to cut). On the *deliberately ruling-dense*
cards — which is most of what's left, and specifically what c011/c010/c019 belong
to — the cutoff binds almost every time. The distribution does not let this plan
argue itself down; it argues the opposite: the cards this repo chose to test
rulings-recall on are exactly the shape where a fixed top-3/0.38 cutoff is most
likely to drop the one ruling that matters. That's a structural property of what
"ruling-heavy" cards look like (a handful of load-bearing rulings buried in a pile
of boilerplate variants), not an artifact of picking unlucky cards.

## 3. Candidate directions, with trade-offs (Jon decides; none chosen here)

### 3.1 Widen the cutoff (raise `TOP_N`, lower `COSINE_FLOOR`, or both)

**Mechanism:** the simplest lever — change the two constants.

**Token cost, estimated from measured data:** average ruling length across the 190
measured rulings is 208 characters / ~52 tokens (median 187 chars / ~47 tokens,
max 580 chars / ~145 tokens). Raising `TOP_N` from 3 to, say, 6 adds up to 3 more
rulings per referenced card that clear the (unchanged) floor — roughly **+150
tokens per card, per question**, trivial for a single-card question, additive for
multi-card ones (c012/c013/c015 each reference 2 cards). This is cheap in absolute
terms. Lowering `COSINE_FLOOR` is harder to cost precisely without re-running the
embeddings (out of scope, paid), but the risk is qualitatively different from
raising `TOP_N`: a lower floor admits more *low-relevance* content, including
exactly the near-duplicate boilerplate rulings noted above (Valki 13-21) — diluting
the prompt with noise rather than cheaply adding one more genuinely relevant
ruling.

**Failure mode:** doesn't fix the *class* of miss, just moves the goalposts. c011's
ruling 17 is buried behind boilerplate on a card with 22 rulings; `TOP_N=6` might
or might not surface it (unmeasured — would require the embeddings, out of scope
here). A wider net is also a blunter instrument than the other options below: it
can't distinguish "genuinely more relevant, ranked 4th" from "boilerplate,
happened to rank 4th." And per §2, the specific COSINE_FLOOR comment already
states this was checked once: *"lowering it wouldn't lift those [c010/c011/c019]
into the top 3 anyway"* — i.e. c011's miss on the raw-question query is not close
to the floor; widening the floor may not be sufficient by itself, only widening
`TOP_N` (or both together) would matter, and that's unverified without re-running
the actual embeddings.

### 3.2 Score rulings against the question vs. against the card

**Does the current code already do one of these?** Yes — scored against the
**question**, not the card. `select_rulings`'s own docstring: *"`query` is the
stripped user question (rulings read as plainer English than the CR-vocabulary
rewrite, so the raw question is the better ruling query)."* `RulesAgent.answer()`
calls it with the bare stripped question (`generate/answer.py`, `ruling_query_mode
== "raw"` branch, `select_rulings(card, question)`), not with anything
card-derived.

**This isn't hypothetical — a variant of "improve the query side" was already
built, measured, and rejected.** `select_rulings_union` (`ruling_retrieval.py`
lines 99-121) unions the raw question with the Haiku rewrite's rules-vocabulary
phrasing(s), keeping the max cosine per ruling across both angles — Part B of
`docs/plan-l1-crossref-expansion.md`. It shipped as `RulesAgent`'s
`ruling_query_mode="union"` option, **off by default**. Measured 2026-07-22
(LOG.md): at the retrieval level it recovered load-bearing rulings on **16/25 →
20/25** question-card rows, "0 regressions" at that layer. But DECISIONS.md
2026-07-23 records the ship decision: **"Part B ruling-query union: DOES NOT
SHIP"** — Jon's pre-commitment was "ships if D ≥ C on graded correct-counts," and
condition D (union) was *worse* than C on the two strongest generation arms
(gpt-5-mini 45→43, v4-flash down), better only on the weakest (gemini). The
retrieval-level win did not reach generation and **actively hurt the lead arm**.
It "stays available behind its flag, OFF by default."

Whether c011 specifically was among the 16→20 gained rows isn't recorded in
LOG.md/DECISIONS.md at the per-row level available in this repo, so that's
unconfirmed either way — but it doesn't change the caution this sets for *any*
retrieval-recall change in this space: **a clean win on retrieval recall does not
guarantee, and in this repo's own recent history did not produce, a win on
generation correctness.** Any of §3.1/§3.3/§3.4 needs the same generation-level
check, not just a retrieval-level one, before it can be called a win. See §4.

**Failure mode:** union mode is already the empirical answer to "does querying
differently help," and the empirical answer was "yes at retrieval, no (net
negative on the strongest arms) at generation." Re-proposing the same shape without
a new idea on top would very likely reproduce the same rejection.

### 3.3 Two-stage select-then-rerank over rulings

**Mechanism:** stage 1 (cheap, current cosine) over-selects a wider candidate pool
per card (e.g. top-10 instead of top-3, floor relaxed or dropped); stage 2 reranks
that pool against the question with a stronger signal — a cross-encoder, or an
LLM-based relevance judgment (Haiku-tier) — and keeps the true top-3 by the
reranked order.

**Token cost:** stage 1 is unchanged/cheap (embeddings, already the pattern here).
Stage 2 is the new cost: a rerank call over up to ~10 candidate rulings per card,
per question — if LLM-based, that's one extra cheap-tier generation call per
referenced card (not per question overall, since cards can repeat query-relevant
rulings differently), at Haiku-scale pricing. Meaningfully more than §3.1's
near-zero, but bounded and cheap-tier.

**Failure mode:** adds a second moving part (and a second place variance can enter
— an LLM reranker has its own noise, unlike the current deterministic cosine
selection which `docs/plan-rulings-on-demand.md`'s reproducibility section
explicitly values: *"the retrieval SELECTION [is] deterministic given frozen
embeddings; the answer text varies"*). A reranker breaks that determinism unless
pinned/cached carefully. Also the heaviest build of the three retrieval-only
options — a new component, not a constant change.

### 3.4 Cross-signal: promote a ruling that cites a rule id the main CR RAG already retrieved

**Mechanism as proposed:** if a card's ruling text cites a CR rule number that's
already in the question's retrieved CR-rule pool, that's a free relevance signal —
no extra retrieval call, just an intersection check between two things already
computed.

**Checked and largely doesn't apply as literally stated.** Scanned all 190
measured rulings (§2) for a CR rule-number pattern in the ruling text itself:
**0/190 contain one.** WotC's public rulings are written for players, in plain
English — they explain outcomes, they essentially never cite CR section numbers
by id. So "a ruling that cites a rule id already retrieved" is, on this evidence,
close to an empty set for literal citation-matching; this candidate as literally
specified would fire on close to zero cases in this repo's own eval cohort.

**A viable reframing exists, but it's a different (bigger) build.** The *spirit*
of the idea — cross-signal between the two retrievers — could still work if
reframed as **topical/semantic overlap** rather than literal id-citation: does a
ruling's embedding also score highly against the *text* of a CR chunk the main
RAG already retrieved for this question (not "cites the id," but "talks about the
same rule")? That's no longer free — it's an extra cosine comparison per
(ruling × retrieved-CR-chunk) pair, still cheap (embeddings, no LLM call) but a
real new computation, and a real new component with its own calibration question
(what similarity threshold counts as "the same topic"). Precedent exists in this
repo for a similar-shaped idea on the *rules* side only: `docs/plan-
l1-crossref-expansion.md` Part A already does deterministic CR-to-CR cross-ref
expansion (following literal "see rule X" mentions *inside retrieved CR text* to
pull in missed CR chunks) — and that shipped but measured a **null result** on
its own target class (*"none of the 5 known misses were retrieval gaps (gold
already in pool)"*, LOG.md 2026-07-22). A ruling-to-CR cross-signal would be a new,
different mechanism (rulings don't carry the literal "see rule X" text CR chunks
do), but the sibling experiment's null result on the CR-to-CR version is a data
point worth weighing before investing here.

**Failure mode:** the "costs nothing extra" framing in the original ask doesn't
survive contact with the data for the literal version (citation-matching — near
dead on arrival, 0/190). The topical-overlap reframe is plausible but is honestly
a distinct, uncosted, uncalibrated new build, not a free win.

## 4. How this would be evaluated — the hard part

**No gold file for rulings retrieval exists in this repo.** Checked directly:
`evals/cards.jsonl` has no per-ruling gold field at all — only a CR `gold` field
(rule ids), and that field is empty on 13 of the 14 ruling-carried questions
(c006-c010, c012-c019 all have `"gold": []`). The one exception is c011 itself,
whose CR `gold` is `["702.85a"]` — but that's CR-rule gold, not ruling gold; it
scores whether the cascade rule was retrieved, and says nothing about whether
Valki's ruling 17 was. No field in `cards.jsonl`, on any row, points at a ruling
id. No `evals/*rulings*gold*` or similar tracked file exists.
DECISIONS.md says so explicitly: *"Deferred / not done: the 'cite the ruling by
id' step (rulings-recall is measured off `last_ruling_selection` instead for
now)"* — i.e. the citation-based recall metric that was planned
(`docs/plan-rulings-on-demand.md` §"Grounding reinforcement", `contracts.py:344`'s
`# L8: enables the rulings-recall metric` comment) was never wired up as a scored
metric.

**What does exist, and its limits:** a hardcoded Python dict,
`LOAD_BEARING_RULINGS` (`evals/run_openrouter_arm.py` lines 82-97), mapping 14
question ids (c006-c019) to `{card_name: [load_bearing_ruling_indices]}`,
hand-transcribed from each question's Jon-authored `cards.jsonl` `note` field. This
is real, useful, Jon-sourced ground truth — it's what powered the §3.2 union-arm
measurement above and it's the closest thing to rulings-recall gold in the repo.
But it is **not** a tracked, reusable gold artifact: it lives inline in one
one-off measurement script (`ruling_query_report`), isn't validated/versioned the
way `cards.jsonl`'s CR-rule `gold` field is, isn't read by the main eval/scoring
pipeline (`run_answer_eval.py`, the verdict files), and only covers 14 of 20 card
questions (nothing for c001-c005/c020, correctly, since those have no rulings).

**What a real rulings-recall instrument would need, if Jon wants one built:**
1. **Promote `LOAD_BEARING_RULINGS` to a tracked file** (e.g.
   `evals/rulings_gold.jsonl`, one row per question-card pair, same shape it
   already has), reviewed the way `cards.jsonl`'s `gold`/`note` fields are, so it
   stops being a fact embedded in one script.
2. **A recall@k-style metric**, run the same way rules recall@k already is: for
   each question-card pair with load-bearing ruling indices, did selection
   (`select_rulings`/whatever replaces it) include all of them? Report per-row
   and aggregate, the same shape `ruling_query_report` already computes
   informally.
3. **A generation-level check, not just retrieval-level** — §3.2 is the concrete
   lesson here: the union arm *won* at the retrieval-recall layer (16/25 → 20/25)
   and *lost* where it counts (graded correct-counts on the two strongest
   generation arms). Any future candidate from §3 needs both numbers before a ship
   call, not retrieval-recall alone.
4. **More cases than c011 alone.** The current gold (14 rows) is a reasonable
   start but is itself hand-authored by one person for one purpose; widening it
   (more cards, more question shapes) would make the metric less exposed to one
   question's idiosyncrasies — directly relevant to §5 below.

None of this is proposed as work to start tonight — it's what "evaluated properly"
would require, laid out so the decision to build it (or not) is Jon's, informed.

## 5. Interaction with c011's frozen status — read this before acting on this plan

`docs/plan-c011-stale-rulings.md` recommends **freezing c011** (§5.2: *"c011 itself
stays exactly as-is... frozen, the same way c002 was frozen"*) because it's a
scored question carrying verdicts in three tracked files
(`evals/verdicts_v3ab.json`, `evals/verdicts_v4e.json`,
`evals/verdicts_gpt-5-mini_final.json`), and Jon's established precedent (c002 →
c020) is: don't retroactively edit a graded question's inputs, add a fresh id
instead.

**This plan must not be validated by making c011 pass.** c011 is the single case
that *motivated* this investigation — it's a real, concrete, confirmed instance of
the hard-cutoff problem, and it earns the right to trigger this design doc. But
it is exactly the wrong metric to validate a fix by, for the textbook reason:
**fitting a change to the one case it was designed around, then citing that same
case as proof it worked, is circular.** If a future retrieval change is tuned
until c011's ruling 17 clears the cutoff, and that's reported as the change's
success, the "measurement" would be indistinguishable from curve-fitting to a
single known answer. A rulings-recall fix needs to be checked against **c010 and
c019 too** (the two other confirmed misses, per the same code comment) at minimum,
and ideally against the broader instrument in §4 — not against c011 alone, and
never by re-scoring c011 itself (which stays frozen regardless, per the other
plan).

## 6. Non-goals

- Not proposing to change `COSINE_FLOOR`, `TOP_N`, or any selection parameter
  tonight — this is options-on-the-table, not a chosen direction.
- Not proposing to ship `ruling_query_mode="union"` — already measured and
  rejected by Jon's own pre-commitment (§3.2); re-raising it isn't this plan's
  point, understanding why it failed is.
- Not proposing any change to `evals/cards.jsonl`, any `verdicts_*.json`, or
  c011's retrieved content — c011 stays frozen per
  `docs/plan-c011-stale-rulings.md`.
- Not building the §4 gold-file/metric tonight — laid out as a prerequisite for
  evaluating any of §3's candidates properly, not proposed as tonight's work.
- Not claiming any of §3's candidates would fix c011, c010, or c019 — none were
  measured against real embeddings in this session (paid API, out of scope); §3's
  cost/failure-mode analysis is structural, not empirical-per-candidate.
- Not touching `src/rulesagent/retrieve/rewrite.py`, `generate/answer.py`,
  `generate/openrouter_backend.py`, or any judge-related file.

## What would change Jon's mind

- If Jon considers 3 known misses (c010/c011/c019) out of a 14-row informal gold
  not worth a build yet — reasonable, given no formal metric exists to size the
  problem precisely (§4). This plan doesn't argue urgency, only that the gap is
  real, structural (§2's distribution), and currently unmeasured beyond three
  anecdotes.
- If a quick, unpaid check of §3.1 (raising `TOP_N` alone, replaying already-
  cached embeddings if any exist, no new embedding calls) turns out to already be
  buildable cheaply without touching `COSINE_FLOOR` — worth a narrower follow-up
  plan scoped to just that.
- If Jon wants to fold this into the broader rulings-recall gold-file work (§4)
  as one combined effort rather than two plans — reasonable; flagged here as
  currently two separate decisions only because the diagnosis (this doc) and the
  instrument (§4) are separable pieces of work.
