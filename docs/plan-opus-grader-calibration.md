# Plan: Opus-Grader Calibration (Jon's proposal, 2026-07-22)

**Status: approved in principle by Jon (his idea, same session as the prompt-v3
rulings); runs tonight on already-graded data; he reviews results in the
morning. Read-only over committed verdicts — no production code touched.**

## Goal

Measure whether an Opus grading agent can be trusted to pre-grade answer
evals, by having it **blind-grade cells Jon has already graded** and scoring
its agreement against his verdicts. The output is a number (and a
disagreement list), not a policy — whether/how much grading to delegate
stays Jon's call, made on this evidence.

**The frozen gpt-5-mini judge is untouched.** That instrument routes
same/different between answers; this experiment auditions a *different role*
(direct verdict assignment) with a *different model*. Nothing about the
bakeoff or the transitive pipeline changes.

## Method

1. **Comparison set.** Primary: every cell whose final verdict came from
   Jon's hand directly (the `_manual` files). Secondary (reported
   separately, weaker ground truth): auto-transferred cells from the
   `_final` files, whose verdicts are Jon's-by-transitivity through the
   95%-agreement judge. Implementer counts and reports both Ns.
2. **Grader input per cell (blind):** the question text; the gold rule
   numbers with their match semantics AND the full text of those rules
   pulled from the corpus (the grader must ground in provided rules, never
   its own MTG memory — same law the bot itself lives under); the arm's
   complete answer JSON (answered/text/citations/tldr). It never sees
   Jon's verdict, Jon's note, or any other arm's answer.
3. **Rubric given to the grader,** distilled from Jon's ruling history,
   including the 2026-07-22 c004 rubric call: a correct answer that
   silently assumes away an ambiguity grades **correct** (the disclosure
   bar belongs to the future clarify-then-escalate feature, not the
   verdict); **partial** = materially incomplete or half-right on the
   substance; **wrong** = substantive rules error. Grader outputs verdict +
   one-line reason per cell, JSONL.
4. **Metrics:** overall agreement %; 3x3 confusion matrix; agreement on the
   correct/partial boundary specifically (the rubric-sensitive zone where
   c004 lived); full disagreement list with the grader's reasons, formatted
   for Jon's morning read.
5. **Reference bar:** the frozen judge earned trust at 95% agreement with
   0/21 live-audit errors. That's the natural yardstick to show next to
   the result — not an auto-adopt threshold.

## Cost & mechanics

- Model: `claude-opus-4-8` via the Anthropic SDK (key already in `.env`).
- ~300 cells × (question + gold rule text + answer JSON) in, ~100 tokens
  out. Cost estimated against current published pricing at implementation
  time (claude-api skill), never from memory. Expected order: a few dollars.
- Script: `evals/opus_grader_calibration.py`; report:
  `evals/opus_grader_report.md` + raw JSONL alongside.

## What would change the design

- If direct-manual N is too small for a stable % on the correct/partial
  boundary, report the boundary cells individually instead of as a rate.
- If Opus refuses/degenerates on any cell, that cell is reported as an
  error line, never silently dropped — reliability is part of the audition.
