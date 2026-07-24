**SPIKE, not a design doc.** De-risking run for `docs/plan-cost-calculator-tool.md` §3d's
open item ("Whether `anthropic.Anthropic().messages.parse(..., output_format=Answer)`
supports `tools=` in the same call... Unverified"). Scripts live in
`evals/_spikes/spike1_parse_plus_tools.py`, `spike2_manual_loop.py`,
`spike3_openrouter_tools.py`. Nothing production was touched. All calls below
are real API calls (Claude `claude-sonnet-5` via the Anthropic SDK, `openai/gpt-5-mini`
via OpenRouter's chat-completions API) run 2026-07-23.

## 1. Does `messages.parse(output_format=...)` accept `tools=`?

**Yes -- no conflict, no error.** `client.messages.parse(model=..., tools=TOOLS,
output_format=TinyAnswer, ...)` returns normally. But structured-output and
tool-use don't *fuse* into one behavior: when the model decides to call a tool,
the response comes back with `stop_reason == "tool_use"`, `content` holding a
`tool_use` block, and **`parsed_output` is `None`** -- the parse helper only
populates `parsed_output` on a turn that actually returns final text matching
the schema. `output_format` doesn't force the model to skip tool use; it
constrains whichever turn ends the conversation.

```
=== Attempt: client.messages.parse(output_format=TinyAnswer, tools=[add]) ===
SUCCESS -- no exception raised.
stop_reason: tool_use
content blocks: ['tool_use']
  block: ToolUseBlock(id='toolu_01DGDB11HXkGq9aVN6hWez7s', caller=DirectCaller(type='direct'), input={'a': 482, 'b': 917}, name='add', type='tool_use')
parsed_output: None
```

So the load-bearing question from the plan is answered directly: they don't
conflict at the API/SDK level. The consequence is that `.parse()` alone is not
a complete solution -- it's still on the caller to detect `tool_use`, run the
tool, and loop.

## 2. Working alternative -- keep `tools=` AND `output_format=` on every call, loop on `stop_reason`

The plan's own draft (§3b.2) predicted the shape would be a manual loop using
`client.messages.create(tools=...)`, with the *final* call either reusing
`.parse(output_format=...)` with `tools` still attached, or dropping `tools`
on a last call -- and flagged that choice as unsettled. **Tested directly: no
special final call is needed.** The same `client.messages.parse(tools=TOOLS,
output_format=Answer)` call can be reissued every round, unchanged in shape,
and it naturally returns a populated `parsed_output` on the turn where the
model stops calling tools:

**Case A -- one tool call needed** (full transcript, `evals/_spikes/spike2_manual_loop.py`):

```
--- round 1 ---
stop_reason: tool_use
content block types: ['thinking', 'tool_use']
parsed_output: None
executing tool 'add' input={'a': 482, 'b': 917} -> 1399
--- round 2 ---
stop_reason: end_turn
content block types: ['text']
parsed_output: result=1399 explanation='Used the add tool to compute 482 + 917, which equals 1399.'

FINAL: total rounds: 2, final stop_reason: end_turn
final parsed_output: result=1399 explanation='Used the add tool to compute 482 + 917, which equals 1399.'
```

**Case B -- two sequential tool calls needed** (model must chain two `add`
calls, the second consuming the first's result):

```
--- round 1 ---
stop_reason: tool_use  -> add(15, 27) -> 42
--- round 2 ---
stop_reason: tool_use  -> add(42, 100) -> 142
--- round 3 ---
stop_reason: end_turn
parsed_output: result=142 explanation='Added 15 and 27 to get 42, then added 42 and 100 to get 142.'

FINAL: total rounds: 3, final stop_reason: end_turn
```

The loop shape that worked, matching the standard SDK manual-loop pattern
(`shared/tool-use-concepts.md` -- Manual Agentic Loop), with `output_format`
simply left attached on every iteration:

```python
messages = [{"role": "user", "content": user}]
for _ in range(max_rounds):
    response = client.messages.parse(
        model=MODEL, max_tokens=..., system=system, messages=messages,
        tools=TOOLS, output_format=Answer,
    )
    if response.stop_reason != "tool_use":
        break  # response.parsed_output is now populated
    messages.append({"role": "assistant", "content": response.content})
    tool_results = [
        {"type": "tool_result", "tool_use_id": b.id, "content": run_tool(b.name, b.input)}
        for b in response.content if b.type == "tool_use"
    ]
    messages.append({"role": "user", "content": tool_results})
```

This resolves the plan's open item cleanly: the production integration does
**not** need a tools-off/output-format-on final call as a separate code path
-- one call shape, looped, works end to end.

## 3. Round-trip count and reliability

- **One tool call -> 2 round trips** (the tool-use turn, then the terminal
  turn carrying the structured answer).
- **Two sequential/chained tool calls -> 3 round trips** (one per tool call,
  plus the terminal turn). Round trips scale 1:1 with tool calls, plus one.
- **Reliability, n=2 (both cases in this spike):** both runs terminated with
  `stop_reason: end_turn` and a schema-valid `parsed_output` on the very next
  call after the last tool result was supplied -- the model did not loop
  further, re-call a tool unnecessarily, or return `tool_use` again after
  having what it needed. This is a small sample (2 runs, trivial tool) --
  not a claim about c014-scale prompts with a real `calculate_cost` tool and
  the full production system prompt, which behaves differently at the
  complexity the plan is actually targeting. Production integration should
  still keep the plan's proposed cap (small fixed round limit, e.g. 2-3,
  mirroring the existing empty-draw retry budget at `answer.py`:1187) as a
  guard against a confused model looping, since this spike didn't stress that.

## 4. OpenRouter / gpt-5-mini viability

**Viable -- gpt-5-mini calls tools and honors combined `tools` +
`response_format` (strict json_schema) via OpenRouter's chat-completions API**,
tested with `provider: {allow_fallbacks: false}` (matching
`openrouter_backend.py`'s existing pattern) and both `tools` and
`response_format` sent in the same request body, same as round 1 of a normal
loop:

Round 1 (tools + response_format, no prior history) -- HTTP 200, model chose
to call the tool rather than answer directly or reject the combined request:

```
finish_reason: tool_calls
tool_calls: [{'type': 'function', 'id': 'call_tfHy4qqN1WEXbhu0aaI3cAuC',
              'function': {'name': 'add', 'arguments': '{"a":482,"b":917}'}}]
message.content: None
```

(gpt-5-mini is a reasoning model and returned a `reasoning`/`reasoning_details`
block alongside the tool call -- expected, consistent with the existing
`NO_TEMPERATURE` special-casing already in `openrouter_backend.py` for this
model.)

Round 2 (tool result appended as a `role: "tool"` message, same `tools` +
`response_format` body resent) -- HTTP 200, model stopped calling tools and
returned schema-valid JSON:

```
finish_reason: stop
message.content: {"result":1399,"explanation":"Computed by calling the add tool with 482 and 917."}
PARSED FINAL ANSWER: {'result': 1399, 'explanation': 'Computed by calling the add tool with 482 and 917.'}
```

2 round trips, matching the Anthropic-path count for the same single-tool-call
shape. This is a minimal check (one trivial tool, one call) against the raw
OpenRouter API, not a port of `openrouter_backend.py`'s `generate()` -- per
the task, confirming viability rather than building the integration. The real
port would need: extending `_attempt()`'s request body with `tools`, handling
`finish_reason == "tool_calls"` as a new branch alongside the existing
error/parse-failure handling, and appending `role: "tool"` results in the
loop -- structurally analogous to the Anthropic manual loop in §2, on the
OpenAI-style wire format instead of Anthropic's `tool_use`/`tool_result`
blocks.

## 5. Recommendation

The full cost-calculator build is **not** blocked by anything SDK-shaped. The
plan's central unresolved question -- parse-vs-tools conflict -- doesn't
exist: `tools=` and `output_format=` coexist in a single call shape that can
be reused unchanged across every round of the loop, with the SDK naturally
signaling completion via `parsed_output` being non-`None` once
`stop_reason != "tool_use"`. That simplifies §3b.2 of the plan: drop the
"not settled here" branching between a same-shaped final call vs. a
tools-off/output-format-on final call -- there's only one call shape needed,
looped.

What the plan should still treat as open, because this spike didn't test it:
whether the *production* system prompt (much larger, with the existing
symbol-reference and cost-math instructions already in `SYSTEM_V4NL`) and a
real multi-field `calculate_cost` tool (not a toy `add`) preserve the same
clean 2-3-round convergence seen here with a trivial tool and a two-line
system prompt. The loop mechanics are proven; whether the model reliably
converges to a *correct* tool call (right modifier classification, right
`{X}` handling) at production complexity is exactly the §5 "honest failure
mode" the plan already flags, and remains a question for the real build +
eval, not this spike. OpenRouter/gpt-5-mini is confirmed viable at the same
mechanical level -- the plan's §3d/§7 deferral of that path to a second,
structurally similar integration still stands; nothing here says it's
harder than the Anthropic path, just that it's still a second thing to
build.
