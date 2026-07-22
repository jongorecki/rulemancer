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
from rulesagent.generate.answer import REWRITE_MODEL, REWRITE_N, RulesAgent  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402
from rulesagent.retrieve.rewrite import rewrite_query  # noqa: E402
from rulesagent.tools.ruling_retrieval import select_rulings, select_rulings_union  # noqa: E402
from rulesagent.tools.scryfall import get_card  # noqa: E402

QUESTIONS_PATH = Path(__file__).parent / "questions.jsonl"
CARDS_PATH = Path(__file__).parent / "cards.jsonl"
ANSWERS_DIR = Path(__file__).parent / "answers"

# Part B (docs/plan-l1-crossref-expansion.md): question id -> {card name (as
# it appears in that row's "cards" list) -> [load-bearing ruling indices]},
# manually transcribed from each row's Jon-authored "note" field in
# cards.jsonl -- not regex-parsed from the free text, because several notes
# name ruling numbers for MULTIPLE cards in one paragraph and an automated
# attribution step risks assigning a ruling to the wrong card. This is the
# measurement's ground truth for "did the load-bearing ruling make the cut."
LOAD_BEARING_RULINGS = {
    "c006": {"Fork": [8]},
    "c007": {"Mimic Vat": [0]},
    "c008": {"Lithoform Engine": [4]},
    "c009": {"Teferi's Protection": [21]},
    "c010": {"Emrakul, the Promised End": [2, 3]},
    "c011": {"Valki, God of Lies": [17]},
    "c012": {"Lithoform Engine": [6, 7, 14], "Emrakul, the Promised End": [14]},
    "c013": {"Mimic Vat": [4], "Lithoform Engine": [6, 7]},
    "c014": {"Trinisphere": [0]},
    "c015": {"Grist, the Hunger Tide": [1], "Animate Dead": [1, 4]},
    "c016": {"Skullbriar, the Walking Grave": [2]},
    "c017": {"Sundial of the Infinite": [1, 4]},
    "c018": {"Clone": [0]},
    "c019": {"Gogo, Master of Mimicry": [2, 10, 12]},
}

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


