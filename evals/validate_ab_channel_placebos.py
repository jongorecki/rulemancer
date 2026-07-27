"""Dry-run validator for the three card-channel placebo caches built by
evals/build_ab_placebo_channel_prompts.py -- proves each is correct WITHOUT
any model call, mirroring evals/validate_ab_harness.py's approach for the
original rules-placebo arm. Everything here reads already-built artifacts;
nothing embeds, retrieves, or generates.

Run: uv run python evals/validate_ab_channel_placebos.py
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "evals"))

REAL_CACHE = REPO / "evals" / "answers" / "_prompts_ab_real.json"
RULES_PLACEBO = REPO / "evals" / "answers" / "_prompts_ab_placebo.json"
RULINGS_CACHE = REPO / "evals" / "answers" / "_prompts_ab_placebo_rulings.json"
CARDDATA_CACHE = REPO / "evals" / "answers" / "_prompts_ab_placebo_carddata.json"
ALL_CACHE = REPO / "evals" / "answers" / "_prompts_ab_placebo_all.json"
AB_ROWS = REPO / "evals" / "ab_rows.jsonl"

from build_ab_placebo_channel_prompts import split_user, RULINGS_MARK  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_ids() -> set[str]:
    ids = set()
    for line in AB_ROWS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ids.add(json.loads(line)["id"])
    return ids


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def check_bijection_over_subset(borrowed_from: dict, subset: set[str], label: str) -> bool:
    entries = {qid: donor for qid, donor in borrowed_from.items() if donor is not None}
    self_loops = [qid for qid, donor in entries.items() if donor == qid]
    domain_ok = set(entries.keys()) == subset
    codomain_ok = sorted(entries.values()) == sorted(entries.keys())
    ok = not self_loops and domain_ok and codomain_ok
    print(f"{label}: {len(entries)} swapped rows, {len(borrowed_from) - len(entries)} unchanged "
          f"(null) rows | self-loops={len(self_loops)} | domain matches eligible subset="
          f"{domain_ok} | bijection={codomain_ok} -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_byte_identity(real_prompts: dict, cand_prompts: dict, label: str) -> bool:
    """Prefix/suffix around the Card data section must be byte-identical to
    arm A for every row -- the region-outside-the-swap guarantee."""
    sys_mismatch = [qid for qid in real_prompts
                     if real_prompts[qid]["system"] != cand_prompts[qid]["system"]]
    outside_mismatch = []
    for qid in real_prompts:
        r_pre, _r_body, r_suf = split_user(real_prompts[qid]["user"])
        c_pre, _c_body, c_suf = split_user(cand_prompts[qid]["user"])
        if r_pre != c_pre or r_suf != c_suf:
            outside_mismatch.append(qid)
    ok = not sys_mismatch and not outside_mismatch
    print(f"{label}: system mismatches={len(sys_mismatch)} (expect 0) | "
          f"prefix/suffix mismatches outside Card data={len(outside_mismatch)} (expect 0) "
          f"-> {'PASS' if ok else 'FAIL'}")
    if outside_mismatch[:5]:
        print(f"  first offenders: {outside_mismatch[:5]}")
    return ok


def check_byte_identity_vs_base(base_prompts: dict, cand_prompts: dict, label: str) -> bool:
    """Same as check_byte_identity but compares against a different base
    (arm B's rules-placebo text) for arm E, whose prefix is EXPECTED to
    differ from arm A's (rules swapped) but must match arm B's exactly."""
    outside_mismatch = []
    for qid in base_prompts:
        b_pre, _b_body, b_suf = split_user(base_prompts[qid]["user"])
        c_pre, _c_body, c_suf = split_user(cand_prompts[qid]["user"])
        if b_pre != c_pre or b_suf != c_suf:
            outside_mismatch.append(qid)
    ok = not outside_mismatch
    print(f"{label}: prefix/suffix mismatches vs arm B (rules half) ={len(outside_mismatch)} "
          f"(expect 0) -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_rulings_swap(real_prompts: dict, cand: dict) -> bool:
    """For every swapped row: card body changed, and specifically only the
    bullet lines after 'Rulings:' changed per card (heads identical)."""
    ok = True
    borrowed_from = cand["borrowed_from"]
    unchanged_when_expected = []
    changed_when_not_expected = []
    head_drift = []
    for qid, donor in borrowed_from.items():
        r_pre, r_body, r_suf = split_user(real_prompts[qid]["user"])
        c_pre, c_body, c_suf = split_user(cand["prompts"][qid]["user"])
        if donor is None:
            if r_body != c_body:
                changed_when_not_expected.append(qid)
            continue
        if r_body == c_body:
            unchanged_when_expected.append(qid)
            continue
        # per-card heads (everything up to "Rulings:\n") must be unchanged
        r_blocks = r_body.split("\n\n")
        c_blocks = c_body.split("\n\n")
        if len(r_blocks) != len(c_blocks):
            head_drift.append(qid)
            continue
        for rb, cb in zip(r_blocks, c_blocks):
            r_head = rb.partition(RULINGS_MARK)[0]
            c_head = cb.partition(RULINGS_MARK)[0]
            if r_head != c_head:
                head_drift.append(qid)
                break
    ok = not unchanged_when_expected and not changed_when_not_expected and not head_drift
    print(f"rows expected to swap but body unchanged: {len(unchanged_when_expected)} (expect 0)")
    print(f"rows NOT expected to swap but body changed: {len(changed_when_not_expected)} (expect 0)")
    print(f"rows with a per-card HEAD (header/oracle) drift: {len(head_drift)} (expect 0)")
    print(f"-> {'PASS' if ok else 'FAIL'}")
    return ok


def check_carddata_swap(real_prompts: dict, cand: dict, donor_source_prompts: dict) -> bool:
    """For every swapped row: the new body equals the DONOR's own real card
    body verbatim (whole-section, single-donor coherence)."""
    ok = True
    mismatches = []
    unchanged_when_expected = []
    changed_when_not_expected = []
    for qid, donor in cand["borrowed_from"].items():
        r_pre, r_body, r_suf = split_user(real_prompts[qid]["user"])
        c_pre, c_body, c_suf = split_user(cand["prompts"][qid]["user"])
        if donor is None:
            if r_body != c_body:
                changed_when_not_expected.append(qid)
            continue
        _d_pre, d_body, _d_suf = split_user(donor_source_prompts[donor]["user"])
        if c_body == r_body:
            unchanged_when_expected.append(qid)
        if c_body != d_body:
            mismatches.append(qid)
    ok = not mismatches and not unchanged_when_expected and not changed_when_not_expected
    print(f"rows whose new card body != donor's own real card body: {len(mismatches)} (expect 0)")
    print(f"rows expected to swap but unchanged: {len(unchanged_when_expected)} (expect 0)")
    print(f"rows NOT expected to swap but changed: {len(changed_when_not_expected)} (expect 0)")
    print(f"-> {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    ok = True
    ids = load_ids()
    real = load_json(REAL_CACHE)
    rules_placebo = load_json(RULES_PLACEBO)
    rulings = load_json(RULINGS_CACHE)
    carddata = load_json(CARDDATA_CACHE)
    allc = load_json(ALL_CACHE)

    section("1. All three caches cover the same 120 ids, metadata compatible with run_answer_eval.py")
    for name, cache in (("rulings", rulings), ("carddata", carddata), ("all", allc)):
        ids_ok = set(cache["prompts"]) == ids
        meta_ok = (cache["rewrite_version"] == real["rewrite_version"]
                   and cache["ruling_query_mode"] == real["ruling_query_mode"])
        print(f"{name}: {cache['n_questions']} prompts | ids match ab_rows.jsonl: {ids_ok} | "
              f"rewrite_version/ruling_query_mode match real cache (the only fields "
              f"run_answer_eval.py's --prompts-cache guard checks): {meta_ok} "
              f"-> {'PASS' if ids_ok and meta_ok else 'FAIL'}")
        ok &= ids_ok and meta_ok

    section("2. Derangement (rulings cache) -- over the 117 rows with >=1 ruling")
    eligible_rulings = {qid for qid in ids if rulings["borrowed_from"][qid] is not None}
    ok &= check_bijection_over_subset(rulings["borrowed_from"], eligible_rulings, "rulings")
    print(f"unchanged (no rulings anywhere to swap): "
          f"{sorted(qid for qid in ids if rulings['borrowed_from'][qid] is None)}")

    section("3. Derangement (carddata cache) -- over the 119 rows with card data")
    eligible_cards = {qid for qid in ids if carddata["borrowed_from"][qid] is not None}
    ok &= check_bijection_over_subset(carddata["borrowed_from"], eligible_cards, "carddata")
    print(f"unchanged (no card data at all): "
          f"{sorted(qid for qid in ids if carddata['borrowed_from'][qid] is None)}")

    section("4. Arm E (all) reuses arm B's rules mapping and arm D's card mapping exactly")
    rules_match = allc["borrowed_from"]["rules"] == rules_placebo["borrowed_from"]
    card_match = allc["borrowed_from"]["carddata"] == carddata["borrowed_from"]
    print(f"rules half identical to _prompts_ab_placebo.json's borrowed_from: {rules_match}")
    print(f"card half identical to _prompts_ab_placebo_carddata.json's borrowed_from: {card_match}")
    reuse_ok = rules_match and card_match
    print(f"-> {'PASS' if reuse_ok else 'FAIL'}")
    ok &= reuse_ok

    section("5. Byte-identity outside the swapped region -- rulings cache (vs arm A)")
    ok &= check_byte_identity(real["prompts"], rulings["prompts"], "rulings")

    section("6. Byte-identity outside the swapped region -- carddata cache (vs arm A)")
    ok &= check_byte_identity(real["prompts"], carddata["prompts"], "carddata")

    section("7. Byte-identity outside the swapped region -- all cache (rules half vs arm A, card half vs arm B)")
    sys_mismatch = [qid for qid in real["prompts"]
                     if rules_placebo["prompts"][qid]["system"] != allc["prompts"][qid]["system"]]
    print(f"system mismatches vs arm B: {len(sys_mismatch)} (expect 0)")
    ok &= not sys_mismatch
    ok &= check_byte_identity_vs_base(rules_placebo["prompts"], allc["prompts"], "all")

    section("8. Rulings-only swap: bodies changed, per-card heads (header+oracle) unchanged")
    ok &= check_rulings_swap(real["prompts"], rulings)

    section("9. Card-data swap coherence: new body == donor's own real body verbatim (carddata cache)")
    ok &= check_carddata_swap(real["prompts"], carddata, real["prompts"])

    section("10. Card-data swap coherence for arm E (vs arm A's real card bodies, same donor map as arm D)")
    ok &= check_carddata_swap(real["prompts"], {"borrowed_from": allc["borrowed_from"]["carddata"],
                                                 "prompts": allc["prompts"]}, real["prompts"])

    section("11. One concrete diff per cache")
    sample_qid = sorted(rulings["prompts"])[0]
    for name, cache, base_prompts in (
        ("rulings", rulings, real["prompts"]),
        ("carddata", carddata, real["prompts"]),
        ("all", allc, rules_placebo["prompts"]),
    ):
        qid = sample_qid
        donor = (cache["borrowed_from"]["carddata"][qid]
                 if name == "all" else cache["borrowed_from"][qid])
        b_pre, b_body, b_suf = split_user(base_prompts[qid]["user"])
        c_pre, c_body, c_suf = split_user(cache["prompts"][qid]["user"])
        print(f"-- {name} (qid={qid}, borrowed_from={donor}) --")
        print(f"  prefix identical: {b_pre == c_pre}")
        print(f"  suffix identical: {b_suf == c_suf} ({len(b_suf)} chars)")
        print(f"  body before (first 160): {(b_body or '')[:160]!r}")
        print(f"  body after  (first 160): {(c_body or '')[:160]!r}")

    section("VERDICT")
    print("ALL CHECKS PASS -- three channel-placebo caches validated with zero model calls" if ok
          else "SOME CHECKS FAILED -- see sections above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
