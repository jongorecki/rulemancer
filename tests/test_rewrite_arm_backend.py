"""Slice B tests: wiring the gpt5mini OpenRouter rewriter arm into
evals/run_eval.py -- REWRITE_MODELS gets a slash-free label, rewrite_arm_name
stays slash-free with it (arm names are interpolated into dict keys used
throughout the report code), and the model-id -> backend derivation used at
the rewrite_query() call site (run_eval.py:210) is a small pure function so
it's testable without running the full eval (which needs live rules/vector
data this worktree doesn't have).

Importing evals.run_eval is safe -- module-level code only defines constants
and functions; nothing runs until main() is called, same assumption already
relied on by tests/test_resume_prompts_cache_guard.py importing
evals.run_answer_eval / evals.run_openrouter_arm.
"""

from evals import run_eval as re


def test_rewrite_models_has_slash_free_gpt5mini_label():
    assert re.REWRITE_MODELS["gpt5mini"] == "openai/gpt-5-mini"
    assert "/" not in "gpt5mini"


def test_rewrite_models_existing_entries_unchanged():
    assert re.REWRITE_MODELS["haiku"] == "claude-haiku-4-5"
    assert re.REWRITE_MODELS["sonnet"] == "claude-sonnet-5"


def test_rewrite_arm_name_stays_slash_free_for_gpt5mini():
    name = re.rewrite_arm_name("gpt5mini", 1)
    assert "/" not in name
    assert name == "vec+rw1-gpt5mini"


def test_backend_for_model_is_openrouter_for_slash_ids():
    assert re.rewrite_backend_for_model("openai/gpt-5-mini") == "openrouter"


def test_backend_for_model_is_anthropic_for_non_slash_ids():
    assert re.rewrite_backend_for_model("claude-haiku-4-5") == "anthropic"
    assert re.rewrite_backend_for_model("claude-sonnet-5") == "anthropic"


def test_backend_for_model_matches_every_rewrite_models_entry():
    expected = {"haiku": "anthropic", "sonnet": "anthropic", "gpt5mini": "openrouter"}
    for label, model in re.REWRITE_MODELS.items():
        assert re.rewrite_backend_for_model(model) == expected[label]
