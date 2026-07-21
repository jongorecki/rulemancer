"""Eval harness: measures retrieval recall@k across retrievers.

Runs BM25 and any built vector stores (see build_vector_indexes.py) against
the same question set, so every number is comparable. recall@5 is the
headline. Vector columns only appear if their .pkl has been built.

Metric = recall@k with per-question `match` semantics:
  match="any": a hit at k if AT LEAST ONE gold id is in the top k.
  match="all": a hit at k only if EVERY gold id is in the top k.

Run: `uv run python evals/run_eval.py`
"""

import time
from pathlib import Path

from rulesagent.contracts import EvalQuestion
from rulesagent.ingest.parser import parse_comprehensive_rules
from rulesagent.ingest.chunker import chunk_rules
from rulesagent.index.bm25 import BM25Index
from rulesagent.index.store import VectorStore

REPO = Path(__file__).parent.parent
CR_PATH = REPO / "data" / "raw" / "MagicCompRules 20260619.txt"
QUESTIONS_PATH = REPO / "evals" / "questions.jsonl"
PARSED_DIR = REPO / "data" / "parsed"
KS = (1, 5, 10)
VECTOR_MODELS = ["voyage-4", "voyage-4-large"]


def load_questions(path: Path) -> list[EvalQuestion]:
    return [
        EvalQuestion.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def hit_at(q: EvalQuestion, gold_ranks: dict[str, int], k: int) -> bool:
    """gold_ranks maps each found gold id to its 1-based rank."""
    if q.match == "all":
        return len(gold_ranks) == len(q.gold) and all(r <= k for r in gold_ranks.values())
    return any(r <= k for r in gold_ranks.values())


def evaluate(search_fn, questions: list[EvalQuestion]) -> tuple[dict[int, int], dict[str, bool]]:
    hits = {k: 0 for k in KS}
    per_q_hit5: dict[str, bool] = {}
    max_k = max(KS)
    for q in questions:
        results = search_fn(q.question, max_k)
        ranked = [r.chunk.source_id for r in results]
        gold_ranks = {g: ranked.index(g) + 1 for g in q.gold if g in ranked}
        for k in KS:
            if hit_at(q, gold_ranks, k):
                hits[k] += 1
        per_q_hit5[q.id] = hit_at(q, gold_ranks, 5)
    return hits, per_q_hit5


def main() -> None:
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_ids = {c.source_id for c in chunks}
    questions = load_questions(QUESTIONS_PATH)

    for q in questions:
        missing = [g for g in q.gold if g not in chunk_ids]
        if missing:
            print(f"  [WARN] {q.id}: gold ids not found as chunks: {missing}")

    # assemble retrievers: BM25 always; each vector model if its index exists
    retrievers: dict[str, object] = {"BM25": BM25Index(chunks).search}
    for model in VECTOR_MODELS:
        pkl = PARSED_DIR / f"vector_{model}.pkl"
        if pkl.exists():
            retrievers[model] = VectorStore.load(pkl).search
        else:
            print(f"  [skip] {model}: no index at {pkl.name} (run build_vector_indexes.py)")

    n = len(questions)
    print(f"\n{len(chunks)} chunks | {n} questions | retrievers: {', '.join(retrievers)}\n")

    results = {}
    per_q = {}
    for name, search_fn in retrievers.items():
        start = time.time()
        hits, per_q_hit5 = evaluate(search_fn, questions)
        results[name] = (hits, (time.time() - start) / n)
        per_q[name] = per_q_hit5

    # comparison table
    header = f"{'retriever':<16}" + "".join(f"recall@{k:<5}" for k in KS) + "ms/query"
    print(header)
    print("-" * len(header))
    for name, (hits, secs) in results.items():
        row = f"{name:<16}" + "".join(f"{hits[k]/n:>7.0%}   " for k in KS) + f"{secs*1000:>6.1f}"
        print(row)

    # per-question hit@5 matrix -- where the learning is
    names = list(retrievers)
    print("\nPer-question hit@5 (Y=hit, .=miss):")
    print(f"{'qid':<6}{'match':<6}" + "".join(f"{name[:12]:<14}" for name in names) + "question")
    for q in questions:
        marks = "".join(f"{'Y' if per_q[name][q.id] else '.':<14}" for name in names)
        print(f"{q.id:<6}{q.match:<6}{marks}{q.question[:50]}")


if __name__ == "__main__":
    main()
