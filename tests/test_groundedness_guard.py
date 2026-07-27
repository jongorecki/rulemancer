"""Tests for the groundedness guard (docs/results-groundedness-guard.md).

Two defects were found in the existing check at answer.py's generation
tail (`if parsed.answered and not parsed.citations: ... last_uncited_success
= True`):

1. It is advisory only -- it logs and sets a flag nothing downstream reads
   (except the live API's Debug field, tests/test_uncited_success.py).
2. Its condition, `not parsed.citations`, is an EMPTINESS test over a field
   that mixes CR rule numbers, glossary terms, card names, and card-ruling
   labels ("Archive Trap ruling #2") -- so a row citing zero CR rules but
   one card ruling passes as "grounded".

This file tests the fix: `cr_rule_citations()` (the specific-condition
helper), `needs_regrounding()` (built on it), and `reground_once()` (the
shared re-ask step both RulesAgent.answer() -- the live path -- and
evals/run_answer_eval.py's _answer_from_frozen_prompt() -- the
--prompts-cache path the A/B harness uses -- call). No live Anthropic API
calls anywhere in this file: every client is a scripted fake, matching the
existing pattern in tests/test_uncited_success.py and tests/test_degenerate.py.
"""

from pydantic import ValidationError

from rulesagent.contracts import Answer
from rulesagent.generate import answer as ans
from evals import run_answer_eval as rae


# --- fakes, same pattern as tests/test_uncited_success.py -------------------


class _FakeResponse:
    def __init__(self, parsed_output, content=None, stop_reason="end_turn", usage=None):
        self.parsed_output = parsed_output
        # reground_once() reads `.content` directly (not getattr-guarded) to
        # build the re-ask's assistant turn -- a real SDK response always has
        # it, so the fake must too whenever a test's script might reach
        # regrounding. A plain placeholder is fine: the scripted client below
        # never actually inspects message content, it just pops the next
        # scripted item.
        self.content = content if content is not None else [{"type": "text", "text": "stub"}]
        self.stop_reason = stop_reason
        self.usage = usage


class _FakeUsage:
    def __init__(self, input_tokens, output_tokens, cache_read=0, cache_write=0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = cache_read
        self.cache_creation_input_tokens = cache_write


class _ScriptedClient:
    """Pops one scripted item per `.messages.parse()` call. An item may be an
    Answer (wrapped in a `_FakeResponse`), an already-built `_FakeResponse`
    (to control content/stop_reason/usage), or a BaseException instance (to
    simulate messages.parse() raising ValidationError on empty output)."""

    def __init__(self, script):
        self.messages = self
        self._script = list(script)
        self.calls = 0

    def parse(self, **kwargs):
        self.calls += 1
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, _FakeResponse):
            return item
        return _FakeResponse(item)


class _EmptyStore:
    def search(self, query, k):
        return []


def _validation_error() -> ValidationError:
    """A real ValidationError, same construction as tests/test_degenerate.py's
    helper of the same name -- simulates messages.parse() raising on
    empty/invalid structured output without needing a live API call."""
    try:
        Answer.model_validate({})
    except ValidationError as e:
        return e
    raise AssertionError("expected ValidationError")


def _answer(text="A" * 300, citations=None, answered=True):
    return Answer(
        text=text, tldr="tldr", citations=citations or [],
        answered=answered, suggested_followups=[],
    )


# --- cr_rule_citations --------------------------------------------------


def test_cr_rule_citations_keeps_rule_numbers():
    cites = ["104", "601.2b", "613.8a"]
    assert ans.cr_rule_citations(cites) == cites


def test_cr_rule_citations_drops_glossary_terms():
    # "City's Blessing" is a real glossary source_id (normalize_source_id's
    # own docstring example) -- not a rule number, must not match.
    assert ans.cr_rule_citations(["City's Blessing"]) == []


def test_cr_rule_citations_drops_card_names():
    assert ans.cr_rule_citations(["Lightning Bolt", "Archive Trap"]) == []


def test_cr_rule_citations_drops_ruling_labels():
    # The exact shape from docs/results-groundedness-guard.md: a card-ruling
    # citation label, not a rule number.
    assert ans.cr_rule_citations(["Archive Trap ruling #2"]) == []


