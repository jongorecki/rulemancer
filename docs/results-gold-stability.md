# Results — gold prompt-drift: mined gold moves 0.54 mean overlap when the miner's prompt changes, and the same-prompt number doesn't exist yet

Zero API spend. This re-analyzes data already on disk —
`evals/gold_proposals_full_b09.jsonl` (run A, 50 rows, mined under prompt
**v1-trimmed**) against `evals/gold_proposals_full_b09_rerun.jsonl` (run B,
the same 50 question ids re-mined under prompt **v1 restored**). Both were
produced by Claude Code subagents on Jon's subscription per
`docs/spec-cr-gold-mining.md`; no script here called the Anthropic SDK.
Analysis script: `evals/_double_mine_stability.py`. Per-row detail:
`evals/_double_mine_stability_rows.json`. Neither canonical gold file was
touched.

**This is not the requested measurement, and that has to be said up front.**
The task was "mine the same questions twice under the same conditions and see
how much the gold agrees with itself." `gold_miner_prompt.md:21` states
outright what this pair actually is: **"`b09_rerun` re-mines b09's exact
questions under v1 to test whether the drift was caused by the wording or by
the questions."** Run A used **v1-trimmed** (line 18: "accidental:
justification clauses dropped from rules 1 and 3. **Do not reuse**"); run B
used **v1 restored**. So this pair varies two things at once — the prompt
wording *and* whatever run-to-run sampling noise the miner has regardless of
wording — and one pair cannot separate them. **0.5407 mean overlap here
measures prompt-drift-plus-noise combined, not self-agreement under a fixed
prompt.** A true same-prompt, same-questions stability number does not
currently exist on disk anywhere in this repo (search covered `evals/` and
`data/parsed/` in full). See "What it would take" below for what producing
one requires.

## The number, correctly attached

