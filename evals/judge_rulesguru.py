"""Auto-judge generated answers against RulesGuru's human-written gold
(docs/plan-rulesguru-import.md, decision #2: auto-judge, Jon spot-checks
disagreements rather than hand-grading every row).

Reads a review file produced by run_answer_eval.py (rows that carry
`answer_gold` -- i.e. RulesGuru rows; see run_answer_eval.load_answer_gold),
and for each one asks the adopted OpenRouter judge (gpt-5-mini, the
outside-judge bake-off winner at 95%+ agreement with sonnet-5, see
judge_bakeoff.py) whether the generated answer reaches the same ruling as
RulesGuru's `answer_gold`.

Reuses ablate_gold.JUDGE_SYS verbatim, with ONE added context line specific
to RulesGuru's scenario phrasing:
  "Player names starting with 'A' are the active player; other letters are
  nonactive players in turn order. Questions refer to objects by their
  original names even after copy effects."
This line is JUDGE-ONLY. The bot being judged never sees it -- production
users don't announce these conventions, and correctly parsing scenario
phrasing (who's active, which copy is "the" object) is part of what's being
tested. Baking the convention into the bot's prompt would grade the judge's
own assumption, not the bot's rules understanding.

Output: evals/rulesguru_verdicts.json -- one entry per judged question
(verdict, judge reason, level, complexity) plus a `summary` block (accuracy
overall and broken down by level). Disagreements (verdict == "different")
are what Jon spot-checks by hand.

Needs OPENROUTER_API_KEY in .env (same as judge_bakeoff.py).
Run: `uv run python evals/judge_rulesguru.py [--answers PATH] [--questions PATH] [--out PATH]`
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from ablate_gold import JUDGE_SYS  # noqa: E402
from run_eval import PARSED_DIR  # noqa: E402

load_dotenv()

DEFAULT_ANSWERS = PARSED_DIR / "review.json"
DEFAULT_QUESTIONS = Path(__file__).parent / "rulesguru.jsonl"
DEFAULT_OUT = Path(__file__).parent / "rulesguru_verdicts.json"

JUDGE_SLUG = "openai/gpt-5-mini"  # the adopted judge (evals/judge_bakeoff.py, 95% agreement with sonnet-5)

RULESGURU_JUDGE_SYS = JUDGE_SYS + (
    "\n\nAdditional context for this question set: player names starting "
    "with 'A' are the active player; other letters are nonactive players "
    "in turn order. Questions refer to objects by their original names "
    "even after copy effects."
)
# This preamble is JUDGE-ONLY -- see module docstring. Never handed to the
# bot under test, only to the model grading its answer.


def load_answered_rows(path: Path) -> list[dict]:
    """Rows from a run_answer_eval.py output that carry answer_gold -- i.e.
    the RulesGuru-sourced rows. Non-RulesGuru rows (no answer_gold) are
    silently skipped; there's nothing to judge them against."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [r for r in rows if r.get("answer_gold")]


