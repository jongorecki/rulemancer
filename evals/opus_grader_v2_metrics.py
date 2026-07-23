"""Opus-grader calibration v2 -- METRICS stage (docs/plan-opus-grader-
calibration.md, "v2" section).

Reads the JSONL verdict files an in-session Opus subagent writes per arm
(evals/opus_grader_v2_out/<arm>.jsonl, one line per cell: {"id", "arm",
"verdict", "reason"}), scores them against Jon's verdicts using the SAME
comparison-set logic as v1 (primary = the `_manual` files + the fully-manual
`verdicts_deepseek-v3-2.json` reference arm; secondary = auto-transferred
cells from the `_final` files), merges everything into
evals/opus_grader_results_v2.jsonl, and writes evals/opus_grader_report_v2.md
with v2's headline numbers, an explicit v1-vs-v2 side-by-side, and a
resolution table of every v1 disagreement (resolved / persisted / still
disagreeing) plus any NEW disagreement v2 introduced.

Like the prep script, this makes ZERO Anthropic/OpenRouter API calls -- it
only reads JSON/JSONL files already on disk and does arithmetic.

Handles missing/partial out-files gracefully: an arm with no out-file, a
partial out-file, or malformed lines is reported as incomplete (with which
ids are missing) rather than crashing the whole report -- this is expected
and normal for a --report-only invocation before grading has actually run
(see the graceful-degradation smoke run this script's own dry run performs).

Run: `uv run python evals/opus_grader_v2_metrics.py`
PYTHONIOENCODING=utf-8 recommended (Windows console).
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from opus_grader_calibration import (  # noqa: E402
    ARM_ANSWER_FILES,
    EVALS_DIR,
    FROZEN_JUDGE_AGREEMENT_PCT,
    FROZEN_JUDGE_LIVE_AUDIT_ERRORS,
    VERDICT_ORDER,
    build_comparison_set,
    build_question_map,
    compute_metrics,
    render_confusion,
    render_disagreements,
    render_errors,
)

OUT_DIR = EVALS_DIR / "opus_grader_v2_out"
V2_RESULTS_PATH = EVALS_DIR / "opus_grader_results_v2.jsonl"
V2_REPORT_PATH = EVALS_DIR / "opus_grader_report_v2.md"
V1_RESULTS_PATH = EVALS_DIR / "opus_grader_results.jsonl"  # existing v1 file, READ ONLY

VALID_VERDICTS = {"correct", "partial", "wrong"}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            out.append({"_parse_error": f"{type(e).__name__}: {e}", "_raw": line})
    return out


def load_v2_out(expected_by_arm: dict[str, set[str]]) -> tuple[dict[tuple[str, str], dict], dict[str, dict]]:
    """Reads evals/opus_grader_v2_out/<arm>.jsonl for every arm. Returns
    (graded_by_key, arm_status) -- graded_by_key maps (arm, id) -> the
    grader's row (only rows with a valid verdict+id); arm_status reports,
    per arm, whether its out-file exists, how many rows parsed, how many
    were valid, and which expected ids are missing -- the graceful-
    degradation surface this script promises, rather than crashing on a
    missing or partial file."""
    graded_by_key: dict[tuple[str, str], dict] = {}
    arm_status: dict[str, dict] = {}

    for arm, expected_ids in expected_by_arm.items():
        path = OUT_DIR / f"{arm}.jsonl"
        rows = load_jsonl(path)
        malformed = [r for r in rows if "_parse_error" in r]
        candidates = [r for r in rows if "_parse_error" not in r]
        valid = [r for r in candidates if r.get("id") in expected_ids and r.get("verdict") in VALID_VERDICTS]
        invalid = [r for r in candidates if r not in valid]
        seen_ids = {r["id"] for r in valid}
        # last-write-wins on duplicate ids within one file, same benign
        # policy as v1's dict-building patterns elsewhere in this project
        for r in valid:
            graded_by_key[(arm, r["id"])] = r
        missing_ids = sorted(expected_ids - seen_ids)
        arm_status[arm] = {
            "out_file_exists": path.exists(),
            "n_lines": len(rows),
            "n_malformed": len(malformed),
            "n_invalid": len(invalid),
            "n_valid": len(valid),
            "n_expected": len(expected_ids),
            "n_missing": len(missing_ids),
            "missing_ids": missing_ids,
            "complete": path.exists() and not missing_ids and not malformed and not invalid,
        }
    return graded_by_key, arm_status


def build_v2_results(cells: list[dict], graded_by_key: dict[tuple[str, str], dict]) -> list[dict]:
    """One row per comparison-set cell, in v1's exact result schema
    (arm/id/set/opus_verdict/opus_reason/jon_verdict/jon_note/agree, or
    arm/id/set/error) -- so v1's own compute_metrics()/render_confusion()/
    render_disagreements()/render_errors() work UNCHANGED on v2 data."""
    results = []
    for cell in cells:
        arm, qid = cell["arm"], cell["id"]
        base = {"arm": arm, "id": qid, "set": cell["set"]}
        g = graded_by_key.get((arm, qid))
        if g is None:
            results.append({**base, "error": "not yet graded (missing from evals/opus_grader_v2_out/<arm>.jsonl)"})
            continue
        results.append({
            **base,
            "opus_verdict": g["verdict"],
            "opus_reason": g.get("reason", ""),
            "jon_verdict": cell["jon_verdict"],
            "jon_note": cell["jon_note"],
            "agree": g["verdict"] == cell["jon_verdict"],
        })
    return results


def classify_resolution(v1_results: list[dict], v2_results: list[dict]) -> dict[str, list[dict]]:
    """Every v1 PRIMARY+SECONDARY disagreement, cross-referenced against the
    SAME (arm, id) cell in v2:
      - resolved:  v1 disagreed, v2 now agrees
      - persisted: v1 disagreed, v2 still disagrees (verdict shown for both)
      - pending:   v1 disagreed, v2 hasn't been graded yet (out-file missing/incomplete)
      - new:       v1 AGREED, v2 introduces a fresh disagreement on that same cell
    """
    v1_by_key = {(r["arm"], r["id"]): r for r in v1_results if "error" not in r}
    v2_by_key = {(r["arm"], r["id"]): r for r in v2_results if "error" not in r}

    resolved, persisted, pending, new = [], [], [], []
    for key, r1 in v1_by_key.items():
        if r1["agree"]:
            continue
        r2 = v2_by_key.get(key)
        row = {
            "arm": key[0], "id": key[1], "jon": r1["jon_verdict"],
            "v1_opus": r1["opus_verdict"],
        }
        if r2 is None:
            pending.append(row)
        elif r2["agree"]:
            row["v2_opus"] = r2["opus_verdict"]
            resolved.append(row)
        else:
            row["v2_opus"] = r2["opus_verdict"]
            persisted.append(row)

    for key, r1 in v1_by_key.items():
        if not r1["agree"]:
            continue
        r2 = v2_by_key.get(key)
        if r2 is not None and not r2["agree"]:
            new.append({
                "arm": key[0], "id": key[1], "jon": r1["jon_verdict"],
                "v1_opus": r1["opus_verdict"], "v2_opus": r2["opus_verdict"],
            })

    return {"resolved": resolved, "persisted": persisted, "pending": pending, "new": new}


def pct(x) -> str:
    return f"{x:.1f}%" if x is not None else "n/a"


def frac_pct(num, den) -> str:
    return f"{num}/{den} ({pct(num / den * 100 if den else None)})"


def render_arm_status(arm_status: dict[str, dict]) -> str:
    lines = ["| Arm | Out-file | Valid rows | Missing | Complete? |", "|---|---|---|---|---|"]
    for arm, s in arm_status.items():
        exists = "yes" if s["out_file_exists"] else "**missing**"
        complete = "yes" if s["complete"] else "**NO**"
        missing_note = f"{s['n_missing']}/{s['n_expected']}"
        if s["missing_ids"] and len(s["missing_ids"]) <= 8:
            missing_note += f" ({', '.join(s['missing_ids'])})"
        elif s["missing_ids"]:
            missing_note += f" ({', '.join(s['missing_ids'][:8])}, ...)"
        extra = []
        if s["n_malformed"]:
            extra.append(f"{s['n_malformed']} malformed line(s)")
        if s["n_invalid"]:
            extra.append(f"{s['n_invalid']} invalid row(s) (bad id/verdict)")
        extra_note = f" -- {'; '.join(extra)}" if extra else ""
        lines.append(f"| {arm} | {exists} | {s['n_valid']}/{s['n_expected']} | {missing_note}{extra_note} | {complete} |")
    return "\n".join(lines)


def render_resolution_table(rows: list[dict], show_v2: bool) -> str:
    if not rows:
        return "*None.*"
    rows = sorted(rows, key=lambda r: (r["arm"], r["id"]))
    if show_v2:
        lines = ["| Arm | Q | Jon | v1 Opus | v2 Opus |", "|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['arm']} | {r['id']} | {r['jon']} | {r['v1_opus']} | {r.get('v2_opus', '?')} |")
    else:
        lines = ["| Arm | Q | Jon | v1 Opus |", "|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['arm']} | {r['id']} | {r['jon']} | {r['v1_opus']} |")
    return "\n".join(lines)


def build_report(v1_results: list[dict], v2_results: list[dict], arm_status: dict[str, dict],
                 question_map) -> str:
    m1 = compute_metrics(v1_results)
    m2 = compute_metrics(v2_results)
    p1, s1, c1 = m1["primary"], m1["secondary"], m1["combined"]
    p2, s2, c2 = m2["primary"], m2["secondary"], m2["combined"]
    res = classify_resolution(v1_results, v2_results)

    n_complete = sum(1 for s in arm_status.values() if s["complete"])
    n_arms = len(arm_status)
    any_graded = m2["n_graded"] > 0

    lines: list[str] = []
    lines.append("# Opus-Grader Calibration Report -- v2")
    lines.append("")
    lines.append(
        "v2 changes EXACTLY ONE thing vs v1 (`evals/opus_grader_calibration.py` / "
        "`evals/opus_grader_report.md`): every card-interaction question's grading input "
        "now includes the same 'Card data' block (oracle text + selected rulings) the "
        "answering arm saw in its generation prompt. Rubric, blindness, and comparison-set "
        "logic are unchanged. Grading itself runs as in-session Opus SUBAGENTS on Jon's "
        "Claude subscription (not billed Anthropic API calls) -- this script only reads "
        "their JSONL output and computes metrics. Full method: "
        "`docs/plan-opus-grader-calibration.md`."
    )
    lines.append("")

    lines.append("## Grading completeness")
    lines.append("")
    lines.append(f"{n_complete}/{n_arms} arms fully graded ({m2['n_graded']} graded cells / "
                  f"{m2['n_total']} total comparison cells).")
    lines.append("")
    lines.append(render_arm_status(arm_status))
    lines.append("")
    if not any_graded:
        lines.append(
            "**No cells graded yet** -- `evals/opus_grader_v2_out/` has no (complete) "
            "per-arm JSONL files. Every metric below is `n/a` by design (graceful "
            "degradation, not a crash): this is the expected state right after the PREP "
            "stage, before any grading subagent has run. Re-run this script once grading "
            "output lands."
        )
        lines.append("")

    lines.append("## v2 headline")
    lines.append("")
    lines.append(f"- **Primary set** (Jon's direct hand-grades, N={p2['n']}): "
                  f"{frac_pct(p2['agree'], p2['n']) if p2['n'] else '0/0 (n/a -- not graded yet)'} agreement")
    lines.append(f"- **Secondary set** (auto-transferred-by-transitivity, N={s2['n']}): "
                  f"{frac_pct(s2['agree'], s2['n']) if s2['n'] else '0/0 (n/a -- not graded yet)'} agreement")
    lines.append(f"- **Combined** (N={c2['n']}): "
                  f"{frac_pct(c2['agree'], c2['n']) if c2['n'] else '0/0 (n/a -- not graded yet)'} agreement")
    lines.append(f"- **Correct/partial boundary agreement** (primary, N={p2['boundary_n']}): "
                  f"{frac_pct(p2['boundary_agree'], p2['boundary_n']) if p2['boundary_n'] else 'n/a'}"
                  f" -- {p2['boundary_correct_to_partial']} correct-to-partial flips, "
                  f"{p2['boundary_partial_to_correct']} partial-to-correct flips")
    lines.append(f"- **Reference yardstick:** the frozen gpt-5-mini judge earned trust at "
                  f"**{FROZEN_JUDGE_AGREEMENT_PCT}% agreement** with **{FROZEN_JUDGE_LIVE_AUDIT_ERRORS}** "
                  f"live-audit errors -- shown for comparison only, not an auto-adopt threshold.")
    lines.append(f"- **Coverage:** {m2['n_graded']} graded / {m2['n_errors']} not-yet-graded "
                  f"out of {m2['n_total']} total comparison cells (expect 300 = 6 arms x 50 "
                  "questions once every arm is complete).")
    lines.append("- **Cost:** n/a -- v2 grading runs as in-session Opus subagents on Jon's "
                  "subscription, not metered Anthropic API calls (docs/plan-opus-grader-"
                  "calibration.md v2 mechanics note).")
    lines.append("")

    lines.append("## v1 vs v2 side-by-side")
    lines.append("")
    lines.append("| | v1 (no card data) | v2 (+ card data) |")
    lines.append("|---|---|---|")
    lines.append(f"| Primary agreement (N v1={p1['n']}, N v2={p2['n']}) | "
                  f"{frac_pct(p1['agree'], p1['n'])} | "
                  f"{frac_pct(p2['agree'], p2['n']) if p2['n'] else 'n/a (not graded yet)'} |")
    lines.append(f"| Secondary agreement (N v1={s1['n']}, N v2={s2['n']}) | "
                  f"{frac_pct(s1['agree'], s1['n'])} | "
                  f"{frac_pct(s2['agree'], s2['n']) if s2['n'] else 'n/a (not graded yet)'} |")
    lines.append(f"| Combined agreement (N v1={c1['n']}, N v2={c2['n']}) | "
                  f"{frac_pct(c1['agree'], c1['n'])} | "
                  f"{frac_pct(c2['agree'], c2['n']) if c2['n'] else 'n/a (not graded yet)'} |")
    lines.append(f"| Correct/partial boundary (primary) (N v1={p1['boundary_n']}, N v2={p2['boundary_n']}) | "
                  f"{frac_pct(p1['boundary_agree'], p1['boundary_n']) if p1['boundary_n'] else 'n/a'} | "
                  f"{frac_pct(p2['boundary_agree'], p2['boundary_n']) if p2['boundary_n'] else 'n/a (not graded yet)'} |")
    lines.append("")

    lines.append("## Resolution of v1's disagreements")
    lines.append("")
    lines.append(f"v1 had {len(res['resolved']) + len(res['persisted']) + len(res['pending'])} "
                  "primary+secondary disagreements. Cross-referenced against the same "
                  f"(arm, id) cell in v2: **{len(res['resolved'])} resolved** (v2 now agrees "
                  f"with Jon), **{len(res['persisted'])} persisted** (v2 still disagrees), "
                  f"**{len(res['pending'])} pending** (that cell isn't graded in v2 yet). v2 "
                  f"also introduced **{len(res['new'])} new** disagreements on cells v1 had "
                  "agreed on.")
    lines.append("")
    lines.append("### Resolved (v1 wrong-vs-Jon -> v2 agrees)")
    lines.append("")
    lines.append(render_resolution_table(res["resolved"], show_v2=True))
    lines.append("")
    lines.append("### Persisted (still disagreeing in v2)")
    lines.append("")
    lines.append(render_resolution_table(res["persisted"], show_v2=True))
    lines.append("")
    lines.append("### Pending (not yet graded in v2)")
    lines.append("")
    lines.append(render_resolution_table(res["pending"], show_v2=False))
    lines.append("")
    lines.append("### New disagreements (v1 agreed, v2 doesn't)")
    lines.append("")
    lines.append(render_resolution_table(res["new"], show_v2=True))
    lines.append("")

    lines.append("## Confusion matrix -- v2 primary set (N=%d)" % p2["n"])
    lines.append("")
    lines.append(render_confusion(p2["confusion"]))
    lines.append("")
    lines.append("## Confusion matrix -- v2 secondary set (N=%d)" % s2["n"])
    lines.append("")
    lines.append(render_confusion(s2["confusion"]))
    lines.append("")

    lines.append("## Not-yet-graded / malformed cells")
    lines.append("")
    not_yet = [e for e in m2["errors"] if e["error"].startswith("not yet graded")]
    genuine = [e for e in m2["errors"] if not e["error"].startswith("not yet graded")]
    if not_yet:
        by_arm = Counter(e["arm"] for e in not_yet)
        lines.append(
            f"{len(not_yet)} cells with no grader output yet, across "
            f"{len(by_arm)} arm(s) -- see the Grading completeness table above for exactly "
            "which ids per arm; not re-listed here 1-by-1 to keep this report short."
        )
        lines.append("")
    lines.append("Genuine errors (malformed JSONL lines / invalid verdict values -- always "
                  "worth reading individually):")
    lines.append("")
    lines.append(render_errors(genuine))
    lines.append("")

    lines.append("## Full v2 disagreement list")
    lines.append("")
    lines.append("Primary set:")
    lines.append("")
    lines.append(render_disagreements(p2["disagreements"], question_map))
    lines.append("")
    lines.append("Secondary set:")
    lines.append("")
    lines.append(render_disagreements(s2["disagreements"], question_map))
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    print("Loading question map...", flush=True)
    question_map = build_question_map()

    print("Building comparison set (same logic as v1)...", flush=True)
    cells = build_comparison_set(question_map)
    print(f"  {len(cells)} cells total", flush=True)

    expected_by_arm: dict[str, set[str]] = {arm: set() for arm in ARM_ANSWER_FILES}
    for c in cells:
        expected_by_arm[c["arm"]].add(c["id"])

    print(f"Reading grader output from {OUT_DIR}...", flush=True)
    graded_by_key, arm_status = load_v2_out(expected_by_arm)
    for arm, s in arm_status.items():
        note = "complete" if s["complete"] else f"INCOMPLETE ({s['n_valid']}/{s['n_expected']} valid)"
        print(f"  {arm}: {note}", flush=True)

    v2_results = build_v2_results(cells, graded_by_key)
    V2_RESULTS_PATH.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in v2_results) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(v2_results)} rows -> {V2_RESULTS_PATH}", flush=True)

    if not V1_RESULTS_PATH.exists():
        print(f"[ERROR] v1 raw results not found at {V1_RESULTS_PATH} -- cannot build the "
              "v1-vs-v2 comparison. Report NOT written.")
        return
    v1_results = [json.loads(line) for line in V1_RESULTS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Loaded {len(v1_results)} v1 rows from {V1_RESULTS_PATH} (read-only reference)", flush=True)

    print("Building report...", flush=True)
    report_md = build_report(v1_results, v2_results, arm_status, question_map)
    V2_REPORT_PATH.write_text(report_md, encoding="utf-8")
    print(f"Wrote report to {V2_REPORT_PATH}", flush=True)

    n_graded = sum(1 for r in v2_results if "error" not in r)
    print(f"\n{n_graded}/{len(v2_results)} v2 cells graded "
          f"({sum(1 for s in arm_status.values() if s['complete'])}/{len(arm_status)} arms complete).")


if __name__ == "__main__":
    main()
