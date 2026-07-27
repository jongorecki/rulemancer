"""One-shot verification for the three v2/raw production-config prompt
caches (Jon, 2026-07-27). Prints a terse report matching the 7-point
verification list from the task brief. Read-only -- never Read a raw cache
file into an LLM context; this script does the heavy lifting on disk and
prints only the small aggregates.

Run: uv run python evals/verify_v2raw_caches.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

REPO = Path(__file__).parent.parent
ANSWERS = REPO / "evals" / "answers"

CACHE_A = ANSWERS / "_prompts_rules86_real_v2raw.json"
CACHE_B = ANSWERS / "_prompts_rules86_placebo_v2raw.json"
CACHE_C = ANSWERS / "_prompts_rulesguru_full_v2raw.json"

RULES86 = REPO / "evals" / "questions_rules86.jsonl"
RULESGURU = REPO / "evals" / "rulesguru_full_v2.jsonl"


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_ids(p: Path) -> set[str]:
    ids = set()
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(json.loads(line)["id"])
    return ids


def main() -> None:
    a = load_json(CACHE_A)
    b = load_json(CACHE_B)
    c = load_json(CACHE_C)

    print("=" * 70)
    print("1. STAMPED CONFIG")
    for name, d in [("A (rules86 real)", a), ("B (rules86 placebo)", b), ("C (rulesguru full)", c)]:
        print(f"  {name}: rewrite_version={d['rewrite_version']!r} ruling_query_mode={d['ruling_query_mode']!r}")

    print("\n2. ENTRY COUNTS / ID SETS")
    src86 = load_ids(RULES86)
    srcrg = load_ids(RULESGURU)
    a_ids = set(a["prompts"])
    b_ids = set(b["prompts"])
    c_ids = set(c["prompts"])
    print(f"  A: {len(a_ids)} entries (source rules86: {len(src86)}) | id-set match: {a_ids == src86}")
    print(f"  B: {len(b_ids)} entries (source rules86: {len(src86)}) | id-set match: {b_ids == src86}")
    print(f"  C: {len(c_ids)} entries (source rulesguru_full_v2: {len(srcrg)}) | id-set match: {c_ids == srcrg}")

    print("\n3. CACHE C -- CARD DATA BLOCK / RESOLUTION")
    n_cards = c.get("n_cards", {})
    unresolved = c.get("unresolved_refs", {})
    with_block = sum(1 for qid in c_ids if "\n\nCard data:\n" in c["prompts"][qid]["user"])
    zero_card_rows = sum(1 for qid in c_ids if n_cards.get(qid, 0) == 0)
    total_unresolved = sum(len(v) for v in unresolved.values())
    rows_with_unresolved = len(unresolved)
    print(f"  rows with 'Card data:' block present: {with_block}/{len(c_ids)}")
    print(f"  rows with 0 resolved cards: {zero_card_rows}/{len(c_ids)}")
    print(f"  rows with >=1 unresolved card ref: {rows_with_unresolved}")
    print(f"  total unresolved card refs: {total_unresolved}")
    if rows_with_unresolved:
        print("  [LOUD] unresolved refs detail:")
        for qid, refs in unresolved.items():
            print(f"    {qid}: {refs}")

    print("\n4. CACHE A/B -- CARD-FREE GUARD + DERANGEMENT")
    a_has_card_block = [qid for qid in a_ids if "\n\nCard data:\n" in a["prompts"][qid]["user"]]
    b_has_card_block = [qid for qid in b_ids if "\n\nCard data:\n" in b["prompts"][qid]["user"]]
    print(f"  A rows with Card data block (should be 0): {len(a_has_card_block)} {a_has_card_block[:5]}")
    print(f"  B rows with Card data block (should be 0): {len(b_has_card_block)} {b_has_card_block[:5]}")
    borrowed = b.get("borrowed_from", {})
    self_loops = [qid for qid, donor in borrowed.items() if donor == qid]
    is_bijection = sorted(borrowed.values()) == sorted(borrowed.keys())
    print(f"  derangement self-loops (should be 0): {len(self_loops)} {self_loops[:5]}")
    print(f"  derangement is a bijection over the row set: {is_bijection}")

    print("\n5. A vs B -- FIRST DIVERGENCE + BYTE-IDENTICAL TAIL (3 samples)")
    sample_ids = sorted(a_ids)[:3]
    for qid in sample_ids:
        ua = a["prompts"][qid]["user"]
        ub = b["prompts"][qid]["user"]
        n = min(len(ua), len(ub))
        div = next((i for i in range(n) if ua[i] != ub[i]), n)
        # Confirm everything AFTER the rules-context block (i.e. from
        # "\n\nQuestion:" onward) is byte-identical between real and placebo.
        marker = "\n\nQuestion:"
        ia = ua.find(marker)
        ib = ub.find(marker)
        tail_identical = (ia != -1 and ib != -1 and ua[ia:] == ub[ib:])
        print(f"  {qid}: first divergence at char {div} (len a={len(ua)} b={len(ub)}) | "
              f"tail-from-'Question:' byte-identical: {tail_identical}")

    print("\n6. CACHE C -- PROMPT LENGTH (system+user chars)")
    lens = [len(c["prompts"][qid]["system"]) + len(c["prompts"][qid]["user"]) for qid in c_ids]
    print(f"  mean: {sum(lens)/len(lens):.0f} chars | max: {max(lens)} chars | n={len(lens)}")

    print("\n7. VOYAGE CALL ACCOUNTING")
    print("  (see the individual build scripts' own stdout for live counters;")
    print("   this script only re-derives what's structurally verifiable from the cache files.)")
    print(f"  A+C together retrieved {sum(len(v) for v in a.get('retrieved_rule_ids', {}).values())} "
          f"+ {sum(len(v) for v in c.get('retrieved_rule_ids', {}).values())} chunk ids total "
          f"(not a call count -- see build script logs for actual embed_query call counts).")

    print("\n8. REWRITE PROOF -- sample rewritten queries (raw vs v2)")
    for qid in sample_ids[:2]:
        rq = a.get("rewritten_queries", {}).get(qid, [])
        print(f"  {qid} raw question vs rewrite(s):")
        print(f"    rewrites: {rq}")

    print("=" * 70)


if __name__ == "__main__":
    main()
