# Spec — CR gold mining on the subscription

Written 2026-07-25. Jon ruled: spec this now, run it in parallel with building
the effort / no-rewrite / model-override knobs (`docs/spec-effort-and-norewrite.md`).

Runs entirely on Jon's Claude Max subscription via Claude Code subagents.
**Zero API credits.** No dependency on the other spec; no shared files.

---

## 0. The billing boundary — the one rule that cannot be broken

Verified 2026-07-25: `~/.claude.json` has `billingType: 'stripe_subscription'`,
`organizationType: 'claude_max'`, no `primaryApiKey`; `ANTHROPIC_API_KEY` and
`ANTHROPIC_AUTH_TOKEN` are unset in the shell. Claude Code and every subagent it
spawns therefore run on the subscription.

**But `mtg-rules-bot/.env` contains `ANTHROPIC_API_KEY`.** Any Python script in
this repo that constructs an Anthropic client picks it up via `load_dotenv()` and
bills API credits.

Therefore: **the mining is done by Claude Code subagents using their own file
tools. No script in this repo may call the Anthropic SDK as part of this work.**
If a task here seems to need one, stop and report — do not write it.

`hasExtraUsageEnabled = True` on the account, so sustained heavy use can spill
into paid overage. Run batches **sequentially**, not as a wide fan-out, and
re-check after the calibration batch (§4) before scaling.

---

## 1. The gap this fills

`evals/questions.jsonl` holds **31** questions — the tuned Jon-31 set, the only
questions in the project with human-authored CR-rule retrieval gold (9 `all`,
1 `any`, rest default).

`report-rulesguru-holdout.md` establishes why that's the bottleneck:

- Held-out recall@50 is **63%** — but with one gold rule labeled per question,
  a "miss" can't be distinguished from a multi-rule question where a *different*
  correct rule was retrieved.
- RulesGuru is a **poor CR-rule-retrieval instrument** — 147/150 questions have
  cards, so oracle text confounds the signal.
- The place CR retrieval is actually load-bearing — pure-rules questions — is
  **3 questions** in RulesGuru. A held-out pure-rules set "does not exist yet."

So the target is **retrieval gold at scale**: for each question, which CR chunks
must be surfaced, and how they combine.

## 2. Scope boundary — retrieval gold, not answer gold

| may be proposed by a model | stays human-authored |
|---|---|
| `gold` — which CR chunk ids are relevant | `answer_gold` — what the correct answer is |
| `match` — any / all / groups | whether a proposal is accepted at all |
| `gold_groups` — the AND-of-ORs structure | the question set itself |

RulesGuru's answer gold is written by certified judges and outranks anything
generated here. **Nothing in this spec modifies `answer_gold`.**

**Jon's ruling, 2026-07-25 — no per-item approval gate at scale.** The mined
labels are accepted as correct without individual review, because these questions
**already carry judge-authored answers**. The model is not deciding what is
correct; it is tracing a known-correct answer back to the CR rules it rests on.
The human judgment stays the anchor — DESIGN.md's "do not delegate" concern is
about authoring correctness, and that is not what happens here.

**Operational consequence: the miner is given the judge-authored answer
alongside the question.** The task is "cite the chunks this answer depends on,"
not "work out the rules yourself." That is both more reliable and what makes the
assume-correct stance sound.

One honesty note for later write-ups, not a blocker: gold derived this way is
conditioned on the answer text. That is the right target for measuring
*retrieval* — it is exactly what the correct answer needed — but it must not
later be described as independent of the answers.

Mechanical validation still applies to every proposal (§4). That is a lint
against unretrievable ids, not a judgment call.

## 3. Output schema

Proposals land in `evals/gold_proposals.jsonl` (new file, gitignored until
approved), one object per question:

```
{
  "id":            "<existing question id>",
  "gold":          ["613.6", "611.3a"],      // flat union, always
  "match":         "any" | "all" | "groups",
  "gold_groups":   [["704.3"], ["704.5g","704.4"]],   // only when match=="groups"
  "rationale":     "<one or two sentences, why these rules and why this mode>",
  "confidence":    "high" | "medium" | "low",
  "proposed_by":   "claude-opus-5 (subscription subagent)",
  "batch":         "<batch id>"
}
```

Fields mirror `EvalQuestion` (`contracts.py:149-197`) exactly so an approved
proposal promotes without transformation. `match` semantics are the contract's,
not reinvented: `any` = alternatives, `all` = every id required, `groups` =
AND-of-ORs with `gold` holding the flat union.

## 4. The chunk-inventory constraint — read this before designing batches

`contracts.py:161` : *"a gold id must be a source_id that actually EXISTS as a
chunk — citing a folded label (e.g. '701.5' 'Cast', which has no chunk of its
own) can never be retrieved."*

A model given only the raw CR will confidently cite rule numbers that are not
retrievable chunks, and every one of those is a silently unusable label. So:

**Each mining agent is given the actual chunk `source_id` inventory as its
citable vocabulary, and is instructed that a proposal citing anything outside it
is invalid.** The raw CR text is context for judgment; the inventory is the
legal answer space.

Every batch is then validated mechanically against the inventory before it
reaches the review queue. Any out-of-inventory id fails that proposal — it is not
silently dropped, because a silently dropped id turns an `all` into a weaker
`any` without anyone noticing.

## 5. Batching

The CR is 976 KB / 160K words ≈ **250-300K tokens**. Opus 5's window is 1M, so a
full load fits with room for questions alongside. But Claude Code subagents do
**not** share a prompt cache, so every spawn re-reads it — batch size is the
entire cost model.

**Do not guess it.** Run one calibration batch first (§7 step 1), measure, then
choose. The open question is whether full-CR-load per batch beats targeted
`Grep` against the CR file; full load better serves "find ALL the gold rules,"
targeted grep is far cheaper. Calibration decides, on evidence.

## 6. Verification — we have 31 human-labeled answers to grade against

This is the part that makes the whole thing trustworthy, and it must run first.

**Blind reproduction test.** Run the miner on the 31 questions in
`questions.jsonl` *without showing it their existing gold*, then compare:

- exact `gold` set match rate
- `match`-mode agreement (any/all/groups)
- precision and recall on chunk ids (did it find Jon's ids; did it invent extras)
- every disagreement listed for Jon to read

**Not a blocking gate** (Jon's ruling, §2) — a sanity read. It costs almost
nothing, runs on 31 questions we already have labels for, and is the only cheap
signal that the miner is working as intended before a large batch. Report the
numbers; scale unless they are alarming.

This also cuts both ways honestly: a disagreement may be the miner finding a real
rule Jon's gold missed. Those are Jon's to read — per DESIGN.md item 4, reading
the failures is not delegated.

## 7. Execution order

1. **Calibration batch** — one batch, small, against the 31. Produces: the
   blind-reproduction numbers (§6), a measured per-question cost in subagent
   terms, and the full-load-vs-grep answer (§5).
2. **Jon reviews** the calibration result and rules on whether to scale.
3. **Scale** to the RulesGuru corpus in sequential batches, if approved.
4. **Approval UI** over `gold_proposals.jsonl`, following the existing
   approval-UI pattern, for promotion into `questions.jsonl`.

Steps 3 and 4 do not begin without step 2.

## 8. Out of scope

Answer gold of any kind. Modifying `questions.jsonl` directly. The pure-rules
question set itself (that's question *authoring*, DESIGN.md item 2 — separate,
and Jon's standing grant already covers how it's drafted). Anything requiring an
API call.
