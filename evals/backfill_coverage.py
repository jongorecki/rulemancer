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
from rulesagent.generate.answer import prompt_supplied_rule_ids  # noqa: E402
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


def row_prompt_supplied_ids(row: dict) -> list[str]:
    """The prompt-supplied id set for a row -- ids that reached the model
    outside retrieval, via the system prompt or a tool schema (see
    rulesagent.generate.answer.prompt_supplied_rule_ids). Prefers the field
    recorded at generation time (rows written after that fix landed) and
    falls back to recomputing it from the row's own recorded
    system_version/layers_tool fields for older rows that predate it --
    both of those fields are already stamped on every run_answer_eval.py
    row (constant across a run, per-row for provenance), so no re-run is
    needed to backfill this. Rows carrying neither field (e.g.
    h2h_gpt5mini.json, joined from a bare OpenRouter result with no
    RulesAgent config attached) get no prompt-supplied ids -- honestly
    "unknown", not guessed."""
    if "prompt_supplied_rule_ids" in row:
        return row["prompt_supplied_rule_ids"]
    system_version = row.get("system_version")
    if system_version is None:
        return []
    layers_tool = bool(row.get("layers_tool"))
    return sorted(prompt_supplied_rule_ids(system_version, layers_tool))


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

    `coverage` is the CORRECTED formula (retrieved OR prompt-supplied, see
    row_prompt_supplied_ids/prompt_supplied_rule_ids) -- the measurement-bug
    fix. `coverage_uncorrected` keeps the original retrieved-only formula
    alongside it so the fix is auditable, not a silent overwrite of the old
    number. `hit`/`gap` are unaffected by the fix: hit still comes from
    hit_bool_from_ids() over retrieved_ids only (hit_at()'s own semantics
    are untouched, per the coverage-bug task's invariant), and `gap` is
    computed against the corrected coverage.
    """
    gold = row.get("gold") or []
    match = row.get("match", "any")
    retrieved_ids = row.get("retrieved_rule_ids") or []
    prompt_ids = row_prompt_supplied_ids(row)
    cov_uncorrected = coverage_from_ids(gold, retrieved_ids)
    cov = coverage_from_ids(gold, retrieved_ids, prompt_supplied=prompt_ids)

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
        "coverage": cov, "coverage_uncorrected": cov_uncorrected,
        "prompt_supplied_n": len(prompt_ids),
        "hit": hit, "gap": gap,
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
    covs_uncorrected = [r["coverage_uncorrected"] for r in scored if r["coverage_uncorrected"] is not None]
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
        # Pre-fix number, kept alongside the corrected one above so the
        # measurement-bug fix is auditable rather than a silent overwrite
        # (see score_row's docstring / prompt_supplied_rule_ids).
        "mean_coverage_uncorrected": (sum(covs_uncorrected) / len(covs_uncorrected)) if covs_uncorrected else None,
        "hit_rate": (sum(1 for h in hits if h) / len(hits)) if hits else None,
        "n_hit_scored": len(hits),
        "debug": arm_label in DEBUG_ARMS,
        "retrieval_off": retrieval_off,
    }
    return summary, scored


# ---------------------------------------------------------------------------
# Gold-size stratification (docs/spec-coverage-metric.md follow-up, Jon
# 2026-07-26). THE TRAP: a row with exactly one gold rule can never be
# "partial" coverage -- it is all-or-nothing (1/1 or 0/1). So a flat
# zero/partial/full split over the whole corpus puts only multi-rule
# questions in "partial", which are harder by construction, and any
# accuracy comparison across those buckets confuses gold-set size with
# retrieval quality. Stratifying by gold-set size first is the fix; see
# coverage_at()/coverage_from_ids() docstrings in run_eval.py for the
# guard-rail this motivated.
# ---------------------------------------------------------------------------

STRATA_ORDER = ["1", "2", "3", "4+"]
COVERAGE_BUCKET_ORDER = ["zero", "partial", "full"]

# The six arms behind the numbers in the task brief: one rep each (r1, not
# the r2 duplicate) of every distinct shipped `claude-opus-5`/effort=low
# product config, excluding the gold-audit candidate-review arms (not a
# shipped config, they're a curation worklist) and h2h_gpt5mini (a raw
# OpenRouter comparison arm with no recorded judge). n=408 gold-bearing
# rows across these six, matching docs/HANDOFF-development.md's "shipped
# config" (opus5_low) references and the "BOTH reps of the shipped config"
# language for gold_audit_batch2_opuslow.
# The shipped product config, and ONLY that: claude-opus-5, system_version 3,
# effort=low, layers_tool on. Both reps of each h2h bucket are included so the
# 7-10% run-to-run flip rate stays visible instead of being averaged away by
# picking one rep.
#
# Do NOT add claude-sonnet-5 arms (h2h_sonnet_*, layers_slice0_base_layers_*)
# here. They are a different generator, and layers_slice0_* additionally runs
# with layers_tool=False, so it can never receive the prompt-supplied-id
# correction. Mixing them in makes the corrected mean look smaller for a reason
# that has nothing to do with retrieval -- which is the exact class of
# multi-variable confusion docs/results-adversarial-review.md exists to stop.
SHIPPED_ARMS = [
    "l0_opuslow",
    "h2h_opuslow_hard_r1", "h2h_opuslow_hard_r2",
    "h2h_opuslow_easy_r1", "h2h_opuslow_easy_r2",
    "opus5_low_norewrite_costbase",
]

# Verdict file for each arm that has one, resolved by hand (filename
# convention is inconsistent across scripts: some are `verdicts_<arm>.json`,
# two are `<prefix>_verdicts_<rest>.json`) and confirmed to exist on disk.
# Arms absent from this map report coverage-only, per the brief: "where an
# arm has no verdict file, report coverage-only rather than dropping the arm."
VERDICT_FILES = {
    "derivability_B_goldonly": "verdicts_derivability_B.json",
    "derivability_C_failures": "verdicts_derivability_C.json",
    "h2h_gpt5mini": "h2h_verdicts_gpt5mini.json",
    "h2h_opuslow_easy_r1": "verdicts_h2h_opuslow_easy_r1.json",
    "h2h_opuslow_easy_r2": "verdicts_h2h_opuslow_easy_r2.json",
    "h2h_opuslow_hard_r1": "verdicts_h2h_opuslow_hard_r1.json",
    "h2h_opuslow_hard_r2": "verdicts_h2h_opuslow_hard_r2.json",
    "h2h_sonnet_easy_r1": "verdicts_h2h_sonnet_easy_r1.json",
    "h2h_sonnet_easy_r2": "verdicts_h2h_sonnet_easy_r2.json",
    "l0_opuslow": "verdicts_l0_opuslow.json",
    "layers_slice0_base_layers_r1": "layers_slice0_verdicts_base_layers_r1.json",
    "layers_slice0_base_layers_r2": "layers_slice0_verdicts_base_layers_r2.json",
    # The arm and its verdict file are named after different things -- the arm
    # after its cost-baseline purpose, the verdicts after the bucket-A row set.
    # Confirmed to be the same 68 question ids, joined and verified 2026-07-26.
    "opus5_low_norewrite_costbase": "verdicts_opus5_low_bucketA.json",
}


def coverage_bucket(cov: float) -> str:
    """The three-way split every coverage number gets sorted into for
    reporting. cov==0.0 -> "zero", cov==1.0 -> "full", else "partial".
    Structural note this function does NOT itself know: a row whose gold_n
    is 1 can only ever land in "zero" or "full" -- see module docstring."""
    if cov <= 0.0:
        return "zero"
    if cov >= 1.0:
        return "full"
    return "partial"


def gold_size_stratum(gold_n: int) -> str:
    """Which STRATA_ORDER bucket a row's gold-set size falls in. 1/2/3
    each get their own bucket (small enough to matter individually); 4+
    pools everything larger, where the exact size stops changing the
    all-or-nothing structure that motivates stratifying at all."""
    if gold_n >= 4:
        return "4+"
    return str(gold_n)


def load_verdict_map(arm: str, repo: Path = REPO) -> dict[str, bool] | None:
    """id -> (verdict == "same") for one arm, or None when this arm has no
    known verdict file (VERDICT_FILES) or the file is missing/unreadable --
    callers must treat None as "unknown", never as "all wrong"."""
    fn = VERDICT_FILES.get(arm)
    if fn is None:
        return None
    path = repo / "evals" / fn
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    entries = data.get("entries", []) if isinstance(data, dict) else data
    return {e["id"]: e.get("verdict") == "same" for e in entries
            if isinstance(e, dict) and "id" in e and "verdict" in e}


def stratify_by_gold_size(scored_rows: list[dict],
                           verdict_maps: dict[str, dict[str, bool] | None]) -> dict:
    """The stratified breakdown: gold-size stratum x coverage bucket, with
    n / mean coverage per stratum and accuracy per cell wherever a verdict
    file exists for that row's arm. Rows with gold_n==0 (empty gold,
    coverage None) are excluded, same convention as everywhere else in this
    module. `verdict_maps` is {arm: load_verdict_map(arm)} -- None for arms
    with no verdict file, so those rows contribute coverage but not
    accuracy, per row_prompt_supplied_ids' sibling policy of reporting
    "unknown" honestly rather than dropping or guessing.
    """
    by_stratum: dict[str, list[dict]] = {s: [] for s in STRATA_ORDER}
    for r in scored_rows:
        if r["coverage"] is None:
            continue
        by_stratum[gold_size_stratum(r["gold_n"])].append(r)

    strata_out = []
    for s in STRATA_ORDER:
        rows = by_stratum[s]
        n = len(rows)
        covs = [r["coverage"] for r in rows]
        buckets_out = {}
        for b in COVERAGE_BUCKET_ORDER:
            brows = [r for r in rows if coverage_bucket(r["coverage"]) == b]
            acc_hits = []
            arms_without_verdicts = set()
            for r in brows:
                vmap = verdict_maps.get(r["arm"])
                if vmap is None:
                    arms_without_verdicts.add(r["arm"])
                    continue
                v = vmap.get(r["id"])
                if v is not None:
                    acc_hits.append(v)
            buckets_out[b] = {
                "n": len(brows),
                "accuracy": (sum(acc_hits) / len(acc_hits)) if acc_hits else None,
                "n_accuracy_scored": len(acc_hits),
                "arms_without_verdicts": sorted(arms_without_verdicts),
            }
        strata_out.append({
            "stratum": s,
            "n": n,
            "mean_coverage": (sum(covs) / n) if n else None,
            # Stated explicitly per the brief: an empty "partial" cell for
            # stratum "1" is a structural fact (1/1 or 0/1, nothing between),
            # not a data gap -- the dashboard/report must say so rather than
            # leave a confusing blank.
            "structurally_no_partial": s == "1",
            "buckets": buckets_out,
        })
    return {"strata": strata_out}


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


def print_stratified_table(title: str, strat: dict) -> None:
    n_total = sum(s["n"] for s in strat["strata"])
    print(f"\n{title} ({n_total} gold-bearing rows)")
    print(f"{'gold_n':<8}{'n':>6}{'mean_cov':>10}   "
          f"{'zero(n/acc)':<18}{'partial(n/acc)':<18}{'full(n/acc)':<18}")
    for s in strat["strata"]:
        cells = []
        for b in COVERAGE_BUCKET_ORDER:
            bd = s["buckets"][b]
            if b == "partial" and s["structurally_no_partial"]:
                cells.append(f"n/a (structural)".ljust(18))
                continue
            acc = f"{bd['accuracy']*100:.1f}%" if bd["accuracy"] is not None else "—"
            cells.append(f"{bd['n']}/{acc}".ljust(18))
        mc = f"{s['mean_coverage']*100:.1f}%" if s["mean_coverage"] is not None else "—"
        print(f"{s['stratum']:<8}{s['n']:>6}{mc:>10}   " + "".join(cells))


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

    verdict_maps = {name: load_verdict_map(name) for name in arms}

    # Pooled across every non-debug, non-retrieval-off arm -- i.e. real
    # pipeline runs, not scratch fixtures and not oracle arms whose coverage
    # is near-zero by construction (retrieval was off, so "zero coverage"
    # there means nothing about retrieval quality). This is the general
    # dashboard breakdown.
    pipeline_rows = [r for r in all_scored
                      if not arms[r["arm"]]["debug"] and not arms[r["arm"]]["retrieval_off"]]
    strat_pipeline = stratify_by_gold_size(pipeline_rows, verdict_maps)

    # The six arms behind the brief's worked numbers (SHIPPED_ARMS above).
    shipped_rows = [r for r in all_scored if r["arm"] in SHIPPED_ARMS]
    strat_shipped = stratify_by_gold_size(shipped_rows, verdict_maps)

    out = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "gap_threshold": GAP_THRESHOLD,
        "arms": list(arms.values()),
        "skipped": skipped,
        "worklist_n_total": len(all_rows_ranked),
        "worklist_n_above_threshold": len(above_threshold),
        "worklist": all_rows_ranked[:200],  # cap for the dashboard payload; full ranking is deterministic
        "gold_size_stratification": strat_pipeline,
        "gold_size_stratification_shipped": strat_shipped,
        "shipped_arms": SHIPPED_ARMS,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"wrote {OUT_PATH} ({len(arms)} arms, {len(all_scored)} rows scored, "
          f"{len(skipped)} skipped)")
    print(f"\n{'arm':<40}{'n':>6}{'empty':>7}{'mean_cov':>10}{'was':>10}{'hit_rate':>10}{'hit_n':>7}  note")
    for a in arms.values():
        mc = f"{a['mean_coverage']*100:.1f}%" if a["mean_coverage"] is not None else "—"
        mc_old = f"{a['mean_coverage_uncorrected']*100:.1f}%" if a["mean_coverage_uncorrected"] is not None else "—"
        hr = f"{a['hit_rate']*100:.1f}%" if a["hit_rate"] is not None else "—"
        note = "retrieval OFF (oracle)" if a["retrieval_off"] else ("debug/smoke" if a["debug"] else "")
        print(f"{a['arm']:<40}{a['n_rows']:>6}{a['n_empty_gold']:>7}{mc:>10}{mc_old:>10}{hr:>10}{a['n_hit_scored']:>7}  {note}")
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

    print_stratified_table(
        "Gold-size stratification -- pooled pipeline arms (excludes debug/oracle):",
        strat_pipeline)
    print_stratified_table(
        f"Gold-size stratification -- six shipped-config arms "
        f"({', '.join(SHIPPED_ARMS)}):", strat_shipped)


if __name__ == "__main__":
    main()
