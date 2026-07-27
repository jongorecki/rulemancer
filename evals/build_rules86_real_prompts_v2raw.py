"""Freeze the PRODUCTION-CONFIG (rewrite_version="v2", ruling_query_mode=
"raw") real-retrieval prompt cache for the 86-row card-free rules probe
(evals/questions_rules86.jsonl). Jon, 2026-07-27 -- the headline-run
prerequisite: the existing evals/answers/_prompts_rules86_real.json was built
at rewrite_version="none"/ruling_query_mode="union" (build_rules86_real_
prompts.py, unchanged, left on disk), which evals/run_answer_eval.py's
--prompts-cache guard correctly refuses to run a v2/raw generation against.

Unlike build_rules86_real_prompts.py, this does NOT reimplement retrieval by
hand (embed_query + vstore.search_vec + build_prompt) -- that shape can only
ever reproduce rewrite_version="none" (raw stripped question straight into
retrieval). Getting v2/raw right means running the REAL RulesAgent.answer()
pipeline (rewrite -> retrieval -> build_prompt), intercepted right before the
generation call -- see evals/_capture_v2raw.py's capture() for exactly how
and why that's still zero-Anthropic-call-safe.

PREREQUISITE: evals/warm_rewrite_cache_v2.py must have already been run for
every question in evals/questions_rules86.jsonl (a real, budgeted
claude-haiku-4-5 spend, done once, shared with the rulesguru_full_v2 cache
build). capture() raises loudly if a question's rewrite isn't actually warm,
rather than silently shipping a same-as-original fallback rewrite under a
"v2" stamp.

ZERO-CARDS GUARD: this question set is constructed to have no [Card Name]
tokens at all -- asserted below (n_cards == 0) via the real agent's own
agent.last_cards, not by re-parsing the question ourselves.

Run: uv run python evals/build_rules86_real_prompts_v2raw.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.index.store import VectorStore  # noqa: E402
from run_eval import PARSED_DIR, VECTOR_MODEL, load_questions  # noqa: E402
from _capture_v2raw import capture  # noqa: E402

REPO = Path(__file__).parent.parent
ROWS = REPO / "evals" / "questions_rules86.jsonl"
OUT = REPO / "evals" / "answers" / "_prompts_rules86_real_v2raw.json"


def main() -> None:
    questions = load_questions(ROWS)
    vstore = VectorStore.load(PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl")

    prompts: dict[str, dict] = {}
    retrieved_rule_ids: dict[str, list[str]] = {}
    rewritten_queries: dict[str, list[str]] = {}

    for i, q in enumerate(questions, 1):
        result = capture(vstore, q.question, q.id)
        if result.n_cards != 0:
            raise SystemExit(
                f"[ERROR] {q.id} resolved {result.n_cards} card(s) -- "
                f"questions_rules86.jsonl must have zero cards by construction, "
                f"refusing to build a cache that would confound the probe"
            )
        if result.has_card_data_block:
            raise SystemExit(f"[ERROR] {q.id} has a 'Card data:' block despite 0 cards -- unreachable")
        prompts[q.id] = {"system": result.system, "user": result.user}
        retrieved_rule_ids[q.id] = result.retrieved_rule_ids
        rewritten_queries[q.id] = result.rewritten_queries
        print(f"  [{i}/{len(questions)}] {q.id} captured")

    out = {
        "derived_from": ROWS.name,
        "arm": "rules86_real_v2raw",
        "rewrite_version": "v2",
        "ruling_query_mode": "raw",
        "vector_model": VECTOR_MODEL,
        "n_questions": len(prompts),
        "retrieved_rule_ids": retrieved_rule_ids,
        "rewritten_queries": rewritten_queries,
        "prompts": prompts,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.name}: {len(prompts)} prompts")
    print("zero-cards guard: passed for all rows")
    mean_ctx = sum(len(v) for v in retrieved_rule_ids.values()) / len(retrieved_rule_ids)
    print(f"mean retrieved chunks/question: {mean_ctx:.2f}")


if __name__ == "__main__":
    main()
