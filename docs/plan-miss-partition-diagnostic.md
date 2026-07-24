# Plan — miss-partition diagnostic: retrieval failure vs. reasoning failure

DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Awaiting Jon's review.

## 0. The question, and why it governs where effort goes next

For every graded miss (verdict `wrong` or `partial`), was the gold rule
**absent from the generator's context** (a retrieval failure — chunking,
embedding, rewriting, reranking, cross-ref expansion all become candidate
fixes) or **present and the model still answered wrong** (a reasoning
failure — those levers are close to worthless, and the fix belongs in
generation: prompting, notation, multi-step reasoning support)?

These two failure modes demand opposite engineering effort, and the project
does not currently know the split. Every retrieval-side plan on record —
L1 cross-refs, the rewriter bakeoff, rerank, chunk-context-split, the v5
symbol-injection programme — has been justified by recall@k moving, never
by a measurement of whether recall@k moving actually explains the misses
that remain. This diagnostic closes that gap. It is scoped as a read-only
measurement over data that already exists; no new eval run, no new prompt
variant, no model call.

## 1. Why it's urgent now, not eventually

`answer.py:32` — **`TOP_K = 15  # pure-vector top-15 (raised from 10:
near-miss rules like a`** / `# multiplayer clause at rank ~13 were just
outside the old window)`. Fifteen chunks is what the generator sees on
every production query today.

The shipped retriever (`vec+rw1-haiku`, `docs/report-rewriter-bakeoff.md`)
measures, over the 31-question `questions.jsonl` rules set:

| depth | recall |
|---|---|
| @5 | 71% |
| @10 | **87%** |
| @20 | **94%** |
| @50 | 100% |

Recall@10 already beats recall@5 by 16 points and recall@20 only adds
another 7 — the marginal chunk past rank 10 is mostly redundant coverage,
not new hits. At the generator's actual window (k=15, between the @10 and
@20 rows), gold is very plausibly in context for most rules questions
already. If most graded misses on that set turn out to be reasoning
failures rather than retrieval failures, every further point of retrieval
tuning is chasing a shrinking, largely-already-closed gap — and the
project's return on effort is in generation instead (cost/quality tradeoffs
there are `docs/plan-cost-calculator-tool.md`'s territory, written in
parallel; this document does not redesign it, only names it as where the
"it's a reasoning failure" branch routes to).

## 2. Direct supporting evidence already on record

**c014 is a confirmed reasoning failure**, not a hypothesis. Two separate
prompt programmes tried to move it and failed:

- **v4** (`DECISIONS.md`, 2026-07-25, "prompt v4 is NO-GO"): *"v4 also never
  moved **c014**, the mana-arithmetic failure the entire notation legend was
  built for — it got the model to **state** the cost breakdown correctly
  and still conclude wrong, which points at multi-step reasoning about cost
  modification rather than notation."*
- **v5** (symbol injection, the notation-legend candidate that superseded
  v4's static dictionary): built and measured, and c014's graded verdict in
  `evals/verdicts_sonnet-v2_final.json` is `partial` — not flipped to
  `correct` by either programme.

Two prompt-side interventions, aimed at two different theories of what was
wrong with the prompt, both left c014 unmoved. That is exactly the pattern
a reasoning failure produces and a retrieval failure does not: retrieval
was never touched by either intervention, so if the fix were "get the right
chunk in front of the model," neither v4 nor v5 could have found it. This
diagnostic exists to find out how many more misses look like c014, cheaply,
before committing more prompt-engineering cycles the way v4/v5 did.

## 3. THE BLOCKER — most of the eval set has no gold to test against

The diagnostic is nearly free to run for **rules questions**
(`questions.jsonl`, `rulesguru.jsonl` once run — see §7), which carry gold
ids. It **cannot** be run for card questions:

Measured directly against this worktree's `evals/cards.jsonl` (20 rows):

```
python -c "
import json
n=empty=0
for line in open('evals/cards.jsonl', encoding='utf-8'):
    line=line.strip()
    if not line: continue
    n+=1
    if not json.loads(line).get('gold'):
        empty+=1
print(n, empty)
"
# -> 20 18
```

**18 of 20 rows in `evals/cards.jsonl` have `gold: []`.** Retrieval quality
on card questions has therefore never been measured, because there is
nothing to measure it against — a row with no gold cannot be scored
"present" or "absent," it can only be skipped. And card questions are not a
side interest: **the entire v4/v5 symbol-injection programme targeted card
questions** (mana-cost notation only matters when a card with mana symbols
is in play). Two full prompt-engineering cycles were spent on the slice of
the eval set where retrieval quality is, today, unmeasurable and unmeasured.

This makes `docs/plan-slice-c-gold-discovery-build-spec.md` — already
committed, currently a stopped/spec'd build, not executed — **a
prerequisite for this diagnostic's card-question half, not a housekeeping
item that can happen whenever.** Until card gold exists, this diagnostic
runs on 31 rules questions and reports "no data" on 18 of 20 card questions,
which is itself the headline finding worth stating plainly rather than
quietly working around: the project's most recent and most expensive
generation-side investment (v4/v5) was aimed at the one part of the eval
set this diagnostic is structurally unable to check today.

## 4. The exact computation

For each graded row (a question id, scored under a specific arm/model):

1. Look up the row's gold ids (and `match` mode — see §4.3) from the
   question's source file (`questions.jsonl` / `cards.jsonl` /
   `rulesguru.jsonl`).
