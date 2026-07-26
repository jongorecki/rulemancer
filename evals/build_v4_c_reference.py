"""Task 5 (docs/plan-v4e-execution-tasks.md): derive the condition-C (v3)
reference each v4 cell is judge-compared against.

Condition A never had per-arm judge-compare re-runs against itself, but
condition C did (the v3 A/B, evals/judge_v3ab.py) -- and Jon graded the
resulting stable-flip queue (evals/verdicts_v3ab.json). So "condition C's
outcome" for an arm is: condition-A's baseline verdict/answer for every
question EXCEPT the ids that stably flipped in condition C for that arm,
where the flip's own condition-C answer text and Jon's graded verdict from
verdicts_v3ab.json are substituted instead.

Built per RUN (r1, r2) because condition C itself has two runs and a
stable-flip qid's graded verdict can differ slightly by run (e.g.
gpt-5-mini/c015: r1 graded wrong, r2 graded partial -- both non-correct, so
it never changes the correct-count either way, but the text differs and
matters for the judge call). Non-flip ids use the SAME condition-A answer
for both runs (by definition they judged "same" as A in both runs of C).

sonnet has ZERO stable flips in condition C (confirmed against
judge_v3ab_summary.json) -- its reference is condition-A's baseline
unchanged in both runs, already reflecting the 2026-07-22 c004
correct-with-note ruling (baked into verdicts_sonnet-v2_final.json).

Sanity gate (must print before anything downstream is trusted): the
derived reference's correct-count (verdict=="correct") must equal
sonnet 46/50 and gpt-5-mini 45/50 -- the published condition-C baselines.

Output: evals/v4_c_reference_<arm>_r<run>.json
        {qid: {answer, verdict, source: "condition_a"|"condition_c_flip"}}
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lib_v3ab as L  # noqa: E402

EVALS = Path(__file__).parent
SUMMARY_PATH = EVALS / "judge_v3ab_summary.json"
VERDICTS_V3AB_PATH = EVALS / "verdicts_v3ab.json"

ARMS = ["sonnet", "gpt-5-mini"]
RUNS = [1, 2]
COND = "C"


def load_v3ab_verdicts() -> dict[str, dict]:
    rows = json.loads(VERDICTS_V3AB_PATH.read_text(encoding="utf-8"))
    return {r["id"]: r for r in rows}


def build_reference(arm: str, run: int, summary: dict, v3ab_verdicts: dict) -> dict:
    a_ref = L.condition_a_reference(arm)
    stable_flips = summary[arm][COND]["stable_flip"]

    out = {}
    for qid in L.ALL_QIDS:
        if qid in stable_flips:
            key = f"{arm}_{COND}_r{run}:{qid}"
            if key not in v3ab_verdicts:
                raise ValueError(
                    f"stable flip {arm}/{COND}/r{run}:{qid} has no graded verdict "
                    f"in {VERDICTS_V3AB_PATH.name} (id {key!r} missing)"
                )
            cand_row = {r["id"]: r for r in L.load_condition_run(arm, COND, run)}[qid]
            out[qid] = {
                "answer": cand_row["answer"] or "",
                "verdict": v3ab_verdicts[key]["verdict"],
                "source": "condition_c_flip",
                "note": v3ab_verdicts[key].get("note", ""),
            }
        else:
            out[qid] = {
                "answer": a_ref[qid]["answer"],
                "verdict": a_ref[qid]["verdict"],
                "source": "condition_a",
                "note": "",
            }
    return out


def main() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    v3ab_verdicts = load_v3ab_verdicts()

    print("=== sanity gate: derived condition-C reference correct-counts ===")
    all_ok = True
    for arm in ARMS:
        for run in RUNS:
            ref = build_reference(arm, run, summary, v3ab_verdicts)
            out_path = EVALS / f"v4_c_reference_{arm}_r{run}.json"
            out_path.write_text(json.dumps(ref, indent=2, ensure_ascii=False), encoding="utf-8")
            n_correct = sum(1 for v in ref.values() if v["verdict"] == "correct")
            n_flip = sum(1 for v in ref.values() if v["source"] == "condition_c_flip")
            expected = {"sonnet": 46, "gpt-5-mini": 45}[arm]
            status = "OK" if n_correct == expected else "MISMATCH"
            if n_correct != expected:
                all_ok = False
            print(f"  {arm} r{run}: correct={n_correct}/50 (expected {expected}) "
                  f"[{status}]  flips_applied={n_flip}  -> {out_path.name}")

    if not all_ok:
        print("\nSANITY GATE FAILED -- STOP, do not proceed on this reference.")
        sys.exit(1)
    print("\nSanity gate PASSED for both arms/runs.")


if __name__ == "__main__":
    main()
