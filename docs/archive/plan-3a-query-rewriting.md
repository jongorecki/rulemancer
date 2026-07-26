# Plan — #3a: Query-rewriting layer (Jon reviewed 2026-07-21)

Working Rule 0 artifact.

## Scope, stated plainly (Jon's clarification)

This rewrites the **user's question only**. The Comprehensive Rules corpus is
never touched — same 3,617 chunks, same embeddings, same vector index. The
layer sits between "what the user typed" and "what we send to the retriever."
Same corpus, better search key.

Two things Jon raised, split apart because only one is testable:

1. **Rewriting** — deterministic, runs with no user present, measurable in the
   eval. **In scope for #3a.**
2. **Clarifying questions back to the user** — **in scope, as a non-blocking
   side channel** (Jon's call; my first draft deferred this and he was right to
   push back). See below.

### Clarification: ask, but never wait

The rewriter **always** returns usable rewrites, even when it wants to ask
something. The clarifying question is an *optional extra field*, not a gate:

```python
class RewrittenQuery(BaseModel):
    original: str
    queries: list[str]           # ALWAYS populated — retrieval never blocks
    clarification: str | None    # optional; a question worth asking the user
```

That single design choice is what makes this testable:

- **In the eval**, `clarification` is recorded and ignored. Retrieval runs off
  `queries` exactly as measured. Nothing hangs waiting for a human who isn't
  there, and the numbers stay deterministic.
- **In the interactive demo (#4)**, the UI shows the question alongside the
  answer — "I assumed two-player; if you meant Commander, say so." The user
  gets an answer immediately and can refine.

So it is the *same code path* in both modes, which is the property my first
draft claimed we couldn't have.

**It also becomes a free measurement.** The eval logs which of the 31 questions
the rewriter flagged as ambiguous. If the flags correlate with the misses,
that's evidence the clarification is doing real work. If it flags questions
that answer fine, the prompt is over-triggering. Either way it's a number, not
a vibe — which is the standard everything else in this repo is held to.

**The real risk is over-triggering,** not under. An LLM given permission to ask
questions will ask constantly, and a bot that interrogates you before answering
"what does trample do?" is worse than one that just answers. So the prompt sets
a high bar: ask only when the answer would *materially differ* between readings
— player count (two-player vs multiplayer/Commander), which of two cards is
meant, a named format — and never for a question that has one correct answer
regardless. This is genuinely common in Magic, which is why it's worth having:
q014's remaining multiplayer nuance is exactly an ambiguity case, not a
retrieval bug.

**Success bar:** ≤ 5 of 31 eval questions flagged. More than that means the
prompt is too eager and gets tightened before this ships.

## The problem, stated from evidence

q016 ("can I respond to a cost being paid?") is the one WRONG answer in the
93.5%. It is a *retrieval* failure with a proven causal chain: the two
answering rules rank **189 (117.3c)** and **109 (601.2h)** for that query. No
reasonable k reaches them, so the generator honestly declines. The user's
words ("respond", "cost being paid") and the rules' words (priority; "casting
a spell is a single action" / payment happens inside 601.2 with no priority
window) barely overlap — not lexically, and apparently not in embedding space
either.

That is the textbook case for query rewriting: translate the question into the
corpus's own vocabulary *before* retrieval.

## Step 0 — the spike (cheapest possible falsification, do this FIRST)

Before building anything: hand-run a rewrite of q016's text through
claude-sonnet-5 with a general "translate into Comprehensive Rules
terminology" prompt, embed the result, and print the ranks of 117.3c and
601.2h.

- If they land in the top ~15 → the approach is validated, build the layer.
- If they still rank in the hundreds → **stop.** The problem isn't phrasing,
  it's that those rules are not semantically retrievable for this question at
  all, and the fix is something else (multi-hop from a cross-reference, or a
  rules-terminology glossary expansion). Report that instead of building.

This is one script and two API calls. It gates everything below.

### Spike RESULT (run 2026-07-21) — split verdict, build proceeds

| rule | baseline | best rewrite | outcome |
|---|---|---|---|
| 601.2h | 108 | **2** (sonnet, 3-rewrite set) | fixed, decisively |
| 117.3c | 198 | 69 (haiku, 3-rewrite set) | **not fixed** — most rewrites made it worse (300, 291, 219) |

**Why 117.3c can't be reached by rewriting.** Its chunk text is: *"Which
player has priority is determined by the following rules: If a player has
priority when they cast a spell, activate an ability, or take a special
action, that player receives priority afterward."* It never mentions costs,
responding, or timing windows — it describes who *retains* priority. It's a
correct gold answer only through a deductive hop (combine with 601.2h's
"casting is atomic" ⇒ no window during payment). Embeddings match meaning, not
inference, so no phrasing of the question gets there.

