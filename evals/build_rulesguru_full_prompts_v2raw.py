"""Freeze the PRODUCTION-CONFIG (rewrite_version="v2", ruling_query_mode=
"raw") real-retrieval prompt cache for ALL 1,409 rows of
evals/rulesguru_full_v2.jsonl -- the headline-run cache. Jon, 2026-07-27.

Runs the real RulesAgent.answer() pipeline per question (rewrite, card
resolution via Scryfall, PER-CARD RAW-MODE ruling selection via
select_rulings() -- not select_rulings_union(), which is what the two
"none"/"union" model scripts (build_ab_real_prompts.py, build_purerules_
real_prompts.py) get by construction since they call build_prompt() directly
with unfiltered cards -- retrieval, cross-ref expansion, build_prompt()),
intercepted right before the generation call. See evals/_capture_v2raw.py's
capture() for the mechanics and the zero-Anthropic-call safety argument.

Card data: these rows DO reference cards ([Card Name] tokens), so unlike the
86-row card-free set, `Card data:` blocks are expected here -- capture()
reports n_cards and unresolved refs per row (via agent.last_unresolved_refs,
the same {"ref", "reason"} shape RulesAgent.answer() itself records) so the
builder can report resolution failures loudly instead of them vanishing.

PREREQUISITE: evals/warm_rewrite_cache_v2.py must have already warmed every
question's v2 rewrite -- capture() raises loudly per-row if it wasn't.

Run: uv run python evals/build_rulesguru_full_prompts_v2raw.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.index.store import VectorStore  # noqa: E402
from run_eval import PARSED_DIR, VECTOR_MODEL, load_questions  # noqa: E402
from _capture_v2raw import capture  # noqa: E402

REPO = Path(__file__).parent.parent
ROWS = REPO / "evals" / "rulesguru_full_v2.jsonl"
OUT = REPO / "evals" / "answers" / "_prompts_rulesguru_full_v2raw.json"


def main() -> None:
    questions = load_questions(ROWS)
    vstore = VectorStore.load(PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl")

    prompts: dict[str, dict] = {}
    retrieved_rule_ids: dict[str, list[str]] = {}
    rewritten_queries: dict[str, list[str]] = {}
    n_cards_by_id: dict[str, int] = {}
    unresolved_by_id: dict[str, list[dict]] = {}

    t0 = time.time()
    rows_with_card_block = 0
    rows_with_zero_cards = 0
    total_unresolved_refs = 0
    rows_with_any_unresolved = 0

    for i, q in enumerate(questions, 1):
        result = capture(vstore, q.question, q.id)
        prompts[q.id] = {"system": result.system, "user": result.user}
        retrieved_rule_ids[q.id] = result.retrieved_rule_ids
        rewritten_queries[q.id] = result.rewritten_queries
        n_cards_by_id[q.id] = result.n_cards
        if result.unresolved_refs:
            unresolved_by_id[q.id] = result.unresolved_refs
            total_unresolved_refs += len(result.unresolved_refs)
            rows_with_any_unresolved += 1
        if result.n_cards == 0:
            rows_with_zero_cards += 1
            if result.has_card_data_block:
                raise SystemExit(f"[ERROR] {q.id} has a 'Card data:' block despite 0 resolved cards -- unreachable")
        else:
            if not result.has_card_data_block:
                raise SystemExit(f"[ERROR] {q.id} resolved {result.n_cards} card(s) but has NO 'Card data:' block")
            rows_with_card_block += 1
        if i % 100 == 0 or i == len(questions):
            elapsed = time.time() - t0
            print(f"  [{i}/{len(questions)}] captured | {elapsed:.0f}s elapsed | "
                  f"{rows_with_card_block} with cards, {total_unresolved_refs} unresolved refs so far")

    out = {
        "derived_from": ROWS.name,
        "arm": "rulesguru_full_v2raw",
        "rewrite_version": "v2",
        "ruling_query_mode": "raw",
        "vector_model": VECTOR_MODEL,
        "n_questions": len(prompts),
        "retrieved_rule_ids": retrieved_rule_ids,
        "rewritten_queries": rewritten_queries,
        "n_cards": n_cards_by_id,
        "unresolved_refs": unresolved_by_id,
        "prompts": prompts,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.name}: {len(prompts)} prompts")
    print(f"rows with a Card data block: {rows_with_card_block}")
    print(f"rows with zero cards: {rows_with_zero_cards}")
    print(f"rows with >=1 unresolved card ref: {rows_with_any_unresolved}")
    print(f"total unresolved card refs: {total_unresolved_refs}")
    lens = [len(p["system"]) + len(p["user"]) for p in prompts.values()]
    print(f"prompt length (system+user chars): mean={sum(lens)/len(lens):.0f} max={max(lens)}")


if __name__ == "__main__":
    main()
