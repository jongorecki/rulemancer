"""Regression coverage for the _progress/ test-pollution bug (see tests/
conftest.py's `_hermetic_progress_dir` and `_real_progress_dir_untouched_
guard` fixtures for the actual fix + suite-wide detection net).

This file proves the mechanism directly: Heartbeat's DEFAULT path (no
explicit `path=` kwarg -- exactly what both eval runners' internal
`Heartbeat(run=..., model=..., variant=..., n_total=...)` calls use, see
evals/run_answer_eval.py and evals/run_openrouter_arm.py) honors a
redirected `progress.PROGRESS_DIR`, and that nothing lands in the real
directory even though this test exercises the exact default-path code path
that used to leak into it.

Checked against a directory that is explicitly NOT the real one, so a
failure here can never itself pollute evals/answers/_progress/ -- unlike a
test that only asserts against the real path and could write there first.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))

import progress  # noqa: E402
from progress import Heartbeat  # noqa: E402

REAL_PROGRESS_DIR = Path(__file__).parent.parent / "evals" / "answers" / "_progress"


def test_heartbeat_default_path_honors_progress_dir_redirect(tmp_path, monkeypatch):
    """The exact seam both runners depend on: Heartbeat.__init__ resolves
    `PROGRESS_DIR` by module-global name lookup at call time (evals/
    progress.py), not at import time -- so redirecting `progress.
    PROGRESS_DIR` (what tests/conftest.py's autouse fixture does for every
    test in the suite) transparently covers it with zero changes to either
    runner's source."""
    fake_dir = tmp_path / "not_the_real_progress_dir"
    # This test's own tmp_path is independent of the autouse
    # _hermetic_progress_dir fixture's tmp_path -- re-patch explicitly so
    # this test is self-contained and legible on its own.
    monkeypatch.setattr(progress, "PROGRESS_DIR", fake_dir)

    hb = Heartbeat(run="regress", model="fake/model", variant=None, n_total=3)
    hb.tick("q001")
    hb.finish(True)

    written = fake_dir / "regress.json"
    assert written.exists()
    data = json.loads(written.read_text(encoding="utf-8"))
    assert data["run"] == "regress"
    assert data["status"] == "done"
    assert data["n_done"] == 1

    # The actual point of the fix: nothing landed in the real directory,
    # even though this Heartbeat was constructed with no explicit `path=`
    # -- the same call shape run_answer_eval.py / run_openrouter_arm.py use.
    assert not (REAL_PROGRESS_DIR / "regress.json").exists()
