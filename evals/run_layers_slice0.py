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

RESUMABLE, on ROW COUNT rather than file existence: an arm counts as done
only when its answers file holds the full expected number of rows AND has been
judged. A killed run leaves a partial file behind (run_answer_eval.py persists
after every question), and that partial is resumed, not judged as if whole --
judging it would compute a rate over the wrong denominator and report it with
no error. Delete an answers file to force a full re-run.

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


def _row_count(path: Path) -> int:
    """Rows already written to an answers file, 0 if absent/unreadable.

    run_answer_eval.py persists atomically after every question, so this is
    the honest completeness signal -- file existence is not."""
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    return len(data) if isinstance(data, list) else 0


def _jsonl_len(path: Path) -> int:
    """Non-blank lines in a .jsonl question file."""
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


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
        # How many rows a COMPLETE arm has: the bucket-A subset for the layers
        # set, every row of the file for the regression set.
        expected_n = (
            len(qids.split(",")) if set_name == "layers"
            else _jsonl_len(spec["questions"])
        )
        for arm in arms:
            for rep in range(1, spec["reps"] + 1):
                tag = f"{arm}_{set_name}_r{rep}"
                out = ANSWERS / f"layers_slice0_{tag}.json"
                verdicts = EVALS / f"layers_slice0_verdicts_{tag}.json"

                # "Complete" means the right NUMBER of rows, not merely that
                # a file exists. run_answer_eval.py writes incrementally after
                # every question, so a killed run leaves a PARTIAL answers
                # file behind. Checking only existence meant skipping
                # regeneration and then judging that partial as if it were a
                # whole arm -- a rate computed over the wrong denominator,
                # reported with no error anywhere. Same failure class as the
                # two index-as-identifier bugs: plausible wrong numbers,
                # nothing crashes.
                have = _row_count(out)
                complete = have == expected_n

                if complete and verdicts.exists():
                    print(f"[skip] {tag} ({have}/{expected_n} rows, judged)", flush=True)
                    skipped += 1
                    continue
                if have and not complete:
                    print(f"[resume] {tag} has {have}/{expected_n} rows -- regenerating "
                          f"the remainder before judging", flush=True)

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

                if not complete:
                    _run(gen, LOG_DIR / f"{tag}.gen.log", args.dry_run)
                    got = _row_count(out)
                    if not args.dry_run and got != expected_n:
                        raise SystemExit(
                            f"{tag}: generation produced {got}/{expected_n} rows -- "
                            f"refusing to judge an incomplete arm"
                        )

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
