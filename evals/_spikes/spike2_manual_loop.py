"""
Spike 2 -- Unknown #2/#3: working alternative when messages.parse() hits
stop_reason=="tool_use" (parsed_output=None). Manual loop: keep calling
client.messages.parse(tools=..., output_format=...) each turn, appending the
tool_use block + a tool_result message, until parsed_output is populated
(i.e. the model stops calling tools and returns the final structured Answer).

This also answers #3: round-trip count, and whether the model reliably
emits the final structured answer after the tool result.

Run same way as spike1.
"""
import os
from pathlib import Path

from pydantic import BaseModel

import anthropic

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


def run_add_tool(input_: dict) -> str:
    return str(input_["a"] + input_["b"])


def run_case(system: str, user: str, max_rounds: int = 4) -> None:
    client = anthropic.Anthropic()
    messages: list[dict] = [{"role": "user", "content": user}]

    round_count = 0
    parsed = None
    response = None
    for round_count in range(1, max_rounds + 1):
        print(f"--- round {round_count}: calling messages.parse(tools=..., output_format=TinyAnswer) ---")
        response = client.messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=system,
            messages=messages,
            tools=TOOLS,
            output_format=TinyAnswer,
        )
        print("  stop_reason:", response.stop_reason)
        print("  content block types:", [b.type for b in response.content])
        parsed = response.parsed_output
        print("  parsed_output:", parsed)

        if response.stop_reason != "tool_use":
            break

        # Append assistant turn (raw content, including tool_use blocks)
        messages.append({"role": "assistant", "content": response.content})

        # Execute every tool_use block, collect tool_result blocks
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "add":
                    result_text = run_add_tool(block.input)
                else:
                    result_text = f"unknown tool {block.name}"
                print(f"  executing tool '{block.name}' input={block.input} -> {result_text}")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    print()
    print("=== FINAL ===")
    print("total rounds:", round_count)
    print("final stop_reason:", response.stop_reason if response else None)
    print("final parsed_output:", parsed)
    print()


if __name__ == "__main__":
    print("########## CASE A: single tool call needed ##########")
    run_case(
        system=(
            "You must call the `add` tool to compute any sum -- never add numbers "
            "yourself. After you get the tool result, respond with the final "
            "structured answer: result = the sum, explanation = a one-sentence "
            "note on how you got it."
        ),
        user="What is 482 + 917? Use the add tool, then give the final answer.",
    )

    print()
    print("########## CASE B: two sequential tool calls needed ##########")
    run_case(
        system=(
            "You must call the `add` tool for every addition -- never add numbers "
            "yourself, even intermediate sums. After all additions are done, "
            "respond with the final structured answer: result = the final total, "
            "explanation = a one-sentence note on the steps."
        ),
        user=(
            "Compute (15 + 27) + 100 using the add tool for each addition step "
            "(so two separate add calls, the second using the first's result), "
            "then give the final answer."
        ),
        max_rounds=5,
    )
