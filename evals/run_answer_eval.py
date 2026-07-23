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

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent))  # so `from run_eval import ...` resolves
# regardless of the caller's cwd -- evals/ isn't part of the installed
# rulesagent package, it's a scripts directory, so it needs to be on
# sys.path explicitly rather than relying on script-directory auto-insertion.

from run_eval import CR_PATH, PARSED_DIR, VECTOR_MODEL, load_questions  # noqa: E402

from rulesagent.contracts import Answer  # noqa: E402
from rulesagent.generate.answer import GEN_MODEL, RulesAgent, _degenerate  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402
from rulesagent.tools.scryfall import ATTRIBUTION  # noqa: E402

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


def _answer_from_frozen_prompt(client, model: str, system: str, user: str) -> Answer:
    """Generate straight from an already-assembled (system, user) pair,
    bypassing RulesAgent.answer()'s retrieval/rewrite/assembly entirely --
    used only when --prompts-cache supplies a frozen prompt (docs/plan-v3-
    execution-tasks.md Task 2: genuine cross-arm AND cross-run byte-identity
    requires every arm/run to generate from the literal same prompt bytes,
    which RulesAgent.answer()'s live, uncached Voyage query embedding can't
    guarantee -- see --prompts-cache's help text for the measured drift).

    Deliberately duplicates RulesAgent.answer()'s generation-call tail
    (retry-on-empty/degenerate, ATTRIBUTION suffix) rather than modifying
    RulesAgent itself -- same "copy the pattern into the eval script rather
    than touch the class under test" choice run_openrouter_arm.py's
    _RecordingClient already makes (see its own docstring), so the
    incumbent/go-no-go-critical sonnet path in answer.py stays untouched.
    Kept in sync by hand; if RulesAgent.answer()'s tail changes, this must
    be re-copied. cards_present is inferred from the frozen user string
    (build_prompt() only appends "\\n\\nCard data:\\n" when cards is
    non-empty) rather than threaded separately, since the prompts-cache
    stores only the two assembled strings."""
    msgs: list[dict] = [{"role": "user", "content": user}]
    parsed, response = None, None
    weak = None
    for _attempt in range(2):
        try:
            response = client.messages.parse(
                model=model, max_tokens=16384, system=system, messages=msgs,
                output_format=Answer,
            )
            parsed = response.parsed_output
        except ValidationError:
            parsed = None
        if parsed is not None and _degenerate(parsed):
            if weak is None or len(parsed.text) > len(weak.text):
                weak = parsed
            parsed = None
        if parsed is not None:
            break
    if parsed is None and weak is not None:
        parsed = weak
    if parsed is None:
        stop = response.stop_reason if response is not None else "error"
        return Answer(
            text="(no structured answer: the model returned empty output "
            f"twice, stop_reason={stop} -- try again)",
            tldr="Something went wrong generating this answer -- try again.",
            citations=[], answered=False, suggested_followups=[],
        )
    if "\n\nCard data:\n" in user:
        parsed.text = f"{parsed.text}\n\n{ATTRIBUTION}"
    return parsed


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
    p.add_argument(
        "--rewrite-version", choices=["v1", "v2"], default="v2",
        help="rewriter SYSTEM prompt version, threaded into RulesAgent(rewrite_version=...) "
        "(default: v2 -- the shipped default; prompt-v3 A/B condition B needs v1, docs/"
        "plan-v3-execution-tasks.md Task 2)",
    )
    p.add_argument(
        "--ruling-query-mode", choices=["raw", "union"], default="raw",
        help="Part B ruling-query selection mode, threaded into RulesAgent(ruling_query_mode="
        "...) (default: raw -- the shipped default; prompt-v3 A/B condition D needs union)",
    )
    p.add_argument(
        "--condition", default=None,
        help="prompt-v3 A/B condition label (e.g. B/C/D), stamped into each output row's "
        "'condition' field for provenance -- purely informational, has no effect on the run",
    )
    p.add_argument(
        "--run", type=int, default=None,
        help="which of the two independent generation runs this is (1 or 2), stamped into "
        "each output row's 'run' field for provenance -- purely informational",
    )
    p.add_argument(
        "--prompts-cache", type=Path, default=None,
        help="path to a JSON {qid: {system, user}} prompt cache built by "
        "evals/run_openrouter_arm.py --assemble-only. When given, every question's "
        "assembled prompt is READ from this file (via _answer_from_frozen_prompt(), "
        "bypassing RulesAgent's own retrieval/assembly) instead of calling agent.answer() "
        "fresh -- required for genuine cross-arm byte-identity with the OpenRouter arms "
        "sharing the same cache. Rows generated this way carry empty rewrite_queries/"
        "clarification (RulesAgent never ran its rewrite step) -- an honest gap, same "
        "treatment build_arm_review.py already gives the non-native OpenRouter rows.",
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
    agent = RulesAgent(
        store, model=args.model, rewrite=args.rewrite, show_rewrite=args.show_rewrite,
        rewrite_version=args.rewrite_version, ruling_query_mode=args.ruling_query_mode,
        # card_no_refresh=True: eval-reproducibility freeze mode (plan #3b) --
        # use any cached Scryfall entry regardless of TTL age. Previously
        # unset (defaulted False) on this native-sonnet path while
        # run_openrouter_arm.py's _capture_prompt() already set it True for
        # every OpenRouter arm -- an inconsistency that could let a card's
        # oracle text/rulings drift (a live TTL refresh) between the sonnet
        # arm's prompt and every other arm's prompt for the identical
        # question, undermining the cross-arm byte-identity guarantee the
        # prompt-v3 A/B depends on. Set here so all six arms read cards from
        # the same frozen cache during the A/B.
        card_no_refresh=True,
    )

    prompts_cache = None
    if args.prompts_cache is not None:
        if not args.prompts_cache.exists():
            print(f"[ERROR] --prompts-cache {args.prompts_cache} does not exist -- "
                  f"build it first with evals/run_openrouter_arm.py --assemble-only")
            return
        cached = json.loads(args.prompts_cache.read_text(encoding="utf-8"))
        if cached["rewrite_version"] != args.rewrite_version or cached["ruling_query_mode"] != args.ruling_query_mode:
            print(f"[ERROR] --prompts-cache {args.prompts_cache} was built with "
                  f"rewrite_version={cached['rewrite_version']!r}/ruling_query_mode="
                  f"{cached['ruling_query_mode']!r}, but this run asked for "
                  f"rewrite_version={args.rewrite_version!r}/ruling_query_mode="
                  f"{args.ruling_query_mode!r} -- refusing to silently mix configs")
            return
        prompts_cache = cached["prompts"]

    questions = load_questions(args.questions)
    answer_gold = load_answer_gold(args.questions)
    if args.limit is not None:
        questions = questions[: args.limit]
    print(
        f"Generating {len(questions)} answers | model={args.model} "
        f"| rewrite={args.rewrite} | show_rewrite={args.show_rewrite} "
        f"| rewrite_version={args.rewrite_version} | ruling_query_mode={args.ruling_query_mode} "
        f"| condition={args.condition} | run={args.run} "
        f"| prompts_cache={args.prompts_cache} "
        f"| questions={args.questions.name}\n"
    )

    results = []
    start = time.time()
    for i, q in enumerate(questions, 1):
        t0 = time.time()
        if prompts_cache is not None:
            if q.id not in prompts_cache:
                print(f"[ERROR] question id {q.id!r} not found in {args.prompts_cache} -- "
                      f"the cache doesn't cover this question set")
                return
            ans = _answer_from_frozen_prompt(
                agent.client, args.model,
                prompts_cache[q.id]["system"], prompts_cache[q.id]["user"],
            )
        else:
            ans = agent.answer(q.question)
        rewritten = agent.last_rewritten  # None when --no-rewrite, or when using --prompts-cache

        gold_text = {g: chunk_map[g].text for g in q.gold if g in chunk_map}
        cited_text = {c: chunk_map[c].text for c in ans.citations if c in chunk_map}

        row = {
            "id": q.id,
            "question": q.question,
            "match": q.match,
            "kind": q.kind,
            "show_rewrite": args.show_rewrite,
            "rewrite_version": args.rewrite_version,
            "ruling_query_mode": args.ruling_query_mode,
            "condition": args.condition,
            "run": args.run,
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
