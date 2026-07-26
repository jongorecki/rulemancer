# Handoff — the eval instrument was measuring the easy half of the problem

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-25 session, which built the effort knob, measured opus-5 at effort low
against sonnet, rebuilt the retrieval gold for the held-out 150, and found two
rules that had never been in the corpus at all.**

Suite is **554 passed, exit 0**. Seven commits: `579d544`, `314d6e4`, `c41a6f0`,
`a1892e9`, `8b94ef5`, `7a5ca03`, `9e41d7d`, `2d212a7`.

---

## ⚠️ FIRST, UNLEARN THIS

**1. "Retrieval is at 63% recall@50" was measuring one rule per question.**
Every one of the 1,409 RulesGuru rows is labelled `match: "any"`, while 83 of
the held-out 150 carry more than one gold id. So a question needing three rules
scored a pass on one. Re-labelled with real structure, the same retriever on
the same 150 questions splits like this:

| mode | n | groups that must ALL hit | @15 | @50 | @200 |
|---|---|---|---|---|---|
| `any` | 55 | 1.0 | **58.2%** | 65.5% | 81.8% |
| `groups` | 79 | 2.4 | **10.1%** | 22.8% | 35.4% |
| `all` | 16 | 2.2 | **0.0%** | 6.2% | 18.8% |

At production `TOP_K=15`, multi-rule questions are **essentially never
satisfied**. Retrieval is healthy at finding *one* relevant rule and close to
non-functional at getting two or three distinct rules into the window. That was
invisible under flat-`any` labels.

**2. Recall before and after the relabel is not comparable.** On the 134
questions both label sets can score: old@50 = 57.5%, v2@50 = 38.1%. Same
retriever, same questions — only the bar moved. Matching the old rate needs
**5-8x the depth** (old@15 = 43.3% needs v2 k=100). Do not report the drop as a
regression.

**3. Two rules were never in the corpus.** `606.5` (source line has no period
after the number) and `119.1d` (has an extra one). Both silently skipped by the
parser, both now fixed and appended to the index. `rg4420`'s judge answer quotes
606.5 verbatim, so that question was unanswerable by construction.

---

## THE ONE THING TO DO FIRST

**Grade the 68-row bucket-A arm and settle the model question.** The run is
complete at `evals/answers/opus5_low_norewrite_costbase.json` (68 rows,
opus-5 @ effort low, no rewriter, $5.04 total, **$0.0741/question**, zero
truncations, zero declines, zero uncited answers).

**The auto-judge finished: 51/68 = 75.0%**
(`evals/verdicts_opus5_low_bucketA.json`, frozen judge, digest
`b54fbdb95565abf8` **unchanged** — the instrument did not move, so this is
comparable to every prior number). Monotonic by difficulty, which validates the
labels and the judge together:

```
Level 1      9/9   100%      Level 3        9/15   60%
Level 2     30/39   77%      Corner Case    3/5    60%
```

**Against sonnet's 63.0%/66.7% BASE reps on the same bucket, judged by the same
frozen instrument, at 31% lower cost.** Opus-low is above both reps — but the
+8-12pt gap sits inside the measured 11% within-arm noise band, so it is
"clearly not worse, probably better", not proven better. Note also that several
variables differ from BASE (model, effort, rewriter off), so the delta cannot be
attributed to one.

**17 disagreements are waiting for Jon to read** — that is the remaining work on
this question, and it is not delegable. A grader is built at
`data/parsed/grading_opus5_disagreements.html`. Expect some to be judge errors:
Jon's earlier regrade of 42 sonnet misses recovered 8 (~19%), which would put
true accuracy nearer 78-80%. `rg104` is among the 17 and Jon has already
confirmed it genuinely wrong (a reasoning miss — the model cited `702.16d`,
which states both that the equip is illegal and that the Equipment unattaches as
an SBA, and still answered "stays attached").

---

## WHAT SHIPPED

**The effort knob** (`docs/spec-effort-and-norewrite.md`). `RulesAgent(effort=)`
→ `output_config={"effort": ...}`, validated at construction, recorded per row,
enforced by the resume guard. `None` default keeps the request byte-identical.
There was no way to express effort before this; every Anthropic call ran at the
API default, and cost is ~90% thinking tokens.

**`--rewrite-version none`** on both runners. `RulesAgent(rewrite=)` already
existed; `run_answer_eval.py` also already had `--no-rewrite`, which is the trap
— two independent switches for one behaviour meant a run file could record
`"v2"` for a run that never rewrote. Both now collapse to one derived truth
immediately after parsing.