Confirming that the retriever isn't broken: `116.3` ("If a player takes a
special action, that player receives priority afterward") — near-identical
wording to 117.3c — ranks **9**. Retrieval finds that family fine; 117.3c just
isn't semantically about q016. Separately, rank **1** was `118.2` ("if a cost
includes a mana payment, the player paying the cost has a chance to activate
mana abilities"), which may answer the question better than either gold id.

**Jon's call (2026-07-21):** build the rewriting layer on the strength of the
601.2h result, and re-audit q016's gold separately. This deliberately
separates "is rewriting good?" from "is this label right?" — one questionable
gold shouldn't veto a layer with a measured 50x rank improvement, and equally,
a working layer shouldn't be used to justify quietly relabelling gold.

**Consequence for the success bar:** q016 is no longer the primary criterion
(its gold is under review, so it can't referee anything). Revised bars below.

### Second spike finding: fusing with the original HURTS

Not what the plan predicted. I argued that keeping the raw question in the
fusion was a safety property — a bad rewrite would degrade gently because the
original kept voting. Measured, the opposite:

| | best single rewrite | RRF(original + rewrites) |
|---|---|---|
| 601.2h | 2 | 10 |
| 117.3c | 69 | 145 |

RRF was worse than the best individual rewrite in **every** arm. The original
is a weak query — that's the entire premise of this slice — so fusing with it
drags good rewrites down. This is the Phase C hybrid finding again (fusion
dilutes when inputs differ in strength), and I walked into it after having
written that entry. Worth its own DECISIONS line.

**Design change:** the original is no longer automatically fused in. Whether
to include it becomes a measured arm (`+orig`) rather than an assumption.

## What gets built (assuming the spike passes)

### 1. `src/rulesagent/retrieve/rewrite.py`

`RewrittenQuery` goes in contracts.py — shape and rationale under "Clarification"
above (`original`, `queries`, optional `clarification`).

`rewrite_query(question, client, model) -> RewrittenQuery`

**Rewriter model: `claude-haiku-4-5`, measured against `claude-sonnet-5`.**
Rewriting is a small translation task, not the reasoning step — the generator
stays pinned to `claude-sonnet-5`. Cost is nearly irrelevant at this size
(~250 tokens in / ~100 out ≈ $0.0008 per query on Haiku at $1/$5 per 1M; all
31 eval questions cost about two cents, and Sonnet 5 at $3/$15 — $2/$10 intro
through 2026-08-31 — would still be under a nickel). **The real argument for
Haiku is latency**, since this call sits in front of every query in the #4
demo. So it's an eval arm, not an assumption: run the rewriter on both models
with retrieval held constant and report whether the cheap model is good enough.
Both are pinned, and rewrites are cached per-model, so this costs nothing on
re-runs.

Prompt (general, no eval-specific content — see anti-overfit below): rewrite a
casual Magic question into the vocabulary the Comprehensive Rules actually
use. Name the game concepts likely at issue (priority, the stack, zones,
steps and phases, timing, state-based actions). Produce N distinct rewrites
that attack the question from different angles. **No rule numbers** in the
output — a hallucinated number pollutes the embedding.

### 2. Retrieval with rewrites

Retrieve once per query string, then fuse with **RRF** (`rrf_fuse` already
exists from Phase C).

**The raw question is NOT automatically fused in** — see the second spike
finding above. My original argument (keeping it in is a free safety net) was
measured and found false: it dragged every arm down. Including the original is
now a measured variant (`+orig`), not a built-in assumption.

I also predicted RRF would do well here because, unlike Phase C, every input
is the same retriever at the same strength. That held *between rewrites* but
not once the original was mixed in — the original isn't an equal-strength
input, it's the weak query we're trying to replace. Same lesson as Phase C,
learned twice.

### 3. Eval plumbing

`run_eval.py` gains two arms next to the existing ones (nothing removed, so
every prior number stays comparable):

- `vec+rw1` — single rewrite, fused with the original
- `vec+rw3` — three rewrites, fused with the original

Rewrites are **cached to disk** keyed by `(model, prompt_version, question)`,
same discipline as the query-embedding and rerank caches, so re-runs make zero
API calls and the eval stays byte-reproducible. `prompt_version` in the key
means editing the prompt busts the cache automatically. The rewritten strings
then flow through the *existing* query-embedding cache unchanged — they're
just different strings.

### 4. `evals/run_answer_eval.py` — committed this time

The 31-answer generation that produced `data/parsed/review.json` was run
ad hoc and never committed. It gets committed now as a real script with a
`--rewrite/--no-rewrite` flag. Needed anyway for #4's "one command for a
stranger."

`RulesAgent` gains `rewrite: bool = True` so both arms are runnable.

## Anti-overfit guards (explicit, because the eval is only 31 questions)

1. The rewriter prompt contains **no** text drawn from the eval set — no
   question wording, no rule numbers, no MTG examples that appear in the 31.
   Few-shot examples, if any, are invented questions outside the set.
2. Success is defined **before** the run (below), not chosen after seeing it.
3. The per-question hit@5 matrix is the real report. An aggregate that goes up
   while three questions flip hit→miss is a regression, not a win.

## Success criteria (pre-committed)

Revised after the spike — q016 is demoted from primary criterion, because its
gold is under re-audit and a label being re-judged can't referee anything.

| Check | Bar |
|---|---|
| Aggregate (**now primary**) | recall@5 beats the 65% pure-vector baseline. Report the number whatever it is |
| Regressions | **zero** questions flip hit→miss at k=5. Any flip gets explained, not averaged away |
| q016 (informational) | 601.2h in top-15 — already proven in the spike. 117.3c is not expected to land and is not counted against the layer |
| Answer eval | no new wrong/partial vs the current 29/1/1. q016's verdict is held pending the gold re-audit |
| Reproducibility | two consecutive eval runs byte-identical, zero API calls on the second |
| Clarification rate | ≤ 5 of 31 questions flagged (higher = prompt too eager, tighten before shipping) |

If the aggregate rises but a regression appears, the honest outcome is
"rewriting helps case X and hurts case Y, here's why" — that's a better
DECISIONS entry than a clean win, and it's the kind of thing the Capgemini
conversation is actually about.

## Decided: always-on (Jon, 2026-07-21)

Always-on for now. The reasoning that supports it:

- Conditional needs a confidence signal (e.g. "rewrite only if top-1 cosine <
  threshold"). That threshold is a knob tuned on 31 questions — the single
  most overfittable thing we could add, and hard to defend in an interview.
- Because the raw question stays in the fusion, always-on's downside is
  bounded by construction.
- Simpler to explain, which is this project's whole thesis.

The honest cost of always-on, to report rather than hide: **+1 LLM call and
~1–2s of latency on every query**, on top of the ~150ms Voyage embed. If the
deployed demo in #4 feels slow, that's the moment to revisit conditional —
with a latency measurement to justify it, not a guess.

Also open, and I'd defer it: rewriting could be *cached at the app layer* for
repeat questions, which mostly erases the cost concern for a demo. Not now.

## Verification

- `uv run python evals/run_eval.py` — new arms in the table + per-question
  matrix; run twice to confirm identical output and no API calls.
- `uv run python evals/run_answer_eval.py --rewrite` (background, >120s) —
  regenerate 31 answers.
- Jon grades. To keep that cheap: the script reports which questions' top-15
  **changed at all**; unchanged retrieval means substance shouldn't move, so
  Jon reads the changed ones closely and spot-checks the rest.
- Existing 36 golden tests still pass (nothing upstream is touched, but prove
  it).

## Delegation (token economy)

Opus writes this spec and reads the numbers. A Sonnet subagent implements
`rewrite.py`, the two eval arms, the cache, and `run_answer_eval.py` against
this already-approved spec — it decides nothing about shape. Opus verifies by
running the eval and reading the per-question matrix, which is the part that
requires judgment.

## Out of scope for #3a

Multi-hop / cross-reference following ("see rule 704" → pull 704), and a
multi-turn loop where the user's clarification answer feeds back for a second
retrieval pass. The clarification *question* ships in #3a (one-shot, alongside
the answer); the conversational round-trip is a #4 UI concern. q014's remaining
multiplayer nuance stays open — the clarification field may address it, which
the eval will show.

## Eval arms, final list

Existing arms all stay so prior numbers remain comparable. New arms are a full
**2×2: rewrite count × rewriter model** (Jon's call — adding `rw1-sonnet`
completes the grid).

|  | 1 rewrite | 3 rewrites (RRF-fused) |
|---|---|---|
| **haiku-4-5** | `vec+rw1-haiku` | `vec+rw3-haiku` |
| **sonnet-5** | `vec+rw1-sonnet` | `vec+rw3-sonnet` |

Plus one variant, from the spike's second finding: **`+orig`** — the best cell
above, re-run with the original question fused back in. The spike says this
hurts; the eval confirms or refutes it across all 31 rather than on one
question. Cheap (no new LLM calls — the rewrites are cached; only the fusion
changes).

**Why all four and not three.** With only three cells, the two effects are
confounded: if `rw3-sonnet` beats `rw1-haiku`, that could be the stronger model
*or* the extra rewrites, and there's no way to tell them apart. The full grid
separates them — compare down a column for the model effect (count held fixed),
across a row for the count effect (model held fixed). If the two effects
interact (e.g. Haiku needs three tries to cover what Sonnet gets in one, which
is a genuinely plausible result), only the 2×2 shows it.

Decision rule, pre-committed: **ship the cheapest cell that isn't beaten.**
One rewrite over three (fewer calls, lower latency), Haiku over Sonnet (faster),
unless the grid shows a real gap. Marginal differences on 31 questions are noise
— I'll say so rather than crown a winner on a one-question spread.

Cost of the extra arm is negligible: ~$0.002 for the Sonnet pass over 31
questions, and it's cached, so re-runs are free.
