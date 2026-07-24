"""Slice 0 driver -- the control arm for the layer-system tool.

docs/plan-layer-system-tool.md Sec 6.1 / Sec 9 Slice 0, per Jon's Sec 8.2
ruling (the tool must TIE OR BEAT this arm on win-rate AND regression).

Runs two arms, neither of which may have the layers tool attached:

  BASE     production system prompt, layers tool OFF
  CONTROL  system prompt + CR 613.6/611.3a bullet ("v3+613"), layers tool OFF

over two question sets:

  layers      the 54 bucket-A COMPUTE rows (evals/_layers_buckets.json)
  regression  the frozen 100-row non-layers sample

BASE is also Slice 5's tool-off arm, so it is paid for once and used twice.

Reps: 3 on layers, 2 on regression. A single favourable run is not a rate
(Sec 6.3), and the regression arm is looking for a material swing rather than a
one-question difference, so it needs fewer.

RESUMABLE: a run whose answers file already exists is skipped, so an
interrupted run picks up where it stopped instead of re-spending. Delete the
file to force a re-run.

Run: `uv run python evals/run_layers_slice0.py [--dry-run] [--only ARM] [--sets SET]`
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

EVALS = Path(__file__).resolve().parent
REPO = EVALS.parent
ANSWERS = EVALS / "answers"
LOG_DIR = EVALS / "_slice0_logs"

BUCKETS_PATH = EVALS / "_layers_buckets.json"
UNION_SLICE = EVALS / "_layers_union_slice.jsonl"
REGRESSION_SAMPLE = EVALS / "_layers_regression_sample.jsonl"

# arm -> extra flags for run_answer_eval.py. Both arms suppress the layers
# tool; they differ ONLY in the system prompt. Keep it that way -- any other
# difference makes the Sec 8.2 comparison uninterpretable.
ARMS = {
    "base": ["--no-layers-tool"],
    "control": ["--no-layers-tool", "--system-version", "v3+613"],
}

SETS = {
    "layers": {"questions": UNION_SLICE, "reps": 3},
    "regression": {"questions": REGRESSION_SAMPLE, "reps": 2},
}


def bucket_a_ids() -> list[str]:
    buckets = json.loads(BUCKETS_PATH.read_text(encoding="utf-8"))
    return [qid for qid, bucket in buckets.items() if bucket == "A"]


def _run(cmd: list[str], log_path: Path, dry_run: bool) -> None:
    printable = " ".join(cmd)
    print(f"  $ {printable}", flush=True)
    if dry_run:
        return
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"$ {printable}\n\n")
        log.flush()
        # Never pipe a long run through `| tail` -- it masks the exit code.
        # Tee to a file and check returncode explicitly instead.
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                              cwd=str(REPO), env=env)
    if proc.returncode != 0:
        raise SystemExit(
            f"FAILED (exit {proc.returncode}): {printable}\n  log: {log_path}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the commands without running them (no API calls)")
    ap.add_argument("--only", choices=sorted(ARMS), default=None,
                    help="run just one arm")
    ap.add_argument("--sets", choices=sorted(SETS), default=None,
                    help="run just one question set")
    args = ap.parse_args()

    # Create the log dir up front, not lazily in _run(). A caller redirecting
    # this script's own stdout into LOG_DIR (the obvious way to run it
    # unattended) fails before main() gets a chance to create it, and the
    # shell reports that failure as the exit status of whatever ran last --
    # so an 11-hour run "succeeds" in milliseconds having done nothing.
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ANSWERS.mkdir(parents=True, exist_ok=True)

    qids = ",".join(bucket_a_ids())
    arms = [args.only] if args.only else sorted(ARMS)
    sets = [args.sets] if args.sets else sorted(SETS)

    planned, skipped = 0, 0
    started = time.time()

    for set_name in sets:
        spec = SETS[set_name]
        for arm in arms:
            for rep in range(1, spec["reps"] + 1):
                tag = f"{arm}_{set_name}_r{rep}"
                out = ANSWERS / f"layers_slice0_{tag}.json"
                verdicts = EVALS / f"layers_slice0_verdicts_{tag}.json"

                if out.exists() and verdicts.exists():
                    print(f"[skip] {tag} (already complete)", flush=True)
                    skipped += 1
                    continue

                print(f"[run ] {tag}", flush=True)
                gen = [
                    sys.executable, "evals/run_answer_eval.py",
                    "--questions", str(spec["questions"]),
                    "--out", str(out),
                    "--run", str(rep),
                    "--condition", tag,
                    *ARMS[arm],
                ]
                # The layers set is a 54-row subset of the 68-row union slice;
                # the regression set is run whole.
                if set_name == "layers":
                    gen += ["--qids", qids]

                if not out.exists():
                    _run(gen, LOG_DIR / f"{tag}.gen.log", args.dry_run)

                judge = [
                    sys.executable, "evals/judge_rulesguru.py",
                    "--answers", str(out),
                    "--questions", str(spec["questions"]),
                    "--out", str(verdicts),
                ]
                _run(judge, LOG_DIR / f"{tag}.judge.log", args.dry_run)
                planned += 1

    mins = (time.time() - started) / 60
    print(f"\ndone: {planned} run(s), {skipped} skipped, {mins:.1f} min")
    if not args.dry_run and planned:
        print("next: uv run python evals/report_layers_slice0.py")


if __name__ == "__main__":
    main()
