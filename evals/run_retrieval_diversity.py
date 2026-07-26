"""8-way retrieval-diversity factorial: MMR x hybrid x multi-query.

Spec: docs/spec-retrieval-diversity.md. Ruled by Jon 2026-07-25.

WHY a separate harness instead of extending run_eval.py: run_eval.py produced
every retrieval number quoted so far, and it picks its comparison baseline
DYNAMICALLY (`best_arm = max(rw_arm_names, ...)`). Adding arms to it would
silently change what past runs are compared against. It stays frozen as the
historical instrument; this file imports from it and edits nothing.

The factorial is orthogonal by construction:

    semantic ranking S := vec                      (no MQ)
                       |  rrf_fuse(3 rewrites)     (MQ)
    hybrid            := S  |  rrf_fuse([bm25, S])
    mmr               := identity  |  mmr_select(pool, lambda)

so "hybrid" always means "add the lexical ranking to whatever the semantic
ranking is", and MMR is always a selection stage on the finished pool. The
alternative for hybrid+MQ -- flat RRF over [bm25, rw1, rw2, rw3] -- was rejected
because it gives the rewrites three votes to BM25's one, which would confound
the hybrid factor with the multi-query factor.

ZERO API SPEND: MMR and hybrid are pure local math. Multi-query is pinned to
haiku n=3, which is 150/150 cached (450 rewrite strings, all embedded), and
--cache-only (default ON) raises on a miss rather than silently calling out.
Claude Code runs on Jon's Max subscription, but Python in this repo that builds
an Anthropic client bills API CREDITS -- so the guard is code, not intention.

Run: uv run python evals/run_retrieval_diversity.py
"""

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from rulesagent.cache import KVCache
from rulesagent.contracts import EvalQuestion, Retrieved, normalize_source_id
from rulesagent.index.bm25 import BM25Index
from rulesagent.index.store import VectorStore
from rulesagent.ingest.chunker import chunk_rules
from rulesagent.ingest.parser import parse_comprehensive_rules
from rulesagent.retrieve.hybrid import rrf_fuse
from rulesagent.retrieve.mmr import mmr_select
from run_eval import CR_PATH, PARSED_DIR, VECTOR_MODEL, gold_groups, hit_at, load_questions

REPO = Path(__file__).parent.parent
QUESTIONS = REPO / "evals" / "questions_rulesguru150_v3.jsonl"
POOL = 200  # candidates each base retriever returns, and the pool MMR reorders
KS = (5, 15, 50, 200)  # 15 is production TOP_K (generate/answer.py)
LAMBDAS = (1.0, 0.7, 0.5, 0.3)  # 1.0 is the self-test: must equal the non-MMR arm
REWRITE_MODEL = "claude-haiku-4-5"
REWRITE_VERSION = "v2"
REWRITE_NS = (1, 3)
# n=1 is what PRODUCTION runs today (generate/answer.py REWRITE_N = 1, with
# RulesAgent(rewrite=True) as the default), so it -- not the raw question -- is
# the arm any recommendation has to beat. n=3 is multi-query proper: three
# rewrites, three searches, RRF over the three rankings. Measuring both
# separates "rewriting at all" from "fusing several rewrites", which a single
# n=3 arm against a raw-question baseline silently conflates.
COVERAGE_K = 15


class CacheMiss(RuntimeError):
    """Raised instead of quietly billing API credits."""


def load_cached_rewrites(questions: list[EvalQuestion], n: int,
                         cache_only: bool) -> dict[str, list[str]]:
    """Read the haiku n=3 rewrites straight out of data/cache.db.

    rewrite.py stores value = json [[queries], clarification] under key =
    json [model, version, n, question]. We read the table directly rather than
    calling rewrite_query() so that a cache miss CANNOT fall through to an API
    call -- the whole point of the spend guard.
    """
    cache = KVCache("rewrite")
    out, missing = {}, []
    for q in questions:
        key = json.dumps([REWRITE_MODEL, REWRITE_VERSION, n, q.question])
        raw = cache.get(key)
        if raw is None:
            missing.append(q.id)
            continue
        val = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
        queries = [s for s in val[0] if s and s.strip()]
        out[q.id] = queries or [q.question]
    if missing:
        msg = (f"{len(missing)} question(s) have no cached {REWRITE_MODEL} "
               f"{REWRITE_VERSION} n={n} rewrite: {missing[:10]}")
        if cache_only:
            raise CacheMiss(msg + "\nRe-run with --allow-api to fetch them (bills API credits).")
        print(f"  [WARN] {msg}")
    return out


