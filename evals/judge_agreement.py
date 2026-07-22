"""Judge agreement harness -- validate an OpenRouter model as an outside judge
against the ALREADY-STORED sonnet-5 verdicts (docs/plan-openrouter-models.md,
step D / handoff to-do #4).

evals/judge_bakeoff.py already ran this exact comparison for three fixed
OpenRouter judges (deepseek-v3.2, gemini-2.5-flash-lite, gpt-5-mini) against
BOTH the sonnet-5 and Haiku verdicts on evals/judge_pairs.jsonl, writing
evals/judge_bakeoff_results.json. That file's "rows" list is where the STORED
sonnet-5 verdicts actually live -- one "sonnet" field per row ("same" or
"different"), keyed by pid. THIS script is the general form: --model takes ANY
OpenRouter id and re-judges the SAME 22 pairs against those stored verdicts,
without re-calling sonnet-5 -- it's already graded and pinned, so re-asking it
would just burn an Anthropic call for a number that's already on file.

Judge prompt: JUDGE_SYS, imported verbatim from ablate_gold.py -- the "EXACT
same judge prompt text" the task requires. Not retyped here so it can never
silently drift from the wording the Anthropic judges were scored against.

Judge call: NOT openrouter_backend.generate(). That function's
response_format is hardcoded to the Answer schema (text/citations/answered),
which isn't the judge's output shape (a same/different verdict). Rather than
touch openrouter_backend.py (out of scope, READ ONLY), this module posts its
own raw request -- same pinned-model / no-fallback discipline
(provider.allow_fallbacks=False) -- and parses a one-word same/different
reply, the same elicitation and regex-parse judge_bakeoff.py's or_judge()
already uses, so a candidate's numbers here are comparable to a bake-off
entry run earlier. Errors and unparsable replies return sentinels that count
as disagreement, same reasoning as or_judge(): a judge that can't answer
reliably shouldn't win the job.

Output: printed agreement tally (N agree / N total, percentage vs the stored
sonnet-5 verdicts), plus one entry APPENDED to evals/judge_agreement_results.json
(a JSON list, one entry per run) -- never overwritten, so multiple candidate
models accumulate in one place.

Run: `uv run python evals/judge_agreement.py --model <openrouter-id>
      [--ids pid1,pid2,...] [--dry-run]`
(needs OPENROUTER_API_KEY in .env; --dry-run makes no API calls)
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from ablate_gold import JUDGE_SYS  # noqa: E402

load_dotenv()

PAIRS_PATH = Path(__file__).parent / "judge_pairs.jsonl"
BAKEOFF_RESULTS_PATH = Path(__file__).parent / "judge_bakeoff_results.json"
RESULTS_PATH = Path(__file__).parent / "judge_agreement_results.json"

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def load_pairs() -> dict[str, dict]:
    """pid -> {question, reference, candidate}, straight from judge_pairs.jsonl."""
    out = {}
    for line in PAIRS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["pid"]] = row
    return out


def load_stored_sonnet_verdicts() -> dict[str, str]:
    """pid -> sonnet-5's ALREADY-JUDGED verdict, read from
    judge_bakeoff_results.json's "rows" list -- the verdict set this harness
    re-judges against. Never re-calls sonnet-5; that number is already on file."""
    data = json.loads(BAKEOFF_RESULTS_PATH.read_text(encoding="utf-8"))
    return {row["pid"]: row["sonnet"] for row in data["rows"]}


def judge_raw(model: str, question: str, reference: str, candidate: str) -> str:
    """One same/different verdict from an OpenRouter model for the SAME judge
    prompt ablate_gold.py's Anthropic judges use. See module docstring for why
    this doesn't go through openrouter_backend.generate()."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return "error"
    user = (f"Question: {question}\n\nREFERENCE (correct):\n{reference}\n\n"
            f"CANDIDATE:\n{candidate}\n\n"
            "Reply with exactly one word: same or different.")
    body = {
        "model": model,
        "messages": [{"role": "system", "content": JUDGE_SYS},
                     {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": 4000,  # reasoning-style models spend completion budget thinking
        "provider": {"allow_fallbacks": False},
    }
    headers = {"Authorization": f"Bearer {key}"}
    for attempt in (1, 2):
        try:
            r = httpx.post(API_URL, headers=headers, json=body, timeout=180.0)
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True, help="OpenRouter judge model id to validate")
    p.add_argument("--ids", default="",
                    help="comma-separated pids to re-judge (default: every pid with a stored "
                         "sonnet-5 verdict)")
    p.add_argument("--dry-run", action="store_true",
                    help="print the pairs + stored sonnet-5 verdicts that WOULD be re-judged; "
                         "make no API calls, write no results")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    pairs = load_pairs()
    sonnet_verdicts = load_stored_sonnet_verdicts()

    pids = [i.strip() for i in args.ids.split(",") if i.strip()] or list(sonnet_verdicts)
    missing = [p for p in pids if p not in pairs or p not in sonnet_verdicts]
    if missing:
        print(f"[WARN] skipping {len(missing)} pid(s) with no pair or no stored sonnet-5 "
              f"verdict: {missing}")
        pids = [p for p in pids if p not in missing]

    print(f"Re-judging {len(pids)} pair(s) vs stored sonnet-5 verdicts | model={args.model}"
          f"{' | DRY RUN' if args.dry_run else ''}\n")

    rows = []
    for pid in pids:
        pair = pairs[pid]
        sonnet = sonnet_verdicts[pid]
        if args.dry_run:
            print(f"  {pid:<28} sonnet={sonnet}")
            rows.append({"pid": pid, "sonnet": sonnet, "verdict": None})
            continue
        verdict = judge_raw(args.model, pair["question"], pair["reference"], pair["candidate"])
        rows.append({"pid": pid, "sonnet": sonnet, "verdict": verdict})
        print(f"  {pid:<28} sonnet={sonnet:<10} {args.model}={verdict}")

    if args.dry_run:
        print("\n[DRY RUN] no API calls made, no results written.")
        return

    n = len(rows)
    agree = sum(1 for r in rows if r["verdict"] == r["sonnet"])
    pct = 100.0 * agree / n if n else 0.0
    disagrees = [r["pid"] for r in rows if r["verdict"] != r["sonnet"]]

    print(f"\nAGREEMENT WITH STORED SONNET-5 VERDICTS: {agree}/{n} = {pct:.1f}%"
          f"  (adoption bar: >=95%, per plan-openrouter-models.md)")
    if disagrees:
        print(f"  disagrees on: {disagrees}")

    entry = {
        "model": args.model,
        "n": n,
        "agree": agree,
        "pct": pct,
        "disagrees_on": disagrees,
        "rows": rows,
    }
    history = []
    if RESULTS_PATH.exists():
        history = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        if not isinstance(history, list):
            history = [history]
    history.append(entry)
    RESULTS_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nresults appended -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
