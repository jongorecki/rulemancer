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

import argparse
import json
import pickle
from pathlib import Path

from rulesagent.cache import KVCache
from rulesagent.contracts import EvalQuestion, Retrieved, RewrittenQuery
from rulesagent.generate.answer import TOP_K as GEN_TOP_K
from rulesagent.ingest.parser import parse_comprehensive_rules
from rulesagent.ingest.chunker import chunk_rules
from rulesagent.index.bm25 import BM25Index
from rulesagent.index.embed import embed_query
from rulesagent.index.store import VectorStore
from rulesagent.retrieve.hybrid import rrf_fuse, weighted_fuse
from rulesagent.retrieve.rerank import rerank
from rulesagent.retrieve.rewrite import rewrite_query

REPO = Path(__file__).parent.parent
CR_PATH = REPO / "data" / "raw" / "MagicCompRules 20260619.txt"
QUESTIONS_PATH = REPO / "evals" / "questions.jsonl"
PARSED_DIR = REPO / "data" / "parsed"
VECTOR_MODEL = "voyage-4-large"  # the Phase B A/B winner
KS = (1, 5, 10, 20, 50)
DEPTH = 100  # candidates pulled from each base retriever before fusion
MAIN_ALPHA = 0.5  # vector weight for the headline weighted arm
ALPHA_SWEEP = (0.3, 0.5, 0.7)
RERANK_POOL = 50  # vector candidates fed to the reranker (Phase C: best pool)
RERANK_MODELS = ("rerank-2.5", "rerank-2.5-lite")

# Plan #3a: rewrite arms. label -> model, so arm names read "vec+rw{n}-{label}"
# matching the plan's 2x2 grid (rewrite count x rewriter model). Dict order
# (haiku then sonnet) fixes the row order everywhere below.
REWRITE_MODELS = {"haiku": "claude-haiku-4-5", "sonnet": "claude-sonnet-5"}
REWRITE_NS = (1, 3)


_KNOWN_KINDS = {"rule", "glossary", "interaction", "other", "card-interaction"}
# EvalQuestion.kind (src/rulesagent/contracts.py) is a closed Literal that
# predates external question sources like RulesGuru ("kind": "rulesguru").
# Widening that Literal is a src/ change this import deliberately stays out
# of (plan-rulesguru-import.md "What does NOT change") -- so the loader
# coerces any kind it doesn't recognize to "other" before validating. Every
# other extra field (answer_gold, level, complexity, tags, url, submitter)
# needs no such handling: pydantic drops unknown fields by default.


def load_questions(path: Path) -> list[EvalQuestion]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") not in _KNOWN_KINDS:
            row["kind"] = "other"
        questions.append(EvalQuestion.model_validate(row))
    return questions


def query_vectors(questions: list[EvalQuestion], model: str) -> dict[str, "object"]:
    """Freeze query embeddings to disk so the eval is reproducible. Voyage
    returns slightly different query vectors on repeated calls; caching the
    first result makes vector retrieval deterministic run-to-run (and faster,
    since queries aren't re-embedded).

    L3 (docs/plan-l3-sqlite-caches.md): SQLite-backed (data/cache.db,
    `query_emb` table per the plan's fixed table set), key = the
    query/rewrite string, value = `pickle.dumps` of the numpy vector (numpy
    doesn't round-trip JSON cleanly). `model` is only ever called with the
    single pinned VECTOR_MODEL in this codebase (mirrors the single
    query_emb_voyage-4-large.pkl file that existed on disk -- there was
    never a second model's file to collide with). Returns the same
    {question: vector} shape as before -- callers are unaffected by the
    storage swap."""
    cache = KVCache("query_emb")
    result: dict[str, object] = {}
    for q in questions:
        raw = cache.get(q.question)
        if raw is None:
            vec = embed_query(q.question, model)
            cache.put(q.question, pickle.dumps(vec))
            result[q.question] = vec
        else:
            result[q.question] = pickle.loads(raw)
    return result


