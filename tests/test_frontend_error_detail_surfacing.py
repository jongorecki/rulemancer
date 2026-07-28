# Mobile UX audit fix, finding 1 (task-mobile-ux-fixes, 2026-07-28). Before
# this fix, frontend/index.html's askApi() did `if (!r.ok) throw new
# Error("HTTP " + r.status)` -- the server's specific, friendly `detail`
# message for every guard (code-at-cap, revoked, rate-limited, daily budget)
# was discarded, and the user saw a bare status code / a dev-facing fallback
# mentioning `uv run python run.py`. frontend/gate.html's /unlock handler had
# the identical pattern: one hardcoded string for every non-OK response,
# including telling a rate-limited visitor to "try again" when the real fix
# is to wait.
#
# These tests drive the actual client-side JS in a real (headless) browser
# via Playwright, with fetch("/answer") / fetch("/unlock") intercepted at the
# network layer (no live server, no port 8000 or 8947 involved, no API
# spend) -- exactly the reproduction method the audit itself used, so this
# guards the fix the same way the bug was found.

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO / "frontend" / "index.html"
GATE_HTML = REPO / "frontend" / "gate.html"


def _file_url(path: Path) -> str:
    return path.resolve().as_uri()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def test_index_html_surfaces_server_detail_on_answer_failure(browser):
    """A non-OK /answer response with a JSON `detail` body must render that
    exact sentence -- not a bare status code, not the old dev-facing
    fallback text."""
    detail = "This demo code is used up. Ask Jon for another."
    page = browser.new_page()
    page.route(
        "**/answer",
        lambda route: route.fulfill(
            status=402,
            content_type="application/json",
            body='{"detail": "%s"}' % detail,
        ),
    )
    try:
        page.goto(_file_url(INDEX_HTML))
        page.fill("#rm-composer", "Does trample deal damage through a blocker?")
        page.press("#rm-composer", "Enter")
        page.wait_for_selector("text=ERROR", timeout=5000)
        body_text = page.inner_text("#app")
        assert detail in body_text
        assert "HTTP 402" not in body_text
        assert "uv run python run.py" not in body_text
    finally:
        page.close()


def test_index_html_falls_back_to_readable_message_when_body_is_unparseable(browser):
    """Same guard, but the response body isn't JSON (a network drop, an HTML
    error page from an intermediary) -- must still render a calm, readable
    sentence, never a raw status code or an exception string."""
    page = browser.new_page()
    page.route(
        "**/answer",
        lambda route: route.fulfill(
            status=402,
            content_type="text/html",
            body="<html><body>Bad Gateway</body></html>",
        ),
    )
    try:
        page.goto(_file_url(INDEX_HTML))
        page.fill("#rm-composer", "Does trample deal damage through a blocker?")
        page.press("#rm-composer", "Enter")
        page.wait_for_selector("text=ERROR", timeout=5000)
        body_text = page.inner_text("#app")
        assert "Something went wrong reaching Rulemancer" in body_text
        assert "HTTP 402" not in body_text
        assert "Bad Gateway" not in body_text
        assert "uv run python run.py" not in body_text
    finally:
        page.close()


# gate.html's fetch("/unlock") is a bare relative path (unlike index.html's
# askApi, it has no file://-origin fallback -- by design, it only ever runs
# same-origin with the API). Loading it via a real file:// URL makes that
# relative fetch resolve to file:///unlock, which Chromium refuses to POST
# to -- fetch() rejects before Playwright's route interception is even
# relevant, and every case looks like the generic network-error fallback.
# Routing a fake http origin end to end (the page itself served from the
# same origin via route.fulfill(path=...), same as /unlock) sidesteps that
# without starting a real server or touching any port.
_GATE_ORIGIN = "http://rulemancer.test"


def test_gate_html_surfaces_detail_on_unlock_failure(browser):
    """A rate-limited /unlock response's real remedy ("wait 15 minutes")
    must reach the user instead of the old one-size-fits-all "check it and
    try again", which is actively wrong advice for a rate limit."""
    detail = "Too many tries too fast. Wait 15 minutes and try again, or ask Jon for help."
    page = browser.new_page()
    page.route(f"{_GATE_ORIGIN}/", lambda route: route.fulfill(path=str(GATE_HTML)))
    page.route(
        f"{_GATE_ORIGIN}/unlock",
        lambda route: route.fulfill(
            status=429,
            content_type="application/json",
            body='{"ok": false, "detail": "%s"}' % detail,
        ),
    )
    try:
        page.goto(f"{_GATE_ORIGIN}/")
        page.fill("#code", "some-code")
        page.click("#submit-btn")
        page.wait_for_function(
            "document.getElementById('msg').textContent.trim().length > 0",
            timeout=5000,
        )
        msg_text = page.inner_text("#msg")
        assert detail in msg_text
        assert "check it and try again" not in msg_text.lower()
    finally:
        page.close()


def test_gate_html_falls_back_to_readable_message_when_unlock_body_is_unparseable(browser):
    """Same /unlock failure path, but the body isn't JSON -- must still
    render the old generic-but-readable sentence, never a raw status code."""
    page = browser.new_page()
    page.route(f"{_GATE_ORIGIN}/", lambda route: route.fulfill(path=str(GATE_HTML)))
    page.route(
        f"{_GATE_ORIGIN}/unlock",
        lambda route: route.fulfill(status=403, content_type="text/plain", body="nope"),
    )
    try:
        page.goto(f"{_GATE_ORIGIN}/")
        page.fill("#code", "bad-code")
        page.click("#submit-btn")
        page.wait_for_function(
            "document.getElementById('msg').textContent.trim().length > 0",
            timeout=5000,
        )
        msg_text = page.inner_text("#msg")
        assert msg_text.strip() == "That code didn't work. Check it and try again."
        assert "HTTP 403" not in msg_text
    finally:
        page.close()
