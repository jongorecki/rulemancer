"""Shared pytest fixtures.

Hermetic heartbeat directory (docs/plan-run-progress.md, evals/progress.py):
several tests exercise run_answer_eval.main()/run_openrouter_arm.main() end
to end with mocked backends (tests/test_resume_prompts_cache_guard.py,
tests/test_qidfilter.py). Both runners create a Heartbeat internally with no
explicit `path=` kwarg -- `Heartbeat.__init__` then falls back to
`PROGRESS_DIR / f"{run}.json"` (evals/progress.py), where `PROGRESS_DIR` is
looked up from the `progress` module's own globals *at call time*, not
bound at import time by whoever imported `Heartbeat`. That means redirecting
the module attribute here transparently covers every heartbeat write in the
whole suite -- direct `Heartbeat(...)` calls in unit tests AND the two
runners' internal calls -- with zero changes to either runner and no change
to the documented default runtime path (evals/watch_runs.py and both
runners still resolve the real `evals/answers/_progress/` when actually
run, e.g. `uv run python evals/run_answer_eval.py ...` from a shell; only
an imported module's attribute is patched, and only for the lifetime of a
single test).

Before this fixture existed, tests/test_resume_prompts_cache_guard.py's
four tests that call `roa.main()`/`rae.main()` directly (none of them
monkeypatched `progress.PROGRESS_DIR` themselves) wrote real heartbeat
files into evals/answers/_progress/ -- the exact directory
evals/watch_runs.py reads as live operator-run state. A phantom row there
inflates the watcher's grand-total denominator or hides a genuinely
stalled real run in the noise.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "evals"))

import progress  # noqa: E402

REAL_PROGRESS_DIR = Path(__file__).parent.parent / "evals" / "answers" / "_progress"


@pytest.fixture(autouse=True)
def _hermetic_progress_dir(tmp_path, monkeypatch):
    """Redirect every heartbeat write in this test to a private tmp
    directory. Autouse + function-scoped: applies to every test without
    each test file having to remember it, and `monkeypatch` reverts the
    attribute after the test regardless of pass/fail/exception."""
    monkeypatch.setattr(progress, "PROGRESS_DIR", tmp_path / "_progress")


@pytest.fixture(scope="session", autouse=True)
def _real_progress_dir_untouched_guard():
    """Regression test for the pollution bug: snapshot every file under the
    REAL evals/answers/_progress/ directory before the session and assert
    it is byte-for-byte identical (same files, same mtime, same size) after
    the whole suite runs. Compares mtime+size rather than just "no new
    files" so a test that overwrites an existing real heartbeat *in place*
    -- same filename, same size, different content -- would still be
    missed by mtime alone; size is checked too as a cheap second signal,
    and this pairs with `_hermetic_progress_dir` above, which is what
    actually prevents the write from happening in the first place. If this
    ever fails, some test wrote into the real directory without going
    through `_hermetic_progress_dir` -- e.g. by calling
    `monkeypatch.undo()` early, or constructing a `Heartbeat` with an
    explicit `path=` pointed at the real directory."""
    def _snapshot() -> dict[str, tuple[int, int]]:
        if not REAL_PROGRESS_DIR.exists():
            return {}
        return {
            str(p.relative_to(REAL_PROGRESS_DIR)): (p.stat().st_mtime_ns, p.stat().st_size)
            for p in REAL_PROGRESS_DIR.rglob("*")
            if p.is_file()
        }

    before = _snapshot()
    yield
    after = _snapshot()
    assert after == before, (
        "A test wrote into the REAL evals/answers/_progress/ directory -- "
        "the directory evals/watch_runs.py reads as live operator-run "
        f"state. Before: {sorted(before)}. After: {sorted(after)}. Every "
        "test that constructs a Heartbeat (directly, or indirectly via "
        "run_answer_eval.main()/run_openrouter_arm.main()) must go through "
        "the module-global `progress.PROGRESS_DIR` (this file's "
        "`_hermetic_progress_dir` autouse fixture already redirects it for "
        "every test) or pass an explicit tmp `path=` -- never rely on the "
        "real default in a test."
    )
