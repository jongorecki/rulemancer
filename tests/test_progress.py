"""evals/progress.py: atomic JSON writes + the Heartbeat writer (docs/
plan-run-progress.md Sec 2/5). Covers what the runners actually depend on:
- a reader never sees invalid JSON, even under concurrent writes (Sec 5.5).
- Heartbeat.tick()/finish() produce the documented fields and terminal
  states, including the cost_so_far null-vs-numeric distinction (Sec 2).
"""

import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))

from progress import Heartbeat, atomic_write_json, read_json_retrying  # noqa: E402


def test_atomic_write_json_round_trips(tmp_path):
    path = tmp_path / "out.json"
    atomic_write_json(path, {"a": 1, "b": [1, 2, 3]})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1, "b": [1, 2, 3]}


def test_atomic_write_json_no_leftover_temp_file(tmp_path):
    path = tmp_path / "out.json"
    atomic_write_json(path, {"a": 1})
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_atomic_write_json_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "dir" / "out.json"
    atomic_write_json(path, {"a": 1})
    assert path.exists()


def test_atomicity_reader_never_sees_invalid_json(tmp_path):
    """Sec 5.5: hammer the writer while a reader polls in a loop; the
    reader must never catch a half-written / invalid JSON file. Writes
    payloads of varying size (small then large then small) specifically to
    make a torn, non-atomic write more likely to be observed if the
    temp-file + os.replace approach didn't actually work."""
    path = tmp_path / "heartbeat.json"
    atomic_write_json(path, {"n": 0, "pad": ""})  # seed it so the reader never starts on a missing file

    stop = threading.Event()
    reader_errors = []
    writer_errors = []
    reads = {"n": 0}

    def writer():
        try:
            for i in range(300):
                pad = "x" * ((i % 7) * 5000)  # varying payload size, 0..30000 chars
                atomic_write_json(path, {"n": i, "pad": pad})
        except Exception as e:  # noqa: BLE001 -- must surface to the main thread, not just log
            writer_errors.append(repr(e))
        finally:
            stop.set()

    def reader():
        while not stop.is_set():
            try:
                read_json_retrying(path)
                reads["n"] += 1
            except (json.JSONDecodeError, OSError) as e:
                reader_errors.append(str(e))

    t_writer = threading.Thread(target=writer)
    t_reader = threading.Thread(target=reader)
    t_reader.start()
    t_writer.start()
    t_writer.join(timeout=30)
    stop.set()
    t_reader.join(timeout=5)

    # Both directions matter: the reader must never see invalid JSON (the
    # documented guarantee), AND the writer itself must never fail outright
    # -- a prior version of _replace_with_retry's Windows race (see its
    # docstring) surfaced as an unhandled PermissionError in the writer
    # thread, which pytest only reported as a background warning unless a
    # test explicitly checks for it, exactly as this assertion does.
    assert writer_errors == [], f"writer thread raised: {writer_errors}"
    assert reader_errors == [], f"reader saw invalid JSON {len(reader_errors)} time(s): {reader_errors[:3]}"
    assert reads["n"] > 0  # sanity: the reader actually raced the writer at least once


def test_heartbeat_init_writes_running_with_zero_done(tmp_path):
    path = tmp_path / "hb.json"
    Heartbeat(run="r1", model="m", variant="v1", n_total=5, path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "running"
    assert data["n_done"] == 0
    assert data["n_total"] == 5
    assert data["run"] == "r1"
    assert data["model"] == "m"
    assert data["variant"] == "v1"
    assert data["last_qid"] is None
    assert data["errors"] == 0
    assert data["cost_so_far"] is None  # no tick yet
    assert "pid" in data and isinstance(data["pid"], int)
    assert "started_at" in data and "updated_at" in data


def test_heartbeat_tick_advances_counts_and_last_qid(tmp_path):
    path = tmp_path / "hb.json"
    hb = Heartbeat(run="r1", model="m", variant=None, n_total=3, path=path)
    hb.tick("q001")
    hb.tick("q002", errored=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["n_done"] == 2
    assert data["errors"] == 1
    assert data["last_qid"] == "q002"
    assert data["status"] == "running"


def test_heartbeat_cost_stays_null_when_never_passed(tmp_path):
    """The sonnet path (run_answer_eval.py) never has usage/cost -- cost_so_far
    must render null throughout, not a fabricated 0 (plan Sec 2)."""
    path = tmp_path / "hb.json"
    hb = Heartbeat(run="r1", model="claude-sonnet-5", variant=None, n_total=2, path=path)
    hb.tick("q001")
    hb.tick("q002")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["cost_so_far"] is None


def test_heartbeat_cost_accumulates_when_passed(tmp_path):
    path = tmp_path / "hb.json"
    hb = Heartbeat(run="r1", model="openai/gpt-5-mini", variant=None, n_total=3, path=path)
    hb.tick("q001", cost_delta=0.001)
    hb.tick("q002", cost_delta=0.0)  # a real zero-cost call still counts as "has cost"
    hb.tick("q003", cost_delta=0.002)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["cost_so_far"] == pytest.approx(0.003)


def test_heartbeat_finish_success_writes_done(tmp_path):
    path = tmp_path / "hb.json"
    hb = Heartbeat(run="r1", model="m", variant=None, n_total=1, path=path)
    hb.tick("q001")
    hb.finish(True)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "done"


def test_heartbeat_finally_pattern_records_failed_on_crash(tmp_path):
    """The exact usage pattern the runners use: success stays False unless
    the whole try block completes, so an exception mid-loop still ends with
    status=failed rather than a stuck 'running'."""
    path = tmp_path / "hb.json"
    hb = Heartbeat(run="r1", model="m", variant=None, n_total=3, path=path)
    success = False
    with pytest.raises(RuntimeError):
        try:
            hb.tick("q001")
            raise RuntimeError("boom")
            success = True  # noqa: F841 -- never reached, that's the point
        finally:
            hb.finish(success)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["n_done"] == 1  # the tick before the crash is preserved
