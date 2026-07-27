"""Freeze arm A's (real) prompts for the retrieval-value A/B
(docs/spec-retrieval-value-ab.md). Reads evals/ab_rows.jsonl (120 rows, built
by build_ab_rows.py) and, for each row, runs the real local retrieval
pipeline (Voyage query embedding + vector search over the frozen CR index --
no Anthropic call anywhere in this script) and assembles the exact
(system, user) pair via build_prompt(), the same canonical assembler
build_gold_prompts.py / build_prompts_variant.py use.

WHY NO REWRITE STEP: production's default query rewrite is a
claude-haiku-4-5 call (RulesAgent(rewrite_version="v2")). This experiment's
absolute constraint is zero Anthropic API calls of any kind, so this script
does not call the rewriter -- checked, and essentially none of these 120
questions have a cached v2 rewrite already (22/1409 corpus-wide sampled
have any rewrite cached, 0/1409 have a cached QUERY EMBEDDING for the raw
stripped question, so there's no way to assemble this from cache alone
either). Retrieval here runs directly on the stripped question text (the
same "[Card]" -> "Card" stripping every other arm's generator sees), which
is production's `--rewrite-version none` / `RulesAgent(rewrite=False)`
configuration -- a real, named, honest configuration, not a silent
deviation. Recorded as rewrite_version="none" in the output file's
provenance, same field build_norules_prompts.py stamps for the same reason.
The pilot/full-run commands this harness prints pass --rewrite-version none
so run_answer_eval.py's --prompts-cache identity gate matches.

WHY UNION-MODE RULINGS: build_prompt()'s own label_rulings(card) call (no
`indices` argument) always labels the FULL rulings list -- that is union
mode, unconditionally, for every caller of build_prompt() including this
one. No separate choice needed; recorded for provenance to match
build_gold_prompts.py's convention.

WHY --layers-tool DOESN'T LIVE HERE: RESOLVE_LAYERS_TOOL is only ever
attached inside RulesAgent.answer()'s live tool loop (answer.py ~2217);
evals/run_answer_eval.py's --prompts-cache path
(_answer_from_frozen_prompt()) calls client.messages.parse() with NO tools
argument at all -- confirmed by reading that function. That means the
frozen prompt itself never encodes layers_tool one way or the other; arm A
vs arm C's --layers-tool / --no-layers-tool flag only changes the
`layers_tool` field stamped onto the output ROW for provenance/coverage
scoring (prompt_supplied_rule_ids()), NOT the actual request sent to the
model. This is a real spec/code gap, flagged in the harness report rather
than silently worked around.

Retrieval config: TOP_K (from rulesagent.generate.answer, the production
constant, currently 15) pure-vector top-k, VECTOR_MODEL = "voyage-4-large"
(run_eval.VECTOR_MODEL, the shipped index). This is a live Voyage API call
per question NOT already cached -- Voyage billing, never Anthropic; the
harness brief explicitly authorizes local/embedding retrieval work.

Run: uv run python evals/build_ab_real_prompts.py
"""

import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.cache import KVCache  # noqa: E402
from rulesagent.contracts import Retrieved  # noqa: E402
from rulesagent.generate.answer import TOP_K, build_prompt  # noqa: E402
from rulesagent.index.embed import embed_query  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402
from rulesagent.tools.scryfall import get_card, parse_card_refs  # noqa: E402
from run_eval import CR_PATH, PARSED_DIR, VECTOR_MODEL, load_questions  # noqa: E402

REPO = Path(__file__).parent.parent
ROWS = REPO / "evals" / "ab_rows.jsonl"
OUT = REPO / "evals" / "answers" / "_prompts_ab_real.json"


def ordered_cards(question: str):
    """Cards in first-appearance order of the bracketed tokens, deduped
    case-insensitively -- same convention build_prompts_variant.py documents
    for reproducing production's card ordering."""
    _stripped, tokens = parse_card_refs(question)
    seen: set[str] = set()
    ordered_tokens = [t for t in tokens if not (t.lower() in seen or seen.add(t.lower()))]
    cards = []
    missing = []
    for t in ordered_tokens:
        c = get_card(t, no_refresh=True)
        if c is None:
            missing.append(t)
        else:
            cards.append(c)
    return cards, missing


def main() -> None:
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_map = {c.source_id: c for c in chunks}
    questions = load_questions(ROWS)
    vstore = VectorStore.load(PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl")
    qemb = KVCache("query_emb")

    prompts: dict[str, dict] = {}
    retrieved_rule_ids: dict[str, list[str]] = {}
    missing_cards: dict[str, list[str]] = {}
    n_new_embeds = 0

    for q in questions:
        stripped, _refs = parse_card_refs(q.question)
        cards, missing = ordered_cards(q.question)
        if missing:
            missing_cards[q.id] = missing

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
        "arm": "A_real",
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
    if missing_cards:
        print(f"[WARN] {len(missing_cards)} question(s) had a card token Scryfall couldn't resolve:")
        for qid, toks in list(missing_cards.items())[:10]:
            print(f"  {qid}: {toks}")
    mean_ctx = sum(len(v) for v in retrieved_rule_ids.values()) / len(retrieved_rule_ids)
    print(f"mean retrieved chunks/question: {mean_ctx:.2f} (TOP_K={TOP_K})")


if __name__ == "__main__":
    main()