**Structured gold for the held-out 150** (`evals/questions_rulesguru150_v2.jsonl`,
NEW file — `rulesguru.jsonl` is untouched, nothing moves until you point
something at v2):

```
match:    any 150         ->  groups 79, any 55, all 16
gold ids: 290 (1.93/q)    ->  497 (3.31/q)
existing gold preserved:      290/290 (100%)
```

Three opus subagents on Jon's **subscription** (no API credits), blind to the
existing gold but given the judge answers, so the task was tracing a
known-correct answer back to its rules. Then a placement pass resolved the 96
ids they hadn't independently found: 79 placed as alternatives inside an
existing group, 15 kept as not-load-bearing, 2 promoted to their own group.

**`evals/_chunk_inventory.txt`** — 3,619 real chunk source_ids, the closed
vocabulary the miners cite against. This is what makes the corpus auditable; it
caught 19 folded-parent labels before they became gold and found 11 already in
the 1,409-row corpus.

**Parser fixes + four coverage guards** (`tests/test_cr_parse_coverage.py`).
Both regexes now treat the trailing period as optional. The tests are the real
fix: rule-shaped lines all parsed, no numeric holes, **no gaps in subrule
letters**, no orphan subrules. The letter check is Jon's idea and the strongest
— it reads only parsed output, so it holds regardless of what a future
malformation looks like. It found `119.1d` on its first run.

**Apostrophe normalisation.** The CR uses U+2019 exclusively (2,995, zero
ASCII); questions and card names use ASCII exclusively. Three glossary chunks
carry it in their source_id, so a gold id written the way every question writes
it could never match. `normalize_source_id()` folds both sides in `hit_at`,
`hit_at_forced`, and the grading UI.

**Grading UI**, three passes: judge ruling shown under each answer; full card
text per face (cost/type/P-T/oracle) plus Scryfall rulings; gold rules rendered
**by match mode** with OR-groups as separate blocks and explicit ANDs.

---

## HOW JON WORKS (unchanged, load-bearing)

- **Rule 0: plan before code.** Every `plan-*.md` / `spec-*.md` is design-only
  until Jon rules.
- **USE SUBAGENTS.** Opus on the subscription for mining/analysis, Sonnet for
  scoped implementation against a written spec. Lead keeps judgment and talking
  to Jon. *If your harness forbids the Agent tool, say so immediately.*
- **THE BILLING BOUNDARY.** Claude Code and its subagents run on Jon's Claude
  Max subscription (`billingType: stripe_subscription`, no `primaryApiKey`, no
  API key env vars). But `mtg-rules-bot/.env` holds `ANTHROPIC_API_KEY`, so any
  Python in this repo that constructs an Anthropic client bills API credits.
  **Mining/analysis is done BY subagents with their own tools, never by a script
  that calls the SDK.** `hasExtraUsageEnabled = True`, so sustained heavy use
  can spill into paid overage.
- **Do-not-delegate:** eval questions, grading verdicts, **reading failures**.
  Jon ruled (2026-07-25) that mined *retrieval* gold may be accepted without
  per-item review, because the questions already carry judge-authored answers —
  the model traces a known-correct answer to its rules, it does not decide what
  is correct. That ruling does not extend to `answer_gold`.
- **Verify agents' claims yourself.** Every batch this session was
  re-validated independently; all passed, and the check is cheap.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR,
  Scryfall via `rulesagent.tools.scryfall.get_card`, or a live check. Model
  facts via the claude-api skill.
- **Verify by rendering.** UI work is screenshotted in a browser, not inspected
  as markup. Serve over `http.server`; **Jon runs the app on port 8000 — never
  bind or kill it.**
