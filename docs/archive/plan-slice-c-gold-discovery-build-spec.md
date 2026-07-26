**STOPPED before building. This is a build spec, not an executed proposal
batch. See §0 for why.**

# Build spec — Slice C, automated gold-rule discovery

Written 2026-07-23, in response to a task asking me to execute Slice C of
`docs/plan-v5-and-gold-discovery.md` if it is "unambiguous and Rule-0
approved," or stop and write a spec otherwise. It is not approved. This
document is the stop-and-spec deliverable.

## 0. Why I stopped instead of executing

Three independent, repo-sourced reasons, each sufficient on its own:

1. **`plan-v5-and-gold-discovery.md` line 1 marks the whole document DESIGN
   ONLY.** Verbatim: *"DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Three
   independently-approvable slices; each needs Jon's ruling on its own open
   questions before it starts."* Slice C's own open question (scope — see
   §5) was never resolved in the doc.

2. **The doc that superseded two of the three slices explicitly left Slice C
   out of the approval.** `docs/plan-v5-symbol-injection.md` line 1-2: *"Jon
   approved building from this on 2026-07-25 ('since all questions are
   answered, go ahead and start building')."* Line 6-8: *"Supersedes Slices
   A and B of `docs/plan-v5-and-gold-discovery.md` (Slice C, gold discovery,
   is untouched and stays queued)."* Jon's approval was scoped to A and B by
   name. Slice C was carved out, not carried along.

3. **Slice C's own Stage 2 needs a paid API call that this task forbids
   regardless of approval status.** The precedent Slice C explicitly reuses
   — *"reusing `ablate_gold.py`'s majority-of-N-trials machinery"* — is
   implemented with a live `anthropic.Anthropic()` client
   (`evals/ablate_gold.py` line 29: `import anthropic`; line 50:
   `client = anthropic.Anthropic()`). Slice C's Stage 2 asks for the same
   pattern against a candidate pool, run on gpt-5-mini, which is an
   OpenRouter call. This task's constraints say plainly: *"No paid API
   calls — Anthropic, OpenRouter, Voyage all forbidden."* Even with a
   hypothetical sign-off on scope, I have no compliant way to run Stage 2 in
   this session.

Given all three, guessing at scope and shipping a partial or wrong-shaped
tool overnight is worse than shipping nothing. This spec exists so the next
session — with Jon's scope ruling and a paid-API-permitted context — can
build Slice C without re-deriving any of the above.

## 1. What already exists in the repo that Slice C should reuse (verified by reading, not memory)

- **`evals/ablate_gold.py`** — the necessity-testing pattern Slice C's Stage
  2 explicitly extends. Functions: `load_cards()`, `generate(retrieved,
  cards, question) -> Answer`, `judge(question, reference, candidate,
  model) -> str`, `majority_different(...)`, `trials(retrieved, cards,
  question, n=TRIALS)`. `TRIALS = 3`, `JUDGE_MODEL = "claude-sonnet-5"`,
  `HAIKU_JUDGE = "claude-haiku-4-5"`. Docstring states the ceiling Slice C
  exists to lift: *"We ablate only the CITED rules... That makes ablation
  cheap and sound"* — and *"does NOT auto-write gold... encoding it is Jon's
  call."* Slice C's output contract must match this: propose, never write.

- **`src/rulesagent/retrieve/crossrefs.py`, `expand_crossrefs(retrieved,
  chunk_map, max_extra=5, debug=...)`** — the "existing L1 cross-reference
  expansion" Slice C's Stage 1 says to reuse is real and already shipped
  (wired into `RulesAgent.answer()` per `src/rulesagent/generate/answer.py`
  lines 1154-1156). Stage 1 does not need to build this; it needs to call it
  at a wider depth than production.

- **`src/rulesagent/index/store.py`, `VectorStore.search(query, k=10)` /
  `search_vec(qvec, k=10)`** — the sweep primitive for Stage 1's
  depth-100-200 candidate pool. No new retrieval code needed, only a wider
  `k` and multiple query formulations unioned.

- **`src/rulesagent/retrieve/rewrite.py`, `rewrite_query()`** — supplies the
  "each rewrite" query formulation Stage 1 calls for.

## 2. Current data shape (measured, not assumed)

Read directly from the tracked eval files in this worktree:

- `evals/cards.jsonl`: **20 card questions, 18 with `gold: []`.** The two
  with real gold: `c004` (`match: "groups"`, gold `["704.3", "120.5",
  "117.2d", "704.5g", "704.4", "120.6", "302.7"]`) and `c011` (`match:
  "any"`, gold `["702.85a"]"`). These two are the **only** available
  validation-gate targets — Slice C's own required gate (*"reproduce
  existing hand-curated gold on questions that already have it before it's
  trusted"*) has exactly two cards to prove itself against, not a larger
  held-out set. That constraint should be stated in the gate's report, not
  glossed over.

- `evals/questions.jsonl`: **31 rules-only questions, 0 with empty/missing
  `gold`.** Every rules question already has hand-curated gold; Slice C's
  scope question (§5) is therefore really about card questions, plus the
  handful of rules questions Slice C's own text calls "incomplete" (it does
  not name which — that's part of what needs Jon's ruling, since I found no
  rules-question `gold: []` to point at empirically).

