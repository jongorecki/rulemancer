# Report — cost-calculator validation at scale (the 199 cost-tagged set)

Run 2026-07-24. Validates the shipped `calculate_cost` tool beyond c014, on the
199 cost-tagged questions in `evals/rulesguru_full.jsonl`. Two stages: a free
trigger scan (precision/safety), then generation on the fired subset
(reliability/correctness).

## Stage 1 — trigger precision (free, no generation)

| set | fired | rate |
|---|---|---|
| cost-tagged (199) | 5 | **2.5%** |
| non-cost control (200) | 0 | **0.0% false-positive** |

- **Safety confirmed:** the trigger fired on 0 of 200 non-cost questions. It does
  not fire when it shouldn't — the "additive, false-positive is cheap" design
  claim holds.
- **Reach is narrow:** 2.5% of even cost-tagged questions. The tool engages only
  on the specific `{X}` + cost-modification shape (c014's shape). It is a
  precision instrument, not a general cost-question helper.
- Fired qids: rg289, rg897, rg1487, rg6636, rg6916 (+ c014).

## Stage 2 — reliability and correctness (generation on the 5 fired)

Aggregated across all tool-fired generation runs to date (c014 ×4, stage-2a ×5,
stage-2b ×5 = **14 tool-fired generations**):

- **Tool engages: 14/14.** When the trigger fires, the tool is actually called
  every time. That half is solid.
- **RELIABILITY DEFECT: ~21% empty-output (3/14).** Three runs returned empty
  output / `stop_reason=error` and produced no answer. The **non-tool baseline is
  ~0%** (0 errors across 150 rulesguru sonnet answers and 64 v5-grid answers). So
  the empty-output failures concentrate on the tool-loop path — this is a real
  integration defect, not API noise. (Earlier notes called the first such error
  "transient"; the aggregate rate against a 0% baseline says otherwise.)
- **Correctness when it answers: 2/3 same-as-gold** (frozen judge). Small n.
  - rg897 (L1): **same** — correctly handled Thorn of Amethyst's {1} cost
    increase via 601.2f; Chalice/mana-value ruling correct.
  - rg1487 (L1): **same** — X=2 → mana value 5, Thryx cost reduction, correct.
  - rg289 (Corner Case): **different** — and instructive: it fired on a mana-
    *production* question (a Cauldron producing {C}), where a *cost* calculator
    is the WRONG instrument. The trigger's precision is imperfect even inside
    cost-tagged: `{X}` + a cost word can appear on a non-cost-assignment question.

## Verdict — promising, NOT yet production-trustworthy

The c014/Trinisphere win is real (proven separately, tool-verified). But scaled
validation says the integration is not ready to rely on or expand:

1. **Reliability must be fixed first.** ~21% empty-output on the tool path is a
   blocker. Likely causes to investigate: the large `calculate_cost` tool-result
   payload (all the X-breakdowns) interacting with the final `messages.parse`
   turn; or the tool round-trip nesting inside the existing 2-attempt retry. This
   is the next slice before the tool is trusted, and BEFORE adding combat/layer
   tools on the same loop — they'd inherit the defect.
2. **Trigger precision refinement (minor).** Exclude mana-*production* questions
   from the cost trigger (rg289). Cheap; do it with the reliability slice.

## What is validated

- The deterministic calculator is correct (unit-tested; c014/Trinisphere proven).
- The trigger is SAFE (0% false-positive on 200 non-cost).
- The tool reliably ENGAGES when triggered (14/14).

## What is not

- Reliability of the generation that follows the tool call (~21% empty-output).
- Broad reach (2.5% by design — narrow is fine, but it means the cost tool alone
  moves few questions; the value is precision on a specific hard class).

Recommendation: a reliability-fix slice on the tool-loop before the cost tool is
relied upon or the combat/layer tools are built on the same machinery.
