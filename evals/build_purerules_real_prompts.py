"""Freeze the real-retrieval prompt cache for the pure-rules probe
(evals/purerules.jsonl, 8 rows). Same script as build_ab_real_prompts.py,
scoped to a different question set -- see that file's docstring for the full
rationale on --rewrite-version none / --ruling-query-mode union / zero
Anthropic calls; none of that changes here, only ROWS/OUT and one extra
guard.

WHY THIS SET EXISTS: docs/results-channel-ablation.md found CR-rule
retrieval near-inert on the 120-row A/B set, but that set is 99.4%
card-interaction questions -- scrambling the rules there may just mean "the
card text already carries the answer, so the rules are redundant." These 8
rows are real corpus questions rewritten so NO card name appears anywhere
(behaviour described in the abstract instead) -- the CR rules are the ONLY
information channel available. If rules matter here, that's evidence for
"redundant given cards" over "inert," which the 120-row set alone can't
distinguish.

ZERO-CARDS GUARD: parse_card_refs() finds `[Card Name]` bracket tokens: a
question with none returns (question, []) unchanged (see its docstring).
Since these 8 rows are constructed to have no bracket tokens, ordered_cards()
must return (cards=[], missing=[]) for every row -- asserted below, hard
failure if violated, since a stray card token would break the whole point of
this probe (CR rules ceasing to be the only channel).

Run: uv run python evals/build_purerules_real_prompts.py
"""

import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.cache import KVCache  # noqa: E402
from rulesagent.generate.answer import TOP_K, build_prompt  # noqa: E402
from rulesagent.index.embed import embed_query  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.tools.scryfall import parse_card_refs  # noqa: E402
from run_eval import PARSED_DIR, VECTOR_MODEL, load_questions  # noqa: E402
from build_ab_real_prompts import ordered_cards  # noqa: E402

REPO = Path(__file__).parent.parent
ROWS = REPO / "evals" / "purerules.jsonl"
OUT = REPO / "evals" / "answers" / "_prompts_purerules_real.json"


def main() -> None:
    questions = load_questions(ROWS)
    vstore = VectorStore.load(PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl")
    qemb = KVCache("query_emb")

    prompts: dict[str, dict] = {}
    retrieved_rule_ids: dict[str, list[str]] = {}
    n_new_embeds = 0

    for q in questions:
        stripped, refs = parse_card_refs(q.question)
        cards, missing = ordered_cards(q.question)
        # Zero-cards-by-construction guard -- fail loudly, not a warning,
        # since a card token here would silently reintroduce the channel
        # this probe exists to exclude.
        if refs or cards or missing:
            raise SystemExit(
                f"[ERROR] {q.id} has card token(s) {refs!r} -- purerules.jsonl "
                f"must have zero cards by construction, refusing to build a "
                f"cache that would confound the probe"
            )

        raw = qemb.get(stripped)
        if raw is None:
            vec = embed_query(stripped, VECTOR_MODEL)  # Voyage call -- not Anthropic
            qemb.put(stripped, pickle.dumps(vec))
            n_new_embeds += 1
        else:
            vec = pickle.loads(raw)

        ranked = vstore.search_vec(vec, TOP_K)
        sys_text, user_text = build_prompt(stripped, ranked, cards)
        prompts[q.id] = {"system": sys_text, "user": user_text}
        retrieved_rule_ids[q.id] = [r.chunk.source_id for r in ranked]

    out = {
        "derived_from": ROWS.name,
        "arm": "purerules_real",
        "rewrite_version": "none",
        "ruling_query_mode": "union",
        "vector_model": VECTOR_MODEL,
        "top_k": TOP_K,
        "n_questions": len(prompts),
        "retrieved_rule_ids": retrieved_rule_ids,
        "prompts": prompts,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.name}: {len(prompts)} prompts")
    print(f"new Voyage query embeddings computed: {n_new_embeds}/{len(questions)}")
    print("zero-cards guard: passed for all rows")
    mean_ctx = sum(len(v) for v in retrieved_rule_ids.values()) / len(retrieved_rule_ids)
    print(f"mean retrieved chunks/question: {mean_ctx:.2f} (TOP_K={TOP_K})")


if __name__ == "__main__":
    main()
