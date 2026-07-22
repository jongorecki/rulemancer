"""OpenRouter generation arm eval runner (docs/plan-openrouter-models.md,
steps C + D's task 1 and task 3).

Runs the SAME eval question set (evals/questions.jsonl + evals/cards.jsonl)
through a non-Claude generator on OpenRouter, holding retrieval/rewrite/card
enrichment fixed -- the generation A/B the plan calls for.

A separate script from run_answer_eval.py, not a --backend flag bolted onto
it, because the two harnesses' shapes diverge too much to share cleanly:
  - run_answer_eval.py calls RulesAgent.answer() straight through to a REAL
    Anthropic client and records the parsed Answer it returns.
  - This script needs the assembled PROMPT (system, user) WITHOUT ever
    calling Anthropic -- so it intercepts RulesAgent's own client with a
    recording fake (tests/test_prompt_identity.py's _RecordingClient
    pattern, copied verbatim below: the fake raises the instant
    .messages.parse() is called, with the call kwargs attached), then feeds
    that exact prompt to openrouter_backend.generate() instead. Retrieval,
    the query rewriter, and card enrichment all run for real -- the fake
    only ever intercepts the FINAL generation call. This works because every
    eval question's rewrite is already warm in the `rewrite` table and every
    referenced card is already warm in the `scryfall` table (both in
    data/cache.db as of L3, docs/plan-l3-sqlite-caches.md -- previously
    data/parsed/rewrite_cache.pkl / scryfall_cache.json; verified for all 50
    rows before writing this), so rewrite_query() returns from its cache and
    never reaches the fake client at all.

Result records carry the plan's attribution fields straight off
openrouter_backend.ORResult (served_model/provider/temperature_sent/
seed_sent/usage) so a run is honest about what actually served it, not just
what was requested.

NOT frozen here: query embeddings. run_answer_eval.py's RulesAgent path has
no embedding-freeze hook either (VectorStore.search() always embeds live via
Voyage) -- freezing it would mean monkeypatching internals of answer.py,
which is out of scope (READ ONLY). This is the same minor Voyage-wobble
caveat tests/test_prompt_identity.py's c015 test already documents for the
existing single-arm path; it isn't a new limitation this script introduces.

Cost/sequencing standing rules (DESIGN.md, plan-openrouter-models.md):
- Never runs while the app server is answering; arms run sequentially, one
  model at a time -- this script makes no attempt to parallelize across
  questions or arms.
- allow_fallbacks=False is openrouter_backend.py's job, unmodified here.

Run: `uv run python evals/run_openrouter_arm.py --model <openrouter-id>
      [--questions PATH] [--cards PATH] [--limit N] [--variance] [--out PATH]`
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # so `from run_eval import ...` resolves
# regardless of the caller's cwd -- same reasoning as run_answer_eval.py's identical line.

from run_eval import CR_PATH, PARSED_DIR, VECTOR_MODEL, load_questions  # noqa: E402

from rulesagent.generate import openrouter_backend  # noqa: E402
from rulesagent.generate.answer import RulesAgent  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402

QUESTIONS_PATH = Path(__file__).parent / "questions.jsonl"
CARDS_PATH = Path(__file__).parent / "cards.jsonl"
ANSWERS_DIR = Path(__file__).parent / "answers"

VARIANCE_IDS = ("q001", "q014", "c015")  # the plan's task-3 spot-check set
VARIANCE_DRAWS = 3


class _Recorded(Exception):
    """Raised by _RecordingClient the instant .messages.parse() is called --
    unwinds RulesAgent.answer() with the call kwargs attached, before it ever
    reaches the real Anthropic API. Copied from
    tests/test_prompt_identity.py's _RecordingClient pattern verbatim."""


class _RecordingClient:
    def __init__(self):
        self.messages = self

    def parse(self, **kwargs):
        self.kwargs = kwargs
        raise _Recorded


def _capture_prompt(store: VectorStore, question: str) -> tuple[str, str]:
    """tests/test_prompt_identity.py's _capture() helper, verbatim pattern: a
    fresh RulesAgent + fresh recording client per question, so no state leaks
    between calls. Runs retrieval/rewrite/card-enrichment for real (warm
    caches -> no Anthropic call happens during rewrite either) and raises
    _Recorded the instant the generation call would go out. Never touches the
    Anthropic API -- there is no live client anywhere in this call chain."""
    client = _RecordingClient()
    agent = RulesAgent(store, client=client, card_no_refresh=True)
    try:
        agent.answer(question)
    except _Recorded:
        pass
    else:
        raise RuntimeError(
            f"expected _Recorded for {question!r} but answer() returned normally -- "
            "the recording client didn't intercept the generation call"
        )
    kw = client.kwargs
    return kw["system"], kw["messages"][0]["content"]


def _slug_for(model: str) -> str:
    return model.replace("/", "-").replace(".", "-")


def _answer_row(qid: str, question: str, result: openrouter_backend.ORResult) -> dict:
    row = {
        "id": qid,
        "question": question,
        "served_model": result.served_model,
        "provider": result.provider,
        "temperature_sent": result.temperature_sent,
        "seed_sent": result.seed_sent,
        "usage": result.usage,
    }
    if result.answer is not None:
        row["answered"] = result.answer.answered
        row["text"] = result.answer.text
        row["citations"] = result.answer.citations
        row["error"] = None
        row["raw_text"] = None
    else:
        row["answered"] = None
        row["text"] = None
        row["citations"] = None
        row["error"] = result.error
        row["raw_text"] = result.raw_text
    return row


