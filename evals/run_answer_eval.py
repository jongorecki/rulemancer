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

from anthropic.lib._parse._transform import transform_schema
from anthropic._models import TypeAdapter
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent))  # so `from run_eval import ...` resolves
# regardless of the caller's cwd -- evals/ isn't part of the installed
# rulesagent package, it's a scripts directory, so it needs to be on
# sys.path explicitly rather than relying on script-directory auto-insertion.

from progress import Heartbeat, atomic_write_json, prompts_cache_sha256  # noqa: E402
from qidfilter import QidFilterError, select_qids  # noqa: E402
from run_eval import CR_PATH, PARSED_DIR, VECTOR_MODEL, load_questions  # noqa: E402

from rulesagent.contracts import Answer  # noqa: E402
from rulesagent.generate.answer import (  # noqa: E402
    GEN_EFFORT_LEVELS,
    GEN_MAX_TOKENS,
    GEN_MODEL,
    GEN_REQUEST_TIMEOUT,
    PROMPT_VERSION,
    RulesAgent,
    _cacheable_system,
    _degenerate,
    _sum_usage,
    _usage_dict,
    available_sources_from_context,
    available_sources_from_prompt_text,
    citation_source_breakdown,
    cr_rule_citations,
    needs_regrounding,
    prompt_supplied_rule_ids,
    reground_once,
)
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.ingest.chunker import chunk_rules  # noqa: E402
from rulesagent.ingest.parser import parse_comprehensive_rules  # noqa: E402
from rulesagent.tools.scryfall import ATTRIBUTION  # noqa: E402

QUESTIONS_PATH = Path(__file__).parent / "questions.jsonl"
DEFAULT_OUT = PARSED_DIR / "review.json"

# --- Batch API support (Anthropic Message Batches, 50% of sync price) -------
#
# ONLY the --prompts-cache (frozen-prompt) path is batchable: each row there
# is a single independent messages.parse()-equivalent call from an already-
# assembled (system, user) pair, with no tool loop and no cross-row
# dependency -- exactly the shape the Batches API wants. The live path
# (RulesAgent.answer(), no --prompts-cache) has a genuine multi-turn tool
# loop and is refused outright (see _validate_batch_combination()) rather
# than silently downgraded to synchronous, which would look like it ran at
# batch-discount cost while actually paying full price. --reground is
# refused for the same "silent-mismatch" reason: the re-ask is a SECOND call
# that depends on the first response, so it can't be folded into one batch
# request. (A two-phase batch -- submit the initial batch, then a second,
# smaller batch of only the rows needing regrounding, keyed the same way --
# would work, but isn't built here: it doubles the moving parts for a flag
# that's off by default in every existing arm.)
BATCH_RECORDS_DIR = Path(__file__).parent / "answers" / "_batches"


def _validate_batch_combination(batch: bool, prompts_cache_path, reground: bool) -> None:
    """Refuse the two unsupported --batch combinations loudly, before any
    submission happens. Called from main() right after arg parsing so a bad
    combination fails in milliseconds, not after CR parsing / vector index
    loading / batch submission.

    A bare sys.exit(1) rather than a raised exception because this mirrors
    every other CLI-validation failure in this file (--qids + --limit
    together, a --prompts-cache identity mismatch, etc.) -- all print an
    [ERROR] line and exit 1, none raise a Python exception to the user."""
    if batch and prompts_cache_path is None:
        print(
            "[ERROR] --batch requires --prompts-cache. The live agent.answer() path has "
            "a genuine tool loop (retrieval, layer resolution, multi-turn) and is not a "
            "single independent request per question, so it cannot be submitted as a "
            "batch without restructuring. Freeze a prompts cache first (evals/"
            "run_openrouter_arm.py --assemble-only) and pass it via --prompts-cache, or "
            "drop --batch."
        )
        sys.exit(1)
    if batch and reground:
        print(
            "[ERROR] --batch cannot be combined with --reground. Regrounding re-asks with "
            "a SECOND API call that depends on the first response's citations, so it isn't "
            "a single independent request and can't be folded into one batch item. Drop "
            "--reground, or run --batch first and reground the flagged rows in a separate, "
            "smaller synchronous or second-batch pass."
        )
        sys.exit(1)


def _batch_record_path(out_path: Path) -> Path:
    """Where a --batch run's durable submission record lives for a given
    --out. One record per --out, matching the one-output-file-per-run
    convention _load_resumable() already uses."""
    return BATCH_RECORDS_DIR / f"{out_path.stem}.batch.json"


def _batch_identity(model: str, max_tokens: int, effort: str | None, cache_prompt: bool,
                    prompts_cache_path, prompts_cache_digest: str | None,
                    qids: list[str]) -> dict:
    """The fields that define WHICH experiment a submitted batch answers --
    the batch-level analogue of _load_resumable()'s row-identity check.
    Compared verbatim (order-independent on qids only) so a config change
    between two runs at the same --out is caught rather than silently
    reusing (or resubmitting over) a batch that answers a different
    question."""
    return {
        "model": model,
        "max_tokens": max_tokens,
        "effort": effort,
        "cache_prompt": cache_prompt,
        "prompts_cache": str(prompts_cache_path) if prompts_cache_path else None,
        "prompts_cache_sha256": prompts_cache_digest,
        "qids": sorted(qids),
    }


def _batch_output_format() -> dict:
    """The output_config.format body for a batched Answer generation --
    reproduces BY HAND the exact JSON-schema transform
    `client.messages.parse(output_format=Answer)` applies internally
    (anthropic.lib._parse._transform.transform_schema over
    TypeAdapter(Answer).json_schema()), because the Batches API takes raw
    MessageCreateParamsNonStreaming, not the .parse() convenience wrapper --
    there is no batch equivalent of .parse(). Using the identical transform
    is what makes a --batch request byte-identical (aside from the
    batch-vs-sync endpoint itself) to what _answer_from_frozen_prompt()
    sends via .parse() for the same question."""
    schema = TypeAdapter(Answer).json_schema()
    return {"type": "json_schema", "schema": transform_schema(schema)}


