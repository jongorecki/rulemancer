"""v5 grid (docs/plan-v5-symbol-injection.md §3): judge-compare each of the
2x2 bullets x injection cells (A=v3 production baseline, B=v3+injection,
C=v4nl, D=v5 the candidate) against that SAME arm's SAME question's existing
graded condition-C (v3) answer, using judge_arm_pairs.py's frozen
call_judge()/decide_transfer() -- unchanged, same import judge_v3ab.py and
judge_v4.py already use.

**The reference.** "Condition C" (old B/C/D grid naming,
docs/plan-prompt-tuning.md) is v3 production -- confirmed by
docs/plan-v4e-execution-tasks.md's own grid table ("sonnet cond C v3 = 46",
"gpt-5-mini cond C v3 = 45") and by DECISIONS.md's 2026-07-25 v4-revert entry
(PROMPT_VERSION 4 -> 3, i.e. back to condition C's prompt). Task 5
(evals/judge_v4.py) already built exactly this "condition-C (v3) answer,
graded" reference -- evals/v4_c_reference_<arm>_r<run>.json, condition A
folded with condition C's Jon-graded STABLE flips (v3ab_stable_flip_index.json
+ verdicts_v3ab.json), condition A elsewhere (judge_pairs_v3ab_<arm>_C_r<run>.json
auto-transfer). This module reads those files read-only and reuses them
verbatim as the reference for every v5-grid cell -- nothing here rebuilds or
edits that derivation. Coverage was checked by hand for every (arm, qid, run)
this grid needs (sonnet: c012/c014/c015 x r1/r2; gpt-5-mini:
c002/c004/c011/c012/c015 x r1/r2 -- 16 lookups total) against both
v4_c_reference_<arm>_r<run>.json files (50 qids each, so every id used here is
present) -- all covered, so there is no missing-reference case to stop on for
this run (see the commit message for the check).

  judge = "same"       -> auto_verdict = the condition-C (v3) reference's
                          verdict transfers (correct AND wrong both
                          transfer -- the judge routes, it never grades)
  judge = "different"  -> auto_verdict = None; a candidate flip vs v3,
                          routed to Jon's queue
  judge = error/unparsed after retries -> excluded from both buckets,
                          logged as judge_error

Stable-flip rule (unchanged from every prior A/B in this programme): a
question counts as a flip candidate only if r1 AND r2 both judge "different"
against the reference. Unstable otherwise -- excluded from the arithmetic and
the queue, logged separately.

c002 (gpt-5-mini only) is MONITORED, NON-SCORING per cards.jsonl's
`scoring_status` field and DECISIONS.md's 2026-07-25 entry: it runs, it is
judged, and its result is reported under its own heading, but it never enters
a cell's scoring counts (transfers / flips / unstable / judge_error) or any
correct-count / go-no-go delta.

Cell A is v3 vs v3 (a fresh v5-grid capture of the unmodified production
prompt, judged against the same v3 answer it derives from) -- a negative
control. Its transfer rate should be ~100%; report it prominently. A low
transfer rate on cell A means the run or the routing broke, not that the
prompt did something.

Run:
    .venv/Scripts/python.exe evals/judge_v5.py [--force] [--workers N]

Outputs:
  evals/judge_pairs_v5_<arm>_<cell>_r<run>.json  (16 files: {sonnet,
    gpt-5-mini} x {A,B,C,D} x {r1,r2}; same {id, judge, ref_verdict,
    auto_verdict, exception} row shape judge_v4.py/judge_v3ab.py produce)
  evals/judge_v5_summary.json  (per arm x cell: scoring no_flip/stable_flip/
    unstable_flip/judge_error/exception id lists + counts, PLUS a separate
    monitored_non_scoring block for c002)
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from judge_arm_pairs import call_judge, decide_transfer  # noqa: E402 -- frozen, unmodified

EVALS = Path(__file__).parent
ANSWERS = EVALS / "answers"
SUMMARY_PATH = EVALS / "judge_v5_summary.json"

ARMS = ["sonnet", "gpt-5-mini"]
CELLS = ["A", "B", "C", "D"]
RUNS = [1, 2]
WORKERS = 10

# docs/plan-v5-symbol-injection.md §3 Phase-1 question set (arm runs its own
# misses only -- this is NOT the full 50-question grid).
ARM_QIDS = {
    "sonnet": ["c012", "c014", "c015"],
    "gpt-5-mini": ["c002", "c004", "c011", "c012", "c015"],
}

# DECISIONS.md 2026-07-25 "c002 is excluded from scoring" + cards.jsonl
# c002.scoring_status. Monitored, never scored.
NON_SCORING_QIDS = {"c002"}

CELL_LABEL = {
    "A": "v3 (production baseline)",
    "B": "v3 + injection",
    "C": "v4nl",
    "D": "v5 (the candidate)",
}

# Historical figures, quoted as-written (docs/plan-v5-symbol-injection.md §6)
# -- NOT recomputed here. Forward counts from this script are on the
# Phase-1 miss subset only (3 or 5 questions per arm), not the full 50.
HISTORICAL_BASELINE_QUOTED = {
    "note": "Quoted from docs/plan-v5-symbol-injection.md Section 6, not "
            "recomputed by this script. /49-style = c002 excluded from the "
            "full 50-question grid's denominator.",
    "sonnet": {"all_50": 46, "c002_excluded": "45/49"},
    "gpt-5-mini": {"all_50": 45, "c002_excluded": "44/49"},
}


def _load_json(path: Path):
    if not path.exists():
        raise SystemExit(f"missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ==================================================================
# IO: reference + candidate loading
# ==================================================================

def load_reference(arm: str, run: int) -> dict:
    """The existing graded condition-C (v3) answer, per (arm, run) -- built
    for Task 5, reused verbatim here. See module docstring."""
    path = EVALS / f"v4_c_reference_{arm}_r{run}.json"
    if not path.exists():
        raise SystemExit(
            f"missing {path} -- this is the existing graded condition-C (v3) "
            "reference (Task 5's derivation); cannot judge without it. Per "
            "task instructions, STOP rather than improvise a reference."
        )
    return _load_json(path)


def candidate_exception(error, answer_text) -> str | None:
    """Same gating judge_v3ab.py/judge_v4.py use: a provider-side error
    excludes the row; otherwise only a genuinely blank answer is
    unjudgeable. Deliberately does NOT key off an "answered" flag -- the v5
    grid data has rows marked answered=False that still carry a full answer
    (the runner's own hedged/honesty flag, unrelated to judgeability), and
    gating on that field would silently exclude real answers from being
    judged, which the frozen pattern never does."""
    if error:
        return "provider_error"
    if not (answer_text or "").strip():
        return "unjudgeable_empty_answer"
    return None


def load_candidate_rows(arm: str, cell: str, run: int) -> list[dict]:
    """Normalized candidate rows for one (arm, cell, run), scoped to
    ARM_QIDS[arm]: [{id, question, answer, exception}]. Handles the two
    answers/ file conventions the v5 grid runner used:
      - sonnet: answers/sonnet_v5g<cell>_r<run>_cards.json, flat list,
        answer text in row["answer"]
      - gpt-5-mini: answers/gpt-5-mini_v5g<cell>_r<run>.json,
        {"results": [...]}, answer text in row["text"]
    """
    if arm == "sonnet":
        path = ANSWERS / f"sonnet_v5g{cell}_r{run}_cards.json"
        raw_rows = _load_json(path)
        text_key = "answer"
    else:
        path = ANSWERS / f"{arm}_v5g{cell}_r{run}.json"
        payload = _load_json(path)
        raw_rows = payload["results"]
        text_key = "text"

    by_id = {r["id"]: r for r in raw_rows}
    expected = set(ARM_QIDS[arm])
    missing = expected - set(by_id)
    if missing:
        raise SystemExit(f"{arm} v5g{cell} r{run} ({path.name}): missing ids {sorted(missing)}")

    rows = []
    for qid in ARM_QIDS[arm]:
        r = by_id[qid]
        answer_text = r.get(text_key)
        exception = candidate_exception(r.get("error"), answer_text)
        rows.append({"id": qid, "question": r.get("question", ""), "answer": answer_text, "exception": exception})
    return rows


# ==================================================================
# Pure decision logic -- unit tested in tests/test_judge_v5.py with a
# stubbed judge_fn. No network here.
# ==================================================================

def route_row(qid: str, question: str, ref_row: dict, candidate_row: dict, judge_fn) -> dict:
    """One candidate row vs its condition-C (v3) reference row.
    judge_fn(question, reference_answer, candidate_answer, row_id) -> judge
    verdict string ("same"|"different"|"error"|"unparsed").

    judge=="same"      -> auto_verdict = ref_row["verdict"] (transfers,
                          correct AND wrong both transfer -- the judge
                          routes, it never grades)
    judge=="different" -> auto_verdict = None (candidate flip, Jon's queue)
    judge==error/unparsed -> auto_verdict = None (judge_error, excluded from
                          both buckets)
    candidate_row has an exception (provider error / empty answer) -> never
                          calls the judge; auto_verdict = None, exception
                          passthrough.
    """
    if candidate_row["exception"] is not None:
        return {"id": qid, "judge": None, "ref_verdict": ref_row["verdict"],
                 "auto_verdict": None, "exception": candidate_row["exception"]}
    v = judge_fn(question, ref_row["answer"], candidate_row["answer"], qid)
    return {"id": qid, "judge": v, "ref_verdict": ref_row["verdict"],
             "auto_verdict": decide_transfer(v, ref_row["verdict"]), "exception": None}


def classify_stability(row_r1: dict, row_r2: dict) -> str:
    """no_flip / stable_flip / unstable_flip / judge_error / exception.

    Stable-flip rule (unchanged from every prior A/B in this programme,
    docs/plan-prompt-tuning.md task-3 brief item 2): a flip counts only if
    BOTH runs judge "different" against the reference. Only one run
    diverging is an UNSTABLE flip -- generation variance, excluded from the
    arithmetic and the queue.
    """
    if row_r1["exception"] or row_r2["exception"]:
        return "exception"
    ja, jb = row_r1["judge"], row_r2["judge"]
    valid = {"same", "different"}
    if ja not in valid or jb not in valid:
        return "judge_error"
    if ja == "same" and jb == "same":
        return "no_flip"
    if ja == "different" and jb == "different":
        return "stable_flip"
    return "unstable_flip"


def bucket_qids(arm: str, r1_by_id: dict, r2_by_id: dict) -> dict:
    """Split this arm's ARM_QIDS into a scoring bucket-set and a
    monitored_non_scoring bucket-set (c002 only, gpt-5-mini), each shaped
    {no_flip: [...], stable_flip: [...], unstable_flip: [...],
    judge_error: [...], exception: [...]}. c002 NEVER lands in the scoring
    buckets, enforced here by qid, not by post-hoc filtering."""
    scoring = {"no_flip": [], "stable_flip": [], "unstable_flip": [], "judge_error": [], "exception": []}
    non_scoring = {"no_flip": [], "stable_flip": [], "unstable_flip": [], "judge_error": [], "exception": []}
    for qid in ARM_QIDS[arm]:
        bucket = classify_stability(r1_by_id[qid], r2_by_id[qid])
        target = non_scoring if qid in NON_SCORING_QIDS else scoring
        target[bucket].append(qid)
    return {"scoring": scoring, "monitored_non_scoring": non_scoring}


# ==================================================================
# IO / network -- not unit tested (network call), exercised by main()
# ==================================================================

def pairs_path(arm: str, cell: str, run: int) -> Path:
    return EVALS / f"judge_pairs_v5_{arm}_{cell}_r{run}.json"


def judge_cell_run(arm: str, cell: str, run: int, ref: dict, workers: int) -> list[dict]:
    cand_rows = load_candidate_rows(arm, cell, run)

    def judge_one(row: dict) -> dict:
        qid = row["id"]
        ref_row = ref[qid]

        def judge_fn(question, reference, candidate, rid):
            return call_judge(question, reference, candidate, f"{arm}:v5{cell}:r{run}:{rid}")

        return route_row(qid, row["question"], ref_row, row, judge_fn)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(judge_one, cand_rows))
    rows.sort(key=lambda r: r["id"])
    return rows


def run_all(force: bool, workers: int) -> None:
    t0 = time.time()
    n_calls = 0
    for arm in ARMS:
        for cell in CELLS:
            for run in RUNS:
                out = pairs_path(arm, cell, run)
                if out.exists() and not force:
                    print(f"  skip {arm} v5{cell} r{run} (exists)")
                    continue
                ref = load_reference(arm, run)
                print(f"  judging {arm} v5{cell} ({CELL_LABEL[cell]}) r{run} "
                      f"vs condition-C (v3) reference ({arm}) ...")
                rows = judge_cell_run(arm, cell, run, ref, workers)
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
    out = {"_historical_baseline_quoted": HISTORICAL_BASELINE_QUOTED, "_reference_files_used": {}}
    for arm in ARMS:
        out["_reference_files_used"][arm] = [
            f"v4_c_reference_{arm}_r1.json", f"v4_c_reference_{arm}_r2.json",
        ]
        out[arm] = {}
        for cell in CELLS:
            p1, p2 = pairs_path(arm, cell, 1), pairs_path(arm, cell, 2)
            if not (p1.exists() and p2.exists()):
                raise SystemExit(f"missing judge output for {arm} v5{cell}: run judge_v5.py first")
            r1 = {r["id"]: r for r in _load_json(p1)}
            r2 = {r["id"]: r for r in _load_json(p2)}

            buckets = bucket_qids(arm, r1, r2)
            scoring, non_scoring = buckets["scoring"], buckets["monitored_non_scoring"]
            out[arm][cell] = {
                "label": CELL_LABEL[cell],
                "ref_verdict": {qid: r1[qid]["ref_verdict"] for qid in ARM_QIDS[arm]},
                "scoring": {**scoring, "counts": {k: len(v) for k, v in scoring.items()}},
                "monitored_non_scoring": {**non_scoring, "counts": {k: len(v) for k, v in non_scoring.items()}},
            }
    SUMMARY_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nsummary -> {SUMMARY_PATH}")
    for arm in ARMS:
        for cell in CELLS:
            c = out[arm][cell]["scoring"]["counts"]
            nc = out[arm][cell]["monitored_non_scoring"]["counts"]
            n_scoring = sum(c.values())
            transfer_rate = f"{c['no_flip']}/{n_scoring}" if n_scoring else "n/a"
            flag = "  <-- NEGATIVE CONTROL, should be ~100% transfer" if cell == "A" else ""
            print(f"  {arm:12s} v5{cell} ({CELL_LABEL[cell]:24s}): scoring transfer={transfer_rate} "
                  f"stable_flip={c['stable_flip']} unstable_flip={c['unstable_flip']} "
                  f"judge_error={c['judge_error']} exception={c['exception']}{flag}")
            if sum(nc.values()):
                print(f"    {'':12s} MONITORED, NON-SCORING (c002): no_flip={nc['no_flip']} "
                      f"stable_flip={nc['stable_flip']} unstable_flip={nc['unstable_flip']} "
                      f"judge_error={nc['judge_error']} exception={nc['exception']}")


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
