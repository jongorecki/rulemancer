# Duplicated-constant guard (2026-07-27). commit c1c043f added a
# question-length guard of 2,000 characters, derived from the longest real
# question in the 1,409-row corpus (1,013 chars, doubled and rounded). The
# value has to exist in two places: rulesagent.api.main.MAX_QUESTION_CHARS
# (enforced server-side in /answer) and a mirrored `const MAX_QUESTION_CHARS`
# in frontend/index.html (used client-side for the textarea's maxlength and
# the character-remaining counter). Both comments point at each other, but
# nothing enforced agreement -- someone could bump one and forget the other,
# and the mismatch would only surface as a confusing UX bug (the counter
# says "you have room" while the server 413s, or vice versa).
#
# frontend/index.html and frontend/gate.html are served as plain static
# files (FileResponse / StaticFiles, see main.py's `_index` route) with no
# templating step, so injecting the server constant into the page at
# request time would mean switching that route from FileResponse to a
# read-and-string-replace HTMLResponse -- which breaks the existing
# FileResponse-identity assertions in tests/test_gate_routing.py
# (`resp.path.name == "index.html"`) and loses FileResponse's normal static
# semantics (conditional GET, etc.) for what both routes still are
# otherwise. That's not "genuinely awkward" in the sense of being
# impossible, but it's a real behavior change to routing for a one-constant
# sync problem. This repo already solved an identical shape of problem
# today the other way -- see test_design_tokens_no_drift.py's
# test_frontend_and_design_system_palettes_do_not_drift, which pins two
# files that can't share an import against each other with a test, not a
# build step. This test follows that precedent: pin the two values with a
# test instead of restructuring how the page is served.
#
# If this test fails, one of the two constants was changed without the
# other -- update whichever one is now wrong so both enforce the same limit.

import re
from pathlib import Path

from rulesagent.api import main

REPO = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO / "frontend" / "index.html"

_JS_CONST_RE = re.compile(r"const\s+MAX_QUESTION_CHARS\s*=\s*(\d+)\s*;")


def test_frontend_max_question_chars_matches_server_constant():
    html = INDEX_HTML.read_text(encoding="utf-8")
    match = _JS_CONST_RE.search(html)
    assert match, (
        "frontend/index.html no longer defines `const MAX_QUESTION_CHARS = "
        "<n>;` in the shape this test expects -- if the JS was refactored "
        "(e.g. to read the limit from a server-injected value instead of a "
        "hardcoded literal), update this test's extraction regex to match "
        "the new shape rather than deleting the test. The point is "
        "agreement between the two values, however each is expressed."
    )
    frontend_value = int(match.group(1))
    assert frontend_value == main.MAX_QUESTION_CHARS, (
        f"frontend/index.html's MAX_QUESTION_CHARS ({frontend_value}) does not "
        f"match rulesagent.api.main.MAX_QUESTION_CHARS ({main.MAX_QUESTION_CHARS}). "
        "These two constants must agree: the frontend uses its copy for the "
        "textarea's maxlength and the character-remaining counter, while the "
        "server enforces its copy as the real /answer guard. A mismatch means "
        "the UI tells visitors something the server doesn't honor (or vice "
        "versa). Update whichever constant is now wrong so both express the "
        "same limit."
    )
