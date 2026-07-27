"""Freeze arm B's (placebo) prompts for the retrieval-value A/B
(docs/spec-retrieval-value-ab.md, "Design: the placebo arm"). Reads the arm A
real-prompt cache (evals/answers/_prompts_ab_real.json, built by
build_ab_real_prompts.py) and, for every row, swaps in the rules block that
was retrieved for a DIFFERENT question in the same 120-row set -- everything
else (system, cards, symbol block, the question itself) stays byte-identical
to arm A.

HOW: rather than string-splicing the frozen `user` text (fragile against any
future change to build_prompt()'s layout), this rebuilds each placebo row by
calling the SAME build_prompt() with the SAME (stripped question, cards) as
arm A but the DONOR's retrieved chunk list in rank order (chunk ids ->
Chunk objects via chunk_map, score is irrelevant to _format_context()).
Since build_prompt() only ever reads `retrieved` to produce the "Rules
context:" block -- cards/symbol-block/question are untouched by it -- this
guarantees the user text differs from arm A's in exactly that one region,
by construction, not by inspection after the fact.

DERANGEMENT: donor(i) != i for every row, and donor() is a bijection over
the 120 rows (a proper derangement, not just "no self-loops") -- built by
shuffling the row order with a fixed seed until no row lands on its own
index (rejection sampling; a 120-element derangement is found almost
immediately in practice). Recorded per row (`borrowed_from`) so the mapping
is auditable.

Zero API cost: no retrieval, no embedding, no model call. Every donor
context was already computed (and paid for, in Voyage terms) by
build_ab_real_prompts.py; this script only rearranges already-fetched chunk
text.

Run: uv run python evals/build_ab_placebo_prompts.py
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

REPO = Path(__file__).parent.parent
REAL_CACHE = REPO / "evals" / "answers" / "_prompts_ab_real.json"
OUT = REPO / "evals" / "answers" / "_prompts_ab_placebo.json"

SEED = 613  # same seed convention as build_ab_rows.py; independent RNG draw


def derangement(n: int, seed: int) -> list[int]:
    """A random permutation of range(n) with no fixed point, via rejection
    sampling on a shuffle -- reproducible under `seed`. Raises if it somehow
    fails to find one in a generous number of tries (should never happen for
    n=120; the expected number of shuffles until a derangement is ~e)."""
    rng = random.Random(seed)
    idx = list(range(n))
    for _ in range(10_000):
        rng.shuffle(idx)
        if all(idx[i] != i for i in range(n)):
            return idx
    raise SystemExit(f"[ERROR] could not find a derangement of {n} elements in 10000 tries")


def main() -> None:
    real = json.loads(REAL_CACHE.read_text(encoding="utf-8"))
    real_prompts = real["prompts"]
    retrieved_ids = real["retrieved_rule_ids"]
    qids = sorted(real_prompts)  # fixed order for the derangement index

    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_map = {c.source_id: c for c in chunks}

    # Need each row's stripped question text (build_prompt's `question` arg
    # is the STRIPPED form -- confirmed against build_ab_real_prompts.py,
    # which passes `stripped` not q.question) and its cards, same derivation
    # as arm A so cards/symbol-block/question match byte-for-byte.
    ab_rows = {}
    for line in (REPO / "evals" / "ab_rows.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            ab_rows[row["id"]] = row["question"]

    perm = derangement(len(qids), SEED)
    donor_of = {qids[i]: qids[perm[i]] for i in range(len(qids))}

    # Assert derangement holds over the actual qid mapping (not just index
    # arithmetic) before writing anything.
    self_loops = [qid for qid, donor in donor_of.items() if donor == qid]
    if self_loops:
        raise SystemExit(f"[ERROR] derangement has self-loop(s): {self_loops}")
    if sorted(donor_of.values()) != qids:
        raise SystemExit("[ERROR] donor mapping is not a bijection over the row set")

    placebo_prompts: dict[str, dict] = {}
    for qid in qids:
        donor = donor_of[qid]
        stripped, _refs = parse_card_refs(ab_rows[qid])
        cards, _missing = ordered_cards(ab_rows[qid])
        donor_retrieved = [Retrieved(chunk=chunk_map[sid], score=1.0)
                            for sid in retrieved_ids[donor] if sid in chunk_map]
        sys_text, user_text = build_prompt(stripped, donor_retrieved, cards)
        placebo_prompts[qid] = {"system": sys_text, "user": user_text}

    # Sanity: the placebo's own rules block must never equal arm A's rules
    # block for the same row (that's what "no self-loop" is FOR) --
    # cross-checked here at the text level too, not just the id-mapping
    # level, so a chunk_map/versioning drift between the two runs can't
    # silently produce an identical block despite a "different" donor id.
    identical_blocks = [
        qid for qid in qids
        if placebo_prompts[qid]["user"] == real_prompts[qid]["user"]
    ]
    if identical_blocks:
        raise SystemExit(f"[ERROR] placebo user text identical to arm A for: {identical_blocks}")

    out = {
        "derived_from": REAL_CACHE.name,
        "arm": "B_placebo",
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
    print("sample borrowed_from mapping:")
    for qid in qids[:5]:
        print(f"  {qid} <- {donor_of[qid]}")


if __name__ == "__main__":
    main()
