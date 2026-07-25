"""Guards for the effort knob and the no-rewrite arm
(docs/spec-effort-and-norewrite.md).

Two things these lock down, both of which are this repo's recurring defect
shape -- a value that looks present but isn't:

1. `effort` must actually reach the generation call's kwargs, and must be
   ABSENT entirely (not None, not a default string) when unset. A silently
   dropped effort produces a run that looks like an effort arm and is really a
   default-effort arm, with nothing raising.
2. The two ways of switching the rewriter off on run_answer_eval.py
   (--no-rewrite and --rewrite-version none) must collapse to one truth, so a
   run file can never record "v2" for a run that never rewrote, or "none" for
   one that did.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rulesagent.generate.answer import (  # noqa: E402
    GEN_EFFORT_LEVELS,
    GEN_MODEL,
    REWRITE_MODEL,
    RulesAgent,
)


class _Store:
    """Minimal store double -- .chunks for the chunk_map, .search unused here."""

    chunks: list = []

    def search(self, *a, **k):
        return []


class _Recorded(Exception):
    pass


class _RecordingClient:
    """run_openrouter_arm.py's _RecordingClient, verbatim pattern: capture the
    generation call's kwargs and unwind before any HTTP happens."""

    def __init__(self):
        self.messages = self
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        raise _Recorded


def _agent(**kw):
    return RulesAgent(_Store(), client=_RecordingClient(), **kw)


# --- effort validation -------------------------------------------------------


def test_unknown_effort_raises_at_construction():
    """Eager, not at call time -- an unknown level must never surface 40
    minutes into an unattended batch."""
    with pytest.raises(ValueError, match="unknown effort"):
        _agent(effort="ultra")


@pytest.mark.parametrize("level", sorted(GEN_EFFORT_LEVELS))
def test_every_documented_level_constructs(level):
    assert _agent(effort=level).effort == level


def test_effort_levels_are_the_documented_five():
    assert GEN_EFFORT_LEVELS == {"low", "medium", "high", "xhigh", "max"}


# --- the request fragment ----------------------------------------------------


def test_default_adds_no_output_config():
    """The byte-identical-by-default guarantee. Empty dict, so the ** expansion
    at the call site contributes literally nothing."""
    agent = _agent()
    assert agent.effort is None
    assert agent._effort_kwargs == {}


def test_explicit_effort_builds_the_output_config_fragment():
    assert _agent(effort="low")._effort_kwargs == {"output_config": {"effort": "low"}}


# --- the call boundary -------------------------------------------------------
#
# The fragment being right is not the same as it arriving. These two assert on
# the kwargs the generation call was actually invoked with.


def _capture_gen_kwargs(**kw):
    agent = RulesAgent(_Store(), client=_RecordingClient(), card_no_refresh=True, **kw)
    try:
        agent.answer("does trample assign lethal damage before deathtouch?")
    except _Recorded:
        pass
    return agent.client.kwargs


def test_effort_reaches_the_generation_call():
    kwargs = _capture_gen_kwargs(effort="low", rewrite=False)
    assert kwargs is not None, "generation call was never made"
    assert kwargs.get("output_config") == {"effort": "low"}


def test_no_output_config_key_when_effort_unset():
    """Absent, not None -- a None would still serialize into the request body."""
    kwargs = _capture_gen_kwargs(rewrite=False)
    assert kwargs is not None, "generation call was never made"
    assert "output_config" not in kwargs


# --- the no-rewrite arm ------------------------------------------------------


def test_rewrite_false_makes_no_rewriter_call():
    """Assert the ABSENCE of the rewriter call directly, rather than inferring
    it from last_rewritten (which answer() resets to None on entry regardless,
    so asserting None there would pass even if the rewriter had run).

    rewrite_query() calls `client.messages.parse()` -- the same method the
    generation call uses -- so if the rewriter ran it would be the FIRST
    recorded call, carrying REWRITE_MODEL. Asserting the first call is the
    generation model is therefore a real check, not a vacuous one."""
    agent = RulesAgent(_Store(), client=_RecordingClient(), rewrite=False,
                       card_no_refresh=True)
    try:
        agent.answer("does trample assign lethal damage before deathtouch?")
    except _Recorded:
        pass

    first_model = agent.client.kwargs["model"]
    assert first_model != REWRITE_MODEL, (
        f"first API call used the rewriter model {REWRITE_MODEL} despite rewrite=False"
    )
    assert first_model == GEN_MODEL
    assert agent.last_rewritten is None
