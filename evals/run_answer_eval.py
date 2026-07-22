"""Answer eval: generate a cited answer for every eval question and write the
review file Jon grades by hand.

This is the script that produced data/parsed/review.json originally -- run ad
hoc and never committed (plan #3a, slice 4). It's a real script now, with a
--rewrite/--no-rewrite flag so both arms (query rewriting on vs off) are
runnable and comparable.

Takes well over 120s for 31 questions (one generation call per question, plus
one rewrite call per question when --rewrite is on) -- run it in the
background or with a long timeout, not inline with a short one.

Run: `uv run python evals/run_answer_eval.py [--rewrite | --no-rewrite]
      [--model MODEL] [--out PATH] [--questions PATH] [--limit N]`
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # so `from run_eval import ...` resolves
# regardless of the caller's cwd -- evals/ isn't part of the installed
# rulesagent package, it's a scripts directory, so it needs to be on
# sys.path explicitly rather than relying on script-directory auto-insertion.

from run_eval import CR_PATH, PARSED_DIR, VECTOR_MODEL, load_questions  # noqa: E402

from rulesagent.generate.answer import GEN_MODEL, RulesAgent  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402

QUESTIONS_PATH = Path(__file__).parent / "questions.jsonl"
DEFAULT_OUT = PARSED_DIR / "review.json"


def load_answer_gold(path: Path) -> dict[str, str]:
    """id -> answer_gold, read straight from the raw jsonl rows.

    `answer_gold` (RulesGuru's human-written reference answer) isn't a field
    on EvalQuestion/contracts.py -- it's exactly the kind of extra field
    load_questions() is required to ignore -- so it has to be recovered from
    the raw JSON here rather than off the loaded EvalQuestion objects. Rows
    without it (questions.jsonl, cards.jsonl) just don't appear in the dict.
    """
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("answer_gold"):
            out[row["id"]] = row["answer_gold"]
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--rewrite",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="rewrite the question before retrieving (default: on -- plan #3a's shipped config)",
    )
    p.add_argument(
        "--show-rewrite",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="show the generator the rewrite too, so it can flag intent drift "
        "(EXPERIMENTAL, default off -- see RulesAgent.show_rewrite; may empty citations)",
    )
    p.add_argument("--model", default=GEN_MODEL, help=f"generator model (default: {GEN_MODEL})")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output path (default: {DEFAULT_OUT})")
    p.add_argument(
        "--questions", type=Path, default=QUESTIONS_PATH,
        help=f"eval questions jsonl (default: {QUESTIONS_PATH})",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="answer only the first N questions (default: all) -- for cheap smoke slices",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_map = {c.source_id: c for c in chunks}

    pkl = PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl"
    if not pkl.exists():
        print(f"[ERROR] no vector index at {pkl.name}; run build_vector_indexes.py")
        return
    store = VectorStore.load(pkl)
    agent = RulesAgent(store, model=args.model, rewrite=args.rewrite, show_rewrite=args.show_rewrite)

    questions = load_questions(args.questions)
    answer_gold = load_answer_gold(args.questions)
    if args.limit is not None:
        questions = questions[: args.limit]
    print(
        f"Generating {len(questions)} answers | model={args.model} "
        f"| rewrite={args.rewrite} | show_rewrite={args.show_rewrite} "
        f"| questions={args.questions.name}\n"
    )

    results = []
    start = time.time()
    for i, q in enumerate(questions, 1):
        t0 = time.time()
        ans = agent.answer(q.question)
        rewritten = agent.last_rewritten  # None when --no-rewrite

        gold_text = {g: chunk_map[g].text for g in q.gold if g in chunk_map}
        cited_text = {c: chunk_map[c].text for c in ans.citations if c in chunk_map}

        row = {
            "id": q.id,
            "question": q.question,
            "match": q.match,
            "kind": q.kind,
            "show_rewrite": args.show_rewrite,
            "answered": ans.answered,
            "answer": ans.text,
            "citations": ans.citations,
            "gold": q.gold,
            "gold_text": gold_text,
            "cited_text": cited_text,
            # New in plan #3a: what the rewriter actually did for this
            # question, so a reviewer can see whether an answer change
            # traces back to a different rewrite. None/[] when
            # --no-rewrite so the two arms stay visibly distinguishable
            # in the output, not just via a side channel.
            "rewrite_queries": rewritten.queries if rewritten else [],
            "clarification": rewritten.clarification if rewritten else None,
        }
        if q.id in answer_gold:
            # Carried through only for questions that have it (RulesGuru
            # rows) -- judge_rulesguru.py reads it straight off this row
            # rather than re-joining against the source jsonl.
            row["answer_gold"] = answer_gold[q.id]
        results.append(row)
        print(f"  [{i}/{len(questions)}] {q.id} ({time.time() - t0:.1f}s)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Objective health checks so the show_rewrite A/B and the decline behavior
    # don't need eyeballing all 31 answers to summarize.
    declined = [r["id"] for r in results if not r["answered"]]
    empty_cit = [r["id"] for r in results if not r["citations"]]
    confident_uncited = [r["id"] for r in results if r["answered"] and not r["citations"]]
    print(f"\nWrote {len(results)} answers to {args.out} in {time.time() - start:.1f}s")
    print(f"  declined (answered=false): {len(declined)} -> {declined}")
    print(f"  empty citations:           {len(empty_cit)} -> {empty_cit}")
    print(f"  CONFIDENT BUT UNCITED (answered=true, citations=[]): "
          f"{len(confident_uncited)} -> {confident_uncited}")


if __name__ == "__main__":
    main()
