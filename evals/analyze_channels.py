"""Channel-ablation read-out: which part of the context is carrying the answers?

Five arms over the same 120 rows (evals/ab_rows.jsonl), each differing from arm A
in exactly one channel, everything else byte-identical:

    A  real rules, real card text, real rulings      <- baseline
    B  PLACEBO rules, real card text, real rulings   <- isolates the CR rules
    R  real rules, real card text, PLACEBO rulings   <- isolates the rulings
    K  real rules, PLACEBO card text + rulings       <- isolates the card channel
    Z  PLACEBO everything                            <- parametric floor

Read every arm as a distance ABOVE Z, not as an absolute number. Z is what the
model scores with no usable context at all, so it is the zero point for what the
retrieval pipeline is actually worth.

TWO CORRECTNESS NOTES, both of which will silently mislead if ignored:

1. The derangement was drawn over an ELIGIBLE SUBSET, not all 120 rows. rg1006
   has no cards at all; rg46/rg625/rg1006 have no rulings anywhere. Those rows
   are byte-identical to arm A on that dimension, with borrowed_from=null. They
   are NOT placebo rows and are excluded per-arm below -- counting them would
   dilute the measured effect toward zero.

2. Paired comparison (McNemar) is the read, not arm means. Power depends on the
   discordant pairs, not the row count: this corpus runs ~17-20% discordance, so
   n=120 yields ~20-24 informative pairs and can only resolve a large effect.

Zero API cost -- pure analysis over files on disk.
Run: uv run python evals/analyze_channels.py
"""

import io
import json
import sys
from collections import Counter
from pathlib import Path

EVALS = Path(__file__).resolve().parent
PILOT = EVALS / "answers" / "ab_pilot"

# arm -> (answer shards, verdict shards, prompts cache holding borrowed_from)
ARMS = {
    "A  baseline (all real)": (["A_real", "A_real_rest"],
                               ["ab_pilot_verdicts_A", "ab_pilot_verdicts_A_rest"], None),
    "B  placebo RULES": (["B_placebo", "B_placebo_rest"],
                         ["ab_pilot_verdicts_B", "ab_pilot_verdicts_B_rest"],
                         "_prompts_ab_placebo"),
    "R  placebo RULINGS": (["R_placebo_rulings"], ["ab_pilot_verdicts_R"],
                           "_prompts_ab_placebo_rulings"),
    "K  placebo CARD DATA": (["K_placebo_carddata"], ["ab_pilot_verdicts_K"],
                             "_prompts_ab_placebo_carddata"),
    "Z  placebo EVERYTHING": (["Z_placebo_all"], ["ab_pilot_verdicts_Z"],
                              "_prompts_ab_placebo_all"),
}


def load_rows(names):
    rows = []
    for n in names:
        p = PILOT / f"{n}.json"
        if p.exists():
            rows += json.load(io.open(p, encoding="utf-8"))
    return rows


def load_verdicts(names):
    v = {}
    for n in names:
        p = EVALS / f"{n}.json"
        if not p.exists():
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        for e in (d["entries"] if isinstance(d, dict) else d):
            v[e["id"]] = e["verdict"] == "same"
    return v


def swapped_ids(cache_name):
    """Ids this arm actually placebo'd. None means 'all rows' (baseline)."""
    if cache_name is None:
        return None
    p = PILOT / f"{cache_name}.json"
    if not p.exists():
        return None
    bf = json.load(io.open(p, encoding="utf-8")).get("borrowed_from") or {}
    return {k for k, v in bf.items() if v}


def main() -> None:
    base_v = load_verdicts(ARMS["A  baseline (all real)"][1])
    z_v = load_verdicts(ARMS["Z  placebo EVERYTHING"][1])

    print(f"{'arm':26}{'n':>5}{'judged':>8}{'acc':>9}{'vs A':>8}{'vs Z':>8}")
    print("-" * 64)
    accs = {}
    for label, (ashards, vshards, cache) in ARMS.items():
        rows = load_rows(ashards)
        verd = load_verdicts(vshards)
        if not rows or not verd:
            print(f"{label:26}{len(rows):5}{len(verd):8}{'  pending':>9}")
            continue
        ids = [r["id"] for r in rows if r["id"] in verd]
        acc = 100 * sum(verd[i] for i in ids) / len(ids)
        accs[label] = acc
        base = accs.get("A  baseline (all real)")
        zed = accs.get("Z  placebo EVERYTHING")
        d_a = f"{acc-base:+6.1f}" if base is not None and label != "A  baseline (all real)" else "     -"
        d_z = f"{acc-zed:+6.1f}" if zed is not None and label != "Z  placebo EVERYTHING" else "     -"
        print(f"{label:26}{len(rows):5}{len(ids):8}{acc:8.1f}%{d_a:>8}{d_z:>8}")

    print("\nPAIRED vs baseline A -- only rows this arm ACTUALLY placebo'd")
    print("(rows with nothing to swap are excluded; see module docstring note 1)")
    for label, (ashards, vshards, cache) in ARMS.items():
        if label.startswith("A "):
            continue
        verd = load_verdicts(vshards)
        if not verd:
            continue
        sw = swapped_ids(cache)
        ids = sorted(i for i in verd if i in base_v and (sw is None or i in sw))
        if not ids:
            continue
        t = Counter((base_v[i], verd[i]) for i in ids)
        disc = t[(True, False)] + t[(False, True)]
        excl = len([i for i in verd if i in base_v]) - len(ids)
        print(f"\n  A vs {label}   n={len(ids)}"
              + (f"  ({excl} row(s) excluded as not actually swapped)" if excl else ""))
        print(f"    both right {t[(True, True)]:3} | A only {t[(True, False)]:3}"
              f" | {label.split()[0]} only {t[(False, True)]:3} | both wrong {t[(False, False)]:3}")
        print(f"    discordant {disc}"
              + ("   <- too few to resolve anything" if disc < 10 else ""))


if __name__ == "__main__":
    main()
