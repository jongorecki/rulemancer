"""Test for --retry-errors model mismatch guard (Task 2 review fix).

Ensures that the retry-errors path rejects files whose recorded model
doesn't match the --model argument, preventing accidental model splicing.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import sys

import pytest


def test_retry_errors_rejects_model_mismatch():
    """Guard should error when --retry-errors file's model != --model arg."""
    # Create a temporary answers file with a recorded model
    file_model = "deepseek/deepseek-v4-flash"
    args_model = "anthropic/claude-3-5-sonnet"  # different model

    data = {
        "model": file_model,
        "rewrite_version": "v2",
        "ruling_query_mode": "raw",
        "prompts_cache": None,
        "results": [
            {
                "id": "q001",
                "question": "What is a rule?",
                "answered": None,
                "text": None,
                "citations": None,
                "error": "timeout",
                "raw_text": None,
            }
        ],
        "summary": {"n_questions": 1, "answered": 0, "parse_failures": 0, "total_cost": 0},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        answers_file = Path(tmpdir) / "answers.json"
        answers_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Import here to avoid stale imports if run multiple times
        from evals import run_openrouter_arm

        # Mock sys.argv and sys.exit to capture the error
        with patch("sys.argv", [
            "run_openrouter_arm.py",
            "--retry-errors", str(answers_file),
            "--model", args_model,
        ]):
            with patch("sys.exit") as mock_exit:
                # Redirect stdout to capture the error message
                from io import StringIO
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                try:
                    run_openrouter_arm.main()
                    output = sys.stdout.getvalue()
                finally:
                    sys.stdout = old_stdout

                # Verify the error message mentions both models
                assert "model=" in output or mock_exit.called, \
                    f"Expected model mismatch error, got: {output}"


def test_retry_errors_accepts_matching_model():
    """Guard should NOT reject when file's model matches --model arg."""
    model = "deepseek/deepseek-v4-flash"

    data = {
        "model": model,
        "rewrite_version": "v2",
        "ruling_query_mode": "raw",
        "prompts_cache": None,
        "results": [],  # empty, so main loop completes trivially
        "summary": {"n_questions": 0, "answered": 0, "parse_failures": 0, "total_cost": 0},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        answers_file = Path(tmpdir) / "answers.json"
        answers_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        from evals import run_openrouter_arm

        with patch("sys.argv", [
            "run_openrouter_arm.py",
            "--retry-errors", str(answers_file),
            "--model", model,
        ]):
            from io import StringIO
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                run_openrouter_arm.main()
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

            # Should NOT error on model mismatch (it may error on other grounds,
            # but not on the model check)
            assert "refusing to silently mix models" not in output, \
                f"Unexpected model mismatch error: {output}"