def _first_diff(a: str, b: str) -> int | None:
    """Index of the first byte where a and b differ, or None if identical.
    A length mismatch with an identical shared prefix reports the shared
    length as the divergence point (that's where they stop agreeing)."""
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def _load_all_questions() -> dict[str, str]:
    """id -> question text, from BOTH eval files -- what --variance looks up
    q001/q014/c015 in, independent of whatever --questions/--limit the main
    loop was given."""
    out = {q.id: q.question for q in load_questions(QUESTIONS_PATH)}
    out.update({q.id: q.question for q in load_questions(CARDS_PATH)})
    return out


def run_variance(store: VectorStore, model: str) -> dict:
    """Task 3: for q001/q014/c015, draw VARIANCE_DRAWS answers each from the
    SAME captured prompt and report whether the draws are byte-identical --
    the honest question for any temp=0 arm (temp=0 reduces draw variance, it
    does not guarantee it -- same caveat openrouter_backend.py documents)."""
    all_q = _load_all_questions()
    out = {}
    for qid in VARIANCE_IDS:
        question = all_q.get(qid)
        if question is None:
            out[qid] = {"error": f"question id {qid!r} not found in questions.jsonl/cards.jsonl"}
            continue
        system, user = _capture_prompt(store, question)
        texts = []
        for draw in range(VARIANCE_DRAWS):
            result = openrouter_backend.generate(system, user, model)
            text = result.answer.text if result.answer is not None else f"(ERROR: {result.error})"
            texts.append(text)
            print(f"    variance {qid} draw {draw + 1}/{VARIANCE_DRAWS} "
                  f"({'ok' if result.answer is not None else 'FAIL'})")
        lengths = [len(t) for t in texts]
        diffs_vs_first = [_first_diff(texts[0], t) for t in texts[1:]]
        identical = all(d is None for d in diffs_vs_first)
        entry = {"byte_identical": identical, "lengths": lengths}
        if not identical:
            # "vs_draw0": one entry per later draw -- None where that draw matched
            # draw 0, else the first index they diverge at.
            entry["first_divergence_vs_draw0"] = diffs_vs_first
        out[qid] = entry
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True,
                    help="OpenRouter model id to generate with, e.g. deepseek/deepseek-v4-flash")
    p.add_argument("--questions", type=Path, default=QUESTIONS_PATH,
                    help=f"rules-only eval questions jsonl (default: {QUESTIONS_PATH})")
    p.add_argument("--cards", type=Path, default=CARDS_PATH,
                    help=f"card eval questions jsonl (default: {CARDS_PATH})")
    p.add_argument("--out", type=Path, default=None,
                    help="output path (default: evals/answers/openrouter_<model-slug>.json)")
    p.add_argument("--limit", type=int, default=None,
                    help="answer only the first N questions of the COMBINED (questions+cards) "
                         "set (default: all) -- for cheap smoke slices; 0 skips the main loop "
                         "entirely (useful with --variance for a spot-check-only run)")
    p.add_argument("--variance", action="store_true",
                    help="also run the q001/q014/c015 x3-draw spot-check (Task 3) and store it "
                         "under the 'variance' key of the output JSON")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_path = args.out or (ANSWERS_DIR / f"openrouter_{_slug_for(args.model)}.json")

    pkl = PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl"
    if not pkl.exists():
        print(f"[ERROR] no vector index at {pkl.name}; run build_vector_indexes.py")
        return
    store = VectorStore.load(pkl)

    questions = load_questions(args.questions) + load_questions(args.cards)
    if args.limit is not None:
        questions = questions[: args.limit]

    print(f"Generating {len(questions)} answers | model={args.model} | out={out_path}\n")

    results = []
    start = time.time()
    for i, q in enumerate(questions, 1):
        t0 = time.time()
        system, user = _capture_prompt(store, q.question)
        result = openrouter_backend.generate(system, user, args.model)
        results.append(_answer_row(q.id, q.question, result))
        status = "ok" if result.answer is not None else f"FAIL ({result.error})"
        print(f"  [{i}/{len(questions)}] {q.id} -> {status} ({time.time() - t0:.1f}s)")

    answered = sum(1 for r in results if r["answered"] is True)
    parse_failures = sum(1 for r in results if r["text"] is None)
    total_cost = sum((r["usage"] or {}).get("cost", 0) or 0 for r in results)

    variance = None
    if args.variance:
        print("\nVariance spot-check (q001/q014/c015, 3 draws each):")
        variance = run_variance(store, args.model)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": args.model,
        "results": results,
        "summary": {
            "n_questions": len(results),
            "answered": answered,
            "parse_failures": parse_failures,
            "total_cost": total_cost,
        },
        "variance": variance,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(results)} answers -> {out_path} in {time.time() - start:.1f}s")
    print(f"  answered:       {answered}/{len(results)}")
    print(f"  parse failures: {parse_failures}/{len(results)}")
    print(f"  total cost:     ${total_cost:.4f}")


if __name__ == "__main__":
    main()
