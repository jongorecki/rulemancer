"""Task 3: judge-compare each B/C/D condition-run against that SAME arm's
condition-A (v2 baseline) answer, using judge_arm_pairs.py's frozen
call_judge()/decide_transfer() unchanged (which itself wraps
judge_bakeoff.or_judge(), the bake-off-validated gpt-5-mini judge protocol,
verbatim). Nothing about the judge prompt, model, or retry policy is
touched here -- only the REFERENCE side is different from the original
bake-off: instead of comparing every arm against deepseek-v3.2's answer,
here each arm's condition-B/C/D answer is compared against that SAME arm's
own condition-A answer, because the question this task answers is "did
prompt-v3 change this arm's answer," not "does this arm agree with the
v3.2 reference arm."

  judge = "same"       -> auto_verdict = condition-A's verdict (transfers,
                           correct AND wrong both transfer -- the judge
                           routes, it never grades)
  judge = "different"   -> auto_verdict = None; a candidate flip, routed to
                           Jon's queue (does NOT mean wrong -- could be a
                           rewording that still lands on the same
                           conclusion in Jon's eyes; the judge only detects
                           divergence, per the same semantics
                           judge_arm_pairs.py already uses)
  judge = error/unparsed -> excluded from both buckets, logged as
                           judge_error (never silently counted either way)

Stable-flip rule (docs/plan-prompt-tuning.md §4.5, task-3 brief item 2): a
question counts as a flip candidate only if r1 AND r2 of that condition
BOTH judge "different" against A. If only one run diverges, it's an
UNSTABLE flip -- generation variance, logged separately, excluded from the
queue and from go/no-go arithmetic.

Run (resumable -- skips (arm,cond,run) whose pairs file already exists
unless --force; ~10 concurrent judge calls, ThreadPoolExecutor -- calling
the frozen call_judge() from multiple threads, not modifying it):

    .venv/Scripts/python.exe evals/judge_v3ab.py [--force] [--workers N]

Outputs:
  evals/judge_pairs_v3ab_<arm>_<cond>_r<run>.json  (36 files, one per
    condition-run; same {id, judge, ref_verdict, auto_verdict} row shape
    judge_arm_pairs.py already uses, plus "exception" passthrough)
  evals/judge_v3ab_summary.json  (per arm x condition: no_flip / stable_flip
    / unstable_flip / judge_error / exception id lists + counts)
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lib_v3ab as L  # noqa: E402
from judge_arm_pairs import call_judge, decide_transfer  # noqa: E402 -- frozen, unmodified

EVALS = Path(__file__).parent
SUMMARY_PATH = EVALS / "judge_v3ab_summary.json"
WORKERS = 10


def pairs_path(arm: str, cond: str, run: int) -> Path:
    return EVALS / f"judge_pairs_v3ab_{arm}_{cond}_r{run}.json"


def judge_condition_run(arm: str, cond: str, run: int, ref: dict, workers: int) -> list[dict]:
    cand_rows = L.load_condition_run(arm, cond, run)

    def judge_one(row: dict) -> dict:
        qid = row["id"]
        ref_row = ref[qid]
        if row["exception"] is not None:
            return {"id": qid, "judge": None, "ref_verdict": ref_row["verdict"],
                     "auto_verdict": None, "exception": row["exception"]}
        candidate_text = row["answer"] or ""
        if not candidate_text.strip():
            return {"id": qid, "judge": None, "ref_verdict": ref_row["verdict"],
                     "auto_verdict": None, "exception": "unjudgeable_empty_answer"}
        v = call_judge(row["question"], ref_row["answer"], candidate_text, f"{arm}:{cond}:r{run}:{qid}")
        return {"id": qid, "judge": v, "ref_verdict": ref_row["verdict"],
                 "auto_verdict": decide_transfer(v, ref_row["verdict"]), "exception": None}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(judge_one, cand_rows))
    rows.sort(key=lambda r: r["id"])
    return rows


def run_all(force: bool, workers: int) -> None:
    t0 = time.time()
    n_calls = 0
    for arm in L.ARMS:
        ref = L.condition_a_reference(arm)
        for cond in L.CONDITIONS:
            for run in L.RUNS:
                out = pairs_path(arm, cond, run)
                if out.exists() and not force:
                    print(f"  skip {arm} {cond} r{run} (exists)")
                    continue
                print(f"  judging {arm} {cond} r{run} vs condition-A ({arm}) ...")
                rows = judge_condition_run(arm, cond, run, ref, workers)
                out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
                n_judged = sum(1 for r in rows if r["exception"] is None)
                n_calls += n_judged
                same = sum(1 for r in rows if r["judge"] == "same")
                diff = sum(1 for r in rows if r["judge"] == "different")
                err = sum(1 for r in rows if r["exception"] is None and r["judge"] not in ("same", "different"))
                exc = sum(1 for r in rows if r["exception"] is not None)
                print(f"    -> same={same} different={diff} judge_error={err} exception={exc}  ({out.name})")
    print(f"\n{n_calls} judge calls in {time.time()-t0:.0f}s")


def summarize() -> None:
    """Cross r1/r2 per (arm, condition) into no_flip / stable_flip /
    unstable_flip / judge_error / exception buckets."""
    out = {}
    for arm in L.ARMS:
        out[arm] = {}
        for cond in L.CONDITIONS:
            p1 = pairs_path(arm, cond, 1)
            p2 = pairs_path(arm, cond, 2)
            if not (p1.exists() and p2.exists()):
                raise SystemExit(f"missing judge output for {arm} {cond}: run judge_v3ab.py first")
            r1 = {r["id"]: r for r in json.loads(p1.read_text(encoding="utf-8"))}
            r2 = {r["id"]: r for r in json.loads(p2.read_text(encoding="utf-8"))}

            buckets = {"no_flip": [], "stable_flip": [], "unstable_flip": [],
                       "judge_error": [], "exception": []}
            for qid in L.ALL_QIDS:
                a, b = r1[qid], r2[qid]
                if a["exception"] or b["exception"]:
                    buckets["exception"].append(qid)
                    continue
                ja, jb = a["judge"], b["judge"]
                valid = {"same", "different"}
                if ja not in valid or jb not in valid:
                    buckets["judge_error"].append(qid)
                elif ja == "same" and jb == "same":
                    buckets["no_flip"].append(qid)
                elif ja == "different" and jb == "different":
                    buckets["stable_flip"].append(qid)
                else:
                    buckets["unstable_flip"].append(qid)
            out[arm][cond] = {
                "ref_verdict": {qid: r1[qid]["ref_verdict"] for qid in L.ALL_QIDS},
                **buckets,
                "counts": {k: len(v) for k, v in buckets.items()},
            }
    SUMMARY_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nsummary -> {SUMMARY_PATH}")
    for arm in L.ARMS:
        for cond in L.CONDITIONS:
            c = out[arm][cond]["counts"]
            print(f"  {arm:20s} {cond}: no_flip={c['no_flip']:2d} stable_flip={c['stable_flip']:2d} "
                  f"unstable_flip={c['unstable_flip']:2d} judge_error={c['judge_error']:2d} "
                  f"exception={c['exception']:2d}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-judge even if pairs file exists")
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--summarize-only", action="store_true", help="skip judging, just rebuild the summary")
    args = ap.parse_args()
    if not args.summarize_only:
        run_all(args.force, args.workers)
    summarize()


if __name__ == "__main__":
    main()