def cached_rerank(query, candidates, model, cache: KVCache, chunk_map):
    """Rerank with an on-disk cache. Key = (model, query, exact pool ids), so
    a run with unchanged data hits the cache and makes zero API calls; if the
    pool changes (re-chunk / re-embed), the key changes and it re-reranks.
    Voyage's reranker is deterministic, so a cached result is identical to a
    fresh one.

    L3 (docs/plan-l3-sqlite-caches.md): `cache` is a KVCache over the
    `rerank` table. key = JSON-list of [model, query, pool ids] (tuples
    can't be a TEXT key directly); value = `pickle.dumps` of the reranked
    (source_id, score) order (numpy-adjacent score data, our own format --
    pickle inside a BLOB is fine)."""
    pool_ids = tuple(c.chunk.source_id for c in candidates)
    key = json.dumps([model, query, list(pool_ids)])
    raw = cache.get(key)
    if raw is not None:
        order = pickle.loads(raw)
        return [Retrieved(chunk=chunk_map[sid], score=s) for sid, s in order]
    result = rerank(query, candidates, model)
    order = [(r.chunk.source_id, r.score) for r in result]
    cache.put(key, pickle.dumps(order))
    return result


def gold_groups(q: EvalQuestion) -> list[list[str]]:
    """The general AND-of-ORs form of a question's gold. any/all are the two
    degenerate cases, so all three match modes flow through one hit rule and
    existing any/all questions score exactly as before."""
    if q.match == "groups":
        return q.gold_groups
    if q.match == "all":
        return [[g] for g in q.gold]  # each id its own required group
    return [q.gold]  # "any": one OR-group of alternatives


def hit_at(q: EvalQuestion, ranking: list[Retrieved], k: int) -> bool:
    topk = {r.chunk.source_id for r in ranking[:k]}
    return all(any(g in topk for g in group) for group in gold_groups(q))


def rewrite_arm_name(label: str, n: int) -> str:
    return f"vec+rw{n}-{label}"


