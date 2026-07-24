"""Aggregate Slice 0 into the numbers Jon's Sec 8.2 ruling actually turns on.

docs/plan-layer-system-tool.md Sec 6.1/6.3. Reports, for BASE vs CONTROL:

  * win-rate on the 54-row bucket-A COMPUTE set
  * regression on the frozen 100-row non-layers sample
  * a PAIRED comparison (same question, same rep index) with an exact McNemar
    sign test, because the arms are matched and the pooled-rate difference on
    54 questions is easy to over-read
  * the four Sec 1.1 seeds broken out individually -- they are the Sec 6.1
    diagnostic, not the test set
  * truncation counts (stop_reason == "max_tokens"), which are measurement
    noise rather than wrong answers and bias whichever arm runs longer

Aggregate before claiming a rate; a single favourable run is not a rate.

Grading verdicts are Jon's. This prints the frozen auto-judge numbers and the
disagreement list for him to read -- it does not assign a verdict.

Run: `uv run python evals/report_layers_slice0.py`
"""

import json
from collections import defaultdict
from math import comb
from pathlib import Path

EVALS = Path(__file__).resolve().parent
ANSWERS = EVALS / "answers"

ARMS = ["base", "control"]
SETS = {"layers": 3, "regression": 2}
SEEDS = ["rg3868", "rg807", "rg811", "rg633"]  # Sec 1.1; rg633 is NOT fixable


def exact_mcnemar_p(b: int, c: int) -> float:
    """Two-sided exact sign test on the discordant pairs only.

    b = questions the CONTROL arm got right and BASE got wrong,
    c = the reverse. Concordant pairs carry no information about which arm is
    better, which is exactly why a paired test is the honest one here.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def load(set_name: str) -> tuple[dict, dict, list[str]]:
    """-> (verdicts[arm][rep][qid] = bool_correct, rows[arm][rep][qid] = row, missing)"""
    verdicts: dict = defaultdict(lambda: defaultdict(dict))
    rows: dict = defaultdict(lambda: defaultdict(dict))
    missing = []
    for arm in ARMS:
        for rep in range(1, SETS[set_name] + 1):
            tag = f"{arm}_{set_name}_r{rep}"
            vp = EVALS / f"layers_slice0_verdicts_{tag}.json"
            ap = ANSWERS / f"layers_slice0_{tag}.json"
            if not vp.exists():
                missing.append(str(vp.name))
                continue
            for e in json.loads(vp.read_text(encoding="utf-8"))["entries"]:
                verdicts[arm][rep][e["id"]] = (e["verdict"] == "same")
            if ap.exists():
                for r in json.loads(ap.read_text(encoding="utf-8")):
                    rows[arm][rep][r["id"]] = r
    return verdicts, rows, missing


def pooled_rate(verdicts: dict, arm: str, reps: int) -> tuple[int, int]:
    correct = total = 0
    for rep in range(1, reps + 1):
        for ok in verdicts[arm][rep].values():
            total += 1
            correct += bool(ok)
    return correct, total


def report_set(set_name: str) -> None:
    reps = SETS[set_name]
    verdicts, rows, missing = load(set_name)
    print(f"\n{'=' * 68}\n{set_name.upper()}  ({reps} reps/arm)\n{'=' * 68}")
    if missing:
        print(f"  MISSING verdict files ({len(missing)}): {', '.join(missing)}")
        if all(not verdicts[a] for a in ARMS):
            print("  nothing to report for this set.")
            return

    for arm in ARMS:
        c, t = pooled_rate(verdicts, arm, reps)
        pct = f"{100 * c / t:.1f}%" if t else "n/a"
        print(f"  {arm:<8} pooled {c}/{t} = {pct}")

    # Paired, per (question, rep). Only pairs present in BOTH arms count.
    b = c_ = concordant = pairs = 0
    flips = []
    for rep in range(1, reps + 1):
        shared = set(verdicts["base"][rep]) & set(verdicts["control"][rep])
        for qid in sorted(shared):
            base_ok = verdicts["base"][rep][qid]
            ctrl_ok = verdicts["control"][rep][qid]
            pairs += 1
            if base_ok == ctrl_ok:
                concordant += 1
            elif ctrl_ok:
                b += 1
                flips.append((qid, rep, "control fixed it"))
            else:
                c_ += 1
                flips.append((qid, rep, "control BROKE it"))

    p = exact_mcnemar_p(b, c_)
    print(f"\n  paired on {pairs} (question, rep) pairs: {concordant} agree")
    print(f"    control right / base wrong : {b}")
    print(f"    base right / control wrong : {c_}")
    print(f"    exact McNemar two-sided p  : {p:.3f}")
    if b + c_ and p >= 0.05:
        print("    -> NOT distinguishable from noise at this sample size.")
    elif b + c_:
        print(f"    -> real difference, favouring {'control' if b > c_ else 'base'}.")

    if flips:
        print("\n  discordant pairs (Jon reads these, the judge does not decide):")
        for qid, rep, what in flips:
            print(f"    {qid:<10} rep{rep}  {what}")

    # Truncation is measurement noise, not a wrong answer.
    for arm in ARMS:
        trunc = [
            (qid, rep)
            for rep in range(1, reps + 1)
            for qid, r in rows[arm][rep].items()
            if r.get("stop_reason") == "max_tokens"
        ]
        if trunc:
            print(f"\n  !! {arm}: {len(trunc)} truncated (stop_reason=max_tokens)"
                  f" -- rg3391 class, scored as wrong but is not a reasoning miss")
            for qid, rep in trunc[:10]:
                print(f"     {qid} rep{rep}")

    if set_name == "layers":
        print("\n  the four Sec 1.1 seeds (diagnostic, not the test set):")
        for qid in SEEDS:
            cells = []
            for arm in ARMS:
                got = [verdicts[arm][rep].get(qid) for rep in range(1, reps + 1)]
                cells.append(
                    f"{arm}=" + "".join(
                        "." if g is None else ("Y" if g else "n") for g in got
                    )
                )
            note = "  (rg633 is NOT expected to be fixed -- Sec 1.3)" if qid == "rg633" else ""
            print(f"    {qid:<10} {'  '.join(cells)}{note}")


def main() -> None:
    print("Slice 0 -- CONTROL ARM vs BASE (docs/plan-layer-system-tool.md Sec 6.1)")
    print("Judge: judge_bakeoff prompt + gpt-5-mini, FROZEN. Verdicts are Jon's.")
    for set_name in SETS:
        report_set(set_name)
    print(f"\n{'=' * 68}")
    print("The Sec 8.2 bar for Slice 5: the tool must TIE OR BEAT the better of")
    print("these two arms on BOTH win-rate and regression.")


if __name__ == "__main__":
    main()