2. Recover the ordered list of chunk `source_id`s that were actually placed
   in that row's generator prompt (§4.1).
3. Test each gold id for membership, and if present, its rank within that
   ordered list (§5).
4. Emit one row of the output table (§6). Assign no verdict — the row is
   evidence, not a score (§6 again, stated plainly because it's easy to
   slide into scoring by accident).

### 4.1 Where "chunks actually in the prompt" comes from — the two candidate sources, and why one wins outright

**Candidate A — captured prompt files, `evals/answers/_prompts_*.json`.**
These store `{system, user}` as plain strings (confirmed:
`build_prompts_variant.py` line 14, *"`_prompts_C.json` stores only
{system, user} STRINGS, not the structured retrieved/cards/question inputs
that produced them"*). `_format_context()` (`answer.py:745-746`) builds the
rules-context block as
`"\n\n".join(f"[{r.chunk.source_id}] {r.chunk.text}" for r in retrieved)`,
and `build_prompt()` (`answer.py:749-813`) assembles the `user` string as,
in order: `"Rules context:\n{context}"`, then optionally
`"\n\nCard data:\n{...}"`, then an optional symbol-reference block, then
`"\n\nQuestion: {question}"`. So recovering the chunk list is: slice `user`
between the `"Rules context:\n"` marker and the next `"\n\nCard data:"` /
`"\n\nQuestion:"` marker (whichever comes first — same slicing pattern
`build_prompts_variant.py` already uses for the same file to splice in
injected blocks, so this is established practice in this repo, not a new
technique), then regex-extract every `\[([^\]]+)\]` at the start of a block
within that slice. Order of extraction is retrieval rank order, because
`_format_context` iterates `retrieved` in the order the pipeline produced
it — including cross-ref expansion (`expand_crossrefs`, called *before*
`build_prompt` in `RulesAgent.answer()`, `answer.py:1155`), so this source
sees the **actual final context window**, not just the pre-expansion
vector/rerank top-k. That matters: `expand_crossrefs` can add up to
`max_extra=5` chunks the raw top-`TOP_K` search never ranked, and a gold id
pulled in only by cross-ref expansion is a real "present" that a
pre-expansion source would report as "absent."

Slicing must anchor on structural markers (`"Rules context:\n"` /
`"\n\nCard data:"` / `"\n\nQuestion:"`), **not a bare bracket regex over the
whole `user` string** — the card-data block also uses square brackets for
card name references (`parse_card_refs`), so an unanchored scan would
false-positive-match `[Bog Glider]` as a chunk id. Rule ids also contain
`.` (a regex metacharacter: `"702.19b"`), so extracted ids must be
`re.escape()`d before being tested for membership, not compared as raw
regex.

**Candidate B — structured run rows in the answer-eval output
(`evals/answers/*.json`, produced by `run_answer_eval.py`).** Read directly
(`run_answer_eval.py:361-394`): each row stores `id`, `question`, `match`,
`answered`, `answer`, `citations`, `gold`, `gold_text`, `cited_text`,
`rewrite_queries`. **`gold_text` is `{g: chunk_map[g].text for g in
q.gold if g in chunk_map}` — a display lookup of gold ids against the
whole corpus, unconditional on whether that id was retrieved for this row.**
There is no field anywhere in this row that lists the chunks actually
placed in context. `self.last_retrieved` exists in-memory on the
`RulesAgent` instance during a run (`answer.py:1157`) but is never written
to the output row.

**Decision: Candidate A (captured prompt strings), because Candidate B does
not contain the needed information at all — this isn't a quality tradeoff
between two viable sources, it's the only source that has it.** The
honest cost of A: it's string-matching over free text rather than reading a
structured field, so it inherits whatever fragility that implies (a chunk
whose *text* happens to contain another chunk's `[id]`-shaped bracket
sequence — checked: `_format_context` only emits the bracket at each
chunk's own leading position, so a false match would require a rule's body
text to itself contain `[digits.digits]`, which the CR's prose style does
not produce, but this is asserted from reading the format function, not
verified against the actual corpus text, and should be spot-checked during
build). Recommendation for future runs, not this diagnostic: have
`run_answer_eval.py` additionally dump `last_retrieved` chunk ids as a
structured field. That is a one-line, low-risk change to the eval harness,
but it is code, so it is out of scope for this design-only document and is
listed again under §9 (non-goals).

### 4.2 Availability check — does Candidate A even exist to read?

`evals/answers/` is gitignored (confirmed:
`.gitignore` has no `evals/answers` line, but `git ls-files evals` lists
`evals/cards.jsonl`, `evals/questions.jsonl`, `evals/rulesguru.jsonl`, and
every `evals/verdicts_*.json` / `evals/verdicts_*.auto.json` /
`evals/verdicts_*.manual.json` — **zero files under `evals/answers/`**).
This worktree, checked directly, confirms the consequence: `ls evals/answers`
returns `No such file or directory`. **The prompt captures this diagnostic
depends on do not exist in a fresh clone or a fresh worktree — only on a
machine where they were generated and never cleaned up (most likely Jon's
main working checkout).** This is a scope-defining fact, addressed in §5.

### 4.3 Respecting `match` semantics, not just "is any gold id present"

`EvalQuestion.match` (`contracts.py:167-191`) is `"any" | "all" | "groups"`:
- `"any"` (default): gold ids are alternatives — one hit is a full pass.
- `"all"`: every gold id is required (true interactions, e.g. trample +
  deathtouch both needed).
- `"groups"`: an AND of ORs, via `gold_groups` — added because card-gold
  ablation found real mixed gold that `any`/`all` can't express.

A "gold present" verdict computed as a flat "any gold id found anywhere in
context" would silently misreport `match="all"` and `match="groups"`
questions — a question needing two rules where only one was retrieved would
show as "present" when the generator was actually missing half its
required material. The per-question row (§6) reports **presence and rank
per individual gold id** (or per group, for `"groups"`), and the headline
partition is computed honoring each question's own `match` mode: an
`"all"`-question only counts as "gold fully present" when every required
id is in context; a `"groups"`-question only counts as fully present when
every group has at least one member in context.

## 5. A third bucket: rank-within-window, not just membership

"Present" vs. "absent" collapses a real boundary case: gold that is in the
assembled context but ranked so low that if the pipeline had used a smaller
effective window (a future TOP_K decrease, a token-budget cut, a
reranker that reorders and truncates), it would fall out. A binary
present/absent split hides that fragility and could read a currently-passing
question as a stable retrieval success when it's actually a near-miss.

So the per-row output carries **rank-within-window** (the gold id's
0-indexed position among the chunks the prompt actually contained), not
just a boolean. This makes the boundary visible: a gold id at rank 1-3
is a comfortable pass; a gold id at rank 13-14 (inside `TOP_K=15` by a
hair) is a pass today that a two-chunk retrieval regression would flip to a
miss with zero change on the generation side. Reporting rank turns "how
close was this" into a number instead of an assumption, and lets a later
pass distinguish "retrieval is robust here" from "retrieval is currently
lucky here" — two situations that look identical under membership alone but
call for different responses (do nothing, vs. treat as a near-miss worth
tracking the way `near-misses.md`'s pattern already does for the job-hunt
tracker).

## 6. What it produces

A per-question table:

| qid | arm/model | verdict (from verdict file) | gold ids | match mode | present? (per-id) | rank (per present id) | fully-satisfies-match? |
|---|---|---|---|---|---|---|---|

...plus a headline split, computed only over graded **misses** (`wrong` /
`partial`):

- N misses with gold fully present in context (candidate reasoning
  failures — c014-shaped)
- N misses with gold partially present (some required ids in, some out —
  ambiguous, flagged separately, not folded into either bucket)
- N misses with gold fully absent (candidate retrieval failures)
- N misses with empty gold, not scoreable (the cards.jsonl 18-of-20, until
  §3's blocker is resolved)

**This is explicitly a diagnostic, not a score.** It assigns no
correct/wrong/partial verdict of its own — those already exist in
`evals/verdicts_*.json` and are Jon's to assign, not this tool's. The
diagnostic's only output is a classification of *why* an existing miss is a
miss, to route effort, not a re-grading of whether it's a miss at all.

## 7. Scope: which graded runs this actually applies to, given §4.2

**What's tracked and present in any clone (including this worktree,
verified directly):** every `evals/verdicts_*.json` /
`*.auto.json` / `*.manual.json` file, `evals/cards.jsonl`,
`evals/questions.jsonl`, `evals/rulesguru.jsonl`. These tell us **which
rows were graded, under which arm, and their verdict** — the "what" — but
never the chunks-in-context — the "why," which lives only in the untracked
prompt captures (§4.2).

**What's needed but not present in a fresh clone/worktree:**
`evals/answers/_prompts_*.json` and friends. Confirmed absent here.

**Consequence for scope:** this diagnostic can only run where both exist
together — which in practice means **Jon's main working checkout**, not a
fresh clone and not this worktree, because the prompt captures are
local build artifacts that were never committed and may or may not still
be on disk there. Before building, the executing session should `ls
evals/answers/` on the main checkout and report exactly which
`_prompts_*.json` files survive; the diagnostic's real coverage is bounded
by whichever verdict files have a matching prompt capture, not by which
verdict files exist. Verified present in this worktree as a baseline for
what "verdict data" looks like: `evals/verdicts_sonnet-v2_final.json` (50
rows: 19 cards questions — c002 is deliberately excluded from scoring per
`DECISIONS.md` 2026-07-25 — plus 31 rules questions; 4 misses: c012
`wrong`, c014 `partial`, c015 `partial`, q029 `wrong`). q029 is a known
non-retrieval failure mode in its own right (`docs/plan-q029-empty-answer-
guard.md`: an empty-answer generation bug, not a rules-content miss) and
should be flagged as such rather than forced into the retrieval/reasoning
partition — a third "not applicable" tag alongside the two failure modes,
for misses the partition's own premise doesn't fit.

Other tracked verdict files (`verdicts_v3ab.json`, `verdicts_v4e.json`,
per-model `verdicts_*.auto/manual/final.json`) cover additional
arms/models (deepseek, gpt-5-mini, gemini-flash-lite, sonnet, across v3ab
and v5 conditions B/C/D). Each is in scope **only if** a corresponding
`_prompts_*` capture for that exact arm survives locally — this plan does
not assume it does, and the build step should enumerate the actual
intersection rather than assuming full coverage.

## 8. Extension to RulesGuru

`evals/rulesguru.jsonl` — 150 rows, measured directly (`134` with
non-empty `gold`, matching the task's stated figure; the remaining 16 are
presumably scenario questions the human curators judged as not resolving
to specific CR citations). Gold ids are CR rule numbers in the same format
as `questions.jsonl`/`cards.jsonl` (e.g. `["810.1", "810.5"]`) and resolve
against the same parsed CR — confirmed `Chunk.source_id` (`contracts.py:105`)
is the field name gold ids must match, not `rule_id`; there is no
`rule_id` field on `Chunk` to confuse it with.

This diagnostic's computation (§4) is source-agnostic to which question
file the gold came from — it only needs `{id, gold, match, gold_groups}` —
so extending to RulesGuru is a data-availability question, not a design
change: **RulesGuru has never been run through `run_answer_eval.py`**
(confirmed: no `verdicts_rulesguru*.json` exists among tracked verdict
files, and `DECISIONS.md`'s 2026-07-22 import entry describes import and a
planned judge, not an executed run). So RulesGuru is prospective for this
diagnostic, gated on a run existing at all — cross-reference
`docs/plan-rulesguru-as-instrument.md` (written in parallel) for whether
and how that run happens; this document does not redesign that decision,
only notes that once RulesGuru has graded rows and prompt captures, this
diagnostic applies to it unchanged.

## 9. Non-goals

- Not a retrieval fix. It routes effort; it does not implement reranking,
  rewriting, chunking, or crossref changes.
- Not a new eval run, arm, or prompt variant. Read-only over what already
  exists.
- Not a re-grading of existing verdicts. Verdict files are read, not
  written.
- Not a change to `run_answer_eval.py` to add structured `last_retrieved`
  logging (§4.1's recommendation) — that's real, low-risk code, flagged for
  a future session, out of scope for a design-only document.
- Not a resolution of the cards.jsonl gold gap (§3) — that's
  `plan-slice-c-gold-discovery-build-spec.md`'s job. This document only
  states the dependency.
- Not model/API work of any kind. No paid calls anywhere in this design.

## 10. The honest limit — "gold in context and still wrong" is not proof

Finding gold present in context for a miss is evidence toward "reasoning
failure," not proof of it. Three ways that inference can be wrong, stated
rather than glossed:

1. **Gold present but insufficient.** The gold id being the *closest*
   matching chunk doesn't mean it's *complete* — the question may need
   information the gold chunk doesn't carry (this is exactly what
   card-gold ablation's mixed-gold discovery already found for `match:
   groups` questions, §4.3). "Present" only tests the ids the eval set
   author already decided were the right ones; it can't detect that the
   gold set itself is incomplete.
2. **Question ambiguity.** Some misses are the judge or Jon disagreeing
   with the model on a genuinely arguable ruling, not the model failing to
   use material it had. c002's exclusion (`DECISIONS.md` 2026-07-25) is a
   documented instance of a question turning out to be a weak instrument
   for reasons unrelated to retrieval or reasoning quality at all.
3. **The gold *chunk* may not contain the part of the rule that
   matters.** Chunking is at the sub-rule level (`plan-chunk-context-split.md`);
   a chunk can carry a rule's `source_id` while a sibling or parent chunk
   carries the clause the question actually turns on. "Gold chunk present"
   is chunk-level, not clause-level — a genuine retrieval failure can hide
   inside a "present" verdict if the diagnostic's gold labeling is coarser
   than the reasoning the question requires.

Because of this, §6's headline split is a **prioritization signal, not a
final verdict**: it tells you where to look first (reasoning-shaped misses
get a prompt/generation review; retrieval-shaped misses get a retrieval
review), not a guarantee of what you'll find when you look. Any row this
diagnostic calls a "candidate reasoning failure" should still get an eyes-on
read of the actual chunk text before design effort is committed, the same
way c014 was — this tool would have flagged c014 as a candidate; a human
still had to read the mana-cost chunk and confirm it was there and correct
before concluding the model's arithmetic, not its inputs, was the problem.

## 11. What would change Jon's mind (open questions for review)

- **Source-of-truth risk (§4.2/§5):** if the prompt captures this depends
  on turn out not to survive on the main checkout either, this diagnostic
  has no data to run on until a future eval run is re-executed with
  captures saved deliberately. Worth confirming what's actually on disk
  before treating this as buildable next.
- **Rank threshold (§5):** is there a rank Jon wants flagged as "near-miss"
  (e.g. within 3 of the window edge), or should the raw rank number alone
  be the deliverable with no threshold baked in?
- **q029-shaped rows (§7):** should generation-bug misses (blank answer, no
  citations) be silently excluded from the partition, or surfaced as an
  explicit third bucket the way this draft proposes? Affects the headline
  count's denominator.
- **Scope of "graded runs" (§7):** run this against the sonnet production
  arm only first, or attempt every arm whose prompt capture happens to
  survive? Affects how much of §7's uncertain intersection needs resolving
  before a first result exists.
- **Priority vs. `plan-slice-c-gold-discovery-build-spec.md` (§3):** given
  the blocker, does Jon want this diagnostic run now on the 31-question
  rules-only slice as a first, partial read — or held until Slice C
  unblocks card-question coverage so the first read is complete rather than
  partial?
