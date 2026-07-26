"""Backfill the graded coverage metric (docs/spec-coverage-metric.md) across
every recorded answers/*.json arm that carries `retrieved_rule_ids`.

Zero model calls, zero re-run arms: every number here is pure arithmetic over
`gold` + `retrieved_rule_ids` fields already sitting on disk (spec section 6).
`coverage_from_ids()` (evals/run_eval.py) is the one formula used; this script
only does the file-finding, joining, and aggregation around it.

Also builds THE DIAGNOSTIC: a worklist of rows where `hit_at()` would have
scored a complete retrieval success (all required groups satisfied) while
graded coverage says a meaningful share of the cited gold never showed up.
That gap is a ranking signal for which multi-rule rows are worth a human
look, not a claim that any of them are wrong.

Run: .venv/Scripts/python.exe evals/backfill_coverage.py
Writes: evals/coverage_backfill.json (consumed by build_metrics_history.py)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evals"))
sys.path.insert(0, str(REPO / "src"))

from rulesagent.contracts import EvalQuestion, normalize_source_id  # noqa: E402
from run_eval import coverage_from_ids, gold_groups  # noqa: E402  (byte-identical, imported not reimplemented)

ANSWERS_DIR = REPO / "evals" / "answers"
V3_PATH = REPO / "evals" / "questions_rulesguru150_v3.jsonl"
H2H_SET_PATH = REPO / "evals" / "_h2h_set.jsonl"
OUT_PATH = REPO / "evals" / "coverage_backfill.json"

# Every evals/answers/*.json file confirmed (grep "retrieved_rule_ids") to carry
# it per row, or (h2h_gpt5mini) per row of its `results` list. 21 files, per
# docs/spec-coverage-metric.md section 6.
ARM_FILES = [
    "_opus5_low_disagreements.json", "_pilot_cache_check.json", "_pilot_opus5_high.json",
    "_smoke_derivB.json", "_ui_mode_demo.json", "derivability_B_goldonly.json",
    "derivability_C_failures.json", "gold_audit_batch2_candidates.json",
    "gold_audit_batch2_opuslow_candidates.json", "h2h_gpt5mini.json",
    "h2h_opuslow_easy_r1.json", "h2h_opuslow_easy_r2.json", "h2h_opuslow_hard_r1.json",
    "h2h_opuslow_hard_r2.json", "h2h_sonnet_easy_r1.json", "h2h_sonnet_easy_r2.json",
    "l0_opuslow.json", "layers_slice0_base_layers_r1.json", "layers_slice0_base_layers_r2.json",
    "layers_slice0_base_layers_r3.json", "opus5_low_norewrite_costbase.json",
]

# Internal scratch/debug files (smoke tests, tiny pilot/UI-demo fixtures) --
# genuinely backfilled like every other file, just flagged separately because
# n<10 rows makes a per-arm mean read as evidence of nothing.
DEBUG_ARMS = {"_opus5_low_disagreements", "_pilot_cache_check", "_pilot_opus5_high",
              "_smoke_derivB", "_ui_mode_demo"}

# Files whose rows do not carry `gold`/`match` inline and must be joined back
# to a question file by id (only h2h_gpt5mini, confirmed: its rows are raw
# OpenRouter results with no gold field at all).
JOIN_SOURCES = {"h2h_gpt5mini.json": H2H_SET_PATH}

# THE THRESHOLD for "inflated enough to change a number": more than half of a
# question's cited gold missing despite hit_at() scoring it a complete
# retrieval success. Chosen (not the midpoint by default-itis) because it is
# the same bar results-miss-partition.md's rg4023 worked example crosses (10
# gold ids, 3 retrieved -> coverage 0.30, gap 0.70) and it cannot be crossed by
# an "almost there" row (e.g. 4/5 gold retrieved -> gap 0.20) -- only rows
# where the boolean's full-credit call and the graded reality are more than a
# coin flip apart make the cut.
GAP_THRESHOLD = 0.5


def load_arm_rows(path: Path) -> list[dict]:
    """List-shaped files return their list directly; h2h_gpt5mini.json is a
    summary dict whose per-row data lives under `results`."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("results", [])


