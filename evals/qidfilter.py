"""`--qids` scattered-subset selection, shared by both eval runners
(run_answer_eval.py, run_openrouter_arm.py). Sibling-module import, same
pattern those runners already use for progress.py/run_eval.py -- evals/
isn't part of the installed rulesagent package, so it's not a real
sub-package, just a scripts directory each script adds to sys.path itself.

Today the only subsetter is `--limit N`, which takes a prefix of the master
question list. When the wanted set is scattered (e.g. a handful of
regressions: c012,c014,c015) a prefix can't express it, hence this.
"""


class QidFilterError(ValueError):
    """Raised by select_qids() on a malformed/invalid --qids spec. A plain
    ValueError subclass -- callers catch this specifically rather than
    ValueError broadly so a genuine bug elsewhere isn't mistaken for a bad
    --qids spec."""


def select_qids(questions, spec: str) -> list:
    """Return the subset of `questions` (objects with an `.id` attribute)
    whose id appears in `spec` -- a comma-separated string of ids.

    The result is ordered as the ids appear in `questions` (master-file
    order), NOT the order given in `spec` -- determinism matters more than
    preserving whatever order was typed on the command line.

    Whitespace around each id is stripped. Raises QidFilterError, naming the
    offending id(s), on:
      - an empty spec, a whitespace-only spec, or a stray/trailing comma
        (any entry that strips to "")
      - a duplicate id within spec
      - a requested id that isn't present in `questions`
    """
    raw_ids = [piece.strip() for piece in spec.split(",")]
    if any(piece == "" for piece in raw_ids):
        raise QidFilterError(
            f"--qids {spec!r} contains an empty id -- check for a stray/trailing comma "
            f"or a blank spec"
        )

    seen: set[str] = set()
    dupes: list[str] = []
    for qid in raw_ids:
        if qid in seen and qid not in dupes:
            dupes.append(qid)
        seen.add(qid)
    if dupes:
        raise QidFilterError(
            f"--qids {spec!r} has duplicate id(s): {', '.join(sorted(dupes))}"
        )

    requested = set(raw_ids)
    available = {q.id for q in questions}
    missing = requested - available
    if missing:
        raise QidFilterError(
            f"--qids requested id(s) not found in the loaded questions: "
            f"{', '.join(sorted(missing))}"
        )

    return [q for q in questions if q.id in requested]