- Commit per slice on master, heredoc messages, `Co-Authored-By: Claude Opus 5`.
  `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Suite is `uv run pytest`.
  Never pipe a long run through `| tail`.

---

## THE LESSON TO CARRY

Last session's defects were *an index into an externally-owned list, persisted
as if it were an identifier*. This session found three more faces of it:

- **Two switches for one behaviour** (`--no-rewrite` vs `--rewrite-version
  none`) — the run file records one while the other governs. Caught before
  shipping, by the existing schema test printing the artifact.
- **Card ruling labels are 0-based.** `answer.py:1867/1873` build
  `[Card ruling #N]` with `enumerate(...)` and no `start=1`, so `ruling #4` is
  the FIFTH ruling. Numbering the UI 1..n would have shown the grader the wrong
  text. Verified against the live prompt before rendering.
- **Rule numbers are positions, not identities** — which is why a CR renumber
  would silently repoint gold at the wrong rule.
  `docs/spec-cr-update-check.md` proposes content fingerprinting, the same move
  `ruling_id()` already made for card rulings.

Also: **check an invariant against reality before asserting it.** A naive
consecutive-letter check flags 19 healthy rules, because the CR skips `l` and
`o` (they read as `1` and `0`). Against the real 24-letter alphabet, all 568
parents are gapless with zero exceptions.

---

## RESIDUALS / OPEN ITEMS

- **In flight when this was written:** the auto-judge on the 68 rows, and a
  subagent sharpening over-broad "header" gold on the 150 (67 questions cite a
  parent rule that has lettered children, e.g. `603.10`, `616.1`) writing to
  `evals/gold_proposals_headers.jsonl`. Check both; neither mutates existing
  eval files.
- **The header sweep covers only the 150.** 456 questions across the full 1,409
  cite a parent-with-children. Same job, bigger batch.
- **`rg4420` is parked at `606.4`** with low confidence. Now that 606.5 exists
  in the index, its gold should become `606.5`.
- **The 8-way retrieval experiment is NOT started** — see the next section. This
  is the highest-value open work.
- **Full-corpus mining** (the remaining 1,259 rows) projects to ~4.6M subagent
  tokens on measured rates (~3,600/question; caching does not help — the miners
  grep rather than re-read, and subagents don't share a cache).
- **Query-side apostrophe normalisation was measured and rejected**: no change
  at @1/@5/@10, +1.3pp @50. Not worth a corpus re-embed.
- **Jon's legality-gate prompt idea** ("first decide whether this is a legal
  sequence of play, then answer") — queued, deliberately NOT introduced during
  the model bakeoff. Size it first by counting how many of the 34 confirmed-wrong
  sonnet misses in `rulesguru_disagreement_verdicts.json` are "assumed an
  illegal action succeeded", then run it as a `SYSTEM_VERSIONS` arm.
- **`docs/spec-cr-update-check.md`** is written and unruled.

## WHAT TO DO NEXT (Jon's stated priorities)

1. **Grade the 68 / settle opus-low vs sonnet.**
2. **The retrieval-diversity experiment.** The mode-split says the problem is
   getting *distinct* rules into the window, not ranking. Jon asked for all
   three, separately and in every combination (7 arms + baseline): **MMR**
   diversity reranking, **hybrid BM25 + vector**, and **multi-query** union.
   All are retrieval-only — measurable against v2 gold with **zero generation
   spend**. MMR is the best first bet: cosine similarity clusters near-duplicates
   (`613.3`/`613.7a`/`613.8a` eat the window together) which is exactly what
   starves a groups question.
   **Do not just raise TOP_K**: at effort low, input tokens are ~55% of cost, so
   15 → 100 could double cost/question and erase opus-low's advantage.
3. **The model bakeoff** — deepseek-v4-flash ($0.09/$0.18, native effort,
   accepts temperature), gpt-5-mini Flex ($0.125/$1.00), sonnet-5 @ low as the
   single anchor (Jon: sonnet only at low), opus-5 @ low. **Grok is excluded on
   Jon's moral grounds — do not reintroduce it.** Every prior gpt-5-mini number
   was measured with `"reasoning": null`, so its 15-point deficit is untested.
   Resolve the rewrite dimension on *retrieval* first and the generation matrix
   halves.

## ENVIRONMENT & GOTCHAS

- **Cost, measured:** opus-5 @ effort low, no rewrite, bucket A =
  **$0.0741/question** (~22s). sonnet-5 at default effort = $0.096. **Sonnet's
  intro pricing ends 2026-08-31**, after which it is ~$0.144.
- **At effort low the cost model inverts:** output drops ~10x (1,270 mean vs
  sonnet's ~10.6k) so **input becomes the majority of spend**. Prompt caching is
  worth more than previously estimated, and TOP_K increases cost more.
- The vector index was updated by **appending** two embeddings, asserting the
  existing 3,617 vectors stayed byte-identical, so today's retrieval numbers
  remain comparable. Backup: `vector_voyage-4-large.pkl.bak-pre-606.5`. If a
  future change *removes* a chunk, rebuild instead of appending.
- `load_questions()` coerces unknown `kind` values to `"other"`, so
  `kind: "rulesguru"` loads fine. Constructing `EvalQuestion` directly does not.
- Chrome extension blocks `file://`; serve local HTML over `http.server`.
- Doc-metadata / token-economy rules live in `D:\Job_hunt\CLAUDE.md` and
  `Token-Economy-Policy.md`.
