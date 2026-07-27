"""Consolidated read-out for the retrieval A/B + groundedness-guard experiment.

Joins every arm shard under evals/answers/ab_pilot/ with its verdict file and
reports, per arm: accuracy, decline rate, grounded rate (rows citing >=1 CR
rule), reground firing rate, fabrication check, and measured cost.

Grounded rate is the metric the guard targets. It counts ONLY CR rule-number
citations -- card names, glossary terms and "[X ruling #N]" labels are not
grounding claims, which is the exact defect the guard fixes
(docs/results-groundedness-guard.md).

The `gained` column counts rows where the reground re-ask took cr_citations from
0 to >0. It is NOT a fabrication count, and an earlier version of this file
wrongly implied it was. Gaining a citation is the re-ask working as intended
whenever the cited rule was genuinely in context -- checked on all 5 such rows in
Bg, every one of them cited a rule actually present in its own prompt.

**The real fabrication canary is `unresolved` in evals/grounding_sources.py**: a
citation that resolves to nothing the prompt provided. That is the number that
must stay at zero, and it has, across every arm.

Note also that `acc` is computed only over rows that have a verdict. An arm whose
judging is incomplete will show accuracy for the judged subset while `n` reports
every generated row -- read the two columns together, not separately.

Zero API cost -- pure analysis over files already on disk.

Run: uv run python evals/analyze_guard_ab.py
"""

import io
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rulesagent import pricing  # noqa: E402
from rulesagent.generate.answer import cr_rule_citations  # noqa: E402

EVALS = Path(__file__).resolve().parent
PILOT = EVALS / "answers" / "ab_pilot"

# arm label -> (answer shards, verdict shards). Shards exist because arms were
# run in a 15-row pilot batch first and the remaining 105 after the cost
# checkpoint; they are the same config and are pooled here.
ARMS = {
    "A  real rules": (["A_real", "A_real_rest"], ["ab_pilot_verdicts_A", "ab_pilot_verdicts_A_rest"]),
    "B  placebo rules": (["B_placebo", "B_placebo_rest"], ["ab_pilot_verdicts_B", "ab_pilot_verdicts_B_rest"]),
    "D  real, effort=high": (["D_efforthigh"], ["ab_pilot_verdicts_D"]),
    "Ag real + reground": (["Ag_real_reground", "Ag_real_reground_rest"],
                           ["ab_pilot_verdicts_Ag", "ab_pilot_verdicts_Ag_rest"]),
    "Bg placebo + reground": (["Bg_placebo_reground", "Bg_placebo_reground_rest"],
                              ["ab_pilot_verdicts_Bg", "ab_pilot_verdicts_Bg_rest"]),
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


def main() -> None:
    ri, ro = pricing.rate("claude-opus-5")
    print(f"{'arm':24}{'n':>5}{'acc':>8}{'grounded':>10}{'decline':>9}"
          f"{'reground':>10}{'gained':>9}{'judged':>8}{'cost':>9}")
    print("-" * 86)
    grand = 0.0
    summary = {}
    for label, (ashards, vshards) in ARMS.items():
        rows = load_rows(ashards)
        if not rows:
            continue
        verd = load_verdicts(vshards)
        n = len(rows)
        ins = sum(r["usage"]["input_tokens"] for r in rows if r.get("usage"))
        outs = sum(r["usage"]["output_tokens"] for r in rows if r.get("usage"))
        cost = ins / 1e6 * ri + outs / 1e6 * ro
        grand += cost

        grounded = sum(1 for r in rows if cr_rule_citations(r.get("citations") or []))
        decline = sum(1 for r in rows if r.get("answered") is False)
        fired = sum(1 for r in rows if r.get("regrounded"))
        # NOT fabrication -- rows where the re-ask produced CR citations that
        # were absent from the first draw. Verified in-context on every such row.
        gained = sum(1 for r in rows if r.get("regrounded")
                     and not r.get("cr_citations_before") and r.get("cr_citations_after"))

        judged = [i for i in (r["id"] for r in rows) if i in verd]
        acc = (100 * sum(verd[i] for i in judged) / len(judged)) if judged else None
        acc_s = f"{acc:6.1f}%" if acc is not None else "     --"
        fired_s = f"{100*fired/n:7.1f}%" if fired else "      --"
        gained_s = f"{gained:>8}" if fired else "      --"
        print(f"{label:24}{n:5}{acc_s:>8}{100*grounded/n:9.1f}%{100*decline/n:8.1f}%"
              f"{fired_s:>10}{gained_s:>9}{len(judged):8}{cost:8.2f}")
        summary[label] = dict(n=n, acc=acc, grounded=100 * grounded / n,
                              decline=100 * decline / n, cost=cost)
    print("-" * 86)
    print(f"{'TOTAL SPEND':24}{'':5}{'':8}{'':10}{'':9}{'':10}{'':11}{grand:8.2f}")

    # Paired reads, only where both arms cover the same ids.
    def paired(a_label, b_label, a_shards, b_shards, av, bv):
        A = {r["id"]: r for r in load_rows(a_shards)}
        B = {r["id"]: r for r in load_rows(b_shards)}
        va, vb = load_verdicts(av), load_verdicts(bv)
        ids = sorted(set(A) & set(B) & set(va) & set(vb))
        if not ids:
            return
        t = Counter((va[i], vb[i]) for i in ids)
        disc = t[(True, False)] + t[(False, True)]
        print(f"\n{a_label}  vs  {b_label}   (paired, n={len(ids)})")
        print(f"   both right {t[(True, True)]:4} | {a_label.split()[0]} only {t[(True, False)]:4}"
              f" | {b_label.split()[0]} only {t[(False, True)]:4} | both wrong {t[(False, False)]:4}")
        print(f"   discordant pairs: {disc} ({100*disc/len(ids):.0f}%)  <- what power depends on")

    paired("A", "B", ARMS["A  real rules"][0], ARMS["B  placebo rules"][0],
           ARMS["A  real rules"][1], ARMS["B  placebo rules"][1])


if __name__ == "__main__":
    main()
