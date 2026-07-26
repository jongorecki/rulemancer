"""THROWAWAY Phase-1 debugging harness -- cost-tool reliability defect repro.

NOT a permanent eval script. Purpose: reproduce and instrument the ~21%
empty-output ("stop_reason=error") rate on the calculate_cost tool-loop path
in RulesAgent.answer() (src/rulesagent/generate/answer.py), and measure the
SPLIT between the two structurally different causes of `response is None`:

  1. ValidationError on a messages.parse() call (empty/unparseable content).
  2. Cap-exhaustion: TOOL_ROUND_CAP (3) rounds all came back stop_reason==
     "tool_use" with no terminal structured-Answer turn (the for/else in
     answer.py's inner loop).

Does NOT modify answer.py. Instruments purely by monkeypatching
agent.client.messages.parse with a wrapper that:
  - infers (attempt#, round#) from message-list shape (len==1 => new attempt)
  - logs stop_reason/usage/content-block-types on every successful call
  - on ValidationError, makes ONE diagnostic client.messages.create() call
    with the same model/system/messages/tools (minus output_format) to
    recover the raw response's content/stop_reason/usage, then re-raises
    the ValidationError unchanged so answer.py's own except-path is
    untouched.

Run (from repo root, on master, NOT a worktree):
  .venv\\Scripts\\python.exe evals\\_phase1_costtool_repro.py > evals\\_phase1_costtool_repro.log 2>&1

Reads evals/rulesguru_full.jsonl (rg289, rg897, rg1487, rg6636, rg6916) and
evals/cards.jsonl (c014), 4 repeats each -> 24 generations. Vector store /
agent construction mirrors evals/run_answer_eval.py (the only existing
script that drives RulesAgent.answer() directly on eval questions).
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # sibling-module imports, same
# pattern run_answer_eval.py / run_eval.py already use (evals/ isn't a real
# installed package).

from pydantic import ValidationError  # noqa: E402

from run_eval import PARSED_DIR, VECTOR_MODEL, load_questions  # noqa: E402
from qidfilter import select_qids  # noqa: E402

from rulesagent.generate.answer import GEN_MODEL, RulesAgent, _degenerate  # noqa: E402
from rulesagent.index.store import VectorStore  # noqa: E402
# NOTE: unlike run_answer_eval.py, we don't need parse_comprehensive_rules/
# chunk_rules here -- those only feed THAT script's own gold_text/cited_text
# reporting columns. RulesAgent.__init__ builds its own self.chunk_map
# straight off store.chunks (see answer.py L1088), so the agent is fully
# usable from just the pickled VectorStore.

QIDS_RULESGURU = ["rg289", "rg897", "rg1487", "rg6636", "rg6916"]
QID_CARDS = "c014"
REPEATS = 4

# ---------------------------------------------------------------------------
# Instrumentation state (module-level, reset per generation by the driver)
# ---------------------------------------------------------------------------
CURRENT = {"qid": None, "repeat": None}
_attempt_n = {"n": -1}
_round_n = {"n": -1}
RECORDS: list[dict] = []  # one dict per messages.parse() call, across the whole run


def _usage_dict(usage):
    if usage is None:
        return None
    try:
        return usage.model_dump()
    except Exception:
        return repr(usage)


def _content_types(content):
    if not content:
        return []
    return [getattr(b, "type", None) for b in content]


def _content_text_present(content):
    if not content:
        return False
    for b in content:
        if getattr(b, "type", None) == "text" and getattr(b, "text", ""):
            return True
    return False


def _content_thinking_only(content):
    if not content:
        return True
    return all(getattr(b, "type", None) in ("thinking", "redacted_thinking") for b in content)


def install_instrumentation(agent: RulesAgent):
    """Monkeypatch agent.client.messages.parse (instance attribute shadow --
    does not touch answer.py). Returns nothing; wraps in place."""
    messages_obj = agent.client.messages
    orig_parse = messages_obj.parse
    orig_create = messages_obj.create

    def wrapper(*args, **kwargs):
        msgs = kwargs.get("messages")
        is_new_attempt = isinstance(msgs, list) and len(msgs) == 1
        if is_new_attempt:
            _attempt_n["n"] += 1
            _round_n["n"] = 0
        else:
            _round_n["n"] += 1

        tool_result_bytes = None
        if isinstance(msgs, list) and msgs:
            last = msgs[-1]
            if isinstance(last, dict) and last.get("role") == "user" and isinstance(last.get("content"), list):
                try:
                    tool_result_bytes = len(json.dumps(last["content"]).encode("utf-8"))
                except Exception:
                    tool_result_bytes = None

        record = {
            "qid": CURRENT["qid"],
            "repeat": CURRENT["repeat"],
            "attempt": _attempt_n["n"],
            "round": _round_n["n"],
            "tool_attached": kwargs.get("tools") is not None,
            "tool_result_bytes_in": tool_result_bytes,
        }

        try:
            response = orig_parse(*args, **kwargs)
        except ValidationError as e:
            record["event"] = "validation_error"
            record["validation_error_summary"] = str(e)[:400]
            # ONE diagnostic client.messages.create() call, identical params
            # minus output_format (create() doesn't accept it), to recover
            # the raw response answer.py's own except-path discards.
            diag_kwargs = dict(kwargs)
            diag_kwargs.pop("output_format", None)
            try:
                raw = orig_create(*args, **diag_kwargs)
                record["raw_stop_reason"] = getattr(raw, "stop_reason", None)
                record["raw_usage"] = _usage_dict(getattr(raw, "usage", None))
                record["raw_content_types"] = _content_types(getattr(raw, "content", None))
                record["raw_content_text_present"] = _content_text_present(getattr(raw, "content", None))
                record["raw_thinking_only"] = _content_thinking_only(getattr(raw, "content", None))
            except Exception as diag_e:
                record["diag_error"] = repr(diag_e)
            RECORDS.append(record)
            raise
        else:
            record["event"] = "ok"
            record["stop_reason"] = getattr(response, "stop_reason", None)
            record["usage"] = _usage_dict(getattr(response, "usage", None))
            record["content_types"] = _content_types(getattr(response, "content", None))
            RECORDS.append(record)
            return response

    messages_obj.parse = wrapper


def reset_generation(qid: str, repeat: int):
    CURRENT["qid"] = qid
    CURRENT["repeat"] = repeat
    _attempt_n["n"] = -1
    _round_n["n"] = -1


def classify_generation(qid: str, repeat: int, ans) -> str:
    """Classify using OUR OWN per-round log for this (qid, repeat) to split
    the hard-failure sentinel, plus _degenerate() on the returned Answer to
    catch the separate "weak fallback reused" class (answer.py's q029 gate:
    both attempts degenerate/failed, but a not-answered weak draw got reused
    as the final Answer instead of the honest empty-output message)."""
    gen_records = [r for r in RECORDS if r["qid"] == qid and r["repeat"] == repeat]
    if not gen_records:
        return "no-records"

    empty_signature = "(no structured answer: the model returned empty output twice"
    if empty_signature not in ans.text:
        if _degenerate(ans):
            return "degenerate"
        return "answered"

    # Hard-failure path: determine mode from the LAST attempt's records.
    last_attempt = max(r["attempt"] for r in gen_records)
    last_attempt_records = [r for r in gen_records if r["attempt"] == last_attempt]
    had_validation_error = any(r["event"] == "validation_error" for r in last_attempt_records)
    max_round_in_last_attempt = max(r["round"] for r in last_attempt_records)
    all_ok_tool_use = all(
        r["event"] == "ok" and r.get("stop_reason") == "tool_use"
        for r in last_attempt_records
    )
    cap_exhausted = (
        not had_validation_error
        and all_ok_tool_use
        and max_round_in_last_attempt >= 2  # rounds 0,1,2 = TOOL_ROUND_CAP(3) rounds
    )
    if had_validation_error:
        return "validation-empty"
    if cap_exhausted:
        return "cap-exhausted"
    return "degenerate"  # last attempt's response wasn't None via either
    # hard-failure mode -> parsed was discarded as a degenerate draw and no
    # usable weak fallback existed either.


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[STOP] ANTHROPIC_API_KEY is not set in this process's environment. "
              "answer.py calls load_dotenv() at import time, so check .env.")
        sys.exit(1)

    print(f"[setup] GEN_MODEL (production default) = {GEN_MODEL!r}")

    pkl = PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl"
    if not pkl.exists():
        print(f"[STOP] no vector index at {pkl.name}; run build_vector_indexes.py first")
        sys.exit(1)
    store = VectorStore.load(pkl)

    agent = RulesAgent(
        store, model=GEN_MODEL, rewrite=True, show_rewrite=False,
        card_no_refresh=True,
    )
    install_instrumentation(agent)

    # Load the 5 rulesguru questions.
    rulesguru_path = Path(__file__).parent / "rulesguru_full.jsonl"
    all_rulesguru = load_questions(rulesguru_path)
    rg_questions = select_qids(all_rulesguru, ",".join(QIDS_RULESGURU))

    # Load c014 from cards.jsonl.
    cards_path = Path(__file__).parent / "cards.jsonl"
    all_cards = load_questions(cards_path)
    c014_questions = select_qids(all_cards, QID_CARDS)

    all_questions = list(rg_questions) + list(c014_questions)
    print(f"[setup] {len(all_questions)} questions x {REPEATS} repeats = "
          f"{len(all_questions) * REPEATS} generations planned\n")

    generation_summaries = []
    t_start = time.time()
    for q in all_questions:
        for repeat in range(REPEATS):
            reset_generation(q.id, repeat)
            t0 = time.time()
            ans = None
            try:
                ans = agent.answer(q.question)
                final_text = ans.text
                answered_flag = ans.answered
            except Exception as e:  # a hard crash outside the normal retry path
                final_text = f"(harness caught exception: {e!r})"
                answered_flag = False
            dt = time.time() - t0
            classification = (
                classify_generation(q.id, repeat, ans) if ans is not None
                else "harness-exception"
            )
            generation_summaries.append({
                "qid": q.id, "repeat": repeat, "classification": classification,
                "answered": answered_flag, "seconds": round(dt, 1),
                "final_text_head": final_text[:160],
            })
            print(f"[{q.id} repeat={repeat}] classification={classification} "
                  f"answered={answered_flag} ({dt:.1f}s)")
            print(f"    text_head: {final_text[:160]!r}")

    total_dt = time.time() - t_start
    print(f"\n[done] {len(generation_summaries)} generations in {total_dt:.1f}s\n")

    # ---- Summary ----
    from collections import Counter
    counts = Counter(g["classification"] for g in generation_summaries)
    print("=== CLASSIFICATION SUMMARY ===")
    for k in ("answered", "validation-empty", "cap-exhausted", "degenerate", "no-records", "harness-exception"):
        print(f"  {k}: {counts.get(k, 0)}")
    n_total = len(generation_summaries)
    n_empty = counts.get("validation-empty", 0) + counts.get("cap-exhausted", 0)
    print(f"\nTotal generations: {n_total}")
    print(f"Empty-output failures (validation-empty + cap-exhausted): {n_empty} "
          f"({100.0 * n_empty / n_total:.1f}%)")
    print(f"  of which validation-empty: {counts.get('validation-empty', 0)}")
    print(f"  of which cap-exhausted:    {counts.get('cap-exhausted', 0)}")

    print("\n=== PER-GENERATION TABLE ===")
    for g in generation_summaries:
        print(f"{g['qid']:10s} repeat={g['repeat']} {g['classification']:18s} "
              f"answered={g['answered']!s:5s} {g['seconds']:6.1f}s  {g['final_text_head']!r}")

    print("\n=== RAW FAILURE DETAIL (validation-empty / cap-exhausted only) ===")
    failure_qids_repeats = {
        (g["qid"], g["repeat"]) for g in generation_summaries
        if g["classification"] in ("validation-empty", "cap-exhausted")
    }
    for qid, repeat in sorted(failure_qids_repeats):
        print(f"\n--- {qid} repeat={repeat} ---")
        for r in RECORDS:
            if r["qid"] == qid and r["repeat"] == repeat:
                print(json.dumps(r, indent=None, default=str))

    # Dump full raw records too, for post-hoc analysis.
    out_json = Path(__file__).parent / "_phase1_costtool_repro_records.json"
    out_json.write_text(json.dumps(RECORDS, indent=2, default=str), encoding="utf-8")
    print(f"\n[artifact] full per-round records written to {out_json}")


if __name__ == "__main__":
    main()