def hit_at_forced(q: EvalQuestion, ranking: list[Retrieved], k: int, mode: str) -> bool:
    """Like hit_at, but scores q's flat `gold` list under a FORCED any/all
    semantics, ignoring the question's own `match`/`gold_groups` fields.
    Used only by --match-both: the two columns must look at the identical
    flat gold list under both rules, not each question's preferred one, or
    the gap between them (the finding --match-both exists to show) would be
    comparing different things per question rather than two strictness
    levels of the same thing. Empty gold never hits, same as hit_at."""
    if not q.gold:
        return False
    topk = {r.chunk.source_id for r in ranking[:k]}
    if mode == "any":
        return any(g in topk for g in q.gold)
    return all(g in topk for g in q.gold)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--questions", type=Path, default=QUESTIONS_PATH,
        help=f"eval questions jsonl (default: {QUESTIONS_PATH})",
    )
    p.add_argument(
        "--match-both", action="store_true",
        help="also score every method's SAME retrieved top-k under forced "
        "any AND forced all semantics (one retrieval pass, two hit rules) "
        "and print both recall@k columns; default off, existing question "
        "sets' output is unchanged either way",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_ids = {c.source_id for c in chunks}
    questions = load_questions(args.questions)

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
    qvecs = query_vectors(questions, VECTOR_MODEL)  # frozen -> reproducible
    chunk_map = {c.source_id: c for c in chunks}
    rerank_cache = KVCache("rerank")

    # --- Plan #3a: rewrite arms -----------------------------------------
    # One rewrite call per (question, model, n) -- cached on disk in
    # rewrite.py's own `rewrite` table, so a second eval run makes zero
    # rewriting API calls. Every rewrite string then needs a query vector;
    # those flow through the SAME `query_emb` table the base questions use
    # above -- rewrites are just different strings, so this stays
    # reproducible for free.
    rewrites: dict[tuple[str, str, int], RewrittenQuery] = {}
    rewrite_texts: set[str] = set()
    for q in questions:
        for label, model in REWRITE_MODELS.items():
            for n_rw in REWRITE_NS:
                rw = rewrite_query(q.question, model, n_rw)
                rewrites[(q.id, label, n_rw)] = rw
                rewrite_texts.update(rw.queries)

    qvec_cache = dict(qvecs)  # base-question vectors already frozen above
    qvec_kv = KVCache("query_emb")
    for text in rewrite_texts:
        if text in qvec_cache:
            continue
        raw = qvec_kv.get(text)
        if raw is None:
            vec = embed_query(text, VECTOR_MODEL)
            qvec_kv.put(text, pickle.dumps(vec))
            qvec_cache[text] = vec
        else:
            qvec_cache[text] = pickle.loads(raw)

    def rewrite_rankings(q_id: str, label: str, n: int) -> tuple[list[Retrieved], list[list[Retrieved]]]:
        """(fused ranking, individual per-rewrite rankings) for one
        (question, arm). Individual rankings are kept so the `+orig`
        variant below can re-fuse them with the original question's ranking
        directly, rather than re-fusing an already-fused list."""
        rw = rewrites[(q_id, label, n)]
        individual = [vstore.search_vec(qvec_cache[s], DEPTH) for s in rw.queries]
        fused = individual[0] if len(individual) == 1 else rrf_fuse(individual)
        return fused, individual

    rw_arm_names = [rewrite_arm_name(label, n) for label in REWRITE_MODELS for n in REWRITE_NS]

    method_names = (
        ["BM25", VECTOR_MODEL, "hybrid-RRF", f"hybrid-wt{MAIN_ALPHA}"]
        + [f"rerank:{m}" for m in RERANK_MODELS]
        + rw_arm_names
    )
    matrix_names = ["BM25", VECTOR_MODEL] + [f"rerank:{m}" for m in RERANK_MODELS] + rw_arm_names
    n = len(questions)
    n_empty_gold = sum(1 for q in questions if not q.gold)
    n_scored = (n - n_empty_gold) or 1  # denominator floor: never /0
    # Empty-gold questions (RulesGuru rows whose citedRules was {}) can never
    # hit -- hit_at/hit_at_forced both return False for them already -- so
    # excluding them is purely a DENOMINATOR change: recall% is hits/n_scored,
    # not hits/n. They're still counted in n and reported here, per the plan
    # ("skip in recall scoring but count in the summary").
    print(f"\n{len(chunks)} chunks | {n} questions ({n_empty_gold} empty-gold, "
          f"excluded from recall denominator) | vector={VECTOR_MODEL} | rerank pool={RERANK_POOL}\n")

    hits = {name: {k: 0 for k in KS} for name in method_names}
    per_q5 = {name: {} for name in method_names}
    sweep5 = {a: 0 for a in ALPHA_SWEEP}
    top_gen_k: dict[str, dict[str, list[str]]] = {name: {} for name in method_names}
    # method -> question id -> chunk ids in that method's top-GEN_TOP_K, for
    # the retrieved-set churn report below (Jon's addendum): recall@k only
    # checks whether the gold ids showed up, not what else moved.
    individual_by_arm: dict[tuple[str, str], list[list[Retrieved]]] = {}
    # (q.id, arm_name) -> the per-rewrite rankings that fed that arm's fused
    # result, kept for the `+orig` pass below.
    hits_any = {name: {k: 0 for k in KS} for name in method_names}
    hits_all = {name: {k: 0 for k in KS} for name in method_names}
    # --match-both only: same rankings, scored a second way (forced any /
    # forced all) with zero extra retrieval calls -- populated in the same
    # per-question loop below, printed as two extra columns afterward.

    for q in questions:
        bm = bm25.search(q.question, DEPTH)
        vec = vstore.search_vec(qvecs[q.question], DEPTH)  # cached query vector
        rankings = {
            "BM25": bm,
            VECTOR_MODEL: vec,
            "hybrid-RRF": rrf_fuse([bm, vec]),
            f"hybrid-wt{MAIN_ALPHA}": weighted_fuse([bm, vec], [1 - MAIN_ALPHA, MAIN_ALPHA]),
        }
        # rerank stage two: reorder the vector top-RERANK_POOL pool (cached)
        for m in RERANK_MODELS:
            rankings[f"rerank:{m}"] = cached_rerank(
                q.question, vec[:RERANK_POOL], m, rerank_cache, chunk_map
            )
        # rewrite arms
        for label in REWRITE_MODELS:
            for n_rw in REWRITE_NS:
                arm = rewrite_arm_name(label, n_rw)
                fused, individual = rewrite_rankings(q.id, label, n_rw)
                rankings[arm] = fused
                individual_by_arm[(q.id, arm)] = individual

        for name, ranking in rankings.items():
            for k in KS:
                if hit_at(q, ranking, k):
                    hits[name][k] += 1
                if args.match_both:
                    if hit_at_forced(q, ranking, k, "any"):
                        hits_any[name][k] += 1
                    if hit_at_forced(q, ranking, k, "all"):
                        hits_all[name][k] += 1
            per_q5[name][q.id] = hit_at(q, ranking, 5)
            top_gen_k[name][q.id] = [r.chunk.source_id for r in ranking[:GEN_TOP_K]]
        for a in ALPHA_SWEEP:
            if hit_at(q, weighted_fuse([bm, vec], [1 - a, a]), 5):
                sweep5[a] += 1

    # rerank_cache is a KVCache -- every new entry is already committed to
    # data/cache.db by cached_rerank()'s put() call above; no flush needed.

    # --- +orig variant ----------------------------------------------------
    # Spike finding: fusing a rewrite arm with the original question hurt on
    # the one question it was tried on. This re-tests that across all 31
    # questions, against whichever of the four cells actually scored best,
    # rather than trusting the one-question spike result.
    best_arm = max(rw_arm_names, key=lambda name: hits[name][5])
    orig_arm = f"{best_arm}+orig"
    hits[orig_arm] = {k: 0 for k in KS}
    per_q5[orig_arm] = {}
    hits_any[orig_arm] = {k: 0 for k in KS}
    hits_all[orig_arm] = {k: 0 for k in KS}
    for q in questions:
        vec = vstore.search_vec(qvecs[q.question], DEPTH)
        individual = individual_by_arm[(q.id, best_arm)]
        ranking = rrf_fuse(individual + [vec])
        for k in KS:
            if hit_at(q, ranking, k):
                hits[orig_arm][k] += 1
            if args.match_both:
                if hit_at_forced(q, ranking, k, "any"):
                    hits_any[orig_arm][k] += 1
                if hit_at_forced(q, ranking, k, "all"):
                    hits_all[orig_arm][k] += 1
        per_q5[orig_arm][q.id] = hit_at(q, ranking, 5)

    method_names = method_names + [orig_arm]
    matrix_names = matrix_names + [orig_arm]

    # comparison table
    header = f"{'retriever':<20}" + "".join(f"recall@{k:<5}" for k in KS)
    print(header)
    print("-" * len(header))
    for name in method_names:
        print(f"{name:<20}" + "".join(f"{hits[name][k]/n_scored:>7.0%}   " for k in KS))

    print("\nweighted-fusion alpha sweep (recall@5, alpha = vector weight):")
    print("  " + "   ".join(f"a={a}: {sweep5[a]/n_scored:.0%}" for a in ALPHA_SWEEP))

    if args.match_both:
        # Same top-k as the table above, scored a second/third way -- no
        # extra retrieval calls (Jon's call, docs/plan-rulesguru-import.md
        # decision #1). The gap between the two columns measures how many
        # context-extra citations the retriever drops relative to what's
        # strictly required.
        print(f"\n--match-both: recall@k under FORCED any vs FORCED all (ignores each question's own `match` field):")
        header2 = f"{'retriever':<20}" + "".join(f"any@{k:<3}/all@{k:<3}" for k in KS)
        print(header2)
        print("-" * len(header2))
        for name in method_names:
            row = "".join(
                f"{hits_any[name][k]/n_scored:>6.0%}/{hits_all[name][k]/n_scored:<6.0%}"
                for k in KS
            )
            print(f"{name:<20}{row}")

    # per-question hit@5 matrix (pipeline progression: BM25 -> vector -> rerank -> rewrite)
    print("\nPer-question hit@5 (Y=hit, .=miss):")
    print(f"{'qid':<6}{'match':<6}" + "".join(f"{name[:16]:<18}" for name in matrix_names) + "question")
    for q in questions:
        marks = "".join(f"{'Y' if per_q5[name][q.id] else '.':<18}" for name in matrix_names)
        print(f"{q.id:<6}{q.match:<6}{marks}{q.question[:44]}")

    # --- retrieved-set churn (Jon's addendum, 2026-07-21) ------------------
    # recall@k only checks whether the gold ids showed up -- it's blind to
    # everything else that moved. This shows what actually changed in the
    # generator's real context window (GEN_TOP_K, imported from
    # generate/answer.py so it can't drift from what RulesAgent actually
    # uses) between the pure-vector baseline and the best-scoring rewrite
    # arm, so it's possible to eyeball whether rewriting swaps in a
    # meaningfully different (better or worse) rule set, not just a
    # different recall number.
    print(f"\nRetrieved-set churn ({VECTOR_MODEL} top-{GEN_TOP_K} vs {best_arm} top-{GEN_TOP_K}):")
    changed_counts = []
    unchanged = 0
    for q in questions:
        base_ids = top_gen_k[VECTOR_MODEL][q.id]
        arm_ids = top_gen_k[best_arm][q.id]
        dropped = [c for c in base_ids if c not in arm_ids]
        added = [c for c in arm_ids if c not in base_ids]
        changed_counts.append(len(dropped))
        if not dropped and not added:
            unchanged += 1
            continue
        print(f"  {q.id}  {q.question[:50]}")
        print(f"    dropped: {dropped}")
        print(f"    added:   {added}")
    mean_changed = sum(changed_counts) / len(changed_counts) if changed_counts else 0.0
    print(f"\n  mean chunks changed per question: {mean_changed:.1f} / {GEN_TOP_K}")
    print(f"  unchanged questions: {unchanged}/{n}")

    # --- regressions vs the pure-vector baseline (hit@5) -------------------
    # The success bar is zero flips; any flip gets reported explicitly,
    # never averaged away.
    print(f"\nRegressions vs pure-vector baseline (hit@5, baseline={VECTOR_MODEL!r}):")
    any_regression = False
    for name in method_names:
        if name == VECTOR_MODEL:
            continue
        flips = [q.id for q in questions if per_q5[VECTOR_MODEL][q.id] and not per_q5[name][q.id]]
        if flips:
            any_regression = True
            print(f"  {name}: {flips}")
    if not any_regression:
        print("  none")

    # --- clarification report ----------------------------------------------
    # Plan's bar: <= 5 of 31 questions flagged. Higher means the prompt is
    # too eager to ask and should be tightened before shipping.
    print(f"\nClarification report (non-null clarification; bar: <= 5 of {n}):")
    for label in REWRITE_MODELS:
        for n_rw in REWRITE_NS:
            flagged = [q.id for q in questions if rewrites[(q.id, label, n_rw)].clarification]
            print(f"  {rewrite_arm_name(label, n_rw):<16}: {len(flagged)}/{n} -> {flagged}")


if __name__ == "__main__":
    main()
