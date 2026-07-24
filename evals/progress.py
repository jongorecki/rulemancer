"""Run-progress heartbeats + atomic JSON writes (docs/plan-run-progress.md).

Shared by both long-running eval runners (run_openrouter_arm.py,
run_answer_eval.py) so a detached/backgrounded run's progress is a
falsifiable filesystem fact -- evals/watch_runs.py reads it -- rather than
something someone has to remember to go check stdout for.

Two independent pieces:

- `atomic_write_json()` -- temp file in the SAME directory + os.replace, so
  a reader (the watcher, or a resuming run) never catches a half-write.
  Used both for the heartbeat file itself and, by the runners, for the
  actual output file (incremental row writes, plan Sec 4).
- `Heartbeat` -- one heartbeat JSON per run at
  evals/answers/_progress/{run}.json, updated after every question. Status
  is written in a `finally` at the call site (see `Heartbeat.finish()`) so a
  crash still records "failed" instead of leaving "running" forever.
"""

import json
import os
import tempfile
import time
from pathlib import Path

PROGRESS_DIR = Path(__file__).parent / "answers" / "_progress"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_write_json(path: Path, payload: dict, indent: int = 2,
                      ensure_ascii: bool = False) -> None:
    """Write `payload` to `path` atomically: build the full bytes in a temp
    file next to `path` (same directory -> same filesystem/volume, so
    os.replace is atomic on both POSIX and Windows), then os.replace() it
    into place. A concurrent reader either sees the old complete file or the
    new complete file -- never a partial write, regardless of how large the
    payload is or when the reader happens to poll."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=indent, ensure_ascii=ensure_ascii)
        _replace_with_retry(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def read_json_retrying(path: Path, attempts: int = 20, delay: float = 0.02) -> dict:
    """Read + parse JSON from `path`, tolerating the same transient Windows
    race _replace_with_retry works around, just from the read side: a
    reader's open() (what `path.read_text()` does under the hood) can land
    in the same brief window a concurrent os.replace() is using and get
    ERROR_SHARING_VIOLATION / PermissionError, even though the file on disk
    is never actually corrupted -- found by this module's own atomicity
    stress test (tests/test_progress.py) once the write side was already
    fixed and started completing hundreds of replaces a second, giving the
    read side far more chances to land in that window.

    A json.JSONDecodeError is NOT retried and NOT caught here -- that would
    mean atomic_write_json's actual guarantee (a reader only ever sees a
    complete old file or a complete new one, never a half-write) had been
    violated, which is a real bug the caller needs to see, not a transient
    race to paper over."""
    last_exc = None
    for _ in range(attempts):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError as e:
            last_exc = e
            time.sleep(delay)
    raise last_exc


def _replace_with_retry(src: str, dst: Path, attempts: int = 20, delay: float = 0.02) -> None:
    """os.replace() with a short retry budget for a Windows-only transient
    race, found by this module's own atomicity stress test
    (tests/test_progress.py): MoveFileEx (what os.replace() calls under the
    hood on Windows) can fail with ERROR_ACCESS_DENIED / PermissionError for
    a few milliseconds when another process has `dst` open for reading at
    the exact instant of the rename -- exactly the shape of a watcher
    polling the heartbeat file while the writer replaces it hundreds of
    times a second. POSIX rename() has no equivalent race (open POSIX file
    handles don't block a rename), so this loop only ever actually retries
    on Windows; elsewhere the first os.replace() succeeds and the loop
    costs nothing beyond the one call."""
    last_exc = None
    for _ in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError as e:
            last_exc = e
            time.sleep(delay)
    raise last_exc


class Heartbeat:
    """One heartbeat file for one run.

    Usage::

        hb = Heartbeat(run=out_path.stem, model=args.model,
                       variant=args.condition, n_total=len(questions))
        ok = False
        try:
            for q in questions:
                ...
                hb.tick(q.id, errored=bool(row.get("error")), cost_delta=...)
            ok = True
        finally:
            hb.finish(ok)

    `cost_delta` is OpenRouter-only (plan Sec 2): pass a number (even 0.0)
    on every tick for a run that has real per-call usage, and never pass it
    at all for a run that doesn't (run_answer_eval.py's sonnet path has no
    `usage` field). `cost_so_far` in the written JSON is null until the
    first non-None cost_delta arrives, and stays null forever if one never
    does -- showing a real absence rather than inventing a number.
    """

    def __init__(self, run: str, model: str | None, variant: str | None,
                n_total: int, path: Path | None = None):
        self.run = run
        self.model = model
        self.variant = variant
        self.n_total = n_total
        self.n_done = 0
        self.errors = 0
        self.cost_so_far: float | None = None
        self._has_cost = False
        self.last_qid: str | None = None
        self.started_at = _now_iso()
        self.path = path or (PROGRESS_DIR / f"{run}.json")
        self.pid = os.getpid()
        self._write("running")

    def tick(self, last_qid: str, errored: bool = False,
            cost_delta: float | None = None) -> None:
        self.n_done += 1
        self.last_qid = last_qid
        if errored:
            self.errors += 1
        if cost_delta is not None:
            self.cost_so_far = (self.cost_so_far or 0.0) + cost_delta
            self._has_cost = True
        self._write("running")

    def finish(self, success: bool) -> None:
        """Terminal write. Call from a `finally` block wrapping the whole
        run so a crash (success=False, because the try block's success flag
        never got set) still records "failed" rather than leaving "running"
        as the last thing anyone ever wrote."""
        self._write("done" if success else "failed")

    def _write(self, status: str) -> None:
        payload = {
            "run": self.run,
            "model": self.model,
            "variant": self.variant,
            "n_total": self.n_total,
            "n_done": self.n_done,
            "last_qid": self.last_qid,
            "errors": self.errors,
            "started_at": self.started_at,
            "updated_at": _now_iso(),
            "status": status,
            "cost_so_far": self.cost_so_far if self._has_cost else None,
            "pid": self.pid,
        }
        atomic_write_json(self.path, payload)