def load_meta(path: Path) -> dict[str, dict]:
    """id -> {level, complexity} straight from the raw rulesguru.jsonl rows
    -- these aren't on the EvalQuestion contract (same reasoning as
    run_answer_eval.load_answer_gold), so they're read here directly rather
    than through load_questions()."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["id"]] = {"level": row.get("level", ""), "complexity": row.get("complexity", "")}
    return out


def judge_with_reason(question: str, reference: str, candidate: str,
                       judge_slug: str = JUDGE_SLUG) -> tuple[str, str]:
    """(verdict, reason) from the OpenRouter judge. Same request shape as
    judge_bakeoff.or_judge (pinned model, allow_fallbacks=False, one retry
    on transient failure) but asks for a one-line reason alongside the
    verdict, since the deliverable here is spot-check material, not just an
    agreement percentage.

    `judge_slug` defaults to the adopted JUDGE_SLUG (gpt-5-mini) so every
    existing caller is unaffected; pass a different OpenRouter slug to grade
    with a different judge model (e.g. for a cross-family read)."""
    user = (
        f"Question: {question}\n\nREFERENCE (correct):\n{reference}\n\n"
        f"CANDIDATE:\n{candidate}\n\n"
        "Respond with EXACTLY two lines, nothing else:\n"
        "Verdict: same OR Verdict: different\n"
        "Reason: <one sentence explaining the verdict>"
    )
    body = {
        "model": judge_slug,
        "messages": [{"role": "system", "content": RULESGURU_JUDGE_SYS},
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
                del body["temperature"]
                continue
            r.raise_for_status()
            content = r.json()["choices"][0]["message"].get("content") or ""
            vm = re.search(r"verdict:\s*(same|different)", content, re.I)
            rm = re.search(r"reason:\s*(.+)", content, re.I | re.S)
            verdict = vm.group(1).lower() if vm else "unparsed"
            reason = rm.group(1).strip() if rm else content.strip()[:300]
            return verdict, reason
        except Exception as e:
            if attempt == 2:
                return "error", f"judge call failed: {e}"
            time.sleep(2)
    return "error", "judge call failed"


def judge_row_votes(question: str, reference: str, candidate: str, votes: int,
                     judge_slug: str = JUDGE_SLUG) -> dict:
    """Judge one row `votes` times independently and return the majority
    verdict plus every individual vote.

    Each call is a fresh, independent POST to judge_with_reason -- the
    request already pins temperature=0, so repeat calls measure PROVIDER-SIDE
    nondeterminism (routing to different backends/quantizations under the
    OpenRouter slug, cache effects, etc.), not sampling variance. Majority
    voting can smooth that out; it cannot fix a judge that is consistently
    wrong (systematic bias), because all N votes would agree on the same
    wrong answer.

    Returns every vote (not just the winner) plus a tally and an
    `unanimous` flag, because the per-row spread is the evidence a re-run
    is stable, and throwing individual votes away destroys that evidence.
    """
    results = [judge_with_reason(question, reference, candidate, judge_slug) for _ in range(votes)]
    tally: dict[str, int] = {}
    for verdict, _reason in results:
        tally[verdict] = tally.get(verdict, 0) + 1
    majority_verdict = max(tally.items(), key=lambda kv: kv[1])[0]
    return {
        "votes": [{"verdict": v, "reason": r} for v, r in results],
        "tally": tally,
        "majority_verdict": majority_verdict,
        "unanimous": len(tally) == 1,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--answers", type=Path, default=DEFAULT_ANSWERS,
                    help=f"run_answer_eval.py output (default: {DEFAULT_ANSWERS})")
    p.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS,
                    help=f"source rulesguru jsonl, for level/complexity lookup (default: {DEFAULT_QUESTIONS})")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output path (default: {DEFAULT_OUT})")
    p.add_argument("--votes", type=int, default=1,
                    help="judge each row this many times and take the majority verdict "
                         "(default: 1, i.e. existing single-pass behaviour unchanged). "
                         "Every vote is recorded per row, not just the majority.")
    p.add_argument("--workers", type=int, default=6,
                    help="parallel judge calls when --votes > 1 (default: 6)")
    p.add_argument("--judge", type=str, default=JUDGE_SLUG,
                    help=f"OpenRouter judge model slug (default: {JUDGE_SLUG}, i.e. existing "
                         "behaviour unchanged). Recorded in the output's judge_model field so "
                         "the instrument is never silently ambiguous.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    judge_slug = args.judge
    rows = load_answered_rows(args.answers)
    meta = load_meta(args.questions)
    if not rows:
        print(f"[ERROR] no answer_gold-carrying rows in {args.answers} -- "
              "run run_answer_eval.py --questions evals/rulesguru.jsonl first")
        return

    entries = []
    if args.votes > 1:
        print(f"Judging {len(rows)} RulesGuru answers with {judge_slug}, "
              f"{args.votes} votes/row ({args.workers} workers)\n")

        def judge_one(r: dict) -> dict:
            m = meta.get(r["id"], {"level": "", "complexity": ""})
            vote_info = judge_row_votes(r["question"], r["answer_gold"], r["answer"], args.votes, judge_slug)
            return {
                "id": r["id"],
                "question": r["question"],
                "level": m["level"],
                "complexity": m["complexity"],
                "verdict": vote_info["majority_verdict"],
                "votes": vote_info["votes"],
                "tally": vote_info["tally"],
                "unanimous": vote_info["unanimous"],
                "reason": vote_info["votes"][0]["reason"],
                "answer": r["answer"],
                "answer_gold": r["answer_gold"],
            }

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            entries = list(ex.map(judge_one, rows))
        entries.sort(key=lambda e: e["id"])
        for i, e in enumerate(entries, 1):
            tag = "unanimous" if e["unanimous"] else f"SPLIT {e['tally']}"
            print(f"  [{i}/{len(entries)}] {e['id']} (level={e['level']}) -> {e['verdict']} ({tag})")
    else:
        print(f"Judging {len(rows)} RulesGuru answers with {judge_slug}\n")
        for i, r in enumerate(rows, 1):
            m = meta.get(r["id"], {"level": "", "complexity": ""})
            verdict, reason = judge_with_reason(r["question"], r["answer_gold"], r["answer"], judge_slug)
            entries.append({
                "id": r["id"],
                "question": r["question"],
                "level": m["level"],
                "complexity": m["complexity"],
                "verdict": verdict,
                "reason": reason,
                "answer": r["answer"],
                "answer_gold": r["answer_gold"],
            })
            print(f"  [{i}/{len(rows)}] {r['id']} (level={m['level']}, complexity={m['complexity']}) -> {verdict}")

    judged = [e for e in entries if e["verdict"] in ("same", "different")]
    n = len(judged) or 1
    accuracy = sum(1 for e in judged if e["verdict"] == "same") / n
    by_level: dict[str, dict[str, int]] = {}
    for e in judged:
        lvl = e["level"]
        d = by_level.setdefault(lvl, {"same": 0, "different": 0})
        d[e["verdict"]] += 1
    by_level_acc = {
        lvl: d["same"] / (d["same"] + d["different"]) if (d["same"] + d["different"]) else 0.0
        for lvl, d in by_level.items()
    }
    unparsed = [e["id"] for e in entries if e["verdict"] not in ("same", "different")]
    disagreements = [e["id"] for e in entries if e["verdict"] == "different"]

    summary = {
        # PROVENANCE. "the judge is FROZEN" was previously a property of the
        # code at run time that the ARTIFACT could not prove: JUDGE_SLUG went
        # out in the request but was never written to the output, so two
        # verdict files judged by different models were indistinguishable
        # after the fact. Recording the model and a digest of the exact system
        # prompt makes a silent instrument change detectable instead.
        #
        # This stamps what ran; it does NOT reword the prompt or change the
        # model. Verdict files written before 2026-07-25 carry no stamp -- read
        # their provenance from git, not from the file.
        "judge_model": judge_slug,
        "judge_prompt_sha256": hashlib.sha256(
            RULESGURU_JUDGE_SYS.encode("utf-8")
        ).hexdigest()[:16],
        "n_judged": len(judged),
        "n_total": len(entries),
        "accuracy": accuracy,
        "by_level": by_level_acc,
        "by_level_counts": by_level,
        "unparsed_or_error": unparsed,
        "disagreements": disagreements,
        "votes_per_row": args.votes,
    }
    if args.votes > 1:
        unanimous = [e for e in entries if e.get("unanimous")]
        split = [e for e in entries if not e.get("unanimous")]
        summary["unanimous_count"] = len(unanimous)
        summary["split_count"] = len(split)
        summary["split_pct"] = len(split) / len(entries) if entries else 0.0
        summary["split_ids"] = [e["id"] for e in split]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"entries": entries, "summary": summary}, indent=2, ensure_ascii=False),
                         encoding="utf-8")

    print(f"\nWrote {len(entries)} verdicts -> {args.out}")
    print(f"  accuracy: {sum(1 for e in judged if e['verdict']=='same')}/{len(judged)} = {accuracy:.0%}")
    print("  by level:")
    for lvl, acc in by_level_acc.items():
        c = by_level[lvl]
        print(f"    {lvl:<14} {c['same']}/{c['same']+c['different']} = {acc:.0%}")
    if unparsed:
        print(f"  unparsed/error: {unparsed}")
    print(f"  disagreements (spot-check these): {disagreements}")
    if args.votes > 1:
        print(f"  votes/row: {args.votes} -- unanimous {summary['unanimous_count']}/{len(entries)}, "
              f"split {summary['split_count']}/{len(entries)} ({summary['split_pct']:.1%})")
    print(f"  judge: {judge_slug} prompt={summary['judge_prompt_sha256']}")


if __name__ == "__main__":
    main()
