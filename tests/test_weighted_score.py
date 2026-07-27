"""evals/weighted_score.py: level-weighted re-scoring of judged arms.

The four tests docs/spec-weighted-scoring.md asks for, plus shape coverage:

- a flat weight vector reproduces the accuracy the judge already computed
  (guards the arithmetic against every real verdict file in the repo, not a
  hand-built fixture);
- scaling every weight by a constant leaves the score unchanged -- this is the
  fact that already fooled one sensitivity run, where (1,2,3,4|1) and
  (0.5,1,1.5,2|0.5) produced byte-identical scores because the second is the
  first halved;
- a level present in the verdicts but absent from the weight vector is an
  error, never a silent 1.0;
- round-trip: the weight vector written into the output re-scores to the number
  written beside it, so a reader can reproduce it from the artifact alone.

Plus both `by_level_counts` shapes this repo writes -- `{same, different}` from
the auto judge and `{correct, n}` (fractional `correct` allowed, partial credit)
from the human merge -- and the refusal to guess at an unrecognised third.
"""
import json
from pathlib import Path

import pytest

import weighted_score as ws

REPO = Path(__file__).resolve().parents[1]

# Every real verdict file that carries by_level_counts. Collected at import so a
# newly added arm is covered automatically rather than needing a test edit.
SCORABLE = sorted(
    p for p in (REPO / "evals").glob("*verdicts*.json")
    if (lambda d: isinstance(d, dict) and (d.get("summary") or {}).get("by_level_counts"))(
        json.loads(p.read_text(encoding="utf-8"))
    )
)

FLAT = ws.WEIGHT_SCHEMES["flat"]["weights"]


def test_repo_has_scorable_verdict_files():
    """Guards the parametrisation itself: an empty glob would pass silently."""
    assert len(SCORABLE) >= 5, [p.name for p in SCORABLE]


@pytest.mark.parametrize("path", SCORABLE, ids=lambda p: p.name)
def test_flat_reproduces_reported_accuracy(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    counts = ws.normalize_counts(data["summary"]["by_level_counts"])
    assert ws.score(counts, FLAT) == pytest.approx(data["summary"]["accuracy"], abs=1e-9)


@pytest.mark.parametrize("path", SCORABLE, ids=lambda p: p.name)
def test_level_counts_sum_to_n_total(path):
    """A denominator that disagrees with n_total means a level went missing."""
    data = json.loads(path.read_text(encoding="utf-8"))
    counts = ws.normalize_counts(data["summary"]["by_level_counts"])
    assert sum(n for _, n in counts.values()) == data["summary"]["n_total"]


@pytest.mark.parametrize("scheme", sorted(ws.WEIGHT_SCHEMES))
@pytest.mark.parametrize("factor", [0.5, 2.0, 7.3])
def test_only_ratios_matter(scheme, factor):
    counts = {"0": (30.0, 30.0), "1": (28.0, 30.0),
              "2": (24.0, 30.0), "3": (20.0, 30.0), "Corner Case": (15.0, 30.0)}
    weights = ws.WEIGHT_SCHEMES[scheme]["weights"]
    scaled = {k: v * factor for k, v in weights.items()}
    assert ws.score(counts, scaled) == pytest.approx(ws.score(counts, weights), abs=1e-12)


def test_unweighted_level_is_an_error_not_a_default():
    counts = {"0": (1.0, 1.0), "Nonexistent Level": (0.0, 1.0)}
    with pytest.raises(ws.ScoreError, match="absent from the weight vector"):
        ws.score(counts, FLAT)
    # and specifically NOT the score it would get by defaulting the level to 1.0
    assert ws.score({"0": (1.0, 1.0)}, FLAT) == 1.0


def test_roundtrip_emitted_weights_reproduce_emitted_number(tmp_path):
    path = REPO / "evals" / "verdicts_derivability_B_human.json"
    result = ws.score_file(path, "corner-half")
    counts = ws.normalize_counts(
        json.loads(path.read_text(encoding="utf-8"))["summary"]["by_level_counts"])
    assert ws.score(counts, result["weights"]) == pytest.approx(result["weighted"], abs=1e-12)
    assert result["weights"] == ws.WEIGHT_SCHEMES["corner-half"]["weights"]


def test_both_by_level_counts_shapes_normalize():
    auto = {"2": {"same": 28, "different": 2}}
    human = {"2": {"correct": 28, "n": 30}}
    assert ws.normalize_counts(auto) == ws.normalize_counts(human) == {"2": (28.0, 30.0)}


def test_fractional_correct_survives_partial_credit():
    """bucketA's human merge stores correct as a float; integer counting loses it."""
    counts = ws.normalize_counts({"3": {"correct": 11.5, "n": 15}})
    assert counts == {"3": (11.5, 15.0)}
    assert ws.score(counts, FLAT) == pytest.approx(11.5 / 15)


def test_unrecognised_shape_refuses_to_guess():
    with pytest.raises(ws.ScoreError, match="unrecognised by_level_counts shape"):
        ws.normalize_counts({"2": {"right": 28, "total": 30}})


def test_corner_half_is_the_ruled_scheme():
    """Jon's ruling 2026-07-26: flat L0-L3, Corner Case 0.5. "rules" (the
    86-row card-free instrument, added 2026-07-27) is not a corner case, so
    it stays full weight like L0-L3."""
    assert ws.DEFAULT_SCHEME == "corner-half"
    assert ws.WEIGHT_SCHEMES["corner-half"]["weights"] == {
        "0": 1.0, "1": 1.0, "2": 1.0, "3": 1.0, "Corner Case": 0.5, "rules": 1.0}


def test_corner_half_raises_a_corner_heavy_arm():
    """Direction check: discounting the worst-performing slice must not lower it."""
    counts = {"3": (20.0, 30.0), "Corner Case": (15.0, 30.0)}
    flat = ws.score(counts, FLAT)
    weighted = ws.score(counts, ws.WEIGHT_SCHEMES["corner-half"]["weights"])
    assert weighted > flat


def test_file_without_by_level_counts_is_an_error(tmp_path):
    p = tmp_path / "verdicts_empty.json"
    p.write_text(json.dumps({"entries": [], "summary": {"accuracy": 1.0}}), encoding="utf-8")
    with pytest.raises(ws.ScoreError, match="no summary.by_level_counts"):
        ws.score_file(p, "flat")
