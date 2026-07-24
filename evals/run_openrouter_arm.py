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

from progress import Heartbeat, atomic_write_json, prompts_cache_sha256  # noqa: E402
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


def _capture_prompt(store: VectorStore, question: str, rewrite_version: str = "v2",
                    ruling_query_mode: str = "raw") -> tuple[str, str]:
    """tests/test_prompt_identity.py's _capture() helper, verbatim pattern: a
    fresh RulesAgent + fresh recording client per question, so no state leaks
    between calls. Runs retrieval/rewrite/card-enrichment for real (warm
    caches -> no Anthropic call happens during rewrite either) and raises
    _Recorded the instant the generation call would go out. Never touches the
    Anthropic API -- there is no live client anywhere in this call chain.

    `rewrite_version`/`ruling_query_mode` (prompt-v3 A/B, docs/plan-v3-
    execution-tasks.md Task 2): threaded straight into RulesAgent so this
    captures the exact condition-B/C/D prompt, not just the shipped default."""
    client = _RecordingClient()
    agent = RulesAgent(store, client=client, card_no_refresh=True,
                       rewrite_version=rewrite_version, ruling_query_mode=ruling_query_mode)
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


def _build_payload(args: argparse.Namespace, results: list[dict], variance: dict | None,
                   prompts_cache_digest: str | None) -> dict:
    """The output-file shape main()'s final write produces. Prior to the
    resume-safety fix below, this was byte-identical to what the pre-
    incremental-writes runner produced (docs/plan-run-progress.md Sec 4
    hard requirement); `summary.prompts_cache` / `summary.prompts_cache_sha256`
    are a deliberate, documented ONE-TIME schema addition on top of that --
    see _load_resumable()'s docstring for why. Used for BOTH the final write
    and every incremental write during the loop -- the only thing that
    varies between calls is which prefix of `results` has been filled in so
    far and whether `variance` is known yet (None until the loop + variance
    pass finish), never the shape itself."""
    answered = sum(1 for r in results if r["answered"] is True)
    parse_failures = sum(1 for r in results if r["text"] is None)
    total_cost = sum((r["usage"] or {}).get("cost", 0) or 0 for r in results)
    return {
        "model": args.model,
        "rewrite_version": args.rewrite_version,
        "ruling_query_mode": args.ruling_query_mode,
        "condition": args.condition,
        "run": args.run,
        "reasoning": args.reasoning_dict,
        "prompts_cache": str(args.prompts_cache) if args.prompts_cache else None,
        "results": results,
        "summary": {
            "n_questions": len(results),
            "answered": answered,
            "parse_failures": parse_failures,
            "total_cost": total_cost,
            # Resume-safety fix (coordinator review, on top of the original
            # plan): mirrors the top-level `prompts_cache` path plus a
            # content digest, so _load_resumable() can tell two prompt
            # variants apart even when model/rewrite_version/
            # ruling_query_mode/reasoning are all identical -- exactly the
            # v5 2x2 grid's four cells. See prompts_cache_sha256()'s
            # docstring (evals/progress.py) for why this is computed
            # ourselves rather than trusted from the cache file.
            "prompts_cache": str(args.prompts_cache) if args.prompts_cache else None,
            "prompts_cache_sha256": prompts_cache_digest,
        },
        "variance": variance,
    }