def load_v3_groups() -> dict[str, list[list[str]]]:
    """id -> gold_groups, for the 79 match:"groups" rows of the curated
    150-set (docs/spec-coverage-metric.md section 6's named join)."""
    out = {}
    with open(V3_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("match") == "groups":
                out[row["id"]] = row["gold_groups"]
    return out


def load_h2h_set() -> dict[str, dict]:
    """id -> {gold, match} for the 36-question h2h set h2h_gpt5mini.json's
    rows must be joined against (they carry no gold/match of their own)."""
    out = {}
    with open(H2H_SET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            out[row["id"]] = {"gold": row["gold"], "match": row["match"]}
    return out


def resolve_gold_groups(row: dict, match: str, v3_groups: dict) -> list[list[str]] | None:
    """The gold_groups a match:"groups" row needs to compute a hit boolean.
    Only match:"groups" rows need this at all (any/all derive their groups
    from `gold` alone, same as gold_groups() does). Returns None when it
    cannot be resolved (row carries no gold_groups AND isn't in the v3 join) --
    the caller then leaves this row's hit/gap as None rather than guessing."""
    if match != "groups":
        return None  # unused: gold_groups() derives any/all from gold directly
    if "gold_groups" in row:
        return row["gold_groups"]
    return v3_groups.get(row["id"])


def hit_bool_from_ids(groups: list[list[str]], retrieved_ids: list[str]) -> bool:
    """Mirrors hit_at()'s predicate exactly (evals/run_eval.py lines 169-177),
    sourced from a plain retrieved-id list instead of `Retrieved` objects --
    those wrap a full `Chunk` (kind/section/text) that recorded answer rows
    never stored, so reconstructing them just to call hit_at() would require
    fabricating fields hit_at() never actually reads. hit_at() itself is not
    touched; this is a second, id-only implementation of the same one-line
    rule, verified against hit_at() directly in tests/test_coverage_metric.py."""
    retrieved = {normalize_source_id(x) for x in retrieved_ids}
    return all(any(normalize_source_id(g) in retrieved for g in group) for group in groups)


def score_row(arm: str, row: dict, v3_groups: dict) -> dict:
    """One row's coverage + (where resolvable) hit boolean + gap.

    Returns None for `coverage`/`hit`/`gap` fields only where the underlying
    convention says so: coverage is None for empty gold (same convention as
    coverage_at()/group_coverage()); hit/gap are None when the row is
    match:"groups" and no gold_groups could be resolved (see
    resolve_gold_groups) -- reported honestly as "unknown", never defaulted to
    a guessed True/False.
    """
    gold = row.get("gold") or []
    match = row.get("match", "any")
    retrieved_ids = row.get("retrieved_rule_ids") or []
    cov = coverage_from_ids(gold, retrieved_ids)

    hit = None
    if gold:
        if match == "groups":
            groups = resolve_gold_groups(row, match, v3_groups)
            if groups is not None:
                hit = hit_bool_from_ids(groups, retrieved_ids)
        else:
            q = EvalQuestion(id=row["id"], question="", gold=gold, match=match)
            hit = hit_bool_from_ids(gold_groups(q), retrieved_ids)

    gap = None
    if cov is not None and hit is not None:
        gap = (1.0 if hit else 0.0) - cov

    return {
        "arm": arm, "id": row["id"], "match": match, "gold_n": len(gold),
        "question": row.get("question", ""),
        "coverage": cov, "hit": hit, "gap": gap,
        "retrieved_n": len(retrieved_ids),
    }


def score_arm(fn: str, path: Path, v3_groups: dict, h2h_set: dict) -> tuple[dict, list[dict]]:
    arm_label = fn[:-5]  # strip ".json" -- the clean name used in every report/label
    rows = load_arm_rows(path)
    join = h2h_set if fn in JOIN_SOURCES else None
    scored = []
    n_join_missing = 0
    for row in rows:
        if join is not None:
            info = join.get(row["id"])
            if info is None:
                n_join_missing += 1
                continue
            row = {**row, "gold": info["gold"], "match": info["match"]}
        scored.append(score_row(arm_label, row, v3_groups))

    n = len(scored)
    n_empty_gold = sum(1 for r in scored if r["coverage"] is None)
    n_scored = n - n_empty_gold
    covs = [r["coverage"] for r in scored if r["coverage"] is not None]
    hits = [r["hit"] for r in scored if r["hit"] is not None]
    n_hit_unknown = sum(1 for r in scored if r["coverage"] is not None and r["hit"] is None)
    n_retrieved_empty = sum(1 for r in scored if r["retrieved_n"] == 0)
    # An arm where EVERY row's retrieved_rule_ids is empty is a retrieval-off
    # oracle condition (gold handed to the generator directly, e.g.
    # derivability_B_goldonly) rather than a retrieval failure -- 0% coverage
    # there is expected, not a regression, and the dashboard must say so
    # rather than implying retrieval scored zero.
    retrieval_off = n > 0 and n_retrieved_empty == n

    summary = {
        "arm": arm_label, "n_rows": n, "n_empty_gold": n_empty_gold, "n_scored": n_scored,
        "n_join_missing": n_join_missing, "n_hit_unknown": n_hit_unknown,
        "mean_coverage": (sum(covs) / len(covs)) if covs else None,
        "hit_rate": (sum(1 for h in hits if h) / len(hits)) if hits else None,
        "n_hit_scored": len(hits),
        "debug": arm_label in DEBUG_ARMS,
        "retrieval_off": retrieval_off,
    }
    return summary, scored


def build_worklist(all_scored: list[dict], threshold: float = GAP_THRESHOLD) -> tuple[list[dict], list[dict]]:
    """Rows where hit_at() would call it a complete pass but coverage
    disagrees, ranked by the size of that disagreement -- biggest inflation
    first. Only rows with a resolvable gap (hit AND coverage both known)
    participate; hit==False rows are not inflation (gap<=0) and are excluded
    from THIS list, though they're still in the per-row data. Returns
    (full ranking, the subset above `threshold`)."""
    rows = [r for r in all_scored if r["gap"] is not None and r["gap"] > 0]
    rows.sort(key=lambda r: r["gap"], reverse=True)
    above = [r for r in rows if r["gap"] > threshold]
    return rows, above


def main() -> None:
    v3_groups = load_v3_groups()
    h2h_set = load_h2h_set()

    arms = {}
    all_scored: list[dict] = []
    skipped = []
    for fn in ARM_FILES:
        path = ANSWERS_DIR / fn
        name = fn[:-5]  # strip ".json"
        if not path.exists():
            skipped.append({"arm": name, "reason": "file not found"})
            continue
        try:
            summary, scored = score_arm(fn, path, v3_groups, h2h_set)
        except Exception as e:  # noqa: BLE001 -- a live-written arm can be mid-write JSON
            skipped.append({"arm": name, "reason": f"{type(e).__name__}: {e}"})
            continue
        arms[name] = summary
        all_scored.extend(scored)

    all_rows_ranked, above_threshold = build_worklist(all_scored)

    out = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "gap_threshold": GAP_THRESHOLD,
        "arms": list(arms.values()),
        "skipped": skipped,
        "worklist_n_total": len(all_rows_ranked),
        "worklist_n_above_threshold": len(above_threshold),
        "worklist": all_rows_ranked[:200],  # cap for the dashboard payload; full ranking is deterministic
    }
    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"wrote {OUT_PATH} ({len(arms)} arms, {len(all_scored)} rows scored, "
          f"{len(skipped)} skipped)")
    print(f"\n{'arm':<40}{'n':>6}{'empty':>7}{'mean_cov':>10}{'hit_rate':>10}{'hit_n':>7}  note")
    for a in arms.values():
        mc = f"{a['mean_coverage']*100:.1f}%" if a["mean_coverage"] is not None else "—"
        hr = f"{a['hit_rate']*100:.1f}%" if a["hit_rate"] is not None else "—"
        note = "retrieval OFF (oracle)" if a["retrieval_off"] else ("debug/smoke" if a["debug"] else "")
        print(f"{a['arm']:<40}{a['n_rows']:>6}{a['n_empty_gold']:>7}{mc:>10}{hr:>10}{a['n_hit_scored']:>7}  {note}")
    if skipped:
        print("\nskipped:")
        for s in skipped:
            print(f"  {s['arm']}: {s['reason']}")
    print(f"\nworklist: {len(all_rows_ranked)} rows with a resolvable gap>0, "
          f"{len(above_threshold)} above threshold {GAP_THRESHOLD}")
    print(f"\n{'rank':<5}{'arm':<44}{'id':<10}{'match':<7}{'gold_n':>7}{'hit':>5}{'cov':>7}{'gap':>7}")
    for i, r in enumerate(all_rows_ranked[:10], 1):
        print(f"{i:<5}{r['arm']:<44}{r['id']:<10}{r['match']:<7}{r['gold_n']:>7}"
              f"{'Y' if r['hit'] else '.':>5}{r['coverage']*100:>6.0f}%{r['gap']*100:>6.0f}%")


if __name__ == "__main__":
    main()
