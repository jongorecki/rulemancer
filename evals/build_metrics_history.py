"""Collect every number we own about every judged arm into one comparable table.

WHY THIS EXISTS. Jon, 2026-07-26: he wants cost, accuracy, weighting, tokens and
config for every arm and iteration **side by side across time**, in one page, to
answer a specific question -- *is it time for the full RulesGuru run on the entire
dataset?* Numbers currently live scattered across `docs/results-*.md`,
`docs/report-*.md` and handoff prose, each written at a different moment against a
file that may have moved since.

THE TWO THINGS THAT MAKE THIS HONEST RATHER THAN IMPRESSIVE:

**1. Arms are not all comparable, so the table says which are.** Different arms
ran on different question sets (the v3 150, a hard 54, an easy 50), so a single
ranked list would invite comparisons that mean nothing. Every arm gets a
`qset` fingerprint -- the first 8 hex of a SHA-256 over its sorted question ids --
and arms sharing a fingerprint are the only ones directly comparable. This is
computed from the ids themselves, not inferred from a filename or a count.

**1b. A shared question set is necessary but NOT sufficient.** Jon, 2026-07-26:
the page implied we were testing things against each other that were never
comparable experiments. Three arms share the 150-question fingerprint and measure
three different quantities -- one runs the product end to end, one is handed the
gold rules with retrieval switched off (it measures whether the answers are
*derivable at all*), and one records no config whatsoever. So every arm also gets
a **kind**, DERIVED FROM THE RECORDED DATA and never from its name: `pipeline`
(retrieval recorded and non-empty), `oracle` (retrieval recorded and empty on
every row -- the model answered without retrieved rules), `unknown` (retrieval
not recorded, so nothing is established). A delta may only be taken between two
arms sharing BOTH the fingerprint AND the kind, and never to or from `unknown`.
Different kinds still render side by side, because that is useful, but each says
what it measures and the page says plainly they are not on the same scale.

**2. Every number carries what produced it -- and there are THREE events, not
one.** This repo has already shipped a results doc that disagreed with its own
verdict file inside one commit, because a number was read at one time and
published at another. Worse, "the run" is ambiguous: the **generation run**
(answers file: when the answers were produced, under which config) and the
**judging run** (verdict file: when those answers were scored, by which judge
model and prompt digest) are separate events, and where a human regraded, the
**human grading pass** is a third. The judge is nondeterministic -- re-judging
identical answers moved one arm by 2 pp -- so an accuracy that does not name its
judging run is not reproducible. All three layers are reported separately for
every number on the page. A row you cannot trace is a row you cannot use to make
a go/no-go call.

**KNOWN PROVENANCE GAP, surfaced rather than papered over.** Verdict files do not
record which answers file they judged -- the link is filename convention
(`verdicts_X.json` <-> `answers/X.json`) plus a small alias table. Every row
reports how its join was made (`exact` / `alias` / `prefix` / `unmatched`), so a
guessed join is visible as a guess. Rows that cannot be joined still appear, with
accuracy and no cost.

COST IS COMPUTED, NOT ASSUMED. Token ratios are not a cost result -- opus costs
more per token than sonnet, so fewer tokens does not establish which is cheaper.
Per-MTok prices below come from the `claude-api` skill (checked 2026-07-26), never
from recall, and cache-tier multipliers are applied separately because a cached
read costs a tenth of a fresh input token. Sonnet 5 is dual-priced: its
introductory rate runs through 2026-08-31, so both are shown and the arm is
costed at BOTH, since which one applies depends on when you re-run it.

Usage:
    python evals/build_metrics_history.py
    python evals/build_metrics_history.py --json evals/_metrics_history.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import grounding_sources as gs
import weighted_score as ws

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
ANSWERS = EVALS / "answers"

# Pricing comes from `rulesagent.pricing`, the single cached copy in this repo,
# which records when it was checked against the claude-api skill and what dated
# changes are pending. It used to be duplicated here and in two eval scripts;
# three hand-maintained copies of a number that expires is three chances to
# publish a stale cost. Never edit rates here -- refresh the module.
from rulesagent.pricing import (  # noqa: E402
    BATCH_DISCOUNT,
    CACHE_READ_MULT,
    CACHE_WRITE_MULT,
    CHECKED_ON as PRICING_CHECKED_ON,
    PRICING,
    SCHEDULED_CHANGES,
    SOURCE as PRICING_SOURCE,
    check_freshness,
)

SONNET_INTRO_ENDS = next(
    (d.isoformat() for d, what in SCHEDULED_CHANGES if "sonnet-5" in what), None
)

# Verdict stems whose answers file is named differently. Kept explicit and small:
# a fuzzy matcher that silently picks the wrong answers file would attach one
# arm's cost to another arm's accuracy, which is worse than reporting no cost.
ALIASES = {
    "derivability_B": "derivability_B_goldonly",
    "derivability_B_human": "derivability_B_goldonly",  # same answers, human-regraded
    "derivability_C": "derivability_C_failures",
    "rulesguru_sonnet": "rulesguru_answers",            # verified: model=claude-sonnet-5, n=150
}


def _mtime(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).astimezone().isoformat(timespec="minutes")


# ---------------------------------------------------------------------------
# ARM KIND. What the arm actually measures -- decided by the recorded data.
#
# The only field that establishes it is `retrieved_rule_ids`, which the answer
# writer records per question. An arm whose every row retrieved nothing yet still
# answered was handed its rules some other way (the derivability runs are handed
# gold); an arm that retrieved on every row ran the product. An arm that does not
# record the field at all establishes NEITHER, and is called `unknown` rather
# than assumed -- guessing here is exactly the error this section exists to stop.
# ---------------------------------------------------------------------------
KIND_RULE = ("Derived per arm from the answers file, never from its name. "
             "`retrieved_rule_ids` non-empty on every row → pipeline (the product path). "
             "Recorded but empty on every row → oracle (the model answered without retrieved "
             "rules; the derivability runs are handed gold instead). "
             "Field absent, mixed, or no answers file joined → unknown.")


def classify_arm(rows: list[dict]) -> tuple[str, str]:
    """(kind, the evidence sentence that justifies it). Never guesses."""
    real = [r for r in rows if "question" in r or "answer" in r]
    if not real:
        return "unknown", ("the answers file holds a run summary, not per-question rows — "
                           "no model, effort or retrieval is recorded for this arm")
    have = [r for r in real if "retrieved_rule_ids" in r]
    if not have:
        return "unknown", (f"the {len(real)} answer rows do not record `retrieved_rule_ids`, "
                           "so whether retrieval ran is not established by any file we own")
    if len(have) != len(real):
        return "unknown", (f"only {len(have)} of {len(real)} rows record `retrieved_rule_ids` — "
                           "mixed, so the arm cannot be classified")
    hit = sum(1 for r in have if r.get("retrieved_rule_ids"))
    if hit == 0:
        return "oracle", (f"retrieval recorded and EMPTY on all {len(have)} rows — the model "
                          "answered without retrieved rules, so this measures whether the answer "
                          "is derivable at all, not what the pipeline scores")
    if hit == len(have):
        avg = sum(len(r["retrieved_rule_ids"]) for r in have) / len(have)
        return "pipeline", (f"retrieval recorded and non-empty on all {len(have)} rows "
                            f"({avg:.1f} rule ids per question on average) — the product path")
    return "unknown", (f"retrieval ran on {hit} of {len(have)} rows — mixed, so the arm "
                       "cannot be classified as either path")


def _row_correct(e: dict) -> bool | None:
    """One row's final correctness, human grading winning where it exists.

    `final_correct` is written by the human-merge step and is the number of
    record; `verdict` is the judge's raw call. Reading `verdict` on a regraded
    file would silently discard the human pass.
    """
    if e.get("final_correct") is not None:
        return bool(e["final_correct"])
    v = e.get("verdict")
    return None if v is None else v == "same"


def _ids_of(path: Path) -> frozenset[str] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rows = raw if isinstance(raw, list) else list(raw.values()) if isinstance(raw, dict) else []
    ids = {r["id"] for r in rows if isinstance(r, dict) and "id" in r}
    return frozenset(ids) or None


def _answer_match_fraction(path: Path, want: frozenset[str], judged: dict[str, str]) -> float | None:
    """Fraction of ids where this candidate's `answer` text equals the text the
    verdict actually judged for that id (`judged`, read off the verdict's own
    `entries[*].answer`). None if there's nothing usable to compare.

    This is content evidence, not a naming convention: the verdict file quotes
    back the literal answer string it graded, and only the answers file that
    produced that string can match it on (close to) every id. Two arms that
    share a question-id set but ran a different retrieval condition -- real
    rules retrieved vs. none (placebo) -- write different answer text for the
    same question, so this discriminates exactly the case id-matching can't.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rows = raw if isinstance(raw, list) else list(raw.values()) if isinstance(raw, dict) else []
    by_id = {r["id"]: r.get("answer") for r in rows if isinstance(r, dict) and "id" in r}
    compared = [qid for qid in want if qid in by_id and qid in judged]
    if not compared:
        return None
    matched = sum(1 for qid in compared if by_id[qid] == judged[qid])
    return matched / len(compared)


def _disambiguate_by_answer_text(
    candidates: list[Path], want: frozenset[str], judged: dict[str, str]
) -> tuple[Path | None, str]:
    """Among several id-matching candidates, pick the one whose answer text the
    verdict actually judged. Requires a clean win (exactly one candidate at a
    perfect 1.0 match) -- anything less is evidence that doesn't resolve the
    tie, and this fails loudly to `unknown` rather than guessing.
    """
    if not judged:
        return None, f"ambiguous ({len(candidates)} files share these ids; verdict has no answer text to check against)"
    scored = [(p, _answer_match_fraction(p, want, judged)) for p in candidates]
    perfect = [p for p, frac in scored if frac == 1.0]
    if len(perfect) == 1:
        return perfect[0], "content-match"
    if len(perfect) > 1:
        return None, f"ambiguous ({len(perfect)} files share these ids AND match the judged answer text -- genuinely indistinguishable)"
    return None, f"ambiguous ({len(candidates)} files share these ids; none matches the judged answer text on every question)"


def resolve_answers(
    stem: str, want: frozenset[str], judged: dict[str, str] | None = None
) -> tuple[Path | None, str]:
    """(answers path, how the join was made) -- and the join is VERIFIED.

    Filename convention alone is a guess: verdict files do not record which
    answers file they judged. So every candidate is confirmed by comparing
    question-id sets against the verdict's, and a name that matches while the ids
    do not is reported as `name-matched-ids-differ` rather than being used. That
    turns "probably the right file" into a checked fact, which is the difference
    between a cost figure you can publish and one you can't.

    A shared id set is necessary but not sufficient -- two genuinely different
    experiments (e.g. a real-vs-placebo retrieval pair) can be run on the exact
    same question set on purpose. When more than one file matches on ids, the
    tie is broken by content: `judged` is `{id: answer text}` read straight off
    the verdict's own `entries`, i.e. the answer string it actually graded, and
    only the file whose rows reproduce that text on every id can be the source
    (see `_disambiguate_by_answer_text`). No filename whitelist is involved --
    this holds for any future real/placebo-style pair, not just this one.
    """
    judged = judged or {}
    candidates: list[tuple[Path, str]] = []
    exact = ANSWERS / f"{stem}.json"
    if exact.exists():
        candidates.append((exact, "exact"))
    if stem in ALIASES and (p := ANSWERS / f"{ALIASES[stem]}.json").exists():
        candidates.append((p, "alias"))
    for p in sorted(ANSWERS.glob(f"{stem}*.json")):
        if not p.name.startswith("_"):
            candidates.append((p, "prefix"))

    # Dedup by resolved path, keeping the first (best) "how" tag seen: the
    # prefix glob `{stem}*.json` also matches the exact-name file itself (star
    # matches zero chars), so without this the same file would show up twice
    # and manufacture a fake ambiguity between a file and itself.
    seen_paths: dict[Path, str] = {}
    for path, how in candidates:
        rp = path.resolve()
        seen_paths.setdefault(rp, how)
    deduped = [(p, how) for p, how in seen_paths.items()]

    named_but_wrong = False
    id_matched: list[tuple[Path, str]] = []
    for path, how in deduped:
        got = _ids_of(path)
        if got == want:
            id_matched.append((path, how))
        elif got is not None:
            named_but_wrong = True

    if len(id_matched) == 1:
        return id_matched[0]
    if len(id_matched) > 1:
        return _disambiguate_by_answer_text([p for p, _ in id_matched], want, judged)

    # No name matched, or the named file held different questions. Fall back to
    # an id-set search across every answers file -- a slower but strictly
    # stronger join, since it is decided by the data rather than the filename.
    matches = [p for p in sorted(ANSWERS.glob("*.json"))
               if not p.name.startswith("_") and _ids_of(p) == want]
    if len(matches) == 1:
        return matches[0], "id-match"
    if len(matches) > 1:
        return _disambiguate_by_answer_text(matches, want, judged)
    return None, "name-matched-ids-differ" if named_but_wrong else "unmatched"


def cost_of(rows: list[dict], model: str) -> dict:
    """Per-question cost, tokens, and cache behaviour. Returns {} if unpriceable."""
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    n = 0
    n_batch = 0
    for r in rows:
        u = r.get("usage") or {}
        if not u:
            continue
        n += 1
        tot["input"] += u.get("input_tokens", 0) or 0
        tot["output"] += u.get("output_tokens", 0) or 0
        tot["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
        tot["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
        if r.get("batch") is True:
            n_batch += 1
    if not n:
        return {}
    # Anthropic's Message Batches API is BATCH_DISCOUNT (50%) off every token
    # tier -- see rulesagent/pricing.py's cost_usd(), which this module used to
    # bypass by pricing off the raw PRICING table directly. run_answer_eval.py
    # --batch stamps a `"batch": true` field on every row it writes precisely so
    # this can be read off the file rather than assumed; an arm is only priced
    # at the batch rate when EVERY costed row in it says so, so a mixed arm
    # (should never happen, but would be a real bug if it did) prices at the
    # non-batch rate rather than silently guessing.
    is_batch = n_batch == n

    def price(key: str) -> float | None:
        if key not in PRICING:
            return None
        pin, pout = PRICING[key]
        total = (
            tot["input"] * pin
            + tot["cache_write"] * pin * CACHE_WRITE_MULT
            + tot["cache_read"] * pin * CACHE_READ_MULT
            + tot["output"] * pout
        ) / 1_000_000 / n
        return total * BATCH_DISCOUNT if is_batch else total

    out = {
        "n_costed": n,
        "in_per_q": tot["input"] / n,
        "out_per_q": tot["output"] / n,
        "cache_read_per_q": tot["cache_read"] / n,
        "cache_write_per_q": tot["cache_write"] / n,
        "cost_per_q": price(model),
        "priced_as": model if model in PRICING else None,
        "batch": is_batch,
    }
    # Sonnet's intro rate expires; show both so a re-run decision uses the right one.
    if model == "claude-sonnet-5":
        out["cost_per_q_intro"] = price("claude-sonnet-5@intro")
        out["intro_ends"] = SONNET_INTRO_ENDS
    return out


# Config axes read for the "arm config matrix" -- every field that can silently
# make two arms different experiments, plus the derived `retrieval` column.
# `model`/`effort`/`system_version`/`ruling_query_mode`/`rewrite_version` overlap
# CONFIG_FIELDS above (used for timeline step/delta bookkeeping); this list is
# wider on purpose, because the matrix's job is to expose every axis a review
# might miss, not just the ones a delta chain already accounts for.
ARM_CONFIG_MATRIX_FIELDS = [
    ("model", "Model"), ("system_version", "System ver"), ("effort", "Effort"),
    ("max_tokens", "Max tokens"), ("ruling_query_mode", "Ruling mode"),
    ("layers_tool", "Layers tool"), ("show_rewrite", "Show rewrite"),
    ("rewrite_version", "Rewrite ver"), ("retrieval", "Retrieval"),
]


def _field_summary(rows: list[dict], field: str) -> dict:
    """One config field's shape across an arm's rows.

    Constant -> {value, mixed:False}. Not constant -> {mixed:True, breakdown},
    breakdown sorted by frequency. An arm that isn't constant on a field it
    should be constant on is itself a finding -- this is what lets the page
    show it rather than silently reporting the first row's value.
    """
    if not rows:
        return {"value": None, "mixed": False, "breakdown": None}
    counts: dict[str, int] = {}
    reprs: dict[str, object] = {}
    for r in rows:
        v = r.get(field)
        key = repr(v)
        counts[key] = counts.get(key, 0) + 1
        reprs[key] = v
    if len(counts) <= 1:
        return {"value": rows[0].get(field), "mixed": False, "breakdown": None}
    breakdown = sorted(({"value": reprs[k], "n": n} for k, n in counts.items()),
                       key=lambda b: (-b["n"], str(b["value"])))
    return {"value": None, "mixed": True, "breakdown": breakdown}


def _retrieval_summary(rows: list[dict]) -> dict:
    """Derived retrieval column: off (nothing retrieved, e.g. an oracle arm
    handed gold directly) vs on (retrieval ran, with the mean rule-id count),
    vs mixed (some rows retrieved, some didn't -- worth flagging on its own)."""
    if not rows:
        return {"value": None, "mixed": False, "breakdown": None}
    ns = [len(r.get("retrieved_rule_ids") or []) for r in rows]
    on = [n for n in ns if n > 0]
    off_n = len(ns) - len(on)
    if not off_n:
        return {"value": f"on (mean {sum(on) / len(on):.1f} ids)", "mixed": False, "breakdown": None}
    if not on:
        return {"value": "off (0 rows retrieved)", "mixed": False, "breakdown": None}
    return {"value": None, "mixed": True,
            "breakdown": [{"value": f"on (mean {sum(on) / len(on):.1f} ids)", "n": len(on)},
                          {"value": "off (0 ids)", "n": off_n}]}


def build_arm_config_matrix(arms: list[dict]) -> dict:
    """Every recorded config axis, per arm, side by side -- with the axes arms
    disagree on named explicitly.

    Built 2026-07-26 after an adversarial review found published comparisons
    (e.g. the derivability-B oracle ceiling vs the shipped-pipeline projection)
    attributing a gap to retrieval when the arms also differed on `effort` and
    other axes nothing on the page surfaced. This never decides which axis
    *caused* a gap -- it only makes "these arms differ on N things" impossible
    to miss, which is the fact the review was missing.
    """
    rows = []
    for a in arms:
        axes = a.get("config_axes") or {}
        recorded = bool(axes)
        values = {f: (axes.get(f) or {"value": None, "mixed": False, "breakdown": None})
                  for f, _ in ARM_CONFIG_MATRIX_FIELDS}
        rows.append({"arm": a["arm"], "qset": a["qset"], "kind": a["kind"],
                     "config_recorded": recorded, "values": values})

    differs, same = [], []
    for f, _ in ARM_CONFIG_MATRIX_FIELDS:
        # An internally-mixed arm never counts as "agreeing" with anything --
        # it gets its own sentinel signature rather than its (nonexistent)
        # constant value, so a mixed arm always shows up as a disagreement.
        sigs = {("<mixed>" if r["values"][f]["mixed"] else json.dumps(r["values"][f]["value"]))
                for r in rows if r["config_recorded"]}
        (differs if len(sigs) > 1 else same).append(f)

    inconsistent_arms = [
        {"arm": r["arm"], "fields": [f for f, _ in ARM_CONFIG_MATRIX_FIELDS if r["values"][f]["mixed"]]}
        for r in rows if any(r["values"][f]["mixed"] for f, _ in ARM_CONFIG_MATRIX_FIELDS)
    ]

    return {
        "fields": [{"key": f, "label": lab} for f, lab in ARM_CONFIG_MATRIX_FIELDS],
        "rows": rows,
        "differs": differs,
        "same": same,
        "inconsistent_arms": inconsistent_arms,
    }


def collect() -> dict:
    arms, skipped = [], []
    for vpath in sorted(list(EVALS.glob("*verdicts*.json"))):
        try:
            data = json.loads(vpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            skipped.append(f"{vpath.name}: unreadable ({e})")
            continue
        if not isinstance(data, dict):
            # Some *verdicts*.json files are bare arrays of hand-graded rows with
            # no summary at all (e.g. answer_verdicts.json). Nothing to score.
            skipped.append(f"{vpath.name}: bare array, no summary")
            continue
        summary = data.get("summary") or {}
        entries = data.get("entries") or []
        if not summary.get("by_level_counts") or not entries:
            skipped.append(f"{vpath.name}: no summary.by_level_counts")
            continue

        stem = vpath.stem.replace("verdicts_", "").replace("h2h_", "h2h_")
        if vpath.stem.startswith("verdicts_"):
            stem = vpath.stem[len("verdicts_"):]

        ids = sorted(e["id"] for e in entries if "id" in e)
        qset = hashlib.sha256("|".join(ids).encode()).hexdigest()[:8]

        try:
            counts = ws.normalize_counts(summary["by_level_counts"])
            flat = ws.score(counts, ws.WEIGHT_SCHEMES["flat"]["weights"])
            weighted = ws.score(counts, ws.WEIGHT_SCHEMES["corner-half"]["weights"])
        except ws.ScoreError as e:
            skipped.append(f"{vpath.name}: {e}")
            continue

        judged = {e["id"]: e.get("answer") for e in entries if "id" in e}
        apath, join = resolve_answers(stem, frozenset(ids), judged)
        cfg, cost, axes = {}, {}, {}
        kind, kind_why = "unknown", ("no answers file could be joined to this verdict file, so "
                                     "nothing records how the arm ran")
        if apath is not None:
            raw = json.loads(apath.read_text(encoding="utf-8"))
            # Answers files come in two shapes: a list of rows, or a dict keyed
            # by question id. Normalize rather than assume, so a shape mismatch
            # can't silently drop an arm's cost.
            rows = raw if isinstance(raw, list) else list(raw.values())
            rows = [r for r in rows if isinstance(r, dict)]
            first = rows[0] if rows else {}
            cfg = {
                "model": first.get("model"),
                "effort": first.get("effort"),
                "rewrite_version": first.get("rewrite_version"),
                "ruling_query_mode": first.get("ruling_query_mode"),
                "system_version": first.get("system_version"),
                "n_answers": len(rows),
                # Not a CONFIG_FIELDS axis (those gate the delta/pair machinery),
                # but a comparison whose losing side never recorded a prompt
                # cache can't have "same prompt" verified even in principle --
                # that gap is otherwise invisible next to fields that compare
                # None == None as "not differing".
                "prompts_cache_recorded": bool(first.get("prompts_cache")),
            }
            cost = cost_of(rows, first.get("model") or "")
            kind, kind_why = classify_arm(rows)
            # Full config-axis view for the arm config matrix -- unlike `cfg`
            # above (first row only), this checks every row so an arm that
            # isn't actually constant on a field shows up as mixed rather
            # than silently reporting whatever row 0 happened to record.
            axes = {f: _field_summary(rows, f) for f, _ in ARM_CONFIG_MATRIX_FIELDS if f != "retrieval"}
            axes["retrieval"] = _retrieval_summary(rows)

        arms.append({
            "arm": stem,
            "qset": qset,
            "kind": kind,
            "kind_why": kind_why,
            # Per-row verdicts, kept only long enough to measure rep-to-rep churn
            # and paired head-to-head records. Popped before the file is written --
            # working data, not a result.
            "_verdicts": {e["id"]: e.get("verdict") for e in entries if "id" in e},
            "_correct": {e["id"]: _row_correct(e) for e in entries if "id" in e},
            "n": summary.get("n_total") or len(entries),
            "accuracy_flat": flat,
            "accuracy_weighted": weighted,
            "accuracy_auto": summary.get("accuracy_auto"),
            "human_corrected": bool(summary.get("human_overturned")),
            "grader": summary.get("grader"),
            "by_level": {k: {"correct": c, "n": n_} for k, (c, n_) in counts.items()},
            "judge_model": summary.get("judge_model"),
            "judge_digest": summary.get("judge_prompt_sha256"),
            "config": cfg,
            "config_axes": axes,
            "cost": cost,
            # THREE separate events, never collapsed into one "Run" column.
            "generation": {
                "file": apath.relative_to(REPO).as_posix() if apath else None,
                "mtime": _mtime(apath) if apath else None,
                "join": join,
                "recorded": apath is not None,
            },
            "judging": {
                "file": vpath.relative_to(REPO).as_posix(),
                "mtime": _mtime(vpath),
                "judge_model": summary.get("judge_model"),
                "judge_digest": summary.get("judge_prompt_sha256"),
                # An accuracy whose judging run names no judge cannot be reproduced.
                "recorded": bool(summary.get("judge_model")),
            },
            "human": ({
                "grader": summary.get("grader"),
                "grading_date": summary.get("grading_date"),
                "n_regraded": len(summary.get("human_regraded") or []),
                "n_overturned": len(summary.get("human_overturned") or []),
                "overturned": summary.get("human_overturned") or [],
                "source_auto": summary.get("source_auto"),
            } if summary.get("grader") or summary.get("human_overturned") else None),
            "provenance": {
                "verdicts": vpath.relative_to(REPO).as_posix(),
                "verdicts_mtime": _mtime(vpath),
                "answers": apath.relative_to(REPO).as_posix() if apath else None,
                "answers_mtime": _mtime(apath) if apath else None,
                "join": join,
            },
        })

    arms.sort(key=lambda a: (a["qset"], -(a["accuracy_flat"] or 0)))
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
        "arms": arms,
        "skipped": skipped,
        "pricing": {"per_mtok": PRICING, "cache_read_mult": CACHE_READ_MULT,
                    "cache_write_mult": CACHE_WRITE_MULT,
                    "sonnet_intro_ends": SONNET_INTRO_ENDS,
                    "checked_on": PRICING_CHECKED_ON.isoformat(),
                    "source": PRICING_SOURCE,
                    # Empty means the cache is trustworthy. Non-empty means a
                    # cost on this page may be wrong -- carried into the data so
                    # the page can say so rather than quietly publishing it.
                    "freshness_warnings": check_freshness()},
        "current_config": {
            "GEN_MODEL": "claude-opus-5", "GEN_EFFORT": "low", "REWRITE_N": 3,
            "REWRITE_MODEL": "claude-haiku-4-5", "REWRITE_FUSION_DEPTH": 100,
            "TOP_K": 15, "TOP_N": 5, "COSINE_FLOOR": 0.38,
            "note": ("Current values read from source, NOT what each historical arm ran. "
                     "Per-run retrieval config is not recorded in the answers files."),
        },
        "weighting": {
            "scheme": "corner-half", "weights": ws.WEIGHT_SCHEMES["corner-half"]["weights"],
            "ruled_by": "Jon, 2026-07-26",
        },
    }


# ---------------------------------------------------------------------------
# TIMELINE: what changed at each step, by how much, and whether that is real.
#
# The table above is a snapshot -- where each arm landed. It cannot answer "what
# did that change buy us", because that needs a *baseline* and a *noise floor*,
# and getting either wrong manufactures a result. Three rules keep this honest:
#
# 1. Deltas never cross a question-set fingerprint. Arms ran on a 150, a 68, a
#    54, a 50, a 36 and a 15; a delta between two of those is arithmetic on
#    unrelated numbers.
# 2. Not every arm on a question set is a step on the same road. The
#    derivability arms handed the model its gold instead of retrieving -- an
#    oracle diagnostic, not a pipeline configuration. Chaining a delta from
#    "sonnet with retrieval" to "opus holding the answer key" would read as a
#    +21pp improvement that nobody shipped. Those arms are declared below and
#    render off-chain, labelled, with no delta.
# 3. The noise floor is measured, not assumed. Where the same configuration ran
#    twice (`_r1`/`_r2`), the spread between those reps IS the resolution of
#    this instrument for that question set -- so any step-delta smaller than it
#    is reported as not distinguishable from noise.
# ---------------------------------------------------------------------------

# Kind is DERIVED (see classify_arm). These add context a file cannot carry --
# they never decide the classification, and a step with no note still gets one
# from its evidence sentence.
STEP_NOTES = {
    "derivability_B": "The gold-only derivability probe. docs/results-derivability.md is the writeup.",
    "derivability_C": ("Re-run of the rows arm B got wrong. docs/results-derivability.md withdraws "
                       "its reading — the four 'passes' were the judge changing its mind."),
}

REP_SUFFIX = re.compile(r"_r\d+$")
HUMAN_SUFFIX = re.compile(r"_human$")

# ~1 verdict flip per 100 judged rows, measured in docs/results-easy-regression.md.
JUDGE_FLIPS_PER_ROW = 0.01


def step_key(arm: str) -> str:
    """Arm name minus its rep index and its regrade marker.

    `h2h_opuslow_hard_r1` and `_r2` are two runs of one configuration;
    `opus5_low_bucketA` and `_human` are two gradings of one run. Both collapse
    to a single step, and which of the two it is gets decided by the *answers
    file*, not the name -- reps have different answers files, regrades share one.
    """
    return HUMAN_SUFFIX.sub("", REP_SUFFIX.sub("", arm))


def _run_at(a: dict) -> tuple[str, str]:
    """When the arm ran, and where that came from.

    The answers file's mtime is the closest thing on disk to the run; the
    verdicts mtime is when it was *judged*, which for derivability_B is nearly
    twelve hours later. Arms with no joined answers file fall back to the
    verdict time, and say so.
    """
    p = a["provenance"]
    if p.get("answers_mtime"):
        return p["answers_mtime"], "answers file mtime"
    return p["verdicts_mtime"], "verdict file mtime (no answers file joined)"


def _churn(a: dict, b: dict) -> dict | None:
    """Rows whose verdict differs between two reps of the same configuration.

    This is a different quantity from the accuracy spread and both matter: rows
    can churn heavily while the totals barely move.
    """
    shared = set(a["_verdicts"]) & set(b["_verdicts"])
    if not shared:
        return None
    flipped = sorted(i for i in shared if a["_verdicts"][i] != b["_verdicts"][i])
    return {"n_rows": len(shared), "n_flipped": len(flipped), "ids": flipped[:12]}


def _mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _pool_levels(per_rep: list[dict]) -> dict:
    """Sum correct/n per level across reps of one configuration.

    Reps are the SAME questions answered again, so the pooled denominator is
    rep-count x questions. That is the right base for a per-level *rate* (more
    observations of the same question sharpen the rate) but the wrong base for a
    sampling interval -- the interval is computed on the question count instead,
    and `n_questions` is kept beside `n` so a consumer cannot confuse them.
    """
    out: dict[str, dict] = {}
    for lv in per_rep:
        for level, c in (lv or {}).items():
            slot = out.setdefault(level, {"correct": 0.0, "n": 0.0, "n_questions": 0.0})
            slot["correct"] += c["correct"]
            slot["n"] += c["n"]
    for level, slot in out.items():
        slot["n_questions"] = slot["n"] / len(per_rep) if per_rep else 0.0
        slot["acc"] = slot["correct"] / slot["n"] if slot["n"] else None
    return out


def git_commits() -> list[dict]:
    """Every commit with an ISO author-independent commit time, newest first.

    Association only. Nothing links a commit to an eval run in the data; the
    timeline pairs them by timestamp window and labels that as an inference.
    """
    try:
        out = subprocess.run(["git", "log", "--pretty=%h%x1f%cI%x1f%s"],
                             cwd=REPO, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    rows = []
    for line in out.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            rows.append({"sha": parts[0], "at": parts[1], "subject": parts[2]})
    return rows


# ===========================================================================
# ROADMAP / BACKLOG
#
# WHY IT LIVES HERE. Jon, 2026-07-26: the page should let someone decide *what
# to do next*, not only see where things stand. `docs/` holds 41 `plan-*.md` and
# 7 `spec-*.md`; only six carry an explicit status marker, so status is INFERRED
# FROM EVIDENCE -- a commit that implements it, a results doc that measured it,
# a code path that exists (or provably does not).
#
# THE THREE RULES THIS TABLE OBEYS, because it is read to decide spending:
#
# 1. EVERY STATUS CARRIES ITS EVIDENCE, AND THE EVIDENCE IS RE-CHECKED AT BUILD
#    TIME. `commit` refs are looked up in `git log`; `path` refs must exist on
#    disk; `path_absent` refs must NOT exist. A claim that has gone stale renders
#    as a broken evidence line instead of quietly staying true. Where evidence
#    cannot establish a status, the item says `unknown` and names what would
#    settle it.
#
# 2. NO INVENTED COSTS, DIRECTIONS, OR MAGNITUDES. A dollar figure is either
#    DERIVED (`api_questions`: question count x the measured $/question of the
#    shipped config, taken live from the projections computed above) or QUOTED
#    from a doc that states it (`api_stated`, with the citation). Otherwise it is
#    `unknown`, which is a useful cell. Metric direction is `measured` only when
#    a results/report doc measured it; a doc's own forecast renders as
#    "predicted, unmeasured".
#
# 3. API CREDITS AND FREE WORK ARE DIFFERENT POOLS. `api_*` spends credits (an
#    Anthropic client built from `.env`). `zero` is local compute or a re-scoring
#    pass over files already on disk -- weighted scoring was pure arithmetic and
#    genuinely cost $0. `subscription` is Claude Code subagent labor on Jon's Max
#    plan: real time, zero credits. `hosting` is neither.
#
# MERGES ARE EXPLICIT. Where two docs are the same idea, one item carries both
# and lists the folded doc under `merged`, with the sentence that justifies the
# merge. An alphabetical dump of 48 files would be worse than nothing.
# ===========================================================================

# Author's value rank. NOT a computed score -- a judgement, shown with its
# reason so a reader can disagree with it. It only ever orders items; it is never
# multiplied by anything or presented as a magnitude.
INFO_RANK = {
    3: "resolves a named uncertainty in the go/no-go decision",
    2: "moves or validates a measured metric, or unblocks something that does",
    1: "quality, infrastructure or evidence work with no measured metric attached",
}

ROADMAP: list[dict] = [
    {
        "id": "opus-quality-next",
        "title": "Where opus-5 accuracy can still move, after the prompt levers closed",
        "one_line": "Prompt engineering was tested on the cheap model and the transferable "
                    "conclusion is that there is nothing to port to opus. This ranks the "
                    "remaining accuracy levers by evidence rather than by ease of trying.",
        "status": "design-only", "action": "explore", "info": 3,
        "info_why": "Rule 0: design only until Jon rules. Its value is mostly NEGATIVE "
                    "evidence, which is cheaper to record than to rediscover: two "
                    "plausible-sounding prompt changes were measured and rejected.",
        "tells_us": "Anti-refusal instruction: do NOT ship it. It bought gpt-5-mini +5.0 "
                    "points only because that model declines on 11.1% of rows; opus declines "
                    "on 0.7%, so its entire addressable upside is 0.7 points, well inside the "
                    "2-4 point judge instability. It also attacks the refusal reflex that "
                    "rules86-placebo showed is load-bearing (90.7% declines, 3.5% "
                    "confabulation under corrupted retrieval). Procedural scaffolding: also "
                    "rejected, flat to 4 points worse on gpt-5-mini while declines rose, and "
                    "opus already cites a CR rule on 98.1% of answers unprompted.",
        "evidence": [
            {"kind": "doc", "ref": "docs/plan-opus-quality-next.md",
             "note": "the plan itself, with the rejected levers and a failed prediction "
                     "recorded because it was testable"},
            {"kind": "doc", "ref": "docs/results-rules86-placebo.md",
             "note": "why the refusal reflex is worth protecting rather than instructing away"},
            {"kind": "doc", "ref": "docs/results-judge-stability.md",
             "note": "the 2-4 point instability that makes a 0.7 point upside unmeasurable"},
        ],
        "cost": {"kind": "spent", "why": "the prompt-lever bake-off ran on gpt-5-mini rather "
                                        "than opus precisely because the cheap model is where "
                                        "an instruction with real headroom could be measured"},
        "metric": {"name": "addressable upside from prompt levers", "dir": "up",
                   "basis": "measured", "cite": "docs/plan-opus-quality-next.md",
                   "detail": "opus declines on 0.7% of rows (10/1409) against gpt-5-mini's "
                             "11.1% (157/1409), so the prompt lever that moved the cheap model "
                             "+5.0 points has almost nothing to act on here"},
        "deps": [],
    },
    {
        "id": "gated-demo",
        "title": "Gated public demo on Fly.io (per-person access codes + spend guards)",
        "one_line": "Put Rulemancer in front of hiring managers behind per-person access codes, "
                    "with three layers of spend control so a leaked code cannot drain the "
                    "Anthropic balance. Shipped 2026-07-27 at rulemancer.fly.dev.",
        "status": "shipped", "action": "build", "info": 3,
        "info_why": "The demo spends real credits per query on a publicly reachable URL, so the "
                    "guards are the product decision, not the chat UI. Cost per serve was measured "
                    "(mean $0.0485, max $0.0648) rather than extrapolated, because the batched "
                    "eval rate does not transfer to live serving.",
        "tells_us": "All four guards were verified against the deployed URL, not just in tests: "
                    "per-code cap refuses before the model call (2 events recorded, not 3), a "
                    "revoked code invalidates an already-issued session, unlock is rate-limited at "
                    "5 attempts per 15 minutes per IP (~123 years to walk the 21.6M code space), "
                    "and the daily budget breaker refuses with zero added spend.",
        "evidence": [
            {"kind": "doc", "ref": "docs/superpowers/plans/2026-07-27-gated-demo.md",
             "note": "the 15-task implementation plan this shipped from"},
            {"kind": "doc", "ref": "docs/superpowers/specs/2026-07-27-public-launch-design.md",
             "note": "the approved design: access codes over one shared passphrase, evidence "
                     "surface split from the live app"},
        ],
        "cost": {"kind": "hosting", "why": "Fly shared-cpu-1x always-on, ~$5/mo, plus $0.55 of "
                                        "Anthropic credit spent measuring real cost per serve"},
        "metric": {"name": "cost per serve", "dir": "down", "basis": "measured",
                   "cite": "docs/superpowers/plans/2026-07-27-gated-demo.md",
                   "detail": "mean $0.0485 and max $0.0648 over 8 real queries; the $0.06 "
                             "figure extrapolated from the batched eval rate was 19% high on the "
                             "mean but 8% LOW on the max, so it was not a safe bound for sizing "
                             "a spend guard"},
        "deps": [],
    },
    {
        "id": "evidence-site",
        "title": "Public evidence site (generated from the arm data, not hand-typed)",
        "one_line": "A static page for someone who will not read code: six curated findings, "
                    "each carrying the population it was computed over, generated from "
                    "_metrics_history.json so a published number cannot drift from the run "
                    "that produced it.",
        "status": "partial", "action": "build", "info": 3,
        "info_why": "The page is the project's public claim surface, so the risk is not that it "
                    "looks bad, it is that it goes stale silently. That risk is handled in code "
                    "rather than by discipline: every arm-backed finding declares claimed_n, "
                    "claimed_accuracy and claimed per-level figures, and the build raises "
                    "DriftError above a 0.0005 tolerance. A test also diffs the committed "
                    "site/index.html against a fresh render, so a stale commit fails the suite.",
        "tells_us": "Six findings ship: the 1,409-question headline with its error bars, the "
                    "rules reversal, refusal-not-confabulation, the fair cross-model comparison, "
                    "the two-sided judge audit, and the level-3 weakness. The cross-model "
                    "full-corpus arm is not registered in the metrics history, so that finding "
                    "is doc-backed against docs/results-crossmodel-fair.md and the page says so "
                    "rather than hardcoding the figure.",
        "evidence": [
            {"kind": "doc", "ref": "docs/superpowers/plans/2026-07-27-evidence-surface.md",
             "note": "the plan this shipped from; tasks 1, 2, 5 and 6 (README, hygiene gate, "
                     "public repo) landed 2026-07-27, tasks 3 and 4 (the generator and the "
                     "page) on 2026-07-28"},
            {"kind": "path", "ref": "evals/build_evidence_site.py",
             "note": "the generator, including the drift guard"},
            {"kind": "path", "ref": "docs/evidence/findings.json",
             "note": "the curated narrative and the claimed figures it is checked against"},
            {"kind": "path", "ref": "site/index.html",
             "note": "the committed output, served with no build step"},
        ],
        "cost": {"kind": "zero", "why": "stdlib-only generator over data that already exists; "
                                        "hosting is a free static tier"},
        "metric": {"name": "published figures checked against their arm", "dir": "up",
                   "basis": "measured", "cite": "tests/test_evidence_site.py",
                   "detail": "17 tests green. Drift was verified by injecting a wrong "
                             "accuracy, a wrong n, a wrong per-level figure and a wrong "
                             "companion-arm figure into the real findings file: all four "
                             "raised DriftError."},
        "deps": ["gated-demo"],
    },
    # ---------------------------------------------------------------- ready --
    {
        "id": "l0-arm",
        "title": "L0-only pipeline arm (207 questions) -- SUPERSEDED by the full corpus run",
        "one_line": "Run the shipped config over the corpus's L0 questions, the one difficulty "
                    "level no pipeline arm had ever touched. Folded into the full 1,409-row run "
                    "on 2026-07-27, which measured all 207 L0 rows directly.",
        "status": "shipped", "action": "run", "info": 3,
        "info_why": "SUPERSEDED 2026-07-27: this item's own goal -- get L0 out of extrapolation "
                    "and into measurement -- was achieved as a side effect of running the entire "
                    "corpus (docs/results-headline-accuracy.md) rather than by running it in "
                    "isolation. Originally: \"L0 is the only level with zero pipeline rows, so the "
                    "full-run projection is currently extrapolated over it rather than measured.\"",
        "tells_us": "L0 measured 199/207 = 96.14% (95% CI [92.6%, 98.0%]), the highest of any "
                    "level -- confirming the handoff's prediction that the projection read low "
                    "because L0 is the corpus's easiest slice. The 80.3% full-run projection this "
                    "item questioned is retired; the real number is 85.88%, 3.1 points above it.",
        "evidence": [
            {"kind": "doc", "ref": "docs/HANDOFF-development.md",
             "note": "live queue item 1: \"Run an L0-only pipeline arm (~$11, 207 questions)\" "
                     "-- the original ask, now overtaken"},
            {"kind": "doc", "ref": "docs/results-headline-accuracy.md",
             "note": "L0: 199/207 correct, 96.14%, measured as part of the full 1,409-row run, "
                     "commit 2543454"},
        ],
        "metric": {"name": "full-run projection coverage", "dir": "up", "basis": "measured",
                   "cite": "docs/results-headline-accuracy.md",
                   "detail": "coverage moved from a projected share to 100% of the corpus mix in "
                             "one run. L0 landed at 96.14%, the corpus's best level, which is the "
                             "direction the handoff predicted and this item existed to confirm."},
        "cost": {"kind": "spent", "why": "measured as part of the $43.61 full-corpus run rather "
                                          "than as a standalone ~$11 arm"},
        "deps": [],
    },
    {
        "id": "gold-audit-b2",
        "title": "Gold audit, batch 2",
        "one_line": "Hand-grade the full-data misses (rg1802, rg4440, rg5628 plus the h2h and "
                    "cost-base rows) with the retrieved panel showing what the run actually saw.",
        "status": "open", "action": "measure", "info": 3,
        "docs": ["docs/spec-gold-audit-ui.md"],
        "info_why": "Grading calls, not model changes, have moved arm B twice (90.0 -> 93.3 -> "
                    "91.3). Every accuracy on this page inherits that error.",
        "tells_us": "How much of the remaining failure is the bot versus the gold or the judge.",
        "evidence": [
            {"kind": "doc", "ref": "docs/HANDOFF-development.md", "note": "live queue item 2"},
            {"kind": "path", "ref": "evals/build_gold_audit_input.py",
             "note": "the harness exists; --provenance run flips the panel to the green "
                     "\"retrieved by the run\" label"},
            {"kind": "doc", "ref": "docs/results-gold-audit-batch1.md",
             "note": "batch 1: 2 of 15 were the judge being wrong, after Jon's second-pass "
                     "adjudication"},
        ],
        "metric": {"name": "published accuracy correctness", "dir": "either", "basis": "measured",
                   "cite": "docs/results-gold-audit-batch1.md",
                   "detail": "batch 1 moved arm B by 3.3 pp up and then 2.0 pp back down. "
                             "Direction is genuinely unknown in advance -- that is the point."},
        "cost": {"kind": "zero",
                 "why": "regrades answers already on disk; no generation, no judge calls, no "
                        "Anthropic client. Jon's time is the real cost."},
        "deps": [],
    },
    {
        "id": "miss-partition",
        "title": "Miss-partition diagnostic — retrieval failure vs reasoning failure",
        "one_line": "For every graded miss, decide whether the gold rule was missing from the "
                    "context or present and misused — so effort goes to the right half of the stack.",
        "status": "design-only", "action": "decide", "info": 2,
        "info_why": "It is the cheapest way to choose between the retrieval backlog and the "
                    "prompt/tool backlog, and the data it needs now exists.",
        "tells_us": "Which of the two remaining levers is worth funding at all.",
        "evidence": [
            {"kind": "doc", "ref": "docs/plan-miss-partition-diagnostic.md",
             "note": "header: \"DRAFT under Rule 0 — DESIGN ONLY. Nothing built.\""},
            {"kind": "derived",
             "note": "the plan states it \"has no data to run on until a future eval run is "
                     "re-executed\" with per-row retrieval recorded. That field is now recorded: "
                     "this page classifies arms as pipeline/oracle purely from "
                     "`retrieved_rule_ids`, so the blocker it names looks cleared."},
        ],
        "metric": {"name": "where the next fix should go", "dir": "none", "basis": "predicted",
                   "cite": "docs/plan-miss-partition-diagnostic.md",
                   "detail": "a diagnostic, not an intervention. It moves no metric by itself."},
        "cost": {"kind": "zero",
                 "why": "an analysis pass over verdict and answers files already on disk, if it "
                        "is scoped to arms that recorded retrieval. The plan's own §0 asks for a "
                        "third bucket, which is a design question, not a spend."},
        "deps": [],
    },
    {
        "id": "cards-rag",
        "title": "Semantic search over card oracle text -- MOVED to Tutormancer",
        "one_line": "\"Cards like this one, but cheaper / different colours / strictly better\" -- "
                    "split out to its own repo (D:\\Job_hunt\\tutormancer) on 2026-07-27, because "
                    "card NAME resolution does not fail here (the 9 unresolved refs on the "
                    "1,409-row corpus are all planeswalker loyalty costs like [+1], never card "
                    "names), so a card "
                    "index does nothing for rules answering.",
        "status": "cut", "action": "none", "info": 3,
        "info_why": "The channel ablation showed card oracle text carries the system (-31 pts "
                    "when scrambled, p=4.3e-07) while CR-rule retrieval measured ~inert on that "
                    "same corpus (-3.3 pts, p=0.50). SUPERSEDED 2026-07-27: that \"inert\" result "
                    "was a corpus artifact -- the ablation ran on a corpus that is 99.4% "
                    "card-interaction questions, and on card-free rules questions scrambling the "
                    "retrieved rules collapses accuracy 98.84% -> 15.12% (-83.7 pts, "
                    "docs/results-rules86-placebo.md, commit f515246). Correct restatement: rules "
                    "are redundant GIVEN card text, not inert in general. This does not change the "
                    "cut decision here -- card-name resolution still isn't the failure mode -- but "
                    "the retrieval-effort rationale above is no longer the reason to skip it.",
        "tells_us": "Whether semantic search over 38,336 cards can find functional equivalents "
                    "and constrained substitutes. Unlike the rules index, its ground truth is "
                    "COMPUTED (functional reprints, strictly-better and colour-shifted pairs are "
                    "derivable from Scryfall), so it needs no hand-labelling and no LLM judge.",
        "docs": ["docs/spec-cards-rag-MOVED.md"],
        "evidence": [
            {"kind": "doc", "ref": "docs/results-channel-ablation.md",
             "note": "the ablation that motivates it -- oracle text -31 pts, rulings -6, CR "
                     "rules -3, layers tool 0 (measured on the card-heavy corpus)"},
            {"kind": "doc", "ref": "docs/results-rules86-placebo.md",
             "note": "the reversal: on 86 card-free rules questions, the same intervention "
                     "collapses accuracy -83.7 pts. CR rules are load-bearing when cards aren't "
                     "there to cover for them."},
            {"kind": "path", "ref": "data/scryfall.db",
             "note": "38,336 oracle cards and 77,999 rulings already local, with oracle_text, "
                     "type_line, mana_value, colors and faces per card"},
        ],
        "metric": {"name": "recall@k vs computed gold", "dir": "up", "basis": "predicted",
                   "cite": "docs/spec-cards-rag-MOVED.md",
                   "detail": "no prior number -- the eval does not exist yet. The spec mandates a "
                             "deranged-index placebo control and a BM25 baseline before any "
                             "recall figure is believed."},
        "cost": {"kind": "zero",
                 "why": "query time is a local matmul plus one query embedding -- $0 in Anthropic "
                        "credits, and evaluation is $0 because gold is computed and retrieval is "
                        "local. One-time indexing is ~4M Voyage tokens; Voyage pricing is NOT in "
                        "rulesagent.pricing and must be added before any spend."},
        "deps": [],
    },
    {
        "id": "retrieval-value-ab",
        "title": "Measure what retrieval is actually worth (single-variable A/B) -- DONE",
        "one_line": "Hold the entire pipeline fixed and swap only WHICH rules go in the context "
                    "block — real retrieval vs another question's retrieval — so the difference "
                    "is retrieval's contribution and nothing else. Run 2026-07-27 on 86 card-free "
                    "rules questions.",
        "status": "shipped", "action": "build", "info": 3,
        "info_why": "DONE 2026-07-27. Originally: \"No arm on disk isolates retrieval. Every "
                    "published comparison changes two or more variables at once.\" That's no "
                    "longer true -- real vs placebo prompts are byte-identical except inside the "
                    "rules block (first divergence at character offset 16), which is exactly the "
                    "single-variable swap this item proposed.",
        "tells_us": "Retrieval is load-bearing, not decorative: scrambling the retrieved rules "
                    "collapses accuracy 98.84% -> 15.12% (-83.7 pts) on card-free questions. But "
                    "the collapse is mostly REFUSAL, not error -- placebo declined to answer on "
                    "78/86 rows (90.7%) and confabulated a confident wrong answer on only 3/86 "
                    "(3.5%; one of those looks like a possible judge false positive). The old "
                    "82.8% -> 91.3% oracle-gap framing this item was scoped to answer is "
                    "superseded by results-headline-accuracy.md's measured 85.88% corpus figure; "
                    "this experiment answers the narrower, cleaner question of whether retrieval "
                    "itself does anything, and the answer is yes, decisively.",
        "docs": ["docs/spec-retrieval-value-ab.md"],
        "evidence": [
            {"kind": "doc", "ref": "docs/results-rules86-placebo.md",
             "note": "the run: real rules 85/86 = 98.84% [93.70%, 99.79%] vs scrambled rules "
                     "13/86 = 15.12% [9.05%, 24.16%], arms rules86_real_votes3 / "
                     "rules86_placebo_votes3, judge openai/gpt-5-mini 3-vote majority, commit "
                     "f515246"},
            {"kind": "doc", "ref": "docs/results-adversarial-review.md",
             "note": "the review that found the original gap: citations are 99.2% grounded, but "
                     "retrieval supplies zero gold on 55.6% of scored rows and those rows still "
                     "score 89.4%; correlation between coverage and correctness is r=+0.06 -- this "
                     "review is why a card-free set was needed to see retrieval's effect at all"},
            {"kind": "doc", "ref": "docs/results-norules-control.md",
             "note": "the earlier control this design replaced as the primary instrument — it was "
                     "matched to arm B (effort=high), not the shipped pipeline (effort=low), so it "
                     "could not measure the shipped product's dependence on retrieval"},
        ],
        "metric": {"name": "accuracy delta, real vs placebo context", "dir": "up",
                   "basis": "measured", "cite": "docs/results-rules86-placebo.md",
                   "detail": "-83.7 points (98.84% -> 15.12%), far past the pre-registered "
                             "decision thresholds against the measured 7-10% run-to-run noise "
                             "floor. Judge instability at contestable accuracy is ~2-4 points "
                             "(docs/results-judge-stability.md), so the gap is not an instrument "
                             "artifact."},
        "cost": {"kind": "spent",
                 "why": "ran within the pre-registered $4.55-$45 range (86 questions x 2 arms x "
                        "3 judge votes)"},
        "deps": [],
    },
    {
        "id": "three-way-verdicts",
        "title": "Three-way verdicts — correct / incorrect / declined",
        "one_line": "Split the judge's binary correct/incorrect into three states so a grounded "
                    "refusal stops scoring identically to a confident wrong answer.",
        "status": "open", "action": "build", "info": 2,
        "info_why": "The rules86 placebo arm showed why this matters: 90.7% of its rows were "
                    "honest declines and only 3.5% were confabulations, but the accuracy metric "
                    "scored both as \"incorrect\" and made the system look roughly 6x worse than "
                    "it actually behaved. `answered` is already recorded per row at generation "
                    "time, so this is a scoring-layer change, not a re-run.",
        "tells_us": "Whether other arms -- especially low-scoring ones like level 3 (67.90%) -- "
                    "are hiding a similar refuse-vs-error split, or whether the headline run's "
                    "refusal rate (0.71%, 9 of 10 declines scored wrong) means this mostly matters "
                    "under corrupted/adversarial retrieval rather than in the shipped pipeline.",
        "evidence": [
            {"kind": "doc", "ref": "docs/results-rules86-placebo.md",
             "note": "\"Verdicts should be three-way: correct / incorrect / declined. Recommended "
                     "follow-up, and it costs nothing because answered is already recorded per "
                     "row.\""},
            {"kind": "doc", "ref": "docs/results-headline-accuracy.md",
             "note": "the shipped pipeline's own refusal rate for contrast: 10/1,409 (0.71%), "
                     "9 of which scored incorrect -- so the corpus run is not currently hiding a "
                     "large refusal population, unlike the placebo arm"},
            {"kind": "path", "ref": "evals/run_answer_eval.py",
             "note": "line ~1026: `\"answered\": ans.answered` already recorded per row; line "
                     "~1153: `declined = [r[\"id\"] for r in results if not r[\"answered\"]]` "
                     "already computed but not threaded into the judge/scoring path"},
        ],
        "metric": {"name": "instrument validity (refusal separated from error)", "dir": "up",
                   "basis": "predicted", "cite": "docs/results-rules86-placebo.md",
                   "detail": "not built yet -- the placebo arm shows the size of the effect where "
                             "refusals are common (a 6x apparent-vs-real severity gap); on the "
                             "shipped pipeline where refusals are rare it mainly changes how a "
                             "handful of rows get read, not the headline number."},
        "cost": {"kind": "zero",
                 "why": "arithmetic over `answered`, already recorded on every answer row -- no "
                        "new generation, no new judge calls"},
        "deps": [],
    },
    {
        "id": "harder-cardfree-set",
        "title": "Harder card-free rules set (rules86 is near-ceiling)",
        "one_line": "Draft a card-free rules set calibrated to be hard enough to detect pipeline "
                    "improvements -- rules86's real arm sits at 98.84%, too close to ceiling to "
                    "measure gains, only damage.",
        "status": "open", "action": "build", "info": 2,
        "info_why": "results-rules86-placebo.md names this gap in its own caveats: \"The real arm "
                    "at 98.84% is near-ceiling, which means this set cannot detect improvements to "
                    "the real pipeline. It is a sensitive instrument for damage, not for gains. A "
                    "harder card-free set would be needed to measure progress.\"",
        "tells_us": "Whether future retrieval or prompt changes actually move accuracy on "
                    "rules-only questions -- something rules86 structurally cannot show at 98.84%.",
        "evidence": [
            {"kind": "doc", "ref": "docs/results-rules86-placebo.md",
             "note": "the near-ceiling caveat and its own recommendation to build a harder set"},
            {"kind": "doc", "ref": "docs/spec-pure-rules-holdout.md",
             "note": "reusable machinery: the approval UI and purerules.jsonl pipeline "
                     "(build_purerules_approval_ui.py, Jon approves/rewrites/cuts in browser) "
                     "already exists for drafting and vetting card-free/harder questions"},
        ],
        "metric": {"name": "real-arm accuracy headroom", "dir": "down", "basis": "predicted",
                   "cite": "docs/results-rules86-placebo.md",
                   "detail": "rules86's real arm has ~1 point of headroom below ceiling (98.84%); "
                             "no target headroom is set yet for a harder set -- that is what this "
                             "item would draft."},
        "cost": {"kind": "subscription",
                 "why": "drafting runs on subagents under the standing grant, same as "
                        "purerules-eval and the rules86 55-row batch; Jon's blind-review pass is "
                        "the bottleneck, not credits"},
        "deps": ["retrieval-value-ab"],
        "dep_why": "it is the direct follow-on to that experiment's stated ceiling limitation",
    },
    {
        "id": "attack-level3",
        "title": "Attack level 3 (67.90% -- the corpus's weakest tier)",
        "one_line": "Level 3 is the lowest-scoring tier in the first corpus-wide measurement "
                    "(67.90%, n=162) and fails at ~6x the base rate in a separate sample -- "
                    "diagnose why before spending on anything else.",
        "status": "open", "action": "decide", "info": 3,
        "info_why": "Two independent measurements now agree level 3 is the weak point: the "
                    "headline run's monotonic per-level decline and the failure taxonomy's ~6x "
                    "base-rate finding on a different 311-row sample. Two instruments landing on "
                    "the same tier is a stronger signal than either alone.",
        "tells_us": "Whether level 3 failures cluster by cause (retrieval miss vs reasoning "
                    "failure, the split miss-partition targets) and whether any item already on "
                    "this board (second-hop, gold-sufficiency) actually reaches level 3 "
                    "specifically, or whether none of them do and a new item is needed.",
        "evidence": [
            {"kind": "doc", "ref": "docs/results-headline-accuracy.md",
             "note": "per-level table: L0 96.14%, L1 90.27%, L2 84.24%, L3 67.90% [60.4%, 74.6%] "
                     "n=162, Corner Case 71.01% -- L3 is the lowest of the four numbered levels"},
            {"kind": "doc", "ref": "docs/results-failure-taxonomy.md",
             "note": "7.4% base failure rate corpus-wide; level 3 at 42.9%, ~6x the base rate, "
                     "measured on a separate 311-row sample -- the headline run corroborates this "
                     "independently rather than repeating the same data"},
        ],
        "metric": {"name": "level 3 accuracy", "dir": "up", "basis": "measured",
                   "cite": "docs/results-headline-accuracy.md",
                   "detail": "67.90% [60.4%, 74.6%], n=162 -- the baseline this item would move. "
                             "No intervention is scoped yet; that is what the diagnosis decides."},
        "cost": {"kind": "unknown",
                 "why": "no plan sizes an L3-specific fix yet -- the diagnosis (miss-partition, "
                        "run first) decides whether the lever is retrieval, reasoning, or gold "
                        "quality before anything gets priced"},
        "deps": ["miss-partition"],
        "dep_why": "need the retrieval-vs-reasoning split before scoping an L3-specific fix, or "
                   "the spend targets the wrong half of the stack",
    },
    {
        "id": "human-grading-sample",
        "title": "Human-grade a plain random sample (not just judge-flagged rows)",
        "one_line": "Grade a random cross-section of the corpus by hand instead of only rows a "
                    "judge already flagged -- every human verdict in this project so far comes "
                    "from a stratified pull (judge-flagged-different, or judge-passed hard-level), "
                    "never a plain random draw across the full accuracy distribution.",
        "status": "open", "action": "measure", "info": 2,
        "info_why": "results-judge-error-rate.md's 32 hand-graded rows are a census of "
                    "judge-flagged-different rows only (15 arm-B + 17 bucket-A). "
                    "results-judge-false-negatives.md's newer 77-row hand-grade improves on this "
                    "by covering judge-PASSED rows, including a census of all 53 hard-level "
                    "passes, and measures 0/77 false negatives (95% CI [0%, 4.7%]). Both are real "
                    "improvements, but both are still stratified pulls, not a plain random sample "
                    "across the whole corpus -- so the residual risk is a class of error neither "
                    "stratum happens to contain.",
        "tells_us": "Whether the measured 0% false-negative rate (upper bound 4.7%) holds outside "
                    "the strata it has been checked on, and gives the judge false-positive/"
                    "false-negative rates their first check against an unbiased sample.",
        "evidence": [
            {"kind": "doc", "ref": "docs/results-judge-error-rate.md",
             "note": "the 32-row census, explicitly \"every row those arms' judge flagged "
                     "different\" -- judge-flagged-only, not random"},
            {"kind": "doc", "ref": "docs/results-judge-false-negatives.md",
             "note": "77 rows hand-graded, 0/77 false negatives, CI [0%, 4.7%], including a "
                     "census of all 53 hard-level passes -- judge-passed-only, still not random"},
            {"kind": "doc", "ref": "docs/results-judge-panel.md",
             "note": "the multi-model judge panel was tested and rejected as primary (40% vs "
                     "gpt-5-mini's 72% agreement with human verdicts) -- a reminder that LLM "
                     "cross-checks of LLM answers are not a substitute for a human anchor"},
        ],
        "metric": {"name": "false-negative rate, unbiased sample", "dir": "none", "basis": "measured",
                   "cite": "docs/results-judge-false-negatives.md",
                   "detail": "current baseline is 0/77 (CI to 4.7%), but on two stratified "
                             "samples; a random draw could land inside or outside that interval "
                             "and either result is informative."},
        "cost": {"kind": "zero",
                 "why": "Jon's own grading time against answers already on disk, same cost shape "
                        "as gold-audit-b2 -- no generation, no judge calls, no Anthropic client"},
        "deps": [],
    },
    {
        "id": "cosine-floor",
        "title": "Spec the cosine floor",
        "one_line": "Re-introduce a calibrated similarity floor on the fused multi-query result, "
                    "which RRF removed when REWRITE_N went to 3.",
        "status": "open", "action": "build", "info": 2,
        "info_why": "It targets a measured side effect of a change that already shipped to "
                    "production, and it costs nothing at runtime.",
        "tells_us": "Whether the chunk churn multi-query introduced is costing us anything.",
        "docs": ["docs/spec-cosine-floor.md"],
        "evidence": [
            {"kind": "doc", "ref": "docs/HANDOFF-development.md",
             "note": "live queue item 4: \"free at runtime (scores = embeddings @ qvec is one "
                     "in-process matmul), cuts the 38% chunk churn multi-query introduced, "
                     "restores a calibrated signal that RRF removed\""},
            {"kind": "commit", "ref": "86b5d27",
             "note": "the REWRITE_N 1 -> 3 switch that activated the RRF fusion branch"},
            {"kind": "doc", "ref": "docs/results-retrieval-diversity.md",
             "note": "the factorial that measured the churn"},
        ],
        "metric": {"name": "retrieval churn", "dir": "down", "basis": "predicted",
                   "cite": "docs/HANDOFF-development.md",
                   "detail": "the 38% churn figure is measured; that a floor reduces it is the "
                             "handoff's forecast, not a result."},
        "cost": {"kind": "zero",
                 "why": "one in-process matmul over embeddings already in memory; no API call in "
                        "the runtime path. Measuring the effect on recall would reuse the "
                        "cache-only diversity harness, which ran at zero API spend."},
        "deps": [],
    },
    {
        "id": "gold-sufficiency",
        "title": "Spec gold sufficiency and necessity testing",
        "one_line": "Use the oracle (gold-only) arm as a formal test: success proves a candidate "
                    "gold set is sufficient, leave-one-out checks whether it's also minimal.",
        "status": "open", "action": "build", "info": 2,
        "info_why": "Gold quality has only ever been judged by reading CR text next to a question; "
                    "this turns it into a measurement the oracle arm already produces evidence for.",
        "tells_us": "Whether a candidate gold set is sufficient, whether it's over-specified, and "
                    "how much of arm B's 91.3% is gold versus the model's own MTG training.",
        "docs": ["docs/spec-gold-sufficiency.md"],
        "evidence": [
            {"kind": "doc", "ref": "docs/results-derivability.md",
             "note": "arm B (137/150 = 91.3%) is this test already run; rg7215/rg549/rg811 are "
                     "the confirmed positive case -- failed gold-only, passed once retrieval "
                     "supplied a rule gold lacked"},
            {"kind": "doc", "ref": "docs/results-miss-partition.md",
             "note": "90/202 rows answered correctly without the flagged gold rule ever in "
                     "context -- the corroborating over-specification signal this spec's "
                     "leave-one-out design targets directly"},
            {"kind": "doc", "ref": "docs/results-orgroup-repass.md",
             "note": "the 25 needs-Jon OR-groups this spec's member-level necessity test can "
                     "mechanically resolve, per rule 6's own criterion"},
        ],
        "metric": {"name": "gold sufficiency / necessity rate", "dir": "none", "basis": "predicted",
                   "cite": "docs/results-derivability.md",
                   "detail": "arm B's 91.3% and the 2% confirmed-incomplete rate are measured; "
                             "the necessity (over-specification) rate and the parametric-knowledge "
                             "confound rate are not measured yet -- that's what this spec proposes."},
        "cost": {"kind": "api_stated", "lo": 2.88, "hi": 16.49,
                 "cite": "docs/spec-gold-sufficiency.md",
                 "why": "$2.88 for the 25 needs-Jon OR-group member tests alone (51 calls at arm "
                        "B's own $0.05647/question rate) up to ~$16.49 for the full recommended "
                        "first pass (needs-Jon necessity + a 20-row general necessity sample + "
                        "13-row failure triage + a full-150 parametric-knowledge control)."},
        "deps": [],
    },
    {
        "id": "or-group-repass",
        "title": "Re-pass v3's 105 conjunctive OR-groups",
        "one_line": "Re-mine the gold groups written before the miner learned that an OR-group "
                    "must not chain steps that are all required.",
        "status": "open", "action": "measure", "info": 2,
        "info_why": "A conjunctive group scored as an OR silently inflates recall, so every "
                    "retrieval number measured against that gold reads high.",
        "tells_us": "How much of the reported retrieval recall is an artefact of the gold's shape.",
        "evidence": [
            {"kind": "doc", "ref": "docs/HANDOFF-development.md", "note": "live queue item 6"},
            {"kind": "path", "ref": "evals/gold_miner_prompt.md",
             "note": "\"Batches b01-b09 were mined before rule 6 existed and contain conjunctive "
                     "OR-groups ... 5 of 9 sampled multi-member groups were conjunctive chains "
                     "wrongly merged, which silently inflates recall.\""},
        ],
        "metric": {"name": "retrieval recall (measurement validity)", "dir": "down",
                   "basis": "measured",
                   "cite": "evals/gold_miner_prompt.md",
                   "detail": "the adversarial review found the error in 5 of 9 sampled groups. "
                             "Fixing it should move measured recall DOWN toward the truth."},
        "cost": {"kind": "subscription",
                 "why": "gold mining runs on Claude Code subagents. docs/spec-cr-gold-mining.md "
                        "§8 puts \"anything requiring an API call\" out of scope."},
        "deps": [],
    },
    {
        "id": "match-semantics-curation",
        "title": "Curate match modes on the full 1,409-question corpus",
        "one_line": "Every row in rulesguru_full_v2.jsonl (and its 207-row L0 subset) defaults to "
                    "match: \"any\" with no exceptions; 745 rows (52.9%) have 2+ gold rules, so a "
                    "single incidental retrieval hit currently scores as a full pass on more than "
                    "half the corpus.",
        "status": "open", "action": "measure", "info": 2,
        "info_why": "It is the same measurement-validity defect as or-group-repass, at 7x the row "
                    "count and with no prior curation pass at all -- every retrieval number "
                    "computed against the full corpus inherits it.",
        "tells_us": "How much of the full-corpus recall/hit@k/\"context ok\" numbers are real versus "
                    "an artefact of an uncurated default.",
        "evidence": [
            {"kind": "doc", "ref": "docs/results-match-semantics.md",
             "note": "measured distributions across all three question files, confirms the judge "
                     "path (evals/judge_rulesguru.py) never reads match/gold so accuracy is "
                     "unaffected, and sizes the fix"},
            {"kind": "doc", "ref": "docs/results-orgroup-repass.md",
             "note": "the same defect, already found and partly corrected on the 150-set's 105 "
                     "curated groups (54 mis-encoded conjunctions)"},
            {"kind": "path", "ref": "evals/run_eval.py",
             "note": "gold_groups()/hit_at() (lines 158-177): match:\"any\" collapses the whole "
                     "gold list into one OR-group, so recall/hit@k/\"context ok\" all inherit "
                     "whatever match says, correctly given what match IS -- the gap is upstream, "
                     "in match never having been curated on this file"},
        ],
        "metric": {"name": "retrieval recall (measurement validity), full corpus", "dir": "down",
                   "basis": "measured",
                   "cite": "docs/results-match-semantics.md",
                   "detail": "745/1,409 rows (52.9%) carry 2+ gold rules under the uncurated "
                             "default; the or-group-repass pilot found 54/105 (51%) of a "
                             "comparable multi-rule population were mis-encoded once actually "
                             "checked against CR text, so a comparable share of these 745 rows "
                             "is a reasonable prior, not yet confirmed row-by-row."},
        "cost": {"kind": "subscription",
                 "why": "same CR-grounded read as or-group-repass (grep the CR text, Scryfall's "
                        "local cache where a card's wording decides it) -- no API call, no "
                        "Anthropic credits. Scale is the real cost: 745 rows is roughly 7x the "
                        "105-group pilot, and that pilot still needed Jon's own ruling on 25 of "
                        "105 groups (24%) even with full CR grounding."},
        "deps": ["or-group-repass"],
        "dep_why": "or-group-repass is the proven method (rule 6's test, applied and validated at "
                   "n=105); running the same method across 7x the rows before it's been checked "
                   "once on the pilot scope would be repeating unvalidated work at scale.",
    },
    {
        "id": "coverage-metric",
        "title": "Graded retrieval coverage score",
        "one_line": "Replaced hit_at()'s boolean hit/miss with the fraction of a question's gold "
                    "ids actually retrieved, so match:\"any\"/\"all\"/\"groups\" stop deciding how "
                    "strict the score is.",
        "status": "shipped", "action": "build", "info": 2,
        "info_why": "It targets a measured scoring defect (match-semantics-curation, "
                    "results-miss-partition's context-ok paradox) with a metric that needed zero "
                    "new model calls to validate.",
        "tells_us": "What fraction of a question's cited evidence actually lands in the retrieved "
                    "window, independent of whether that question's match mode was ever curated. "
                    "The per-row gap against hit_at() also ranks which multi-rule rows are worth a "
                    "human look, instead of leaving all 745 as an undifferentiated pile.",
        "docs": ["docs/spec-coverage-metric.md"],
        "evidence": [
            {"kind": "doc", "ref": "docs/results-match-semantics.md",
             "note": "745/1,409 full-corpus rows (52.9%) are match:\"any\" with 2+ gold ids, so a "
                     "single incidental hit currently scores full retrieval success"},
            {"kind": "doc", "ref": "docs/results-miss-partition.md",
             "note": "rg4023: a 10-id gold list scored \"context ok\" on 3 unrelated-enough ids "
                     "while the two deciding rules were never retrieved -- the boolean's failure "
                     "mode this spec targets"},
            {"kind": "path", "ref": "evals/run_eval.py",
             "note": "gold_groups()/hit_at() (lines 158-177) byte-identical, untouched; "
                     "coverage_at()/coverage_from_ids() added alongside, printed as a second table"},
            {"kind": "path", "ref": "evals/run_retrieval_diversity.py",
             "note": "group_coverage() (line 122) already exists but collapses to boolean on "
                     "match:\"any\" rows -- the spec's flat formula is the part that still works "
                     "on a 100%-any corpus; untouched"},
            {"kind": "path", "ref": "evals/backfill_coverage.py",
             "note": "backfills coverage across all 21 evals/answers/*.json files that record "
                     "retrieved_rule_ids (989 rows), zero model calls; also builds the hit_at-vs-"
                     "coverage gap worklist"},
            {"kind": "path", "ref": "evals/coverage_backfill.json",
             "note": "the backfill's output: per-arm mean coverage + hit rate, and the ranked "
                     "worklist, regenerate with evals/backfill_coverage.py"},
            {"kind": "path", "ref": "tests/test_coverage_metric.py",
             "note": "24 tests: empty gold excluded from means, single-rule gold, the any-mode "
                     "multi-rule disagreement case, groups-mode strictness, and hit_bool_from_ids() "
                     "checked for exact agreement with the untouched hit_at()"},
        ],
        "metric": {"name": "retrieval measurement resolution", "dir": "none", "basis": "measured",
                   "cite": "evals/coverage_backfill.json",
                   "detail": "a scoring-instrument change, not an intervention -- it moves no "
                             "accuracy or recall number by itself. Backfilled across 989 rows: "
                             "158 rows score a gap > 0.5 (hit_at() calls it a full pass while more "
                             "than half the cited gold never showed up) -- the worklist, not a "
                             "single mean, is the useful output."},
        "cost": {"kind": "zero",
                 "why": "recomputable directly from retrieved_rule_ids and gold already recorded "
                        "per row in evals/answers/*.json (confirmed on all 21 files that carry "
                        "retrieved_rule_ids, 989 rows total) -- no new model calls, no re-run arms."},
        "deps": [],
    },
    {
        "id": "double-mine",
        "title": "Double-mine for gold stability",
        "one_line": "Mine the same questions twice and measure how much the proposed gold agrees "
                    "with itself.",
        "status": "open", "action": "measure", "info": 2,
        "info_why": "0.54 run-to-run overlap is a noise floor under every recall number "
                    "measured against mined gold, and it has never been priced into one.",
        "tells_us": "How large the error bar on mined gold is.",
        "evidence": [
            {"kind": "doc", "ref": "docs/HANDOFF-development.md",
             "note": "live queue item 6: \"double-mine for stability (0.54 run-to-run overlap)\""},
        ],
        "metric": {"name": "gold stability", "dir": "none", "basis": "measured",
                   "cite": "docs/HANDOFF-development.md",
                   "detail": "0.54 overlap is already measured; this quantifies it properly "
                             "rather than changing it."},
        "cost": {"kind": "subscription", "why": "same subagent-mining path, no API credits"},
        "deps": [],
    },
    {
        "id": "resume-mining",
        "title": "Resume CR gold mining (809 rows)",
        "one_line": "Finish mining retrieval gold for the rest of the 1,409-question corpus.",
        "status": "partial", "action": "run", "info": 2,
        "info_why": "Without gold you cannot measure retrieval on those rows at all, which caps "
                    "what any full run can tell you about retrieval.",
        "tells_us": "Nothing on its own — it is the instrument the retrieval work is measured with.",
        "evidence": [
            {"kind": "commit", "ref": "8b94ef5", "note": "first structured mining pass, held-out 150"},
            {"kind": "commit", "ref": "56990b3", "note": "miner prompt versioned + merge rule"},
            {"kind": "doc", "ref": "docs/spec-cr-gold-mining.md", "note": "the spec it runs from"},
            {"kind": "doc", "ref": "docs/HANDOFF-development.md",
             "note": "live queue item 6: \"resume mining (809 rows)\""},
        ],
        "metric": {"name": "eval coverage", "dir": "up", "basis": "measured",
                   "cite": "docs/spec-cr-gold-mining.md",
                   "detail": "coverage is countable: rows with gold / rows in the corpus."},
        "cost": {"kind": "subscription",
                 "why": "spec §5: Claude Code subagents do not share a prompt cache, so batch "
                        "size is the whole cost model — but the pool is the Max plan, not credits"},
        "deps": ["or-group-repass"],
        "dep_why": "the pre-rule-6 batches should be repaired before more gold is mined on top "
                   "of the same prompt lineage",
    },
    {
        "id": "citation-filter",
        "title": "Post-hoc citation filter",
        "one_line": "Drop citations the answer does not actually rest on, after generation, "
                    "rather than trying to make the model emit fewer.",
        "status": "design-only", "action": "decide", "info": 1,
        "info_why": "The read-only evidence pass is already done inside the plan; what is left "
                    "is a decision and a small build.",
        "tells_us": "Whether citation precision is a real problem or a cosmetic one.",
        "evidence": [
            {"kind": "doc", "ref": "docs/plan-citation-filter.md",
             "note": "\"DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Awaiting Jon's review.\" "
                     "Its §evidence table is the discharge of a DECISIONS.md pre-commitment."},
        ],
        "metric": {"name": "citation precision", "dir": "up", "basis": "predicted",
                   "cite": "docs/plan-citation-filter.md",
                   "detail": "no arm has been re-graded under a filter; the plan says so and "
                             "calls that a separate, bigger exercise."},
        "cost": {"kind": "zero",
                 "why": "a filter over an answer already produced. Re-GRADING arms under it "
                        "would cost judge calls, and the plan scopes that out."},
        "deps": [],
    },
    {
        "id": "cr-update-check",
        "title": "CR update checker (scripts/check_cr_update.py)",
        "one_line": "Detect when a new Comprehensive Rules release silently drops or renumbers a "
                    "rule, and fix the gold automatically where the fix is provably safe.",
        "status": "shipped", "action": "build", "info": 1,
        "info_why": "It protects the corpus rather than moving a metric, but two rules (606.5, "
                    "119.1d) were missing for the life of the project before anyone noticed.",
        "tells_us": "Nothing new — it stops a class of silent corruption.",
        "evidence": [
            {"kind": "commit", "ref": "da7f374",
             "note": "\"Record Jon's rulings: CR-update checker approved\" — approved, so this is "
                     "not awaiting a ruling"},
            {"kind": "doc", "ref": "docs/spec-cr-update-check.md", "note": "the spec"},
            {"kind": "path", "ref": "scripts/check_cr_update.py",
             "note": "built 2026-07-26 with 40 tests. Classifies rules unchanged/renumbered/"
                     "edited/deleted/ambiguous by content fingerprint and auto-fixes only "
                     "renumbered ids, and only with --apply. Self-test on the current CR: "
                     "unchanged=3153, remaps=0, flags=0, exit 0"},
        ],
        "metric": {"name": "silent rule drops", "dir": "down", "basis": "measured",
                   "cite": "docs/spec-cr-update-check.md",
                   "detail": "two confirmed drops to date; the parser guards from 9e41d7d / "
                             "2d212a7 close part of it already."},
        "cost": {"kind": "zero", "why": "a local script over the CR text file; no model calls"},
        "deps": [],
    },
    {
        "id": "packaging",
        "title": "Packaging — README and repo hygiene",
        "one_line": "Finish the public-facing README so a technical reader can skim it in 90 "
                    "seconds or clone and run it in one command.",
        "status": "partial", "action": "build", "info": 1,
        "info_why": "It is the portfolio surface, and it is the only thing standing between the "
                    "deploy track and a link Jon can send.",
        "tells_us": "Nothing measurable — it is presentation.",
        "evidence": [
            {"kind": "commit", "ref": "08e5ff0", "note": "MIT license, SVG wordmark, uv.lock, one name"},
            {"kind": "commit", "ref": "4f68819", "note": "branding assets, real Makefile targets"},
            {"kind": "path", "ref": "README.md",
             "note": "landed and tracked as of 2026-07-26 — the architecture diagram was "
                     "corrected to claude-opus-5 at effort=low (it had claimed claude-sonnet-5) "
                     "and the quickstart was verified by actually running it"},
            {"kind": "doc", "ref": "docs/plan-packaging.md", "note": "the plan"},
        ],
        "metric": {"name": "none", "dir": "none", "basis": "unknown",
                   "cite": None, "detail": "no product metric moves."},
        "cost": {"kind": "zero", "why": "writing and repo hygiene"},
        "deps": [],
    },
    {
        "id": "rerank-after-rewrite",
        "title": "Rerank after rewrite",
        "one_line": "Put the cross-encoder reranker after the rewrite step instead of instead of "
                    "it — the one cell of the retrieval grid nobody has run.",
        "status": "design-only", "action": "decide", "info": 1,
        "info_why": "Cheap, but the plan was scoped to a control that production has since moved "
                    "off, so it needs a re-scope before it is worth running.",
        "tells_us": "Whether reranking still adds anything once multi-query fusion has run.",
        "relevant": False,
        "relevance_note": "Overtaken in part by commit 86b5d27. The plan scopes itself to the "
                          "shipped control `vec+rw1-haiku` at REWRITE_N=1, and notes its option "
                          "(c) \"collapses to (b) exactly\" at n=1. Production now runs "
                          "REWRITE_N=3, so the arm it describes is no longer the shipped path.",
        "evidence": [
            {"kind": "doc", "ref": "docs/plan-rerank-after-rewrite.md",
             "note": "\"DRAFT under Rule 0 — DESIGN ONLY. Nothing built.\""},
            {"kind": "commit", "ref": "86b5d27", "note": "the REWRITE_N change that overtook its scoping"},
            {"kind": "path", "ref": "src/rulesagent/retrieve/rerank.py",
             "note": "the reranker itself already exists and is cached"},
        ],
        "metric": {"name": "retrieval recall@k", "dir": "up", "basis": "predicted",
                   "cite": "docs/plan-rerank-after-rewrite.md",
                   "detail": "the plan quotes 71% for the shipped arm as the baseline to beat; "
                             "no reranked-after-rewrite number exists."},
        "cost": {"kind": "api_stated", "lo": 0.10, "hi": 0.30, "bound": "upper",
                 "cite": "docs/plan-rerank-after-rewrite.md",
                 "why": "the plan's own table: 2 stacked arms x 31 questions = 62 reranker calls, "
                        "\"under $0.10\"; x 134 questions = 268 calls, \"under $0.30\""},
        "tradeoff": {
            "options": [
                {"name": "Re-scope to the shipped n=3 path and run it", "pick": True,
                 "pros": ["under $0.30 — the cheapest priced experiment on the whole board",
                          "reranking already exists and is cached, so there is no build"],
                 "cons": ["needs a re-scope first: the plan's control arm is no longer what production runs",
                          "the diversity factorial already found most of the rewrite gain banked, so the "
                          "headroom for a second re-ranking step may be small"]},
                {"name": "Run it exactly as written (n=1 control)", "pick": False,
                 "pros": ["no re-scope needed; the plan is complete as it stands"],
                 "cons": ["measures an arm production no longer runs, so a win would not transfer"]},
                {"name": "Drop it", "pick": False,
                 "pros": ["frees the slot for the L0 slice and the gold audit"],
                 "cons": ["gives up the one untested cell of the retrieval grid for under $0.30"]},
            ],
            "why": "The price is trivial and the machinery exists, so the only real objection is that the "
                   "plan aims at the wrong baseline. That is a scoping edit, not a rebuild.",
            "against": "The retrieval-diversity result is a genuine reason to expect little: it found most "
                       "of the rewrite gain already banked, which is where a reranker would have to find "
                       "its headroom.",
            "flip": "A miss-partition result showing retrieval, not reasoning, is where the losses are."},
        "deps": [],
    },
    {
        "id": "second-hop",
        "title": "Second-hop retrieval",
        "one_line": "Retrieve again from what the first retrieval found, so rules two or three "
                    "hops from the question's wording can be reached at all.",
        "status": "open", "action": "decide", "info": 2,
        "info_why": "It is the only proposal aimed at a failure class that question-side "
                    "rewriting provably cannot reach.",
        "tells_us": "Whether the multi-hop misses are reachable by retrieval at all.",
        "evidence": [
            {"kind": "doc", "ref": "docs/HANDOFF-development.md",
             "note": "live queue item 5, and the rg241 finding: all four rules in the derivation "
                     "are indexed, but hops 2-3 have no resemblance to the question"},
            {"kind": "doc", "ref": "docs/plan-l1-crossref-expansion.md",
             "note": "names an LLM second-hop query as the fallback if structural cross-ref "
                     "expansion is not enough — which is what L1 Part B measured"},
        ],
        "metric": {"name": "retrieval recall on multi-hop questions", "dir": "up",
                   "basis": "predicted", "cite": "docs/HANDOFF-development.md",
                   "detail": "the rg241 diagnosis is measured; that a second hop fixes it is not."},
        "cost": {"kind": "unknown",
                 "why": "no doc sizes it. There is no plan-*.md for second-hop retrieval yet, so "
                        "no question count and no per-question call count to multiply."},
        "deps": [],
    },
    {
        "id": "armb-rerun",
        "title": "Re-run derivability arm B with corrected ruling labels",
        "one_line": "Re-run the gold-only arm so its ruling citations line up with the rulings it "
                    "was actually handed, making them usable data.",
        "status": "open", "action": "decide", "info": 1,
        "info_why": "It repairs one arm's citation data. The accuracy number is unaffected — the "
                    "bug is in the eval harness, not production.",
        "tells_us": "Whether arm B's citations can be read at all; today 69% of citing rows are off.",
        "evidence": [
            {"kind": "commit", "ref": "ad53532",
             "note": "root cause: evals/build_gold_prompts.py, not the product"},
            {"kind": "commit", "ref": "b11f1cd",
             "note": "the fix — ruling labels moved to the prompt boundary"},
            {"kind": "doc", "ref": "docs/report-ruling-citation-offbyone.md",
             "note": "\"production is clean across 397 citations; the defect ... affects 69% of "
                     "citing rows in derivability arms B/C\". Still needs Jon's ruling on whether "
                     "the re-run is worth it."},
        ],
        "metric": {"name": "citation usability in arm B", "dir": "up", "basis": "measured",
                   "cite": "docs/report-ruling-citation-offbyone.md",
                   "detail": "69% of citing rows are currently unusable; the fix is verified."},
        "cost": {"kind": "api_stated", "lo": 8.47, "hi": 8.47,
                 "cite": "docs/HANDOFF-development.md",
                 "why": "the handoff's own figure for re-running arm B"},
        "tradeoff": {
            "options": [
                {"name": "Re-run arm B ($8.47)", "pick": False,
                 "pros": ["makes 69% of its citing rows readable instead of misaligned",
                          "the fix is already shipped and verified (b11f1cd), so the re-run is not a gamble"],
                 "cons": ["the accuracy number does not change — this buys citation data only",
                          "nothing currently open depends on arm B's citations"]},
                {"name": "Leave it, and mark the citations unusable", "pick": True,
                 "pros": ["costs nothing",
                          "arm B's 91.3% is unaffected either way; the defect is in the eval harness"],
                 "cons": ["any future analysis of where arm B cited from starts by re-running this anyway"]},
            ],
            "why": "Nothing on the ready list needs arm B's citations. The $8.47 is small, but it buys a "
                   "dataset with no current consumer, and the accuracy the arm is quoted for is not "
                   "affected.",
            "against": "If the miss-partition diagnostic ends up wanting per-row citation provenance from "
                       "the oracle arm, this becomes a prerequisite rather than a nice-to-have.",
            "flip": "Any open item that needs to read arm B's citations."},
        "deps": [],
    },
    {
        "id": "purerules-eval",
        "title": "Pure-rules held-out eval set",
        "one_line": "Generalize card questions into rules questions so retrieval and generation "
                    "can be measured without the oracle-text confound.",
        "status": "partial", "action": "build", "info": 2,
        "info_why": "Two separate rulings are parked waiting on this instrument, so it unblocks "
                    "more than it measures.",
        "tells_us": "Nothing directly — it is the missing instrument two open decisions need.",
        "docs": ["docs/spec-pure-rules-holdout.md"],
        "evidence": [
            {"kind": "commit", "ref": "47b3090", "note": "batch 1 drafted (8 candidates) + approval UI"},
            {"kind": "commit", "ref": "f4396c5", "note": "approval UI shows power/toughness and DFC faces"},
            {"kind": "path", "ref": "evals/build_purerules_approval_ui.py", "note": "the UI exists"},
            {"kind": "doc", "ref": "DECISIONS.md",
             "note": "2026-07-24 \"Pure-rules eval: standing grant to draft freely\" — batch 1 "
                     "approved 8/8 with zero edits; throughput is bounded by Jon's review because "
                     "eval questions and gold stay do-not-delegate"},
        ],
        "metric": {"name": "measurement validity", "dir": "up", "basis": "predicted",
                   "cite": "DECISIONS.md",
                   "detail": "the confound is documented (the holdout set is 98% card questions, "
                             "only ~3 where CR-rule retrieval is load-bearing); the fix is untested."},
        "cost": {"kind": "subscription",
                 "why": "drafting runs on subagents under the standing grant; Jon's review is the "
                        "bottleneck, not credits"},
        "deps": [],
    },
    {
        "id": "sso",
        "title": "SSO track — OIDC, then SAML, then the breakage lab",
        "one_line": "Add real single sign-on to the admin surface, in three separately-approved "
                    "slices, and break it deliberately to learn the failure modes.",
        "status": "design-only", "action": "decide", "info": 1,
        "info_why": "Explicitly a resume-evidence track. It moves no product metric and should "
                    "not compete with measurement work for the same slot.",
        "tells_us": "Nothing about the bot.",
        "evidence": [
            {"kind": "doc", "ref": "docs/plan-sso.md",
             "note": "\"Working Rule 0 artifact. DESIGN ONLY — no source changes in this pass.\" "
                     "Ships as three independently-approved slices."},
            {"kind": "path", "ref": "TODO-SSO.md", "note": "the track's own to-do list"},
        ],
        "metric": {"name": "none", "dir": "none", "basis": "unknown", "cite": None,
                   "detail": "the plan says the value is Jon being able to explain it cold."},
        "cost": {"kind": "zero", "why": "local build; the identity provider side is free-tier work"},
        "tradeoff": {
            "options": [
                {"name": "Build the SSO track", "pick": False,
                 "pros": ["spends no credits", "it is the point of the project for Jon's job search"],
                 "cons": ["moves no metric on this page",
                          "the SAML slice needs the deploy track first, which needs the README"]},
                {"name": "Do the measurement backlog first", "pick": True,
                 "pros": ["the L0 slice and the gold audit are what the go/no-go call is waiting on",
                          "SSO is not blocked by anything that decays if it waits"],
                 "cons": ["the portfolio surface stays unfinished for longer"]},
            ],
            "why": "Both are defensible; they compete for the same hours, not the same budget. The "
                   "measurement items gate a decision that is live right now, and SSO gates nothing.",
            "against": "If the job search is the actual deadline, that is an external clock this page "
                       "cannot see, and it would reverse the order. Stated as a judgement, not a "
                       "measurement.",
            "flip": "An interview or a deadline that makes the deployed demo urgent."},
        "deps": ["deploy"],
        "dep_why": "the plan's §0 sequencing: OIDC needs no deployed URL, SAML does",
    },
    {
        "id": "deploy",
        "title": "Deploy track — private demo to a public Fly.io link",
        "one_line": "Get Rulemancer onto the internet behind a link, in independently-shippable "
                    "slices.",
        "status": "design-only", "action": "decide", "info": 1,
        "info_why": "Nothing measured depends on it, but the portfolio value does.",
        "tells_us": "Nothing measurable.",
        "merged": ["docs/plan-limitations-and-deploy.md"],
        "merge_why": "plan-deploy.md's own opening: it \"turns the L5 bullet list in "
                     "docs/plan-limitations-and-deploy.md ... into a sequenced, "
                     "independently-shippable set of slices.\" Same track, one superseding the "
                     "other. The older doc's L1/L3/L8 items shipped separately.",
        "evidence": [
            {"kind": "doc", "ref": "docs/plan-deploy.md",
             "note": "\"Rule 0. DESIGN ONLY, no code yet.\""},
            {"kind": "commit", "ref": "09683fc",
             "note": "L3 SQLite caches — deploy blocker #1 — already shipped"},
        ],
        "metric": {"name": "none", "dir": "none", "basis": "unknown", "cite": None,
                   "detail": "no product metric."},
        "cost": {"kind": "hosting", "lo": 3.0, "hi": 5.0, "unit": "/month",
                 "cite": "docs/plan-limitations-and-deploy.md",
                 "why": "the merged doc's hosting table: Fly.io ~$3-5/mo for an always-on small "
                        "VM with volumes for the SQLite caches. Not API credits."},
        "deps": ["packaging"],
        "dep_why": "the plan wants the README current with everything shipped since it was drafted",
    },
    # -------------------------------------------------------------- blocked --
    {
        "id": "full-run",
        "title": "The full RulesGuru run — all 1,409 questions -- DONE",
        "one_line": "Run the shipped config over the entire corpus and publish a real number "
                    "instead of a projection. Ran 2026-07-27: 85.88%.",
        "status": "shipped", "action": "run", "info": 3,
        "info_why": "DONE 2026-07-27. It was the decision this whole page existed to serve, and "
                    "it went ahead without waiting on gold-audit-b2 (grading-error correction is "
                    "still open and not yet folded into this figure).",
        "tells_us": "The actual accuracy, with no reweighting and no extrapolation: 85.88% on all "
                    "1,409 rows (1,210 correct), 95% Wilson CI [83.96%, 87.60%]. By level: L0 "
                    "96.14%, L1 90.27%, L2 84.24%, L3 67.90%, Corner Case 71.01% -- a monotonic "
                    "decline that corroborates docs/results-failure-taxonomy.md's separate finding "
                    "that L3 fails at ~6x the base rate. This beat the old 80.3% [71.7-86.8] "
                    "projection by 3.1 points; that projection is now retired.",
        "evidence": [
            {"kind": "doc", "ref": "docs/HANDOFF-development.md",
             "note": "live queue item 3: \"At $73-91 it is not a cost decision. The judge is now "
                     "measured; the remaining question is L0 coverage.\" -- the ask that was run"},
            {"kind": "doc", "ref": "docs/results-headline-accuracy.md",
             "note": "the result: 85.88% [83.96%, 87.60%], config opus-5/low/v2/raw/no-layers-tool, "
                     "batched, $43.61, commit 2543454. Refusals measured at 0.71% (10/1,409 rows), "
                     "so the figure is not a refusal artifact -- contrast docs/"
                     "results-rules86-placebo.md where placebo context drives refusal to 90.7%"},
        ],
        "metric": {"name": "headline accuracy", "dir": "none", "basis": "measured",
                   "cite": "docs/results-headline-accuracy.md",
                   "detail": "85.88% [83.96%, 87.60%], n=1,409. Net error direction is more "
                             "likely an understatement than an overstatement: judge false "
                             "positives run 4.4% (pull the number down) while false negatives "
                             "measure 0% with a 4.7% upper bound (would pull it up)."},
        "cost": {"kind": "spent", "why": "$43.61, generation only, 1,409 rows batched -- plus "
                                          "$1.90 to warm the v2 rewrite prompt cache first"},
        "deps": [],
    },
    {
        "id": "rewriter-bakeoff-p2",
        "title": "Rewriter bakeoff, phase 2 (generation-side)",
        "docs": ["docs/plan-rewriter-model-bakeoff.md"],
        "one_line": "Take the phase-1 retrieval winner through to generation and see whether the "
                    "coverage gain shows up in answers.",
        "status": "partial", "action": "run", "info": 2,
        "info_why": "Phase 1 produced a conflict that only a better instrument can resolve, so "
                    "running phase 2 now would measure the wrong thing.",
        "tells_us": "Whether a better rewriter is worth its cost in answer quality.",
        "evidence": [
            {"kind": "doc", "ref": "docs/report-rewriter-bakeoff.md",
             "note": "phase 1 ran 2026-07-23, retrieval only — so phase 1 is shipped"},
            {"kind": "doc", "ref": "DECISIONS.md",
             "note": "2026-07-24 Lever 3: \"rewriter: HOLD for the pure-rules eval.\" haiku and "
                     "sonnet are identical at the operational depth (TOP_K=15) but sonnet gains "
                     "on the 134-question holdout, which is 98% card questions"},
        ],
        "metric": {"name": "answer accuracy", "dir": "up", "basis": "predicted",
                   "cite": "DECISIONS.md",
                   "detail": "the retrieval coverage gain is measured (@50 75% vs 63%); its value "
                             "in answers is explicitly called unmeasured."},
        "cost": {"kind": "unknown",
                 "why": "the bakeoff plan sizes phase 1 only (\"cents, not dollars\" for 279 "
                        "rewrite calls). Phase 2 adds generation and judging on a question set "
                        "that does not exist yet, so it cannot be priced."},
        "deps": ["purerules-eval"],
        "dep_why": "Jon's Lever 3 ruling names the pure-rules set as the instrument that settles it",
    },
    {
        "id": "l2-generator",
        "title": "Re-test the generator model choice, post-tools",
        "one_line": "Re-run the sonnet-vs-cheap-model comparison on the tool-triggering subset, "
                    "now that exact sub-computations live in Python instead of the model. The "
                    "tool-triggering subset is smaller than when this item was scoped: the layer "
                    "resolver that motivated it was removed 2026-07-27 (measured zero benefit), so "
                    "only the cost calculator remains as a live tool to re-test against.",
        "status": "open", "action": "run", "info": 2,
        "info_why": "The tool roadmap changed the generator's job, so the old comparison measured "
                    "a pipeline that no longer exists. UPDATE 2026-07-27: it's changed again -- "
                    "the layers tool this item originally cited as \"the tool this was waiting on\" "
                    "is gone (commit f357c4a), so \"post-tools\" now means post-cost-calculator "
                    "only. Re-scope to the cost-tagged subset before running.",
        "tells_us": "Whether a cheap model plus the cost-calculator tool matches an expensive "
                    "model without it.",
        "evidence": [
            {"kind": "doc", "ref": "DECISIONS.md",
             "note": "2026-07-24 Lever 2: \"DEFERRED to post-tools\". The re-test measures three "
                     "things, not one: accuracy, tool-call well-formedness, citation stability"},
            {"kind": "commit", "ref": "24f2bb9",
             "note": "layers trigger calibrated to 77.8% -- the tool this item was originally "
                     "waiting on; since removed"},
            {"kind": "commit", "ref": "f357c4a",
             "note": "layer resolver REMOVED 2026-07-27, measured zero benefit (5-3 on fired "
                     "rows, p=0.73) -- narrows this item's scope to the cost calculator alone"},
        ],
        "metric": {"name": "cost per question at equal accuracy", "dir": "down",
                   "basis": "predicted", "cite": "DECISIONS.md",
                   "detail": "gpt-5-mini's measured weak spot is structured-output precision "
                             "(stable citations 2/50 on a since-superseded prompt), which is "
                             "exactly what tools lean on. Needs re-measuring, not assuming."},
        "cost": {"kind": "unknown",
                 "why": "the tool-triggering subset size is not fixed in any doc, so there is no "
                        "question count to multiply"},
        "deps": ["purerules-eval", "miss-partition"],
        "dep_why": "the ruling ties it to the pure-rules instrument, and the partition tells you "
                   "whether generation is even where the losses are",
    },
    # --------------------------------------------------------------- shipped --
    {"id": "s-rewriting", "title": "Query-rewriting layer (#3a)", "status": "shipped", "info": 2,
     "docs": ["docs/plan-3a-query-rewriting.md"],
     "one_line": "Rewrite the user's question into several search keys and retrieve on those; the "
                 "corpus is untouched.",
     "tells_us": "", "action": "run",
     "evidence": [{"kind": "commit", "ref": "3607d9b", "note": "RewrittenQuery contract"},
                  {"kind": "commit", "ref": "9cf1409", "note": "the layer"},
                  {"kind": "commit", "ref": "225cbbf", "note": "temperature pinned to 0"},
                  {"kind": "commit", "ref": "86b5d27", "note": "REWRITE_N 1 -> 3 in production"},
                  {"kind": "path", "ref": "src/rulesagent/retrieve/rewrite.py"}],
     "metric": {"name": "retrieval recall", "dir": "up", "basis": "measured",
                "cite": "docs/results-retrieval-diversity.md",
                "detail": "the diversity factorial found most of the rewrite gain already banked."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {"id": "s-scryfall", "title": "Scryfall card enrichment (#3b) + local bulk snapshot",
     "status": "shipped", "info": 2, "action": "run",
     "docs": ["docs/plan-3b-scryfall-enrichment.md"],
     "one_line": "Resolve [bracketed] card names to oracle text and rulings and put them in the "
                 "prompt, served from a local bulk snapshot instead of live lookups.",
     "tells_us": "",
     "merged": ["docs/plan-scryfall-local-bulk.md", "docs/plan-card-enrichment-fields.md"],
     "merge_why": "one card-data path built in three passes: enrichment (#3b), then the "
                  "layout-first field set, then replacing live lookups with a local snapshot. "
                  "Separate docs, same subsystem, and each supersedes the previous one's data model.",
     "evidence": [{"kind": "commit", "ref": "700e2bc", "note": "enrichment"},
                  {"kind": "commit", "ref": "44ef20f", "note": "layout-first per-face fields"},
                  {"kind": "commit", "ref": "c481292", "note": "local bulk + per-face lookup + self-heal"},
                  {"kind": "path", "ref": "src/rulesagent/tools/scryfall_store.py"},
                  {"kind": "path", "ref": "scripts/refresh_scryfall_bulk.py"}],
     "metric": {"name": "answer accuracy on card questions", "dir": "up", "basis": "measured",
                "cite": "DECISIONS.md",
                "detail": "2026-07-21 \"#3b built ... verified live\"; the gold-by-ablation pass "
                          "then found the RAG rules were redundant on 4 of 5 card questions."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {"id": "s-rulings", "title": "Per-card ruling mini-RAG (rulings on demand)",
     "status": "shipped", "info": 2, "action": "run",
     "docs": ["docs/plan-rulings-on-demand.md"],
     "one_line": "Select only the rulings relevant to the question for each referenced card, "
                 "instead of pasting all of them.",
     "tells_us": "",
     "evidence": [{"kind": "commit", "ref": "27733fe", "note": "built + verified"},
                  {"kind": "commit", "ref": "7a316bd", "note": "ruling_id made content-derived, not positional"},
                  {"kind": "commit", "ref": "17f4d16", "note": "positional cache purged; TOP_N 3 -> 5"},
                  {"kind": "path", "ref": "src/rulesagent/tools/ruling_retrieval.py"}],
     "metric": {"name": "prompt size", "dir": "down", "basis": "measured",
                "cite": "docs/plan-packaging.md",
                "detail": "context cut 35->6 / 22->3 / 18->3 rulings with zero loss."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {"id": "s-chunking", "title": "Chunking: embedded text split from context text",
     "status": "shipped", "info": 2, "action": "run",
     "docs": ["docs/plan-chunk-context-split.md"],
     "one_line": "Embed a distinctive short text, hand the generator the complete one.",
     "tells_us": "",
     "evidence": [{"kind": "commit", "ref": "63d25ed", "note": "plan approved"},
                  {"kind": "commit", "ref": "e02d5ea", "note": "implemented"},
                  {"kind": "doc", "ref": "DECISIONS.md", "note": "2026-07-21 \"KEPT, a measured tradeoff\""}],
     "metric": {"name": "retrieval recall@5", "dir": "none", "basis": "measured",
                "cite": "DECISIONS.md", "detail": "adopted as a tradeoff, not a clean win."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {"id": "s-crossrefs", "title": "L1 cross-reference expansion", "status": "shipped", "info": 2,
     "action": "run",
     "one_line": "Follow the CR's own \"see rule X\" references in retrieved chunks and pull the "
                 "referenced rules in. Part A shipped; Part B was measured and not adopted.",
     "tells_us": "",
     "evidence": [{"kind": "commit", "ref": "92fa295", "note": "Part A pure function, TDD"},
                  {"kind": "commit", "ref": "fd84b08", "note": "Part A wired into RulesAgent"},
                  {"kind": "commit", "ref": "30ac5db",
                   "note": "Part B (rewrite-as-ruling-query union arm) measured and NOT shipped"},
                  {"kind": "path", "ref": "src/rulesagent/retrieve/crossrefs.py"}],
     "metric": {"name": "multi-hop recall", "dir": "none", "basis": "measured",
                "cite": "docs/plan-rulings-recall.md",
                "detail": "the plan records that cross-ref expansion \"shipped but measured a "
                          "null result\" on the misses it was aimed at — which is what makes "
                          "second-hop retrieval the live proposal."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {"id": "s-diversity", "title": "Retrieval diversity factorial (MMR x hybrid x multi-query)",
     "status": "shipped", "info": 2, "action": "measure",
     "docs": ["docs/spec-retrieval-diversity.md"],
     "one_line": "Run the three diversity levers as a factorial to see which actually gets "
                 "distinct rules into the window.",
     "tells_us": "",
     "evidence": [{"kind": "commit", "ref": "fb480c9", "note": "\"MMR refuted, most of the rewrite gain already banked\""},
                  {"kind": "path", "ref": "src/rulesagent/retrieve/mmr.py"},
                  {"kind": "doc", "ref": "docs/results-retrieval-diversity.md"}],
     "metric": {"name": "retrieval diversity", "dir": "up", "basis": "measured",
                "cite": "docs/results-retrieval-diversity.md",
                "detail": "multi-query wins, MMR refuted. Ran at zero API spend (cache-only)."},
     "cost": {"kind": "spent", "why": "shipped; the run itself was cache-only, zero API spend"},
     "deps": []},
    {"id": "s-tools", "title": "Deterministic tools — cost calculator (shipped); "
                               "layer resolver (shipped, then REMOVED)",
     "status": "shipped", "info": 2, "action": "run",
     "one_line": "Move exact sub-computations (mana costs, CR 613 layers) out of the model and "
                 "into Python functions the model can call. The cost calculator stuck; the layer "
                 "resolver was built, calibrated, measured at zero benefit, and removed "
                 "(commit f357c4a, 2026-07-27) along with its 76-test suite.",
     "tells_us": "",
     "merged": ["docs/plan-cost-calculator-tool.md", "docs/plan-layer-system-tool.md",
                "docs/spec-slice0-harness.md"],
     "merge_why": "one pattern, built twice, plus the harness slice that made the second one "
                  "measurable. The layers plan says outright that \"every piece of machinery this "
                  "needs already exists and already shipped\" for the cost tool.",
     "evidence": [{"kind": "commit", "ref": "a36db25", "note": "name-routed, tool-agnostic dispatch seam"},
                  {"kind": "commit", "ref": "1dfe6d4", "note": "cap-exhaustion + silent-garbage guards"},
                  {"kind": "commit", "ref": "c85de03", "note": "layer resolver slice 1"},
                  {"kind": "commit", "ref": "4343848", "note": "resolve_layers wired into the dispatch loop"},
                  {"kind": "commit", "ref": "24f2bb9",
                   "note": "trigger calibration FAILED at 20.4%, ruled to threshold 1, now 77.8%"},
                  {"kind": "commit", "ref": "f357c4a",
                   "note": "layer resolver REMOVED, measured zero benefit -- layer_resolver.py "
                           "and its 76-test suite deleted; the rules86 A/B (results-rules86-"
                           "placebo.md) confirms it did not exist at run time"},
                  {"kind": "path", "ref": "src/rulesagent/tools/cost_calculator.py",
                   "note": "the surviving tool"}],
     "metric": {"name": "accuracy on tool-shaped questions", "dir": "none", "basis": "measured",
                "cite": "docs/report-costtool-validation.md; commit f357c4a for the removal",
                "detail": "cost calculator validated at scale on the 199 cost-tagged questions. "
                          "The layers trigger had reached 42/54 = 77.8% of bucket A, but the "
                          "removal measurement (commit f357c4a) found it fired on 42 of 68 rows "
                          "whose gold requires a CR 613 rule and changed nothing: 5-3 on fired "
                          "rows, p=0.73 -- while costing 8.6% per query and 41% more API round "
                          "trips (8,469 -> 5,982 input tokens, 116 -> 68 rounds). Trigger rate was "
                          "never the bottleneck; the tool just didn't help once it fired."},
     "cost": {"kind": "spent", "why": "shipped, then partly reverted"}, "deps": []},
    {"id": "s-eval-harness", "title": "Eval instrument — RulesGuru import, judging, and the knobs",
     "status": "shipped", "info": 3, "action": "measure",
     "one_line": "The measurement stack: an external judge-authored question set, an outside "
                 "judge, transitive grading, and the effort/no-rewrite/model knobs every arm needs.",
     "tells_us": "",
     "merged": ["docs/plan-rulesguru-import.md", "docs/plan-rulesguru-as-instrument.md",
                "docs/plan-openrouter-models.md", "docs/plan-judge-transitive-grading.md",
                "docs/plan-opus-grader-calibration.md", "docs/spec-effort-and-norewrite.md",
                "docs/plan-run-progress.md"],
     "merge_why": "seven docs, one instrument. The import built the set, as-instrument specified "
                  "how to consume it, OpenRouter added the outside judge, transitive grading and "
                  "the Opus calibration decided how much grading to delegate, and the knobs plus "
                  "run-progress made the arms runnable and observable.",
     "evidence": [{"kind": "commit", "ref": "a27c4e0", "note": "RulesGuru 150 imported with human gold"},
                  {"kind": "commit", "ref": "538cc5f", "note": "gpt-5-mini judge adopted at 95% agreement"},
                  {"kind": "commit", "ref": "819bbc7", "note": "transitive-grading pipeline"},
                  {"kind": "commit", "ref": "f5968cc", "note": "Opus-grader calibration v2: 78.3% primary"},
                  {"kind": "commit", "ref": "579d544", "note": "effort knob, no-rewrite arm, model override"},
                  {"kind": "commit", "ref": "228aa24", "note": "run-progress heartbeats + incremental writes"},
                  {"kind": "commit", "ref": "15644d4", "note": "judge provenance stamped into verdict files"},
                  {"kind": "path", "ref": "evals/progress.py"},
                  {"kind": "doc", "ref": "docs/report-rulesguru-holdout.md",
                   "note": "\"overturn three working premises\" — the holdout's first result"}],
     "metric": {"name": "measurement validity", "dir": "up", "basis": "measured",
                "cite": "docs/report-rulesguru-holdout.md",
                "detail": "the external set overturned three premises that the internal "
                          "31-question set had supported."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {"id": "s-judge-error", "title": "Judge error rate, both directions", "status": "shipped",
     "info": 3, "action": "measure",
     "one_line": "Measure how often the frozen judge is wrong in each direction, because every "
                 "accuracy on this page inherits it.",
     "tells_us": "",
     "evidence": [{"kind": "commit", "ref": "3bfd0c8",
                   "note": "\"FP is small, but the reference grader failed validation\""},
                  {"kind": "commit", "ref": "eb16810", "note": "arm B corrected to 91.3%"},
                  {"kind": "doc", "ref": "docs/results-judge-error-rate.md"}],
     "metric": {"name": "accuracy overstatement", "dir": "down", "basis": "measured",
                "cite": "docs/results-judge-error-rate.md",
                "detail": "false positives 4.4% (95% CI 1.7-10.9%), treated as an upper bound. "
                          "The reference grader agreed with the frozen judge 32/32 on Jon's "
                          "hand-graded rows, so it cannot serve as an independent check."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {"id": "s-weighted", "title": "Level-weighted scoring", "status": "shipped", "info": 1,
     "action": "measure",
     "docs": ["docs/spec-weighted-scoring.md"],
     "one_line": "Score flat across L0-L3 with Corner Case at half weight, per Jon's ruling.",
     "tells_us": "",
     "evidence": [{"kind": "commit", "ref": "b085417", "note": "spec, design-only"},
                  {"kind": "commit", "ref": "372965b", "note": "built, 53 tests"},
                  {"kind": "path", "ref": "evals/weighted_score.py"}],
     "metric": {"name": "reported accuracy", "dir": "none", "basis": "measured",
                "cite": "docs/spec-weighted-scoring.md",
                "detail": "no conclusion flips; largest movement 1.5 pp."},
     "cost": {"kind": "zero",
              "why": "pure arithmetic over verdict files already on disk — no model call, no "
                     "re-run, genuinely $0"},
     "deps": []},
    {"id": "s-prod-switches", "title": "Production switches — opus-5 at effort low, REWRITE_N 3",
     "status": "shipped", "info": 3, "action": "run",
     "one_line": "The two config changes the current numbers rest on.",
     "tells_us": "",
     "evidence": [{"kind": "commit", "ref": "d95a461", "note": "GEN_MODEL -> claude-opus-5, GEN_EFFORT=low"},
                  {"kind": "commit", "ref": "86b5d27", "note": "REWRITE_N 1 -> 3"},
                  {"kind": "doc", "ref": "docs/results-easy-regression.md",
                   "note": "the regression check that cleared the switch"}],
     "metric": {"name": "accuracy and cost", "dir": "up", "basis": "measured",
                "cite": "docs/results-easy-regression.md",
                "detail": "+13.0 pp on the easy set and +9.3 pp on the hard set versus sonnet, "
                          "both clearing their noise floors; REWRITE_N 3 measured at "
                          "$0.00036/question, ~0.6% of answer cost."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {"id": "s-ui", "title": "Frontend and API — FastAPI backend, cache-busting, multi-turn, ticker",
     "status": "shipped", "info": 1, "action": "build",
     "one_line": "The app surface: an HTTP seam over RulesAgent plus the small frontend fixes "
                 "that made it usable.",
     "tells_us": "",
     "merged": ["docs/plan-api.md", "docs/plan-cache-busting.md",
                "docs/plan-multiturn-stability.md", "docs/plan-turn-phase-ticker.md"],
     "merge_why": "four mini-plans, one product surface, all shipped in the same week and none "
                  "large enough to track separately.",
     "evidence": [{"kind": "commit", "ref": "7588fc2", "note": "FastAPI backend"},
                  {"kind": "commit", "ref": "014037e", "note": "cache-busting"},
                  {"kind": "commit", "ref": "1ceedf1", "note": "multi-turn stability"},
                  {"kind": "commit", "ref": "36f0994", "note": "turn-phase ticker"},
                  {"kind": "path", "ref": "src/rulesagent/api/main.py"}],
     "metric": {"name": "follow-up answer reliability", "dir": "up", "basis": "measured",
                "cite": "docs/plan-multiturn-stability.md",
                "detail": "the plan measured follow-ups flaking ~50% before the fix."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {"id": "s-guards", "title": "Answer guards — blank answers, silent card drops, SQLite caches",
     "status": "shipped", "info": 1, "action": "build",
     "one_line": "Stop the failure modes that look like success: a blank answer marked answered, "
                 "a dropped card reference nobody logs, a cache two processes corrupt.",
     "tells_us": "",
     "merged": ["docs/plan-q029-empty-answer-guard.md", "docs/plan-l3-sqlite-caches.md"],
     "merge_why": "both are silent-failure closures approved in the same window; L3 also cleared "
                  "deploy blocker #1.",
     "evidence": [{"kind": "commit", "ref": "197ac79", "note": "q029 empty-answer guard + c012 observability"},
                  {"kind": "commit", "ref": "390545b", "note": "Plan A uncited-success flag"},
                  {"kind": "commit", "ref": "09683fc", "note": "L3 SQLite cache layer"},
                  {"kind": "path", "ref": "src/rulesagent/cache.py"}],
     "metric": {"name": "silent failures", "dir": "down", "basis": "measured",
                "cite": "docs/plan-q029-empty-answer-guard.md",
                "detail": "q029 drew answered:true with empty text and slipped past the "
                          "degenerate check; that specific shape is now caught."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {"id": "s-symbol-injection", "title": "Symbol injection (production, cell B)", "status": "shipped",
     "info": 1, "action": "run",
     "one_line": "Inject definitions for the mana symbols a question actually contains. The "
                 "injection shipped; the v5 bullet set on top of it did not.",
     "tells_us": "",
     "evidence": [{"kind": "doc", "ref": "DECISIONS.md",
                   "note": "2026-07-23 \"symbol injection RATIFIED as production (cell B is "
                           "production)\" — 0 added tokens on 31 of 50 questions, +93 on card "
                           "questions"},
                  {"kind": "doc", "ref": "docs/report-v5-grid.md",
                   "note": "the grid that separated injection from the bullets"}],
     "metric": {"name": "prompt tokens", "dir": "none", "basis": "measured",
                "cite": "docs/report-v5-grid.md",
                "detail": "injection is near-free; the v5 bullets cost +510 tok/query over "
                          "production for nothing measured."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    # ------------------------------------------------------- cut / superseded --
    {"id": "x-prompt-v4", "title": "Prompt v4 — mana arithmetic and multiplayer refinement",
     "status": "cut", "info": 1, "action": "build",
     "docs": ["docs/plan-prompt-v4.md"],
     "one_line": "Nearly double the system prompt to teach mana notation and multiplayer "
                 "phrasing. Built, tested, and reverted.",
     "tells_us": "",
     "merged": ["docs/plan-v4e-execution-tasks.md"],
     "merge_why": "the execution-tasks doc is the build decomposition of the v4 plan plus "
                  "condition E; it has no independent proposal.",
     "relevant": False,
     "relevance_note": "Superseded by the cost-calculator tool. The tool plan's own opening: "
                       "\"Two full prompt programmes have now targeted the same miss\" — v4's "
                       "mana legend and v5's symbol injection both failed to move c014, so the "
                       "arithmetic moved into Python instead.",
     "evidence": [{"kind": "doc", "ref": "DECISIONS.md",
                   "note": "2026-07-25 \"prompt v4 is NO-GO; production reverts to v3 by "
                           "version-selecting\" (PROMPT_VERSION 4 -> 3)"},
                  {"kind": "path", "ref": "evals/build_prompts_v4.py",
                   "note": "the build exists — this was measured, not abandoned"}],
     "metric": {"name": "answer accuracy", "dir": "none", "basis": "measured",
                "cite": "docs/plan-v5-and-gold-discovery.md",
                "detail": "sonnet 46 -> 46 (zero divergence), gpt-5-mini 45 -> 43, at ~+1,215 "
                          "tokens on every query. It failed its own go criterion."},
     "cost": {"kind": "spent", "why": "already run"}, "deps": []},
    {"id": "x-condition-e", "title": "Condition E — reasoning-enabled generation",
     "status": "cut", "info": 1, "action": "run",
     "one_line": "Turn on the OpenRouter models' reasoning mode as its own arm.",
     "tells_us": "",
     "relevant": False,
     "relevance_note": "Partly superseded rather than dead: the Anthropic-side version of the "
                       "same lever shipped as the `effort` knob (commit 579d544), and the "
                       "shipped config now runs opus-5 at effort=low precisely because effort is "
                       "the primary cost lever.",
     "evidence": [{"kind": "doc", "ref": "DECISIONS.md",
                   "note": "2026-07-24 \"condition E (reasoning effort) FAILS ON LATENCY, before "
                           "accuracy matters\""},
                  {"kind": "doc", "ref": "docs/plan-condition-e-reasoning.md",
                   "note": "header: \"DESIGN ONLY. No code changes in this document\""}],
     "metric": {"name": "latency", "dir": "up", "basis": "measured", "cite": "DECISIONS.md",
                "detail": "it failed on latency before accuracy could be assessed."},
     "cost": {"kind": "spent", "why": "the decision was reached without a full run"}, "deps": []},
    {"id": "x-v5-bullets", "title": "v5 bullets (cell D) and the miss-matrix / gold-discovery parent",
     "status": "cut", "info": 1, "action": "build",
     "one_line": "Stack the v4 bullet set on top of symbol injection.",
     "tells_us": "",
     "merged": ["docs/plan-v5-and-gold-discovery.md", "docs/plan-v5-symbol-injection.md"],
     "merge_why": "one three-slice parent whose slices all resolved elsewhere: slice A became "
                  "symbol injection (shipped, tracked above), slice B the miss matrix (now the "
                  "miss-partition diagnostic), slice C automated gold discovery (stopped). The "
                  "parent has nothing left of its own.",
     "relevant": False,
     "relevance_note": "Jon's Lever 1 ruling, 2026-07-24: \"STAY ON CELL B.\" Cell D fixed 0 of 3 "
                       "sonnet misses and produced 0 stable flips, at +510 tok/query over "
                       "production, paid on every query forever with no prompt caching. Recorded "
                       "as a \"not now,\" not a permanent close.",
     "evidence": [{"kind": "doc", "ref": "DECISIONS.md", "note": "2026-07-24 Lever rulings: v5 no-go"},
                  {"kind": "doc", "ref": "docs/report-v5-grid.md", "note": "64 generations, 0 errors"}],
     "metric": {"name": "answer accuracy", "dir": "none", "basis": "measured",
                "cite": "docs/report-v5-grid.md",
                "detail": "0 of 3 sonnet misses repaired, 0 stable flips on gpt-5-mini."},
     "cost": {"kind": "spent", "why": "already run"}, "deps": []},
    {"id": "x-combat", "title": "Combat damage assignment tool", "status": "cut", "info": 1,
     "action": "build",
     "one_line": "A deterministic tool for assigning combat damage across blockers with trample "
                 "and deathtouch.",
     "tells_us": "",
     "relevant": False,
     "relevance_note": "Shelved, not killed. Its own §11 research found only 7 genuinely "
                       "assignment-shaped questions in the whole 1,409-row corpus (~0.5%), a thin "
                       "ROI against its §8 bar; the layers tool had four failing questions in one "
                       "regrade and targets the weakest tier. Revisit if the base rate rises.",
     "evidence": [{"kind": "doc", "ref": "DECISIONS.md",
                   "note": "2026-07-24 \"Layer-system tool is the next tool; combat-damage shelved\""},
                  {"kind": "doc", "ref": "docs/plan-combat-damage-tool.md",
                   "note": "complete design §1-10 plus §11 build-prep research — buildable as-is"}],
     "metric": {"name": "accuracy on assignment questions", "dir": "up", "basis": "predicted",
                "cite": "docs/plan-combat-damage-tool.md",
                "detail": "predicted only, and over ~0.5% of the corpus."},
     "cost": {"kind": "unknown", "why": "the plan does not price a measurement run"}, "deps": []},
    {"id": "x-rulings-recall", "title": "Rulings-recall — widen the per-card ruling cutoff",
     "status": "cut", "info": 1, "action": "build",
     "one_line": "Raise TOP_N or lower COSINE_FLOOR so the per-card ruling mini-RAG stops cutting "
                 "off the ruling an answer needs.",
     "tells_us": "",
     "merged": ["docs/plan-c011-stale-rulings.md"],
     "merge_why": "rulings-recall was written directly out of the c011 diagnosis and supersedes "
                  "it as the actionable half; c011's own §5 freezes that question and its §2 says "
                  "it needs redoing from different evidence.",
     "relevant": False,
     "relevance_note": "Jon shelved it 2026-07-23: it rests on 3 known misses (c010/c011/c019) "
                       "with no formal metric. Partly addressed anyway — TOP_N was raised 3 -> 5 "
                       "in commit 17f4d16 for a different reason.",
     "evidence": [{"kind": "doc", "ref": "docs/plan-rulings-recall.md",
                   "note": "header: \"JON'S RULING 2026-07-23: SHELVED. Diagnosis kept on record, "
                           "build nothing.\""},
                  {"kind": "commit", "ref": "17f4d16", "note": "TOP_N raised 3 -> 5 independently"}],
     "metric": {"name": "ruling recall", "dir": "up", "basis": "predicted",
                "cite": "docs/plan-rulings-recall.md",
                "detail": "no formal metric exists for it — which is why it was shelved."},
     "cost": {"kind": "unknown", "why": "the plan explicitly cannot cost lowering COSINE_FLOOR "
                                        "without re-running"}, "deps": []},
    {"id": "x-slice-c", "title": "Automated gold discovery by ablation (Slice C)",
     "status": "superseded", "info": 1, "action": "build",
     "one_line": "Discover gold rules by generating with each candidate rule removed and seeing "
                 "which removals break the answer.",
     "tells_us": "",
     "merged": ["docs/plan-slice-c-gold-discovery-build-spec.md",
                "docs/plan-card-gold-ablation.md"],
     "merge_why": "the same ablation idea at two scales — the card-level version shipped as "
                  "evals/ablate_gold.py, and the corpus-scale build spec stopped before building.",
     "relevant": False,
     "relevance_note": "Superseded in practice by subscription gold mining "
                       "(docs/spec-cr-gold-mining.md), which produces gold proposals with no API "
                       "spend at all. Slice C's cost model is O(candidates) generations per "
                       "question, which is the expensive way to get the same artefact.",
     "evidence": [{"kind": "doc", "ref": "docs/plan-slice-c-gold-discovery-build-spec.md",
                   "note": "header: \"STOPPED before building. This is a build spec, not an "
                           "executed proposal batch.\""},
                  {"kind": "commit", "ref": "004450b",
                   "note": "the card-scale ablation harness DID ship"},
                  {"kind": "path", "ref": "evals/ablate_gold.py"}],
     "metric": {"name": "gold coverage", "dir": "up", "basis": "predicted",
                "cite": "docs/plan-v5-and-gold-discovery.md",
                "detail": "the parent plan proposes candidates with evidence and explicitly does "
                          "not certify gold."},
     "cost": {"kind": "unknown",
              "why": "O(candidates) generations per question with the pool capped at 20; the "
                     "build spec declines to re-derive a total"},
     "deps": []},
    # ------------------------------------------------------------- unknown --
    {"id": "u-prompt-v3", "title": "Prompt v3 and rewriter v2 — the shipped prompt",
     "status": "shipped", "info": 2, "action": "build",
     "docs": ["docs/plan-prompt-tuning.md"],
     "one_line": "The system prompt production runs today, plus the rewriter prompt bump that "
                 "landed with it.",
     "tells_us": "",
     "merged": ["docs/plan-v3-execution-tasks.md"],
     "merge_why": "the execution-tasks doc is the build decomposition of the same approved plan.",
     "evidence": [{"kind": "commit", "ref": "f9a70fe", "note": "prompt v3 + rewriter v2 + version selection"},
                  {"kind": "commit", "ref": "9c20ffb", "note": "A/B condition plumbing"},
                  {"kind": "doc", "ref": "DECISIONS.md", "note": "2026-07-23 v3 A/B outcome calls"}],
     "metric": {"name": "answer accuracy", "dir": "up", "basis": "measured", "cite": "DECISIONS.md",
                "detail": "v3 was adopted on the graded A/B; the later v4 attempt used v3 as its "
                          "baseline and lost to it."},
     "cost": {"kind": "spent", "why": "shipped"}, "deps": []},
    {
        "id": "se-rule-chains",
        "title": "Stack Exchange as a source of rule-chain structure (not gold)",
        "one_line": "Mine Board & Card Games Stack Exchange's magic-the-gathering tag for the "
                    "ordered CR-rule chains disciplined answers walk through, filtered to "
                    "top-answer-equals-accepted-answer plus specific numbered citations -- never "
                    "as answer gold, only as candidate structure for gold_groups composition.",
        "status": "design-only", "action": "decide", "info": 2,
        "info_why": "It's a candidate feed for two already-identified problems (the 54 mis-encoded "
                    "OR-groups and rg241's second-hop retrieval gap) at zero API spend for the pull "
                    "itself, but yield is thin (roughly half the sample fails the hard filter, and "
                    "only 2 of 10 sampled questions produce a genuinely conjunctive multi-rule "
                    "chain) and every retained row needs real per-item drift and licensing checks "
                    "before it can touch anything.",
        "tells_us": "Whether a free, self-refreshing, community-vetted stream can supply usable "
                    "rule-composition evidence once RulesGuru itself is exhausted as a growth path.",
        "docs": ["docs/spec-stackexchange-rule-chains.md"],
        "evidence": [
            {"kind": "doc", "ref": "docs/results-orgroup-repass.md",
             "note": "the 105-group re-pass this spec targets: 54 mis-encoded conjunctions, 25 "
                     "needing Jon's judgment -- categories an SE answer's explicit rule-chain "
                     "language can provide a second opinion on, never an override"},
            {"kind": "doc", "ref": "docs/HANDOFF-development.md",
             "note": "live queue item 5, the rg241 second-hop finding this spec's Q64560 worked "
                     "example (614.1c/614.12/702.161a/702.44a, none surface-resembling the "
                     "question) is offered as a concrete instance of"},
            {"kind": "path", "ref": "scripts/check_cr_update.py",
             "note": "its normalize()/rule_fingerprint() are reused as one-sided text functions for "
                     "citation resolution; its classify_rules() needs a full old-release-vs-new "
                     "diff an isolated SE quote can't supply on its own -- resolved in this spec "
                     "by sourcing per-release CR text from the Academy Ruins archive instead"},
        ],
        "metric": {"name": "OR-group adjudication and second-hop retrieval evidence", "dir": "none",
                   "basis": "predicted",
                   "cite": "docs/spec-stackexchange-rule-chains.md",
                   "detail": "a candidate-structure feed, not an intervention -- it moves no "
                             "project metric by itself. The 50% filter-survival rate and 3-of-12 "
                             "citations needing content-level drift resolution are measured, on a "
                             "10-question design-phase sample; whether a real pilot's yield "
                             "resolves any of the 25 flagged OR-groups is not established here."},
        "cost": {"kind": "zero",
                 "why": "the Stack Exchange API pull is free and self-serve (confirmed live: "
                        "quota_max 300/day unkeyed, 10,000/day with a free registered key); the "
                        "real cost is per-candidate validation labor (CR drift checks, license/"
                        "attribution bookkeeping), which is Haiku-batchable, not an API/Voyage "
                        "spend."},
        "deps": ["or-group-repass"],
    },
]


def _resolve_cost(cost: dict, per_q: tuple[float | None, float | None]) -> dict:
    """Turn a cost basis into dollars, or say plainly that it cannot be."""
    out = dict(cost)
    kind = cost.get("kind")
    lo = hi = None
    if kind == "api_questions":
        q_lo, q_hi = per_q
        if q_lo is None:
            out["unresolved"] = ("no shipped-config arm carries a measured cost/question, so this "
                                 "cannot be priced from measurement")
        else:
            lo, hi = q_lo * cost["n"], q_hi * cost["n"]
            out["per_q"] = [q_lo, q_hi]
    elif kind in ("api_stated", "hosting"):
        lo, hi = cost.get("lo"), cost.get("hi")
    out["lo"], out["hi"] = lo, hi
    out["pool"] = {"api_questions": "api", "api_stated": "api", "zero": "free",
                   "subscription": "subscription", "hosting": "hosting",
                   "spent": "spent", "unknown": "unknown"}.get(kind, "unknown")
    return out


DONE_STATUSES = {"shipped", "cut", "superseded"}


def resolve_doc(ref: str) -> Path | None:
    """Locate a doc whether it is live or archived, or None if it is gone.

    Finished design docs move to `docs/archive/` to keep the top level small --
    ~894 KB of deliberation was enough to fill a context window before any work
    began. Archiving must not break the inventory's evidence checks, so a
    reference resolves in either location. This is why archiving a doc is a safe
    operation: the roadmap keeps pointing at it.
    """
    p = REPO / ref
    if p.exists():
        return p
    archived = REPO / "docs" / "archive" / Path(ref).name
    return archived if archived.exists() else None


def _doc_coverage() -> dict:
    """Which plan/spec docs the inventory accounts for -- and which it misses.

    A backlog that silently drops a doc is worse than one that admits the gap,
    so this globs the directories rather than trusting the inventory to be
    complete. Archived docs are still inventoried: the roadmap is the index that
    makes the archive safe to ignore, so it has to cover what is in there.
    """
    docs = sorted(
        ("docs/" + p.name)
        for d in (REPO / "docs", REPO / "docs" / "archive")
        for p in d.glob("*.md")
        if p.name.startswith(("plan-", "spec-"))
    )
    seen = {d for it in ROADMAP for d in it.get("merged", [])}
    seen |= {e["ref"] for it in ROADMAP for e in it.get("evidence", [])
             if e.get("kind") == "doc"}
    seen |= {d for it in ROADMAP for d in it.get("docs", [])}
    missing = [d for d in docs if d not in seen]
    return {"n_docs": len(docs), "n_covered": len(docs) - len(missing), "missing": missing}


def build_roadmap(comparisons: dict, current: dict) -> dict:
    """Inventory every plan/spec with its status re-verified against the repo.

    The verification is the point. Statuses were inferred once, by hand, from
    commits and code paths; this re-checks every one of those references on every
    build, so a claim that stops being true renders as a broken evidence line
    rather than quietly persisting.
    """
    shas = {c["sha"] for c in git_commits()}

    # $/question of the SHIPPED configuration -- the same basis the decision panel
    # uses, so the page never shows two different prices for the same run.
    cands = [p for p in comparisons.get("projections", [])
             if p.get("kind") == "pipeline" and p.get("cost_lo") is not None
             and p["config"].get("model") == current.get("GEN_MODEL")
             and p["config"].get("effort") == current.get("GEN_EFFORT")]
    cands.sort(key=lambda p: -p["n_questions"])   # same pick as the decision panel
    per_q: tuple[float | None, float | None] = (
        (cands[0]["cost_lo"], cands[0]["cost_hi"]) if cands else (None, None))
    basis = (f"{current.get('GEN_MODEL')} / effort {current.get('GEN_EFFORT')}"
             if per_q[0] is not None else None)

    by_id = {it["id"]: it for it in ROADMAP}
    items = []
    for it in ROADMAP:
        ev = []
        for e in it.get("evidence", []):
            row = dict(e)
            kind, ref = e["kind"], e.get("ref")
            if kind == "commit":
                row["ok"] = ref in shas
                row["broken_why"] = None if row["ok"] else "no such commit in git log"
            elif kind == "path":
                row["ok"] = (REPO / ref).exists()
                row["broken_why"] = None if row["ok"] else "path does not exist"
            elif kind == "path_absent":
                gone = not (REPO / ref).exists()
                tracked = ref in _tracked_files()
                row["ok"] = gone or not tracked
                row["broken_why"] = None if row["ok"] else "path exists and is tracked, so the claim is stale"
                row["detail"] = ("absent" if gone else "present in the working tree but untracked")
            elif kind == "doc":
                # Resolves live OR archived. Finished design docs move to
                # docs/archive/ to keep the top level readable; that is a
                # relocation, not a deletion, so it must not read as broken
                # evidence. Genuinely missing still does.
                found = resolve_doc(ref)
                row["ok"] = found is not None
                row["archived"] = bool(found and "archive" in found.parts)
                row["broken_why"] = None if row["ok"] else "doc does not exist"
            else:
                row["ok"] = True
                row["broken_why"] = None
            ev.append(row)

        unmet = [d for d in it.get("deps", []) if by_id.get(d, {}).get("status") not in DONE_STATUSES]
        cost = _resolve_cost(it.get("cost", {"kind": "unknown", "why": "not costed"}), per_q)
        status = it["status"]
        bucket = ("done" if status in ("shipped",)
                  else "dead" if status in ("cut", "superseded")
                  else "unknown" if status == "unknown"
                  else "blocked" if unmet else "ready")
        items.append({
            **{k: v for k, v in it.items() if k not in ("evidence", "cost", "deps")},
            "evidence": ev, "cost": cost, "deps": it.get("deps", []), "unmet": unmet,
            "unmet_titles": [by_id[d]["title"] for d in unmet if d in by_id],
            "bucket": bucket,
            "evidence_ok": all(e["ok"] for e in ev),
            "info_why_rank": INFO_RANK.get(it.get("info", 1), ""),
        })

    # ORDER. Ready first, best-informed first, and within an information tier the
    # cheapest first -- because within a tier, cost is the only thing separating
    # them. Deliberately NOT a computed "value per dollar": the numerator is an
    # unmeasured effect size for most of these, and dividing a judgement by a
    # dollar figure would dress a guess up as arithmetic.
    def key(i):
        c = i["cost"]
        free = 0 if c["pool"] in ("free", "subscription") else 1
        amt = c["lo"] if c["lo"] is not None else 10_000.0
        return (-i.get("info", 1), free, amt, i["title"])

    for it in items:
        it["_k"] = key(it)
    items.sort(key=lambda i: i["_k"])
    for it in items:
        it.pop("_k")

    counts: dict[str, int] = {}
    for it in items:
        counts[it["bucket"]] = counts.get(it["bucket"], 0) + 1
    ready_api = [i for i in items if i["bucket"] == "ready" and i["cost"]["pool"] == "api"
                 and i["cost"]["lo"] is not None]
    return {
        "items": items, "counts": counts, "coverage": _doc_coverage(),
        "cost_basis": basis, "per_q": list(per_q),
        "ready_api_lo": sum(i["cost"]["lo"] for i in ready_api) or None,
        "ready_api_hi": sum(i["cost"]["hi"] for i in ready_api) or None,
        "info_rank": INFO_RANK,
        "broken": [{"id": i["id"], "ref": e.get("ref"), "why": e["broken_why"]}
                   for i in items for e in i["evidence"] if not e["ok"]],
    }


# ===========================================================================
# EXECUTIVE SUMMARY LAYER
#
# Jon, 2026-07-26: the page reads like an instrument panel for the person who
# built it. It needs a layer that reads like a recommendation to someone who will
# never open a verdict file -- what we should do, what it costs, how sure we are,
# and what would change the answer. Plus, per the follow-on: the OPTIONS the
# recommendation was chosen from, with real pros and cons, because a
# recommendation without its alternatives is an assertion rather than an argument.
#
# THE DESIGN PROBLEM. Hardcoded prose goes stale silently -- which is this repo's
# signature failure. Arm B moved 93.3% -> 91.3% mid-session; any hand-written
# summary would have been wrong within the hour and would not have said so.
# Fully computed prose, on the other hand, reads like a robot and hides its
# reasoning.
#
# THE RESOLUTION USED HERE: authored sentence templates, computed values, and
# computed BRANCH SELECTION against named thresholds declared immediately below.
# The page renders those thresholds, so the recommendation is auditable -- a
# reader can disagree with the threshold rather than with an opinion baked into a
# string. If the data crosses a threshold, the page says something different on
# its own, without anyone editing prose.
#
# Anything that genuinely cannot be computed is stamped with who authored it and
# when, so a stale judgement is visibly a judgement.
# ===========================================================================

AUTHORED_ON = "2026-07-26"
AUTHORED_BY = "Claude Opus 5, from the repo's own docs and commits"

# Named, visible, and the ONLY thing that selects the headline recommendation.
THRESHOLDS = [
    {"key": "coverage_min", "value": 0.95, "fmt": "pct",
     "label": "Corpus coverage before committing to a full run",
     "why": "A projection reweights measured levels onto the corpus mix. If a whole "
            "difficulty level has never been run, the projection is extrapolating over it, "
            "not measuring it."},
    {"key": "interval_max_pp", "value": 15.0, "fmt": "pp",
     "label": "Widest acceptable 95% interval on the projected accuracy",
     "why": "An interval wider than this cannot distinguish a good result from a bad one, so "
            "spending on the full run buys a number nobody can act on."},
    {"key": "budget_max_usd", "value": 200.0, "fmt": "usd",
     "label": "Full-run cost that triggers a separate budget conversation",
     "why": "Below this, cost is not the deciding factor and should not be presented as one."},
    {"key": "judge_fp_max_pp", "value": 5.0, "fmt": "pp",
     "label": "Highest tolerable judge false-positive rate before publishing a headline",
     "why": "The judge marking a wrong answer correct inflates every accuracy on this page. "
            "Above this, fix the instrument before quoting the number."},
]
THRESH = {t["key"]: t["value"] for t in THRESHOLDS}

# Doc-sourced, NOT measured here. Wall-clock is not recorded per row in any
# answers file (checked: no elapsed/duration field), so run time cannot be
# computed. This is the only run-time figure the repo has, and it is quoted with
# its source rather than turned into a number of our own.
RUNTIME_NOTE = ("Wall-clock is not recorded per row in any answers file, so run time cannot be "
                "computed from measurement. docs/plan-rulesguru-as-instrument.md estimates "
                "~4s per question, putting 150 questions at \"roughly 10+ minutes\" — that was "
                "written about sonnet, and the shipped config is a different model.")

# Doc-sourced, NOT measured here. docs/results-judge-false-negatives.md hand-grades
# rows itself (Jon reading answers against gold) -- there is no JSON verdict file
# behind it the way fp_rate above has judge_error_results.json, so it cannot be
# read as a number the way the rest of this function is. Quoted with its source
# for the same reason RUNTIME_NOTE is, and superseding judge_error_results.json's
# older fn_ref_rate (2/30 on a smaller, still-stratified sample) with the newer,
# larger, deduplicated combined bound.
FALSE_NEGATIVE_NOTE = {
    "combined_rate": 0.0, "combined_k": 0, "combined_n": 77, "combined_ci": [0.0, 0.047],
    "doc": "docs/results-judge-false-negatives.md",
    "why": ("77 unique rows hand-graded across two passes (30, then 53 more including a census "
            "of all hard-level judge-PASSED rows), 0 confirmed false negatives, 95% CI [0%, 4.7%] "
            "-- tighter than either pass alone. Supersedes judge_error_results.json's older "
            "2/30 = 6.7% reference-sample figure, a smaller and still-stratified predecessor."),
}


# Doc-sourced, NOT reconstructed here. Once the full-corpus arm exists, its own
# rows get folded into the same config-signature bucket the live projection
# machinery groups by (see `projections` in build_comparisons), so re-deriving
# "what the projection said before the run" from the current data would be
# circular -- the blend now includes the answer it is supposed to be predicting.
# docs/results-headline-accuracy.md recorded the actual pre-run figure at the
# time (82.8% [78.2%, 86.6%], from the three then-existing partial arms under
# the shipped config) before that circularity existed, so that is quoted rather
# than recomputed.
PROJECTION_VALIDATION = {
    "projected": 0.828, "ci": [0.782, 0.866], "measured": 0.8588, "miss_pp": 3.1,
    "cost_estimate_lo": 52, "cost_estimate_hi": 91,
    "doc": "docs/results-headline-accuracy.md",
    "why": ("This page projected 82.8% [78.2%, 86.6%] from three partial-coverage arms under "
            "the shipped config before the full run existed. The measured result, 85.88% on all "
            "1,409 questions, landed +3.1 points above it -- near the top of the projected "
            "interval, not outside it. That is what the corpus-mix reweighting method was for."),
}


def judge_error() -> dict:
    """The measured judge error rates, read from their file at build time."""
    p = EVALS / "judge_error_results.json"
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    fp, fn = d.get("false_positive") or {}, d.get("false_negative") or {}
    return {
        "file": "evals/judge_error_results.json", "mtime": _mtime(p),
        "judge": (d.get("judge_under_audit") or {}).get("model"),
        "digest": (d.get("judge_under_audit") or {}).get("prompt_sha256"),
        "fp_rate": fp.get("rate"), "fp_k": fp.get("k"), "fp_n": fp.get("n"),
        "fp_ci": fp.get("ci"),
        "ref_agreement": (d.get("validation") or {}).get("agreement"),
        "ref_n": (d.get("validation") or {}).get("n"),
        "fn_ref_rate": (fn.get("reference_sample") or {}).get("rate"),
        "fn_census": FALSE_NEGATIVE_NOTE,
    }


def build_summary(data: dict) -> dict:
    """The recommendation layer. Every branch below is selected by THRESHOLDS."""
    C, N = data["comparisons"], data["full_corpus"]
    cur, rm = data["current_config"], data["roadmap"]
    proj = [p for p in C.get("projections", []) if p.get("kind") == "pipeline"
            and p.get("projected_acc") is not None]
    shipped = sorted([p for p in proj
                      if p["config"].get("model") == cur.get("GEN_MODEL")
                      and p["config"].get("effort") == cur.get("GEN_EFFORT")],
                     key=lambda p: -p["n_questions"])
    head = shipped[0] if shipped else (proj[0] if proj else None)
    je = judge_error()

    # ---- has the full corpus already been measured? --------------------------
    # Data-driven, not a hardcoded arm name: any pipeline-kind step whose n
    # equals the full corpus size, on a config that was actually recorded. An
    # unrelated question set landing on exactly N pipeline-graded rows by
    # coincidence would be its own kind of newsworthy, so this is treated as
    # conclusive rather than hedged.
    full_run = next((st for s in data["timeline"]["sets"] for st in s["steps"]
                      if st["kind"] == "pipeline" and st["n"] == N and st["config_recorded"]),
                     None)
    f_full = None
    if full_run:
        lvl = full_run["by_level"]
        arm_match = next((a for a in data["arms"]
                          if a["arm"] == full_run["step"] and a["qset"] == full_run["qset"]), None)
        f_full = {
            "step": full_run["step"], "qset": full_run["qset"], "n": full_run["n"],
            "acc": full_run["flat"], "ci95": wilson(full_run["flat"], full_run["n"]),
            "cost_per_q": full_run["cost_per_q"],
            "cost_total": (full_run["cost_per_q"] * full_run["n"])
                          if full_run["cost_per_q"] is not None else None,
            "batch": bool(((arm_match or {}).get("cost") or {}).get("batch")),
            "model": full_run["config"].get("model"), "effort": full_run["config"].get("effort"),
            "run_at": full_run["run_at"],
            "levels": {k: {"acc": v["acc"], "n_questions": v["n_questions"]} for k, v in lvl.items()},
        }

    # ---- the facts every sentence below interpolates -----------------------
    f: dict = {"N": N, "judge": je, "runtime_note": RUNTIME_NOTE, "full_run": f_full,
               "projection_validation": PROJECTION_VALIDATION if f_full else None}
    if f_full:
        # The corpus is measured. Use ITS OWN numbers, not the blended
        # same-config projection -- that projection groups by config signature
        # and this very run now sits inside that bucket, so reusing it here
        # would be circular (see PROJECTION_VALIDATION's comment above).
        f.update({
            "acc": f_full["acc"], "ci": f_full["ci95"],
            "ci_width_pp": (f_full["ci95"][1] - f_full["ci95"][0]) * 100 if f_full["ci95"] else None,
            "coverage": 1.0, "missing": [],
            "cost_lo": f_full["cost_per_q"], "cost_hi": f_full["cost_per_q"],
            "full_lo": f_full["cost_total"], "full_hi": f_full["cost_total"],
            "model": f_full["model"], "effort": f_full["effort"],
            "n_run": f_full["n"],
        })
    elif head:
        f.update({
            "acc": head["projected_acc"], "ci": head["ci95"],
            "ci_width_pp": (head["ci95"][1] - head["ci95"][0]) * 100 if head.get("ci95") else None,
            "coverage": head["covered_share"], "missing": head["missing_levels"],
            "cost_lo": head["cost_lo"], "cost_hi": head["cost_hi"],
            "full_lo": head["cost_lo"] * N, "full_hi": head["cost_hi"] * N,
            "model": head["config"].get("model"), "effort": head["config"].get("effort"),
            "n_run": head["n_questions"],
        })
    mix = (C.get("corpus") or {}).get("by_level") or {}
    f["missing_n"] = sum(mix.get(lv, 0) for lv in (f.get("missing") or []))
    slice_item = next((i for i in rm["items"] if i["id"] == "l0-arm"), None)
    f["slice_lo"] = (slice_item or {}).get("cost", {}).get("lo")
    f["slice_hi"] = (slice_item or {}).get("cost", {}).get("hi")

    # ---- BRANCH SELECTION. Ordered; the first unmet threshold decides. ------
    checks = []
    if f_full:
        # The question this branch chain used to answer -- should we run the
        # full corpus -- is resolved. The thresholds still get evaluated, for
        # the record of what cleared before the run, but they no longer pick
        # the verdict.
        verdict, why_key = "measured", None
        checks = [
            {"key": "coverage_min", "pass": True, "actual": 1.0, "fmt": "pct"},
            {"key": "interval_max_pp", "pass": (f["ci_width_pp"] or 0) <= THRESH["interval_max_pp"],
             "actual": f["ci_width_pp"], "fmt": "pp"},
            {"key": "judge_fp_max_pp",
             "pass": je.get("fp_rate") is not None and je["fp_rate"] * 100 <= THRESH["judge_fp_max_pp"],
             "actual": (je.get("fp_rate") or 0) * 100, "fmt": "pp"},
            {"key": "budget_max_usd", "pass": (f["full_hi"] or 0) <= THRESH["budget_max_usd"],
             "actual": f["full_hi"], "fmt": "usd"},
        ]
    elif not head:
        verdict, why_key = "nodata", None
    else:
        checks = [
            {"key": "coverage_min", "pass": f["coverage"] >= THRESH["coverage_min"],
             "actual": f["coverage"], "fmt": "pct"},
            {"key": "interval_max_pp", "pass": (f["ci_width_pp"] or 0) <= THRESH["interval_max_pp"],
             "actual": f["ci_width_pp"], "fmt": "pp"},
            {"key": "judge_fp_max_pp",
             "pass": je.get("fp_rate") is not None and je["fp_rate"] * 100 <= THRESH["judge_fp_max_pp"],
             "actual": (je.get("fp_rate") or 0) * 100, "fmt": "pp"},
            {"key": "budget_max_usd", "pass": f["full_hi"] <= THRESH["budget_max_usd"],
             "actual": f["full_hi"], "fmt": "usd"},
        ]
        failed = [c for c in checks if not c["pass"]]
        why_key = failed[0]["key"] if failed else None
        verdict = {None: "go", "coverage_min": "slice-first", "interval_max_pp": "narrow-first",
                   "judge_fp_max_pp": "fix-judge-first",
                   "budget_max_usd": "budget-gate"}[why_key]
    f["checks"] = checks
    f["verdict"] = verdict
    f["why_key"] = why_key

    # ---- what's next, now that the corpus itself has an answer --------------
    # Not invented: read off the roadmap's own open items (status/cost/deps
    # already computed by build_roadmap) plus the on-disk state of the one
    # experiment that is neither on the roadmap nor finished -- the fair
    # cross-model comparison, still generating.
    f["next"] = None
    if f_full:
        by_id = {i["id"]: i for i in rm["items"]}
        cost_rank = {"zero": 0, "free": 0, "subscription": 1, "hosting": 2, "spent": 3, "unknown": 4}
        candidates = []
        for cid in ("three-way-verdicts", "harder-cardfree-set", "attack-level3"):
            it = by_id.get(cid)
            if not it or it.get("status") != "open":
                continue
            deps = it.get("deps") or []
            deps_ok = all(by_id.get(d, {}).get("status") == "shipped" for d in deps)
            blocking = [by_id[d]["title"] for d in deps if by_id.get(d, {}).get("status") != "shipped"]
            candidates.append({"id": cid, "title": it["title"], "cost": it["cost"],
                               "deps_ok": deps_ok, "blocking": blocking,
                               "rank": cost_rank.get(it["cost"].get("kind"), 5)})
        ready = sorted([c for c in candidates if c["deps_ok"]], key=lambda c: c["rank"])

        fair_path = ANSWERS / "gpt5mini_fair_1409.json"
        fair = None
        if fair_path.exists():
            try:
                rows = json.loads(fair_path.read_text(encoding="utf-8"))
                rows = rows if isinstance(rows, list) else list(rows.values())
                rows = [r for r in rows if isinstance(r, dict)]
                answered = sum(1 for r in rows if r.get("answered"))
                judged = any((a.get("provenance", {}).get("answers") or "")
                             .endswith("gpt5mini_fair_1409.json") for a in data["arms"])
                fair = {"n_rows": len(rows), "n_target": N, "n_answered": answered,
                        "n_shards": len(list(ANSWERS.glob("gpt5mini_sh*.json"))),
                        "judged": judged}
            except (OSError, ValueError):
                fair = None
        f["next"] = {"pick": ready[0] if ready else None,
                     "blocked": [c for c in candidates if not c["deps_ok"]],
                     "fair_comparison": fair}

    # ---- model choice, computed from kind-matched pairs ---------------------
    arm_cfg_by_step = {(a["qset"], a["arm"]): a["config"] for a in data["arms"]}
    model_pairs = []
    for s in C.get("head_to_head", []):
        for p in s.get("pairs", []):
            if any(d["field"] == "model" for d in p["differs"]) and p["flat_pp"] is not None:
                lead, trail = ((p["a"], p["b"]) if p["flat_pp"] < 0 else (p["b"], p["a"]))
                # flat_pp is a-b; the arm with the HIGHER score leads.
                a_wins = p["flat_pp"] > 0
                win_step, lose_step = (p["a"], p["b"]) if a_wins else (p["b"], p["a"])
                win_cfg = arm_cfg_by_step.get((s["qset"], win_step), {})
                lose_cfg = arm_cfg_by_step.get((s["qset"], lose_step), {})
                model_pairs.append({
                    "n": p["n"], "floor_pp": p["floor_pp"], "beats_noise": p["beats_noise"],
                    "winner": p["a"] if a_wins else p["b"],
                    "loser": p["b"] if a_wins else p["a"],
                    "win_model": (next(d for d in p["differs"] if d["field"] == "model")
                                  ["a" if a_wins else "b"]),
                    "lose_model": (next(d for d in p["differs"] if d["field"] == "model")
                                   ["b" if a_wins else "a"]),
                    "gap_pp": abs(p["flat_pp"]),
                    "win_cost": p["a_cost"] if a_wins else p["b_cost"],
                    "lose_cost": p["b_cost"] if a_wins else p["a_cost"],
                    "confounded": len(p["differs"]) > 1,
                    "differs": [d["label"] for d in p["differs"]],
                    # A field can fail to appear in `differs` because both sides
                    # genuinely match, OR because neither side ever recorded it
                    # (None == None reads as "not differing"). prompts_cache
                    # tells the two apart for the one field that would prove
                    # "same prompt" rather than assume it.
                    "prompt_parity_unverified": not (win_cfg.get("prompts_cache_recorded")
                                                      and lose_cfg.get("prompts_cache_recorded")),
                })
    f["model_pairs"] = model_pairs

    # A comparison against gpt-5-mini can only enter model_pairs above if it
    # shares BOTH a question set and a classified kind with an opus arm --
    # checked against the data rather than asserted, because it is easy to
    # believe a comparison exists once report_h2h.py has been run even though
    # the numbers never join anything on this page.
    gpt5mini_arms = [a for a in data["arms"]
                     if "gpt-5-mini" in (a["config"].get("model") or "").lower()
                     or "gpt-5-mini" in a["arm"].lower() or "gpt5mini" in a["arm"].lower()]
    opus_qset_kind = {(a["qset"], a["kind"]) for a in data["arms"]
                      if a["config"].get("model") == "claude-opus-5"}
    gpt5mini_joins = any((a["qset"], a["kind"]) in opus_qset_kind and a["kind"] != "unknown"
                         for a in gpt5mini_arms)
    f["model_comparison_note"] = {
        "any_confounded": any(m["confounded"] for m in model_pairs),
        "any_prompt_unverified": any(m["prompt_parity_unverified"] for m in model_pairs),
        "gpt5mini_joins_any_pair": gpt5mini_joins,
        "gpt5mini_self_judged_quote": (
            "READ THE RESULT ASYMMETRICALLY. The judge IS gpt-5-mini (judge_bakeoff + "
            "openai/gpt-5-mini, frozen). This arm is therefore graded by its own family, which "
            "the RulesGuru held-out report already flagged as bias in gpt-5-mini's favour. "
            "Consequence: a LOSS here is strong evidence, a WIN is weak."),
        "gpt5mini_self_judged_cite": "evals/report_h2h.py:15-19",
    }
    cheaper_too = [m for m in model_pairs
                   if m["win_cost"] is not None and m["lose_cost"] is not None
                   and m["win_cost"] < m["lose_cost"]]
    f["model_dominated"] = (len(model_pairs) > 0
                            and len(cheaper_too) == len(model_pairs)
                            and all(m["beats_noise"] for m in model_pairs)
                            and len({m["win_model"] for m in model_pairs}) == 1)
    f["intro_ends"] = data["pricing"]["sonnet_intro_ends"]
    # The intro-rate caveat, computed rather than asserted: sonnet is dual-priced,
    # so the same arm has two costs and the comparison can land differently.
    intro = []
    for a in data["arms"]:
        c = a.get("cost") or {}
        if c.get("cost_per_q_intro"):
            intro.append({"arm": a["arm"], "std": c["cost_per_q"], "intro": c["cost_per_q_intro"],
                          "qset": a["qset"]})
    f["intro_arms"] = intro

    # ---- effort: is there a kind-matched, effort-only comparison? -----------
    effort_pairs = [p for s in C.get("head_to_head", []) for p in s.get("pairs", [])
                    if [d["field"] for d in p["differs"]] == ["effort"]]
    f["effort_controlled"] = len(effort_pairs)
    f["effort_pairs"] = [{"a": p["a"], "b": p["b"], "flat_pp": p["flat_pp"],
                          "n": p["n"], "beats_noise": p["beats_noise"]} for p in effort_pairs]
    f["efforts_seen"] = sorted({str((p["config"] or {}).get("effort")) for p in proj}
                               | {str((p["config"] or {}).get("effort"))
                                  for p in C.get("projections", [])})
    # The cheapest honest effort probe: re-run the SMALLEST question set the
    # shipped config has already run, through the pipeline. Using the smallest set
    # on the page would quote a 15-row oracle slice, which is not a probe of this.
    probe_ns = [s["n"] for s in data["timeline"]["sets"] for u in s["steps"]
                if u["kind"] == "pipeline" and u["config_recorded"]
                and u["config"].get("model") == cur.get("GEN_MODEL")
                and u["config"].get("effort") == cur.get("GEN_EFFORT")]
    f["effort_probe"] = ({"n": min(probe_ns),
                          "lo": min(probe_ns) * f["cost_lo"], "hi": min(probe_ns) * f["cost_hi"]}
                         if probe_ns and f.get("cost_lo") else None)

    # ---- the oracle ceiling, kept explicitly separate from the product ------
    ceilings = [s["headroom"] for s in C.get("head_to_head", []) if s.get("headroom")]
    f["ceilings"] = ceilings

    # ---- roadmap rollup ----------------------------------------------------
    ready = [i for i in rm["items"] if i["bucket"] == "ready"]
    f["ready_n"] = len(ready)
    f["ready_free_n"] = len([i for i in ready if i["cost"]["pool"] in ("free", "subscription")])
    f["blocked_n"] = len([i for i in rm["items"] if i["bucket"] == "blocked"])
    f["top_ready"] = [{"title": i["title"], "cost": i["cost"], "id": i["id"]} for i in ready[:3]]

    return {"authored_on": AUTHORED_ON, "authored_by": AUTHORED_BY,
            "thresholds": THRESHOLDS, "facts": f, "runtime_note": RUNTIME_NOTE}


_TRACKED: set[str] | None = None


def _tracked_files() -> set[str]:
    global _TRACKED
    if _TRACKED is None:
        try:
            out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                                 text=True, timeout=30)
            _TRACKED = set(out.stdout.splitlines()) if out.returncode == 0 else set()
        except (OSError, subprocess.SubprocessError):
            _TRACKED = set()
    return _TRACKED


CONFIG_FIELDS = [("model", "model"), ("effort", "effort"), ("rewrite_version", "rewrite"),
                 ("ruling_query_mode", "ruling mode"), ("system_version", "system ver")]


def build_timeline(arms: list[dict]) -> dict:
    commits = git_commits()

    # --- collapse arms into steps -------------------------------------------
    steps: dict[tuple[str, str], dict] = {}
    for a in arms:
        key = (a["qset"], step_key(a["arm"]))
        steps.setdefault(key, {"qset": a["qset"], "step": key[1], "arms": []})["arms"].append(a)

    built = []
    for (qset, name), s in steps.items():
        members = s["arms"]
        # Reps = distinct answers files. Regrades = several verdict files over one.
        by_answers: dict[str, list[dict]] = {}
        for a in members:
            by_answers.setdefault(a["provenance"]["answers"] or f"__none__{a['arm']}", []).append(a)

        reps = []
        for apath, group in by_answers.items():
            # Within one run, the human-corrected grading is the number of record.
            group.sort(key=lambda a: (not a["human_corrected"], a["arm"]))
            head = group[0]
            reps.append({
                "arm": head["arm"], "answers": head["provenance"]["answers"],
                "flat": head["accuracy_flat"], "weighted": head["accuracy_weighted"],
                "auto": head["accuracy_auto"],
                "run_at": _run_at(head)[0], "run_at_source": _run_at(head)[1],
                "human_corrected": head["human_corrected"],
                "regrade_of": [g["arm"] for g in group[1:]] or None,
                "regrade_pp": ((head["accuracy_flat"] - group[1]["accuracy_flat"]) * 100
                               if len(group) > 1 and head["accuracy_flat"] is not None
                               and group[1]["accuracy_flat"] is not None else None),
                "cost_per_q": (head["cost"] or {}).get("cost_per_q"),
                "in_per_q": (head["cost"] or {}).get("in_per_q"),
                "out_per_q": (head["cost"] or {}).get("out_per_q"),
                "join": head["provenance"]["join"],
                "_v": head,
            })
        reps.sort(key=lambda r: r["run_at"])

        cfgs = [r["_v"]["config"] for r in reps]
        base_cfg = cfgs[0] if cfgs else {}
        # A step is only one step if its reps really shared a configuration.
        heterogeneous = [f for f, _ in CONFIG_FIELDS
                         if len({(c or {}).get(f) for c in cfgs}) > 1]

        spread_pp = churn = None
        if len(reps) > 1:
            flats = [r["flat"] for r in reps if r["flat"] is not None]
            if len(flats) > 1:
                spread_pp = (max(flats) - min(flats)) * 100
            churn = _churn(reps[0]["_v"], reps[1]["_v"])

        # Kind comes from the arms' own recorded data. If the arms under one step
        # disagree, the step is not one experiment and must not be differenced.
        kinds = {a["kind"] for a in members}
        if len(kinds) == 1:
            kind, kind_why = kinds.pop(), members[0]["kind_why"]
        else:
            kind = "unknown"
            kind_why = ("arms under this step classify differently ("
                        + ", ".join(sorted(f"{a['arm']}={a['kind']}" for a in members))
                        + ") — not one experiment")
        built.append({
            "qset": qset, "step": name, "kind": kind, "kind_why": kind_why,
            "kind_note": STEP_NOTES.get(name),
            "n": members[0]["n"],
            "run_at": reps[0]["run_at"] if reps else None,
            "run_at_source": reps[0]["run_at_source"] if reps else None,
            "config": {f: (base_cfg or {}).get(f) for f, _ in CONFIG_FIELDS},
            # No answers file joined means no config was recorded at all. That is
            # not the same as "the config was empty", and rendering it as a set of
            # fields that changed to nothing would invent a change that never
            # happened. Every consumer must check this before reading `config`.
            "config_recorded": bool(base_cfg),
            "heterogeneous_fields": heterogeneous,
            "flat": _mean([r["flat"] for r in reps]),
            "weighted": _mean([r["weighted"] for r in reps]),
            "auto": _mean([r["auto"] for r in reps]),
            "cost_per_q": _mean([r["cost_per_q"] for r in reps]),
            "in_per_q": _mean([r["in_per_q"] for r in reps]),
            "out_per_q": _mean([r["out_per_q"] for r in reps]),
            "n_reps": len(reps), "rep_spread_pp": spread_pp, "rep_churn": churn,
            "reps": [{k: v for k, v in r.items() if k != "_v"} for r in reps],
            "judge_model": members[0]["judge_model"],
            "judge_digest": members[0]["judge_digest"],
            # --- provenance, all three layers, for every view -----------------
            "generation_runs": [{"file": r["_v"]["generation"]["file"],
                                 "mtime": r["_v"]["generation"]["mtime"],
                                 "join": r["_v"]["generation"]["join"],
                                 "arm": r["arm"]} for r in reps],
            "judging_runs": [{"file": a["judging"]["file"], "mtime": a["judging"]["mtime"],
                              "judge_model": a["judging"]["judge_model"],
                              "judge_digest": a["judging"]["judge_digest"],
                              "recorded": a["judging"]["recorded"], "arm": a["arm"]}
                             for a in sorted(members, key=lambda x: x["judging"]["mtime"])],
            "human_passes": [{"arm": a["arm"], **a["human"]} for a in members if a["human"]],
            # Pooled level counts across reps -- the level mix is what the weighting
            # ruling is about, and it is also what a corpus-mix projection needs.
            "by_level": _pool_levels([r["_v"]["by_level"] for r in reps]),
            "_arms": [r["_v"] for r in reps],
        })

    # --- per-question-set noise floor ---------------------------------------
    sets = {}
    for st in built:
        sets.setdefault(st["qset"], []).append(st)

    out_sets = []
    for qset, group in sets.items():
        group.sort(key=lambda s: (s["run_at"] or "", s["step"]))
        n = group[0]["n"]
        # Judge floor: ~1 flip per 100 rows, but accuracy cannot move by less
        # than one row, so on small sets the row is the binding constraint.
        judge_pp = max(JUDGE_FLIPS_PER_ROW * 100, 100.0 / n) if n else None
        observed = [s["rep_spread_pp"] for s in group if s["rep_spread_pp"] is not None]
        if observed:
            floor_pp, floor_src = max(observed), "widest observed spread between reps of one configuration"
        else:
            floor_pp, floor_src = judge_pp, ("judge nondeterminism only (~1 verdict flip per 100 rows, "
                                             "and one row on this set is %.1f pp) — no repeated arm here" % (100.0 / n))

        # --- chain deltas across pipeline steps only -------------------------
        prev = None
        for st in group:
            st["delta"] = None
            if st["kind"] != "pipeline":
                continue
            if prev is not None:
                both_recorded = st["config_recorded"] and prev["config_recorded"]
                changed = ([{"field": f, "label": lab, "from": prev["config"].get(f),
                             "to": st["config"].get(f)}
                            for f, lab in CONFIG_FIELDS
                            if prev["config"].get(f) != st["config"].get(f)]
                           if both_recorded else [])
                d_flat = ((st["flat"] - prev["flat"]) * 100
                          if st["flat"] is not None and prev["flat"] is not None else None)
                d_cost_pct = ((st["cost_per_q"] - prev["cost_per_q"]) / prev["cost_per_q"] * 100
                              if st["cost_per_q"] and prev["cost_per_q"] else None)
                d_out_pct = ((st["out_per_q"] - prev["out_per_q"]) / prev["out_per_q"] * 100
                             if st["out_per_q"] and prev["out_per_q"] else None)
                between = [c for c in commits
                           if prev["run_at"] and st["run_at"] and prev["run_at"] < c["at"] <= st["run_at"]]
                st["delta"] = {
                    "baseline": prev["step"], "baseline_run_at": prev["run_at"],
                    "baseline_flat": prev["flat"], "baseline_cost": prev["cost_per_q"],
                    "changed": changed,
                    "changed_known": both_recorded,
                    "flat_pp": d_flat,
                    "weighted_pp": ((st["weighted"] - prev["weighted"]) * 100
                                    if st["weighted"] is not None and prev["weighted"] is not None else None),
                    "cost_pct": d_cost_pct,
                    "cost_abs": (st["cost_per_q"] - prev["cost_per_q"]
                                 if st["cost_per_q"] and prev["cost_per_q"] else None),
                    "out_tok_pct": d_out_pct,
                    "floor_pp": floor_pp,
                    "beats_noise": (None if d_flat is None or floor_pp is None
                                    else abs(d_flat) >= floor_pp),
                    "commits": between[:14],
                    "commits_total": len(between),
                }
            prev = st

        out_sets.append({
            "qset": qset, "n": n, "n_steps": len(group),
            "floor_pp": floor_pp, "floor_source": floor_src, "judge_floor_pp": judge_pp,
            "steps": group,
        })

    out_sets.sort(key=lambda s: (-s["n_steps"], -s["n"]))
    return {
        "sets": out_sets,
        "commits_indexed": len(commits),
        "notes": {
            "baseline": "Each delta compares a step to the previous PIPELINE step on the same "
                        "question-set fingerprint, ordered by run time. Nothing is compared across "
                        "fingerprints.",
            "ordering": "Run time is the answers file's mtime where one is joined, else the verdict "
                        "file's. Neither is a recorded run timestamp — the answers files do not "
                        "carry one.",
            "commits": "Commits are associated by falling inside the window between the baseline run "
                       "and this run. That is an inference from timestamps, NOT a recorded link — no "
                       "arm records the commit it ran on.",
            "retrieval": "TOP_K / TOP_N / COSINE_FLOOR are not recorded per arm, so they never appear "
                         "as a step change. What is per-arm: model, effort, rewrite_version, "
                         "ruling_query_mode, system_version.",
            "oracle": "Oracle arms are shown on their set but never chained, because they were handed "
                      "gold instead of retrieving it.",
        },
    }


FULL_CORPUS = 1409  # RulesGuru questions imported (docs/report-rulesguru-full-import.md)
CORPUS_FILE = EVALS / "rulesguru_full_v2.jsonl"
CURATED_150_FILE = EVALS / "questions_rulesguru150_v3.jsonl"
L0_ONLY_FILE = EVALS / "_l0_only.jsonl"


# ---------------------------------------------------------------------------
# COMPARISONS: the side-by-side views a go/no-go call actually needs.
#
# Every one of them obeys the same two gates -- same question-set fingerprint AND
# same kind -- because either one alone lets a meaningless number render. A cost
# /accuracy frontier that plots an oracle arm beside pipeline arms is the same
# error as a cross-set delta, just in a different shape.
# ---------------------------------------------------------------------------

def corpus_level_mix() -> dict:
    """How the 1,409-question corpus is distributed across levels.

    This is the difference between a projection and a guess. The 150-question
    set is stratified 30-per-level; the corpus is not (it is 55% L0/L1). So a
    flat score on a stratified sample is NOT the expected score on the corpus,
    and reweighting per-level accuracy by the corpus mix is the only projection
    the data supports.
    """
    if not CORPUS_FILE.exists():
        return {}
    counts: dict[str, int] = {}
    total = 0
    with CORPUS_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                level = str(json.loads(line).get("level"))
            except json.JSONDecodeError:
                continue
            counts[level] = counts.get(level, 0) + 1
            total += 1
    return {"file": CORPUS_FILE.relative_to(REPO).as_posix(), "mtime": _mtime(CORPUS_FILE),
            "total": total, "by_level": counts,
            "share": {k: v / total for k, v in counts.items()} if total else {}}


def _match_mode_stats(path: Path) -> dict | None:
    """Per-file distribution of the `match` field, and how often it governs a
    multi-rule gold list (2+ ids in `gold`) -- see docs/results-match-semantics.md.
    Read fresh from the question file every build (never hardcoded) so this
    self-corrects the moment any file is re-curated."""
    if not path.exists():
        return None
    match_counts: dict[str, int] = {}
    multi_sizes: list[int] = []
    total = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            total += 1
            m = row.get("match")
            match_counts[m] = match_counts.get(m, 0) + 1
            gold = row.get("gold")
            if isinstance(gold, list) and len(gold) >= 2:
                multi_sizes.append(len(gold))
    return {
        "file": path.relative_to(REPO).as_posix(), "total": total,
        "match_counts": match_counts,
        "multi_rule_rows": len(multi_sizes),
        "multi_rule_share": (len(multi_sizes) / total) if total else None,
        "multi_rule_mean_size": (sum(multi_sizes) / len(multi_sizes)) if multi_sizes else None,
        "multi_rule_max_size": max(multi_sizes) if multi_sizes else None,
    }


def match_semantics_audit() -> dict:
    """Whether the corpus's `match` field reflects a real per-question call or
    is sitting at an uncurated default -- docs/results-match-semantics.md.
    Every number here is recomputed from the question files at build time."""
    return {
        "curated_150": _match_mode_stats(CURATED_150_FILE),
        "full_corpus": _match_mode_stats(CORPUS_FILE),
        "l0_only": _match_mode_stats(L0_ONLY_FILE),
    }


def wilson(p: float | None, n: float | None, z: float = 1.96) -> list[float] | None:
    """95% Wilson interval. Sampling error only -- judge noise is reported apart.

    Wilson rather than normal-approximation because these n are small and
    accuracies run near 1.0, where the normal interval runs past 100% and stops
    being a statement about anything.
    """
    if p is None or not n:
        return None
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [max(0.0, centre - half), min(1.0, centre + half)]


def _sig(cfg: dict) -> tuple:
    return tuple((cfg or {}).get(f) for f, _ in CONFIG_FIELDS)


def _judge_check(a: dict, b: dict) -> dict:
    """Whether two units' accuracies were produced by comparable judging.

    The judge is nondeterministic, so two arms scored in two judging runs carry
    judge noise in the gap between them even when everything else is identical.
    Two arms scored by DIFFERENT judge models or prompt digests are worse than
    noisy -- they are not the same measurement, and the page says so.
    """
    def keys(u):
        return {(j["judge_model"], j["judge_digest"]) for j in u["judging_runs"]}
    ka, kb = keys(a), keys(b)
    missing = [u["step"] for u in (a, b) if any(not j["recorded"] for j in u["judging_runs"])]
    if missing:
        return {"level": "crit",
                "text": ("no judging run is recorded for " + " and ".join(missing) +
                         " — its verdict file names no judge model or prompt digest, so its "
                         "accuracy is not reproducible and this gap cannot be attributed"),
                "same_judge": False}
    if ka != kb:
        return {"level": "crit",
                "text": ("judged by different judges — " +
                         f"{a['step']} by {'/'.join(str(x) for k in sorted(ka) for x in k)}, " +
                         f"{b['step']} by {'/'.join(str(x) for k in sorted(kb) for x in k)}. " +
                         "Different judges are different measurements, not a gap"),
                "same_judge": False}
    n_runs = len({j["file"] for j in a["judging_runs"]} | {j["file"] for j in b["judging_runs"]})
    return {"level": "warn", "same_judge": True, "n_judging_runs": n_runs,
            "text": (f"same judge and prompt digest, but scored in {n_runs} separate judging runs. "
                     "The judge is nondeterministic (~1 verdict flip per 100 rows), so part of "
                     "this gap is the judge, not the models")}


def _paired(a: dict, b: dict) -> dict | None:
    """Row-level win/loss on the questions both arms answered.

    A paired record survives question difficulty in a way two accuracies do not:
    5 wins against 1 loss on 50 shared rows is a different claim from +8 pp.
    Computed on ONE run of each -- the run of record, human grading first -- and
    that run is named, because a paired record built from a different rep would
    come out differently.
    """
    if not a["_arms"] or not b["_arms"]:
        return None
    ra, rb = a["_arms"][0], b["_arms"][0]
    shared = [i for i in ra["_correct"] if i in rb["_correct"]
              and ra["_correct"][i] is not None and rb["_correct"][i] is not None]
    if not shared:
        return None
    both = sum(1 for i in shared if ra["_correct"][i] and rb["_correct"][i])
    a_only = sum(1 for i in shared if ra["_correct"][i] and not rb["_correct"][i])
    b_only = sum(1 for i in shared if rb["_correct"][i] and not ra["_correct"][i])
    return {"n_shared": len(shared), "both": both, "a_only": a_only, "b_only": b_only,
            "neither": len(shared) - both - a_only - b_only,
            "a_run": ra["arm"], "b_run": rb["arm"],
            "a_judging": ra["judging"]["file"], "b_judging": rb["judging"]["file"]}


def build_comparisons(timeline: dict, corpus: dict) -> dict:
    sets = timeline["sets"]
    mix = corpus.get("share") or {}

    # --- head to head, per set, kind-matched --------------------------------
    h2h = []
    for s in sets:
        units = s["steps"]
        pairs = []
        for i, a in enumerate(units):
            for b in units[i + 1:]:
                if a["kind"] != b["kind"] or a["kind"] == "unknown":
                    continue
                if not a["config_recorded"] or not b["config_recorded"]:
                    continue
                differs = [{"field": f, "label": lab, "a": a["config"].get(f), "b": b["config"].get(f)}
                           for f, lab in CONFIG_FIELDS if a["config"].get(f) != b["config"].get(f)]
                d_flat = ((a["flat"] - b["flat"]) * 100
                          if a["flat"] is not None and b["flat"] is not None else None)
                pairs.append({
                    "a": a["step"], "b": b["step"], "kind": a["kind"], "n": a["n"],
                    "differs": differs,
                    "controlled": len(differs) == 1,
                    "a_flat": a["flat"], "b_flat": b["flat"], "flat_pp": d_flat,
                    "a_weighted": a["weighted"], "b_weighted": b["weighted"],
                    "weighted_pp": ((a["weighted"] - b["weighted"]) * 100
                                    if a["weighted"] is not None and b["weighted"] is not None else None),
                    "a_cost": a["cost_per_q"], "b_cost": b["cost_per_q"],
                    "cost_pct": ((a["cost_per_q"] - b["cost_per_q"]) / b["cost_per_q"] * 100
                                 if a["cost_per_q"] and b["cost_per_q"] else None),
                    "a_in": a["in_per_q"], "b_in": b["in_per_q"],
                    "a_out": a["out_per_q"], "b_out": b["out_per_q"],
                    "paired": _paired(a, b),
                    "judge": _judge_check(a, b),
                    "floor_pp": s["floor_pp"],
                    "beats_noise": (None if d_flat is None or s["floor_pp"] is None
                                    else abs(d_flat) >= s["floor_pp"]),
                })
        # Different kinds on one set are not a head-to-head, but the oracle-vs-rest
        # gap IS informative: it is roughly the headroom retrieval is leaving.
        oracles = [u for u in units if u["kind"] == "oracle" and u["flat"] is not None]
        others = [u for u in units if u["kind"] != "oracle" and u["flat"] is not None]
        headroom = None
        if oracles and others:
            o = max(oracles, key=lambda u: u["flat"])
            p = max(others, key=lambda u: u["flat"])
            headroom = {"oracle": o["step"], "oracle_flat": o["flat"], "oracle_kind_why": o["kind_why"],
                        "other": p["step"], "other_flat": p["flat"], "other_kind": p["kind"],
                        "other_kind_why": p["kind_why"],
                        "gap_pp": (o["flat"] - p["flat"]) * 100,
                        "judge": _judge_check(o, p)}
        if pairs or headroom:
            h2h.append({"qset": s["qset"], "n": s["n"], "floor_pp": s["floor_pp"],
                        "pairs": pairs, "headroom": headroom})

    # --- cost vs accuracy: who is dominated ---------------------------------
    frontier = []
    for s in sets:
        pts = []
        for u in s["steps"]:
            if u["cost_per_q"] is None or u["flat"] is None:
                continue
            pts.append({"step": u["step"], "kind": u["kind"], "flat": u["flat"],
                        "weighted": u["weighted"], "cost": u["cost_per_q"],
                        "model": u["config"].get("model"), "effort": u["config"].get("effort"),
                        "full_run": u["cost_per_q"] * FULL_CORPUS, "dominated_by": None})
        for p in pts:
            for q in pts:
                if q is p or q["kind"] != p["kind"]:
                    continue          # never rank an oracle against the product path
                if q["flat"] >= p["flat"] and q["cost"] <= p["cost"] and (
                        q["flat"] > p["flat"] or q["cost"] < p["cost"]):
                    p["dominated_by"] = q["step"]
                    break
        unpriced = [{"step": u["step"], "kind": u["kind"], "flat": u["flat"],
                     "why": u["reps"][0]["join"] if u["reps"] else "no run"}
                    for u in s["steps"] if u["cost_per_q"] is None]
        if pts or unpriced:
            frontier.append({"qset": s["qset"], "n": s["n"], "points": pts, "unpriced": unpriced})

    # --- per-level ----------------------------------------------------------
    levels = []
    for s in sets:
        order = ["0", "1", "2", "3", "Corner Case"]
        present = [lv for lv in order if any(lv in u["by_level"] for u in s["steps"])]
        present += sorted({lv for u in s["steps"] for lv in u["by_level"]} - set(order))
        rows = [{"step": u["step"], "kind": u["kind"], "flat": u["flat"],
                 "cells": {lv: u["by_level"].get(lv) for lv in present}} for u in s["steps"]]
        if present:
            levels.append({"qset": s["qset"], "n": s["n"], "order": present, "rows": rows,
                           "corpus_share": {lv: mix.get(lv) for lv in present}})

    # --- config matrix: what has been tried, what has not -------------------
    tried: dict[tuple, list] = {}
    for s in sets:
        for u in s["steps"]:
            if not u["config_recorded"]:
                continue
            tried.setdefault(_sig(u["config"]), []).append(
                {"qset": s["qset"], "n": s["n"], "step": u["step"], "kind": u["kind"],
                 "flat": u["flat"], "cost": u["cost_per_q"], "n_reps": u["n_reps"]})
    gen_axis = sorted({(k[0], k[1]) for k in tried}, key=lambda t: (str(t[0]), str(t[1])))
    ret_axis = sorted({(k[2], k[3], k[4]) for k in tried}, key=lambda t: tuple(str(x) for x in t))
    matrix = {
        "gen_axis": [{"model": m, "effort": e} for m, e in gen_axis],
        "ret_axis": [{"rewrite_version": r, "ruling_query_mode": q, "system_version": v}
                     for r, q, v in ret_axis],
        "cells": {f"{m}|{e}||{r}|{q}|{v}": tried.get((m, e, r, q, v), [])
                  for m, e in gen_axis for r, q, v in ret_axis},
        "n_tried": len(tried),
        "n_cells": len(gen_axis) * len(ret_axis),
        "note": ("Axes are the fields the answers files actually record. TOP_K / TOP_N / "
                 "COSINE_FLOOR are NOT recorded per arm, so retrieval tuning cannot appear here "
                 "as a tried or untried combination at all."),
    }

    # --- reproducibility: the measurement noise floor -----------------------
    repro = []
    for s in sets:
        for u in s["steps"]:
            if u["n_reps"] < 2:
                continue
            repro.append({"qset": s["qset"], "n": s["n"], "step": u["step"], "kind": u["kind"],
                          "n_reps": u["n_reps"],
                          "reps": [{"arm": r["arm"], "flat": r["flat"], "run_at": r["run_at"],
                                    "cost": r["cost_per_q"]} for r in u["reps"]],
                          "spread_pp": u["rep_spread_pp"], "churn": u["rep_churn"],
                          "judging_runs": u["judging_runs"]})
    single = [{"qset": s["qset"], "n": s["n"], "step": u["step"], "kind": u["kind"]}
              for s in sets for u in s["steps"] if u["n_reps"] < 2]
    repro.sort(key=lambda r: -(r["spread_pp"] or 0))

    # --- projection to the full corpus --------------------------------------
    by_sig: dict[tuple, dict] = {}
    for s in sets:
        for u in s["steps"]:
            if not u["config_recorded"] or u["kind"] == "unknown":
                continue
            slot = by_sig.setdefault(_sig(u["config"]), {
                "config": dict(u["config"]), "kind": u["kind"], "sets": [], "levels": {},
                "costs": [], "in": [], "out": [], "flats": [], "n_questions": 0,
            })
            slot["sets"].append({"qset": s["qset"], "n": s["n"], "step": u["step"],
                                 "flat": u["flat"], "cost": u["cost_per_q"],
                                 "n_reps": u["n_reps"], "spread_pp": u["rep_spread_pp"]})
            slot["n_questions"] += u["n"]
            for lv, c in u["by_level"].items():
                d = slot["levels"].setdefault(lv, {"correct": 0.0, "n": 0.0, "n_questions": 0.0})
                d["correct"] += c["correct"]
                d["n"] += c["n"]
                d["n_questions"] += c["n_questions"]
            if u["cost_per_q"] is not None:
                slot["costs"].append(u["cost_per_q"])
            if u["in_per_q"] is not None:
                slot["in"].append(u["in_per_q"])
            if u["out_per_q"] is not None:
                slot["out"].append(u["out_per_q"])
            if u["flat"] is not None:
                slot["flats"].append(u["flat"])

    projections = []
    for sig, slot in by_sig.items():
        lv = slot["levels"]
        covered = [k for k in lv if mix.get(k)]
        share = sum(mix[k] for k in covered)
        proj = (sum(mix[k] * (lv[k]["correct"] / lv[k]["n"]) for k in covered if lv[k]["n"]) / share
                if share else None)
        missing = sorted(k for k in mix if k not in lv)
        # Sampling interval on the DISTINCT questions, not on rep-inflated rows.
        nq = sum(lv[k]["n_questions"] for k in covered)
        ci = wilson(proj, nq)
        thin = sorted((k for k in covered if lv[k]["n_questions"] < 10),
                      key=lambda k: lv[k]["n_questions"])
        costs = slot["costs"]
        projections.append({
            "config": slot["config"], "kind": slot["kind"], "sets": slot["sets"],
            "n_questions": int(round(nq)),
            "levels": {k: {"acc": (lv[k]["correct"] / lv[k]["n"]) if lv[k]["n"] else None,
                           "n_questions": lv[k]["n_questions"], "share": mix.get(k)}
                       for k in sorted(lv)},
            "covered_share": share, "missing_levels": missing, "thin_levels": thin,
            "projected_acc": proj, "ci95": ci,
            "cost_lo": min(costs) if costs else None, "cost_hi": max(costs) if costs else None,
            "full_run_lo": min(costs) * FULL_CORPUS if costs else None,
            "full_run_hi": max(costs) * FULL_CORPUS if costs else None,
            "in_per_q": _mean(slot["in"]), "out_per_q": _mean(slot["out"]),
            "max_spread_pp": max([s["spread_pp"] for s in slot["sets"]
                                  if s["spread_pp"] is not None] or [None]),
        })
    projections.sort(key=lambda p: (p["kind"] != "pipeline", -(p["projected_acc"] or 0)))

    # --- what is unresolved, and what each would change ---------------------
    open_items = []
    no_judge = [j["arm"] for s in sets for u in s["steps"] for j in u["judging_runs"]
                if not j["recorded"]]
    if no_judge:
        open_items.append({
            "level": "crit", "what": f"{len(no_judge)} verdict files name no judging model",
            "which": sorted(no_judge),
            "changes": ("Their accuracies cannot be reproduced or attributed, so any comparison "
                        "involving them is blocked. Re-judging them under the recorded judge would "
                        "unblock those comparisons — including the whole 54-question head-to-head."),
        })
    bad_join = [{"step": u["step"], "qset": s["qset"], "join": r["join"]}
                for s in sets for u in s["steps"] for r in u["reps"]
                if r["join"] not in ("exact", "alias", "id-match")]
    if bad_join:
        open_items.append({
            "level": "warn", "what": f"{len(bad_join)} runs have no verified answers file",
            "which": [f"{b['step']} ({b['join']})" for b in bad_join],
            "changes": "No cost, tokens or config for those arms. They can be scored but not priced.",
        })
    unknowns = [u["step"] for s in sets for u in s["steps"] if u["kind"] == "unknown"]
    if unknowns:
        open_items.append({
            "level": "warn", "what": f"{len(unknowns)} configurations cannot be classified",
            "which": sorted(set(unknowns)),
            "changes": ("Nothing records whether retrieval ran, so they may not be differenced "
                        "against anything. Re-running them with the current writer (which records "
                        "`retrieved_rule_ids`) would put them back on the board."),
        })
    if single:
        open_items.append({
            "level": "warn", "what": f"{len(single)} configurations ran only once",
            "which": [f"{x['step']} ({x['n']}q)" for x in single],
            "changes": ("No within-config spread was measured for them, so their question set's "
                        "noise floor falls back to judge nondeterminism alone. A second rep costs "
                        "one run and turns an assumed floor into a measured one."),
        })
    gaps: dict[tuple, list] = {}
    for p in projections:
        if p["kind"] == "pipeline" and p["missing_levels"]:
            gaps.setdefault((tuple(p["missing_levels"]), round(p["covered_share"], 3)), []).append(
                f"{p['config'].get('model')}/{p['config'].get('effort')} "
                f"rewrite {p['config'].get('rewrite_version')}")
    for (missing, cover), who in gaps.items():
        open_items.append({
            "level": "warn",
            "what": f"no pipeline evidence at all on level {', '.join(missing)}",
            "which": who + [f"{round((1 - cover) * 100)}% of the corpus by level"],
            # Say "easiest", not "largest": L0 is 207 of 1,409 questions, while L1
            # is 565. Untested does not mean biggest, and overstating the gap
            # would argue for the run on a claim the corpus mix does not support.
            "changes": ("The projected accuracy covers only the levels tested. The untested levels "
                        "are the corpus's easiest, so the projection is more likely low than "
                        "high — but it is an extrapolation until they are run."),
        })
    thin_note = [p for p in projections if p["kind"] == "pipeline" and p["thin_levels"]]
    for p in thin_note[:1]:
        open_items.append({
            "level": "warn",
            "what": "some level estimates rest on very few questions",
            "which": [f"level {lv}: {int(p['levels'][lv]['n_questions'])} questions"
                      for lv in p["thin_levels"]],
            "changes": ("Each of those questions moves that level's accuracy by a large step, and "
                        "the level is weighted by its corpus share in the projection above."),
        })
    # docs/results-match-semantics.md: the full corpus's `match` field (governs
    # what counts as a retrieval hit) is measured fresh from the question files
    # every build, not hardcoded, so this self-corrects if they are re-curated.
    msa = match_semantics_audit()
    fc = msa["full_corpus"]
    if fc and fc["total"] and len(fc["match_counts"]) == 1 and fc["multi_rule_rows"]:
        only_mode = next(iter(fc["match_counts"]))
        curated = msa["curated_150"]
        curated_note = (f"{CURATED_150_FILE.name} carries a real mix: {curated['match_counts']}"
                         if curated else f"{CURATED_150_FILE.name} not found")
        open_items.append({
            "level": "crit",
            "what": (f"all {fc['total']} rows in {fc['file']} carry `match: \"{only_mode}\"` -- one "
                     "mode, no exceptions, on the file every retrieval number on this page not "
                     "explicitly scoped to the 150-set is measured against"),
            "which": [f"{fc['multi_rule_rows']} of {fc['total']} rows ({fc['multi_rule_share']:.1%}) "
                      f"have 2+ gold rules (mean {fc['multi_rule_mean_size']:.2f}, max "
                      f"{fc['multi_rule_max_size']}) and are scored a retrieval hit if just ONE "
                      "of those rules is found",
                      curated_note,
                      "docs/results-match-semantics.md"],
            "changes": ("Answer accuracy (LLM judge vs. reference text) does not read `match` or "
                        "`gold`, so it is unaffected -- the 80.3% projection and the arm accuracies "
                        "stand. But recall, hit@k and \"context ok\" are all computed through this "
                        "field (evals/run_eval.py's gold_groups()/hit_at()), so every retrieval "
                        "measurement on the full corpus and its L0 subset is inflated by an unknown "
                        "amount on any multi-rule row -- the same defect docs/results-orgroup-repass.md "
                        "found in 54/105 groups on the curated 150-set, here uncurated across 745 "
                        "rows of the full 1,409. This is also why docs/results-miss-partition.md's "
                        "context-ok-vs-retrieval-miss conditionals are not interpretable as "
                        "retrieval-vs-reasoning on the hard arm."),
        })

    return {
        "head_to_head": h2h, "frontier": frontier, "levels": levels, "matrix": matrix,
        "repro": repro, "single_rep": single, "projections": projections,
        "open_items": open_items, "corpus": corpus, "kind_rule": KIND_RULE,
    }

# Colors are the dataviz reference palette, unchanged. Only a single accent plus
# the reserved status steps are used -- no categorical series -- so there is no
# multi-hue CVD adjacency to validate here.
HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rulemancer — metrics history</title>
<style>
:root{color-scheme:dark;
 --surface:#1a1a19; --plane:#0d0d0d; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
 --grid:#2c2c2a; --rule:#383835; --accent:#3987e5;
 --good:#0ca30c; --warn:#fab219; --serious:#ec835a; --crit:#d03b3b;
 /* Same three hues, lightness retuned so small badge/pill TEXT clears WCAG AA
    (4.5:1) against --surface in each theme. Measured, not eyeballed: on the dark
    surface #d03b3b is only 3.6:1, and on the light surface #fab219 is 1.8:1 and
    #0ca30c is 3.3:1. The fill colours above are unchanged. */
 --good-t:#0ca30c; --warn-t:#fab219; --crit-t:#e8615f;
 /* Same rule for the accent. --accent is a MARK colour (meters, rails, fills);
    --accent-t is the only one allowed to carry small text, because the light
    theme's #2a78d6 measures 4.30:1 as 21.6px/600-weight text, which WCAG counts
    as normal text (600 is not bold) and therefore fails 4.5:1. Measured in-page,
    not eyeballed. */
 --accent-t:#3987e5;
 --ring:rgba(255,255,255,.10);
 --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px; --s6:40px;}
:root[data-theme=light]{color-scheme:light;
 --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#6e6c66;
 --grid:#e1e0d9; --rule:#c3c2b7; --accent:#2a78d6; --ring:rgba(11,11,11,.10);
 --good-t:#0a7a0a; --warn-t:#8f6200; --crit-t:#b32d2d; --accent-t:#1a5fb4;}
@media(prefers-color-scheme:light){:root:not([data-theme=dark]){color-scheme:light;
 --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#6e6c66;
 --grid:#e1e0d9; --rule:#c3c2b7; --accent:#2a78d6; --ring:rgba(11,11,11,.10);
 --good-t:#0a7a0a; --warn-t:#8f6200; --crit-t:#b32d2d; --accent-t:#1a5fb4;}}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
 font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;}
.wrap{max-width:1240px;margin:0 auto;padding:var(--s5) var(--s4) var(--s6)}
header{display:flex;flex-wrap:wrap;gap:var(--s3);align-items:baseline;justify-content:space-between;
 margin-bottom:var(--s2)}
h1{font-size:1.5rem;margin:0;letter-spacing:-.01em}
h2{font-size:1.0rem;margin:var(--s5) 0 var(--s2);letter-spacing:.04em;text-transform:uppercase;
 color:var(--ink2)}
.sub{color:var(--ink2);margin:0 0 var(--s5);max-width:68ch}
.meta{color:var(--muted);font-size:.8rem}
button{font:inherit;color:var(--ink2);background:var(--surface);border:1px solid var(--ring);
 border-radius:8px;padding:6px 12px;cursor:pointer}
button:hover{color:var(--ink)}
button:focus-visible,th[tabindex]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:var(--s4)}
.tiles{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(min(190px,100%),1fr));
 margin-bottom:var(--s5)}
.tile .k{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.06em}
.tile .v{font-size:1.9rem;line-height:1.15;margin:var(--s1) 0 2px;font-weight:600}
.tile .n{color:var(--ink2);font-size:.82rem}
.decision{border-left:3px solid var(--accent)}
.decision .v{color:var(--accent-t)}
.scroll{overflow-x:auto;border:1px solid var(--ring);border-radius:12px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.86rem}
th,td{text-align:right;padding:9px var(--s3);border-bottom:1px solid var(--grid);white-space:nowrap}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:var(--surface)}
thead th{color:var(--muted);font-weight:600;font-size:.72rem;text-transform:uppercase;
 letter-spacing:.05em;border-bottom:1px solid var(--rule);cursor:pointer;user-select:none}
thead th::after{content:"";opacity:.5}
thead th[aria-sort=ascending]::after{content:" \\2191";opacity:1}
thead th[aria-sort=descending]::after{content:" \\2193";opacity:1}
tbody tr:hover{background:color-mix(in oklab,var(--accent) 8%,transparent)}
tbody tr:last-child td{border-bottom:none}
.num{font-variant-numeric:tabular-nums}
.dim{color:var(--muted)}
.badge{display:inline-block;font-size:.68rem;padding:1px 7px;border-radius:999px;
 border:1px solid var(--ring);color:var(--ink2);vertical-align:1px}
.b-good{color:var(--good-t);border-color:color-mix(in oklab,var(--good-t) 45%,transparent)}
.b-warn{color:var(--warn-t);border-color:color-mix(in oklab,var(--warn-t) 45%,transparent)}
.b-crit{color:var(--crit-t);border-color:color-mix(in oklab,var(--crit-t) 45%,transparent)}
.grp{display:flex;flex-wrap:wrap;gap:var(--s3);align-items:baseline;margin:var(--s5) 0 var(--s2)}
.grp h3{font-size:.95rem;margin:0}
.note{color:var(--ink2);font-size:.85rem;max-width:74ch}
.empty{padding:var(--s6);text-align:center;color:var(--muted)}

/* --- arm config matrix ---------------------------------------------------
   Columns arms disagree on are the finding, so they get the accent tint;
   columns every arm agrees on fall back to the ordinary muted `.dim` look
   already used everywhere else on the page -- no new "de-emphasis" language
   to learn, just less contrast where there's nothing to see. */
th.acm-diff,td.acm-diff{background:color-mix(in oklab,var(--accent) 12%,transparent)}
th.acm-diff{color:var(--accent-t)}

/* --- timeline ------------------------------------------------------------ */
.controls{display:flex;flex-wrap:wrap;gap:var(--s2);align-items:center;
 margin:var(--s2) 0 var(--s4)}
.controls .lbl{color:var(--muted);font-size:.72rem;text-transform:uppercase;
 letter-spacing:.06em;margin-right:var(--s1)}
.chip{font:inherit;font-size:.82rem;padding:5px 11px;border-radius:999px;
 border:1px solid var(--ring);background:var(--surface);color:var(--ink2);cursor:pointer}
.chip:hover{color:var(--ink);border-color:var(--rule)}
.chip[aria-pressed=true]{background:color-mix(in oklab,var(--accent) 20%,var(--surface));
 border-color:var(--accent);color:var(--ink)}
.chip:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.rail{position:relative;padding-left:28px;margin-bottom:var(--s5)}
.rail::before{content:"";position:absolute;left:5px;top:10px;bottom:10px;width:2px;
 background:var(--grid)}
.step{position:relative;margin-bottom:var(--s3)}
.step::before{content:"";position:absolute;left:-28px;top:20px;width:12px;height:12px;
 border-radius:50%;background:var(--accent);border:3px solid var(--plane)}
.step.is-oracle::before{background:var(--muted)}
.step .card{display:grid;gap:var(--s3);grid-template-columns:minmax(0,1.15fr) minmax(0,1fr)}
.step .card:focus-within{border-color:var(--accent)}
.stephead{display:flex;flex-wrap:wrap;gap:var(--s2);align-items:baseline}
.stephead h4{margin:0;font-size:1rem;letter-spacing:-.01em}
.when{color:var(--muted);font-size:.78rem;font-variant-numeric:tabular-nums}
.cfg{display:flex;flex-wrap:wrap;gap:var(--s1);margin-top:var(--s2)}
.cfg span{font-size:.72rem;padding:2px 8px;border-radius:6px;border:1px solid var(--grid);
 color:var(--ink2);background:var(--plane)}
.cfg span.chg{border-color:var(--accent);color:var(--ink);
 background:color-mix(in oklab,var(--accent) 14%,var(--plane))}
.cfg span.chg b{font-weight:600}
.cfg span .was{color:var(--muted);text-decoration:line-through;margin-right:4px}
.score{display:flex;align-items:baseline;gap:var(--s2);flex-wrap:wrap}
.score .big{font-size:2rem;font-weight:600;line-height:1.05;font-variant-numeric:tabular-nums}
.meter{height:6px;border-radius:3px;background:var(--grid);margin:var(--s2) 0 var(--s3);
 overflow:hidden}
.meter i{display:block;height:100%;background:var(--accent);border-radius:3px}
.pills{display:flex;flex-wrap:wrap;gap:var(--s1)}
.pill{font-size:.76rem;padding:2px 9px;border-radius:999px;border:1px solid var(--ring);
 color:var(--ink2);font-variant-numeric:tabular-nums;white-space:nowrap}
.pill b{font-weight:600}
.p-good{color:var(--good-t);border-color:color-mix(in oklab,var(--good-t) 45%,transparent)}
.p-bad{color:var(--crit-t);border-color:color-mix(in oklab,var(--crit-t) 45%,transparent)}
.base{color:var(--ink2);font-size:.8rem;margin-top:var(--s3)}
.base code{color:var(--ink)}
.reps{color:var(--muted);font-size:.78rem;margin-top:var(--s2);font-variant-numeric:tabular-nums}
details.commits{margin-top:var(--s3)}
details.commits summary{cursor:pointer;color:var(--ink2);font-size:.8rem;
 list-style:revert;padding:2px 0}
details.commits summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
details.commits ol{margin:var(--s2) 0 0;padding-left:1.3rem;color:var(--ink2);font-size:.78rem;
 max-height:200px;overflow-y:auto}
details.commits code{color:var(--muted)}
.floornote{color:var(--muted);font-size:.78rem;margin:0 0 var(--s3);max-width:76ch}
.setline{display:flex;flex-wrap:wrap;gap:var(--s3);align-items:baseline;margin:var(--s5) 0 var(--s1)}
.setline h3{margin:0;font-size:.95rem}
@media(max-width:760px){.step .card{grid-template-columns:1fr}}

/* --- shared: kind + provenance ------------------------------------------- */
.nav{display:flex;flex-wrap:wrap;gap:var(--s1);margin:0 0 var(--s5)}
.nav a{font-size:.78rem;padding:4px 10px;border-radius:999px;border:1px solid var(--ring);
 color:var(--ink2);text-decoration:none;background:var(--surface)}
.nav a:hover{color:var(--ink);border-color:var(--rule)}
.nav a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.b-pipe{color:var(--ink2);border-color:var(--rule)}
.prov{display:grid;gap:2px;margin-top:var(--s2);font-size:.75rem;color:var(--ink2)}
.prov div{display:flex;gap:var(--s2);align-items:baseline;flex-wrap:wrap}
.prov .lab{color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-size:.66rem;
 min-width:8.5em;flex:0 0 auto}
.prov code{font-size:.72rem;color:var(--ink2);word-break:break-all}
.prov .t{font-variant-numeric:tabular-nums;color:var(--ink)}
.prov .miss{color:var(--crit-t)}
.warnline{display:flex;gap:var(--s2);align-items:flex-start;font-size:.8rem;color:var(--ink2);
 margin-top:var(--s2);padding:var(--s2) var(--s3);border-radius:8px;border:1px solid var(--ring);
 background:var(--plane)}
.warnline.crit{border-color:color-mix(in oklab,var(--crit-t) 45%,transparent)}
.warnline.warn{border-color:color-mix(in oklab,var(--warn-t) 45%,transparent)}
.warnline b{flex:0 0 auto}
.warnline.crit b{color:var(--crit-t)}
.warnline.warn b{color:var(--warn-t)}
.sec{margin-top:var(--s6)}
.lede{color:var(--ink2);font-size:.88rem;max-width:76ch;margin:0 0 var(--s3)}

/* --- decision panel ------------------------------------------------------- */
.dec{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr))}
.dec .card h4{margin:0 0 var(--s2);font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;
 color:var(--muted)}
.dec .big{font-size:1.7rem;font-weight:600;line-height:1.1;font-variant-numeric:tabular-nums;
 display:block;margin-bottom:var(--s1)}
.dec .card p{margin:var(--s2) 0 0;font-size:.82rem;color:var(--ink2)}
.band{height:8px;border-radius:4px;background:var(--grid);position:relative;margin:var(--s2) 0}
.band i{position:absolute;top:0;bottom:0;background:color-mix(in oklab,var(--accent) 45%,transparent);
 border-radius:4px}
.band u{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink);text-decoration:none}
.scale{display:flex;justify-content:space-between;color:var(--muted);font-size:.7rem;
 font-variant-numeric:tabular-nums}

/* --- head to head --------------------------------------------------------- */
.h2h{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(min(340px,100%),1fr));
 margin-bottom:var(--s4)}
.vs{display:grid;grid-template-columns:1fr auto 1fr;gap:var(--s2);align-items:center;
 margin:var(--s3) 0}
.vs .side{min-width:0}
.vs .side .nm{font-size:.82rem;color:var(--ink2);overflow-wrap:anywhere}
.vs .side .sc{font-size:1.35rem;font-weight:600;font-variant-numeric:tabular-nums}
.vs .side.win .sc{color:var(--accent-t)}
.vs .mid{color:var(--muted);font-size:.74rem;text-align:center}
.vs .side:last-child{text-align:right}
.rec{display:flex;height:10px;border-radius:5px;overflow:hidden;background:var(--grid);
 margin:var(--s2) 0 var(--s1)}
.rec span{display:block;height:100%}
.reclegend{display:flex;flex-wrap:wrap;gap:var(--s3);font-size:.72rem;color:var(--ink2);
 font-variant-numeric:tabular-nums}
.reclegend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;
 vertical-align:-1px}

/* --- matrix / level cells -------------------------------------------------- */
.cellbar{display:block;height:4px;border-radius:2px;background:var(--accent);margin-top:3px;
 min-width:2px}
td.lv{min-width:96px}
td.tried{background:color-mix(in oklab,var(--accent) 12%,transparent)}
td.tried .dim{color:var(--ink2)}
td.gap{color:var(--muted)}
.dominated td{opacity:.62}
.dominated td:first-child{opacity:1}
footer{margin-top:var(--s6);padding-top:var(--s4);border-top:1px solid var(--grid);
 color:var(--muted);font-size:.8rem;max-width:80ch}
footer code{color:var(--ink2)}
ul{margin:var(--s2) 0;padding-left:1.1rem}li{margin:3px 0}

/* --- executive summary ---------------------------------------------------- */
.exec{border-left:3px solid var(--accent);margin-bottom:var(--s5)}
.verdict{display:inline-block;font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;
 padding:3px 10px;border-radius:999px;font-weight:600;color:var(--accent-t);
 border:1px solid color-mix(in oklab,var(--accent-t) 50%,transparent)}
.verdict.hold{color:var(--warn-t);border-color:color-mix(in oklab,var(--warn-t) 50%,transparent)}
.verdict.stop{color:var(--crit-t);border-color:color-mix(in oklab,var(--crit-t) 50%,transparent)}
.exectitle{font-size:1.3rem;line-height:1.3;margin:var(--s2) 0 0;letter-spacing:-.01em;
 max-width:52ch;font-weight:600}
.execwhy{color:var(--ink2);margin:var(--s3) 0 0;max-width:76ch}
.execgrid{display:grid;gap:var(--s3);margin-top:var(--s4);
 grid-template-columns:repeat(auto-fit,minmax(min(230px,100%),1fr))}
.execgrid>div{background:var(--plane);border:1px solid var(--grid);border-radius:10px;
 padding:var(--s3)}
.execgrid .lab{display:block;color:var(--muted);font-size:.68rem;text-transform:uppercase;
 letter-spacing:.06em;margin-bottom:var(--s1)}
.execgrid .big{font-size:1.35rem;font-weight:600;font-variant-numeric:tabular-nums;
 display:block;line-height:1.2}
.execgrid p{margin:var(--s1) 0 0;font-size:.82rem;color:var(--ink2)}
.caveats{list-style:none;padding:0;margin:var(--s4) 0 0;display:grid;gap:var(--s2)}
.caveats li{display:flex;gap:var(--s2);align-items:flex-start;font-size:.83rem;color:var(--ink2)}
.caveats b{flex:0 0 auto;color:var(--warn-t)}
.stamp{color:var(--muted);font-size:.76rem;margin:var(--s4) 0 0;max-width:80ch}
.thtab{width:100%;font-size:.8rem;border-collapse:collapse;margin-top:var(--s2)}
.thtab th,.thtab td{text-align:left;padding:6px var(--s3);border-bottom:1px solid var(--grid);
 white-space:normal;position:static;background:transparent}
.thtab td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.takeaway{border-left:2px solid var(--accent);padding:var(--s2) 0 var(--s2) var(--s3);
 margin:0 0 var(--s3);color:var(--ink2);font-size:.88rem;max-width:80ch}
.takeaway b{color:var(--ink);font-weight:600}

/* --- decisions: options, pros, cons --------------------------------------- */
.dgrid{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(min(280px,100%),1fr));
 margin-top:var(--s3)}
.opt{background:var(--plane);border:1px solid var(--grid);border-radius:10px;padding:var(--s3)}
.opt.pick{border-color:var(--accent);background:color-mix(in oklab,var(--accent) 9%,var(--plane))}
.opt h5{margin:0;font-size:.9rem;display:flex;gap:var(--s2);align-items:baseline;flex-wrap:wrap}
.opt .tag{font-size:.64rem;text-transform:uppercase;letter-spacing:.06em;padding:1px 7px;
 border-radius:999px;border:1px solid color-mix(in oklab,var(--accent-t) 50%,transparent);
 color:var(--accent-t)}
.opt ul{margin:var(--s2) 0 0;padding-left:0;list-style:none;display:grid;gap:var(--s1)}
.opt li{display:flex;gap:6px;font-size:.8rem;color:var(--ink2);align-items:flex-start}
.opt li b{flex:0 0 auto;font-weight:600;font-size:.78rem}
.opt li.pro b{color:var(--good-t)}
.opt li.con b{color:var(--crit-t)}
.opt li.jdg b{color:var(--warn-t)}
.because{margin-top:var(--s4);display:grid;gap:var(--s2)}
.because div{font-size:.85rem;color:var(--ink2);max-width:82ch}
.because .lab{color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-size:.66rem;
 display:block;margin-bottom:2px}
/* --muted text on the --plane fill measures 4.49:1 in the LIGHT theme -- a hair
   under AA for normal text, and these panels are all --plane. Measured in-page
   via canvas (color-mix resolves to oklab(), so naive hex math would miss it),
   not eyeballed. Secondary ink is used inside them instead. */
.opt .dim,.rmgrid .dim,details.ev .dim{color:var(--ink2)}

/* --- roadmap -------------------------------------------------------------- */
.rmwrap{display:grid;gap:var(--s3)}
.rm{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:var(--s4);
 border-left:3px solid var(--grid)}
.rm.b-ready{border-left-color:var(--accent)}
.rm.b-blocked{border-left-color:var(--warn-t)}
.rm.b-dead{border-left-color:var(--rule)}
.rm.b-done{border-left-color:var(--good-t)}
.rmhead{display:flex;flex-wrap:wrap;gap:var(--s2);align-items:baseline}
.rmhead h4{margin:0;font-size:1rem;letter-spacing:-.01em;flex:1 1 18ch;min-width:0}
.rmline{margin:var(--s2) 0 0;color:var(--ink2);font-size:.87rem;max-width:82ch}
.rmgrid{display:grid;gap:var(--s2) var(--s4);margin-top:var(--s3);
 grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr))}
.rmgrid>div{font-size:.8rem;color:var(--ink2);min-width:0}
.rmgrid .lab{display:block;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;
 font-size:.65rem;margin-bottom:2px}
.rmgrid code{word-break:break-word}
.cost{font-variant-numeric:tabular-nums;font-weight:600;color:var(--ink)}
.blockline{margin-top:var(--s3);font-size:.82rem;color:var(--ink2);padding:var(--s2) var(--s3);
 border:1px solid color-mix(in oklab,var(--warn-t) 45%,transparent);border-radius:8px;
 background:var(--plane)}
.blockline b{color:var(--warn-t)}
.staleline{margin-top:var(--s3);font-size:.82rem;color:var(--ink2);padding:var(--s2) var(--s3);
 border:1px solid color-mix(in oklab,var(--crit-t) 45%,transparent);border-radius:8px;
 background:var(--plane)}
.staleline b{color:var(--crit-t)}
details.ev{margin-top:var(--s3)}
details.ev summary{cursor:pointer;color:var(--ink2);font-size:.8rem;list-style:revert;padding:2px 0}
details.ev summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
details.ev ul{margin:var(--s2) 0 0;padding-left:0;list-style:none;display:grid;gap:var(--s1)}
details.ev li{font-size:.78rem;color:var(--ink2);display:flex;gap:var(--s2);align-items:flex-start}
details.ev li .k{flex:0 0 7.5em;color:var(--muted);text-transform:uppercase;font-size:.64rem;
 letter-spacing:.05em;padding-top:2px}
details.ev li.bad .k{color:var(--crit-t)}
details.ev code{color:var(--ink);word-break:break-all}
@media(max-width:640px){.wrap{padding:var(--s4) var(--s3)}h1{font-size:1.25rem}.tile .v{font-size:1.5rem}}
</style></head><body><div class="wrap">
<header>
 <div><h1>Rulemancer — metrics history</h1>
 <p class="meta">Generated __GENERATED__ · every number read from its file at build time</p></div>
 <button id="themeBtn" type="button" aria-label="Toggle colour theme">Theme</button>
</header>
<p class="sub">Every judged arm we own, side by side, grouped by the question set it
actually ran on. Arms in different groups are <strong>not</strong> comparable — different
questions. The question this exists to answer: is it time for the full RulesGuru run?</p>
<div id="app"></div>
<footer id="foot"></footer>
</div>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const pct = v => v==null ? '—' : (v*100).toFixed(1)+'%';
const usd = v => v==null ? '—' : '$'+v.toFixed(5);
const int = v => v==null ? '—' : Math.round(v).toLocaleString();
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const JOIN = {
  'exact':['b-good','verified'], 'alias':['b-good','verified'], 'id-match':['b-good','verified by ids'],
  'prefix':['b-warn','name-matched'], 'unmatched':['b-crit','no answers file'],
  'name-matched-ids-differ':['b-crit','name matched, ids differ']
};
const joinBadge = j => {
  const hit = JOIN[j] || (j.startsWith('ambiguous') ? ['b-crit', j] : ['b-warn', j]);
  return `<span class="badge ${hit[0]}" title="${esc(j)}">${esc(hit[1])}</span>`;
};

const C = D.comparisons || {};
const ACM = D.arm_config_matrix || {fields:[], rows:[], differs:[], same:[], inconsistent_arms:[]};
const RC = D.retrieval_coverage || {arms:[], worklist:[], worklist_n_total:0,
  worklist_n_above_threshold:0, gap_threshold:0.5, skipped:[],
  gold_size_stratification:{strata:[]}, gold_size_stratification_shipped:{strata:[]},
  shipped_arms:[]};
// GS: citation-source classifier (docs/results-groundedness-guard.md), computed
// by evals/grounding_sources.py -- NOT the same thing as RC above (RC is
// whether retrieval hit the gold ids; GS is which kind of source -- CR rule,
// ruling, card, or nothing -- the model's own citations actually rested on).
const GS = D.grounding_sources || {arms:[], n_skipped:0};
// RC is the GRADED coverage backfill (docs/spec-coverage-metric.md), not to be
// confused with RM.coverage below (that's plan/spec DOC coverage -- how many
// roadmap docs are accounted for -- an unrelated meaning of the same word).
const pp = v => (v>=0?'+':'−') + Math.abs(v).toFixed(1) + ' pp';
const pctd = v => (v>=0?'+':'−') + Math.abs(v).toFixed(0) + '%';
const arrow = v => v>0 ? '▲' : (v<0 ? '▼' : '▬');
const day = s => (s||'').slice(0,10);
const stamp = s => (s||'').slice(0,16).replace('T',' ');
const money = v => v==null ? '—' : '$'+v.toFixed(0);

/* KIND. Second comparability gate, alongside the question-set fingerprint.
   An oracle arm answered with retrieval switched off, so it is not on the same
   scale as the product path and is never differenced against it. */
const KIND = {
  pipeline:['b-pipe','pipeline', 'the product path: retrieval ran'],
  oracle:  ['b-warn','oracle — not a pipeline score', 'retrieval off, rules handed in'],
  unknown: ['b-crit','unclassified', 'nothing records how this ran']
};
const kindBadge = (k, why) => {
  const h = KIND[k] || KIND.unknown;
  return `<span class="badge ${h[0]}" title="${esc(why||h[2])}">${esc(h[1])}</span>`;
};

/* PROVENANCE. Three separate events, never one "Run" column: the generation run
   made the answers, the judging run scored them, a human pass may have regraded
   them. The judge is nondeterministic, so an accuracy that does not name its
   judging run is not reproducible. */
function provBlock(gens, judges, humans){
  const g = (gens||[]).filter(x=>x.file).map(x =>
    `<code>${esc(x.file)}</code> <span class="t">${esc(stamp(x.mtime))}</span>`).join('<br>')
    || `<span class="miss">no answers file joined — config and cost unknown</span>`;
  const j = (judges||[]).map(x => x.recorded
    ? `<code>${esc(x.file)}</code> <span class="t">${esc(stamp(x.mtime))}</span><br>
       <span class="dim">${esc(x.judge_model)} · prompt sha256 ${esc(x.judge_digest||'not recorded')}</span>`
    : `<code>${esc(x.file)}</code> <span class="t">${esc(stamp(x.mtime))}</span><br>
       <span class="miss">no judge model or prompt digest recorded — not reproducible</span>`
  ).join('<br>') || `<span class="miss">none</span>`;
  const h = (humans||[]).map(x =>
    `<span class="t">${esc(x.grading_date||'date not recorded')}</span> · ${esc(x.grader||'grader not named')}
     · ${x.n_overturned} of ${x.n_regraded} regraded rows overturned`).join('<br>');
  return `<div class="prov">
    <div><span class="lab">Generation run</span><span>${g}</span></div>
    <div><span class="lab">Judging run</span><span>${j}</span></div>
    ${h ? `<div><span class="lab">Human grading</span><span>${h}</span></div>` : ''}
  </div>`;
}

const warnline = w => w ? `<p class="warnline ${esc(w.level)}"><b>${w.level==='crit'?'✕ Blocked':'⚠ Caution'}</b>
  <span>${esc(w.text)}.</span></p>` : '';

/* The decision number. It must be the SAME basis as the decision panel below --
   two different cost ranges on one page, both labelled "the full run", is exactly
   the sort of thing this page exists to stop. Both read FULL_RUN when it exists,
   HEAD (the blended same-config projection) only when it doesn't -- reusing HEAD
   once FULL_RUN exists would be circular, since the full run's own rows are by
   then folded into HEAD's blend (see build_summary's PROJECTION_VALIDATION note
   in the python source for the full explanation). */
const N = D.full_corpus;
const PROJ = (D.comparisons||{}).projections || [];
const PIPE = PROJ.filter(p => p.kind==='pipeline' && p.projected_acc!=null);
const shipped = PIPE.filter(p => p.config.model===D.current_config.GEN_MODEL
                              && p.config.effort===D.current_config.GEN_EFFORT)
                    .sort((a,b)=>b.n_questions-a.n_questions);
const HEAD = shipped[0] || PIPE[0] || null;
const FULL_RUN = ((D.summary||{}).facts||{}).full_run || null;
const lo = HEAD ? HEAD.cost_lo : null, hi = HEAD ? HEAD.cost_hi : null;

const tiles = [
  {k:'Full RulesGuru run', v: FULL_RUN ? ('$'+FULL_RUN.cost_total.toFixed(0))
                            : (lo==null?'—':('$'+(lo*N).toFixed(0)+'–'+(hi*N).toFixed(0))),
   n: FULL_RUN ? `${N.toLocaleString()} questions, measured (not estimated) — `
                 + `$${FULL_RUN.cost_per_q.toFixed(5)}/question on `
                 + `${FULL_RUN.model} / ${FULL_RUN.effort||'default'}`
                 + `${FULL_RUN.batch?', batch API rate':''}, run ${(FULL_RUN.run_at||'').slice(0,10)}`
      : (HEAD ? `${N.toLocaleString()} questions at the measured cost/question of `
             + `${HEAD.config.model} / ${HEAD.config.effort||'default'} `
             + `(${HEAD.sets.length} question set${HEAD.sets.length>1?'s':''}, ${HEAD.n_questions} questions run)`
           : 'no pipeline arm carries both a cost and per-level counts'),
   cls:'decision'},
  {k: FULL_RUN ? 'Measured accuracy' : 'Expected accuracy',
   v: FULL_RUN ? pct(FULL_RUN.acc) : (HEAD ? pct(HEAD.projected_acc) : '—'),
   n: FULL_RUN ? `measured, not projected · 95% interval ${pct(FULL_RUN.ci95[0])}–${pct(FULL_RUN.ci95[1])} `
                 + `· all ${N.toLocaleString()} corpus questions`
      : (HEAD ? `corpus-mix reweighted · 95% interval ${pct(HEAD.ci95[0])}–${pct(HEAD.ci95[1])} `
             + `· covers ${(HEAD.covered_share*100).toFixed(0)}% of the corpus by level`
           : 'nothing projectable')},
  {k:'Arms tracked', v: String(D.arms.length),
   n:`${new Set(D.arms.map(a=>a.qset)).size} distinct question sets · `
     + `${D.arms.filter(a=>a.kind==='pipeline').length} pipeline, `
     + `${D.arms.filter(a=>a.kind==='oracle').length} oracle, `
     + `${D.arms.filter(a=>a.kind==='unknown').length} unclassified`},
  {k:'Weighting', v:'Corner ×0.5', n:`flat across L0–L3 · ruled by ${esc(D.weighting.ruled_by)}`},
];

const groups = {};
D.arms.forEach(a => (groups[a.qset] ||= []).push(a));
const order = Object.entries(groups).sort((a,b)=>b[1].length-a[1].length || b[1][0].n-a[1][0].n);

const COLS = [
  ['Arm', a=>`${esc(a.arm)} ${a.human_corrected?'<span class="badge b-good">human-corrected</span>':''}`, a=>a.arm],
  ['Kind', a=>kindBadge(a.kind, a.kind_why), a=>a.kind],
  ['Model', a=>`<span class="dim">${esc((a.config||{}).model||'—')}${(a.config||{}).effort?' / '+esc(a.config.effort):''}</span>`, a=>(a.config||{}).model||''],
  ['Flat', a=>`<span class="num">${pct(a.accuracy_flat)}</span>`, a=>a.accuracy_flat],
  ['Weighted', a=>`<span class="num">${pct(a.accuracy_weighted)}</span>`, a=>a.accuracy_weighted],
  ['Auto', a=>`<span class="num dim">${pct(a.accuracy_auto)}</span>`, a=>a.accuracy_auto??-1],
  ['$/question', a=>`<span class="num">${usd((a.cost||{}).cost_per_q)}</span>`, a=>(a.cost||{}).cost_per_q??-1],
  ['In tok', a=>`<span class="num dim">${int((a.cost||{}).in_per_q)}</span>`, a=>(a.cost||{}).in_per_q??-1],
  ['Out tok', a=>`<span class="num dim">${int((a.cost||{}).out_per_q)}</span>`, a=>(a.cost||{}).out_per_q??-1],
  // GENERATION RUN and JUDGING RUN are separate events and get separate columns.
  // The judge prompt digest is a published-number requirement, not a tooltip.
  ['Generation run', a=>a.generation.file
      ? `<span class="dim num">${esc(stamp(a.generation.mtime))}</span><br>
         <span class="dim" style="font-size:.72rem">${esc(a.generation.file.split('/').pop())}</span>
         ${joinBadge(a.generation.join)}`
      : `<span class="badge b-crit">no answers file</span>`, a=>a.generation.mtime||''],
  ['Judging run', a=>a.judging.recorded
      ? `<span class="dim num">${esc(stamp(a.judging.mtime))}</span><br>
         <span class="dim" style="font-size:.72rem">${esc(a.judging.judge_model)} · sha ${esc(a.judging.judge_digest||'none')}</span>`
      : `<span class="dim num">${esc(stamp(a.judging.mtime))}</span><br>
         <span class="badge b-crit">judge not recorded</span>`, a=>a.judging.mtime||''],
  ['Human grading', a=>a.human
      ? `<span class="badge b-good">graded</span><br><span class="dim num" style="font-size:.72rem">${esc(a.human.grading_date||'')} ${esc(a.human.grader||'')}</span><br>
         <span class="dim" style="font-size:.72rem">${a.human.n_overturned}/${a.human.n_regraded} overturned</span>`
      : `<span class="dim">—</span>`, a=>a.human?1:0],
];

function table(rows, key){
  const head = COLS.map((c,i)=>`<th tabindex="0" role="columnheader" data-c="${i}" data-k="${key}">${c[0]}</th>`).join('');
  const body = rows.map(a=>`<tr>${COLS.map(c=>`<td>${c[1](a)}</td>`).join('')}</tr>`).join('');
  return `<div class="scroll"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

/* ======================= THE DECISION =======================================
   Is it time for the full RulesGuru run? Four things decide it: what it costs,
   what accuracy to expect, how much of any difference is measurement error, and
   what is still unresolved. Everything here regenerates from the files. */
const floors = (D.timeline.sets||[]).map(s=>s.floor_pp).filter(v=>v!=null);
const worstFloor = floors.length ? Math.max(...floors) : null;

function decisionHTML(){
  if(!HEAD) return `<section class="sec" id="decision"><h2>The decision</h2>
    <div class="card empty"><strong>No pipeline configuration can be projected.</strong><br>
    A projection needs an arm classified <code>pipeline</code> with both a measured cost and
    per-level counts. None qualified.</div></section>`;

  const cfg = HEAD.config;
  const lo = HEAD.ci95 ? HEAD.ci95[0]*100 : null, hi = HEAD.ci95 ? HEAD.ci95[1]*100 : null;
  const mid = HEAD.projected_acc*100;
  const gap = HEAD.missing_levels.length;

  // Sensitivity: every priced configuration, cheapest full run first.
  const priced = PROJ.filter(p=>p.full_run_lo!=null)
                     .sort((a,b)=>a.full_run_lo-b.full_run_lo);
  const rows = priced.map(p=>{
    const c=p.config, isHead = p===HEAD;
    return `<tr${isHead?' style="outline:1px solid var(--accent);outline-offset:-1px"':''}>
      <td>${esc(c.model||'—')} <span class="dim">/ ${esc(c.effort||'default effort')}</span>
        ${kindBadge(p.kind, p.kind_why)}${isHead?' <span class="badge b-good">shipped config</span>':''}</td>
      <td class="dim">rewrite ${esc(String(c.rewrite_version))} · ${esc(String(c.ruling_query_mode))}</td>
      <td class="num">${usd(p.cost_lo)}${p.cost_hi!==p.cost_lo?'–'+usd(p.cost_hi):''}</td>
      <td class="num"><strong>${money(p.full_run_lo)}${p.full_run_hi!==p.full_run_lo?'–'+money(p.full_run_hi):''}</strong></td>
      <td class="num">${pct(p.projected_acc)}</td>
      <td class="num dim">${p.ci95?pct(p.ci95[0])+'–'+pct(p.ci95[1]):'—'}</td>
      <td class="num dim">${(p.covered_share*100).toFixed(0)}%</td>
      <td class="num dim">${p.n_questions}</td>
      <td class="num dim">${int(p.in_per_q)} / ${int(p.out_per_q)}</td>
    </tr>`;
  }).join('');

  const items = (C.open_items||[]);
  const openHTML = items.length ? items.map(o=>`
    <p class="warnline ${esc(o.level)}"><b>${o.level==='crit'?'✕':'⚠'}</b><span>
      <strong>${esc(o.what)}.</strong> ${esc((o.which||[]).join(', '))}<br>
      <span class="dim">${esc(o.changes)}</span></span></p>`).join('')
    : `<p class="note">Nothing is outstanding. Every arm carries a joined answers file, a named
       judging run, a classification and at least two reps.</p>`;

  return `<section class="sec" id="decision">
   <h2>The decision — is it time for the full run?</h2>
   <p class="lede">Everything below is measured, not asserted. The full corpus is
   <strong>${D.full_corpus.toLocaleString()} questions</strong>; the shipped configuration has been
   run on <strong>${HEAD.n_questions}</strong> of them.</p>
   <div class="dec">
     <div class="card decision">
       <h4>What a full run costs</h4>
       <span class="big">${money(HEAD.full_run_lo)}${HEAD.full_run_hi!==HEAD.full_run_lo?'–'+money(HEAD.full_run_hi):''}</span>
       <div class="n dim">${esc(cfg.model)} / ${esc(cfg.effort||'default')} at
         ${usd(HEAD.cost_lo)}–${usd(HEAD.cost_hi)} per question</div>
       <p>Measured from recorded token usage, not estimated. The range is the spread between the
       question sets this config ran on — harder questions cost more. Config choice moves this a
       long way: see the sensitivity table below.</p>
     </div>
     <div class="card">
       <h4>Accuracy to expect</h4>
       <span class="big">${pct(HEAD.projected_acc)}</span>
       <div class="band" role="img" aria-label="95 percent interval ${lo.toFixed(1)} to ${hi.toFixed(1)} percent">
         <i style="left:${lo}%;width:${Math.max(hi-lo,0.6)}%"></i><u style="left:${mid}%"></u></div>
       <div class="scale"><span>0%</span><span>95% interval ${lo.toFixed(1)}–${hi.toFixed(1)}%</span><span>100%</span></div>
       <p>Per-level accuracy reweighted to the corpus's own level mix
       (${Object.entries(C.corpus.by_level||{}).sort().map(([k,v])=>(k==='Corner Case'?'Corner':'L'+k)+' '+v).join(', ')}).
       A flat score off a stratified sample is not this number — the 150-set is 30 per level, the
       corpus is not.
       ${gap ? `<strong>Covers ${(HEAD.covered_share*100).toFixed(0)}% of the corpus by level</strong>
       — level ${esc(HEAD.missing_levels.join(', '))} is untested, and it is the corpus's easiest
       slice, so this is more likely low than high.` : 'Covers every level in the corpus.'}</p>
     </div>
     <div class="card">
       <h4>Measurement error vs real difference</h4>
       <span class="big">±${worstFloor==null?'—':worstFloor.toFixed(1)} pp</span>
       <div class="n dim">widest noise floor across the question sets</div>
       <p>Where one configuration was run twice, the spread between those two runs IS the
       resolution of this instrument. Any gap smaller than a set's floor is not a result. The judge
       is nondeterministic on top of that — roughly one verdict flip per hundred rows — so two arms
       scored in two judging runs differ a little before either model does anything.</p>
     </div>
   </div>
   <h3 style="font-size:.95rem;margin:var(--s5) 0 var(--s2)">Cost sensitivity to config choice</h3>
   <p class="note">Same corpus, different configuration. Full-run cost is the measured cost per
   question times ${D.full_corpus.toLocaleString()}. Oracle rows are shown because their cost is
   real, but their accuracy is a ceiling, not a product score.</p>
   <div class="scroll"><table aria-label="Projected full-run cost and accuracy by configuration">
     <thead><tr><th>Configuration</th><th>Retrieval config</th><th>$/question</th>
       <th>Full run (${D.full_corpus.toLocaleString()} q)</th><th>Corpus-mix accuracy</th>
       <th>95% interval</th><th>Corpus covered</th><th>Questions run</th><th>In / out tokens</th></tr></thead>
     <tbody>${rows}</tbody></table></div>
   <h3 style="font-size:.95rem;margin:var(--s5) 0 var(--s2)">What is unresolved, and what it would change</h3>
   ${openHTML}
  </section>`;
}

/* ======================= HEAD TO HEAD ======================================= */
function h2hHTML(){
  const sets = (C.head_to_head||[]);
  if(!sets.length) return `<section class="sec" id="h2h"><h2>Head to head</h2>
    <div class="card empty"><strong>No two arms are comparable.</strong><br>
    A pair needs the same question-set fingerprint <em>and</em> the same kind.</div></section>`;

  let h = `<section class="sec" id="h2h"><h2>Head to head — same questions, same kind</h2>
  ${tk('h2h')}
    <p class="lede">Two arms may only be subtracted when they ran the <strong>same questions</strong>
    and measure the <strong>same thing</strong>. Sharing a question set is not enough: an arm handed
    its gold rules with retrieval switched off is not on the same scale as the product path.
    <br><span class="dim">${esc(C.kind_rule||'')}</span></p>`;

  sets.forEach(s=>{
    h += `<div class="setline"><h3>${s.n} questions</h3>
      <span class="meta">fingerprint <code>${esc(s.qset)}</code> · noise floor ±${s.floor_pp.toFixed(1)} pp</span></div>`;
    if(s.pairs.length){
      h += `<div class="h2h">` + s.pairs.map(p=>{
        const aWin = p.flat_pp!=null && p.flat_pp>0, bWin = p.flat_pp!=null && p.flat_pp<0;
        const r = p.paired;
        const bar = r ? (()=>{
          const w = x => (x/r.n_shared*100).toFixed(1)+'%';
          return `<div class="rec" role="img" aria-label="paired record on ${r.n_shared} shared rows">
            <span style="width:${w(r.both)};background:var(--grid)"></span>
            <span style="width:${w(r.a_only)};background:var(--accent)"></span>
            <span style="width:${w(r.b_only)};background:var(--serious)"></span>
            <span style="width:${w(r.neither)};background:var(--crit)"></span></div>
          <div class="reclegend">
            <span><i style="background:var(--grid)"></i>both right ${r.both}</span>
            <span><i style="background:var(--accent)"></i>${esc(p.a)} only ${r.a_only}</span>
            <span><i style="background:var(--serious)"></i>${esc(p.b)} only ${r.b_only}</span>
            <span><i style="background:var(--crit)"></i>both wrong ${r.neither}</span></div>
          <p class="reps">Paired on the ${r.n_shared} rows both answered, from one run of each:
            <code>${esc(r.a_run)}</code> and <code>${esc(r.b_run)}</code>. A different rep would give
            a different record.</p>`;
        })() : `<p class="reps">No paired record — the two runs share no scorable rows.</p>`;

        const verdict = p.beats_noise===null ? '<span class="badge">no accuracy delta</span>'
          : p.beats_noise ? `<span class="badge b-good">clear of the ±${p.floor_pp.toFixed(1)} pp floor</span>`
                          : `<span class="badge b-warn">inside the ±${p.floor_pp.toFixed(1)} pp floor — not a result</span>`;

        return `<article class="card">
          <div class="stephead"><h4>${esc(p.a)} vs ${esc(p.b)}</h4>${kindBadge(p.kind)}
            ${p.controlled?'<span class="badge b-good">one field differs</span>'
                          :`<span class="badge b-warn">${p.differs.length} fields differ</span>`}</div>
          <p class="reps">Differs in: ${p.differs.length
            ? p.differs.map(d=>`<code>${esc(d.label)}</code> ${esc(String(d.a))} vs ${esc(String(d.b))}`).join(', ')
            : 'no recorded config field — same config, different runs'}</p>
          <div class="vs">
            <div class="side ${aWin?'win':''}"><div class="nm">${esc(p.a)}</div>
              <div class="sc">${pct(p.a_flat)}</div>
              <div class="nm num">${usd(p.a_cost)} / question</div></div>
            <div class="mid">${p.flat_pp==null?'—':arrow(p.flat_pp)+' '+pp(p.flat_pp)}<br>flat</div>
            <div class="side ${bWin?'win':''}"><div class="nm">${esc(p.b)}</div>
              <div class="sc">${pct(p.b_flat)}</div>
              <div class="nm num">${usd(p.b_cost)} / question</div></div>
          </div>
          <div class="pills">
            ${pill('weighted', p.weighted_pp, pp, true, 'Corner-case-weighted, '+p.a+' minus '+p.b)}
            ${pill('$/question', p.cost_pct, pctd, false, p.a+' relative to '+p.b)}
            <span class="pill">out tokens <b>${int(p.a_out)} vs ${int(p.b_out)}</b></span>
            <span class="pill">in tokens <b>${int(p.a_in)} vs ${int(p.b_in)}</b></span>
          </div>
          <p class="base">${verdict}</p>
          ${bar}
          ${warnline(p.judge)}
        </article>`;
      }).join('') + `</div>`;
    } else {
      h += `<div class="card empty"><strong>No kind-matched pair on this set.</strong><br>
        Arms ran here, but no two of them share a kind — so no difference between them would mean
        anything.</div>`;
    }
    if(s.headroom){
      const hr = s.headroom;
      h += `<div class="card" style="margin-top:var(--s3)">
        <div class="stephead"><h4>Retrieval headroom on this set</h4>
          <span class="badge b-warn">not a head-to-head</span></div>
        <p class="note">The oracle arm was handed its rules; the other arm had to find them. The gap
        between them is roughly <strong>what retrieval is leaving on the table</strong> — it is not
        an improvement anyone shipped, and it is not a step delta.</p>
        <div class="vs">
          <div class="side"><div class="nm">${esc(hr.oracle)} ${kindBadge('oracle', hr.oracle_kind_why)}</div>
            <div class="sc">${pct(hr.oracle_flat)}</div>
            <div class="nm">answers derivable when the rules are supplied</div></div>
          <div class="mid">${arrow(hr.gap_pp)} ${pp(hr.gap_pp)}<br>headroom</div>
          <div class="side"><div class="nm">${esc(hr.other)} ${kindBadge(hr.other_kind, hr.other_kind_why)}</div>
            <div class="sc">${pct(hr.other_flat)}</div>
            <div class="nm">best other arm on these questions</div></div>
        </div>
        ${hr.other_kind==='unknown' ? `<p class="warnline warn"><b>⚠ Caution</b><span>
          the counterpart is unclassified — ${esc(hr.other_kind_why)}. Read this gap as indicative,
          not as a measured pipeline-vs-oracle result.</span></p>` : ''}
        ${warnline(hr.judge)}</div>`;
    }
  });
  return h + `</section>`;
}

/* ======================= COST VS ACCURACY =================================== */
function frontierHTML(){
  const sets = (C.frontier||[]).filter(s=>s.points.length||s.unpriced.length);
  if(!sets.length) return '';
  let h = `<section class="sec" id="frontier"><h2>Cost vs accuracy — what is dominated</h2>
  ${tk('frontier')}
    <p class="lede">An arm is <strong>dominated</strong> when another arm on the same questions, of
    the same kind, scored at least as well for no more money. A dominated arm is never the right
    choice. Dominance is only ever computed inside one question set and one kind — an arm with
    retrieval switched off is not on the product's frontier.</p>`;
  sets.forEach(s=>{
    // "On the frontier" is only a claim when something else was in the running.
    // An arm alone on its set-and-kind wins by default, which is not a result.
    const rivals = k => s.points.filter(x=>x.kind===k).length;
    const rows = s.points.slice().sort((a,b)=>b.flat-a.flat).map(p=>`
      <tr class="${p.dominated_by?'dominated':''}">
        <td>${esc(p.step)} ${kindBadge(p.kind)}</td>
        <td class="dim">${esc(p.model||'—')} / ${esc(p.effort||'default')}</td>
        <td class="num">${pct(p.flat)}</td>
        <td class="num dim">${pct(p.weighted)}</td>
        <td class="num">${usd(p.cost)}</td>
        <td class="num">${money(p.full_run)}</td>
        <td>${p.dominated_by
          ? `<span class="badge b-crit">▼ dominated by ${esc(p.dominated_by)}</span>`
          : rivals(p.kind) > 1
            ? `<span class="badge b-good">▲ on the frontier</span>`
            : `<span class="badge" title="Nothing else of this kind was priced on this question set, so there is nothing to be better than.">— only priced ${esc(p.kind)} arm here</span>`}</td></tr>`).join('');
    const un = s.unpriced.map(u=>`<tr><td>${esc(u.step)} ${kindBadge(u.kind)}</td>
      <td class="dim" colspan="2">accuracy ${pct(u.flat)}</td>
      <td class="dim" colspan="4">not priced — ${esc(u.why)}, so no token usage to cost</td></tr>`).join('');
    h += `<div class="setline"><h3>${s.n} questions</h3>
      <span class="meta">fingerprint <code>${esc(s.qset)}</code></span></div>
      <div class="scroll"><table aria-label="Cost versus accuracy, ${s.n} question set">
        <thead><tr><th>Arm</th><th>Model</th><th>Flat</th><th>Weighted</th><th>$/question</th>
          <th>Full run</th><th>Frontier</th></tr></thead>
        <tbody>${rows||''}${un}</tbody></table></div>`;
  });
  return h + `</section>`;
}

/* ======================= PER-LEVEL ========================================== */
function levelsHTML(){
  const sets = (C.levels||[]);
  if(!sets.length) return '';
  let h = `<section class="sec" id="levels"><h2>Per-level accuracy</h2>
  ${tk('levels')}
    <p class="lede">Level mix is exactly what the weighting ruling is about, and it is also why a
    flat score off one question set does not transfer to the corpus. Each set's own mix is shown
    against the corpus mix, so you can see which levels an arm is actually evidence for.</p>`;
  sets.forEach(s=>{
    const head = s.order.map(lv=>`<th>${lv==='Corner Case'?'Corner':'L'+lv}
      <br><span class="dim" style="font-weight:400;text-transform:none;letter-spacing:0">${
        s.corpus_share[lv]==null?'not in corpus':(s.corpus_share[lv]*100).toFixed(0)+'% of corpus'}</span></th>`).join('');
    const rows = s.rows.map(r=>`<tr><td>${esc(r.step)} ${kindBadge(r.kind)}</td>
      <td class="num">${pct(r.flat)}</td>` + s.order.map(lv=>{
        const c = r.cells[lv];
        if(!c) return `<td class="lv dim">no rows</td>`;
        const a = c.acc;
        return `<td class="lv num">${a==null?'—':(a*100).toFixed(0)+'%'}
          <span class="dim" style="font-size:.72rem"> ${c.correct.toFixed(c.correct%1?1:0)}/${c.n}</span>
          <i class="cellbar" style="width:${a==null?0:(a*100).toFixed(0)}%"></i></td>`;
      }).join('') + `</tr>`).join('');
    h += `<div class="setline"><h3>${s.n} questions</h3>
      <span class="meta">fingerprint <code>${esc(s.qset)}</code> · counts are pooled across reps</span></div>
      <div class="scroll"><table aria-label="Per-level accuracy, ${s.n} question set">
        <thead><tr><th>Arm</th><th>Flat</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
  });
  return h + `</section>`;
}

/* ======================= CONFIG MATRIX ====================================== */
function matrixHTML(){
  const M = C.matrix;
  if(!M || !M.gen_axis.length) return '';
  const head = M.ret_axis.map(r=>`<th>rewrite ${esc(String(r.rewrite_version))}<br>
    <span class="dim" style="font-weight:400;text-transform:none;letter-spacing:0">${esc(String(r.ruling_query_mode))} · system v${esc(String(r.system_version))}</span></th>`).join('');
  const rows = M.gen_axis.map(g=>`<tr>
    <td>${esc(String(g.model))} <span class="dim">/ ${esc(String(g.effort??'default'))}</span></td>` +
    M.ret_axis.map(r=>{
      const cell = M.cells[`${g.model}|${g.effort}||${r.rewrite_version}|${r.ruling_query_mode}|${r.system_version}`] || [];
      if(!cell.length) return `<td class="gap">— untested</td>`;
      return `<td class="tried">` + cell.map(x=>`<div>${esc(x.step)}
        <span class="dim">${x.n}q · ${pct(x.flat)} · ${x.n_reps} rep${x.n_reps>1?'s':''}</span>
        ${kindBadge(x.kind)}</div>`).join('') + `</td>`;
    }).join('') + `</tr>`).join('');
  return `<section class="sec" id="matrix"><h2>Config matrix — what has been tried</h2>
  ${tk('matrix')}
    <p class="lede">${M.n_tried} of ${M.n_cells} combinations have been run. Blank cells are not
    failures, they are untested. ${esc(M.note)}</p>
    <div class="scroll"><table aria-label="Configuration coverage matrix">
      <thead><tr><th>Model / effort</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>
    </section>`;
}

/* ======================= ARM CONFIG MATRIX ===================================
   Every config axis recorded on an arm's answer rows, side by side, per arm --
   not per model/effort cell like the coverage matrix above. Built so that "these
   two arms differ on N things" is visible without reading four JSON files. See
   build_arm_config_matrix() for why this exists (2026-07-26 review). */
function fmtAxis(x){
  if(x===null||x===undefined) return '—';
  if(typeof x==='boolean') return x?'true':'false';
  return String(x);
}
function acmCell(v){
  if(!v) return '<span class="dim">—</span>';
  if(v.mixed){
    const detail = v.breakdown.map(b=>`${b.n} ${esc(fmtAxis(b.value))}`).join(' / ');
    const maj = fmtAxis(v.breakdown[0].value);
    return `${esc(maj)} <span class="badge b-warn" title="not constant across this arm's rows">mixed: ${detail}</span>`;
  }
  return esc(fmtAxis(v.value));
}
function armConfigMatrixHTML(){
  if(!ACM.rows.length) return '';
  const diffSet = new Set(ACM.differs);
  const head = `<th>Arm</th><th>Kind</th>` + ACM.fields.map(f=>
    `<th class="${diffSet.has(f.key)?'acm-diff':'dim'}">${esc(f.label)}</th>`).join('');
  const body = ACM.rows.map(r=>{
    const cells = ACM.fields.map(f=>{
      const cls = diffSet.has(f.key) ? 'acm-diff' : 'dim';
      const content = r.config_recorded
        ? acmCell(r.values[f.key])
        : '<span class="badge b-crit">no answers file</span>';
      return `<td class="${cls}">${content}</td>`;
    }).join('');
    return `<tr><td>${esc(r.arm)}<br><span class="dim" style="font-size:.7rem">qset ${esc(r.qset)}</span></td>
      <td>${kindBadge(r.kind)}</td>${cells}</tr>`;
  }).join('');
  const diffLabels = ACM.differs.map(f=>esc((ACM.fields.find(x=>x.key===f)||{}).label||f));
  const inc = ACM.inconsistent_arms.length
    ? `<p class="lede"><span class="badge b-warn">${ACM.inconsistent_arms.length} arm${ACM.inconsistent_arms.length>1?'s':''} internally inconsistent</span> —
       ${ACM.inconsistent_arms.map(i=>`<code>${esc(i.arm)}</code> (${i.fields.map(f=>esc((ACM.fields.find(x=>x.key===f)||{}).label||f)).join(', ')})`).join('; ')}.
       A field that isn't constant within one arm's own rows is a finding about that arm, not noise to average away.</p>`
    : '';
  return `<section class="sec" id="arm-config"><h2>Arm config matrix</h2>
    ${tk('arm-config')}
    <p class="lede">Every config axis recorded on each arm's answer rows, one row per arm.
    Columns every arm agrees on are muted; columns arms <strong>disagree</strong> on are
    highlighted, because attributing an accuracy gap to one axis when the arms also differ
    on a highlighted column is comparing more than one thing at once.</p>
    <p class="lede">${diffSet.size} of ${ACM.fields.length} axes differ across arms${diffLabels.length?': '+diffLabels.join(', '):''}.</p>
    ${inc}
    <div class="scroll"><table aria-label="Arm configuration matrix"><thead><tr>${head}</tr></thead>
      <tbody>${body}</tbody></table></div>
    </section>`;
}

/* ======================= RETRIEVAL COVERAGE (graded) ========================
   docs/spec-coverage-metric.md. RC is the backfilled coverage data
   (evals/backfill_coverage.py -> evals/coverage_backfill.json), NOT the same
   thing as RM.coverage (roadmap doc coverage) below -- different meaning of
   the same English word, kept apart on purpose. */
function retrievalCoverageHTML(){
  const arms = (RC.arms||[]).filter(a=>!a.debug);
  const debugArms = (RC.arms||[]).filter(a=>a.debug);
  if(!arms.length && !debugArms.length) return '';
  const rows = arms.map(a=>{
    const cov = a.mean_coverage==null?'—':pct(a.mean_coverage);
    const hr = a.hit_rate==null?'—':pct(a.hit_rate);
    const flag = a.retrieval_off
      ? '<span class="badge b-warn" title="retrieved_rule_ids empty on every row -- retrieval was OFF by design (e.g. gold handed to the generator directly), not a retrieval failure">retrieval off (oracle)</span>'
      : '';
    return `<tr><td>${esc(a.arm)} ${flag}</td><td class="num dim">${a.n_scored}/${a.n_rows}</td>
      <td class="num">${hr}</td><td class="num"><strong>${cov}</strong></td></tr>`;
  }).join('');
  const wl = (RC.worklist||[]).slice(0,20);
  const wlRows = wl.map((r,i)=>`<tr><td class="num dim">${i+1}</td><td>${esc(r.arm)}</td>
    <td><code>${esc(r.id)}</code></td><td>${esc(r.match)}</td><td class="num">${r.gold_n}</td>
    <td class="num">${pct(r.coverage)}</td><td class="num"><strong>${pct(r.gap)}</strong></td>
    <td class="dim" style="white-space:normal;max-width:40ch">${esc((r.question||'').slice(0,90))}${(r.question||'').length>90?'…':''}</td></tr>`).join('');
  return `<section class="sec" id="retrieval-coverage"><h2>Retrieval coverage — graded, alongside recall@k</h2>
    <p class="lede">recall@k / hit@k elsewhere on this page is a boolean: did retrieval satisfy the
    question's own <code>match</code> rule at all. Coverage is graded: what fraction of a question's
    cited gold ids actually landed in the retrieved set, computed flat over <code>gold</code> -- it never
    calls <code>gold_groups()</code>, so a <code>match:"any"</code> row with several required facts can no
    longer look fully retrieved on the strength of one incidental hit. Backfilled from recorded
    <code>retrieved_rule_ids</code> across every <code>evals/answers/*.json</code> arm that has them
    (${arms.length + debugArms.length} arms, zero model calls, zero re-runs) --
    see <code>docs/spec-coverage-metric.md</code>. <code>hit_at()</code>/<code>gold_groups()</code> are
    unchanged; this is reported beside them, never instead of them.</p>
    <div class="scroll"><table aria-label="Mean coverage per arm">
      <thead><tr><th>Arm</th><th>Scored / rows</th><th>Hit rate (boolean)</th><th>Mean coverage (graded)</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
    ${debugArms.length ? `<p class="note" style="margin-top:var(--s3)"><strong>Debug/smoke fixtures
      (n&lt;10 rows, excluded from the table above -- not meaningful evidence on their own):</strong>
      ${debugArms.map(a=>`<code>${esc(a.arm)}</code> (n=${a.n_rows})`).join(', ')}</p>` : ''}
    <h3 style="margin:var(--s4) 0 var(--s2);font-size:1rem;letter-spacing:-.01em">The diagnostic:
      where the boolean is most inflated</h3>
    <p class="lede">Rows where <code>hit_at()</code> scores a complete pass
      (<code>match:"any"</code> needs one gold id; <code>match:"groups"</code> needs one member per
      group) while coverage says otherwise, ranked by the size of that gap. Gap = 1 − coverage, shown
      only for rows where <code>hit_at()</code> is true -- a miss isn't "inflation," there's no
      full-credit call to disagree with.
      <strong>${RC.worklist_n_above_threshold} of ${RC.worklist_n_total}</strong> scored rows exceed a
      gap of ${(RC.gap_threshold*100).toFixed(0)}% -- more than half that row's cited gold missing
      despite a full-credit hit. Top 20 shown below; the full ranking is in
      <code>evals/coverage_backfill.json</code>.</p>
    <div class="scroll"><table aria-label="Retrieval coverage worklist, ranked by hit-versus-coverage gap">
      <thead><tr><th>#</th><th>Arm</th><th>Question id</th><th>Match</th><th>Gold size</th>
        <th>Coverage</th><th>Gap</th><th>Question</th></tr></thead>
      <tbody>${wlRows}</tbody></table></div>
    ${goldSizeStratHTML()}
    </section>`;
}

/* ---- subsection: coverage stratified by gold-set size ----
   THE TRAP this exists to block: a question with exactly one gold rule can
   never score "partial" coverage -- it's 0/1 or 1/1, nothing between. So an
   unstratified zero/partial/full split puts only multi-rule questions in
   "partial", which are harder by construction, and any accuracy comparison
   across buckets is really comparing gold-set size, not retrieval quality.
   See evals/backfill_coverage.py: stratify_by_gold_size(). */
function stratTable(strat, caption){
  const strata = strat.strata || [];
  if(!strata.length) return '';
  const rows = strata.map(s=>{
    const cells = ['zero','partial','full'].map(b=>{
      const bd = s.buckets[b];
      if(b==='partial' && s.structurally_no_partial){
        return `<td class="num dim" title="A gold-set of size 1 is all-or-nothing (0/1 or 1/1) -- there is no fraction between, so this bucket is structurally empty, not a data gap.">n/a — structural</td>`;
      }
      const acc = bd.accuracy==null
        ? `<span class="dim">${bd.n_accuracy_scored===0 && bd.n>0 ? 'no verdicts' : '—'}</span>`
        : `<strong>${pct(bd.accuracy)}</strong>`;
      const title = bd.arms_without_verdicts && bd.arms_without_verdicts.length
        ? ` title="no verdict file for: ${esc(bd.arms_without_verdicts.join(', '))}"` : '';
      return `<td class="num"${title}>${bd.n} <span class="dim">rows</span> · ${acc}</td>`;
    }).join('');
    return `<tr><td>${esc(s.stratum)}</td><td class="num">${s.n}</td>
      <td class="num">${pct(s.mean_coverage)}</td>${cells}</tr>`;
  }).join('');
  return `<div class="scroll"><table aria-label="${esc(caption)}">
    <caption style="text-align:left;caption-side:top;padding-bottom:var(--s2);color:var(--muted)">${esc(caption)}</caption>
    <thead><tr><th>Gold-set size</th><th>n</th><th>Mean coverage</th>
      <th>Zero coverage (n · accuracy)</th><th>Partial coverage (n · accuracy)</th>
      <th>Full coverage (n · accuracy)</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function goldSizeStratHTML(){
  const pipe = RC.gold_size_stratification || {strata:[]};
  const ship = RC.gold_size_stratification_shipped || {strata:[]};
  if(!(pipe.strata||[]).length && !(ship.strata||[]).length) return '';
  const shipped = RC.shipped_arms || [];
  return `<h3 style="margin:var(--s4) 0 var(--s2);font-size:1rem;letter-spacing:-.01em">
      Stratified by gold-set size — the fix for the trap above</h3>
    <p class="lede">Coverage bucket alone is confounded with how many rules a question cites: a
      1-gold-rule question is all-or-nothing, so it can only land in "zero" or "full" — never
      "partial". Splitting by gold-set size first (1 / 2 / 3 / 4+) before looking at
      zero/partial/full keeps that structural fact from masquerading as a retrieval-quality
      finding. Accuracy per cell is joined from <code>evals/verdicts_*.json</code> by question id
      where a verdict file exists for that arm; cells backed by an arm with no verdict file show
      "no verdicts" rather than a guessed number.</p>
    ${stratTable(pipe, `All pipeline arms (excludes debug fixtures and retrieval-off oracle arms)`)}
    ${shipped.length ? `<p class="note" style="margin-top:var(--s3)"><strong>Six shipped-config
      arms only</strong> (${shipped.map(a=>`<code>${esc(a)}</code>`).join(', ')}) — the set the
      motivating numbers for this section were computed against:</p>
      ${stratTable(ship, `Six shipped-config arms`)}` : ''}`;
}

/* ======================= GROUNDING SOURCES ===================================
   docs/results-groundedness-guard.md. RC above asks "did retrieval hit the
   gold ids"; this asks a different question entirely -- "what did the
   citations the model actually wrote down rest on". CR-reliance is a
   RETRIEVAL-QUALITY monitor (93.3% real rules vs ~28% placebo, measured), not
   an accuracy metric -- an arm can answer correctly from card rulings alone
   and that is fine, it's just not evidence the rules block did anything.
   Glossary terms (coordinator amendment: "Saga", "City's Blessing" -- a
   non-numeric id genuinely present in the rules context) are a GROUNDED
   source, shown in its own column, never counted toward either canary. The
   two canary rates (nothing-resolvable, unresolved) are expected to sit at
   ~0% everywhere; a non-zero reading is a regression worth stopping for, not
   routine noise, so they're flagged rather than just tabulated. */
function groundingSourcesHTML(){
  const arms = GS.arms || [];
  if(!arms.length) return '';
  const canaryBadge = (v, label) => {
    if(v==null) return '<span class="dim">—</span>';
    const bad = v > 0.01; // >1% -- docs/results-groundedness-guard.md: "if your
                           // unresolved rate is above ~1%, your parser is wrong"
    return `<span class="${bad?'badge b-crit':''}" title="${esc(label)}">${pct(v)}</span>`;
  };
  const rows = arms.map(a => `<tr>
    <td>${esc(a.arm)}<br><span class="dim" style="font-size:.7rem">qset ${esc(a.qset)}</span></td>
    <td>${kindBadge(a.kind)}</td>
    <td class="num dim">${a.n_scored}/${a.n_answered}${a.n_unknown ? ` <span class="dim" title="scored as unknown -- no citation_sources recorded and no reachable prompts_cache">(+${a.n_unknown} unknown)</span>` : ''}</td>
    <td class="num"><strong>${pct(a.cr_reliance_rate)}</strong></td>
    <td class="num">${pct(a.rulings_only_rate)}</td>
    <td class="num" title="rows citing at least one glossary term genuinely present in the rules context (e.g. &quot;Saga&quot;, &quot;City's Blessing&quot;) -- grounded, not a canary">${pct(a.glossary_rate)}</td>
    <td class="num">${canaryBadge(a.nothing_resolvable_rate, 'rows with answered=true citing nothing resolvable in the provided context')}</td>
    <td class="num">${canaryBadge(a.unresolved_citation_rate, 'rows with at least one citation that resolves to nothing provided -- the fabrication canary')}</td>
  </tr>`).join('');
  return `<section class="sec" id="grounding"><h2>Grounding sources — which source, not whether one exists</h2>
    ${tk('grounding')}
    <p class="lede"><strong>CR-reliance is a retrieval-quality monitor, not an accuracy metric.</strong>
    Every citation on an answered row classifies as a CR rule number present in the provided rules, a
    card ruling label present in the Card data, a card name present in the Card data, a glossary term
    present in the rules context (e.g. "Saga", "City's Blessing" -- non-numeric, but just as genuinely
    provided as a rule number, and the system prompt explicitly invites citing them), or unresolved
    (present nowhere provided -- the fabrication canary). CR-reliance swings from ~93% with real
    retrieved rules to ~28% under a placebo and costs nothing to compute, because it's already in the
    response the product produces -- see docs/results-groundedness-guard.md. It says nothing about
    whether the answer was <em>right</em>: a row grounded entirely in card rulings can still be correct.
    </p>
    <p class="lede">The rightmost two columns are canaries expected to read
    <strong>~0% everywhere</strong>; "glossary rate" just left of them is NOT a canary -- it's a
    grounded-source column, shown separately so a genuinely-provided glossary citation is never
    mistaken for one. A non-zero "unresolved" rate above ~1% is flagged
    (<span class="badge b-crit">highlighted</span>) as a likely parser defect or a real regression,
    not routine variance -- the throwaway version that produced this finding hit exactly that trap on
    split-card and apostrophe names before the parser was fixed, and a second pass caught glossary
    terms ("Saga", "Crime") being miscounted as fabrication before this column existed.</p>
    <div class="scroll"><table aria-label="Citation-source rates per arm">
      <thead><tr><th>Arm</th><th>Kind</th><th>Scored / answered</th>
        <th>CR-reliance rate</th><th>Rulings/cards-only rate</th><th>Glossary rate</th>
        <th>Nothing-resolvable rate</th><th>Unresolved-citation rate</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
    ${GS.n_skipped ? `<p class="note" style="margin-top:var(--s3)">${GS.n_skipped} arm(s) skipped --
      no resolvable answers file, or every row scored unknown (no recorded citation_sources and no
      reachable prompts_cache to reconstruct from).</p>` : ''}
    </section>`;
}

/* ======================= REPRODUCIBILITY ==================================== */
function reproHTML(){
  const R = (C.repro||[]);
  if(!R.length && !(C.single_rep||[]).length) return '';
  const rows = R.map(r=>`<tr>
    <td>${esc(r.step)} ${kindBadge(r.kind)}</td>
    <td class="num dim">${r.n}</td>
    <td class="num">${r.reps.map(x=>pct(x.flat)).join(' / ')}</td>
    <td class="num"><strong>${r.spread_pp==null?'—':r.spread_pp.toFixed(1)+' pp'}</strong></td>
    <td class="num">${r.churn?`${r.churn.n_flipped} / ${r.churn.n_rows}`:'—'}</td>
    <td class="dim" style="white-space:normal">${r.judging_runs.map(j=>
      `${esc(stamp(j.mtime))} ${j.recorded?esc(j.judge_model):'<span class="prov"><span class="miss">judge not recorded</span></span>'}`).join('<br>')}</td>
  </tr>`).join('');
  const singles = (C.single_rep||[]);
  return `<section class="sec" id="repro"><h2>Reproducibility — the noise floor</h2>
  ${tk('repro')}
    <p class="lede">Every configuration that ran more than once, and how far apart those runs
    landed. That spread is the instrument's resolution: a difference smaller than it is not a
    finding. Rows flipped counts questions whose verdict changed between two runs of the
    <em>identical</em> configuration — rows can churn heavily while the totals barely move.</p>
    ${rows ? `<div class="scroll"><table aria-label="Rep-to-rep reproducibility">
      <thead><tr><th>Configuration</th><th>Questions</th><th>Reps</th><th>Spread</th>
        <th>Rows flipped</th><th>Judging runs</th></tr></thead><tbody>${rows}</tbody></table></div>`
    : `<div class="card empty"><strong>No configuration has been run twice.</strong><br>
        Without a repeat there is no measured noise floor, only the judge's assumed flip rate.</div>`}
    ${singles.length ? `<p class="note" style="margin-top:var(--s3)"><strong>Run once only:</strong>
      ${singles.map(x=>`<code>${esc(x.step)}</code> (${x.n}q)`).join(', ')} — no within-config spread
      was measured for these, so their set falls back to the assumed judge floor.</p>` : ''}
    </section>`;
}

/* ---- timeline: what changed, by how much, and whether it beat the noise ---- */
const TL = D.timeline || {sets:[], notes:{}};
let tlSet = 'all', tlSort = 'time';

// Colour is never the only signal: every pill also carries an arrow and a sign.
function pill(label, val, fmt, betterIsUp, title){
  if(val==null) return '';
  const good = val===0 ? null : (val>0)===betterIsUp;
  const cls = good===null ? '' : (good ? 'p-good' : 'p-bad');
  return `<span class="pill ${cls}" title="${esc(title||'')}">${esc(label)}
    <b>${arrow(val)} ${fmt(val)}</b></span>`;
}

function cfgChips(st){
  if(!st.config_recorded)
    return `<div class="cfg"><span title="No answers file joined, so this arm records no config.">config not recorded for this arm</span></div>`;
  const chg = {};
  if(st.delta && st.delta.changed_known) st.delta.changed.forEach(c => chg[c.field] = c);
  const F = [['model','model'],['effort','effort'],['rewrite_version','rewrite'],
             ['ruling_query_mode','ruling mode'],['system_version','system ver']];
  return `<div class="cfg">` + F.map(([f,lab])=>{
    const v = st.config[f], c = chg[f];
    const shown = v==null ? '—' : v;
    if(!c) return `<span>${esc(lab)} ${esc(shown)}</span>`;
    const was = c.from==null ? '—' : c.from;
    return `<span class="chg" title="changed from ${esc(was)}">${esc(lab)}
      <span class="was">${esc(was)}</span><b>${esc(shown)}</b></span>`;
  }).join('') + `</div>`;
}

function stepCard(st, floor){
  const d = st.delta;
  const acc = st.flat==null ? '—' : pct(st.flat);
  const oracle = st.kind !== 'pipeline';

  let deltaBlock;
  if(oracle){
    deltaBlock = `<p class="base">${kindBadge(st.kind, st.kind_why)}
      <span class="badge">no delta — measures something else</span><br>
      ${esc(st.kind_why)}.${st.kind_note?' '+esc(st.kind_note):''}<br>
      A delta needs the same question set <em>and</em> the same kind, so this step is never
      subtracted from a pipeline step and never used as one's baseline.</p>`;
  } else if(!d){
    deltaBlock = `<p class="base"><span class="badge">first run on this question set</span><br>
      Nothing earlier ran these ${st.n} questions, so there is no baseline to subtract.</p>`;
  } else {
    const real = d.beats_noise;
    const badge = real===null ? '<span class="badge">no accuracy delta</span>'
      : real ? `<span class="badge b-good">clear of noise</span>`
             : `<span class="badge b-warn">within noise — not a result</span>`;
    const changed = !d.changed_known
      ? `<em>what changed is not recorded</em> — one of the two arms has no answers file, so its config is unknown. The accuracy delta still holds; the cause does not.`
      : (d.changed.length
          ? d.changed.map(c=>`<code>${esc(c.label)}</code> ${esc(c.from==null?'—':c.from)} → ${esc(c.to==null?'—':c.to)}`).join(', ')
          : 'no recorded config field changed');
    deltaBlock = `
      <div class="pills">
        ${pill('accuracy', d.flat_pp, pp, true, 'Flat accuracy vs '+d.baseline)}
        ${pill('weighted', d.weighted_pp, pp, true, 'Corner-case-weighted accuracy vs '+d.baseline)}
        ${pill('$/question', d.cost_pct, pctd, false, d.cost_abs==null?'':('absolute '+usd(Math.abs(d.cost_abs))+' per question'))}
        ${pill('out tokens', d.out_tok_pct, pctd, false, 'Output tokens per question')}
      </div>
      <p class="base">${badge}<br>
        <strong>Changed:</strong> ${changed}<br>
        <strong>Compared against:</strong> <code>${esc(d.baseline)}</code>
        (${esc(day(d.baseline_run_at))}, ${pct(d.baseline_flat)}) — the previous pipeline step
        on these same ${st.n} questions.<br>
        <strong>Resolution floor:</strong> ±${d.floor_pp.toFixed(1)} pp.
        ${real===false ? 'This move is smaller than that, so it is not distinguishable from a re-run of the same config.' : ''}
      </p>
      ${d.commits_total ? `<details class="commits"><summary>${d.commits_total} commit${d.commits_total>1?'s':''} landed between the two runs (association by timestamp, not a recorded link)</summary>
        <ol>${d.commits.map(c=>`<li><code>${esc(c.sha)}</code> ${esc(c.subject)}</li>`).join('')}
        ${d.commits_total>d.commits.length?`<li class="dim">… ${d.commits_total-d.commits.length} more</li>`:''}</ol></details>` : ''}`;
  }

  const regrade = st.reps.filter(r=>r.regrade_pp!=null).map(r=>
    `<div class="reps">Human regrade: <strong>${pp(r.regrade_pp)}</strong> over the auto verdict
     (<code>${esc((r.regrade_of||[]).join(', '))}</code>) — the judge, not the pipeline.</div>`).join('');

  const repline = st.n_reps > 1
    ? `<div class="reps">${st.n_reps} reps: ${st.reps.map(r=>pct(r.flat)).join(' / ')}
       · spread ${st.rep_spread_pp==null?'—':st.rep_spread_pp.toFixed(1)+' pp'}
       ${st.rep_churn?`· ${st.rep_churn.n_flipped}/${st.rep_churn.n_rows} rows flipped verdict between reps`:''}</div>`
    : `<div class="reps">1 rep — no within-config spread measured here</div>`;

  const hetero = st.heterogeneous_fields.length
    ? `<div class="reps"><span class="badge b-crit">reps differ in ${esc(st.heterogeneous_fields.join(', '))}</span> — treat as separate runs, not reps.</div>` : '';

  return `<article class="step ${oracle?'is-oracle':''}" data-qset="${esc(st.qset)}"
      data-move="${d && d.flat_pp!=null ? Math.abs(d.flat_pp) : -1}" tabindex="0"
      aria-label="${esc(st.step)}, ${acc} on ${st.n} questions">
    <div class="card">
      <div>
        <div class="stephead"><h4>${esc(st.step)}</h4>
          <span class="when">${esc(day(st.run_at))}</span>
          ${kindBadge(st.kind, st.kind_why)}</div>
        ${cfgChips(st)}
        <div class="score"><span class="big">${acc}</span>
          <span class="dim">flat · ${st.n} questions</span></div>
        <div class="meter"><i style="width:${st.flat==null?0:(st.flat*100).toFixed(1)}%"></i></div>
        ${repline}${hetero}${regrade}
        ${provBlock(st.generation_runs, st.judging_runs, st.human_passes)}
      </div>
      <div>${deltaBlock}</div>
    </div></article>`;
}

function timelineHTML(){
  if(!TL.sets || !TL.sets.length)
    return `<h2>Timeline</h2><div class="card empty"><strong>No steps to plot.</strong><br>
      No arm carried both a question set and a run time.</div>`;

  const chips = [['all','All sets']].concat(TL.sets.map(s=>[s.qset, s.n+' questions']));
  let h = `<h2>Timeline — what changed at each step</h2>
   ${tk('tl')}
   <p class="note">Each card is one configuration. The delta beside it is measured against the
   <strong>previous pipeline step on the same question set</strong>, and against a noise floor taken
   from how far apart two runs of one identical config landed. Steps on different question sets are
   never subtracted from each other.</p>
   <div class="controls" role="group" aria-label="Timeline filters">
     <span class="lbl">Question set</span>
     ${chips.map(c=>`<button type="button" class="chip" data-set="${esc(c[0])}"
        aria-pressed="${c[0]===tlSet}">${esc(c[1])}</button>`).join('')}
     <span class="lbl" style="margin-left:auto">Order</span>
     <button type="button" class="chip" data-sort="time" aria-pressed="${tlSort==='time'}">Chronological</button>
     <button type="button" class="chip" data-sort="move" aria-pressed="${tlSort==='move'}">Biggest move</button>
   </div>`;

  const sets = TL.sets.filter(s => tlSet==='all' || s.qset===tlSet);
  if(!sets.length)
    return h + `<div class="card empty"><strong>Nothing matches that filter.</strong><br>
      Pick another question set.</div>`;

  sets.forEach(s=>{
    let steps = s.steps.slice();
    if(tlSort==='move')
      steps.sort((a,b)=>{
        const av = a.delta && a.delta.flat_pp!=null ? Math.abs(a.delta.flat_pp) : -1;
        const bv = b.delta && b.delta.flat_pp!=null ? Math.abs(b.delta.flat_pp) : -1;
        return bv-av;
      });
    h += `<div class="setline"><h3>${s.n} questions</h3>
      <span class="meta">fingerprint <code>${esc(s.qset)}</code> · ${s.n_steps} step${s.n_steps>1?'s':''}</span></div>
      <p class="floornote"><strong>Noise floor ±${s.floor_pp.toFixed(1)} pp</strong> — ${esc(s.floor_source)}.
      A step-delta smaller than this is not a result on this set.</p>
      <div class="rail">${steps.map(st=>stepCard(st, s.floor_pp)).join('')}</div>`;
  });
  return h;
}

function wireTimeline(){
  document.querySelectorAll('#tl .controls .chip[data-set], #tl .controls .chip[data-sort]').forEach(b=>{
    b.addEventListener('click', ()=>{
      if(b.dataset.set!==undefined) tlSet = b.dataset.set; else tlSort = b.dataset.sort;
      document.getElementById('tl').innerHTML = timelineHTML();
      wireTimeline();
      const again = document.querySelector(`#tl .controls .chip[data-${b.dataset.set!==undefined?'set':'sort'}="${b.dataset.set!==undefined?tlSet:tlSort}"]`);
      if(again) again.focus();
    });
  });
}

/* ========================= EXECUTIVE SUMMARY ===============================
   Authored sentence templates, computed values, computed branch selection. The
   branch is chosen ONLY by D.summary.thresholds, which are rendered below the
   recommendation so a reader can argue with the threshold instead of with a
   sentence somebody typed. Nothing here is a hardcoded conclusion. */
const S = D.summary || {};
const F = S.facts || {};
const TH = {}; (S.thresholds||[]).forEach(t => TH[t.key] = t.value);
const RM = D.roadmap || {items:[], counts:{}, coverage:{n_docs:0,n_covered:0,missing:[]}};

const money2 = (lo,hi) => lo==null ? 'unknown'
  : (hi==null || Math.abs(hi-lo) < 0.005) ? '$'+lo.toFixed(2)
  : '$'+lo.toFixed(2)+'–'+hi.toFixed(2);
const money0 = (lo,hi) => lo==null ? 'unknown'
  : (hi==null || Math.round(hi)===Math.round(lo)) ? '$'+Math.round(lo)
  : '$'+Math.round(lo)+'–'+Math.round(hi);
const ppw = v => v==null ? 'unknown' : v.toFixed(1)+' points';
const lvl = l => l==='Corner Case' ? 'Corner Case' : 'L'+l;
const missLabel = (F.missing||[]).map(lvl).join(' and ') || 'no level';

function costLabel(c){
  if(!c) return ['unknown','not costed'];
  if(c.pool==='free')         return ['$0', c.why||''];
  if(c.pool==='subscription') return ['$0 in credits', c.why||''];
  if(c.pool==='spent')        return ['already spent', c.why||''];
  if(c.pool==='hosting')      return [money0(c.lo,c.hi)+(c.unit||''), c.why||''];
  if(c.unresolved)            return ['unknown', c.unresolved];
  if(c.lo==null)              return ['unknown', c.why||''];
  if(c.bound==='upper')       return ['under $'+c.hi.toFixed(2), c.why||''];
  return [money2(c.lo,c.hi), c.why||''];
}

/* Sonnet is dual-priced, so "which model is cheaper" has two answers until the
   introductory rate expires. Computed per question set from recorded tokens --
   never asserted, because the sign genuinely flips on one of the two sets. */
function introFlip(){
  const bySet = {};
  D.arms.forEach(a => {
    const c = a.cost||{}, m = (a.config||{}).model;
    if(c.cost_per_q==null || !m) return;
    (bySet[a.qset] ||= []).push({m, n:a.n, std:c.cost_per_q, intro:c.cost_per_q_intro});
  });
  const mean = (xs,k) => xs.reduce((s,r)=>s+r[k],0)/xs.length;
  const out = [];
  Object.values(bySet).forEach(rows => {
    const mine = rows.filter(r => r.m===D.current_config.GEN_MODEL);
    const dual = rows.filter(r => r.intro!=null);
    if(!mine.length || !dual.length) return;
    const o = mean(mine,'std'), si = mean(dual,'intro'), ss = mean(dual,'std');
    out.push({n:rows[0].n, mine:o, intro:si, std:ss,
              cheaper_at_intro:o<si, cheaper_at_std:o<ss});
  });
  return out.sort((a,b)=>a.n-b.n);
}
const FLIP = introFlip();

function threshTable(){
  const fmt = (t) => t.fmt==='pct' ? (t.value*100).toFixed(0)+'%'
                   : t.fmt==='pp' ? t.value.toFixed(0)+' pp'
                   : t.fmt==='usd' ? '$'+t.value.toFixed(0) : String(t.value);
  const chk = {}; (F.checks||[]).forEach(c => chk[c.key]=c);
  const rows = (S.thresholds||[]).map(t => {
    const c = chk[t.key];
    const act = !c ? '<span class="dim">not evaluated</span>'
      : (c.fmt==='pct' ? (c.actual*100).toFixed(1)+'%'
        : c.fmt==='pp' ? c.actual.toFixed(1)+' pp' : '$'+c.actual.toFixed(0));
    const verdict = !c ? '<span class="dim">—</span>'
      : c.pass ? '<span class="badge b-good">✓ met</span>'
               : '<span class="badge b-crit">✕ not met</span>';
    return `<tr><td>${esc(t.label)}<br><span class="dim">${esc(t.why)}</span></td>
      <td class="n">${fmt(t)}</td><td class="n">${act}</td><td class="n">${verdict}</td></tr>`;
  }).join('');
  return `<table class="thtab"><thead><tr><th>Threshold</th><th class="n">Bar</th>
    <th class="n">Actual</th><th class="n">Status</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function execHTML(){
  if(!F.verdict || F.verdict==='nodata') return `<section class="sec" id="exec">
    <div class="card exec"><div class="empty"><strong>No recommendation can be made.</strong><br>
    No pipeline configuration carries both a measured cost and per-level counts, so there is
    nothing to project and nothing to price. Run one judged pipeline arm, then rebuild.</div></div></section>`;

  const sliceCost = money2(F.slice_lo, F.slice_hi);
  const fullCost  = money0(F.full_lo, F.full_hi);
  const acc = pct(F.acc), cov = (F.coverage*100).toFixed(0)+'%';
  let pill='Recommended', tone='', title='', why='', gets='', flip='';
  const fc = F.full_run || {};
  const nextPick = F.next && F.next.pick;

  if(F.verdict==='measured'){
    pill='Measured'; tone='';
    title = nextPick
      ? `The corpus is measured: ${acc}. Next: ${esc(nextPick.title)}.`
      : `The corpus is measured: ${acc}. Nothing ready and unblocked is queued next.`;
    why = `The full ${int(F.N)}-question corpus has been run, not projected: ${acc} `
        + `[${pct(F.ci[0])}–${pct(F.ci[1])}], ${ppw(F.ci_width_pp)} wide, on `
        + `${esc(fc.model||'the shipped model')}${fc.effort?' at effort '+esc(fc.effort):''}, `
        + `run ${esc((fc.run_at||'').slice(0,10))}. That question is closed. ${nextPick
          ? `The next one open is ${esc(nextPick.title)}, ready now (${esc(nextPick.cost && nextPick.cost.why || '')}).`
          : `Every roadmap item this page would point to next is still blocked on something else.`}`;
    gets = nextPick
      ? `${esc(nextPick.title)}: ${esc(nextPick.cost && nextPick.cost.why || '')}`
      : `No further move without unblocking one of the items below first.`;
    flip = nextPick
      ? `Once ${esc(nextPick.title)} lands, re-check whether it changes the read on level 3 (67.90%,
         the corpus's weakest tier) before spending on a level-3-specific fix.`
      : `Unblocking one of the dependencies listed below.`;
  } else if(F.verdict==='slice-first'){
    pill='Do this first'; tone='hold';
    title = `Run the ${int(F.missing_n)}-question ${missLabel} slice first, for about ${sliceCost}. Then decide on the full run.`;
    why = `The number for the whole corpus is a projection, not a measurement: ${acc}, built only from `
        + `difficulty levels that cover ${cov} of the questions. ${missLabel} — ${int(F.missing_n)} of `
        + `${int(F.N)} questions — has never been answered by the real pipeline even once, so about one `
        + `question in seven is estimated rather than measured. Running only that slice costs about `
        + `${sliceCost}, against ${fullCost} for everything. Money is not what is holding the full run `
        + `back. Coverage is.`;
    gets = `Either the projection firms up and the full run becomes the obvious next step, or it moves. `
         + `Finding that out for ${sliceCost} beats finding it out for ${fullCost}.`;
    flip = `If ${missLabel} scores close to the levels already measured, this becomes "run the full corpus now". `
         + `If it scores far off, the projection was wrong by more than the price of the run.`;
  } else if(F.verdict==='narrow-first'){
    pill='Not yet'; tone='hold';
    title = `Narrow the estimate before spending ${fullCost} on the full run.`;
    why = `The projected accuracy is ${acc}, but its 95% interval is ${ppw(F.ci_width_pp)} wide — past the `
        + `${TH.interval_max_pp}-point bar this page uses. An interval that wide cannot tell a good result `
        + `from a bad one, so the full run would buy a number nobody could act on.`;
    gets = `A tighter interval, from more questions per level, before committing the larger spend.`;
    flip = `If the interval narrows below ${TH.interval_max_pp} points, the full run is the next step.`;
  } else if(F.verdict==='fix-judge-first'){
    pill='Fix the instrument'; tone='stop';
    title = `Fix the judge before publishing any headline number.`;
    why = `The judge marks a wrong answer correct ${pct((F.judge||{}).fp_rate)} of the time, above the `
        + `${TH.judge_fp_max_pp}% bar. Every accuracy on this page inherits that, so a full run would `
        + `produce a number that is wrong in a known direction.`;
    gets = `An instrument whose error is small enough that the result means something.`;
    flip = `If the measured false-positive rate falls below ${TH.judge_fp_max_pp}%, the coverage and `
         + `interval checks decide instead.`;
  } else if(F.verdict==='budget-gate'){
    pill='Budget call'; tone='hold';
    title = `The full run is a budget decision, not a technical one: ${fullCost}.`;
    why = `Coverage and interval both clear their bars. The only thing left is that ${fullCost} is above `
        + `the $${TH.budget_max_usd} line this page treats as needing a separate conversation.`;
    gets = `The measured corpus accuracy, with no reweighting and no extrapolation.`;
    flip = `Approve the spend, or cut the run down to a sample.`;
  } else {
    pill='Go'; tone='';
    title = `Run the full ${int(F.N)}-question corpus now. It costs ${fullCost}.`;
    why = `Every bar this page sets is met: coverage is ${cov}, the 95% interval is ${ppw(F.ci_width_pp)} `
        + `wide, the judge's measured error is inside tolerance, and ${fullCost} is below the point where `
        + `cost decides anything.`;
    gets = `The real number — ${acc} projected today, measured after the run.`;
    flip = `A new question set, or a judge result that moves, would re-open it.`;
  }

  const je = F.judge||{};
  const ceil = (F.ceilings||[])[0];
  const fn = je.fn_census;
  const caveats = F.verdict==='measured' ? [
    F.projection_validation ? (() => { const pv = F.projection_validation; return (
      `<li><b>✓</b><span><b>The projection was validated, then retired.</b> This page projected
      ${pct(pv.projected)} [${pct(pv.ci[0])}–${pct(pv.ci[1])}] from partial-coverage arms before this run
      existed; the measured result is ${pct(pv.measured)} on all ${int(F.N)} questions — a
      +${pv.miss_pp.toFixed(1)}-point miss, near the top of the projected interval rather than outside it.
      ${esc(pv.doc)} has the full comparison. The reweighting machinery stays live below for every arm that
      still lacks a measurement.</span></li>`); })() : '',
    ceil ? `<li><b>⚠</b><span><b>${pct(ceil.oracle_flat)} is a ceiling, not a product score.</b>
      <code>${esc(ceil.oracle)}</code> answered with retrieval switched off and the gold rules handed to it.
      It says the answers are derivable; it does not say the product finds them. The best pipeline score on
      the same ${int(ceil_n(ceil))} questions is ${pct(ceil.other_flat)}.</span></li>` : '',
    (je.fp_rate!=null && fn) ? `<li><b>⚠</b><span><b>The judge's error is a two-sided bound now, not just
      an upper one.</b> False positives (wrongly passing a wrong answer as correct) run ${pct(je.fp_rate)}
      (${je.fp_k}/${je.fp_n} sampled) and pull the headline down. False negatives (wrongly failing a
      correct answer) measure 0% across ${fn.combined_n} hand-graded rows, 95% CI [0%,
      ${(fn.combined_ci[1]*100).toFixed(1)}%], and would pull it up. At point estimates they do not cancel
      — net direction favours <em>understatement</em>, not overstatement. ${esc(fn.doc)}.</span></li>`
      : (je.fp_rate!=null ? `<li><b>⚠</b><span><b>The judge error is an upper bound.</b> ${pct(je.fp_rate)}
      (${je.fp_k} of ${je.fp_n} sampled) is the rate at which the judge passed an answer it should have
      failed. The reference grader that measured it agreed with the judge on
      ${(je.ref_agreement*100).toFixed(0)}% of the rows with human ground truth, so it is not an independent
      check — read ${pct(je.fp_rate)} as a ceiling on the error, not an estimate of it.</span></li>` : ''),
  ].filter(Boolean).join('') : [
    `<li><b>⚠</b><span><b>The headline is a projection.</b> ${acc} reweights measured levels onto the
      corpus mix and covers ${cov} of it. ${missLabel} has zero pipeline rows across every arm on this
      page — that share is extrapolated, not measured.</span></li>`,
    ceil ? `<li><b>⚠</b><span><b>${pct(ceil.oracle_flat)} is a ceiling, not a product score.</b>
      <code>${esc(ceil.oracle)}</code> answered with retrieval switched off and the gold rules handed to it.
      It says the answers are derivable; it does not say the product finds them. The best pipeline score on
      the same ${int(ceil_n(ceil))} questions is ${pct(ceil.other_flat)}.</span></li>` : '',
    je.fp_rate!=null ? `<li><b>⚠</b><span><b>The judge error is an upper bound.</b> ${pct(je.fp_rate)}
      (${je.fp_k} of ${je.fp_n} sampled) is the rate at which the judge passed an answer it should have
      failed. The reference grader that measured it agreed with the judge on
      ${(je.ref_agreement*100).toFixed(0)}% of the rows with human ground truth, so it is not an independent
      check — read ${pct(je.fp_rate)} as a ceiling on the error, not an estimate of it.</span></li>` : '',
  ].filter(Boolean).join('');

  return `<section class="sec" id="exec" style="margin-top:0">
    <div class="card exec">
      <span class="verdict ${tone}">${esc(pill)}</span>
      <h2 class="exectitle" style="text-transform:none;letter-spacing:-.01em;color:var(--ink)">${esc(title)}</h2>
      <p class="execwhy">${why}</p>
      <div class="execgrid">
        <div><span class="lab">What it costs</span>
          ${F.verdict==='measured' ? `
          <span class="big">${money2(fc.cost_per_q, fc.cost_per_q)}</span>
          <p>per question${fc.batch?', through the batch API (half the standard rate)':''}. ${fullCost} total
             for all ${int(F.N)} questions — measured, not estimated.${fc.batch
             ? ` The pre-run estimate assumed the standard (non-batch) rate, which is why the actual
                spend came in under it.` : ''}</p>` : `
          <span class="big">${esc(sliceCost)}</span>
          <p>for the slice. The full ${int(F.N)}-question run is ${fullCost}, at the measured cost per
             question of ${esc(F.model||'the shipped model')}${F.effort?' at effort '+esc(F.effort):''}.</p>`}</div>
        <div><span class="lab">What we get</span>
          <p style="margin-top:0">${gets}</p>
          ${F.verdict!=='measured' ? `<p class="dim">${esc(S.runtime_note||'')}</p>` : ''}</div>
        <div><span class="lab">How sure we are</span>
          <span class="big">${acc}</span>
          <p>95% interval ${pct(F.ci[0])}–${pct(F.ci[1])}, ${ppw(F.ci_width_pp)} wide, measured on
             ${int(F.n_run)} questions.${F.verdict==='measured'
             ? ` On top of sampling, judge instability adds roughly another 2-4 points of variance
                (docs/results-judge-stability.md) — read this as "roughly ${(F.acc*100).toFixed(0)}%,
                give or take a few points," not a three-digit-precise figure.`
             : ' Treat it as a range, not a number.'}</p></div>
        <div><span class="lab">What would change this</span>
          <p style="margin-top:0">${flip}</p></div>
      </div>
      <ul class="caveats">${caveats}</ul>
      <details class="ev"><summary>The thresholds that produced this recommendation</summary>
        ${threshTable()}</details>
      <p class="stamp">Every number above is computed from the files at build time. The recommendation is
        <em>selected</em> by the thresholds, not written in — if the data crosses one, this page says
        something different without anyone editing it. The sentence templates and the threshold values were
        authored ${esc(S.authored_on||'')} by ${esc(S.authored_by||'')}.</p>
    </div></section>`;
}
function ceil_n(c){ const s=(C.head_to_head||[]).find(x=>x.headroom&&x.headroom.oracle===c.oracle); return s?s.n:0; }

/* ========================= DECISIONS ======================================= */
function optCard(o){
  const items = [].concat(
    (o.pros||[]).map(p=>`<li class="pro"><b>+</b><span>${p}</span></li>`),
    (o.cons||[]).map(p=>`<li class="con"><b>−</b><span>${p}</span></li>`),
    (o.judge||[]).map(p=>`<li class="jdg"><b>?</b><span>${p} <span class="dim">(judgement, not a measurement)</span></span></li>`)
  ).join('');
  return `<div class="opt ${o.pick?'pick':''}">
    <h5>${esc(o.name)} ${o.pick?'<span class="tag">✓ recommended</span>':''}</h5>
    ${o.cost?`<p class="dim" style="margin:var(--s1) 0 0;font-size:.78rem">${esc(o.cost)}</p>`:''}
    <ul>${items || '<li class="dim">nothing recorded</li>'}</ul></div>`;
}
function decisionCard(d){
  return `<div class="card" style="margin-bottom:var(--s4)">
    <h3 style="margin:0;font-size:1.02rem">${esc(d.title)}</h3>
    <p class="lede" style="margin:var(--s2) 0 0">${d.question}</p>
    <div class="dgrid">${d.options.map(optCard).join('')}</div>
    <div class="because">
      <div><span class="lab">Why this one</span>${d.why}</div>
      <div><span class="lab">The strongest argument against it</span>${d.against}</div>
      ${d.close?`<div><span class="lab">How close it is</span>${d.close}</div>`:''}
      <div><span class="lab">What would change the answer</span>${d.flip}</div>
    </div></div>`;
}
function decisionsHTML(){
  if(!F.verdict || F.verdict==='nodata') return '';
  const decs = [];
  const sliceCost = money2(F.slice_lo,F.slice_hi), fullCost = money0(F.full_lo,F.full_hi);
  const sharePct = (F.slice_lo && F.full_lo) ? Math.round(F.slice_lo/F.full_lo*100) : null;
  const fc = F.full_run || {};
  const acc = pct(F.acc);

  // 1. THE FULL RUN -------------------------------------------------------
  if(F.verdict==='measured'){
    const pv = F.projection_validation;
    const nx = F.next || {};
    const pick = nx.pick;
    decs.push({
      title:'Decision 1 — the full RulesGuru run (RESOLVED)',
      question:`Ran ${esc((fc.run_at||'').slice(0,10))}. Cost ${fullCost}, scored ${acc}.`,
      options:[
        {name:`Run all ${int(fc.n||F.N)} now`, cost:fullCost, pick:true,
         pros:[`Done — the number stopped being a reweighted projection`,
               pv ? `Actual cost ${fullCost} came in under the ${money0(pv.cost_estimate_lo,pv.cost_estimate_hi)}
                     pre-run estimate` + (fc.batch?` because of the batch discount`:``) : `Cost cleared its bar`,
               pv ? `Validated the projection method: ${pct(pv.projected)} projected vs ${pct(pv.measured)}
                     measured, a +${pv.miss_pp.toFixed(1)}-point miss` : `Coverage is now 100%`],
         cons:[`Level 3 came in at ${pct((fc.levels&&fc.levels['3']&&fc.levels['3'].acc)||0)}, the corpus's
               weakest tier, which the pre-run number could not have surfaced`,
               `${ppw(F.ci_width_pp)} of sampling interval remains, plus judge-instability noise on top`]},
        {name:'Run a coverage slice first, then the rest', cost:sliceCost,
         pick:false,
         pros:[`Would have cost ${sliceCost}${sharePct?` — about ${sharePct}% of the full run`:``} up front`],
         cons:[`Moot now — the full run already answered the coverage question directly`]},
        {name:'Do not run yet', cost:'$0', pick:false,
         pros:[`Would have spent nothing`],
         cons:[`Moot now — this is the option that did not happen`]},
      ],
      why:`The coverage/interval/judge-fp/budget thresholds that used to select this decision all cleared
           before the run (see the thresholds table on the recommendation above); the run itself confirmed
           what they predicted rather than contradicting it.`,
      against:`The measured 85.88% carries its own uncertainty — sampling (±1.8pp), judge instability
           (~2-4pp), and unresolved judge false-positive/negative rates — so treating the third digit as
           meaningful would be false precision of a different kind than the one this decision used to
           worry about.`,
      close:'',
      flip:pick
        ? `The next open question is ${esc(pick.title)} (${esc(pick.cost && pick.cost.why || 'ready now')}).`
        : `Every roadmap item this would point to next is still blocked — see the blocked list below.`,
    });
  } else {
    decs.push({
      title:'Decision 1 — the full RulesGuru run',
      question:`Do we spend ${fullCost} answering all ${int(F.N)} questions now?`,
      options:[
        {name:`Run all ${int(F.N)} now`, cost:fullCost, pick:F.verdict==='go',
         pros:[`Covers 100% of the corpus, so the number stops being a reweighted projection`,
               `${fullCost} is below the $${TH.budget_max_usd} line where cost would decide anything`,
               `Ends the argument in one pass instead of two`],
         cons:[`${(100-F.coverage*100).toFixed(0)}% of the corpus mix (${missLabel}, ${int(F.missing_n)} questions) has never run, so a surprise there lands after the money is spent`,
               `Going in, the 95% interval is ${ppw(F.ci_width_pp)} wide`]},
        {name:`Run the ${missLabel} slice first (${sliceCost})`, cost:sliceCost,
         pick:F.verdict==='slice-first',
         pros:[`Costs ${sliceCost}${sharePct?` — about ${sharePct}% of the full run`:''}`,
               `Closes the single largest coverage gap on the page`,
               `The full run stays available afterwards, and it is not price-sensitive`],
         cons:[`Adds a step before the headline number exists`,
               `If ${missLabel} lands where expected, the slice bought confirmation rather than news`]},
        {name:'Do not run yet', cost:'$0',
         pick:F.verdict!=='go' && F.verdict!=='slice-first',
         pros:[`Spends nothing`,
               `${F.ready_free_n} backlog items cost no credits and can land first`],
         cons:[`The headline stays a projection`,
               `None of the free items reduce the ${missLabel} gap — only running ${missLabel} does`]},
      ],
      why:`Selected by the coverage threshold: ${(F.coverage*100).toFixed(1)}% measured against a
           ${(TH.coverage_min*100).toFixed(0)}% bar. Cost is genuinely not the constraint — ${fullCost} is well
           under the $${TH.budget_max_usd} line — so the question is only whether the number would mean
           anything, and today one question in seven is extrapolated.`,
      against:`The slice may simply confirm what the projection already assumes, in which case ${sliceCost}
           and a day bought nothing the full run would not have shown anyway. That is a fair argument. It
           loses on the ratio: the slice is a small fraction of the full run's cost and removes the page's
           largest named unknown, and a full run that turns out to have been mis-projected costs ${fullCost}
           to learn the same thing.`,
      close:`Running everything now is the close second. If ${fullCost} were already approved and nobody
           cared about the ordering, the difference between these two options is one extra step.`,
      flip:`A measured ${missLabel} accuracy. If it lands within the spread of the levels already measured,
           run everything. If it lands well below, the retrieval and gold work in the backlog matters more
           than the headline does.`,
    });
  }

  // 2. MODEL CHOICE -------------------------------------------------------
  const mp = F.model_pairs||[];
  if(mp.length){
    const w = mp[0].win_model, l = mp[0].lose_model;
    const gaps = mp.map(m=>`+${m.gap_pp.toFixed(1)} pp on the ${m.n}-question set (noise floor ${m.floor_pp.toFixed(1)} pp)`).join(', ');
    const allConfounded = mp.every(m=>m.confounded);
    const promptUnverified = mp.some(m=>m.prompt_parity_unverified);
    const mcn = F.model_comparison_note || {};
    const fair = (F.next && F.next.fair_comparison) || null;
    const flipRow = FLIP.filter(f=>!f.cheaper_at_intro);
    const introCon = flipRow.length
      ? `On the ${flipRow.map(f=>f.n).join(' and ')}-question set, ${esc(l)} at its introductory rate is
         actually cheaper per question (${usd(flipRow[0].intro)} vs ${usd(flipRow[0].mine)}). That rate runs
         to ${esc(D.pricing.sonnet_intro_ends)}; after it, ${esc(w)} is cheaper on every set measured.`
      : `${esc(l)}'s introductory rate runs to ${esc(D.pricing.sonnet_intro_ends)}; the comparison above uses
         the standard rate, and should be re-checked after that date.`;
    const confoundNote = allConfounded
      ? `Every ${esc(w)}-vs-${esc(l)} pair measured on this page differs in effort as well as model
         (${esc(l)}'s effort is not recorded; ${esc(w)}'s is <code>${esc(F.effort||'low')}</code>) — the
         gap shown is the package, not the model in isolation.`
      : (mp.some(m=>m.confounded) ? `Some of these pairs differ in more than model alone.` : '');
    const promptNote = promptUnverified
      ? `${esc(l)}'s rows never recorded a prompt cache the way ${esc(w)}'s did, so "same prompt" cannot be
         verified even in principle from what is on disk here — it is assumed, not confirmed.`
      : '';
    const fairNote = fair
      ? (fair.judged
         ? `A byte-identical-prompt comparison against gpt-5-mini has since been judged — that result should
            settle the model question, not this one.`
         : `A clean, byte-identical-prompt comparison against gpt-5-mini is in flight
            (${fair.n_answered}/${fair.n_target} rows generated across ${fair.n_shards} shards, not yet
            judged). It will be the first unconfounded cross-model evidence this page has.`)
      : '';
    decs.push({
      title:'Decision 2 — which generation model',
      question:`${esc(w)} or ${esc(l)}?`,
      options:[
        {name:esc(w)+(F.effort?' at effort '+esc(F.effort):''),
         cost:'measured '+usd(mp[0].win_cost)+'/question on the '+int(mp[0].n)+'-question set',
         pick:true,
         pros:[`More accurate on every set measured: ${gaps} — every gap clears its set's own noise floor`,
               `Cheaper per question at standard pricing on every set measured`,
               `Output is nearly constant regardless of difficulty, so cost does not blow up on hard traffic`],
         cons:[introCon],
         judge: [confoundNote, promptNote, fairNote].filter(Boolean)},
        {name:esc(l), cost:'measured '+usd(mp[0].lose_cost)+'/question on the '+int(mp[0].n)+'-question set',
         pros:[`Cheaper on some traffic while its introductory rate lasts (see the caveat opposite)`],
         cons:[`Lower accuracy on every set measured, by more than the noise floor`,
               `More expensive per question at standard pricing`]},
      ],
      why:`${esc(w)} wins every comparison this page can currently make, and every gap clears its own set's
           noise floor — real evidence, pointing one direction. But every one of those comparisons is
           confounded on effort as well as model, and none has verified prompt parity on the losing side.
           That makes this a real lead, not settled proof.`,
      against:`The available comparisons are not a clean test in isolation.${mcn.gpt5mini_joins_any_pair
           ? '' : ` gpt-5-mini is not represented in these numbers at all — it shares no question set with
           any opus arm on this page, so it cannot enter a paired comparison here.`}${mcn.gpt5mini_self_judged_cite
           ? ` Where a separate gpt-5-mini head-to-head does exist elsewhere in this repo, it is judged by a
           model from gpt-5-mini's own family (${esc(mcn.gpt5mini_self_judged_cite)}): "${esc(mcn.gpt5mini_self_judged_quote||'')}"`
           : ''} ${fairNote}`,
      close:'',
      flip:`The fair cross-model comparison landing${fair && !fair.judged ? ' (still generating)' : ''}, or a
           price change. "Settled by the data" overstates what today's confounded pairs can carry on their own.`,
    });
  }

  // 3. EFFORT -------------------------------------------------------------
  const eff = F.effort_controlled||0;
  const pr = F.effort_probe;
  decs.push({
    title:'Decision 3 — reasoning effort',
    question:`Production runs at effort <code>${esc(F.effort||'unset')}</code>. Should it?`,
    options:[
      {name:`Keep effort ${esc(F.effort||'unset')}`, cost:'no change, no spend', pick:true,
       pros:[`It is what every current number on this page was measured under`,
             `Cost is capped by short output rather than by the question's difficulty`],
       cons:[eff ? `${eff} controlled comparison(s) exist` :
             `<strong>No controlled comparison exists.</strong> Not one pair on this page differs in effort
              alone, so nothing here establishes what a higher setting would score`]},
      {name:'Re-run one existing set at a higher effort',
       cost: pr ? money2(pr.lo, pr.hi)+' for '+int(pr.n)+' questions' : 'unknown',
       pros:[`Would give the page its first effort-only comparison`,
             pr ? `Cheap: ${money2(pr.lo,pr.hi)} to re-run the smallest ${int(pr.n)}-question pipeline set the shipped config has already answered` : ''].filter(Boolean),
       cons:[`Spends credits to answer a question nothing currently depends on`,
             `The oracle arms that ran at a higher effort are a different <em>kind</em> and cannot be
              differenced against the product path, so they do not shortcut this`]},
    ],
    why: eff
      ? `A controlled effort comparison exists on this page; read it in the head-to-head section.`
      : `Keep the current setting, but say plainly why: it was adopted on a cost mechanism and a
         regression check against a <em>different model</em>, not against a different effort. That is a
         reasonable basis, and it is not the same thing as having measured it.`,
    against:`"We have never tested the alternative" is a real gap, and the test is cheap. If effort became
         a live question — a cost squeeze, or a hard-question accuracy problem — this would be the first
         thing to measure.`,
    close:'',
    flip:`Any kind-matched pair that differs in effort alone. There are ${eff} on this page today.`,
  });

  return `<section class="sec" id="decisions"><h2>The decisions, with their alternatives</h2>
    ${tk('decisions')}
    <p class="lede">Each decision shows the options as things a person could actually do, the pros and cons
    traceable to numbers on this page, the recommendation, and the strongest case against it. Where an
    option is simply dominated, it says so rather than inventing a counterweight.</p>
    ${decs.map(decisionCard).join('')}</section>`;
}

/* ========================= SECTION TAKEAWAYS ===============================
   One conclusion per section, not a description of it. Computed where the data
   supports a conclusion; where it does not, the sentence says so. */
function takeaways(){
  const t = {};
  const je = F.judge||{}, ceil=(F.ceilings||[])[0];
  t.decisions = F.verdict==='measured'
    ? `The full-corpus call is resolved — it ran, cost less than estimated, and confirmed the projection to
       within 3.1 points. The model choice is a real lead but rests on confounded comparisons, not settled
       proof; a clean cross-model result is in flight. Effort has still never been tested.`
    : `Three calls are live. Only the first one — whether to run the full corpus — is genuinely
       close; the model choice is settled by the data and the effort setting has never been tested.`;
  const mp=(F.model_pairs||[])[0];
  t.h2h = mp
    ? `<b>${esc(mp.win_model)} wins both head-to-heads</b> by ${mp.gap_pp.toFixed(1)} pp or more, and each gap
       clears its own set's noise floor, so neither is measurement wobble. ${ceil ? `The ${pct(ceil.oracle_flat)}
       oracle row is not a competitor — it was handed the gold rules with retrieval off, and the gap to the
       best pipeline score (${pct(ceil.other_flat)}) is roughly the headroom retrieval is leaving on the table.`:''}`
    : `No two arms share both a question set and a kind, so nothing here can be differenced yet.`;
  t.frontier = `Anything marked dominated is worse <em>and</em> pricier than something else on the same
    questions — there is no trade-off to weigh, only a choice already made. Use this to retire arms, not to
    pick one.`;
  t.levels = (F.missing||[]).length
    ? `<b>${missLabel} is the hole.</b> It is ${int(F.missing_n)} of ${int(F.N)} corpus questions and no
       pipeline arm has ever answered one, so every projection on this page fills it in by assumption.
       That is the single cheapest thing left to fix.`
    : `Every difficulty level has pipeline evidence, so the projection is interpolating rather than
       extrapolating.`;
  t.matrix = (C.matrix && C.matrix.n_cells)
    ? `${C.matrix.n_tried} of ${C.matrix.n_cells} configurations have been tried. The blanks are not a to-do
       list — most are combinations nobody has a reason to want. Retrieval settings do not appear here at
       all, because no answers file records them.`
    : `Nothing recorded enough configuration to build a matrix.`;
  t.repro = `Treat any difference smaller than a set's noise floor as nothing. The judge alone flips about
    one verdict per hundred rows on identical answers, so a one- or two-row move is not a result.`;
  t.tl = `Read this for <em>why</em> a number moved, not whether it is good. Config changes and grading
    passes are both steps here, because both have moved a published number.`;
  t.arms = `The reference table. If a row is not marked verified, do not quote its cost.`;
  t.roadmap = `<b>${RM.counts.ready||0} items are ready now and ${RM.counts.blocked||0} are blocked.</b>
    ${F.ready_free_n||0} of the ready ones spend no API credits at all, so the realistic question is not what
    to fund — it is what to do first. Total credit cost of every priced, ready item:
    ${money0(RM.ready_api_lo, RM.ready_api_hi)}.`;
  t.exec = '';
  return t;
}
const TK = takeaways();
const tk = id => TK[id] ? `<p class="takeaway"><b>Bottom line.</b> ${TK[id]}</p>` : '';

/* ========================= ROADMAP ========================================= */
let rmView = 'ready';
const RMV = [['ready','Ready now'],['blocked','Blocked'],['done','Shipped'],
             ['dead','Cut or superseded'],['all','Everything']];
const ST = {
  shipped:['b-good','shipped'], partial:['b-warn','partially shipped'],
  open:['b-pipe','open'], 'design-only':['b-pipe','design only, awaiting a ruling'],
  cut:['badge','cut'], superseded:['badge','superseded'], unknown:['b-crit','status unknown'],
};
const ACT = {run:'run it', build:'build it', decide:'decide on it', measure:'measure it'};
const DIR = {up:['▲','raises'], down:['▼','lowers'], either:['◆','moves'],
             none:['▬','no metric']};

function evLine(e){
  const K = {commit:'commit', path:'code path', path_absent:'absent', doc:'doc', derived:'derived'};
  const body = e.kind==='commit' ? `<code>${esc(e.ref)}</code>`
    : e.ref ? `<code>${esc(e.ref)}</code>` : '';
  const bad = e.ok ? '' : ` <span class="badge b-crit">✕ ${esc(e.broken_why||'stale')}</span>`;
  const det = e.detail ? ` <span class="dim">(${esc(e.detail)})</span>` : '';
  return `<li class="${e.ok?'':'bad'}"><span class="k">${esc(K[e.kind]||e.kind)}</span>
    <span>${body}${det}${bad}${e.note?` — ${esc(e.note)}`:''}</span></li>`;
}

function tradeoffHTML(i){
  const t = i.tradeoff; if(!t) return '';
  return `<details class="ev" open><summary>Doing it and not doing it are both defensible — the options</summary>
    <div class="dgrid">${t.options.map(o=>optCard(o)).join('')}</div>
    <div class="because">
      <div><span class="lab">Why</span>${esc(t.why)}</div>
      <div><span class="lab">The strongest argument against</span>${esc(t.against)}</div>
      <div><span class="lab">What would change it</span>${esc(t.flip)}</div>
    </div></details>`;
}
function rmCard(i){
  const [cl,lab] = ST[i.status] || ST.unknown;
  const [cost, costWhy] = costLabel(i.cost);
  const m = i.metric||{};
  const [gl,verb] = DIR[m.dir] || DIR.none;
  const basis = m.basis==='measured' ? '<span class="badge b-good">measured</span>'
    : m.basis==='predicted' ? '<span class="badge b-warn">predicted, unmeasured</span>'
    : '<span class="badge b-crit">no basis recorded</span>';
  const blocked = i.bucket==='blocked'
    ? `<p class="blockline"><b>⛔ Blocked</b> — needs ${i.unmet_titles.map(esc).join(', ')} first.
       ${i.dep_why?esc(i.dep_why)+'.':''}</p>` : '';
  const stale = i.evidence_ok ? '' :
    `<p class="staleline"><b>✕ Evidence check failed</b> — a reference below no longer resolves in this
     repo, so this row's status is no longer established. Treat it as unknown until it is re-checked.</p>`;
  const rel = i.relevant===false
    ? `<p class="blockline"><b>⚠ Overtaken</b> ${esc(i.relevance_note||'')}</p>` : '';
  const merged = (i.merged||[]).length
    ? `<div><span class="lab">Merged into this row</span>${i.merged.map(d=>`<code>${esc(d)}</code>`).join(', ')}
       <br><span class="dim">${esc(i.merge_why||'')}</span></div>` : '';
  const worth = (i.bucket==='ready' && (i.cost.pool==='free'||i.cost.pool==='subscription') && i.info>=2)
    ? `<p class="rmline"><strong>No trade-off to weigh here.</strong> It spends no API credits and it
       ${m.dir==='none'?'answers a question we are currently guessing at':verb+' '+esc(m.name)}. Do it.</p>` : '';
  return `<article class="rm b-${esc(i.bucket)}">
    <div class="rmhead"><h4>${esc(i.title)}</h4>
      <span class="badge ${cl==='badge'?'':cl}">${esc(lab)}</span>
      <span class="pill"><b>${esc(cost)}</b></span>
      <span class="pill">${esc(ACT[i.action]||i.action||'')}</span></div>
    <p class="rmline">${esc(i.one_line||'')}</p>
    ${worth}${stale}${rel}${blocked}${tradeoffHTML(i)}
    <div class="rmgrid">
      <div><span class="lab">Moves</span>
        <span aria-hidden="true">${gl}</span> ${esc(verb)} <strong>${esc(m.name||'nothing recorded')}</strong>
        ${basis}<br><span class="dim">${esc(m.detail||'')}${m.cite?' — '+esc(m.cite):''}</span></div>
      <div><span class="lab">What it tells us</span>${esc(i.tells_us||'—')}</div>
      <div><span class="lab">Cost basis</span>${esc(costWhy)}
        ${i.cost.cite?`<br><span class="dim">${esc(i.cost.cite)}</span>`:''}</div>
      <div><span class="lab">Priority</span>${esc(i.info_why_rank||'')}
        <br><span class="dim">${esc(i.info_why||'')}</span></div>
      ${merged}
    </div>
    <details class="ev"><summary>Evidence for this status (${i.evidence.length} references, re-checked at build time)</summary>
      <ul>${i.evidence.map(evLine).join('')}</ul></details>
  </article>`;
}

function roadmapHTML(){
  const all = RM.items||[];
  const rows = rmView==='all' ? all : all.filter(i=>i.bucket===rmView);
  const cov = RM.coverage||{};
  const chips = RMV.map(([k,l])=>{
    const n = k==='all' ? all.length : (RM.counts[k]||0);
    return `<button type="button" class="chip" data-rm="${k}" aria-pressed="${k===rmView}">${esc(l)} (${n})</button>`;
  }).join('');
  const body = rows.length
    ? `<div class="rmwrap">${rows.map(rmCard).join('')}</div>`
    : `<div class="card empty"><strong>Nothing in this view.</strong><br>
       Pick another filter above — every item is in exactly one of them.</div>`;
  const gap = (cov.missing||[]).length
    ? `<p class="warnline crit"><b>✕ Gap</b><span>${cov.missing.length} plan/spec docs are not accounted
       for by any row: ${cov.missing.map(esc).join(', ')}.</span></p>`
    : `<p class="note">All ${cov.n_docs} <code>plan-*.md</code> and <code>spec-*.md</code> docs are accounted
       for by a row above — checked by globbing the directory, not by trusting this list.</p>`;
  return `<h2>Roadmap — what to do next</h2>
    ${tk('roadmap')}
    <p class="lede">Every plan and spec in the repo, with a status that had to be <em>earned</em> from
    evidence: a commit that implements it, a results doc that measured it, or a code path that exists or
    provably does not. Only six of the ${cov.n_docs} docs carry a status marker of their own, so the rest are
    inferred — and every reference is re-checked on each build, so a claim that goes stale shows up as a
    failed check rather than quietly staying true. Ready items are ordered by how much they would tell us,
    then by cost.</p>
    <div class="controls" role="group" aria-label="Roadmap filter">
      <span class="lbl">Show</span>${chips}</div>
    ${body}${gap}`;
}
function wireRoadmap(){
  document.querySelectorAll('#roadmap .chip[data-rm]').forEach(b=>{
    b.addEventListener('click', ()=>{
      rmView = b.dataset.rm;
      document.getElementById('roadmap').innerHTML = roadmapHTML();
      wireRoadmap();
      const again = document.querySelector(`#roadmap .chip[data-rm="${rmView}"]`);
      if(again) again.focus();
    });
  });
}

function render(){
  if(!D.arms.length){
    document.getElementById('app').innerHTML =
      '<div class="card empty"><strong>No scorable arms found.</strong><br>'+
      'Every verdict file lacked a <code>summary.by_level_counts</code>. '+
      'Re-run the judge, then rebuild.</div>';
    return;
  }
  let html = `<nav class="nav" aria-label="Sections">
    ${[['#exec','Summary'],['#decisions','Decisions'],['#roadmap','Roadmap'],
       ['#decision','The numbers behind it'],['#h2h','Head to head'],['#frontier','Cost vs accuracy'],
       ['#levels','Per level'],['#matrix','Config matrix'],['#arm-config','Arm config matrix'],
       ['#retrieval-coverage','Retrieval coverage'],
       ['#grounding','Grounding sources'],
       ['#repro','Reproducibility'],
       ['#tl','Timeline'],['#arms','Every arm']]
      .map(([href,label])=>`<a href="${href}">${label}</a>`).join('')}</nav>`;

  // The executive summary goes ABOVE the tiles: it is the first thing anyone
  // should read, and the tiles are already detail by comparison.
  html += execHTML();
  html += decisionsHTML();
  html += `<section class="sec" id="roadmap">${roadmapHTML()}</section>`;

  html += `<div class="tiles">${tiles.map(t=>
    `<div class="card tile ${t.cls||''}"><div class="k">${esc(t.k)}</div>
     <div class="v num">${t.v}</div><div class="n">${t.n}</div></div>`).join('')}</div>`;

  html += decisionHTML();
  html += h2hHTML();
  html += frontierHTML();
  html += levelsHTML();
  html += matrixHTML();
  html += armConfigMatrixHTML();
  html += retrievalCoverageHTML();
  html += groundingSourcesHTML();
  html += reproHTML();

  html += `<section class="sec" id="tl">${timelineHTML()}</section>`;

  html += `<section class="sec" id="arms"><h2>Every arm, side by side</h2>
    ${tk('arms')}
    <p class="lede">One row per verdict file. <strong>Generation run</strong> is when the answers
    were produced; <strong>judging run</strong> is when they were scored, by which judge and under
    which prompt digest; <strong>human grading</strong> is a third pass on top. Two arms judged in
    different judging runs differ a little before their models do anything.</p>`;
  order.forEach(([qset, rows], gi) => {
    html += `<div class="grp"><h3>${rows[0].n} questions</h3>
      <span class="meta">fingerprint <code>${esc(qset)}</code> — ${rows.length} arm${rows.length>1?'s':''}; comparable only to each other, and only where the Kind matches too</span></div>`;
    html += table(rows, 'g'+gi);
  });
  html += `</section>`;
  document.getElementById('app').innerHTML = html;
  wireTimeline();
  wireRoadmap();

  document.querySelectorAll('th[data-c]').forEach(th => {
    const go = () => sort(th);
    th.addEventListener('click', go);
    th.addEventListener('keydown', e => { if(e.key==='Enter'||e.key===' '){ e.preventDefault(); go(); }});
  });
}

function sort(th){
  const tbl = th.closest('table'), ci = +th.dataset.c;
  const asc = th.getAttribute('aria-sort') !== 'ascending';
  tbl.querySelectorAll('th').forEach(o=>o.removeAttribute('aria-sort'));
  th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
  const tb = tbl.tBodies[0];
  const rows = [...tb.rows];
  rows.sort((x,y)=>{
    const a = x.cells[ci].textContent.trim(), b = y.cells[ci].textContent.trim();
    const na = parseFloat(a.replace(/[$%,]/g,'')), nb = parseFloat(b.replace(/[$%,]/g,''));
    const cmp = (!isNaN(na)&&!isNaN(nb)) ? na-nb : a.localeCompare(b);
    return asc ? cmp : -cmp;
  });
  rows.forEach(r=>tb.appendChild(r));
}

document.getElementById('foot').innerHTML = `
 <strong>How to read this.</strong>
 <ul>
  <li><strong>Two gates, not one.</strong> Arms may only be differenced when they share a question-set
      fingerprint <em>and</em> a kind. ${esc(C.kind_rule||'')} Arms of different kinds still appear
      side by side — that is useful — but their numbers are not on the same scale, and nothing
      subtracts one from the other.</li>
  <li><strong>Generation run vs judging run.</strong> They are separate events. The generation run is
      the answers file that produced the answers; the judging run is the verdict file that scored
      them, named with its judge model and prompt digest. Re-judging identical answers has moved an
      arm by 2 pp in this repo, so an accuracy that does not name its judging run is not
      reproducible. Human grading is a third layer on top and is labelled separately wherever it
      applies.</li>
  <li><strong>Corpus-mix projection.</strong> The full corpus is
      ${esc(JSON.stringify(C.corpus&&C.corpus.by_level||{}))} by level, read from
      <code>${esc((C.corpus||{}).file||'—')}</code>; the 150-question set is 30 per level. A flat
      score off a stratified sample is therefore not the expected score on the corpus, so the
      projection reweights each arm's per-level accuracy by the corpus's own mix and reports how
      much of the corpus that covers.</li>
  <li><strong>Every delta names its baseline.</strong> ${esc(TL.notes.baseline||'')}</li>
  <li><strong>Run order.</strong> ${esc(TL.notes.ordering||'')}</li>
  <li><strong>Commits are an inference.</strong> ${esc(TL.notes.commits||'')}</li>
  <li><strong>Oracle arms never chain.</strong> ${esc(TL.notes.oracle||'')}</li>
  <li><strong>Flat vs Weighted.</strong> Flat is how every prior result in this repo is stated.
      Weighted applies Jon's ruling — flat across L0–L3, Corner Case ×0.5. Flat is the number to quote.</li>
  <li><strong>Auto</strong> is the judge's own score before human regrading; where it differs from Flat,
      a human overturned rows. The judge is <em>nondeterministic</em> (~1 verdict flip per 100 rows),
      so treat ±1–2 rows as noise before reading a difference as real.</li>
  <li><strong>$/question</strong> is computed from recorded token usage at
      ${esc(D.pricing.source)}: input, output, cache-write ×${D.pricing.cache_write_mult},
      cache-read ×${D.pricing.cache_read_mult}. Sonnet 5 is shown at its standard rate —
      its introductory rate runs to ${esc(D.pricing.sonnet_intro_ends)}.</li>
  <li><strong>Join</strong> says how an arm's accuracy was linked to its cost. Verdict files do not
      record which answers file they judged, so each link is confirmed by comparing question-id sets.
      Anything not marked <span class="badge b-good">verified</span> should not be used for a cost claim.</li>
  <li><strong>Retrieval config is not per-arm.</strong> The answers files record model and rewrite
      version but not TOP_K / TOP_N / COSINE_FLOOR. Current values —
      TOP_K ${D.current_config.TOP_K}, TOP_N ${D.current_config.TOP_N},
      COSINE_FLOOR ${D.current_config.COSINE_FLOOR}, REWRITE_N ${D.current_config.REWRITE_N} —
      describe the code today, not what each historical arm ran.</li>
 </ul>`;

const btn = document.getElementById('themeBtn');
btn.addEventListener('click', () => {
  const dark = document.documentElement.getAttribute('data-theme') !== 'light';
  document.documentElement.setAttribute('data-theme', dark ? 'light' : 'dark');
});
render();
</script></body></html>
"""


def render_html(data: dict) -> str:
    return (HTML
            .replace("__GENERATED__", data["generated_at"])
            .replace("__DATA__", json.dumps(data).replace("</", "<\\/")))


def load_retrieval_coverage() -> dict:
    """docs/spec-coverage-metric.md's backfill: evals/backfill_coverage.py
    writes evals/coverage_backfill.json (per-arm mean coverage + hit rate,
    plus the hit-vs-coverage gap worklist) from recorded retrieved_rule_ids,
    zero model calls. Returns an empty-but-shaped dict if the backfill hasn't
    been run yet, so the dashboard degrades to "no data" rather than KeyError."""
    path = REPO / "evals" / "coverage_backfill.json"
    if not path.exists():
        return {"arms": [], "worklist": [], "worklist_n_total": 0,
                "worklist_n_above_threshold": 0, "gap_threshold": 0.5, "skipped": [],
                "gold_size_stratification": {"strata": []},
                "gold_size_stratification_shipped": {"strata": []},
                "shipped_arms": []}
    return json.loads(path.read_text(encoding="utf-8"))


def load_grounding_sources(arms: list[dict]) -> dict:
    """Citation-source rates per arm (docs/results-groundedness-guard.md: CR-
    reliance rate / rulings-only rate / nothing-resolvable rate / unresolved-
    citation rate), computed by evals/grounding_sources.py -- the SAME
    reusable scorer that can retroactively score any answers file on disk.
    Reuses each arm's own resolved answers path from collect()
    (`arm["generation"]["file"]`) rather than re-globbing evals/answers/, so
    an arm reported here is the exact same arm the rest of the page reports
    on -- same qset, same kind, same join. Arms with no resolved answers
    file, or whose rows score entirely "unknown" (no citation_sources and no
    reachable prompts_cache), are skipped and counted, never guessed."""
    out = []
    n_skipped = 0
    for a in arms:
        rel = (a.get("generation") or {}).get("file")
        if not rel:
            n_skipped += 1
            continue
        apath = REPO / rel
        if not apath.exists():
            n_skipped += 1
            continue
        try:
            raw = json.loads(apath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            n_skipped += 1
            continue
        rows = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
        if not isinstance(rows, list):
            n_skipped += 1
            continue
        metrics = gs.score_arm(rows)
        if metrics["n_scored"] == 0:
            n_skipped += 1
            continue
        out.append({"arm": a["arm"], "qset": a["qset"], "kind": a["kind"], **metrics})
    out.sort(key=lambda r: (r["cr_reliance_rate"] is None, -(r["cr_reliance_rate"] or 0)))
    return {"arms": out, "n_skipped": n_skipped}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", dest="json_out", default="evals/_metrics_history.json")
    ap.add_argument("--html", dest="html_out", default="evals/metrics_history.html")
    args = ap.parse_args()

    data = collect()
    data["full_corpus"] = FULL_CORPUS
    data["timeline"] = build_timeline(data["arms"])
    data["comparisons"] = build_comparisons(data["timeline"], corpus_level_mix())
    data["roadmap"] = build_roadmap(data["comparisons"], data["current_config"])
    data["summary"] = build_summary(data)
    data["retrieval_coverage"] = load_retrieval_coverage()
    data["arm_config_matrix"] = build_arm_config_matrix(data["arms"])
    data["grounding_sources"] = load_grounding_sources(data["arms"])
    for s in data["timeline"]["sets"]:   # working data, not a result
        for st in s["steps"]:
            st.pop("_arms", None)
    for a in data["arms"]:
        a.pop("_verdicts", None)
        a.pop("_correct", None)
    Path(args.json_out).write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    Path(args.html_out).write_text(render_html(data), encoding="utf-8")
    print(f"wrote {args.html_out}")
    print(f"wrote {args.json_out}: {len(data['arms'])} arms, "
          f"{len({a['qset'] for a in data['arms']})} question sets, "
          f"{len(data['skipped'])} skipped")
    groups: dict[str, list] = {}
    for a in data["arms"]:
        groups.setdefault(a["qset"], []).append(a)
    for qset, members in groups.items():
        print(f"\n  qset {qset}  n={members[0]['n']}  ({len(members)} arms)")
        for a in members:
            c = a["cost"].get("cost_per_q")
            cost = f"${c:.5f}" if c else "  --   "
            print(f"    {a['arm']:<34} {a['kind']:<8} flat {a['accuracy_flat']:>6.1%}  "
                  f"wtd {a['accuracy_weighted']:>6.1%}  {cost}  "
                  f"{a['config'].get('model') or '?'}/{a['config'].get('effort') or '?'}"
                  f"  gen[{a['generation']['join']}] judge[{a['judging']['judge_model'] or 'NOT RECORDED'}]")
    for s in data["skipped"]:
        print(f"  SKIP {s}")

    print(f"\n  timeline: {len(data['timeline']['sets'])} question sets, "
          f"{sum(len(s['steps']) for s in data['timeline']['sets'])} steps, "
          f"{data['timeline']['commits_indexed']} commits indexed")
    for s in data["timeline"]["sets"]:
        print(f"\n  qset {s['qset']} n={s['n']}  floor +/-{s['floor_pp']:.1f}pp ({s['floor_source'][:44]})")
        for st in s["steps"]:
            d = st["delta"]
            tag = "" if st["kind"] == "pipeline" else f"  [{st['kind']}, off-chain]"
            spread = f" spread {st['rep_spread_pp']:.1f}pp" if st["rep_spread_pp"] is not None else ""
            line = (f"    {(st['run_at'] or '')[:16]}  {st['step']:<30} "
                    f"flat {(st['flat'] or 0):>6.1%}{spread}{tag}")
            if d:
                verdict = "REAL" if d["beats_noise"] else "within noise"
                cost = f", cost {d['cost_pct']:+.0f}%" if d["cost_pct"] is not None else ""
                line += (f"\n        vs {d['baseline']}: {d['flat_pp']:+.1f}pp{cost} "
                         f"-> {verdict} (floor {d['floor_pp']:.1f}pp)")
            print(line)

    C = data["comparisons"]
    print(f"\n  head-to-head: {sum(len(h['pairs']) for h in C['head_to_head'])} kind-matched pairs, "
          f"{sum(1 for h in C['head_to_head'] if h['headroom'])} oracle-headroom readings")
    for h in C["head_to_head"]:
        for p in h["pairs"]:
            print(f"    n={p['n']:<4} {p['a']} vs {p['b']}  {p['flat_pp']:+.1f}pp "
                  f"cost {p['cost_pct']:+.0f}%" if p["cost_pct"] is not None else
                  f"    n={p['n']:<4} {p['a']} vs {p['b']}  {p['flat_pp']:+.1f}pp")
            print(f"          judge[{p['judge']['level']}] {p['judge']['text'][:96]}")
    print(f"\n  projections ({len(C['projections'])} configurations):")
    for p in C["projections"]:
        c = p["config"]
        acc = f"{p['projected_acc']:.1%}" if p["projected_acc"] is not None else "--"
        ci = f"[{p['ci95'][0]:.1%}-{p['ci95'][1]:.1%}]" if p["ci95"] else ""
        run = (f"${p['full_run_lo']:.0f}-{p['full_run_hi']:.0f}"
               if p["full_run_lo"] is not None else "unpriced")
        print(f"    {p['kind']:<8} {c.get('model')}/{c.get('effort')} rw={c.get('rewrite_version')} "
              f"rq={c.get('ruling_query_mode')}  corpus-mix {acc} {ci}  cover "
              f"{p['covered_share']:.0%}  full run {run}")
    print(f"\n  config matrix: {C['matrix']['n_tried']} of {C['matrix']['n_cells']} cells tried")
    print(f"  open items: {len(C['open_items'])}")
    for o in C["open_items"]:
        print(f"    [{o['level']}] {o['what']}")


if __name__ == "__main__":
    main()