Mean per-question overlap (Jaccard, `|A∩B| / |A∪B|` over gold rule-id sets)
across the 50 shared question ids: **0.5407**. This closely matches the
figure already recorded in `docs/results-derivability.md` ("mean overlap
0.54") — worth flagging plainly rather than as reassurance: **that prior 0.54
almost certainly comes from this exact same b09/b09_rerun pair** (same file
names, same stated purpose, same 50-question control-run description in the
commit that introduced it). A number reproducing itself from the same
underlying data is not independent confirmation of anything — it's the same
measurement read twice. It doesn't tell us whether 0.54 is "prompt drift" or
"pure noise" or some mix; it only tells us this pair produces 0.54
consistently, which was never in doubt.

## The shape of disagreement — order vs content

Regardless of what's driving it, the shape of the 0.54 is worth recording
accurately, because it rules out one easy explanation (that the number is
inflated by cosmetic reordering).

| category | rows | share |
|---|---|---|
| **Identical gold set** (same ids, any order) | 13 | 26.0% |
| — of which: fully identical (ids, group structure, list order all match) | 12 | 24.0% |
| — of which: same ids, only list order differs (`rg776`) | 1 | 2.0% |
| — of which: same ids, `gold_groups` structure differs | 0 | 0.0% |
| **Genuinely different rule sets** | 37 | 74.0% |
| — of which: same *count* of ids, different members (substitution) | 18 | 36.0% |
| — of which: different *count* of ids (one run adds/drops an id) | 19 | 38.0% |
| — of which: share zero ids (`jaccard = 0`) | 6 | 12.0% |

**Order-only disagreement is almost nonexistent (1/50, `rg776`)**: both runs
cited `{613.7, 701.3b, 701.3c, 613.7e}`, just serialized in a different
sequence, with 0 rows keeping the same flat set but grouping it differently.
So whatever combination of prompt-drift and noise produces the 0.54, it is
not being padded by cosmetic relabeling — when a row disagrees, the rule set
is actually different.

Match-mode agreement (`any` / `all` / `groups`) is **38/50 = 76.0%**, and
there's a distributional shift worth flagging on its own: run A (v1-trimmed)
picked `groups` 33/50 times and `any` 17/50; run B (v1 restored) split it
25/25. That shift is a plausible signature of the prompt difference — v1's
restored justification clauses on rules 1 and 3 may be pushing the miner
toward flatter groupings — but with one pair this is a hypothesis, not a
demonstrated cause.

The Jaccard distribution is bimodal, not a smooth spread:

```
jaccard = 0.00  (share nothing)     6 rows  (12%)
jaccard = 0.01-0.34                13 rows  (26%)
jaccard = 0.34-0.67                18 rows  (36%)
jaccard = 1.00  (identical)        13 rows  (26%)
```

Nothing sits strictly between 0.67 and 1.0 — no population of
"almost-identical, one extra citation" rows just below full agreement. When a
question isn't reproduced exactly, it tends to land at 0.2-0.5, not 0.9.

## The more useful finding: exact-id Jaccard penalizes citation granularity

Spot-checking the 6 "share nothing" rows against the actual CR text
(`data/raw/MagicCompRules 20260619.txt`) shows the zero-overlap number is
partly an artifact of the metric, not proof the runs disagree on substance.

Example — `rg662` ("Can Aden pay 1 life to add {C} via Channel while a
Phyrexian Revoker names Channel?"): run A cited `["605.1a", "113.3b"]`, run B
cited `["602.1", "605.1"]`. Zero string overlap, Jaccard 0. Grepping the CR
directly:

- `113.3b` and `602.1` are both the *activated-ability* definition (602.1 is
  rule 602's own restatement of 113.3b's activated-ability description).
- `605.1` and `605.1a` are both the *mana-ability* definition — 605.1 is the
  parent rule, 605.1a the specific activated-mana-ability criteria clause
  nested under it.

Both runs converged on the same two concepts (what makes something an
activated ability; what makes something a mana ability) and each picked a
different sibling or parent/child rule number to cite it with. Exact-id
Jaccard scores that as complete disagreement (0.0) when the underlying
reasoning agrees completely — the metric can't see that `605.1` and `605.1a`
are the same family, or that `113.3b` and `602.1` say the same thing from two
angles.

**This means 0.5407 is very likely a lower bound on real agreement, not a
point estimate.** A hierarchy-aware metric — one that credits a parent/child
match or a same-parent sibling match at some partial weight instead of 0 —
would very likely land above 0.54, possibly well above it given how many of
the 37 "different" rows involve numerically adjacent ids (`508.1` vs
`508.1a`, `708.2` vs `708.2a`, `603.10` vs `603.10a` all appear in this same
50-row sample).

**Proposing the metric, not computing it — this needs Jon's ruling, not
mine:**

- Build an adjacency table from the CR's own numbering structure (e.g. `X.Ya`
  is a child of `X.Y`; ids sharing the same `X.Y` prefix are siblings) —
  `_chunk_inventory.txt` already enumerates every real chunk id, so the
  parent/child/sibling relationships can be derived mechanically from that
  list without new mining.
- Define partial credit per relationship type — e.g. exact match = 1.0,
  parent/child = some weight *w1* < 1.0, sibling-under-same-parent = some
  weight *w2* < 1.0, unrelated = 0. **The actual weights are a judgment call
  about how much citation-granularity should "count" as agreement, and that
  is explicitly Jon's call, not something to default on.**
- Re-run the same 50-row comparison through the weighted metric and report
  both numbers side by side (exact-id Jaccard vs hierarchy-aware), so the
  gap itself becomes visible rather than one number silently replacing the
  other.
- This is pure local compute once the weights are chosen — no new mining, no
  API spend, just a second pass over the same two files with an adjacency
  table.

## What it would take to get the actually-requested number

A true same-questions, same-prompt, twice measurement needs a **fresh mining
pass**, and per `docs/spec-cr-gold-mining.md` §0 that labor has to come from
Claude Code subagents on Jon's subscription, never a script constructing an
Anthropic client — so this is not something to run without sign-off, and not
something a Python script should do.

- **Which prompt:** the current version, `v2` (`gold_miner_prompt.md`, "b10+
  ... v1 text restored verbatim, plus rule 6"). Re-running under a retired
  prompt (v1 or v1-trimmed) would answer a question nobody's asking anymore.
- **Which questions:** the cleanest choice is 50 questions **already mined
  under v2** (batches b10 and later, once they exist — none of b01-b09 are
  v2), re-mined a second time blind, so both runs share the same prompt and
  only sampling varies. Alternatively, mine 50 *new* v2 questions twice from
  scratch — costs the same either way since both runs must happen regardless
  of whether one "already exists."
- **Cost:** two mining batches of 50 questions each, run sequentially per
  `spec-cr-gold-mining.md` §0's overage caution (not fanned out in parallel)
  — roughly the same subagent-labor cost as one of the existing
  `gold_proposals_full_b0X` batches, times two. No dollar figure in API
  credits; this bills as subscription usage, and per Jon's standing
  preference that's the intended path, not a cost to avoid — it just isn't
  something to launch without his go-ahead given the "run sequentially,
  re-check before scaling" guidance in the spec.
- **Gate:** needs Jon's go-ahead before running, both because it's real
  subagent labor (not free compute) and because the question-set choice above
  is itself a judgment call.

## Caveats

- **(a) This pair is a cross-prompt comparison, not a same-prompt replicate.**
  Stated up front above — repeating it here for the caveat list's sake: run A
  = v1-trimmed, run B = v1 restored. Any framing of 0.5407 as "the miner
  agrees with itself ~54% of the time" is not supported by this data; the
  supported claim is "gold moved this much across this specific prompt edit,
  confounded with ordinary run-to-run noise, whatever that noise floor
  actually is."
- **(b) N = 50, one pair.** No wider sweep was run — doing so costs real
  subscription-subagent labor and wasn't authorized here.
- **(c) Both runs predate rule 6** (the merge-rule fix from the 2026-07-26
  adversarial review). `gold_miner_prompt.md` records that b01-b09 batches
  contain conjunctive OR-groups wrongly merged in ~5/9 sampled multi-member
  groups. That's a separate, already-tracked defect (recall is measured
  optimistically until fixed) and is orthogonal to this measurement — it
  would affect both runs equally and shouldn't bias the overlap number either
  way, but it means neither run A nor run B here is "clean" gold on its own.
- **(d) Conditioned on the judge-authored answer.** Per the mining spec, both
  runs were handed the correct answer and asked to trace it to CR ids, not to
  solve the question blind. Whatever instability exists here is "which ids
  trace a known-correct answer," not "can the model find the right rule from
  scratch" — a harder, differently-shaped task that could be more or less
  stable.
- **(e) No git commit / push / checkout was performed**, and no canonical
  gold file (`questions.jsonl`, `rulesguru_full_v2.jsonl`,
  `gold_proposals_full_b09*.jsonl`) was modified. The only new files are this
  doc and the two `_double_mine_stability*` analysis artifacts in `evals/`.

## What this doesn't cover

- **The actually-requested number**: same questions, same prompt, mined
  twice. Does not exist on disk. See "What it would take" above.
- A hierarchy-aware overlap metric. Proposed above, not computed — the
  partial-credit weights are Jon's call.
- Whether instability is worse on harder questions (`level`/`complexity` was
  not joined against overlap here — 50 rows is thin to slice further without
  overfitting the read).
- Any claim about which of run A / run B is "more correct." Nothing here
  compares either run against human-authored gold; `evals/_gold_disagreements.json`
  (comparing one blind mining pass against Jon's 31 hand-labelled questions)
  is the relevant document for that question, and it's a different comparison
  from this one.
