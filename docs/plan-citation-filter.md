# Plan — Post-hoc citation filter (Rule 0 mini-plan)

DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Awaiting Jon's review.

## The commitment, and its partial discharge

**Origin (`DECISIONS.md:1343-1351`, "2026-07-23 — Four pre-commitments while
grading the v3 A/B queue").** While signing off the groundedness tripwire as
acceptable (not a no-go), Jon queued a follow-up as pre-commitment #1:

> "5 questions / 7 instances / <1%, scattered, not the 1c-multiplayer spike
> the rule was written for. PLUS a follow-up slice queued: read the 7
> answers, determine whether a prompt tweak or a post-hoc citation filter
> could zero them out (**mini-plan needed, Rule 0**)."

**Partial discharge (`DECISIONS.md:1456-1476`, "2026-07-24 — groundedness
follow-up does NOT enter prompt v4").** Jon read the 7 instances and ruled
out the *prompt-tweak* half: v4 ships with no groundedness-targeted bullet,
because the evidence doesn't support spending v4's prompt-change window on
it — the 4 instances still in the decision set aren't one failure class, and
the only whole-cloth ungrounded citations belong to a dropped arm. The entry
is explicit: *"The post-hoc citation-filter option stays queued as its own
Rule 0 slice; pre-commitment #1 is partially discharged, not dropped."*

`docs/plan-v4e-execution-tasks.md:20-23` (ruling #4) and
`docs/HANDOFF-development.md:193-195` ("STILL QUEUED") both repeat this: the
citation-filter half is alive, undesigned, and un-mini-planned. **No
`plan-citation-filter.md` existed before this draft** — confirmed by listing
`docs/plan-*.md` (30 files, none matching) before writing this one. That
absence is why the earlier "build it" pass on this slice stopped instead of
shipping code: Jon named "mini-plan needed" as an explicit precondition, and
it hadn't been met.

## What "post-hoc" means here (established, not assumed)

`DECISIONS.md:1349-1351` poses the follow-up as an either/or against a
**prompt tweak**: *"whether a prompt tweak **or** a post-hoc citation
filter could zero them out."* A prompt tweak changes what the model is
*asked to produce*. The post-hoc filter is defined in contrast to that — it
acts on the model's output *after* generation, not on its instructions.
That much is textually settled.

What is **not** settled by any doc is the second-order question this plan
exists to answer: does "after generation" mean inside the live product path
(mutating `Answer.citations` before anything downstream sees it) or only in
analysis (a scoring-side adjustment that never touches a live `Answer`)?
See Decision 1 below — this is the plan's central open question, not a
detail to assume past.

## Evidence: the 7 flagged instances, itemized

Source: `evals/groundedness_v3ab.json` (git-tracked, already computed by an
earlier session running `evals/groundedness_v3ab.py`'s `check_row`/
`citation_kind` — `evals/groundedness_v3ab.py:40,58` — over the frozen
`evals/answers/` captures). Read directly, unmodified; nothing was
re-executed to produce this table. Counts match `DECISIONS.md:1347`'s "5
questions / 7 instances" exactly, which cross-checks the file against the
number Jon already signed off on.

| # | Arm | Cond | Run | Question | Ungrounded citation(s) | In v4/E decision set? | Class |
|---|-----|------|-----|----------|------------------------|------------------------|-------|
| 1 | deepseek-v4-pro | D | 1 | q016 | `601.2f-h` | No (dropped arm) | **Unverified — pattern-matched only.** Same `601.2` rule family as row 4/5's confirmed parent/child case; classification not independently confirmed against context ids (see Limitation below). |
| 2 | gemini-flash-lite | B | 1 | q014 | `702.7`, `702.4` | No (dropped arm) | **Whole-cloth.** `DECISIONS.md:1467-1469`: "the only whole-cloth ungrounded citations... belong to a dropped arm." |
| 3 | gemini-flash-lite | B | 2 | q014 | `702.7`, `702.4` | No (dropped arm) | **Whole-cloth**, same citations both runs (stable) — same source. |
| 4 | gpt-5-mini | C | 1 | q028 | `601.2` | **Yes** | **Parent/child granularity.** `DECISIONS.md:1464-1465`: cited `601.2` when `601.2a/601.2f/601.2i` were in context. |
| 5 | gpt-5-mini | D | 1 | q028 | `601.2` | **Yes** | **Parent/child granularity** — same pattern, the "×2" in `DECISIONS.md:1464`. |
| 6 | sonnet | B | 1 | q012 | `701.21` | **Yes** | **Appended-to-grounded.** `DECISIONS.md:1465-1467`: appended to a claim already grounded in the provided `Sacrifice` glossary entry. |
| 7 | sonnet | C | 2 | c016 | `904.6d` | **Yes** | **One-digit-off.** `DECISIONS.md:1465`: cited alongside a real, in-context `704.6d` — one digit apart. |

**Limitation, stated plainly:** row 1's classification is inferred by
pattern (same `601.2` family, same shape as the confirmed parent/child
case), not independently re-derived from the actual context-id set for
`q016`/condition D. `evals/answers/_prompts_D.json` — the file
`lib_v3ab.context_ids()` reads to do that check — is untracked and does not
exist in this worktree (`evals/answers/` is absent entirely; confirmed by
listing), and the only copy is in the original repo, which this task is
explicitly barred from touching. Re-running the check to confirm row 1
requires either copying that one file into a worktree or an agent working
directly in the original repo in read-only mode — both are outside this
slice's authorization. Flagged rather than guessed past.

**What a strict filter would strip:** all 7 rows / 9 ungrounded citation
strings (`601.2f-h`, `702.7`, `702.4` ×2 runs, `601.2` ×2, `701.21`,
`904.6d`) — by construction, since "strict `citation_kind`-ungrounded" is
exactly what `check_row` already flagged to produce this file.

**How many are the arguably-shouldn't-strip parent/child case:** 2 citation
strings / 2 rows confirmed (rows 4-5, gpt-5-mini's `601.2`), +1 citation
string / 1 row pattern-matched but unverified (row 1). So a strict filter
with no parent/child exemption would strip 2 (confirmed) to 3 (if row 1
matches) citations that arguably state a true, if imprecise, thing — versus
6-7 that are more clearly wrong (digit-off, appended, or whole-cloth).

## Decision 1 — where does the filter apply (blast radius)

**Option A — production-path mutation.** Filter runs inside
`src/rulesagent/generate/answer.py`, on every `Answer` before it's returned
(near the existing `answered and not citations` check at
`answer.py:1233-1244`). Strips ungrounded entries from `Answer.citations`
for every live call — frontend display, future eval captures, everything.
- *Blast radius:* touches the product's live output for every future user
  and every future eval run. Changes what `Answer.citations` *means* — the
  contract docstring (`contracts.py:340-345`) currently defines it as "the
  rule numbers... the answer actually relied on," which is a claim about
  the model's behavior; post-hoc stripping turns it into "what we're
  willing to show," a different claim, even though the field's *shape*
  doesn't change. That's a semantic contract change the task that spawned
  this plan was told to flag rather than assume past.
- *Risk:* a false-positive strip (e.g., the parent/child case) silently
  removes a citation a human reviewer would have accepted as basically
  correct, with no record that anything was removed unless logged.

**Option B — eval-only analysis.** A new script alongside
`evals/groundedness_v3ab.py` that computes "what the citation list would
look like under the filter" and reports a corrected score, without ever
touching a live `Answer` or the product path.
- *Blast radius:* zero product impact. Every future `Answer` a user or eval
  run sees is unchanged; only a reporting layer changes.
- *Risk:* doesn't actually fix anything a user sees — it only changes how
  Jon and future eval passes *score* groundedness, so if the goal was "stop
  showing ungrounded citations to users," Option B doesn't deliver that.

**Recommendation: Option B first.** It is strictly lower-risk, answers the
scoring question pre-commitment #1 was actually about (grading time was the
binding constraint that shaped v4/condition-E, per
`docs/plan-v4e-execution-tasks.md:14-15` — the same scarce resource applies
here), and produces evidence (does the corrected count actually look
better, and does the parent/child exemption change the picture) before
committing to a product-path change that silently redefines a documented
field's meaning. Option A can follow as its own later slice if Option B's
numbers make Jon want it in production.

**What would change my mind:** if Jon's actual goal was UX-facing (stop
*showing* users a wrong-looking citation, not just re-score internally),
Option A becomes the point of the exercise and B is just a dry run for it.
The plan doesn't currently know which goal Jon had — that's Decision 1's
open question, not something inferable from the docs.

## Decision 2 — what counts as "ungrounded" (filter criterion)

**Option A — reuse `citation_kind`/`check_row` exactly, no exemptions.**
Simplest: it's already-reviewed, frozen-logic-adjacent code, and it's the
same yardstick the signed-off 7/5 baseline was measured with, so a filter
built on it is internally consistent with what Jon already accepted.
- *Trade-off:* strips the parent/child case (rows 4-5, and possibly row 1)
  even though `DECISIONS.md:1464-1465` describes that case as a
  granularity artifact, not a wrong claim — `601.2` is not false when
  `601.2a/f/i` are what's actually in context, it's just less precise than
  citing the subrules directly.

**Option B — strict, plus a parent/child exemption.** Before flagging a
rule-number citation as ungrounded, additionally check whether it's a
*parent* of one or more rule-numbers that ARE in context (e.g., `601.2` is
ungrounded-strict but not ungrounded-with-exemption if `601.2a` is
provided). Everything else (digit-off, appended, whole-cloth) still strips.
- *Trade-off:* more code, a second thing to keep in sync with
  `citation_kind`, and a new judgment call about how "close" a parent
  citation has to be (is `601` too far from `601.2a`? `contracts.py:57-67`'s
  `parent_chain` field already encodes this relationship per-`Rule`, so the
  exemption could reuse existing data rather than string-prefix matching —
  worth noting for whoever designs this next, not solved here).

**Recommendation: undecided — needs Jon's call.** The table above gives him
the concrete numbers (2 confirmed, +1 unverified, out of 7) to decide
whether the parent/child case is common/harmless enough to special-case, or
rare enough that Option A's simplicity wins. This is a judgment call about
what "ungrounded" should mean, not a technical one this plan should resolve
unilaterally.

**What would change my mind:** if row 1 (deepseek-v4-pro q016) gets
independently confirmed as parent/child too, that's 3/7 — a meaningfully
larger share — and would push toward Option B. If it turns out to be
something else on inspection, Option A's simplicity looks better.

## Decision 3 — does this touch the signed-off historical baseline?

**Option A — forward-only.** The filter (whichever blast radius is chosen)
applies only to answers generated from here forward. The 7/5 baseline Jon
already signed off on (`DECISIONS.md:1347`) stays exactly as graded and
recorded; nothing about it is ever recomputed or restated.
- *Trade-off:* the historical instances stay "flagged but not fixed" in the
  record forever — which is arguably correct, since they were already
  ruled acceptable at that level and re-litigating a signed-off number
  retroactively is exactly the kind of thing the frozen-judge discipline
  (`DECISIONS.md:1366-1367`) warns against.

**Option B — retroactively re-score the 7 historical instances under the
filter**, as a read-only report (never modifying `evals/answers/`,
`verdicts_*.json`, or `_prompts_*.json` — those stay frozen evidence per
this task's constraints), to show what the corrected tripwire count would
have been.
- *Trade-off:* useful context, but risks becoming a second, competing
  number next to the number Jon already ruled on — needs to be presented
  as "if we'd had this filter" framing, never as a replacement figure.

**Recommendation: Option A for the filter itself; Option B is basically
already done** — this plan's evidence table *is* that read-only
re-classification, computed without touching any frozen file. A future
implementer doesn't need to re-derive it, just decide whether to build
against it.

**What would change my mind:** if Jon wants the historical 7 actually
re-graded (not just re-classified) under a shipped filter, that's a bigger,
separate ask — it would touch grading, which is explicitly out of scope
here ("Do not touch anything judge-related").

## Non-goals

- Not touching `src/rulesagent/retrieve/rewrite.py`,
  `src/rulesagent/generate/openrouter_backend.py`, or `evals/run_eval.py` —
  owned by another agent in another worktree.
- Not changing the `Answer` schema's shape (field names/types) — only
  Decision 1/Option A would change what an existing field's *values* mean,
  which is called out above as exactly the kind of change needing its own
  sign-off before code.
- Not a prompt change — `DECISIONS.md:1458-1462` already closed that door
  for v4; this plan doesn't reopen it.
- Not re-grading any historical answer — grading is Jon's alone
  (`docs/plan-v4e-execution-tasks.md:47`) and judge-adjacent work is out of
  scope for this slice by the spawning task's own constraints.
- Not resolving row 1's classification by reading the original repo's
  `evals/answers/` — flagged as a limitation, not worked around.

## Open questions for Jon (blocking any build)

1. Decision 1: is the goal to change what users see (Option A, product
   path) or to get a better internal score (Option B, eval-only)? Or B now,
   A later once B's numbers are in?
2. Decision 2: does the parent/child case get an exemption, or does a
   simple strict filter ship as-is?
3. Row 1 (deepseek-v4-pro q016): worth spending a read-only pass in the
   original repo (or copying one file into a worktree) to confirm its
   class, or is "probably parent/child, unconfirmed, dropped arm anyway"
   good enough to not bother?
