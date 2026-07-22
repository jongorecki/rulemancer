"""Outside-judge bake-off (handoff to-do #4).

Runs candidate NON-Claude judges beside the trusted claude-sonnet-5 judge on
evals/judge_pairs.jsonl (same-question answer pairs from different pipeline
configs, including known conclusion-flips) and reports agreement with sonnet's
verdicts. Same adoption bar Haiku cleared: >=95% agreement. A non-Claude judge
also removes Claude-judging-Claude family bias -- README-worthy.

Anthropic judges reuse ablate_gold.judge() verbatim (structured output), so the
sonnet/haiku numbers stay comparable with the existing ablation harness.
OpenRouter judges get the same JUDGE_SYS plus a one-word-verdict instruction
(the most model-agnostic elicitation; structured-output support varies).
Models are PINNED and allow_fallbacks=False per DESIGN -- a silent failover
would corrupt the agreement numbers.

Run: uv run python evals/judge_bakeoff.py   (needs OPENROUTER_API_KEY in .env)
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from ablate_gold import JUDGE_MODEL, HAIKU_JUDGE, JUDGE_SYS, judge  # noqa: E402

load_dotenv()

PAIRS_PATH = Path(__file__).parent / "judge_pairs.jsonl"
RESULTS_PATH = Path(__file__).parent / "judge_bakeoff_results.json"

# Slugs verified live against openrouter.ai/api/v1/models on 2026-07-22.
OPENROUTER_JUDGES = {
    "deepseek-v3.2": "deepseek/deepseek-v3.2",
    "gemini-2.5-flash-lite": "google/gemini-2.5-flash-lite",
    "gpt-5-mini": "openai/gpt-5-mini",
}


def or_judge(slug: str, question: str, reference: str, candidate: str) -> str:
    """One-word same/different verdict from an OpenRouter model. Errors and
    unparsable replies return sentinel strings and count as disagreement --
    a judge that can't answer reliably shouldn't win the job."""
    user = (f"Question: {question}\n\nREFERENCE (correct):\n{reference}\n\n"
            f"CANDIDATE:\n{candidate}\n\n"
            "Reply with exactly one word: same or different.")
    body = {
        "model": slug,
        "messages": [{"role": "system", "content": JUDGE_SYS},
                     {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": 4000,  # reasoning-style models spend completion budget thinking
        "provider": {"allow_fallbacks": False},
    }
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}
    for attempt in (1, 2):
        try:
            r = httpx.post("https://openrouter.ai/api/v1/chat/completions",
                           headers=headers, json=body, timeout=180.0)
            if r.status_code == 400 and "temperature" in r.text and "temperature" in body:
                del body["temperature"]  # some reasoning models reject sampling params
                continue
            r.raise_for_status()
            content = (r.json()["choices"][0]["message"].get("content") or "").lower()
            m = re.search(r"\b(same|different)\b", content)
            return m.group(1) if m else "unparsed"
        except Exception:
            if attempt == 2:
                return "error"
            time.sleep(2)
    return "error"


def main() -> None:
    pairs = [json.loads(l) for l in PAIRS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    judges = ["sonnet", "haiku", *OPENROUTER_JUDGES]
    rows = []
    print(f"{len(pairs)} pairs x {len(judges)} judges\n")
    for p in pairs:
        row = {"pid": p["pid"]}
        row["sonnet"] = judge(p["question"], p["reference"], p["candidate"], JUDGE_MODEL)
        row["haiku"] = judge(p["question"], p["reference"], p["candidate"], HAIKU_JUDGE)
        for name, slug in OPENROUTER_JUDGES.items():
            row[name] = or_judge(slug, p["question"], p["reference"], p["candidate"])
        rows.append(row)
        print("  " + "  ".join(f"{j}={row[j]:<9s}" for j in judges) + f"  {p['pid']}")

    n = len(rows)
    dist = {v: sum(1 for r in rows if r["sonnet"] == v) for v in ("same", "different")}
    print(f"\nsonnet verdict distribution: {dist}  (both classes must be present "
          "or an always-'same' judge scores free points)")
    print(f"\nAGREEMENT WITH SONNET (adoption bar: >=95%, Haiku's was 94-99%):")
    summary = {"n_pairs": n, "sonnet_distribution": dist, "agreement": {}, "rows": rows}
    for j in judges[1:]:
        agree = sum(1 for r in rows if r[j] == r["sonnet"])
        disagrees = [r["pid"] for r in rows if r[j] != r["sonnet"]]
        pct = 100.0 * agree / n
        summary["agreement"][j] = {"pct": pct, "disagrees_on": disagrees}
        print(f"  {j:22s} {agree}/{n} = {pct:.0f}%   disagrees: {disagrees or '-'}")

    RESULTS_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nresults -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
