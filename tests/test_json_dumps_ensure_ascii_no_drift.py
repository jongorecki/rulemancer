# Drift guard for the ensure_ascii em-dash bug (2026-07-27/28).
#
# json.dumps() defaults to ensure_ascii=True, which escapes every non-ASCII
# character to a \uXXXX sequence. src/rulesagent/generate/answer.py once
# built a tool_result's "content" with a bare json.dumps(result) -- and
# because tool_result content is read by the model as literal TEXT, not
# decoded JSON, an em dash in a tool result became the six literal
# characters "—" in the model's context, and the model copied them
# straight into a user-visible answer. Seen live on the demo.
#
# The fix was one line (ensure_ascii=False at the call site), but a future
# edit -- someone adding a new json.dumps() call in this code, or "tidying"
# the existing one back to the default -- would silently reintroduce the
# bug with no other signal. This test pins the rule: every json.dumps(...)
# call in the generate/ and api/ packages (the answer-serving path) must
# pass ensure_ascii=False explicitly.
#
# If this test fails: either add ensure_ascii=False to the offending call,
# or, if that call genuinely needs ASCII-only output (e.g. it feeds a
# system that can't handle raw UTF-8), add its exact "path:line" to
# _EXEMPT below with a comment explaining why -- don't just delete the
# assertion.

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCAN_DIRS = [
    REPO / "src" / "rulesagent" / "generate",
    REPO / "src" / "rulesagent" / "api",
]

# "relative/path.py:lineno" entries exempted from the ensure_ascii=False
# requirement, each with a reason. Empty today -- every json.dumps() call
# in these two packages already passes ensure_ascii=False (verified when
# this guard was added; see tests/test_cost_tool_loop.py's
# test_tool_result_content_preserves_non_ascii_characters_not_escapes for
# the regression test proving the fix at the answer.py call site).
_EXEMPT: set[str] = set()


def _find_bare_json_dumps_calls():
    """Return a list of "path:line" strings for every json.dumps(...) call
    under SCAN_DIRS that does not pass ensure_ascii=False as a keyword
    argument."""
    offenders = []
    for scan_dir in SCAN_DIRS:
        for path in sorted(scan_dir.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                is_json_dumps = (
                    isinstance(func, ast.Attribute)
                    and func.attr == "dumps"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "json"
                )
                if not is_json_dumps:
                    continue
                has_ensure_ascii_false = any(
                    kw.arg == "ensure_ascii"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is False
                    for kw in node.keywords
                )
                if not has_ensure_ascii_false:
                    rel = path.relative_to(REPO).as_posix()
                    offenders.append(f"{rel}:{node.lineno}")
    return offenders


def test_every_json_dumps_in_answer_serving_path_sets_ensure_ascii_false():
    offenders = [o for o in _find_bare_json_dumps_calls() if o not in _EXEMPT]
    assert offenders == [], (
        "Found json.dumps(...) call(s) in src/rulesagent/generate/ or "
        "src/rulesagent/api/ without ensure_ascii=False: "
        f"{offenders}. json.dumps() defaults to ensure_ascii=True, which "
        "escapes non-ASCII characters (e.g. an em dash) to literal "
        "backslash-u sequences. If that json.dumps() output is ever read "
        "back as TEXT by the model (as a tool_result's content is), the "
        "model sees the six-character escape sequence and copies it "
        "verbatim into the user-visible answer -- this is exactly the bug "
        "Jon saw live on the demo (\\u2014 instead of an em dash). Add "
        "ensure_ascii=False to the call, or if it genuinely must stay "
        "ASCII-only, add its \"path:line\" to _EXEMPT in this test with a "
        "comment explaining why."
    )
