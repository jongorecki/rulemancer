"""OpenRouter generation backend -- EVAL-ONLY (docs/plan-openrouter-models.md).

Runs the byte-identical prompt build_prompt() assembles through a non-Claude
model via OpenRouter, so the answer eval can A/B generators with retrieval
held constant. The shipped app never routes through this module; the pinned
claude-sonnet-5 path in answer.py is untouched.

Standing rules honored here (DESIGN.md):
- The model is pinned per call and provider fallbacks are DISABLED
  (allow_fallbacks: false) -- a silent failover corrupts eval numbers.
- The served model reported by OpenRouter is recorded on every result so an
  arm's answers are attributable.
- temperature=0 and a fixed seed are sent where the model supports them
  (gpt-5-mini rejects temperature -- omit it there). Neither guarantees
  determinism; they reduce draw variance, same caveat as the Haiku rewriter.

Structured output: OpenRouter's response_format json_schema (strict) mapped
from the same Answer contract. Models that can't do strict schema output are
dropped from the candidate list rather than hand-parsed (comparability over
coverage).
"""

import json
import os
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv

from rulesagent.contracts import Answer

load_dotenv()

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Per-model quirks, verified against OpenRouter's supported_parameters
# (2026-07-22): all five candidates support response_format/structured_outputs
# and seed; gpt-5-mini does NOT accept temperature (reasoning model).
NO_TEMPERATURE = {"openai/gpt-5-mini"}

SEED = 42  # fixed across all arms; recorded in the result for the writeup


def _answer_schema() -> dict:
    """Answer's JSON schema in the strict shape OpenRouter requires
    (additionalProperties: false, every property required)."""
    schema = Answer.model_json_schema()
    schema.pop("title", None)
    schema["additionalProperties"] = False
    schema["required"] = list(schema["properties"].keys())
    for prop in schema["properties"].values():
        prop.pop("title", None)
    return schema


@dataclass
class ORResult:
    """One generation call's outcome + the attribution the plan requires."""
    answer: Answer | None       # None = the model's output failed to parse
    requested_model: str
    served_model: str | None    # what OpenRouter says actually ran
    provider: str | None        # upstream provider that served it
    temperature_sent: float | None
    seed_sent: int | None
    usage: dict = field(default_factory=dict)
    raw_text: str | None = None  # kept when parsing failed, for diagnosis
    error: str | None = None


def generate(system: str, user: str, model: str,
             timeout: float = 300.0) -> ORResult:
    """One answer from `model` for an already-assembled prompt pair."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return ORResult(None, model, None, None, None, None,
                        error="OPENROUTER_API_KEY not set")

    temperature = None if model in NO_TEMPERATURE else 0.0
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "provider": {"allow_fallbacks": False},
        "seed": SEED,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "answer", "strict": True,
                            "schema": _answer_schema()},
        },
        "max_tokens": 16384,
    }
    if temperature is not None:
        body["temperature"] = temperature

    try:
        r = httpx.post(API_URL, json=body, timeout=timeout,
                       headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError as e:
        return ORResult(None, model, None, None, temperature, SEED,
                        error=f"http: {e}")

    if "error" in data:
        return ORResult(None, model, None, None, temperature, SEED,
                        error=f"openrouter: {data['error']}")

    served = data.get("model")
    provider = data.get("provider")
    usage = data.get("usage") or {}
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        return ORResult(None, model, served, provider, temperature, SEED,
                        usage=usage, error=f"shape: {e}")

    try:
        answer = Answer.model_validate(json.loads(text))
    except Exception as e:  # invalid JSON or schema mismatch -- keep the raw
        return ORResult(None, model, served, provider, temperature, SEED,
                        usage=usage, raw_text=text, error=f"parse: {e}")

    return ORResult(answer, model, served, provider, temperature, SEED,
                    usage=usage)
