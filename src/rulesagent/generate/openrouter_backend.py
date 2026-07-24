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
import random
import time
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


def build_strict_schema(schema: dict) -> dict:
    """Turn a pydantic `.model_json_schema()` dict into OpenRouter's strict
    json_schema shape: no top-level title, additionalProperties: False,
    every property required, no per-property title. Shared by
    `_answer_schema()` (Answer, used by generate()/_attempt()) and the
    OpenRouter rewrite arm's `_Rewrites` schema (rewrite.py) so both follow
    identical strict-schema rules instead of two copies of this logic."""
    schema.pop("title", None)
    schema["additionalProperties"] = False
    schema["required"] = list(schema["properties"].keys())
    for prop in schema["properties"].values():
        prop.pop("title", None)
    return schema


def _answer_schema() -> dict:
    """Answer's JSON schema in the strict shape OpenRouter requires
    (additionalProperties: false, every property required)."""
    return build_strict_schema(Answer.model_json_schema())


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
             timeout: float = 300.0,
             reasoning: dict | None = None) -> ORResult:
    """One answer from `model` for an already-assembled prompt pair.

    Retries two failure classes, both measured on the 2026-07-22 arm runs:
    transient HTTP (429/5xx -- DeepInfra rate limits took 31/50 v4-flash
    questions) inside `_attempt`, and truncated-parse responses (Google
    aborted gemini-flash-lite generations mid-string, returning partial
    JSON with completion_tokens=0 as an HTTP 200) via up to two re-asks
    here. A model that GENUINELY can't follow the schema still surfaces:
    its parse failures are consistent, not stochastic, and the third
    failure is recorded honestly with the raw text kept.

    `reasoning` (docs/plan-condition-e-reasoning.md Sec 2): optional
    OpenRouter `reasoning` request-parameter dict, e.g. {"effort": "high"}.
    Defaults to None -- omitted from the request body entirely, so every
    call site that doesn't pass it (every past eval run) sends the exact
    body it always has. Passed straight through to `_attempt()` unchanged."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return ORResult(None, model, None, None, None, None,
                        error="OPENROUTER_API_KEY not set")
    result = None
    for _ in range(3):
        result = _attempt(system, user, model, key, timeout, reasoning=reasoning)
        if result.answer is not None:
            return result
        if result.error and not result.error.startswith("parse"):
            return result  # definitive non-parse failure -- don't re-ask
        time.sleep(1.0 + random.uniform(0, 1))
    return result


def _post_with_retries(body: dict, key: str, timeout: float) -> tuple[dict | None, str | None]:
    """POST `body` to OpenRouter with the same bounded-retry policy
    `_attempt()` has always used, extracted here so a second caller
    (`call_structured()` below) gets identical retry behavior without
    duplicating it. Returns (parsed_response_json, None) on success, or
    (None, last_error_string) if every attempt failed.

    Transient upstream failures (429 from a pinned provider, 5xx) get a
    bounded retry with backoff -- the v4-flash arm lost 31/50 questions to
    DeepInfra 429s on the first full run (2026-07-22), which is a provider
    traffic condition, not a model answer. Anything else still fails fast
    and is recorded honestly. Retry-After is honored when present.

    One additional case added 2026-07-23 (docs/plan-v3-execution-tasks.md
    Task 2 content-completeness gap-fill): a 400 whose OpenRouter error body
    carries provider_error_code "400001" / "This response_format type is
    unavailable now" -- confirmed by direct testing to be a StreamLake
    (deepseek-v4-pro's provider) capacity condition, not a malformed
    request: identical requests succeeded on a plain retry, no request
    change. A real malformed-request 400 (bad schema, bad model id) still
    fails fast -- this only widens retry for this one detected body shape."""
    data = None
    last_err = None
    for attempt in range(5):
        try:
            r = httpx.post(API_URL, json=body, timeout=timeout,
                           headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            data = r.json()
            break
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            last_err = f"http: {e}"
            retryable_400 = False
            if status == 400:
                try:
                    err_body = e.response.json().get("error", {})
                    retryable_400 = err_body.get("metadata", {}).get("provider_error_code") == "400001"
                except Exception:
                    retryable_400 = False
            if status == 429 or status >= 500 or retryable_400:
                retry_after = e.response.headers.get("retry-after")
                delay = (float(retry_after) if retry_after and
                         retry_after.replace(".", "", 1).isdigit()
                         else 2.0 * (2 ** attempt))
                time.sleep(min(delay, 60.0) + random.uniform(0, 1))
                continue
            break  # non-retryable HTTP error
        except httpx.HTTPError as e:  # timeouts, connection failures
            last_err = f"http: {e}"
            time.sleep(2.0 * (2 ** attempt) + random.uniform(0, 1))
        except json.JSONDecodeError as e:
            # A malformed/truncated HTTP 200 body (docs/plan-run-progress.md
            # Sec 4 -- the bug that crashed the first default r2: Google
            # aborting gemini-flash-lite generations mid-stream still
            # returns a 200, so r.raise_for_status() never fires and the
            # decode error used to escape this loop entirely, uncaught,
            # killing the whole run with zero rows saved). Treated exactly
            # like a transient HTTP failure -- bounded retry with backoff,
            # not a fatal exception -- so a re-ask has a real chance of
            # getting a complete body next time.
            last_err = f"json: {e}"
            time.sleep(2.0 * (2 ** attempt) + random.uniform(0, 1))
    return data, last_err


def call_structured(system: str, user: str, model: str, schema: dict,
                     schema_name: str = "output", timeout: float = 300.0) -> dict | None:
    """Generic structured-output call: send `system`/`user` to `model` via
    OpenRouter, constrained to `schema` (already strict-shaped -- see
    `build_strict_schema()`), and return the parsed JSON dict, or None if
    the call failed for any reason (no API key, HTTP failure/exhausted
    retries, an OpenRouter-reported error, or a response that isn't valid
    JSON matching the requested shape).

    This is the minimal shared primitive for non-Answer structured-output
    callers -- currently the rewrite arm's `_Rewrites` schema
    (rulesagent/retrieve/rewrite.py). It reuses `_post_with_retries()` for
    HTTP-level retry (same policy as `_attempt()`), but -- unlike
    `generate()` -- does not add a second retry-on-parse-failure layer:
    callers here (rewrite_query()) already have their own broad
    never-raise/fallback discipline, so a bare best-effort call is enough.

    Same temperature gating as `_attempt()` (:109/:125-126): a model in
    NO_TEMPERATURE gets the key omitted entirely rather than sent as 0 or
    null -- gpt-5-mini (a reasoning model) rejects `temperature` outright."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None

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
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
        "max_tokens": 16384,
    }
    if temperature is not None:
        body["temperature"] = temperature

    data, _last_err = _post_with_retries(body, key, timeout)
    if data is None or "error" in data:
        return None

    try:
        text = data["choices"][0]["message"]["content"]
        return json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None


def _attempt(system: str, user: str, model: str, key: str,
             timeout: float, reasoning: dict | None = None) -> ORResult:

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
    if reasoning is not None:
        # docs/plan-condition-e-reasoning.md Sec 2/Sec 3: OpenRouter's
        # `reasoning` request parameter, e.g. {"effort": "high"}. Only added
        # when explicitly requested -- default None keeps every past eval's
        # request body byte-identical (nothing else here moves).
        body["reasoning"] = reasoning

    data, last_err = _post_with_retries(body, key, timeout)
    if data is None:
        return ORResult(None, model, None, None, temperature, SEED,
                        error=last_err or "http: exhausted retries")

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