def test_cr_rule_citations_mixed_list_keeps_only_rules():
    mixed = ["601.2b", "Lightning Bolt", "Archive Trap ruling #2", "City's Blessing", "104"]
    assert ans.cr_rule_citations(mixed) == ["601.2b", "104"]


def test_cr_rule_citations_empty_list():
    assert ans.cr_rule_citations([]) == []


# --- needs_regrounding ----------------------------------------------------


def test_needs_regrounding_true_when_answered_and_no_rule_citations():
    assert ans.needs_regrounding(_answer(citations=[])) is True


def test_needs_regrounding_false_when_answered_with_rule_citation():
    assert ans.needs_regrounding(_answer(citations=["601.2b"])) is False


def test_needs_regrounding_true_for_ruling_only_citation():
    # THE defect being fixed: a card-ruling citation is not a rules
    # grounding claim, so this must still need regrounding even though
    # `citations` is non-empty (the old `not parsed.citations` check would
    # have missed this entirely).
    assert ans.needs_regrounding(_answer(citations=["Archive Trap ruling #2"])) is True


def test_needs_regrounding_false_for_honest_decline():
    # An answered=false decline never needs regrounding, regardless of its
    # (empty, per the contract) citations.
    assert ans.needs_regrounding(_answer(answered=False, citations=[])) is False


# --- reground_once, standalone --------------------------------------------


def test_reground_once_returns_new_answer_and_response():
    second = _answer(citations=["601.2b"])
    client = _ScriptedClient([second])
    prior_response = _FakeResponse(_answer(citations=[]))
    parsed, response = ans.reground_once(
        client, "fake-model", "system prompt", [{"role": "user", "content": "q"}],
        prior_response, max_tokens=1000,
    )
    assert client.calls == 1
    assert parsed is second
    assert response.parsed_output is second


def test_reground_once_returns_none_on_validation_error():
    client = _ScriptedClient([_validation_error()])
    prior_response = _FakeResponse(_answer(citations=[]))
    parsed, response = ans.reground_once(
        client, "fake-model", "system", [{"role": "user", "content": "q"}],
        prior_response, max_tokens=1000,
    )
    assert parsed is None
    assert response is None


# --- RulesAgent.answer() integration --------------------------------------


def test_disabled_by_default_never_regrounds():
    """The core byte-identity requirement: an agent built with no reground=
    argument (every existing caller) must behave EXACTLY as before this
    guard existed -- one client call, original ungrounded draw returned
    unchanged, even though it would trip needs_regrounding()."""
    ungrounded = _answer(citations=[])
    client = _ScriptedClient([ungrounded])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False)
    assert agent.reground is False  # the default
    result = agent.answer("does trample work with deathtouch")
    assert client.calls == 1
    assert result is ungrounded
    assert agent.last_regrounded is False
    assert agent.last_cr_citations_before == 0
    assert agent.last_cr_citations_after is None


def test_reground_enabled_fires_and_replaces_answer():
    first = _answer(citations=[])  # answered=true, zero CR rule citations
    second = _answer(citations=["601.2b", "613.8a"])
    client = _ScriptedClient([first, second])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False, reground=True)
    result = agent.answer("does trample work with deathtouch")
    assert client.calls == 2
    assert result is second
    assert agent.last_regrounded is True
    assert agent.last_cr_citations_before == 0
    assert agent.last_cr_citations_after == 2


def test_reground_fires_exactly_once_even_if_still_uncited():
    """If the re-ask ITSELF still cites zero CR rules, the second draw is
    kept as-is -- never retried a second time, never silently reverted to
    the first draw. Exactly 2 client calls total."""
    first = _answer(citations=[])
    second_still_uncited = _answer(citations=["Archive Trap ruling #2"], answered=True)
    client = _ScriptedClient([first, second_still_uncited])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False, reground=True)
    result = agent.answer("does trample work with deathtouch")
    assert client.calls == 2
    assert result is second_still_uncited
    assert agent.last_regrounded is True
    assert agent.last_cr_citations_before == 0
    assert agent.last_cr_citations_after == 0  # fired, still uncited -- 0, not None


def test_reground_keeps_original_when_reask_fails_to_parse():
    first = _answer(citations=[])
    client = _ScriptedClient([first, _validation_error()])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False, reground=True)
    result = agent.answer("does trample work with deathtouch")
    assert client.calls == 2
    assert result is first  # original kept, never silently dropped
    assert agent.last_regrounded is True  # an attempt was made
    assert agent.last_cr_citations_after is None  # distinct from 0 (fired-but-uncited)


