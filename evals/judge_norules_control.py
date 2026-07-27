"""Judge the parametric-knowledge control arm (docs/spec-gold-sufficiency.md
Section 2) against the same reference and the same judge as arm B.

Reuses judge_rulesguru.py's exact judge configuration -- RULESGURU_JUDGE_SYS
(ablate_gold.JUDGE_SYS + the RulesGuru scenario-convention addendum) and
JUDGE_SLUG "openai/gpt-5-mini" -- because arm B's own verdict file
(evals/verdicts_derivability_B.json) carries judge_prompt_sha256
"b54fbdb95565abf8", which is that exact prompt's hash, confirmed by direct
recomputation. Using a different judge prompt here would break the "same
judge" design constraint the control depends on for validity.

Output shape matches verdicts_derivability_B.json exactly (entries +
summary with by_level_counts in the {same, different} auto-judge shape) so
evals/build_metrics_history.py's scoring path (evals/weighted_score.py)
handles it with no special-casing, and so the judge model is self-recorded
-- this project has five older verdict files with no judge attribution
flagged [crit] on the dashboard; this one names its judge in the file.

Run: uv run python evals/judge_norules_control.py
"""

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ablate_gold import JUDGE_SYS  # noqa: E402
from judge_rulesguru import JUDGE_SLUG, judge_row_votes, judge_with_reason  # noqa: E402

REPO = Path(__file__).parent.parent
DEFAULT_ANSWERS = REPO / "evals" / "answers" / "norules_control.json"
DEFAULT_QUESTIONS = REPO / "evals" / "questions_rulesguru150_v3.jsonl"
DEFAULT_OUT = REPO / "evals" / "verdicts_norules_control.json"

RULESGURU_JUDGE_SYS = JUDGE_SYS + (
    "\n\nAdditional context for this question set: player names starting "
    "with 'A' are the active player; other letters are nonactive players "
    "in turn order. Questions refer to objects by their original names "
    "even after copy effects."
)


def load_meta(path: Path) -> dict[str, dict]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["id"]] = {"level": row.get("level", ""), "complexity": row.get("complexity", "")}
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--answers", type=Path, default=DEFAULT_ANSWERS)
    p.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--votes", type=int, default=1,
                    help="judge each row this many times and take the majority verdict "
                         "(default: 1, i.e. existing single-pass behaviour unchanged). "
                         "Every vote is recorded per row, not just the majority.")
    p.add_argument("--workers", type=int, default=6,
                    help="parallel judge calls when --votes > 1 (default: 6)")
    p.add_argument("--judge", type=str, default=JUDGE_SLUG,
                    help=f"OpenRouter judge model slug (default: {JUDGE_SLUG}, i.e. existing "
                         "behaviour unchanged). Recorded in the output's judge_model field.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    judge_slug = args.judge
    rows = json.loads(args.answers.read_text(encoding="utf-8"))
    rows = [r for r in rows if r.get("answer_gold")]
    meta = load_meta(args.questions)
    if not rows:
        print(f"[ERROR] no answer_gold-carrying rows in {args.answers}")
        return

    entries = []
    if args.votes > 1:
        print(f"Judging {len(rows)} norules_control answers with {judge_slug}, "
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
        print(f"Judging {len(rows)} norules_control answers with {judge_slug}\n")
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
            print(f"  [{i}/{len(rows)}] {r['id']} (level={m['level']}) -> {verdict}")

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
        "judge_model": judge_slug,
        "judge_prompt_sha256": hashlib.sha256(RULESGURU_JUDGE_SYS.encode("utf-8")).hexdigest()[:16],
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

    args.out.write_text(
        json.dumps({"entries": entries, "summary": summary}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nWrote {len(entries)} verdicts -> {args.out}")
    print(f"  accuracy: {sum(1 for e in judged if e['verdict']=='same')}/{len(judged)} = {accuracy:.1%}")
    print("  by level:")
    for lvl, acc in by_level_acc.items():
        c = by_level[lvl]
        print(f"    {lvl:<14} {c['same']}/{c['same']+c['different']} = {acc:.0%}")
    if unparsed:
        print(f"  unparsed/error: {unparsed}")
    print(f"  judge: {judge_slug} prompt={summary['judge_prompt_sha256']}")


if __name__ == "__main__":
    main()
