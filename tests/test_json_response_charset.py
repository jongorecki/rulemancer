# plan-answer-ui-fixes Fix 2 (em-dash bug): every /answer-shaped JSON response
# must declare an explicit UTF-8 charset and carry proper UTF-8 bytes for
# non-ASCII characters (em dash chief among them). See main.JSONResponse's
# docstring for the full root-cause writeup: every text-producing layer this
# project controls was audited and found clean (corpus, parser encoding,
# Starlette's own ensure_ascii=False, 1,335 real production DB rows); this
# closes the one remaining gap, an implicit charset on `application/json`
# that a proxy in front of the app could otherwise misinterpret.

from rulesagent.api import main


def test_json_response_declares_explicit_utf8_charset():
    resp = main.JSONResponse({"ok": True})
    assert resp.media_type == "application/json; charset=utf-8"


def test_json_response_encodes_non_ascii_as_real_utf8_bytes():
    resp = main.JSONResponse({"answer": "an em dash — and a curly quote ’"})
    assert "—".encode("utf-8") in resp.body
    assert "’".encode("utf-8") in resp.body
    # never a literal ASCII escape sequence standing in for the real
    # character (the "double-escaped" bug this test exists to catch if it's
    # ever reintroduced) -- ensure_ascii=False means json.dumps must never
    # fall back to \uXXXX for a character this simple.
    assert b"\\u2014" not in resp.body
    assert b"\\u2019" not in resp.body


def test_app_uses_the_charset_hardened_response_by_default():
    assert main.app.router.default_response_class is main.JSONResponse
