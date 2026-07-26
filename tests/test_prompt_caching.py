"""Guards for the prompt-caching knob.

Same defect shape this repo keeps hitting -- a value that looks present but
isn't. A `cache_control` that silently fails to reach the request body produces
a run that looks cached, bills full price on every question, and raises
nothing. So these lock down both directions:

1. Default OFF must send `system=` as a plain str, byte-identical to every run
   made before caching existed. If this fails, historical numbers stop being
   comparable.
2. Default ON must put a real `cache_control` block in the request, carrying
   the SAME text the uncached call would have sent -- caching must not alter
   the prompt, only annotate it.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rulesagent.generate.answer import RulesAgent, _cacheable_system  # noqa: E402


class _Store:
    chunks: list = []

    def search(self, *a, **k):
        return []


class _Recorded(Exception):
    pass


class _RecordingClient:
    """Capture the generation call's kwargs and unwind before any HTTP."""

    def __init__(self):
        self.messages = self
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        raise _Recorded


def _kwargs(**agent_kw):
    client = _RecordingClient()
    agent = RulesAgent(_Store(), client=client, **agent_kw)
    with pytest.raises(_Recorded):
        agent.answer("Does a Saga still get sacrificed if it loses its chapters?")
    return client.kwargs


# --- the pure helper -------------------------------------------------------

def test_helper_off_returns_the_string_unchanged():
    assert _cacheable_system("SYS", False) == "SYS"


def test_helper_on_wraps_with_cache_control():
    out = _cacheable_system("SYS", True)
    assert out == [{"type": "text", "text": "SYS",
                    "cache_control": {"type": "ephemeral"}}]


# --- the wiring, end to end through RulesAgent ------------------------------

def test_default_sends_a_plain_string_system():
    """Byte-identical to every pre-caching run. This is the regression guard."""
    kw = _kwargs()
    assert isinstance(kw["system"], str)
    assert "cache_control" not in repr(kw["system"])


def test_cache_prompt_puts_cache_control_in_the_request():
    kw = _kwargs(cache_prompt=True)
    assert isinstance(kw["system"], list) and len(kw["system"]) == 1
    block = kw["system"][0]
    assert block["type"] == "text"
    assert block["cache_control"] == {"type": "ephemeral"}


def test_caching_does_not_change_the_prompt_text():
    """The cached block must carry exactly the text the uncached call sends --
    otherwise caching is silently running a different experiment."""
    plain = _kwargs()["system"]
    cached = _kwargs(cache_prompt=True)["system"][0]["text"]
    assert cached == plain


def test_flag_is_recorded_on_the_agent():
    assert RulesAgent(_Store(), client=_RecordingClient()).cache_prompt is False
    assert RulesAgent(_Store(), client=_RecordingClient(),
                      cache_prompt=True).cache_prompt is True


def test_caching_leaves_every_other_kwarg_alone():
    """Only `system` may differ between the two arms."""
    off, on = _kwargs(), _kwargs(cache_prompt=True)
    assert set(off) == set(on)
    for k in off:
        if k != "system":
            assert off[k] == on[k], f"{k} changed when caching was enabled"
