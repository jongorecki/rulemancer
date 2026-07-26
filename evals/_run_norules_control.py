"""Thin wrapper around run_answer_eval.main() that registers a
'norules_control' SYSTEM_VERSIONS key at runtime (monkeypatch, not a source
edit) so RulesAgent's constructor-time validity gate accepts
--system-version norules_control for provenance stamping.

Content is irrelevant here beyond passing that gate: the --prompts-cache
path (_answer_from_frozen_prompt) reads system/user straight from the frozen
prompts file built by build_norules_prompts.py and never touches
RulesAgent.system or SYSTEM_VERSIONS. This just stops the run from being
mis-recorded as system_version=3 (which would falsely claim it used
SYSTEM_V3's rules-only framing).

Run exactly like run_answer_eval.py, e.g.:
  uv run python evals/_run_norules_control.py --prompts-cache ... --system-version norules_control ...
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.generate.answer import SYSTEM_VERSIONS  # noqa: E402
from build_norules_prompts import CONTROL_SYSTEM  # noqa: E402

SYSTEM_VERSIONS["norules_control"] = CONTROL_SYSTEM

import run_answer_eval  # noqa: E402

if __name__ == "__main__":
    run_answer_eval.main()
