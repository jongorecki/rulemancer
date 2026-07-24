"""
Spike 3 -- Unknown #4: does the same tool-use pattern work for the
OpenRouter path (gpt-5-mini)? Quick check against OpenRouter's
chat-completions tool API -- NOT a full manual-loop port of
openrouter_backend.py, just enough to see whether gpt-5-mini emits
tool_calls and honors combined tools + response_format (strict json_schema).

Uses raw httpx, matching openrouter_backend.py's own style (no SDK there).

Run same way as spike1/spike2.
"""
import json
import os
from pathlib import Path

import httpx

ENV_PATH = Path(r"D:\Job_hunt\mtg-rules-bot\.env")
if "OPENROUTER_API_KEY" not in os.environ:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY="):
            os.environ["OPENROUTER_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-5-mini"
KEY = os.environ["OPENROUTER_API_KEY"]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two integers and return their sum. Call this whenever you need to add two numbers rather than doing the arithmetic yourself.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        },
    }
]

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "result": {"type": "integer"},
        "explanation": {"type": "string"},
    },
    "required": ["result", "explanation"],
    "additionalProperties": False,
}


def post(body: dict) -> dict:
    r = httpx.post(
        API_URL, json=body, timeout=60.0,
        headers={"Authorization": f"Bearer {KEY}"},
    )
    print("  HTTP status:", r.status_code)
    data = r.json()
    if r.status_code >= 400 or "error" in data:
        print("  ERROR BODY:", json.dumps(data, indent=2)[:2000])
    return data


def main() -> None:
    print("=== Round 1: tools + response_format together, no prior tool history ===")
    messages = [
        {"role": "system", "content": (
            "You must call the `add` tool to compute any sum -- never add "
            "numbers yourself. After the tool result, respond with the final "
            "JSON answer."
        )},
        {"role": "user", "content": "What is 482 + 917? Use the add tool, then give the final answer."},
    ]
    body = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "provider": {"allow_fallbacks": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "answer", "strict": True, "schema": ANSWER_SCHEMA},
        },
        "max_tokens": 4096,
    }
    data = post(body)
    print(json.dumps(data, indent=2)[:3000])

    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    finish_reason = choice.get("finish_reason")
    tool_calls = msg.get("tool_calls")
    print()
    print("finish_reason:", finish_reason)
    print("tool_calls:", tool_calls)
    print("message.content:", msg.get("content"))

    if not tool_calls:
        print()
        print("RESULT: gpt-5-mini did NOT emit a tool_call in round 1 "
              "(either answered directly or the combined tools+response_format "
              "request was rejected/ignored). See body above for detail.")
        return

    # Round 2: feed tool result back, see if it now honors response_format
    print()
    print("=== Round 2: feeding tool_result back, still with tools + response_format ===")
    messages.append(msg)  # assistant turn with tool_calls
    for tc in tool_calls:
        args = json.loads(tc["function"]["arguments"])
        result = str(args["a"] + args["b"])
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": result,
        })

    body2 = dict(body)
    body2["messages"] = messages
    data2 = post(body2)
    print(json.dumps(data2, indent=2)[:3000])

    choice2 = data2.get("choices", [{}])[0]
    msg2 = choice2.get("message", {})
    print()
    print("finish_reason:", choice2.get("finish_reason"))
    print("message.content:", msg2.get("content"))
    if msg2.get("content"):
        try:
            parsed = json.loads(msg2["content"])
            print("PARSED FINAL ANSWER:", parsed)
        except json.JSONDecodeError as e:
            print("content did not parse as JSON:", e)


if __name__ == "__main__":
    main()