def _load_resumable(out_path: Path, args: argparse.Namespace,
                    prompts_cache_digest: str | None) -> dict[str, dict]:
    """qid -> already-written row, read off an existing output file at
    `out_path` from a prior (possibly killed) invocation of this exact
    command -- so a restarted run can skip regenerating them (docs/plan-run-
    progress.md Sec 4).

    Two different kinds of mismatch are handled differently on purpose:

    - model / rewrite_version / ruling_query_mode / reasoning differ: SAFE
      to fall back to a fresh run (return {} -- every question gets
      regenerated and the file is fully overwritten as the loop proceeds),
      because a mismatch on any of these means resumable would have been {}
      anyway, so old rows never get mixed into the new file. This wastes
      money on a path collision but never produces wrong data -- the
      original, pre-resume-feature failure mode, unchanged.
    - prompts_cache identity (path + content digest, see
      prompts_cache_sha256()) differs: NOT safe to fall back silently. The
      v5 2x2 symbol-injection grid (docs/plan-v5-symbol-injection.md Sec 3)
      runs four cells sharing model/rewrite_version/ruling_query_mode/
      reasoning and differing ONLY in which prompts file they read -- so
      for that grid, every other field already "matches" and the old code
      would resume, silently keeping rows generated from a DIFFERENT
      prompt in a file that looks complete and consistent. This is strictly
      worse than a wasted-money collision: it produces silently wrong data,
      the exact failure class this project has been burned by before. So
      this specific mismatch HARD ERRORS (prints and sys.exit(1)) rather
      than resuming OR regenerating -- same "loud refusal on an explicit
      mismatch" convention --retry-errors already uses for model/reasoning,
      just applied here to the field that was actually missing a check.

    Missing file / unparseable JSON: returns {}, proceeds as a fresh run,
    same as before this feature existed."""
    if not out_path.exists():
        return {}
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    current_cache_path = str(args.prompts_cache) if args.prompts_cache else None
    recorded_cache_path = data.get("prompts_cache")
    recorded_cache_digest = (data.get("summary") or {}).get("prompts_cache_sha256")
    if recorded_cache_path != current_cache_path or recorded_cache_digest != prompts_cache_digest:
        print(f"[ERROR] {out_path} exists and was generated with prompts_cache="
              f"{recorded_cache_path!r} (sha256={recorded_cache_digest!r}), but this "
              f"invocation is using prompts_cache={current_cache_path!r} "
              f"(sha256={prompts_cache_digest!r}) -- refusing to silently resume from it "
              f"OR regenerate over it: these look like two different experiments aimed at "
              f"the same --out. Point --out somewhere else, or confirm this really is the "
              f"same prompts file and (if it predates this check) start a fresh --out once.")
        sys.exit(1)

    if (data.get("model") != args.model
            or data.get("rewrite_version") != args.rewrite_version
            or data.get("ruling_query_mode") != args.ruling_query_mode
            or data.get("reasoning") != args.reasoning_dict):
        print(f"[resume] {out_path} exists but was generated with a different config "
              f"-- starting fresh rather than resuming from it")
        return {}
    results = data.get("results") or []
    by_id = {r["id"]: r for r in results if isinstance(r, dict) and "id" in r}
    if by_id:
        print(f"[resume] {out_path} has {len(by_id)} row(s) already -- skipping those qids")
    return by_id


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


def run_variance(store: VectorStore, model: str, rewrite_version: str = "v2",
                 ruling_query_mode: str = "raw", reasoning: dict | None = None) -> dict:
    """Task 3: for q001/q014/c015, draw VARIANCE_DRAWS answers each from the
    SAME captured prompt and report whether the draws are byte-identical --
    the honest question for any temp=0 arm (temp=0 reduces draw variance, it
    does not guarantee it -- same caveat openrouter_backend.py documents).

    `reasoning`: same condition-E passthrough as the main loop (docs/
    plan-condition-e-reasoning.md Sec 2); default None, unaffected."""
    all_q = _load_all_questions()
    out = {}
    for qid in VARIANCE_IDS:
        question = all_q.get(qid)
        if question is None:
            out[qid] = {"error": f"question id {qid!r} not found in questions.jsonl/cards.jsonl"}
            continue
        system, user = _capture_prompt(store, question, rewrite_version=rewrite_version,
                                       ruling_query_mode=ruling_query_mode)
        texts = []
        for draw in range(VARIANCE_DRAWS):
            result = openrouter_backend.generate(system, user, model, reasoning=reasoning)
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


_REASONING_SHORTHAND = {"low", "medium", "high"}

# Sentinel distinguishing "--reasoning wasn't passed at all" from "--reasoning
# was passed with a value" (fix-loop finding 1). Using None as the argparse
# default would collide with a legitimately-parsed value of None (e.g. the
# raw JSON literal "null"), which matters for --retry-errors: omitting the
# flag must silently reuse the file's recorded reasoning (including when
# that's null/None), while explicitly passing --reasoning must be compared
# against the file's value and hard-error on any mismatch.
_REASONING_NOT_PASSED = object()


