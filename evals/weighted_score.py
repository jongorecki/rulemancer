"""Re-score judged arms under a level weight vector. Zero API.

Jon ruled 2026-07-26: **flat across L0-L3, Corner Case 0.5** (`corner-half`
below). Spec and the argument for it: `docs/spec-weighted-scoring.md`.

WHAT THIS IS. Every verdict file already carries `by_level_counts`, so a weighted
accuracy is arithmetic over JSON we have already paid for -- a re-scoring pass,
never a re-run. That means every historical arm can be re-scored, so weighted and
flat numbers stay comparable across the whole history.

WHY CORNER CASE IS DISCOUNTED ON ITS OWN AXIS. Corner Case is the hardest slice
we own but the one Jon values least, because it is unrealistic ("never would
happen in game"), not because it is easy. A pure difficulty ramp therefore gets
his stated preference backwards at the top end. The corner discount is separate
from any difficulty emphasis, and `corner-half` applies the discount and nothing
else.

TWO THINGS THAT HAVE ALREADY CAUSED ERRORS HERE, both guarded below:

1. **Only ratios matter.** A weighted score normalizes by the weighted
   denominator, so scaling every weight by a constant changes nothing. During
   sensitivity testing `(1,2,3,4 | corner 1)` and `(0.5,1,1.5,2 | corner 0.5)`
   produced byte-identical scores, because the second is the first halved. Two
   schemes differing by a scale factor are the SAME scheme.
2. **`by_level_counts` has two shapes in this repo.** Auto-judged files store
   `{same, different}`; human-merged files store `{correct, n}` with `correct`
   as a FLOAT, because partial credit is possible. Both are normalized here.
   Guessing wrong silently halves or doubles a denominator, so an unrecognised
   shape is an error rather than a best-effort read.

A level present in the verdicts but missing from the weight vector is likewise an
error, not a silent 1.0 -- a typo'd level name must fail loudly rather than
quietly reweighting the result.

**Flat is always printed first.** Every prior result in this repo is stated flat,
and a weighted accuracy without its weights beside it is exactly the kind of
number-with-an-unchecked-claim this repo keeps getting caught by. Any JSON this
writes carries the scheme name AND the full weight vector, so a reader can
reproduce the number from the artifact alone.

Usage:
    python evals/weighted_score.py evals/verdicts_derivability_B_human.json
    python evals/weighted_score.py evals/verdicts_*.json --scheme corner-half
    python evals/weighted_score.py evals/verdicts_h2h_*.json --all-schemes
    python evals/weighted_score.py evals/verdicts_*.json --json evals/_weighted.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# One dict, one entry per scheme -- adding a scheme is a dict entry, not a code
# change. Weights are RATIOS; see caveat 1 above.
#
# "rules" LEVEL. The 86-row card-free instrument (rules86_real / rules86_placebo)
# tags every row `level: "rules"` -- not one of the corpus's L0-L3/Corner Case
# labels, because it isn't a difficulty rung on the same ladder. It's a separate
# instrument: 0 of the 1,409 corpus rows carry `level: "rules"`
# (evals/rulesguru_full_v2.jsonl has only 0/1/2/3/Corner Case), so the card-free
# set is not a stratum of the corpus and reweighting it into a corpus-mix
# projection would be fabricating a share for a level the corpus doesn't have.
# Concretely this is moot for `corpus_level_mix()`'s projection step (it only
# includes levels present in the corpus mix, so "rules" is dropped there with
# zero share automatically, never distorting the projected number) -- but
# `weighted_score.py::score()` still has to score THESE FILES on their own
# terms (accuracy on the 86-row set, flat and "weighted"), and every level
# present in a verdict file must appear in the weight vector or it raises
# (by design -- see ScoreError below). Since every row in a rules86 file is
# level "rules" and no other level shares the file, the *value* chosen here is
# mathematically inert for that file (num and den both scale by the same
# weight, so the ratio is unchanged -- see caveat 1 above): 1.0 is chosen not
# because the number matters, but because "rules" is an ordinary full-weight
# level like L0-L3, not a discounted one like Corner Case, and a reader
# scanning the vector should read it that way.
WEIGHT_SCHEMES = {
    "flat": {
        "label": "Flat",
        "weights": {"0": 1.0, "1": 1.0, "2": 1.0, "3": 1.0, "Corner Case": 1.0, "rules": 1.0},
        "rationale": "Every level equal. How every prior result in this repo is stated.",
    },
    "corner-half": {
        "label": "Flat L0-L3, Corner Case 0.5",
        "weights": {"0": 1.0, "1": 1.0, "2": 1.0, "3": 1.0, "Corner Case": 0.5, "rules": 1.0},
        "rationale": (
            "Jon's ruling, 2026-07-26. Implements what he said and nothing more: "
            "corner cases are unrealistic, so they count half. Asserts no "
            "difficulty ordering among L0-L3. 'rules' (the 86-row card-free "
            "instrument) is not a corner case, so it stays full weight."
        ),
    },
    "difficulty-ramp": {
        "label": "1,2,3,4 | Corner 1",
        "weights": {"0": 1.0, "1": 2.0, "2": 3.0, "3": 4.0, "Corner Case": 1.0, "rules": 1.0},
        "rationale": (
            "Scheme A from the spec, kept for sensitivity only. NOT ruled. "
            "Asserts L3 is four times as valuable as L0, which Jon never claimed."
        ),
    },
    "shallow-ramp": {
        "label": "1,1,1.25,1.5 | Corner 0.5",
        "weights": {"0": 1.0, "1": 1.0, "2": 1.25, "3": 1.5, "Corner Case": 0.5, "rules": 1.0},
        "rationale": (
            "The honest form of difficulty emphasis if it is ever wanted: a "
            "shallow ramp with the corner discount kept separate. NOT ruled."
        ),
    },
}

DEFAULT_SCHEME = "corner-half"


class ScoreError(ValueError):
    """Raised when a verdict file cannot be scored without guessing."""


def normalize_counts(by_level_counts: dict) -> dict[str, tuple[float, float]]:
    """level -> (correct, n), from either shape this repo writes.

    `{same, different}` is the auto judge's shape; `{correct, n}` is the
    human-merged shape and may carry fractional `correct` (partial credit).
    """
    out: dict[str, tuple[float, float]] = {}
    for lvl, c in by_level_counts.items():
        keys = set(c)
        if keys >= {"same", "different"}:
            correct, n = float(c["same"]), float(c["same"]) + float(c["different"])
        elif keys >= {"correct", "n"}:
            correct, n = float(c["correct"]), float(c["n"])
        else:
            raise ScoreError(
                f"unrecognised by_level_counts shape at level {lvl!r}: "
                f"keys {sorted(keys)}; expected {{same,different}} or {{correct,n}}"
            )
        out[str(lvl)] = (correct, n)
    return out


def score(counts: dict[str, tuple[float, float]], weights: dict[str, float]) -> float:
    """Weighted accuracy. A level absent from `weights` is an error, not a 1.0."""
    unweighted = sorted(set(counts) - set(weights))
    if unweighted:
        raise ScoreError(
            f"levels present in the verdicts but absent from the weight vector: "
            f"{unweighted}. Add them explicitly rather than defaulting to 1.0."
        )
    num = sum(weights[lvl] * correct for lvl, (correct, _) in counts.items())
    den = sum(weights[lvl] * n for lvl, (_, n) in counts.items())
    if den == 0:
        raise ScoreError("weighted denominator is zero")
    return num / den


def score_file(path: Path, scheme: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    blc = (data.get("summary") or {}).get("by_level_counts")
    if not blc:
        raise ScoreError("no summary.by_level_counts -- cannot be re-scored")
    counts = normalize_counts(blc)
    weights = WEIGHT_SCHEMES[scheme]["weights"]

    flat = score(counts, WEIGHT_SCHEMES["flat"]["weights"])
    weighted = score(counts, weights)
    n_flat = sum(n for _, n in counts.values())
    n_weighted = sum(weights[lvl] * n for lvl, (_, n) in counts.items())

    return {
        "file": path.as_posix(),
        "flat": flat,
        "weighted": weighted,
        "delta_pp": (weighted - flat) * 100,
        "scheme": scheme,
        "weights": dict(weights),          # spec point 3: reproducible from the artifact
        "n": n_flat,
        "n_weighted": n_weighted,
        "levels": sorted(counts),
        # Provenance: the judge is nondeterministic, so a number is a snapshot of
        # a file at a time. Carry what produced it.
        "judge_model": (data.get("summary") or {}).get("judge_model"),
        "judge_prompt_sha256": (data.get("summary") or {}).get("judge_prompt_sha256"),
        "accuracy_reported": (data.get("summary") or {}).get("accuracy"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="verdicts_*.json to re-score")
    ap.add_argument("--scheme", default=DEFAULT_SCHEME, choices=sorted(WEIGHT_SCHEMES))
    ap.add_argument("--all-schemes", action="store_true",
                    help="print every scheme side by side (sensitivity check)")
    ap.add_argument("--json", dest="json_out", help="write results as JSON")
    args = ap.parse_args()

    schemes = sorted(WEIGHT_SCHEMES) if args.all_schemes else [args.scheme]
    rows, errors = [], []
    for f in args.files:
        p = Path(f)
        for s in schemes:
            try:
                rows.append(score_file(p, s))
            except (ScoreError, json.JSONDecodeError) as e:
                errors.append(f"{p.name}: {e}")
                break

    if rows:
        name_w = max(len(Path(r["file"]).name) for r in rows)
        header = f"{'file':<{name_w}}  {'flat':>7}  {'weighted':>9}  {'delta':>7}  scheme"
        print(header)
        print("-" * len(header))
        for r in rows:
            print(f"{Path(r['file']).name:<{name_w}}  {r['flat']:>6.1%}  "
                  f"{r['weighted']:>8.1%}  {r['delta_pp']:>+6.1f}pp  {r['scheme']}")
        print()
        for s in schemes:
            w = WEIGHT_SCHEMES[s]
            print(f"  {s}: {w['label']}  ->  "
                  + " ".join(f"{k}={v:g}" for k, v in w["weights"].items()))

    for e in errors:
        print(f"SKIPPED {e}")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"results": rows, "schemes":
                        {s: WEIGHT_SCHEMES[s] for s in schemes}, "skipped": errors},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
