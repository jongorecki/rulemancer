# scripts/measure_demo_cost.py
"""Measure real $/serve for the gated demo (docs/superpowers/plans/
2026-07-27-gated-demo.md Task 12) -- BEFORE the DAILY_BUDGET_USD default is
chosen for production, per the spec: "This gets measured with a handful of
real queries before the cap is set."

SPENDS REAL ANTHROPIC API CREDITS. Requires Jon's explicit go-ahead and a
confirmed ceiling before running. Not run as part of any test suite or CI --
this is a manual, one-time-per-launch measurement.

    .venv/Scripts/python.exe scripts/measure_demo_cost.py [--n 8]

Prints per-question cost and the average, so Jon can set DAILY_BUDGET_USD
(a Fly secret, not code) from real numbers instead of the batched-eval
estimate ($0.06/serve extrapolated from the $0.031/row batched rate --
see the spec's "Cost model" section).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from rulesagent.generate.answer import GEN_EFFORT, RulesAgent  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.pricing import cost_usd, check_freshness  # noqa: E402

VECTOR_MODEL = "voyage-4-large"

# A small, hand-picked, cross-level sample -- NOT the first N rows of any
# sorted eval file (repo rule: that only ever hits L0 and misprices
# everything). These mirror the kind of question a hiring manager would
# actually type into the demo.
SAMPLE_QUESTIONS = [
    "Does trample let excess damage through a deathtouch blocker?",
    "What happens if I cast [Fork] targeting an instant on the stack?",
    "Can a player respond to their own triggered ability?",
    "If a creature with first strike blocks a creature without it, who deals damage first?",
    "Does [Grist, the Hunger Tide]'s -2 ability target?",
    "What's the difference between a static ability and a triggered ability?",
    "If I control two copies of a legendary creature, what happens?",
    "Can I cast an instant during my upkeep in response to a trigger?",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=8, help="how many sample questions to run (<= len(SAMPLE_QUESTIONS))")
    args = parser.parse_args(argv)
    n = min(args.n, len(SAMPLE_QUESTIONS))

    for warning in check_freshness():
        print(f"WARNING: {warning}", file=sys.stderr)

    store = VectorStore.load(REPO / "data" / "parsed" / f"vector_{VECTOR_MODEL}.pkl")
    agent = RulesAgent(store, effort=GEN_EFFORT)

    costs = []
    for i, q in enumerate(SAMPLE_QUESTIONS[:n], start=1):
        ans = agent.answer(q, history=[])
        usage = agent.last_usage or {}
        input_tokens = usage.get("input_tokens") or 0
        output_tokens = usage.get("output_tokens") or 0
        cache_read = usage.get("cache_read_input_tokens") or 0
        cache_write = usage.get("cache_creation_input_tokens") or 0
        cost = cost_usd(
            agent.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        ) or 0.0
        costs.append(cost)
        print(
            f"[{i}/{n}] ${cost:.4f}  in={input_tokens} out={output_tokens} "
            f"cache_read={cache_read} cache_write={cache_write}  "
            f"answered={ans.answered}  {q[:60]}"
        )

    if costs:
        avg = sum(costs) / len(costs)
        mx = max(costs)
        print(f"\naverage: ${avg:.4f}/serve over {len(costs)} real questions, total spent: ${sum(costs):.4f}")
        print(f"max: ${mx:.4f}/serve")
        print(f"suggested DAILY_BUDGET_USD for a ~20-code launch at 25 queries/code: "
              f"${avg * 25 * 20:.2f} (all codes maxed out in one day, worst case, avg-based)")
        print(f"pessimistic DAILY_BUDGET_USD using MAX observed cost: "
              f"${mx * 25 * 20:.2f} (all codes maxed out in one day, worst case, max-based)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
