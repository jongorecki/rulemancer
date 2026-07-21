"""Eval harness: retrieval recall@k across BM25, vector, and hybrid fusion.

For each question we fetch the BM25 and vector rankings ONCE (one Voyage API
call per query), then derive every method from those same two rankings:
BM25, vector, hybrid-RRF, and hybrid-weighted. This is both efficient and the
correct way to compare fusion methods -- identical inputs, different combiners.
A small alpha sweep shows whether the weighted blend is sensitive to its
vector/BM25 weight.

Metric = recall@k with per-question `match` semantics (any / all). recall@5 is
the headline. Run: `uv run python evals/run_eval.py`
"""

from pathlib import Path

from rulesagent.contracts import EvalQuestion, Retrieved
from rulesagent.ingest.parser import parse_comprehensive_rules
from rulesagent.ingest.chunker import chunk_rules
from rulesagent.index.bm25 import BM25Index
from rulesagent.index.store import VectorStore
from rulesagent.retrieve.hybrid import rrf_fuse, weighted_fuse

REPO = Path(__file__).parent.parent
CR_PATH = REPO / "data" / "raw" / "MagicCompRules 20260619.txt"
QUESTIONS_PATH = REPO / "evals" / "questions.jsonl"
PARSED_DIR = REPO / "data" / "parsed"
VECTOR_MODEL = "voyage-4-large"  # the Phase B A/B winner feeds the hybrid
KS = (1, 5, 10, 20, 50)
DEPTH = 100  # candidates pulled from each base retriever before fusion
MAIN_ALPHA = 0.5  # vector weight for the headline weighted arm
ALPHA_SWEEP = (0.3, 0.5, 0.7)


def load_questions(path: Path) -> list[EvalQuestion]:
    return [
        EvalQuestion.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def hit_at(q: EvalQuestion, ranking: list[Retrieved], k: int) -> bool:
    ranked = [r.chunk.source_id for r in ranking]
    gold_ranks = {g: ranked.index(g) + 1 for g in q.gold if g in ranked}
    if q.match == "all":
        return len(gold_ranks) == len(q.gold) and all(r <= k for r in gold_ranks.values())
    return any(r <= k for r in gold_ranks.values())


def main() -> None:
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_ids = {c.source_id for c in chunks}
    questions = load_questions(QUESTIONS_PATH)

    for q in questions:
        missing = [g for g in q.gold if g not in chunk_ids]
        if missing:
            print(f"  [WARN] {q.id}: gold ids not found as chunks: {missing}")

    bm25 = BM25Index(chunks)
    pkl = PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl"
    if not pkl.exists():
        print(f"  [ERROR] no vector index at {pkl.name}; run build_vector_indexes.py")
        return
    vstore = VectorStore.load(pkl)

    method_names = ["BM25", VECTOR_MODEL, "hybrid-RRF", f"hybrid-wt{MAIN_ALPHA}"]
    n = len(questions)
    print(f"\n{len(chunks)} chunks | {n} questions | vector={VECTOR_MODEL} | depth={DEPTH}\n")

    hits = {name: {k: 0 for k in KS} for name in method_names}
    per_q5 = {name: {} for name in method_names}
    sweep5 = {a: 0 for a in ALPHA_SWEEP}

    for q in questions:
        bm = bm25.search(q.question, DEPTH)
        vec = vstore.search(q.question, DEPTH)
        rankings = {
            "BM25": bm,
            VECTOR_MODEL: vec,
            "hybrid-RRF": rrf_fuse([bm, vec]),
            f"hybrid-wt{MAIN_ALPHA}": weighted_fuse([bm, vec], [1 - MAIN_ALPHA, MAIN_ALPHA]),
        }
        for name, ranking in rankings.items():
            for k in KS:
                if hit_at(q, ranking, k):
                    hits[name][k] += 1
            per_q5[name][q.id] = hit_at(q, ranking, 5)
        for a in ALPHA_SWEEP:
            if hit_at(q, weighted_fuse([bm, vec], [1 - a, a]), 5):
                sweep5[a] += 1

    # comparison table
    header = f"{'retriever':<18}" + "".join(f"recall@{k:<5}" for k in KS)
    print(header)
    print("-" * len(header))
    for name in method_names:
        print(f"{name:<18}" + "".join(f"{hits[name][k]/n:>7.0%}   " for k in KS))

    print("\nweighted-fusion alpha sweep (recall@5, alpha = vector weight):")
    print("  " + "   ".join(f"a={a}: {sweep5[a]/n:.0%}" for a in ALPHA_SWEEP))

    # per-question hit@5 matrix
    print("\nPer-question hit@5 (Y=hit, .=miss):")
    print(f"{'qid':<6}{'match':<6}" + "".join(f"{name[:12]:<14}" for name in method_names) + "question")
    for q in questions:
        marks = "".join(f"{'Y' if per_q5[name][q.id] else '.':<14}" for name in method_names)
        print(f"{q.id:<6}{q.match:<6}{marks}{q.question[:46]}")


if __name__ == "__main__":
    main()