def load_cached_vectors(texts: list[str], cache_only: bool) -> dict[str, np.ndarray]:
    """Query embeddings, cache-only. Same guard, same reason."""
    kv = KVCache("query_emb")
    out, missing = {}, []
    for t in texts:
        raw = kv.get(t)
        if raw is None:
            missing.append(t)
            continue
        out[t] = pickle.loads(raw)
    if missing:
        msg = f"{len(missing)} query string(s) have no cached embedding"
        if cache_only:
            raise CacheMiss(msg + f"; first: {missing[0][:90]!r}"
                            "\nRe-run with --allow-api to embed them (bills API credits).")
        print(f"  [WARN] {msg}")
    return out


def group_coverage(q: EvalQuestion, ranking: list[Retrieved], k: int) -> float | None:
    """Fraction of the question's required gold groups present in the top-k.

    Exists because `groups` recall@15 sits at 10.1% -- a floor, where binary
    hit/miss can stay flat while retrieval genuinely improves. Going from 1-of-3
    to 2-of-3 groups on forty questions would otherwise register as nothing.
    Returns None for empty-gold rows so they stay out of the mean.
    """
    groups = gold_groups(q)
    if not q.gold or not groups:
        return None
    topk = {normalize_source_id(r.chunk.source_id) for r in ranking[:k]}
    hit = sum(1 for g in groups if any(normalize_source_id(x) in topk for x in g))
    return hit / len(groups)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--questions", type=Path, default=QUESTIONS)
    p.add_argument("--allow-api", action="store_true",
                   help="permit live API calls on cache miss (BILLS API CREDITS); "
                        "default is cache-only, which raises instead")
    p.add_argument("--out", type=Path, default=REPO / "evals" / "retrieval_diversity_results.json")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cache_only = not args.allow_api

    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    questions = load_questions(args.questions)
    bm25 = BM25Index(chunks)
    vstore = VectorStore.load(PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl")

    # source_id -> embedding row, so MMR can score ANY candidate's diversity --
    # including BM25-only hits that the vector arm never surfaced.
    vec_of = {c.source_id: vstore.embeddings[i] for i, c in enumerate(vstore.chunks)}
    dim = vstore.embeddings.shape[1]
    uncovered = [c.source_id for c in chunks if c.source_id not in vec_of]
    if uncovered:
        raise RuntimeError(f"{len(uncovered)} chunks have no embedding: {uncovered[:5]}")

    rw = {n: load_cached_rewrites(questions, n, cache_only) for n in REWRITE_NS}
    texts = ([q.question for q in questions]
             + [s for d in rw.values() for v in d.values() for s in v])
    qvec = load_cached_vectors(texts, cache_only)

    n_empty = sum(1 for q in questions if not q.gold)
    n_scored = (len(questions) - n_empty) or 1
    print(f"\n{len(chunks)} chunks | {len(questions)} questions ({n_empty} empty-gold, "
          f"excluded) | pool={POOL} | vector={VECTOR_MODEL}")
    print(f"rewrites: {REWRITE_MODEL} {REWRITE_VERSION} "
          + " ".join(f"n={n}:{len(rw[n])}/{len(questions)}" for n in REWRITE_NS)
          + f" | API calls: {'DISABLED (cache-only)' if cache_only else 'ALLOWED'}\n")

    base_names = ["vector", "rw1", "mq", "hybrid", "hybrid+rw1", "hybrid+mq"]
    arm_names = list(base_names) + [f"{b}+mmr{l}" for b in base_names for l in LAMBDAS]

    hits = {a: {k: 0 for k in KS} for a in arm_names}
    hits_by_mode = {a: {m: {k: 0 for k in KS} for m in ("any", "groups", "all")} for a in arm_names}
    cov = {a: [] for a in arm_names}
    per_q15 = {a: {} for a in arm_names}
    mode_n = {m: 0 for m in ("any", "groups", "all")}

    for q in questions:
        if q.gold:
            mode_n[q.match] += 1
        bm = bm25.search(q.question, POOL)
        vec = vstore.search_vec(qvec[q.question], POOL)
        # n=1: one rewrite, one search, no fusion -- production's config today.
        one = rw[1].get(q.id) or [q.question]
        rw1 = vstore.search_vec(qvec[one[0]], POOL)
        # n=3: three rewrites, three searches, RRF over the three rankings.
        three = [vstore.search_vec(qvec[s], POOL) for s in rw[3].get(q.id, [])]
        mq = rrf_fuse(three) if len(three) > 1 else (three[0] if three else vec)

        rankings = {
            "vector": vec,
            "rw1": rw1,
            "mq": mq,
            "hybrid": rrf_fuse([bm, vec]),
            "hybrid+rw1": rrf_fuse([bm, rw1]),
            "hybrid+mq": rrf_fuse([bm, mq]),
        }
        for b in base_names:
            pool = rankings[b][:POOL]
            vecs = np.array([vec_of.get(r.chunk.source_id, np.zeros(dim)) for r in pool])
            for lam in LAMBDAS:
                rankings[f"{b}+mmr{lam}"] = mmr_select(pool, vecs, k=len(pool), lambda_=lam)

        for a, ranking in rankings.items():
            for k in KS:
                if hit_at(q, ranking, k):
                    hits[a][k] += 1
                    if q.gold:
                        hits_by_mode[a][q.match][k] += 1
            per_q15[a][q.id] = hit_at(q, ranking, 15)
            c = group_coverage(q, ranking, COVERAGE_K)
            if c is not None:
                cov[a].append(c)

    # --- self-test: lambda=1.0 is pure relevance, so it MUST match its base arm
    print("Self-test (lambda=1.0 must reproduce the base arm at every k):")
    ok = True
    for b in base_names:
        same = all(hits[b][k] == hits[f"{b}+mmr1.0"][k] for k in KS)
        ok &= same
        print(f"  {b:<12} {'PASS' if same else 'FAIL'}")
    if not ok:
        raise RuntimeError("lambda=1.0 diverged from its base arm -- relevance term is wrong; "
                           "every number below would be meaningless")

    hdr = f"\n{'arm':<20}" + "".join(f"@{k:<7}" for k in KS) + f"{'cov@15':>9}"
    print(hdr)
    print("-" * len(hdr))
    for a in arm_names:
        c = sum(cov[a]) / len(cov[a]) if cov[a] else 0.0
        print(f"{a:<20}" + "".join(f"{hits[a][k]/n_scored:>6.1%} " for k in KS) + f"{c:>8.1%}")

    for mode in ("groups", "all", "any"):
        n = mode_n[mode] or 1
        print(f"\nmatch={mode}  (n={mode_n[mode]})")
        print(f"{'arm':<20}" + "".join(f"@{k:<7}" for k in KS))
        for a in arm_names:
            print(f"{a:<20}" + "".join(f"{hits_by_mode[a][mode][k]/n:>6.1%} " for k in KS))

    print("\nPaired flips vs 'vector' baseline at k=15 (won / lost):")
    for a in arm_names:
        if a == "vector":
            continue
        won = [q.id for q in questions if per_q15[a][q.id] and not per_q15["vector"][q.id]]
        lost = [q.id for q in questions if per_q15["vector"][q.id] and not per_q15[a][q.id]]
        print(f"  {a:<20} +{len(won):<3} -{len(lost):<3} {'lost: ' + ', '.join(lost[:6]) if lost else ''}")

    payload = {
        "questions": str(args.questions.name), "pool": POOL, "ks": list(KS),
        "lambdas": list(LAMBDAS), "n_scored": n_scored, "mode_n": mode_n,
        "recall": {a: {str(k): hits[a][k] / n_scored for k in KS} for a in arm_names},
        "recall_by_mode": {a: {m: {str(k): hits_by_mode[a][m][k] / (mode_n[m] or 1) for k in KS}
                               for m in mode_n} for a in arm_names},
        "coverage_at_15": {a: (sum(cov[a]) / len(cov[a]) if cov[a] else 0.0) for a in arm_names},
        "per_question_hit_at_15": per_q15,
    }
    args.out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nwrote {args.out.relative_to(REPO).as_posix()}")


if __name__ == "__main__":
    main()