def ruling_query_report(mode: str) -> dict:
    """Part B measurement (docs/plan-l1-crossref-expansion.md): for every
    ruling-bearing cards.jsonl question in LOAD_BEARING_RULINGS, check
    whether the load-bearing ruling(s) clear the floor / make the cut under
    today's shipped RAW-question selection, and -- when mode=="union" --
    under the union-with-Haiku-rewrite arm. MEASURE ONLY: this never touches
    RulesAgent or what a real answer's prompt contains; select_rulings() /
    select_rulings_union() are called directly against the eval question
    text, exactly the query RulesAgent.answer() would select rulings against
    for the SAME question when ruling_select is on (see generate/answer.py).

    `rewrite_query` is called with client=None -- every cards.jsonl question
    already has a warm rewrite-cache entry from prior full eval runs (see
    this module's docstring), so this makes zero live Anthropic calls; a
    cold cache would raise inside rewrite_query's own `anthropic.Anthropic()`
    construction (no API key configured for this measurement on purpose --
    a cache miss should fail loud, not silently spend a call).
    """
    all_cards_q = {q.id: q for q in load_questions(CARDS_PATH)}
    rows = []
    for qid, per_card in LOAD_BEARING_RULINGS.items():
        q = all_cards_q.get(qid)
        if q is None:
            rows.append({"id": qid, "error": "question id not found in cards.jsonl"})
            continue
        rewrites: list[str] = []
        if mode == "union":
            rw = rewrite_query(q.question, REWRITE_MODEL, REWRITE_N, client=None, context=None)
            rewrites = rw.queries
        for card_name, load_bearing in per_card.items():
            card = get_card(card_name, no_refresh=True)
            if card is None:
                rows.append({"id": qid, "card": card_name, "error": "card not found (cold Scryfall cache)"})
                continue
            raw_sel = {i for i, _ in select_rulings(card, q.question)}
            row = {
                "id": qid,
                "card": card_name,
                "load_bearing": load_bearing,
                "raw_selected_indices": sorted(raw_sel),
                "raw_all_clear": all(i in raw_sel for i in load_bearing),
                "raw_missing": [i for i in load_bearing if i not in raw_sel],
            }
            if mode == "union":
                union_sel = {i for i, _ in select_rulings_union(card, [q.question] + rewrites)}
                row.update({
                    "rewrites": rewrites,
                    "union_selected_indices": sorted(union_sel),
                    "union_all_clear": all(i in union_sel for i in load_bearing),
                    "union_missing": [i for i in load_bearing if i not in union_sel],
                })
            rows.append(row)

    n = len(rows)
    n_raw_ok = sum(1 for r in rows if r.get("raw_all_clear"))
    # Index-level counts too (not just the strict "every load-bearing index
    # in this row cleared" all_clear bit): a row can partially improve --
    # e.g. c019 needs 3 rulings and union recovers 2 of the 3 it was
    # missing -- and that's real signal for Jon's ship call even where it
    # doesn't flip all_clear for the whole row.
    n_indices = sum(len(r["load_bearing"]) for r in rows if "load_bearing" in r)
    n_raw_indices_ok = sum(len(r["load_bearing"]) - len(r.get("raw_missing", []))
                           for r in rows if "load_bearing" in r)
    summary = {
        "mode": mode,
        "n_load_bearing_cases": n,
        "raw_all_clear": n_raw_ok,
        "n_load_bearing_indices": n_indices,
        "raw_indices_cleared": n_raw_indices_ok,
    }
    if mode == "union":
        n_union_ok = sum(1 for r in rows if r.get("union_all_clear"))
        n_union_indices_ok = sum(len(r["load_bearing"]) - len(r.get("union_missing", []))
                                 for r in rows if "load_bearing" in r)
        gained_rows = [r["id"] + "/" + r["card"] for r in rows
                      if r.get("union_all_clear") and not r.get("raw_all_clear")]
        lost_rows = [r["id"] + "/" + r["card"] for r in rows
                    if r.get("raw_all_clear") and not r.get("union_all_clear")]
        gained_indices = [f"{r['id']}/{r['card']}#{i}" for r in rows if "load_bearing" in r
                          for i in r["raw_missing"] if i not in r.get("union_missing", r["raw_missing"])]
        lost_indices = [f"{r['id']}/{r['card']}#{i}" for r in rows if "load_bearing" in r
                        for i in r.get("union_missing", []) if i not in r["raw_missing"]]
        summary.update({
            "union_all_clear": n_union_ok,
            "union_indices_cleared": n_union_indices_ok,
            "gained_by_union_rows": gained_rows,       # raw missed the WHOLE row, union clears it
            "lost_by_union_rows": lost_rows,           # raw had the whole row, union drops it
            "gained_by_union_indices": gained_indices,  # individual rulings newly cleared
            "lost_by_union_indices": lost_indices,      # individual rulings union somehow drops
        })
    return {"summary": summary, "rows": rows}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default=None,
                    help="OpenRouter model id to generate with, e.g. deepseek/deepseek-v4-flash "
                         "(required unless --ruling-query is given -- that mode does no generation)")
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
    p.add_argument("--ruling-query", choices=["raw", "union"], default=None,
                    help="MEASURE ONLY (docs/plan-l1-crossref-expansion.md Part B), does not "
                         "change the shipped default: report, per ruling-bearing cards.jsonl "
                         "question, whether the load-bearing ruling clears the floor / makes "
                         "the cut under today's raw-question select_rulings ('raw'), or also "
                         "under the union-with-Haiku-rewrite arm ('union'). Skips the main "
                         "generation loop entirely -- no --model needed, no LLM generation "
                         "call, writes a NEW evals/answers/ruling_query_report_<mode>.json "
                         "rather than touching any existing answers file.")
    args = p.parse_args()
    if args.ruling_query is None and args.model is None:
        p.error("--model is required unless --ruling-query is given")
    return args


def main() -> None:
    args = parse_args()

    if args.ruling_query is not None:
        # Part B measurement path -- no vector store, no generation, no
        # --model needed. See ruling_query_report()'s docstring.
        report = ruling_query_report(args.ruling_query)
        out_path = args.out or (ANSWERS_DIR / f"ruling_query_report_{args.ruling_query}.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        s = report["summary"]
        print(f"Ruling-query report (mode={s['mode']}) -> {out_path}")
        print(f"  load-bearing cases (rows):    {s['raw_all_clear']}/{s['n_load_bearing_cases']} raw all-clear")
        print(f"  load-bearing rulings (index): {s['raw_indices_cleared']}/{s['n_load_bearing_indices']} raw cleared")
        if args.ruling_query == "union":
            print(f"  union all-clear (rows):   {s['union_all_clear']}/{s['n_load_bearing_cases']}")
            print(f"  union cleared (indices):  {s['union_indices_cleared']}/{s['n_load_bearing_indices']}")
            print(f"  gained rows:    {s['gained_by_union_rows']}")
            print(f"  lost rows:      {s['lost_by_union_rows']}")
            print(f"  gained indices: {s['gained_by_union_indices']}")
            print(f"  lost indices:   {s['lost_by_union_indices']}")
        return

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