## 3. Stage 1 — candidate generation (buildable now, no LLM, no approval blocker)

This half of Slice C has no paid-API dependency and no ambiguity in its
mechanism — only in *which questions to run it on* (§5). If Jon resolves
scope, Stage 1 alone is safe to build and run in a future session without
further design work:

```
evals/gold_discovery_stage1.py   (new, proposal-only, does not import
                                   cards.jsonl/questions.jsonl gold fields
                                   for writing — read-only)

def candidate_pool(question: str, cited_rules: list[str] | None,
                    k: int = 150) -> list[str]:
    formulations = [question] + rewrite_query(question) + (cited_rules or [])
    hits: dict[str, Retrieved] = {}
    for q in formulations:
        for r in store.search(q, k=k):
            hits[r.chunk.source_id] = r          # union, de-dup by id
    expanded = expand_crossrefs(list(hits.values()), chunk_map, max_extra=20)
    return ranked_ids(expanded)                   # widest pool, unscored
```

Output per question: a ranked list of rule-chunk ids (target ~50-150 after
union+expansion, capped to the top 20 by whatever ranking signal is chosen
before Stage 2 — cosine score, rerank score, or rank-fusion position; this
choice is itself worth a one-line decision from Jon since it determines
which 20 of ~150 survive to the expensive stage). **No LLM call. No answer
generation. No claim of correctness** — this stage only widens the net past
production top-k; it proves nothing on its own.

## 4. Stage 2 — necessity testing (blocked here; spec only)

Reuses `ablate_gold.py`'s `trials()`/`judge()`/`majority_different()` against
the Stage-1 candidate pool instead of the production top-15. Concretely:
generate a reference answer with the full candidate pool + card data (Jon
confirms it once, same as the existing ablation flow), then leave-one-out
over the capped pool (≤20 items), 3 trials each, majority-judged. Per Slice
C's own cost control: **gpt-5-mini, not sonnet** — "8x cheaper, adequate for
necessity testing" — which is an OpenRouter call and is exactly the call
this task's constraints forbid me from making. This stage cannot be built
*and run* in this session under any interpretation of the constraints; it
can only be specified, which this section does.

Cost, taken from Slice C's own estimate and not re-derived: O(candidates)
generations per question, pool capped at 20, so roughly (20 leave-one-out +
1 group-out + 1 full) × 3 trials ≈ 66 generations/question on gpt-5-mini.
For the validation-gate pair alone (c004, c011) that's ~132 generations —
cheap, but still a paid-API run that needs to happen in a session where such
calls are permitted.

## 5. Decisions Jon needs to make before anyone builds this (verbatim from the source plan, plus one I found)

1. **Scope** (Slice C's own open question, unresolved in the doc): all 18
   `gold: []` card questions, or only the ones implicated in Slice B's
   current miss lists (from `plan-v5-and-gold-discovery.md` §B2: `c012`,
   `c015` appear in the miss tables, but note — per §B6 of that same doc —
   `c012` and `c015` are flagged as cases where *"the answering rule is not
   in the frozen context at all,"* i.e. candidates Stage 1's wider sweep is
   specifically meant to test, not cases already known unfixable).
2. **Validation-gate bar**: with only 2 hand-curated card golds to reproduce
   (§2), what counts as passing — exact set match, superset containing the
   hand gold, or majority overlap? The source plan calls the gate
   "required" but does not define pass/fail.
3. **Stage-2 execution venue**: since this worktree cannot make the
   OpenRouter/Anthropic calls Stage 2 needs, does Jon want Stage 2 run in a
   different, API-permitted session against Stage 1's output, or does he
   want to revisit the "no LLM" framing (e.g., a cheaper necessity signal
   that doesn't need generation)?
4. **Candidate cap ranking signal** (§3, new — not in the source plan):
   which score selects the top 20 of ~150 union+expansion hits before Stage
   2 spends money on them.

## 6. What this session did NOT do

- Did not write, edit, or auto-populate any `gold` field anywhere.
- Did not run Stage 1 or Stage 2 against real questions — no candidate pool
  was generated, no ablation was run, no proposals with confidence scores
  were produced. There is nothing to review in the accept/reject sense this
  cycle; the artifact is scope, not output.
- Did not touch `evals/cards.jsonl`, `evals/questions.jsonl`, any
  `verdicts_*.json`, `_prompts_*.json`, or any file listed as owned by
  another agent.
- Did not modify Slices A/B or `plan-v5-symbol-injection.md`; both are
  out of scope per the task and untouched.

## 7. Non-goals (carried from the source plan, still true)

- No change to the frozen judge, ever.
- No auto-writing of gold — Slice C proposes, Jon encodes, and until scope
  and the validation-gate bar are set, Slice C does not even propose yet.
- No new generation model, no retrieval/TOP_K change, no `Answer` schema
  change.
