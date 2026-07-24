"""Task 5: judge-compare each v4 cell's answer against that SAME arm's
DERIVED condition-C (v3) reference (evals/build_v4_c_reference.py's
output), using judge_arm_pairs.py's frozen call_judge()/decide_transfer()
-- unchanged, same import judge_v3ab.py already uses. Only the reference
side is new: instead of "vs condition A" (judge_v3ab.py) this is "vs
condition A with condition C's graded flips folded in" (the actual thing
this A/B is meant to move against, per docs/plan-v4e-execution-tasks.md
Task 5).

Decision set: sonnet (cell: v4) and gpt-5-mini (cell: v4 default only --
effort=high was killed on latency before grading, per DECISIONS.md
2026-07-24, and never run).

  judge = "same"      -> auto_verdict = the derived condition-C reference's
                         verdict transfers (correct AND wrong both
                         transfer -- the judge routes, it never grades)
  judge = "different"  -> auto_verdict = None; a candidate flip vs C,
                         routed to Jon's queue
  judge = error/unparsed after retries -> excluded from both buckets,
                         logged as judge_error

Stable-flip rule (unchanged from the v3 A/B): counts only if r1 AND r2
both judge "different" against the reference. Unstable otherwise --
excluded from arithmetic and the queue, logged separately.

Run:
    .venv/Scripts/python.exe evals/judge_v4.py [--force] [--workers N]

Outputs:
  evals/judge_pairs_v4_<arm>_r<run>.json  (4 files: sonnet/gpt-5-mini x r1/r2;
    same {id, judge, ref_verdict, auto_verdict, exception} row shape
    judge_v3ab.py already produces)
  evals/judge_v4_summary.json  (per arm: no_flip/stable_flip/unstable_flip/
    judge_error/exception id lists + counts, plus decline counts)
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
SUMMARY_PATH = EVALS / "judge_v4_summary.json"
ARMS = ["sonnet", "gpt-5-mini"]
RUNS = [1, 2]
COND = "v4"
WORKERS = 10


def load_reference(arm: str, run: int) -> dict:
    path = EVALS / f"v4_c_reference_{arm}_r{run}.json"
    if not path.exists():
        raise SystemExit(f"missing {path} -- run evals/build_v4_c_reference.py first")
    return json.loads(path.read_text(encoding="utf-8"))


def pairs_path(arm: str, run: int) -> Path:
    return EVALS / f"judge_pairs_v4_{arm}_r{run}.json"


def judge_run(arm: str, run: int, ref: dict, workers: int) -> list[dict]:
    cand_rows = L.load_condition_run(arm, COND, run)

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
        v = call_judge(row["question"], ref_row["answer"], candidate_text, f"{arm}:v4:r{run}:{qid}")
        return {"id": qid, "judge": v, "ref_verdict": ref_row["verdict"],
                 "auto_verdict": decide_transfer(v, ref_row["verdict"]), "exception": None}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(judge_one, cand_rows))
    rows.sort(key=lambda r: r["id"])
    return rows


def run_all(force: bool, workers: int) -> None:
    t0 = time.time()
    n_calls = 0
    for arm in ARMS:
        for run in RUNS:
            out = pairs_path(arm, run)
            if out.exists() and not force:
                print(f"  skip {arm} r{run} (exists)")
                continue
            ref = load_reference(arm, run)
            print(f"  judging {arm} v4 r{run} vs derived condition-C reference ({arm}) ...")
            rows = judge_run(arm, run, ref, workers)
            out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            n_judged = sum(1 for r in rows if r["exception"] is None)
            n_calls += n_judged
            same = sum(1 for r in rows if r["judge"] == "same")
            diff = sum(1 for r in rows if r["judge"] == "different")
            err = sum(1 for r in rows if r["exception"] is None and r["judge"] not in ("same", "different"))
            exc = sum(1 for r in rows if r["exception"] is not None)
            print(f"    -> same={same} different={diff} judge_error={err} exception={exc}  ({out.name})")
    print(f"\n{n_calls} judge calls in {time.time()-t0:.0f}s")


def decline_counts() -> dict:
    """answered==False counts per arm, v4 vs condition C, per run + combined."""
    out = {}
    for arm in ARMS:
        out[arm] = {}
        for cond in ("C", "v4"):
            for run in RUNS:
                rows = L.load_condition_run(arm, cond, run)
                declined = sorted(r["id"] for r in rows if r["answered"] is False)
                out[arm][f"{cond}_r{run}"] = {"n_declined": len(declined), "ids": declined}
    return out


def summarize() -> None:
    out = {}
    for arm in ARMS:
        p1, p2 = pairs_path(arm, 1), pairs_path(arm, 2)
        if not (p1.exists() and p2.exists()):
            raise SystemExit(f"missing judge output for {arm}: run judge_v4.py first")
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
        out[arm] = {
            "ref_verdict": {qid: r1[qid]["ref_verdict"] for qid in L.ALL_QIDS},
            **buckets,
            "counts": {k: len(v) for k, v in buckets.items()},
        }
    out["_decline_counts"] = decline_counts()
    SUMMARY_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nsummary -> {SUMMARY_PATH}")
    for arm in ARMS:
        c = out[arm]["counts"]
        print(f"  {arm:12s} v4: no_flip={c['no_flip']:2d} stable_flip={c['stable_flip']:2d} "
              f"unstable_flip={c['unstable_flip']:2d} judge_error={c['judge_error']:2d} "
              f"exception={c['exception']:2d}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--summarize-only", action="store_true")
    args = ap.parse_args()
    if not args.summarize_only:
        run_all(args.force, args.workers)
    summarize()


if __name__ == "__main__":
    main()
