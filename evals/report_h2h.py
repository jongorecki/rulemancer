"""Judge the gpt-5-mini head-to-head arm and compare it to sonnet, paired.

Two jobs, because the OpenRouter arm runner and judge_rulesguru.py speak
different row schemas:

  1. ADAPT: run_openrouter_arm.py writes {model, results:[{id, text, ...}]}
     with no answer_gold. judge_rulesguru.py wants a flat list of rows with
     `answer` and `answer_gold`. This rewrites the former into the latter,
     pulling gold from the question file, so the FROZEN judge is reused
     unchanged rather than reimplemented.

  2. COMPARE: sonnet's verdicts on these exact rows already exist (the Slice 0
     BASE arm), so the comparison is paired per question and costs nothing.

READ THE RESULT ASYMMETRICALLY. The judge IS gpt-5-mini (judge_bakeoff +
openai/gpt-5-mini, frozen). This arm is therefore graded by its own family,
which the RulesGuru held-out report already flagged as bias in gpt-5-mini's
favour. Consequence: a LOSS here is strong evidence, a WIN is weak. Say so
whenever these numbers are quoted.

The set is deliberately half rows sonnet got RIGHT (see build_h2h_set.py) so
that a swap which fixes misses while breaking hits shows up as a regression
rather than a win. Corner Case rows are miss-only and cannot be read as a
paired comparison.

Grading verdicts are Jon's. This prints rates and the per-question flip list
for him to read; it does not decide anything.

Run: `uv run python evals/report_h2h.py`
"""

import collections
import json
import subprocess
import sys
from math import comb
from pathlib import Path

EVALS = Path(__file__).resolve().parent
ARM = EVALS / "answers" / "h2h_gpt5mini.json"
ADAPTED = EVALS / "answers" / "_h2h_gpt5mini_adapted.json"
QUESTIONS = EVALS / "_h2h_set.jsonl"
VERDICTS = EVALS / "h2h_verdicts_gpt5mini.json"
SONNET = EVALS / "layers_slice0_verdicts_base_layers_r1.json"


def exact_mcnemar_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / (2 ** n))


def adapt() -> int:
    arm = json.loads(ARM.read_text(encoding="utf-8"))
    gold, level = {}, {}
    for line in QUESTIONS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            gold[r["id"]] = r.get("answer_gold")
            level[r["id"]] = r.get("level")
    rows = []
    for r in arm["results"]:
        if r.get("error") or not gold.get(r["id"]):
            continue
        rows.append({
            "id": r["id"],
            "question": r["question"],
            # OR arm calls the answer text `text`; the judge wants `answer`.
            "answer": r.get("text") or "",
            "answer_gold": gold[r["id"]],
            "answered": r.get("answered"),
            "model": arm["model"],
        })
    ADAPTED.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(rows)


def main() -> None:
    if not ARM.exists():
        raise SystemExit(f"missing {ARM} -- run the OpenRouter arm first")
    n = adapt()
    print(f"adapted {n} rows -> {ADAPTED.name}")

    if not VERDICTS.exists():
        print("judging with the FROZEN judge (judge_bakeoff + gpt-5-mini)...")
        proc = subprocess.run(
            [sys.executable, "evals/judge_rulesguru.py",
             "--answers", str(ADAPTED), "--questions", str(QUESTIONS),
             "--out", str(VERDICTS)],
            cwd=str(EVALS.parent),
        )
        if proc.returncode != 0:
            raise SystemExit(f"judge failed (exit {proc.returncode})")

    mini = {e["id"]: (e["verdict"] == "same")
            for e in json.loads(VERDICTS.read_text(encoding="utf-8"))["entries"]}
    son_all = json.loads(SONNET.read_text(encoding="utf-8"))["entries"]
    son = {e["id"]: (e["verdict"] == "same") for e in son_all}
    lvl = {e["id"]: e.get("level") for e in son_all}

    shared = sorted(set(mini) & set(son))
    print(f"\n{'=' * 64}\nHEAD TO HEAD -- {len(shared)} paired rows, NO tools either side\n{'=' * 64}")
    sc = sum(son[q] for q in shared)
    mc = sum(mini[q] for q in shared)
    print(f"  claude-sonnet-5 : {sc}/{len(shared)} = {sc / len(shared):.1%}")
    print(f"  gpt-5-mini      : {mc}/{len(shared)} = {mc / len(shared):.1%}")

    # By construction half these rows are sonnet misses, so sonnet's rate here
    # is NOT its true accuracy -- only the paired difference is meaningful.
    print("\n  (set is 50% sonnet misses by design -- read the PAIRED numbers,")
    print("   not these rates, which understate sonnet by construction)")

    b = sum(1 for q in shared if mini[q] and not son[q])   # mini fixed it
    c = sum(1 for q in shared if son[q] and not mini[q])   # mini broke it
    p = exact_mcnemar_p(b, c)
    print(f"\n  gpt-5-mini right / sonnet wrong : {b}   <- recovered")
    print(f"  sonnet right / gpt-5-mini wrong : {c}   <- regressed")
    print(f"  exact McNemar two-sided p       : {p:.4f}")
    if b + c:
        who = "gpt-5-mini" if b > c else "sonnet"
        print(f"  -> {'favours ' + who if p < 0.05 else 'NOT distinguishable from noise'}")

    half = collections.Counter()
    for q in shared:
        half["miss" if not son[q] else "hit"] += 1
    print(f"\n  by half: {dict(half)}")
    rec = sum(1 for q in shared if not son[q] and mini[q])
    brk = sum(1 for q in shared if son[q] and not mini[q])
    print(f"    of sonnet's misses, gpt-5-mini fixed : {rec}")
    print(f"    of sonnet's hits,   gpt-5-mini broke : {brk}")

    print("\n  flips (Jon reads these; the judge does not decide):")
    for q in shared:
        if mini[q] != son[q]:
            print(f"    {q:<9} L{str(lvl.get(q)):<12} "
                  f"{'gpt-5-mini FIXED' if mini[q] else 'gpt-5-mini BROKE'}")

    print("\n  CAVEAT: the judge is gpt-5-mini. This arm is graded by its own")
    print("  family, so a loss is strong evidence and a win is weak.")


if __name__ == "__main__":
    main()
