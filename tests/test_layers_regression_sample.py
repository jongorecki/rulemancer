"""The frozen non-layers regression sample must stay frozen.

This is an identity fixture, and its brittleness is the point (see the handoff's
"one defect, two costumes" lesson: what caught the ruling-cache bug was exactly
this class of test). Slice 0's BASE and CONTROL arms and Slice 5's tool-on and
tool-off arms are all measured on these 100 rows. If the file silently changes
between arms, the comparison is invalid and NOTHING crashes to tell you.

If a test here goes red, do NOT rebuild the sample to make it pass until you
have proved what changed and why.
"""

import json
import subprocess
import sys
from pathlib import Path

EVALS = Path(__file__).resolve().parent.parent / "evals"
SAMPLE = EVALS / "_layers_regression_sample.jsonl"
UNION = EVALS / "_layers_union_slice.jsonl"
BUILDER = EVALS / "build_layers_regression_sample.py"


def _ids(path: Path) -> list[str]:
    return [
        json.loads(line)["id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_sample_has_100_unique_rows():
    ids = _ids(SAMPLE)
    assert len(ids) == 100
    assert len(set(ids)) == 100


def test_no_overlap_with_layers_union_slice():
    """A regression row must never double as a win-rate row."""
    assert not set(_ids(SAMPLE)) & set(_ids(UNION))


def test_every_row_is_judgeable():
    """judge_rulesguru.py silently skips rows without answer_gold, which would
    shrink the effective sample without any error."""
    rows = [
        json.loads(line)
        for line in SAMPLE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all(r.get("answer_gold") for r in rows)


def test_builder_is_deterministic():
    """Re-running the builder must reproduce the committed file byte for byte."""
    before = SAMPLE.read_bytes()
    result = subprocess.run(
        [sys.executable, str(BUILDER)],
        capture_output=True,
        text=True,
        cwd=str(BUILDER.parent.parent),
    )
    assert result.returncode == 0, result.stderr
    assert SAMPLE.read_bytes() == before, (
        "builder output drifted -- the sample is not reproducible from its seed"
    )