def _batch_request_params(model: str, system: str, user: str, max_tokens: int,
                          effort: str | None, cache_prompt: bool) -> dict:
    """Request params for one batched question. Mirrors
    _answer_from_frozen_prompt()'s single-call request body field-for-field
    (system via _cacheable_system(), one user message, the same effort_kwargs
    shape) so a --batch row is a genuine rerun of the same request the
    synchronous arm would send for this question, just submitted async."""
    params: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": _cacheable_system(system, cache_prompt),
        "messages": [{"role": "user", "content": user}],
        "output_config": {"format": _batch_output_format()},
    }
    if effort is not None:
        params["output_config"]["effort"] = effort
    return params


def submit_or_attach_batch(
    client, out_path: Path, questions: list, prompts_cache: dict, model: str,
    max_tokens: int, effort: str | None, cache_prompt: bool,
    prompts_cache_path, prompts_cache_digest: str | None,
) -> tuple[str, dict[str, str]]:
    """Submit a Message Batch covering `questions` (each answered from its
    frozen prompt in `prompts_cache`), or -- if a durable record from a prior
    invocation already exists for this --out with a MATCHING identity --
    attach to that existing batch instead of submitting a duplicate.

    Durability (never orphan a submitted batch): the batch id and the
    custom_id -> question_id mapping are written to disk via
    atomic_write_json() IMMEDIATELY after client.messages.batches.create()
    returns, before any polling happens. If the process is killed a moment
    later, the record is the only thing standing between a killed process
    and a batch that keeps running server-side with no local trace of it --
    exactly the "lost work to a process being killed mid-run" failure mode
    this repo has already hit once.

    Resume-without-resubmitting (a duplicate submission is real money):
    re-running this function against the same --out reads the existing
    record first. If its identity (model/max_tokens/effort/cache_prompt/
    prompts_cache identity/qid set -- see _batch_identity()) matches this
    invocation's, it returns the recorded batch_id/mapping WITHOUT calling
    client.messages.batches.create() again. If the identity differs, this
    hard-errors (sys.exit(1)) rather than silently resubmitting or silently
    reusing a batch that answers a different question -- the same
    "mismatch is fatal, not a fallback" discipline _load_resumable() already
    applies to prompts_cache identity.

    custom_id is the question id verbatim (ids in questions.jsonl are
    already unique strings), but the mapping is still built and persisted
    explicitly rather than re-derived from the qid list on every read, so a
    future custom_id scheme change doesn't have to touch this function's
    on-disk shape or its caller.
    """
    qids = [q.id for q in questions]
    identity = _batch_identity(
        model, max_tokens, effort, cache_prompt, prompts_cache_path, prompts_cache_digest, qids,
    )
    record_path = _batch_record_path(out_path)

    if record_path.exists():
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            record = None
        if record is not None:
            if record.get("identity") != identity:
                print(
                    f"[ERROR] {record_path} already records a batch submitted for a "
                    f"different config or question set than this invocation -- refusing "
                    f"to silently resubmit (that's a real duplicate charge) or reuse a "
                    f"mismatched batch. Point --out somewhere else, or delete "
                    f"{record_path} if you're certain a fresh batch is wanted."
                )
                sys.exit(1)
            print(
                f"[batch] attaching to existing batch {record['batch_id']} recorded at "
                f"{record_path} -- not resubmitting"
            )
            return record["batch_id"], record["custom_id_to_qid"]

    requests = []
    custom_id_to_qid: dict[str, str] = {}
    for q in questions:
        if q.id not in prompts_cache:
            print(
                f"[ERROR] question id {q.id!r} not found in the prompts cache -- the "
                f"cache doesn't cover this question set"
            )
            sys.exit(1)
        params = _batch_request_params(
            model, prompts_cache[q.id]["system"], prompts_cache[q.id]["user"],
            max_tokens, effort, cache_prompt,
        )
        requests.append(Request(custom_id=q.id, params=MessageCreateParamsNonStreaming(**params)))
        custom_id_to_qid[q.id] = q.id

    batch = client.messages.batches.create(requests=requests)
    record = {
        "batch_id": batch.id,
        "custom_id_to_qid": custom_id_to_qid,
        "identity": identity,
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    atomic_write_json(record_path, record)
    print(
        f"[batch] submitted batch {batch.id} ({len(requests)} requests) -- "
        f"record saved to {record_path}"
    )
    return batch.id, custom_id_to_qid


def poll_batch(client, batch_id: str, poll_interval: float = 20.0):
    """Block until `batch_id` reaches processing_status == 'ended', printing
    per-poll progress. Safe to interrupt: this function holds no state of its
    own that matters across a restart -- Ctrl-C or a killed process loses
    nothing beyond the current sleep, because submit_or_attach_batch()
    already persisted the batch id to disk before poll_batch() was ever
    called. Re-running the whole script re-invokes submit_or_attach_batch()
    (which attaches instead of resubmitting -- see its docstring) and this
    function resumes polling from wherever the batch actually is
    server-side, regardless of how much progress happened while nothing was
    watching."""
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        print(
            f"[batch] {batch_id}: status={batch.processing_status} "
            f"succeeded={counts.succeeded} errored={counts.errored} "
            f"canceled={counts.canceled} expired={counts.expired} "
            f"processing={counts.processing}"
        )
        if batch.processing_status == "ended":
            return batch
        time.sleep(poll_interval)


def _answer_from_batch_result(result, prompts_cache: dict, qid: str):
    """Turn one Message Batch result into the SAME return shape
    _answer_from_frozen_prompt() produces:
    (answer, stop_reason, usage, regrounded, cr_citations_before,
    cr_citations_after) -- so the row-building code in main() cannot tell,
    and does not need to know, whether a row came from the synchronous path
    or a batch. `regrounded` is always False here: --batch refuses to
    combine with --reground (_validate_batch_combination()), so this path
    never re-asks and there is nothing to fold in.

    Per-request failures are recorded, never dropped: an errored, canceled,
    or expired result becomes a real row with answered=False and a
    stop_reason of "batch_errored" / "batch_canceled" / "batch_expired" --
    reusing the EXISTING stop_reason field rather than inventing a new
    column, so a --batch row's schema stays identical to a synchronous row
    even on failure (requirement: identical output rows). The failure
    detail (when available) lands in the answer text, which is already a
    free-text field every row has.

    Results arrive in ANY order from client.messages.batches.results() --
    this function only ever looks at the ONE result handed to it by
    `custom_id`, keyed by the caller (main()), never by position, so
    result ordering is a non-issue here."""
    user = prompts_cache[qid]["user"]
    outcome = result.result
    if outcome.type == "succeeded":
        msg = outcome.message
        text_block = next((b for b in msg.content if b.type == "text"), None)
        stop_reason = msg.stop_reason
        usage_obj = msg.usage
        usage = {
            "input_tokens": getattr(usage_obj, "input_tokens", None),
            "output_tokens": getattr(usage_obj, "output_tokens", None),
            "cache_read_input_tokens": getattr(usage_obj, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage_obj, "cache_creation_input_tokens", 0) or 0,
        }
        parsed = None
        if text_block is not None:
            try:
                parsed = Answer.model_validate_json(text_block.text)
            except ValidationError:
                parsed = None
        if parsed is None:
            return (
                Answer(
                    text="(no structured answer: the batched response did not parse "
                    f"against the Answer schema, stop_reason={stop_reason})",
                    tldr="Something went wrong generating this answer -- try again.",
                    citations=[], answered=False, suggested_followups=[],
                ),
                stop_reason, usage, False, None, None,
            )
        if "\n\nCard data:\n" in user:
            parsed.text = f"{parsed.text}\n\n{ATTRIBUTION}"
        cr_before = len(cr_rule_citations(parsed.citations))
        return (parsed, stop_reason, usage, False, cr_before, None)

    # errored / canceled / expired -- a real row, never silently dropped.
    detail = None
    if outcome.type == "errored":
        err = getattr(outcome, "error", None)
        detail = getattr(err, "message", None) or (str(err) if err is not None else None)
    return (
        Answer(
            text=f"(this question's batch request {outcome.type}"
            f"{f': {detail}' if detail else ''} -- not answered)",
            tldr="This answer was not generated -- the batch request did not succeed.",
            citations=[], answered=False, suggested_followups=[],
        ),
        f"batch_{outcome.type}", None, False, None, None,
    )


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


def _load_resumable(out_path: Path, args: argparse.Namespace,
                    prompts_cache_digest: str | None,
                    system_version_tag: int | str | None = None) -> dict[str, dict]:
    """qid -> already-written row, read off an existing output file at
    `out_path` from a prior (possibly killed) invocation of this exact
    command (docs/plan-run-progress.md Sec 4). This runner's output file is
    a plain JSON list (no top-level model/config wrapper the way
    run_openrouter_arm.py's is), so the run-defining fields to sanity-check
    against are the ones stamped onto each row.

    Coordinator-review fix, on top of the original plan: this previously
    checked rewrite_version/ruling_query_mode/show_rewrite/condition/run
    but NOT model (there was no per-row `model` field at all -- a real gap,
    now closed by stamping one below) and NOT prompts-cache identity (the
    dangerous one: docs/plan-v5-symbol-injection.md Sec 3's four-cell grid
    can share every one of those fields and differ ONLY in which prompts
    file it reads, so the old guard would have silently resumed across
    prompt variants). Two different kinds of mismatch, handled differently
    on purpose -- see run_openrouter_arm.py's _load_resumable() for the
    full reasoning, identical here:

    - model / rewrite_version / ruling_query_mode / show_rewrite /
      condition / run differ: SAFE to fall back to a fresh run (return {}),
      because resumable={} means every row gets regenerated and the file is
      fully overwritten -- old rows never mix into the new file.
    - prompts_cache identity (path + content digest) differs: HARD ERRORS
      (prints and sys.exit(1)) rather than silently resuming or
      regenerating over it -- the same reasoning as the OR arm.

    Missing file, unparseable JSON, or an empty list return {} and the run
    proceeds fresh, same as before this feature existed."""
    if not out_path.exists():
        return {}
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, list) or not data:
        return {}
    first = data[0]

    current_cache_path = str(args.prompts_cache) if args.prompts_cache else None
    recorded_cache_path = first.get("prompts_cache")
    recorded_cache_digest = first.get("prompts_cache_sha256")
    if recorded_cache_path != current_cache_path or recorded_cache_digest != prompts_cache_digest:
        print(f"[ERROR] {out_path} exists and was generated with prompts_cache="
              f"{recorded_cache_path!r} (sha256={recorded_cache_digest!r}), but this "
              f"invocation is using prompts_cache={current_cache_path!r} "
              f"(sha256={prompts_cache_digest!r}) -- refusing to silently resume from it "
              f"OR regenerate over it: these look like two different experiments aimed at "
              f"the same --out. Point --out somewhere else, or confirm this really is the "
              f"same prompts file and (if it predates this check) start a fresh --out once.")
        sys.exit(1)

    # system_version / layers_tool / max_tokens are in this guard because an
    # arm is DEFINED by them: BASE and CONTROL differ only in system_version,
    # and resuming across that difference would silently produce one file
    # holding half of each arm. Rows generated before these fields existed
    # read as None and mismatch, which correctly forces a fresh run rather
    # than mixing old rows into a new experiment.
    if (first.get("model") != args.model
            or first.get("rewrite_version") != args.rewrite_version
            or first.get("ruling_query_mode") != args.ruling_query_mode
            or first.get("show_rewrite") != args.show_rewrite
            or first.get("condition") != args.condition
            or first.get("system_version") != system_version_tag
            or first.get("layers_tool") != args.layers_tool
            or first.get("max_tokens") != args.max_tokens
            # effort defines an arm exactly the way max_tokens does: a low-effort
            # and a default-effort row are different experiments. Rows written
            # before this field existed read as None, which correctly matches an
            # unset --effort and correctly mismatches any explicit level.
            or first.get("effort") != args.effort
            # reground defines the arm exactly the way effort does (docs/
            # results-groundedness-guard.md): a reground=True row costs a
            # second generation and can carry a different answered/citations
            # value than the same question run with reground=False, so
            # mixing them into one --out would silently blend two
            # experiments. reground's default is False (not None, unlike
            # effort/system_version), so a row written before this field
            # existed reads as `first.get("reground") or False` == False --
            # matching an unset (default) --reground and still correctly
            # mismatching an explicit --reground True.
            or (first.get("reground") or False) != args.reground
            or first.get("run") != args.run):
        print(f"[resume] {out_path} exists but was generated with a different config "
              f"-- starting fresh rather than resuming from it")
        return {}
    by_id = {r["id"]: r for r in data if isinstance(r, dict) and "id" in r}
    if by_id:
        print(f"[resume] {out_path} has {len(by_id)} row(s) already -- skipping those qids")
    return by_id