def test_reground_honors_reask_answered_false():
    """The re-ask may legitimately decide the provided rules don't cover the
    question -- that must be taken verbatim, never overwritten back to True."""
    first = _answer(citations=[])
    honest_decline = _answer(
        text="The rules provided don't settle this -- " + "x" * 200,
        citations=[], answered=False,
    )
    client = _ScriptedClient([first, honest_decline])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False, reground=True)
    result = agent.answer("does trample work with deathtouch")
    assert client.calls == 2
    assert result is honest_decline
    assert result.answered is False


def test_ruling_only_citation_is_ungrounded_and_reground_fires():
    """THE exact defect from docs/results-groundedness-guard.md: a row
    citing only a card ruling (not a CR rule) passes the OLD
    `not parsed.citations` check as "grounded" (last_uncited_success stays
    False) but must be caught -- and, when reground is on, acted on -- by
    the new CR-specific check."""
    ruling_only = _answer(citations=["Archive Trap ruling #2"])
    second = _answer(citations=["601.2b"])
    client = _ScriptedClient([ruling_only, second])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False, reground=True)
    result = agent.answer("does this interaction work")
    # Old advisory check never fires -- citations is non-empty.
    assert agent.last_uncited_success is False
    # New check catches it and regrounds.
    assert agent.last_regrounded is True
    assert agent.last_cr_citations_before == 0
    assert result is second
    assert agent.last_cr_citations_after == 1


def test_reground_disabled_leaves_last_uncited_success_behavior_unchanged():
    """Sanity check: last_uncited_success (the pre-existing advisory flag,
    read by the live API's Debug field) is completely untouched by this
    guard -- same value, same single call, whether reground is on or off,
    since the ruling-only draw is grounded enough to avoid the OLD check
    either way."""
    ruling_only = _answer(citations=["Archive Trap ruling #2"])
    client = _ScriptedClient([ruling_only])
    agent = ans.RulesAgent(_EmptyStore(), client=client, rewrite=False, reground=False)
    agent.answer("does this interaction work")
    assert agent.last_uncited_success is False
    assert client.calls == 1


# --- evals/run_answer_eval.py's _answer_from_frozen_prompt() -------------
#
# Same coverage as the RulesAgent path above, over the OTHER generation path
# -- the one the A/B harness actually uses (docs/results-groundedness-guard.md:
# "If you only implement it in one, the experiment cannot measure it").


def test_frozen_prompt_disabled_by_default_never_regrounds():
    ungrounded = _answer(citations=[])
    client = _ScriptedClient([ungrounded])
    parsed, stop_reason, usage, regrounded, cr_before, cr_after = rae._answer_from_frozen_prompt(
        client, "fake-model", "system", "user",
    )
    assert client.calls == 1
    assert parsed is ungrounded
    assert regrounded is False
    assert cr_before == 0
    assert cr_after is None


def test_frozen_prompt_reground_enabled_fires_once():
    first = _answer(citations=[])
    second = _answer(citations=["601.2b"])
    client = _ScriptedClient([first, second])
    parsed, stop_reason, usage, regrounded, cr_before, cr_after = rae._answer_from_frozen_prompt(
        client, "fake-model", "system", "user", reground=True,
    )
    assert client.calls == 2
    assert parsed is second
    assert regrounded is True
    assert cr_before == 0
    assert cr_after == 1


def test_frozen_prompt_reground_usage_folds_both_calls():
    first_resp = _FakeResponse(
        _answer(citations=[]), usage=_FakeUsage(input_tokens=100, output_tokens=50),
    )
    second_resp = _FakeResponse(
        _answer(citations=["601.2b"]), usage=_FakeUsage(input_tokens=120, output_tokens=60),
    )
    client = _ScriptedClient([first_resp, second_resp])
    parsed, stop_reason, usage, regrounded, cr_before, cr_after = rae._answer_from_frozen_prompt(
        client, "fake-model", "system", "user", reground=True,
    )
    assert regrounded is True
    # A regrounded row costs two generations -- usage must reflect both, not
    # just the final response, or every downstream cost tool undercounts it.
    assert usage["input_tokens"] == 220
    assert usage["output_tokens"] == 110
