"""system_version knob + control-arm system prompt (docs/spec-slice0-harness.md
Task 2). Offline only -- a scripted fake client, same pattern as
tests/test_cost_tool_loop.py's _ScriptedToolClient, plus pure-function tests
against build_prompt()'s new system_override seam.

The byte-identity test (test_default_agent_system_is_byte_identical_to_SYSTEM)
is the production-didn't-move guard: PROMPT_VERSION must stay 3 and SYSTEM
must stay SYSTEM_VERSIONS[PROMPT_VERSION]. If this ever goes red, production
moved -- do not "fix" it by recapturing, stop and report (per the spec's
global rules).
"""
from pathlib import Path

import pytest

from rulesagent.contracts import Answer
from rulesagent.generate import answer as ans

REPO = Path(__file__).parent.parent


class _FakeResponse:
    def __init__(self, parsed_output, stop_reason="end_turn"):
        self.stop_reason = stop_reason
        self.content = []
        self.parsed_output = parsed_output


class _ScriptedClient:
    """Minimal fake .messages.parse() client: records every call's kwargs,
    returns one scripted response per call. No tool-use content -- these
    tests are about the system string, not the tool loop (tests/
    test_cost_tool_loop.py already covers that)."""

    def __init__(self, script):
        self.messages = self
        self._script = list(script)
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._script.pop(0)


class _EmptyStore:
    def search(self, query, k):
        return []


_REAL_ANSWER = Answer(
    text="Trample interacts with deathtouch per 702.19e.",
    tldr="t", citations=["702.19e"], answered=True, suggested_followups=[],
)

PLAIN_QUESTION = "Does trample interact with deathtouch?"


# --- Agent-level: default vs. registered variant vs. unknown key -----------


def test_default_agent_system_is_byte_identical_to_SYSTEM():
    client = _ScriptedClient([_FakeResponse(_REAL_ANSWER)])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    agent.answer(PLAIN_QUESTION)
    assert client.calls[0]["system"] == ans.SYSTEM
    assert agent.system_version == ans.PROMPT_VERSION


def test_system_version_v3_613_produces_system_plus_layers_cr_bullet():
    client = _ScriptedClient([_FakeResponse(_REAL_ANSWER)])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False,
                            system_version="v3+613")
    agent.answer(PLAIN_QUESTION)
    assert client.calls[0]["system"] == ans.SYSTEM + "\n" + ans.LAYERS_CR_BULLET
    assert client.calls[0]["system"] == ans.SYSTEM_V3_613
    assert ans.SYSTEM_VERSIONS["v3+613"] is ans.SYSTEM_V3_613


def test_unknown_system_version_raises_value_error_listing_valid_keys():
    with pytest.raises(ValueError) as exc_info:
        ans.RulesAgent(_EmptyStore(), client=_ScriptedClient([]), system_version="bogus")
    msg = str(exc_info.value)
    assert "bogus" in msg
    for key in ans.SYSTEM_VERSIONS:
        assert str(key) in msg


# --- CR text provenance: both rule sentences appear verbatim ---------------


def test_both_layers_cr_sentences_appear_verbatim_in_repo_cr_text():
    """Split LAYERS_CR_BULLET on its own newlines (intro line, then the
    613.6 paragraph, then the 611.3a paragraph) so the substrings checked
    are the ACTUAL production string, not a hand-retyped copy that could
    itself silently drift out of sync with what ships."""
    cr_path = REPO / "data" / "raw" / "MagicCompRules 20260619.txt"
    cr_text = cr_path.read_text(encoding="utf-8-sig")

    intro, sentence_613_6, sentence_611_3a = ans.LAYERS_CR_BULLET.split("\n")
    assert sentence_613_6 in cr_text
    assert sentence_611_3a in cr_text
    # Curly quotes must be preserved verbatim, not normalised to ASCII.
    assert "’" in sentence_611_3a  # curly apostrophe, isn't
    assert "“" in sentence_611_3a and "”" in sentence_611_3a  # curly quotes


# --- build_prompt()'s system_override seam ----------------------------------


def test_build_prompt_default_system_override_preserves_module_SYSTEM():
    sys_out, _ = ans.build_prompt("q?", [], [])
    assert sys_out == ans.SYSTEM


def test_build_prompt_system_override_replaces_module_system():
    sys_out, _ = ans.build_prompt("q?", [], [], system_override="CUSTOM SYSTEM STRING")
    assert sys_out == "CUSTOM SYSTEM STRING"


def test_build_prompt_system_override_combines_with_convo_ctx():
    # The multiturn context-reading sentence must still append on top of the
    # override, not silently drop it in favor of module SYSTEM.
    sys_out, _ = ans.build_prompt(
        "q?", [], [], convo_ctx="User: hi", system_override="CUSTOM SYSTEM STRING",
    )
    assert sys_out.startswith("CUSTOM SYSTEM STRING")
    assert "transcript at the top" in sys_out
    assert ans.SYSTEM not in sys_out
