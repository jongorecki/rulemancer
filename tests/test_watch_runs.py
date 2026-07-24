"""evals/watch_runs.py: the percentage column, the grand-total line, and
STALLED/DEAD classification (docs/plan-run-progress.md Sec 3, plus Jon's
follow-up ask for an explicit percentage and a combined total across a
multi-cell grid).
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))

import watch_runs as wr  # noqa: E402


def _hb(run="r1", n_done=3, n_total=8, status="running", pid=None,
       started_at=None, updated_at=None):
    now = time.time()
    return {
        "run": run, "model": "m", "variant": None,
        "n_total": n_total, "n_done": n_done, "last_qid": "q003", "errors": 0,
        "started_at": started_at or _iso(now - 60),
        "updated_at": updated_at or _iso(now),
        "status": status, "cost_so_far": None, "pid": pid,
    }


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def test_pct_basic_cases():
    assert wr._pct(0, 8) == 0
    assert wr._pct(4, 8) == 50
    assert wr._pct(8, 8) == 100
    assert wr._pct(3, 8) == 38  # round(37.5) -> 38 (banker's rounding lands here for this value)


def test_pct_zero_total_does_not_crash():
    assert wr._pct(0, 0) == 0


def test_render_line_includes_percent_column():
    hb = _hb(n_done=4, n_total=8, pid=os.getpid())
    line = wr.render_line(hb, time.time(), stale_after=300)
    assert "50%" in line
    assert "4/8" in line


def test_effective_status_running_stays_running_when_pid_alive_and_fresh():
    hb = _hb(status="running", pid=os.getpid(),
             updated_at=_iso(time.time()))
    assert wr._effective_status(hb, time.time(), stale_after=300) == "running"


def test_effective_status_stalled_when_heartbeat_old():
    now = time.time()
    hb = _hb(status="running", pid=os.getpid(), updated_at=_iso(now - 400))
    assert wr._effective_status(hb, now, stale_after=300) == "stalled"


def test_effective_status_dead_when_pid_gone_but_fresh():
    now = time.time()
    hb = _hb(status="running", pid=999999999, updated_at=_iso(now - 1))
    assert wr._effective_status(hb, now, stale_after=300) == "dead"


def test_effective_status_stalled_takes_priority_over_dead():
    """A run that's both stale AND has a dead pid reports stalled -- the
    plan calls STALLED the load-bearing signal, and it's cheaper to check
    (no process lookup), so it should win when both apply."""
    now = time.time()
    hb = _hb(status="running", pid=999999999, updated_at=_iso(now - 400))
    assert wr._effective_status(hb, now, stale_after=300) == "stalled"


def test_effective_status_passes_through_terminal_states():
    now = time.time()
    assert wr._effective_status(_hb(status="done"), now, 300) == "done"
    assert wr._effective_status(_hb(status="failed"), now, 300) == "failed"


def test_render_total_aggregates_done_and_n_total():
    now = time.time()
    heartbeats = [
        _hb(run="a", n_done=8, n_total=8, status="done"),
        _hb(run="b", n_done=2, n_total=8, status="running", pid=999999999,
            updated_at=_iso(now - 1)),  # dead
    ]
    line = wr.render_total(heartbeats, now, stale_after=300)
    assert "10/16" in line
    assert "62%" in line  # round(100*10/16) == 62.5 -> 62 (round-half-to-even)
    assert "2 runs" in line
    assert "1 done" in line
    assert "1 dead" in line


def test_render_includes_total_line_and_separator(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(_hb(run="a", n_done=8, n_total=8, status="done")))
    (tmp_path / "b.json").write_text(json.dumps(_hb(run="b", n_done=1, n_total=8, status="running",
                                                     pid=999999999, updated_at=_iso(time.time() - 1))))
    out = wr.render(tmp_path, stale_after=300)
    lines = out.splitlines()
    assert lines[-1].startswith("TOTAL")
    assert set(lines[-2]) == {"-"}  # separator line
    assert "9/16" in lines[-1]


def test_render_empty_dir_has_no_total_line(tmp_path):
    out = wr.render(tmp_path, stale_after=300)
    assert "TOTAL" not in out
    assert "no runs" in out
