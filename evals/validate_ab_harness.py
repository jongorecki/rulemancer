"""Dry-run validator for the retrieval-value A/B harness
(docs/spec-retrieval-value-ab.md) -- proves the harness is correct WITHOUT
any model call. Everything here reads already-built artifacts
(evals/ab_rows.jsonl, evals/answers/_prompts_ab_real.json, evals/answers/
_prompts_ab_placebo.json) and evals/purerules.jsonl; nothing embeds,
retrieves, or generates.

Run: uv run python evals/validate_ab_harness.py
"""

import json
import random
from pathlib import Path

REPO = Path(__file__).parent.parent
AB_ROWS = REPO / "evals" / "ab_rows.jsonl"
REAL_CACHE = REPO / "evals" / "answers" / "_prompts_ab_real.json"
PLACEBO_CACHE = REPO / "evals" / "answers" / "_prompts_ab_placebo.json"
PURERULES = REPO / "evals" / "purerules.jsonl"
SOURCE = REPO / "evals" / "rulesguru_full_v2.jsonl"

RULES_HDR = "Rules context:\n"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def split_rules_block(user: str) -> tuple[str, str, str]:
    rest = user[len(RULES_HDR):]
    markers = [m for m in ("\n\nCard data:\n", "\n\nSymbol reference", "\n\nQuestion:") if m in rest]
    cut = min(rest.index(m) for m in markers)
    return RULES_HDR, rest[:cut], rest[cut:]


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> int:
    ok = True

    # -------------------------------------------------------------- rows --
    section("1. Row selection")
    rows = load_jsonl(AB_ROWS)
    counts = {lvl: sum(1 for r in rows if r["level"] == lvl) for lvl in ("2", "3", "Corner Case")}
    print(f"total rows: {len(rows)}")
    print(f"level split: {counts}")
    level_ok = len(rows) == 120 and counts == {"2": 40, "3": 40, "Corner Case": 40}
    print(f"-> {'PASS' if level_ok else 'FAIL'}")
    ok &= level_ok

    gold_ok = all(r.get("gold") for r in rows)
    print(f"all rows gold-bearing: {'PASS' if gold_ok else 'FAIL'}")
    ok &= gold_ok

    # ------------------------------------------------------- purerules ----
    section("2. Purerules exclusion")
    held_out = {r["source_qid"] for r in load_jsonl(PURERULES)}
    drawn_ids = {r["id"] for r in rows}
    intersection = drawn_ids & held_out
    print(f"purerules held-out source_qids: {sorted(held_out)}")
    print(f"intersection with drawn rows: {sorted(intersection) or 'none'}")
    excl_ok = not intersection
    print(f"-> {'PASS' if excl_ok else 'FAIL'}")
    ok &= excl_ok

    # ----------------------------------------------------- reproducibility -
    section("3. Seed reproducibility")
    import sys
    sys.path.insert(0, str(REPO / "evals"))
    from build_ab_rows import draw_rows, SEED

    source_rows = load_jsonl(SOURCE)
    redrawn = draw_rows(source_rows, held_out)
    redrawn_ids = sorted(r["id"] for r in redrawn)
    frozen_ids = sorted(drawn_ids)
    repro_ok = redrawn_ids == frozen_ids
    print(f"seed: {SEED}")
    print(f"redraw reproduces frozen file: {'PASS' if repro_ok else 'FAIL'}")
    ok &= repro_ok

    # -------------------------------------------------------- load_questions
    section("4. Loads unmodified through run_eval.load_questions()")
    from run_eval import load_questions
    questions = load_questions(AB_ROWS)
    load_ok = len(questions) == 120
    print(f"loaded {len(questions)} EvalQuestion objects -> {'PASS' if load_ok else 'FAIL'}")
    ok &= load_ok

    # ------------------------------------------------------------ caches --
    section("5. Prompt caches")
    real = load_json(REAL_CACHE)
    placebo = load_json(PLACEBO_CACHE)
    print(f"real cache:    {REAL_CACHE.name} | {real['n_questions']} prompts | "
          f"rewrite_version={real['rewrite_version']!r} ruling_query_mode={real['ruling_query_mode']!r}")
    print(f"placebo cache: {PLACEBO_CACHE.name} | {placebo['n_questions']} prompts | "
          f"rewrite_version={placebo['rewrite_version']!r} ruling_query_mode={placebo['ruling_query_mode']!r}")
    cache_ok = (set(real["prompts"]) == drawn_ids == set(placebo["prompts"])
                and real["rewrite_version"] == placebo["rewrite_version"]
                and real["ruling_query_mode"] == placebo["ruling_query_mode"])
    print(f"-> {'PASS' if cache_ok else 'FAIL'}")
    ok &= cache_ok

    # ------------------------------------------------------- derangement --
    section("6. Derangement")
    borrowed_from = placebo["borrowed_from"]
    self_loops = [qid for qid, donor in borrowed_from.items() if donor == qid]
    bijection_ok = sorted(borrowed_from.values()) == sorted(borrowed_from.keys())
    der_ok = not self_loops and bijection_ok
    print(f"self-loops: {len(self_loops)} (expect 0)")
    print(f"bijection over row set: {'yes' if bijection_ok else 'no'}")
    print(f"-> {'PASS' if der_ok else 'FAIL'}")
    print("sample borrowed_from mapping (first 8, alphabetical by qid):")
    for qid in sorted(borrowed_from)[:8]:
        print(f"  {qid} <- {borrowed_from[qid]}")
    ok &= der_ok

    # --------------------------------------------------- byte-identity ----
    section("7. Real vs placebo differ ONLY in the rules block")
    sys_mismatch = [qid for qid in real["prompts"]
                     if real["prompts"][qid]["system"] != placebo["prompts"][qid]["system"]]
    user_diffs = []
    for qid in real["prompts"]:
        r_pre, r_body, r_suf = split_rules_block(real["prompts"][qid]["user"])
        p_pre, p_body, p_suf = split_rules_block(placebo["prompts"][qid]["user"])
        if r_pre != p_pre or r_suf != p_suf:
            user_diffs.append(qid)
    same_body = [qid for qid in real["prompts"]
                 if split_rules_block(real["prompts"][qid]["user"])[1]
                 == split_rules_block(placebo["prompts"][qid]["user"])[1]]
    print(f"system prompt mismatches: {len(sys_mismatch)} (expect 0)")
    print(f"user prompt mismatches OUTSIDE the rules block: {len(user_diffs)} (expect 0)")
    print(f"rows where the rules block body is UNCHANGED (derangement failure): "
          f"{len(same_body)} (expect 0)")
    identity_ok = not sys_mismatch and not user_diffs and not same_body
    print(f"-> {'PASS' if identity_ok else 'FAIL'}")
    ok &= identity_ok

    # ------------------------------------------------- one concrete diff --
    section("8. One concrete diff (rg1015 or first available qid)")
    sample_qid = "rg1015" if "rg1015" in real["prompts"] else sorted(real["prompts"])[0]
    r_user = real["prompts"][sample_qid]["user"]
    p_user = placebo["prompts"][sample_qid]["user"]
    r_pre, r_body, r_suf = split_rules_block(r_user)
    p_pre, p_body, p_suf = split_rules_block(p_user)
    print(f"qid: {sample_qid}  (placebo borrowed from: {borrowed_from[sample_qid]})")
    print(f"prefix identical:  {r_pre == p_pre}")
    print(f"suffix identical:  {r_suf == p_suf}  ({len(r_suf)} chars)")
    print(f"rules block A (first 200 chars):\n  {r_body[:200]!r}")
    print(f"rules block B (first 200 chars):\n  {p_body[:200]!r}")

    # ------------------------------------------------------- pilot cmds ---
    section("9. Pilot commands (15 rows: 5 per level, via --qids)")
    by_level: dict[str, list[str]] = {"2": [], "3": [], "Corner Case": []}
    for r in sorted(rows, key=lambda r: r["id"]):
        by_level[r["level"]].append(r["id"])
    rng = random.Random(613)
    pilot_ids: list[str] = []
    for lvl in ("2", "3", "Corner Case"):
        pilot_ids.extend(sorted(rng.sample(by_level[lvl], 5)))
    qids_arg = ",".join(pilot_ids)
    print(f"pilot qids ({len(pilot_ids)}): {qids_arg}")

    real_rel = "evals/answers/_prompts_ab_real.json"
    placebo_rel = "evals/answers/_prompts_ab_placebo.json"
    rows_rel = "evals/ab_rows.jsonl"
    out_dir = "evals/answers/ab_pilot"

    cmds = f"""
Arm A (real):
  .venv/Scripts/python.exe evals/run_answer_eval.py --questions {rows_rel} \\
    --qids {qids_arg} --prompts-cache {real_rel} \\
    --rewrite-version none --system-version 3 --effort low --layers-tool \\
    --condition A --out {out_dir}/A_real.json

Arm B (placebo):
  .venv/Scripts/python.exe evals/run_answer_eval.py --questions {rows_rel} \\
    --qids {qids_arg} --prompts-cache {placebo_rel} \\
    --rewrite-version none --system-version 3 --effort low --layers-tool \\
    --condition B --out {out_dir}/B_placebo.json

Arm C (layers off):
  .venv/Scripts/python.exe evals/run_answer_eval.py --questions {rows_rel} \\
    --qids {qids_arg} --prompts-cache {real_rel} \\
    --rewrite-version none --system-version 3 --effort low --no-layers-tool \\
    --condition C --out {out_dir}/C_layersoff.json

Arm D (effort high):
  .venv/Scripts/python.exe evals/run_answer_eval.py --questions {rows_rel} \\
    --qids {qids_arg} --prompts-cache {real_rel} \\
    --rewrite-version none --system-version 3 --effort high --layers-tool \\
    --condition D --out {out_dir}/D_efforthigh.json
"""
    print(cmds)
    print("NOTE (see harness report): --no-layers-tool / --layers-tool has NO effect on the "
          "actual request when --prompts-cache is used -- run_answer_eval.py's "
          "_answer_from_frozen_prompt() never attaches tools, so arm A and arm C will "
          "generate byte-identical requests despite the flag. Recorded per-row for "
          "provenance/coverage scoring only. Flagged plainly, not silently worked around.")

    section("VERDICT")
    print("ALL CHECKS PASS -- harness validated with zero model calls" if ok
          else "SOME CHECKS FAILED -- see sections above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