def _parse_reasoning(parser: argparse.ArgumentParser, raw: str | None) -> dict | None:
    """--reasoning passthrough (docs/plan-condition-e-reasoning.md Sec 2):
    low|medium|high shorthand -> {"effort": <value>}; anything else must be
    valid JSON for an object, used verbatim as OpenRouter's `reasoning` dict.
    Returns None when --reasoning wasn't given at all (the default, off)."""
    if raw is None:
        return None
    if raw in _REASONING_SHORTHAND:
        return {"effort": raw}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        parser.error(f"--reasoning {raw!r} is not low|medium|high and not valid JSON: {e}")
        return None  # unreachable -- parser.error() raises SystemExit
    if not isinstance(parsed, dict):
        parser.error(f"--reasoning {raw!r} must be low|medium|high or a JSON object, "
                     f"got {type(parsed).__name__}")
        return None  # unreachable
    return parsed


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
        help="prompt-v3 A/B condition label (e.g. B/C/D), stamped into the output payload's "
        "'condition' field for provenance -- purely informational, has no effect on the run",
    )
    p.add_argument(
        "--reasoning", default=_REASONING_NOT_PASSED,
        help="condition-E reasoning passthrough (docs/plan-condition-e-reasoning.md Sec 2): "
        "either the shorthand low|medium|high (mapped to OpenRouter's "
        "{\"effort\": \"<value>\"}), or a raw JSON object for anything else (e.g. "
        "'{\"effort\": \"high\", \"exclude\": true}'). Passed straight through to "
        "openrouter_backend.generate()'s reasoning= kwarg. Default: not passed -- omitted from "
        "the request body entirely, so every run without this flag is unaffected. Recorded "
        "verbatim into the output file's 'reasoning' metadata field alongside 'model' / "
        "'rewrite_version' / 'ruling_query_mode' so a run file is self-describing. On "
        "--retry-errors, this flag is OPTIONAL and, if given, must match the file's recorded "
        "reasoning exactly -- a retry can't silently change the reasoning config it's patching.",
    )
    p.add_argument(
        "--run", type=int, default=None,
        help="which of the two independent generation runs this is (1 or 2), stamped into "
        "the output payload's 'run' field for provenance -- purely informational",
    )
    p.add_argument(
        "--prompts-cache", type=Path, default=None,
        help="path to a JSON {qid: {system, user}} prompt cache (see --assemble-only). When "
        "given on a normal generation run, the assembled prompt is READ from this file "
        "instead of being re-captured live -- required for genuine cross-arm AND cross-run "
        "byte-identity, since RulesAgent.answer()'s retrieval step live-embeds the query via "
        "Voyage on every call with no cache (docs/plan-v3-execution-tasks.md Task 2 found "
        "this causes real, non-trivial drift -- ~30%% of the 50 eval questions got a "
        "meaningfully different retrieved-chunk set on a second live capture with identical "
        "config). The file must already exist (built via --assemble-only) -- a missing id or "
        "missing file is a loud error, never a silent fall-back to live capture.",
    )
    p.add_argument(
        "--assemble-only", action="store_true",
        help="build a --prompts-cache file (capturing (system, user) for the FULL combined "
        "questions.jsonl + cards.jsonl set via _capture_prompt(), under --rewrite-version/"
        "--ruling-query-mode) and exit -- no --model needed, no generation call. Run this "
        "ONCE per condition, before the 12 (6 arms x 2 runs) generation invocations that "
        "share it via --prompts-cache.",
    )
    p.add_argument("--ruling-query", choices=["raw", "union"], default=None,
                    help="MEASURE ONLY (docs/plan-l1-crossref-expansion.md Part B), does not "
                         "change the shipped default: report, per ruling-bearing cards.jsonl "
                         "question, whether the load-bearing ruling clears the floor / makes "
                         "the cut under today's raw-question select_rulings ('raw'), or also "
                         "under the union-with-Haiku-rewrite arm ('union'). Skips the main "
                         "generation loop entirely -- no --model needed, no LLM generation "
                         "call, writes a NEW evals/answers/ruling_query_report_<mode>.json "
                         "rather than touching any existing answers file.")
    p.add_argument(
        "--retry-errors", type=Path, default=None,
        help="path to an EXISTING answers JSON (written by a normal run of this script). "
        "Re-generates ONLY the rows with a truthy 'error' field -- reads that file's own "
        "recorded model/rewrite_version/ruling_query_mode/prompts_cache (no need to pass them "
        "again), regenerates each errored question, merges the new result back into the "
        "SAME row (preserving row order and every already-successful row untouched), "
        "recomputes summary, and writes in place to the same path. Still requires --model "
        "argument, which must match the model recorded in the file to prevent accidentally "
        "mixing different models' answers. Content-level completeness "
        "matters more than file presence: a 50/50-row file can still have per-row 'error' "
        "set from a transient 400/429 -- this is how those get fixed without re-spending "
        "the whole 50-question cost.",
    )
    args = p.parse_args()
    args.reasoning_passed = args.reasoning is not _REASONING_NOT_PASSED
    args.reasoning_dict = (_parse_reasoning(p, args.reasoning)
                          if args.reasoning_passed else None)
    if args.assemble_only:
        if args.prompts_cache is None:
            p.error("--assemble-only requires --prompts-cache PATH")
    elif args.retry_errors is not None:
        if args.model is None:
            p.error("--retry-errors requires --model")
    elif args.ruling_query is None and args.model is None:
        p.error("--model is required unless --ruling-query or --assemble-only is given")
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

    if args.retry_errors is not None:
        # Content-level completeness fix (docs/plan-v3-execution-tasks.md Task
        # 2): a 50/50-row file can still have per-row 'error' set from a
        # transient provider 400/429 that outlasted openrouter_backend.py's
        # own retry budget -- this re-generates ONLY those rows, in place, no
        # vector store needed (prompts come from the file's own recorded
        # prompts_cache, not fresh retrieval).
        path = args.retry_errors
        if not path.exists():
            print(f"[ERROR] --retry-errors {path} does not exist")
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        # Guard: model in the file must match the --model argument, to prevent
        # accidentally splicing a different model's answers into the results.
        if data.get("model") and data["model"] != args.model:
            print(f"[ERROR] --retry-errors {path} was generated with model={data['model']!r}, "
                  f"but this invocation passed --model={args.model!r} -- refusing to silently "
                  f"mix models")
            return
        rw_ver, rq_mode = data.get("rewrite_version"), data.get("ruling_query_mode")
        # rewrite_version/ruling_query_mode above are read into locals purely
        # for the log line below -- they are NOT enforced against --rewrite-
        # version/--ruling-query-mode (this path takes no such flags at all),
        # because retry always sources prompts from the file's own recorded
        # prompts_cache, which makes those two settings inert here regardless
        # of what produced the file.
        #
        # `reasoning` (docs/plan-condition-e-reasoning.md Sec 2) is different
        # in kind: it's an ACTIVE inference-time parameter passed straight to
        # generate() on every retried call, so it can't be silently ignored
        # the way rewrite_version/ruling_query_mode are. Default (flag
        # omitted): silently reuse the file's recorded value, including when
        # that's null -- the normal, expected path. Flag explicitly passed:
        # hard-error on any mismatch with the file's recorded value, the same
        # loud-refusal convention the model guard above already uses --
        # fixing the reasoning config for a run means starting a new run, not
        # mutating a retry.
        reasoning_from_file = data.get("reasoning")
        if args.reasoning_passed and args.reasoning_dict != reasoning_from_file:
            print(f"[ERROR] --retry-errors {path} was generated with "
                  f"reasoning={reasoning_from_file!r}, but this invocation passed "
                  f"--reasoning={args.reasoning!r} (resolved to {args.reasoning_dict!r}) -- "
                  f"refusing to silently change the reasoning config on a retry; run a new "
                  f"eval instead")
            return
        cache_path_str = data.get("prompts_cache")
        prompts_cache = None
        if cache_path_str:
            cached = json.loads(Path(cache_path_str).read_text(encoding="utf-8"))
            prompts_cache = cached["prompts"]
        results = data["results"]
        by_id = {r["id"]: i for i, r in enumerate(results)}
        err_ids = [r["id"] for r in results if r.get("error")]
        print(f"Retrying {len(err_ids)} errored rows in {path} | model={args.model} "
              f"| rewrite_version={rw_ver} | ruling_query_mode={rq_mode} "
              f"| reasoning={reasoning_from_file} | prompts_cache={cache_path_str}\n")
        for i, qid in enumerate(err_ids, 1):
            t0 = time.time()
            question = results[by_id[qid]]["question"]
            if prompts_cache is not None and qid in prompts_cache:
                system, user = prompts_cache[qid]["system"], prompts_cache[qid]["user"]
            else:
                print(f"[ERROR] {qid} not found in prompts cache {cache_path_str} -- skipping")
                continue
            result = openrouter_backend.generate(system, user, args.model,
                                                 reasoning=reasoning_from_file)
            results[by_id[qid]] = _answer_row(qid, question, result)
            status = "ok" if result.answer is not None else f"FAIL ({result.error})"
            print(f"  [{i}/{len(err_ids)}] {qid} -> {status} ({time.time() - t0:.1f}s)")

        answered = sum(1 for r in results if r["answered"] is True)
        parse_failures = sum(1 for r in results if r["text"] is None)
        total_cost = sum((r["usage"] or {}).get("cost", 0) or 0 for r in results)
        data["summary"] = {
            "n_questions": len(results), "answered": answered,
            "parse_failures": parse_failures, "total_cost": total_cost,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        remaining = [r["id"] for r in results if r.get("error")]
        print(f"\nRetried {len(err_ids)} rows -> {path}")
        print(f"  remaining errors: {len(remaining)} -> {remaining}")
        return

    pkl = PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl"
    if not pkl.exists():
        print(f"[ERROR] no vector index at {pkl.name}; run build_vector_indexes.py")
        return
    store = VectorStore.load(pkl)

    if args.assemble_only:
        # One retrieval/prompt-assembly pass over the FULL 50-question set
        # (docs/plan-v3-execution-tasks.md Task 2, brief item 2) -- ignores
        # --limit/--questions/--cards overrides on purpose, always the full
        # combined set, so every arm/run sharing this cache answers the same
        # 50 questions. Always fresh: any pre-existing file at this path is
        # overwritten, never merged, so a condition's cache can't end up a
        # stitched-together mix of two different capture sessions.
        all_q = load_questions(QUESTIONS_PATH) + load_questions(CARDS_PATH)
        cache: dict[str, dict[str, str]] = {}
        t0 = time.time()
        for i, q in enumerate(all_q, 1):
            system, user = _capture_prompt(store, q.question, rewrite_version=args.rewrite_version,
                                           ruling_query_mode=args.ruling_query_mode)
            cache[q.id] = {"system": system, "user": user}
            print(f"  [{i}/{len(all_q)}] {q.id} assembled")
        args.prompts_cache.parent.mkdir(parents=True, exist_ok=True)
        with open(args.prompts_cache, "w", encoding="utf-8") as f:
            json.dump({
                "rewrite_version": args.rewrite_version,
                "ruling_query_mode": args.ruling_query_mode,
                "n_questions": len(all_q),
                "prompts": cache,
            }, f, indent=2, ensure_ascii=False)
        print(f"\nAssembled {len(all_q)} prompts (rewrite_version={args.rewrite_version}, "
              f"ruling_query_mode={args.ruling_query_mode}) -> {args.prompts_cache} "
              f"in {time.time() - t0:.1f}s")
        return

    out_path = args.out or (ANSWERS_DIR / f"openrouter_{_slug_for(args.model)}.json")

    prompts_cache = None
    prompts_cache_digest = None
    if args.prompts_cache is not None:
        if not args.prompts_cache.exists():
            print(f"[ERROR] --prompts-cache {args.prompts_cache} does not exist -- "
                  f"build it first with --assemble-only")
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
        # Resume-safety fix: the content-derived identity of THIS cache,
        # recorded in the output and checked in _load_resumable() so two
        # cells that share every other flag (the v5 grid) can't silently
        # resume/mix rows from a different prompts file at the same --out.
        prompts_cache_digest = prompts_cache_sha256(prompts_cache)

    questions = load_questions(args.questions) + load_questions(args.cards)
    if args.limit is not None:
        questions = questions[: args.limit]

    print(
        f"Generating {len(questions)} answers | model={args.model} | out={out_path} "
        f"| rewrite_version={args.rewrite_version} | ruling_query_mode={args.ruling_query_mode} "
        f"| condition={args.condition} | run={args.run} | reasoning={args.reasoning_dict} "
        f"| prompts_cache={args.prompts_cache}\n"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Resume (docs/plan-run-progress.md Sec 4): qids already written by a
    # prior (possibly killed) invocation at this exact --out, under a
    # matching config -- skipped below rather than regenerated. Hard-errors
    # (sys.exit(1)) instead of returning on a prompts-cache identity
    # mismatch -- see _load_resumable()'s docstring.
    resumable = _load_resumable(out_path, args, prompts_cache_digest)

    results = []
    start = time.time()
    hb = Heartbeat(run=out_path.stem, model=args.model, variant=args.condition,
                   n_total=len(questions))
    success = False
    try:
        for i, q in enumerate(questions, 1):
            t0 = time.time()
            if q.id in resumable:
                row = resumable[q.id]
                results.append(row)
                print(f"  [{i}/{len(questions)}] {q.id} -> resumed (already in {out_path.name})")
            else:
                if prompts_cache is not None:
                    if q.id not in prompts_cache:
                        print(f"[ERROR] question id {q.id!r} not found in {args.prompts_cache} -- "
                              f"the cache doesn't cover this question set")
                        return
                    system, user = prompts_cache[q.id]["system"], prompts_cache[q.id]["user"]
                else:
                    system, user = _capture_prompt(store, q.question, rewrite_version=args.rewrite_version,
                                                   ruling_query_mode=args.ruling_query_mode)
                result = openrouter_backend.generate(system, user, args.model,
                                                     reasoning=args.reasoning_dict)
                row = _answer_row(q.id, q.question, result)
                results.append(row)
                status = "ok" if result.answer is not None else f"FAIL ({result.error})"
                print(f"  [{i}/{len(questions)}] {q.id} -> {status} ({time.time() - t0:.1f}s)")

            # Incremental write (Sec 4): the SAME payload shape the final
            # write below produces, just with a shorter `results` prefix and
            # `variance` not known yet -- so a crash keeps every row
            # completed so far, and a resumed run reads them back out.
            atomic_write_json(out_path, _build_payload(args, results, None, prompts_cache_digest))
            cost_delta = (row["usage"] or {}).get("cost", 0) or 0
            hb.tick(q.id, errored=bool(row.get("error")), cost_delta=cost_delta)

        variance = None
        if args.variance:
            print("\nVariance spot-check (q001/q014/c015, 3 draws each):")
            variance = run_variance(store, args.model, rewrite_version=args.rewrite_version,
                                    ruling_query_mode=args.ruling_query_mode,
                                    reasoning=args.reasoning_dict)

        payload = _build_payload(args, results, variance, prompts_cache_digest)
        atomic_write_json(out_path, payload)
        success = True
    finally:
        hb.finish(success)

    answered = payload["summary"]["answered"]
    total_cost = payload["summary"]["total_cost"]
    print(f"\nWrote {len(results)} answers -> {out_path} in {time.time() - start:.1f}s")
    print(f"  answered:       {answered}/{len(results)}")
    print(f"  parse failures: {payload['summary']['parse_failures']}/{len(results)}")
    print(f"  total cost:     ${total_cost:.4f}")


if __name__ == "__main__":
    main()
