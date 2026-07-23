"""Retrieval-noise caveat (task-3 brief, do this first -- it's cheap and
shapes everything downstream).

Retrieval embedding is nondeterministic; condition A's prompts were never
captured so A's retrieval draw is unknowable. What IS knowable: for each
question, diff the RULES-context portion (excludes card rulings) of the
user prompt across the three captured conditions B/C/D.

  B: rewrite v1, ruling raw     C: rewrite v2, ruling raw
  D: rewrite v2, ruling union (Part B; only changes ruling SELECTION)

Classification per question:
  identical              -- rules ids match across B, C, and D
  expected_rewriter_diff -- C == D (same rewriter, so rules retrieval
                             should agree); B differs from them, which is
                             explained by the v1->v2 rewriter change (§2a/2b)
  retrieval_noise_suspect -- C != D on the RULES section. C and D share the
                             same rewriter (v2) and differ ONLY in
                             ruling_query_mode, which by design only touches
                             ruling selection (Card data section), not rules
                             retrieval. A rules-context diff here has no
                             intended-change explanation -- it's the
                             embedding draw varying between captures.

Card-data (ruling) ids are also diffed and reported, but never drive the
tag -- Part B union is EXPECTED to change ruling selection C-vs-D.

Output: evals/retrieval_noise_tags.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lib_v3ab as L  # noqa: E402

OUT = Path(__file__).parent / "retrieval_noise_tags.json"


def classify(qid: str) -> dict:
    rules_b = L.rules_section_ids("B", qid)
    rules_c = L.rules_section_ids("C", qid)
    rules_d = L.rules_section_ids("D", qid)
    cards_b = L.card_section_ids("B", qid)
    cards_c = L.card_section_ids("C", qid)
    cards_d = L.card_section_ids("D", qid)

    if rules_b == rules_c == rules_d:
        tag = "identical"
    elif rules_c != rules_d:
        tag = "retrieval_noise_suspect"
    elif rules_b != rules_c:
        tag = "expected_rewriter_diff"
    else:
        tag = "identical"  # unreachable given the branches above, kept for safety

    return {
        "id": qid,
        "tag": tag,
        "rules_b_only": sorted(rules_b - rules_c - rules_d),
        "rules_c_only": sorted(rules_c - rules_b - rules_d),
        "rules_d_only": sorted(rules_d - rules_b - rules_c),
        "rules_b_eq_c": rules_b == rules_c,
        "rules_c_eq_d": rules_c == rules_d,
        "cards_c_eq_d": cards_c == cards_d,
        "cards_b_eq_c": cards_b == cards_c,
    }


def main() -> None:
    rows = [classify(qid) for qid in L.ALL_QIDS]
    counts = {}
    for r in rows:
        counts[r["tag"]] = counts.get(r["tag"], 0) + 1
    OUT.write_text(json.dumps({"rows": rows, "counts": counts}, indent=2), encoding="utf-8")
    print(f"retrieval-noise tags: {counts} -> {OUT}")
    suspects = [r["id"] for r in rows if r["tag"] == "retrieval_noise_suspect"]
    print(f"  retrieval_noise_suspect ({len(suspects)}): {suspects}")


if __name__ == "__main__":
    main()
