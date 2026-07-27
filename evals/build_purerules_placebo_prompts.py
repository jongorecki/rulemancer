"""Freeze the placebo prompt cache for the pure-rules probe (evals/purerules
.jsonl, 8 rows). Same construction as build_ab_placebo_prompts.py -- see that
file's docstring for the full rationale (rebuild via build_prompt() with a
donor's retrieved-chunk list rather than string-splicing, so only the "Rules
context:" block differs from the real cache, by construction). Scoped here
to the 8-row purerules set.

DERANGEMENT AT n=8 IS FRAGILE: with only 8 items a naive single shuffle has
a real chance of landing a fixed point, and 8! = 40320 is small enough that
"it'll basically always work" (true at n=120) is not a safe assumption to
carry over silently. derangement() below is unchanged from the ab-placebo
version -- rejection-sample a shuffle, retry up to 10,000 times, hard-fail
if none is found -- but the assertions after building the mapping matter
more at this size, not less, so they run unconditionally (never skipped)
and check the actual qid mapping, not just index arithmetic.

Zero API cost: no retrieval, no embedding, no model call -- every donor
context was already paid for (Voyage) by build_purerules_real_prompts.py;
this only rearranges already-fetched chunk text.

Run: uv run python evals/build_purerules_placebo_prompts.py
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.contracts import Retrieved  # noqa: E402
from rulesagent.generate.answer import build_prompt  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402
from rulesagent.tools.scryfall import parse_card_refs  # noqa: E402
from run_eval import CR_PATH  # noqa: E402
from build_ab_real_prompts import ordered_cards  # noqa: E402
from build_ab_placebo_prompts import derangement  # noqa: E402

REPO = Path(__file__).parent.parent
REAL_CACHE = REPO / "evals" / "answers" / "_prompts_purerules_real.json"
ROWS = REPO / "evals" / "purerules.jsonl"
OUT = REPO / "evals" / "answers" / "_prompts_purerules_placebo.json"

# Independent RNG draw from the ab-placebo cache's SEED=613 -- same seed
# convention (build_ab_rows.py), a different value so the two experiments'
# derangements aren't accidentally coupled.
SEED = 614


def main() -> None:
    real = json.loads(REAL_CACHE.read_text(encoding="utf-8"))
    real_prompts = real["prompts"]
    retrieved_ids = real["retrieved_rule_ids"]
    qids = sorted(real_prompts)  # fixed order for the derangement index

    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_map = {c.source_id: c for c in chunks}

    purerules_rows = {}
    for line in ROWS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            purerules_rows[row["id"]] = row["question"]

    if sorted(purerules_rows) != qids:
        raise SystemExit(
            f"[ERROR] purerules.jsonl ids {sorted(purerules_rows)} do not match "
            f"real-cache ids {qids} -- refusing to build a placebo against a "
            f"mismatched question set"
        )

    perm = derangement(len(qids), SEED)
    donor_of = {qids[i]: qids[perm[i]] for i in range(len(qids))}

    # Assert derangement holds over the actual qid mapping (not just index
    # arithmetic) before writing anything -- matters more at n=8, not less.
    self_loops = [qid for qid, donor in donor_of.items() if donor == qid]
    if self_loops:
        raise SystemExit(f"[ERROR] derangement has self-loop(s): {self_loops}")
    if sorted(donor_of.values()) != qids:
        raise SystemExit("[ERROR] donor mapping is not a bijection over the row set")
    if len(set(donor_of.values())) != len(qids):
        raise SystemExit("[ERROR] donor mapping is not injective (duplicate donors)")

    placebo_prompts: dict[str, dict] = {}
    for qid in qids:
        donor = donor_of[qid]
        stripped, refs = parse_card_refs(purerules_rows[qid])
        cards, missing = ordered_cards(purerules_rows[qid])
        if refs or cards or missing:
            raise SystemExit(
                f"[ERROR] {qid} has card token(s) {refs!r} -- purerules.jsonl "
                f"must have zero cards by construction"
            )
        donor_retrieved = [Retrieved(chunk=chunk_map[sid], score=1.0)
                            for sid in retrieved_ids[donor] if sid in chunk_map]
        sys_text, user_text = build_prompt(stripped, donor_retrieved, cards)
        placebo_prompts[qid] = {"system": sys_text, "user": user_text}

    # Sanity: the placebo's own rules block must never equal arm A's rules
    # block for the same row (that's what "no self-loop" is FOR) --
    # cross-checked here at the text level too, not just the id-mapping
    # level.
    identical_blocks = [
        qid for qid in qids
        if placebo_prompts[qid]["user"] == real_prompts[qid]["user"]
    ]
    if identical_blocks:
        raise SystemExit(f"[ERROR] placebo user text identical to real cache for: {identical_blocks}")

    out = {
        "derived_from": REAL_CACHE.name,
        "arm": "purerules_placebo",
        "rewrite_version": real["rewrite_version"],
        "ruling_query_mode": real["ruling_query_mode"],
        "vector_model": real["vector_model"],
        "top_k": real["top_k"],
        "n_questions": len(placebo_prompts),
        "borrowed_from": donor_of,
        "prompts": placebo_prompts,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.name}: {len(placebo_prompts)} prompts")
    print(f"derangement verified: 0 self-loops, bijection over {len(qids)} rows")
    print("borrowed_from mapping:")
    for qid in qids:
        print(f"  {qid} <- {donor_of[qid]}")


if __name__ == "__main__":
    main()