def _answer_from_frozen_prompt(
    client, model: str, system: str, user: str, max_tokens: int = GEN_MAX_TOKENS,
    effort: str | None = None, cache_prompt: bool = False, reground: bool = False,
) -> tuple[Answer, str | None, dict | None, bool, int | None, int | None]:
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
    stores only the two assembled strings.

    Returns (answer, stop_reason, usage, regrounded, cr_citations_before,
    cr_citations_after) -- stop_reason/usage read off the FINAL response
    (the reground call's response when regrounding fired and produced usable
    output, otherwise the original). There is no tool loop here at all --
    this is a single messages.parse() call, never a round trip -- so callers
    must record `tool_rounds: None` for rows generated this way; that
    absence is real information, not a gap to paper over with a fake 0 or 1.

    `reground` (docs/results-groundedness-guard.md, default False): when
    True and the first draw is answered=true with zero CR-rule citations
    (needs_regrounding()), re-ask once via reground_once() -- the SAME
    shared helper RulesAgent.answer() uses, so this arm and the live path
    measure identical enforcement. regrounded is True iff that condition
    fired (independent of whether the reground call itself then produced
    parseable output); cr_citations_before/after are cr_rule_citations()
    counts on the pre-/post-reground draw, with after staying None when
    regrounding never fired. usage folds in the reground call's own tokens
    (via _sum_usage()) so a regrounded row's cost reflects both
    generations, not just one."""
    msgs: list[dict] = [{"role": "user", "content": user}]
    # `effort` and `cache_prompt` were NOT plumbed here originally, so a
    # --prompts-cache run silently generated at the API's DEFAULT effort no
    # matter what --effort said, and never cached. That is this repo's
    # recurring defect -- a value that looks present but isn't -- and it would
    # have made a frozen-prompt "high effort" arm a default-effort arm with
    # nothing raising. Both are threaded through now, using the same
    # empty-dict-when-unset shape as RulesAgent so an unset flag still
    # produces a byte-identical request.
    effort_kwargs = {"output_config": {"effort": effort}} if effort is not None else {}
    call_system = _cacheable_system(system, cache_prompt)
    parsed, response = None, None
    weak = None
    for _attempt in range(2):
        try:
            response = client.messages.parse(
                model=model, max_tokens=max_tokens, system=call_system, messages=msgs,
                output_format=Answer, **effort_kwargs,
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
    stop_reason = getattr(response, "stop_reason", None) if response is not None else None
    usage_obj = getattr(response, "usage", None) if response is not None else None
    usage = None
    if usage_obj is not None:
        usage = {
            "input_tokens": getattr(usage_obj, "input_tokens", None),
            "output_tokens": getattr(usage_obj, "output_tokens", None),
            "cache_read_input_tokens": getattr(usage_obj, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage_obj, "cache_creation_input_tokens", 0) or 0,
        }
    regrounded = False
    cr_before = None
    cr_after = None
    if parsed is not None:
        # Only a genuine successful draw (not the empty/degenerate-fallback
        # paths below) is ever eligible -- an honest answered=false decline
        # never matches needs_regrounding() anyway, so this is never reached
        # for the `weak` fallback case.
        cr_before = len(cr_rule_citations(parsed.citations))
        if reground and needs_regrounding(parsed):
            regrounded = True
            new_parsed, new_response = reground_once(
                client, model, system, msgs, response, max_tokens,
                effort=effort, cache_prompt=cache_prompt,
            )
            if new_parsed is not None:
                # Take the re-ask's own answer (including its own `answered`
                # value) verbatim -- never overwritten back to True.
                parsed = new_parsed
                cr_after = len(cr_rule_citations(parsed.citations))
                stop_reason = getattr(new_response, "stop_reason", stop_reason)
                usage = _sum_usage(usage, _usage_dict(new_response))
            # else: the reground call itself came back empty/invalid --
            # keep the ORIGINAL parsed untouched; cr_after stays None
            # (distinct from 0, which means it fired and still came back
            # uncited).
    if parsed is None and weak is not None:
        parsed = weak
    if parsed is None:
        stop = response.stop_reason if response is not None else "error"
        return Answer(
            text="(no structured answer: the model returned empty output "
            f"twice, stop_reason={stop} -- try again)",
            tldr="Something went wrong generating this answer -- try again.",
            citations=[], answered=False, suggested_followups=[],
        ), stop_reason, usage, regrounded, cr_before, cr_after
    if "\n\nCard data:\n" in user:
        parsed.text = f"{parsed.text}\n\n{ATTRIBUTION}"
    return parsed, stop_reason, usage, regrounded, cr_before, cr_after


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
        "--qids", type=str, default=None,
        help="comma-separated list of specific question ids to run (e.g. c012,c014,c015) "
        "-- a scattered subset, unlike --limit's prefix; run in master-questions-file order "
        "regardless of the order given here. Mutually exclusive with --limit.",
    )
    p.add_argument(
        "--rewrite-version", choices=["v1", "v2", "none"], default="v2",
        help="rewriter SYSTEM prompt version, threaded into RulesAgent(rewrite_version=...) "
        "(default: v2 -- the shipped default; prompt-v3 A/B condition B needs v1, docs/"
        "plan-v3-execution-tasks.md Task 2). 'none' skips the rewriter entirely -- maps to "
        "RulesAgent(rewrite=False), so the raw question goes to retrieval and no "
        "claude-haiku-4-5 rewriter call is made (docs/spec-effort-and-norewrite.md Task 2). "
        "Recorded verbatim, so a no-rewrite run can never be read back as a v2 run.",
    )
    p.add_argument(
        "--cache-prompt", action="store_true",
        help="put cache_control on the system prompt (RulesAgent(cache_prompt=True)). "
        "Default OFF, which sends a byte-identical request to every pre-caching run. "
        "SYSTEM is ~1,400 tokens and identical per question, so this pays back from the "
        "second question with the same prefix onward; the big win is ablation, which "
        "re-sends one prefix hundreds of times. Verify it worked by checking "
        "cache_read_input_tokens > 0 in the output rows -- a silently-ignored "
        "cache_control bills full price and raises nothing.",
    )
    p.add_argument(
        "--effort", choices=sorted(GEN_EFFORT_LEVELS), default=None,
        help="output_config.effort for the generation call, threaded into "
        "RulesAgent(effort=...). Default: NOT PASSED -- omitted from the request body "
        "entirely, so a run without this flag is byte-identical to before (same "
        "default-off discipline as run_openrouter_arm.py's --reasoning). Cost is ~90%% "
        "thinking tokens, so this is the primary cost lever. Recorded per row and "
        "enforced by the resume guard: an effort arm and a default arm are different "
        "experiments (docs/spec-effort-and-norewrite.md Task 1).",
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
        "--system-version", type=str, default=None,
        help="RulesAgent system_version key from SYSTEM_VERSIONS (an int prompt version "
        "such as 3 or 4, or a string tag such as 'v4nl' or 'v3+613' -- the Slice 0 "
        "control-arm bullet, docs/spec-slice0-harness.md Task 2). Default: production "
        f"PROMPT_VERSION ({PROMPT_VERSION}). Passed straight into "
        "RulesAgent(system_version=...) and recorded in each output row.",
    )
    p.add_argument(
        "--layers-tool",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="attach the resolve_layers tool when its calibrated trigger fires (default: "
        "on). --no-layers-tool suppresses it entirely regardless of the trigger -- needed "
        "for a Slice 0 arm run, where neither arm may carry the layers tool (docs/spec-"
        "slice0-harness.md Task 1). Passed straight into RulesAgent(layers_tool=...) and "
        "recorded in each output row for provenance.",
    )
    p.add_argument(
        "--max-tokens", type=int, default=GEN_MAX_TOKENS,
        help=f"generation output cap (default: production's {GEN_MAX_TOKENS}). sonnet-5's "
        "max_tokens bounds adaptive thinking AND visible text together, so on hard "
        "multi-step questions the cap is spent mostly on thinking -- 8%% of the Slice 0 "
        "bucket-A arm truncated at 16384, and rg131 returned a 98-char degrade sentinel "
        "after burning the whole budget twice. Raising this REQUIRES --request-timeout: "
        "the SDK refuses a non-streaming request whose max_tokens implies a >10-minute "
        "run, so 32768 errors out on its own.",
    )
    p.add_argument(
        "--request-timeout", type=float, default=GEN_REQUEST_TIMEOUT,
        help="per-request timeout in SECONDS, passed to the SDK via with_options(). "
        "Default: unset (SDK default, 10 min). Its real job here is suppressing the "
        "SDK's non-streaming max_tokens timeout guard so --max-tokens can be raised "
        "at all. Streaming is the better long-term fix (residuals, rg3391); this is "
        "the cheap one and leaves the messages.parse() structured-output path alone.",
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
    p.add_argument(
        "--reground",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="re-ask once when a draw is answered=true with zero CR-rule citations "
        "(docs/results-groundedness-guard.md) -- applies on BOTH the live agent.answer() "
        "path (threaded into RulesAgent(reground=...)) and the --prompts-cache path "
        "(threaded into _answer_from_frozen_prompt(reground=...)), so either arm can be "
        "measured. Default OFF: every existing arm's requests/numbers stay byte-identical "
        "unless this is explicitly turned on. Recorded per row: reground (this flag), "
        "regrounded (did the re-ask actually fire), cr_citations_before/after.",
    )
    p.add_argument(
        "--batch",
        action="store_true",
        help="submit questions to the Anthropic Message Batches API (50%% of sync price) "
        "instead of calling messages.parse() per question. ONLY supported on the "
        "--prompts-cache path -- refused with an [ERROR] and exit 1 if combined with the "
        "live agent.answer() path (no --prompts-cache) or with --reground (see "
        "_validate_batch_combination()). Submission is durable (batch id + custom_id->qid "
        "mapping written to evals/answers/_batches/<out-stem>.batch.json immediately on "
        "submit) and resumable: re-running against the same --out with the same config "
        "attaches to the existing batch instead of resubmitting.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Collapse the TWO ways of turning the rewriter off into one derived truth,
    # immediately, before anything reads either of them
    # (docs/spec-effort-and-norewrite.md Task 2).
    #
    # This runner already had --no-rewrite (a BooleanOptionalAction feeding
    # RulesAgent(rewrite=...)) before --rewrite-version gained "none". Left
    # unreconciled they are two independent switches for one behaviour, and any
    # disagreement between them writes a run file that lies: "--rewrite-version
    # none" alone would record rewrite_version="none" while the rewriter still
    # ran, and "--no-rewrite" alone would record "v2" for a run that never
    # rewrote anything. Either way the provenance -- and the resume guard that
    # reads it -- is wrong.
    #
    # Normalising onto args HERE means the agent construction, the per-row
    # record, and the resume guard all read the same two fields and cannot
    # disagree. Rewriting off is the sticky state: if either flag says off,
    # it is off, and rewrite_version records "none".
    if args.rewrite_version == "none":
        args.rewrite = False
    if not args.rewrite:
        args.rewrite_version = "none"

    # Fail fast on an unsupported --batch combination, before any of the
    # expensive setup below (CR parsing, vector index load) runs.
    _validate_batch_combination(args.batch, args.prompts_cache, args.reground)

    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    chunk_map = {c.source_id: c for c in chunks}

    pkl = PARSED_DIR / f"vector_{VECTOR_MODEL}.pkl"
    if not pkl.exists():
        print(f"[ERROR] no vector index at {pkl.name}; run build_vector_indexes.py")
        return
    store = VectorStore.load(pkl)

    # Slice 0 harness (docs/spec-slice0-harness.md Task 2c): --system-version
    # is a free-form string on the CLI (argparse has no clean way to accept
    # "either an int or a string" directly) since SYSTEM_VERSIONS keys are a
    # mix of both (3, 4, "v4nl", "v3+613") -- resolve it to the real key type
    # here, same int-else-string coercion evals/build_prompts_variant.py's
    # own VARIANTS table encodes by hand per letter. None (not given) means
    # production: PROMPT_VERSION, unchanged from before this flag existed.
    if args.system_version is None:
        system_version: int | str = PROMPT_VERSION
    else:
        try:
            system_version = int(args.system_version)
        except ValueError:
            system_version = args.system_version  # a string tag, e.g. "v4nl"

    agent = RulesAgent(
        store, model=args.model, rewrite=args.rewrite, show_rewrite=args.show_rewrite,
        rewrite_version=args.rewrite_version, ruling_query_mode=args.ruling_query_mode,
        system_version=system_version, layers_tool=args.layers_tool,
        max_tokens=args.max_tokens, request_timeout=args.request_timeout,
        effort=args.effort, cache_prompt=args.cache_prompt,
        reground=args.reground,
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
    prompts_cache_digest = None
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
        # Resume-safety fix (same as run_openrouter_arm.py): the
        # content-derived identity of THIS cache, stamped onto every row
        # below and checked in _load_resumable().
        prompts_cache_digest = prompts_cache_sha256(prompts_cache)

    questions = load_questions(args.questions)
    answer_gold = load_answer_gold(args.questions)
    if args.qids is not None and args.limit is not None:
        print("[ERROR] --qids and --limit cannot be used together -- they are two "
              "different subsetters and the precedence would be ambiguous; pick one")
        sys.exit(1)
    if args.qids is not None:
        try:
            questions = select_qids(questions, args.qids)
        except QidFilterError as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
    elif args.limit is not None:
        questions = questions[: args.limit]
    print(
        f"Generating {len(questions)} answers | model={args.model} "
        f"| rewrite={args.rewrite} | show_rewrite={args.show_rewrite} "
        f"| rewrite_version={args.rewrite_version} | ruling_query_mode={args.ruling_query_mode} "
        f"| condition={args.condition} | run={args.run} "
        f"| prompts_cache={args.prompts_cache} "
        f"| system_version={system_version} | layers_tool={args.layers_tool} "
        f"| questions={args.questions.name}\n"
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Resume (docs/plan-run-progress.md Sec 4): qids already written by a
    # prior (possibly killed) invocation at this exact --out, under a
    # matching config -- skipped below rather than regenerated. Hard-errors
    # (sys.exit(1)) instead of returning on a prompts-cache identity
    # mismatch -- see _load_resumable()'s docstring.
    resumable = _load_resumable(args.out, args, prompts_cache_digest, system_version)

    # --batch: submit + poll + collect ALL pending questions' results up
    # front, before the per-question loop below ever runs. Only qids not
    # already resumed from --out are submitted, so re-running a partially
    # graded --out after a batch never re-pays for rows already on disk.
    batch_results_by_qid: dict[str, tuple] = {}
    if args.batch:
        pending = [q for q in questions if q.id not in resumable]
        if pending:
            batch_id, custom_id_to_qid = submit_or_attach_batch(
                agent._gen_client, args.out, pending, prompts_cache, args.model,
                args.max_tokens, args.effort, args.cache_prompt,
                args.prompts_cache, prompts_cache_digest,
            )
            poll_batch(agent._gen_client, batch_id)
            results_by_custom_id = {
                r.custom_id: r for r in agent._gen_client.messages.batches.results(batch_id)
            }
            for custom_id, qid in custom_id_to_qid.items():
                result = results_by_custom_id.get(custom_id)
                if result is None:
                    print(
                        f"[WARN] batch {batch_id} returned no result for custom_id="
                        f"{custom_id!r} (qid={qid}) -- recording an honest error row "
                        f"rather than silently skipping it"
                    )
                    batch_results_by_qid[qid] = (
                        Answer(
                            text=f"(no batch result returned for this question, batch={batch_id})",
                            tldr="This answer was not generated.", citations=[],
                            answered=False, suggested_followups=[],
                        ),
                        "batch_missing_result", None, False, None, None,
                    )
                else:
                    batch_results_by_qid[qid] = _answer_from_batch_result(result, prompts_cache, qid)
        else:
            print("[batch] every question already resumed from --out -- nothing to submit")

    results = []
    start = time.time()
    hb = Heartbeat(run=args.out.stem, model=args.model, variant=args.condition,
                   n_total=len(questions))
    success = False
    try:
        for i, q in enumerate(questions, 1):
            t0 = time.time()
            if q.id in resumable:
                row = resumable[q.id]
                results.append(row)
                print(f"  [{i}/{len(questions)}] {q.id} -> resumed (already in {args.out.name})")
            else:
                if args.batch:
                    if q.id not in batch_results_by_qid:
                        print(f"[ERROR] question id {q.id!r} has no batch result -- this "
                              f"should be unreachable (every non-resumed question is "
                              f"submitted to the batch above)")
                        sys.exit(1)
                    ans, stop_reason, usage, regrounded, cr_before, cr_after = batch_results_by_qid[q.id]
                    # Same honest gap as the non-batch --prompts-cache path just
                    # below: no tool loop exists on either frozen-prompt path.
                    tool_calls = None
                    tool_rounds = None
                elif prompts_cache is not None:
                    if q.id not in prompts_cache:
                        print(f"[ERROR] question id {q.id!r} not found in {args.prompts_cache} -- "
                              f"the cache doesn't cover this question set")
                        return
                    ans, stop_reason, usage, regrounded, cr_before, cr_after = _answer_from_frozen_prompt(
                        # agent._gen_client, not agent.client: the raw client
                        # has no timeout override, and GEN_MAX_TOKENS is above
                        # the SDK's non-streaming guard, so the plain client
                        # would be refused before reaching the API. Inheriting
                        # agent.max_tokens also stops this path drifting to a
                        # different budget than RulesAgent.answer() uses.
                        agent._gen_client, args.model,
                        prompts_cache[q.id]["system"], prompts_cache[q.id]["user"],
                        agent.max_tokens,
                        # Previously omitted, so --effort was silently dropped on
                        # this path and a frozen "high effort" arm really ran at
                        # the API default. Both flags now reach the request.
                        effort=args.effort, cache_prompt=args.cache_prompt,
                        reground=args.reground,
                    )
                    # No tool loop on this path at all -- the absence is real
                    # (docs/spec-slice0-harness.md Task 3), never faked as 0/1/[].
                    tool_calls = None
                    tool_rounds = None
                else:
                    ans = agent.answer(q.question)
                    stop_reason = agent.last_stop_reason
                    usage = agent.last_usage
                    tool_calls = agent.last_tool_calls
                    tool_rounds = agent.last_tool_rounds
                    regrounded = agent.last_regrounded
                    cr_before = agent.last_cr_citations_before
                    cr_after = agent.last_cr_citations_after
                rewritten = agent.last_rewritten  # None when --no-rewrite, or when using --prompts-cache
                # agent.last_retrieved: list[Retrieved] (rulesagent.contracts) set by
                # RulesAgent.answer() right before the generation call -- None when
                # --prompts-cache bypassed answer() entirely via
                # _answer_from_frozen_prompt() above, same honest-gap treatment as
                # rewrite_queries/clarification just above.
                retrieved_rule_ids = ([r.chunk.source_id for r in agent.last_retrieved]
                                      if agent.last_retrieved is not None else [])
                # Citation-source classification (docs/results-groundedness-
                # guard.md, the "which source" monitor). Two ways to get
                # AvailableSources depending on which generation path just
                # ran (mirrors the retrieved_rule_ids honest-gap split
                # above): --prompts-cache bypassed agent.answer() entirely,
                # so the only thing on hand is the frozen prompt TEXT it was
                # generated from; the live path already holds the exact
                # structured objects (agent.last_retrieved / .last_cards),
                # so no prompt text is parsed at all there.
                if prompts_cache is not None:
                    sources = available_sources_from_prompt_text(
                        prompts_cache[q.id]["user"]
                    )
                else:
                    sources = available_sources_from_context(
                        agent.last_retrieved or [], agent.last_cards or [],
                    )
                citation_breakdown = citation_source_breakdown(ans.citations, sources)
                # What reached the model outside retrieval this run, via the
                # system prompt (always) and tool-schema descriptions (when
                # the run's layers_tool switch is on -- see
                # rulesagent.generate.answer.prompt_supplied_rule_ids).
                # Recorded per row (not just derivable from system_version/
                # layers_tool below) so the corrected coverage metric is
                # self-describing even if a future arm mixes configs within
                # one output file.
                prompt_supplied_ids = sorted(
                    prompt_supplied_rule_ids(system_version, args.layers_tool)
                )

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
                    # Resume-safety fix (coordinator review, on top of the
                    # original plan): this schema previously had no per-row
                    # `model` field at all, and no prompts-cache identity
                    # -- both needed so _load_resumable() can actually tell
                    # two different experiments apart at the same --out.
                    # See its docstring for the full reasoning.
                    "model": args.model,
                    "prompts_cache": str(args.prompts_cache) if args.prompts_cache else None,
                    "prompts_cache_sha256": prompts_cache_digest,
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
                    # New: what retrieval actually returned for this question, in
                    # RANK ORDER (the miss-partition diagnostic's near-miss bucket
                    # needs rank, not just membership) -- Chunk.source_id per hit,
                    # NOT rule_id (Chunk has no such field). Additive only: every
                    # field above is unchanged in name/shape/value.
                    "retrieved_rule_ids": retrieved_rule_ids,
                    # New: ids the model had in context regardless of
                    # retrieval, for the corrected coverage metric (see
                    # prompt_supplied_ids comment above). Additive only.
                    "prompt_supplied_rule_ids": prompt_supplied_ids,
                    # Slice 0 harness telemetry (docs/spec-slice0-harness.md
                    # Task 3). stop_reason makes rg3391-class max_tokens
                    # truncation visible instead of silently scoring as an
                    # ordinary wrong answer. tool_rounds is None only on the
                    # --prompts-cache path (no tool loop exists there at all
                    # -- a real absence, never faked as 0/1). system_version/
                    # layers_tool are constant across the whole run but
                    # stamped per row for provenance, same reasoning as the
                    # existing model/rewrite_version fields above.
                    "stop_reason": stop_reason,
                    "tool_calls": tool_calls,
                    "tool_rounds": tool_rounds,
                    "usage": usage,
                    "system_version": system_version,
                    "layers_tool": args.layers_tool,
                    # Recorded because _load_resumable() compares it: an arm
                    # generated at a different cap is a different experiment,
                    # and without this field the comparison is None != 32768 on
                    # every row, which silently disables resume entirely.
                    "max_tokens": args.max_tokens,
                    # Same reasoning as max_tokens directly above: _load_resumable()
                    # compares it, and effort defines the arm. Records the value
                    # actually passed -- None stays null rather than being
                    # defaulted to a string, so a row predating this field
                    # matches an unset --effort and mismatches any explicit level.
                    "effort": args.effort,
                    # Groundedness-guard experiment fields (docs/results-
                    # groundedness-guard.md), additive only. "reground" is
                    # whether the flag was ON for this whole run (constant
                    # per file, stamped per row for provenance like model/
                    # system_version above); "regrounded" is whether the
                    # re-ask actually fired for THIS row; cr_citations_before/
                    # after are cr_rule_citations() counts pre-/post-reground
                    # (after is None when regrounding never fired for this
                    # row -- distinct from 0, which means it fired and still
                    # came back uncited). usage above already folds in the
                    # reground call's own tokens when it fired.
                    "reground": args.reground,
                    "regrounded": regrounded,
                    "cr_citations_before": cr_before,
                    "cr_citations_after": cr_after,
                    # Batch API provenance, additive only (docs on --batch
                    # above _validate_batch_combination()): whether THIS row
                    # was generated through the Message Batches API (50% of
                    # sync price) rather than a synchronous call. Downstream
                    # cost tooling should pass batch=row["batch"] to
                    # rulesagent.pricing.cost_usd() -- omitting it on a batch
                    # row overstates spend by 2x.
                    "batch": bool(args.batch),
                    # Citation-source classifier (docs/results-groundedness-
                    # guard.md), additive only. "cites_cr_rule" is the bool
                    # the spec calls out on its own; "citation_sources" is
                    # the full per-row breakdown -- per-citation labels
                    # (same order as "citations" above), the four counts,
                    # and the mutually-exclusive row "category"
                    # (cr_reliant / rulings_or_cards_only /
                    # nothing_resolvable -- the three rows of the table in
                    # the doc that sum to 100%). See
                    # evals/grounding_sources.py for the per-arm rates this
                    # feeds, and for how an OLDER row (predating these two
                    # keys) gets scored retroactively from its own recorded
                    # "prompts_cache" path instead.
                    "cites_cr_rule": citation_breakdown["cites_cr_rule"],
                    "citation_sources": {
                        "labels": citation_breakdown["labels"],
                        "cr_rule": citation_breakdown["cr_rule"],
                        "ruling": citation_breakdown["ruling"],
                        "card": citation_breakdown["card"],
                        # Glossary terms (docs/results-groundedness-guard.md
                        # coordinator amendment): a non-numeric id genuinely
                        # present in the rules context ("Saga", "City's
                        # Blessing") -- grounded, not fabrication. Additive;
                        # rows from before this amendment simply lack the key.
                        "glossary": citation_breakdown["glossary"],
                        "unresolved": citation_breakdown["unresolved"],
                        "category": citation_breakdown["category"],
                    },
                }
                if q.id in answer_gold:
                    # Carried through only for questions that have it (RulesGuru
                    # rows) -- judge_rulesguru.py reads it straight off this row
                    # rather than re-joining against the source jsonl.
                    row["answer_gold"] = answer_gold[q.id]
                results.append(row)
                print(f"  [{i}/{len(questions)}] {q.id} ({time.time() - t0:.1f}s)")

            # Incremental write (Sec 4): this runner's output file is a
            # plain list (unlike run_openrouter_arm.py's dict-with-summary),
            # so the partial write is just the results-so-far list, same
            # shape the final write below produces with fewer elements.
            atomic_write_json(args.out, results)
            # No per-row error concept in this schema (unlike the OR arm's
            # row["error"]) and no usage/cost field on the sonnet path
            # (plan Sec 2) -- errored stays False and cost_delta stays
            # unpassed, so cost_so_far renders null rather than a fake 0.
            hb.tick(q.id, errored=False)

        success = True
    finally:
        hb.finish(success)

    atomic_write_json(args.out, results)

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
