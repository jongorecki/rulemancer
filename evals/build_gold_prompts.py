"""Freeze the derivability-experiment prompts (gold-only, and gold + retrieved).

The question this instrument exists to answer, in Jon's words: "I want to make
sure we can derive the rulesguru answers from the gold rules and rulings."

Every accuracy number this project has -- 63%, 75%, 82.4% -- is retrieval and
reasoning combined, with no way to tell which half fails. These two arms split
them:

  B  gold rules only        pass  => the encoded gold IS sufficient
  C  gold + retrieved top-15  B fails / C passes => gold is INCOMPLETE
                              B fails / C fails  => reasoning failure, or the
                                                    RulesGuru answer is wrong

Arm C is the true ceiling: if a question fails with gold AND everything
retrieval would have supplied, no retrieval improvement can ever fix it.

WHY FROZEN PROMPTS instead of a new RulesAgent mode: build_prompt() is the
canonical assembler (tests/fixtures/prompt_identity.json guards it) and
run_answer_eval already consumes frozen prompts via --prompts-cache. That seam
lets this experiment run without touching the production answer path at all.

ZERO API COST to build. Card data comes from the Scryfall cache, arm C's
retrieval reuses the frozen query-embedding cache and the already-cached haiku
n=1 rewrite (production's config). Nothing here calls a model.

CARD RULINGS: every ruling on every referenced card is included, i.e. union
mode. That is deliberate -- Jon's rg346 finding was that rulings get split and
treated separately, so a derivability failure caused by a truncated ruling
would be indistinguishable from missing gold. Feeding all of them controls for
it.

Run: uv run python evals/build_gold_prompts.py
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
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402
from rulesagent.tools.scryfall import get_card, parse_card_refs  # noqa: E402
from run_eval import CR_PATH, PARSED_DIR, VECTOR_MODEL, load_questions  # noqa: E402

REPO = Path(__file__).parent.parent
QUESTIONS = REPO / "evals" / "questions_rulesguru150_v3.jsonl"
REWRITE_KEY = ("claude-haiku-4-5", "v2", 1)  # production's config


def main() -> None:
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_map = {c.source_id: c for c in chunks}
    questions = load_questions(QUESTIONS)
    vstore = VectorStore.load(PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl")
    rw_cache, qemb = KVCache("rewrite"), KVCache("query_emb")

    prompts_b, prompts_c = {}, {}
    unretrievable, no_cards, missing_rw = {}, [], []
    n_gold, n_ctx_c, n_rulings = [], [], []

    for q in questions:
        # --- cards: all rulings, no selection (union) ---
        # parse_card_refs returns (stripped_text, tokens). The STRIPPED text is
        # what production feeds both the rewriter and the generator -- "[Dovescape]"
        # becomes "Dovescape" so the sentence reads naturally. Building from the
        # raw bracketed question would silently produce a prompt production never
        # sends.
        stripped, refs = parse_card_refs(q.question)
        cards = [c for r in refs if (c := get_card(r)) is not None]
        if not cards:
            no_cards.append(q.id)
        n_rulings.append(sum(len(c.rulings) for c in cards))

        # --- arm B: gold only ---
        missing = [g for g in q.gold if g not in chunk_map]
        if missing:
            unretrievable[q.id] = missing
        gold_ret = [Retrieved(chunk=chunk_map[g], score=1.0) for g in q.gold if g in chunk_map]
        n_gold.append(len(gold_ret))
        sys_b, user_b = build_prompt(stripped, gold_ret, cards)
        prompts_b[q.id] = {"system": sys_b, "user": user_b}

        # --- arm C: gold first, then production's top-15 minus duplicates ---
        # Gold leads because it is relevant by construction; retrieval follows.
        # Deliberately NO crossref expansion, so B and C differ in exactly one
        # thing (the retrieved block) rather than two.
        # Prefer production's exact query text (rewrite of the STRIPPED
        # question). Fall back to the raw question's rewrite, then to the raw
        # question itself -- whichever is cached. Never call the API here: a
        # build step that quietly spends is exactly what --cache-only exists to
        # prevent elsewhere. Which path each question took is reported below.
        query = None
        for candidate in (stripped, q.question):
            raw = rw_cache.get(json.dumps([*REWRITE_KEY, candidate]))
            if raw is None:
                continue
            val = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            qs = [s for s in val[0] if s and s.strip()]
            if qs and qemb.get(qs[0]) is not None:
                query = qs[0]
                break
        if query is None:
            missing_rw.append(q.id)
            query = stripped if qemb.get(stripped) is not None else q.question
        vec_raw = qemb.get(query)
        if vec_raw is None:
            raise SystemExit(f"{q.id}: no cached embedding for {query[:60]!r} -- "
                             "would require an API call; aborting rather than spending")
        ranked = vstore.search_vec(pickle.loads(vec_raw), TOP_K)
        have = {r.chunk.source_id for r in gold_ret}
        merged = gold_ret + [r for r in ranked if r.chunk.source_id not in have]
        n_ctx_c.append(len(merged))
        sys_c, user_c = build_prompt(q.question, merged, cards)
        prompts_c[q.id] = {"system": sys_c, "user": user_c}

    # run_answer_eval's prompts-cache loader cross-checks these two keys
    # against the CLI args, so a frozen set built under one config can't be
    # run under another. Recorded truthfully per arm:
    #   B  nothing was rewritten -- the context is gold, retrieval never ran.
    #   C  the retrieved block came from the cached v2 n=1 rewrite, which is
    #      production's configuration.
    provenance = {
        "B_goldonly": {"rewrite_version": "none", "ruling_query_mode": "union"},
        "C_goldplusretrieved": {"rewrite_version": "v2", "ruling_query_mode": "union"},
    }
    for tag, prompts in (("B_goldonly", prompts_b), ("C_goldplusretrieved", prompts_c)):
        out = REPO / "evals" / "answers" / f"_prompts_derivability_{tag}.json"
        out.write_text(json.dumps({
            "derived_from": QUESTIONS.name,
            "arm": tag,
            **provenance[tag],
            "ruling_mode": "union (all rulings on every referenced card)",
            "crossref_expansion": False,
            "n_questions": len(prompts),
            "prompts": prompts,
        }, indent=1), encoding="utf-8")
        print(f"wrote {out.name}: {len(prompts)} prompts")

    mean = lambda xs: sum(xs) / len(xs) if xs else 0  # noqa: E731
    print(f"\nmean gold chunks/question (arm B): {mean(n_gold):.2f}")
    print(f"mean context chunks/question (arm C): {mean(n_ctx_c):.2f}   (TOP_K={TOP_K})")
    print(f"mean card rulings/question:          {mean(n_rulings):.2f}")
    print(f"questions with no resolvable cards:  {len(no_cards)} {no_cards[:6]}")
    print(f"questions missing a cached rewrite:  {len(missing_rw)} {missing_rw[:6]}")
    if unretrievable:
        print(f"\n[WARN] {len(unretrievable)} question(s) cite gold NOT in the chunk index -- "
              "these can never be satisfied by any retriever, and arm B sees them short:")
        for qid, ids in list(unretrievable.items())[:10]:
            print(f"  {qid}: {ids}")


if __name__ == "__main__":
    main()
