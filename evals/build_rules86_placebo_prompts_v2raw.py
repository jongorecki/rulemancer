"""Freeze the placebo arm's prompts for the 86-row card-free rules probe at
PRODUCTION config (rewrite_version="v2", ruling_query_mode="raw" -- moot for
rulings specifically since this set has zero cards, but the retrieval query
that produced each row's real "Rules context:" block came from the real v2
rewrite, so the donor swap below is swapping REAL v2-retrieved rules blocks,
not none/raw ones). Jon, 2026-07-27. Companion to build_rules86_real_prompts_
v2raw.py; same method as the original build_rules86_placebo_prompts.py --
see that file's docstring for the full DERANGEMENT rationale (SEED=613,
donor(i) != i, rejection-sampled proper derangement over the 86 rows).

WHAT'S DIFFERENT FROM THE ORIGINAL: it reads _prompts_rules86_real_v2raw.json
(not the none/union cache) and reconstructs each placebo row's user text with
build_prompt(stripped_question, donor_retrieved, cards=[], system_override=
SYSTEM_VERSIONS[PROMPT_VERSION]) -- the exact call shape RulesAgent.answer()
itself uses (see src/rulesagent/generate/answer.py, the build_prompt() call
site). cards=[] is correct for every row here (the real cache's own n_cards
would be 0 for all 86 -- this set is card-free by construction, already
guarded when the real cache was built).

SAFETY CROSS-CHECK: build_prompt()'s `system` output does not depend on
`retrieved` at all -- only on system_override/convo_ctx, both identical
between the real and placebo call for a given row. So the placebo's own
computed system string MUST equal the real cache's stored system string for
every row; asserted below, hard failure if it doesn't (would mean this
script's system_override/convo_ctx don't actually match what produced the
real cache).

Zero API cost: no retrieval, no embedding, no model call -- every donor
context was already computed and paid for by build_rules86_real_prompts_
v2raw.py; this only rearranges already-fetched chunk text via a pure
function.

Run: uv run python evals/build_rules86_placebo_prompts_v2raw.py
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.contracts import Retrieved  # noqa: E402
from rulesagent.generate.answer import PROMPT_VERSION, SYSTEM_VERSIONS, build_prompt  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402
from rulesagent.tools.scryfall import parse_card_refs  # noqa: E402
from run_eval import CR_PATH  # noqa: E402

REPO = Path(__file__).parent.parent
REAL_CACHE = REPO / "evals" / "answers" / "_prompts_rules86_real_v2raw.json"
OUT = REPO / "evals" / "answers" / "_prompts_rules86_placebo_v2raw.json"

SEED = 613  # same seed convention as build_rules86_placebo_prompts.py -- independent RNG draw


def derangement(n: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    idx = list(range(n))
    for _ in range(10_000):
        rng.shuffle(idx)
        if all(idx[i] != i for i in range(n)):
            return idx
    raise SystemExit(f"[ERROR] could not find a derangement of {n} elements in 10000 tries")


def main() -> None:
    real = json.loads(REAL_CACHE.read_text(encoding="utf-8"))
    if real["rewrite_version"] != "v2" or real["ruling_query_mode"] != "raw":
        raise SystemExit(
            f"[ERROR] {REAL_CACHE} is not v2/raw (got rewrite_version="
            f"{real['rewrite_version']!r}, ruling_query_mode={real['ruling_query_mode']!r}) "
            f"-- rebuild it with build_rules86_real_prompts_v2raw.py first"
        )
    real_prompts = real["prompts"]
    retrieved_ids = real["retrieved_rule_ids"]
    qids = sorted(real_prompts)

    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_map = {c.source_id: c for c in chunks}

    rows_by_id = {}
    with open(REPO / "evals" / "questions_rules86.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                rows_by_id[row["id"]] = row["question"]

    perm = derangement(len(qids), SEED)
    donor_of = {qids[i]: qids[perm[i]] for i in range(len(qids))}

    self_loops = [qid for qid, donor in donor_of.items() if donor == qid]
    if self_loops:
        raise SystemExit(f"[ERROR] derangement has self-loop(s): {self_loops}")
    if sorted(donor_of.values()) != qids:
        raise SystemExit("[ERROR] donor mapping is not a bijection over the row set")

    system_override = SYSTEM_VERSIONS[PROMPT_VERSION]

    placebo_prompts: dict[str, dict] = {}
    for qid in qids:
        donor = donor_of[qid]
        stripped, _refs = parse_card_refs(rows_by_id[qid])
        donor_retrieved = [Retrieved(chunk=chunk_map[sid], score=1.0)
                            for sid in retrieved_ids[donor] if sid in chunk_map]
        sys_text, user_text = build_prompt(
            stripped, donor_retrieved, [],  # cards=[] -- card-free set
            system_override=system_override,
        )
        if sys_text != real_prompts[qid]["system"]:
            raise SystemExit(
                f"[ERROR] {qid}: placebo system text != real cache's stored system text -- "
                f"build_prompt() call shape here doesn't match what produced the real cache"
            )
        placebo_prompts[qid] = {"system": sys_text, "user": user_text}

    identical_blocks = [
        qid for qid in qids
        if placebo_prompts[qid]["user"] == real_prompts[qid]["user"]
    ]
    if identical_blocks:
        raise SystemExit(f"[ERROR] placebo user text identical to real arm for: {identical_blocks}")

    out = {
        "derived_from": REAL_CACHE.name,
        "arm": "rules86_placebo_v2raw",
        "rewrite_version": real["rewrite_version"],
        "ruling_query_mode": real["ruling_query_mode"],
        "vector_model": real["vector_model"],
        "n_questions": len(placebo_prompts),
        "borrowed_from": donor_of,
        "prompts": placebo_prompts,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.name}: {len(placebo_prompts)} prompts")
    print(f"derangement verified: 0 self-loops, bijection over {len(qids)} rows")
    print("system-text cross-check: passed for all rows (placebo system == real system, per row)")
    print("sample borrowed_from mapping:")
    for qid in qids[:5]:
        print(f"  {qid} <- {donor_of[qid]}")


if __name__ == "__main__":
    main()
