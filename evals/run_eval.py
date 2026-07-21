"""Eval harness: measures retrieval recall@k against the labeled question set.

Phase A measures BM25 only. Vector / hybrid / rerank get added as more
columns later, each run against this same question set so every number is
comparable. Run with: `uv run python evals/run_eval.py`.

The metric is recall@k: for each question, did AT LEAST ONE gold source_id
land in the top k retrieved chunks? We report @1, @5, @10. (recall@5 is the
headline number the build plan tracks.)
"""

import json
from pathlib import Path

from rulesagent.contracts import EvalQuestion
from rulesagent.ingest.parser import parse_comprehensive_rules
from rulesagent.ingest.chunker import chunk_rules
from rulesagent.index.bm25 import BM25Index

REPO = Path(__file__).parent.parent
CR_PATH = REPO / "data" / "raw" / "MagicCompRules 20260619.txt"
QUESTIONS_PATH = REPO / "evals" / "questions.jsonl"
KS = (1, 5, 10)


def load_questions(path: Path) -> list[EvalQuestion]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(EvalQuestion.model_validate_json(line))
    return out


def main() -> None:
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_ids = {c.source_id for c in chunks}
    index = BM25Index(chunks)
    questions = load_questions(QUESTIONS_PATH)

    # Validate gold ids exist as chunks -- a gold id that isn't a real chunk
    # (e.g. a folded label like "701.5") can never be retrieved, so it would
    # silently drag recall down. Warn loudly instead.
    for q in questions:
        missing = [g for g in q.gold if g not in chunk_ids]
        if missing:
            print(f"  [WARN] {q.id}: gold ids not found as chunks: {missing}")

    print(f"\nBM25 retrieval over {len(chunks)} chunks | {len(questions)} questions\n")

    hits = {k: 0 for k in KS}
    max_k = max(KS)
    misses = []
    for q in questions:
        results = index.search(q.question, k=max_k)
        ranked_ids = [r.chunk.source_id for r in results]
        # rank (1-based) of each gold id, if it appeared in the top max_k
        gold_ranks = {g: ranked_ids.index(g) + 1 for g in q.gold if g in ranked_ids}

        for k in KS:
            if q.match == "all":
                # hit only if EVERY gold id is present within the top k
                hit = len(gold_ranks) == len(q.gold) and all(r <= k for r in gold_ranks.values())
            else:  # "any": at least one gold id within the top k
                hit = any(r <= k for r in gold_ranks.values())
            if hit:
                hits[k] += 1

        # a miss (for the top-5 report) uses the same rule at k=5
        if q.match == "all":
            hit5 = len(gold_ranks) == len(q.gold) and all(r <= 5 for r in gold_ranks.values())
        else:
            hit5 = any(r <= 5 for r in gold_ranks.values())
        if not hit5:
            misses.append((q, ranked_ids[:5]))

    n = len(questions)
    print("Recall@k (headline = @5):")
    for k in KS:
        print(f"  recall@{k:<2} = {hits[k]}/{n} = {hits[k]/n:.0%}")

    if misses:
        print("\nMisses (not a hit in top 5) -- this is where the learning is:")
        for q, top5 in misses:
            print(f"  {q.id} [match={q.match}]: {q.question}")
            print(f"    gold={q.gold}  got top5={top5}")


if __name__ == "__main__":
    main()
