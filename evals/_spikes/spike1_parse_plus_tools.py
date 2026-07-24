"""
Spike 1 -- Unknown #1: does client.messages.parse(output_format=...) accept
tools= in the same call, or do structured-output and tool-use conflict?

Throwaway script. Not wired into the eval harness or CLI. Deletes nothing,
imports nothing from the production package other than what's needed to load
the API key the same way the app does (we don't even need that -- we read
.env directly, read-only).

Run:
    PYTHONIOENCODING=utf-8 PYTHONPATH=<worktree>/src \
    D:/Job_hunt/mtg-rules-bot/.venv/Scripts/python.exe evals/_spikes/spike1_parse_plus_tools.py
"""
import os
import sys
from pathlib import Path

from pydantic import BaseModel

import anthropic

# Load ANTHROPIC_API_KEY read-only from the ORIGINAL repo's .env (never write there).
ENV_PATH = Path(r"D:\Job_hunt\mtg-rules-bot\.env")
if "ANTHROPIC_API_KEY" not in os.environ:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("ANTHROPIC_API_KEY="):
            os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

MODEL = "claude-sonnet-5"


class TinyAnswer(BaseModel):
    result: int
    explanation: str


TOOLS = [
    {
        "name": "add",
        "description": "Add two integers and return their sum. Call this whenever you need to add two numbers rather than doing the arithmetic yourself.",
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
    }
]


def main() -> None:
    client = anthropic.Anthropic()

    print("=== Attempt: client.messages.parse(output_format=TinyAnswer, tools=[add]) ===")
    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=(
                "You must call the `add` tool to compute any sum -- never add "
                "numbers yourself. After getting the tool result, report it."
            ),
            messages=[
                {
                    "role": "user",
                    "content": "What is 482 + 917? Use the add tool, then tell me the result.",
                }
            ],
            tools=TOOLS,
            output_format=TinyAnswer,
        )
        print("SUCCESS -- no exception raised.")
        print("stop_reason:", response.stop_reason)
        print("content blocks:", [(b.type) for b in response.content])
        for b in response.content:
            print("  block:", b)
        print("parsed_output:", response.parsed_output)
    except Exception as e:  # noqa: BLE001 -- spike, we want to see exactly what happens
        print(f"EXCEPTION: {type(e).__name__}: {e}")
        # If it's an SDK/API error, print status code and body if available
        if hasattr(e, "status_code"):
            print("status_code:", e.status_code)
        if hasattr(e, "body"):
            print("body:", e.body)
        if hasattr(e, "response") and e.response is not None:
            try:
                print("raw response text:", e.response.text)
            except Exception:
                pass


if __name__ == "__main__":
    main()
