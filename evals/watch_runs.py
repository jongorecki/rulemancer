"""One-line-per-run status for the eval runners (docs/plan-run-progress.md
Sec 3). Reads every heartbeat file `evals/progress.py`'s `Heartbeat` writes
to evals/answers/_progress/*.json and renders it.

Stdlib only -- no tqdm, no rich; neither is in pyproject.toml and adding a
dependency for this is not worth the decision (plan Sec 7 non-goals).

STALLED is the load-bearing feature, not the progress bars: a run that was
never launched and a run that died silently both look, to a bar that was
never drawn, exactly like nothing is happening. A heartbeat file that
stopped advancing is visible immediately. DEAD goes one step further and
checks whether the recorded pid is still alive at all.

Run: `.venv/Scripts/python.exe evals/watch_runs.py [--dir PATH]
     [--stale-after SECONDS] [--watch] [--interval SECONDS]`
"""

import argparse
import calendar
import ctypes
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # so `from progress import ...` resolves
# regardless of the caller's cwd or import path (e.g. `from evals import watch_runs`
# in a test) -- same reasoning as run_answer_eval.py's identical line.

from progress import PROGRESS_DIR, read_json_retrying  # noqa: E402

BAR_WIDTH = 16
DEFAULT_STALE_AFTER = 300  # 5 min, matches the plan's default


def _pid_alive(pid: int | None) -> bool:
    """True if `pid` names a live process. Stdlib-only on both POSIX and
    Windows -- no psutil. Windows has no signal-0 convention for os.kill,
    so that branch goes through ctypes/OpenProcess instead."""
    if not pid:
        return False
    if os.name == "nt":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal
    except OSError:
        return False
    return True


def _parse_iso(s: str | None) -> float | None:
    """started_at/updated_at are "%Y-%m-%dT%H:%M:%SZ" (UTC, no fractional
    seconds -- see progress._now_iso()). Returns a POSIX timestamp, or None
    for a missing/unparseable value rather than raising -- a malformed
    heartbeat should render as a degraded row, not crash the watcher."""
    if not s:
        return None
    try:
        return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
    except ValueError:
        return None


def _fmt_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


def _bar(n_done: int, n_total: int, width: int = BAR_WIDTH) -> str:
    if n_total <= 0:
        filled = 0
    else:
        filled = round(width * min(n_done, n_total) / n_total)
        filled = max(0, min(width, filled))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def _fmt_cost(cost: float | None) -> str:
    return f"${cost:.4f}" if cost is not None else "$--"


def load_heartbeats(progress_dir: Path) -> list[dict]:
    """One dict per heartbeat file, sorted by `run` name for a stable
    render order. A file that fails to parse (caught mid os.replace on some
    exotic filesystem, or hand-edited) is skipped rather than crashing the
    whole watcher -- the atomic writer in progress.py is what actually
    prevents this in practice."""
    out = []
    if not progress_dir.exists():
        return out
    for path in sorted(progress_dir.glob("*.json")):
        try:
            data = read_json_retrying(path)
        except (json.JSONDecodeError, OSError):
            continue
        out.append(data)
    out.sort(key=lambda d: d.get("run", ""))
    return out


def render_line(hb: dict, now: float, stale_after: float) -> str:
    run = str(hb.get("run", "?"))
    n_done = hb.get("n_done", 0)
    n_total = hb.get("n_total", 0)
    status = hb.get("status", "?")
    pid = hb.get("pid")
    updated_at = _parse_iso(hb.get("updated_at"))
    started_at = _parse_iso(hb.get("started_at"))

    name_col = run.ljust(18)
    bar_col = _bar(n_done, n_total)
    frac_col = f"{n_done}/{n_total}".rjust(6)

    if status == "running" and updated_at is not None and (now - updated_at) > stale_after:
        age = _fmt_elapsed(now - updated_at)
        return f"{name_col} {bar_col} {frac_col}   STALLED (no heartbeat {age})"

    if status == "running" and not _pid_alive(pid):
        age = _fmt_elapsed(now - updated_at) if updated_at is not None else "?"
        return f"{name_col} {bar_col} {frac_col}   DEAD (pid {pid} gone, last heartbeat {age} ago)"

    last_qid = hb.get("last_qid") or "--"
    qid_col = ("done" if status == "done" else
              "failed" if status == "failed" else
              str(last_qid)).ljust(8)
    elapsed = _fmt_elapsed((updated_at or now) - started_at) if started_at is not None else "?"
    cost_col = _fmt_cost(hb.get("cost_so_far"))
    return f"{name_col} {bar_col} {frac_col}   {qid_col} {elapsed.rjust(7)}   {cost_col}"


def render(progress_dir: Path, stale_after: float) -> str:
    heartbeats = load_heartbeats(progress_dir)
    if not heartbeats:
        return f"(no runs -- nothing in {progress_dir})"
    now = time.time()
    return "\n".join(render_line(hb, now, stale_after) for hb in heartbeats)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dir", type=Path, default=PROGRESS_DIR,
                    help=f"heartbeat directory (default: {PROGRESS_DIR})")
    p.add_argument("--stale-after", type=float, default=DEFAULT_STALE_AFTER,
                    help=f"seconds since the last heartbeat before a running run is "
                    f"reported STALLED (default: {DEFAULT_STALE_AFTER})")
    p.add_argument("--watch", action="store_true",
                    help="keep refreshing on --interval instead of printing once and exiting")
    p.add_argument("--interval", type=float, default=5.0,
                    help="refresh interval in seconds for --watch (default: 5.0)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not args.watch:
        print(render(args.dir, args.stale_after))
        return
    try:
        while True:
            print(render(args.dir, args.stale_after))
            print(f"\n(refreshing every {args.interval:.0f}s -- Ctrl+C to stop)")
            time.sleep(args.interval)
            print()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
