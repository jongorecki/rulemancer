# Plan — transitive grading: judge-compare arms against Jon's graded reference

Status: APPROVED in-chat (Jon, 2026-07-22, "lets do what we need to do to
reduce that hand grading work as much as we can"). Implementation same day.

## Idea

Jon hand-graded the deepseek-v3.2 arm (evals/verdicts_deepseek-v3-2.json,
50/50: 43 correct / 5 wrong / 2 partial). The bakeoff-validated judge
(gpt-5-mini, 95% agreement, picked over non-Claude alternatives) rules
same/different on answer pairs. Chain the two: for each remaining arm's
answer, judge it against v3.2's answer to the same question —
**same + v3.2-verdict → verdict transfers** (correct AND wrong both
transfer; the judge routes, it never grades). **different → Jon's queue.**

Guardrails (the do-not-delegate line): Jon still owns "what counts as
correct" — every transferred verdict traces to one of his verdicts; a
deterministic ~10% sample of auto-transferred rows goes back into his
queue labeled AUDIT so the judge's agreement rate is checked on this data,
not assumed from the bakeoff.

## Build

`evals/judge_arm_pairs.py`:
- Reuse judge_bakeoff.py's judge prompt/protocol VERBATIM (validated
  instrument — do not reword it) with the pinned judge model.
- `--target <label>` reads data/parsed/review_<label>.json (adapter
  output, uniform shape); reference fixed: review_deepseek-v3-2.json +
  verdicts_deepseek-v3-2.json.
- Output evals/judge_pairs_<label>.json: {id, judge: same|different,
  ref_verdict, auto_verdict|null, audit: bool} + a printed summary line.
- Deterministic audit sample: seeded RNG over auto-transferred ids.
- Then per arm: verdicts_<label>.auto.json (the transferred subset) and a
  reduced data/parsed/grading_<label>_diff.html (existing build_grading_ui,
  UNMODIFIED, fed only different+audit rows) for Jon.

Targets: sonnet-v2, deepseek-v4-pro, deepseek-v4-flash, gemini-flash-lite,
gpt-5-mini (5 arms x 50 pairs = 250 judge calls, gpt-5-mini pricing).

## Roll-up rule

Final per-arm verdict file = Jon's manual verdicts (diff+audit grading)
UNION auto-transferred verdicts; manual wins on any id present in both.
Audit rows where Jon disagrees with the transfer are a judge-error count —
reported, and if >10% of the audit sample, the arm's auto-verdicts are
flagged unreliable and the arm falls back to full manual.

## Out of scope

Changing the grading UI template; changing judge prompt; RulesGuru-150
(same machinery, separate green-light).
