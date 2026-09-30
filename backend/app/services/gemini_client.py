import json
import logging
import re
import time
from typing import Any, Callable, TypeVar

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from app.config import get_settings

logger = logging.getLogger("app.gemini")

settings = get_settings()
_configured = False
_model_cache: dict[str, Any] = {}

T = TypeVar("T")

_RETRY_SECONDS_RE = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)
MAX_RATE_LIMIT_RETRIES = 2
MAX_RATE_LIMIT_WAIT_SECONDS = 65


def _call_with_rate_limit_retry(fn: Callable[[], T]) -> T:
    """Gemini's free tier allows as few as 5 requests/minute per model, so any
    real usage of this app trips it. Retry on 429s using the wait time the API
    itself reports, instead of surfacing a hard failure for a transient limit.
    """
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            return fn()
        except ResourceExhausted as exc:
            if attempt == MAX_RATE_LIMIT_RETRIES:
                raise
            match = _RETRY_SECONDS_RE.search(str(exc))
            wait_seconds = min(float(match.group(1)), MAX_RATE_LIMIT_WAIT_SECONDS) if match else 20.0
            wait_seconds += 2  # buffer so we land just after the quota window resets
            logger.warning(
                "Gemini rate limit hit (attempt %s/%s), waiting %.0fs before retrying",
                attempt + 1,
                MAX_RATE_LIMIT_RETRIES,
                wait_seconds,
            )
            time.sleep(wait_seconds)
    raise AssertionError("unreachable")  # loop always returns or raises


def _ensure_configured() -> None:
    global _configured
    if not _configured:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to backend/.env")
        genai.configure(api_key=settings.gemini_api_key)
        _configured = True


def _get_model(system_instruction: str):
    _ensure_configured()
    key = f"{settings.gemini_model}::{hash(system_instruction)}"
    if key not in _model_cache:
        _model_cache[key] = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=system_instruction,
        )
    return _model_cache[key]


_JSON_BLOCK_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


def _extract_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"Model did not return parseable JSON: {text[:500]}")


class GeminiAgent:
    """Thin wrapper around a Gemini model bound to one agent's system prompt."""

    def __init__(self, system_instruction: str, temperature: float = 0.2):
        self.system_instruction = system_instruction
        self.temperature = temperature

    def generate_json(self, prompt: str) -> Any:
        model = _get_model(self.system_instruction)

        def call():
            return model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=self.temperature,
                    response_mime_type="application/json",
                ),
            )

        response = _call_with_rate_limit_retry(call)
        text = response.text
        try:
            return _extract_json(text)
        except (ValueError, json.JSONDecodeError):
            logger.error("Gemini returned non-JSON output: %s", text[:1000])
            raise

    def generate_text(self, prompt: str) -> str:
        model = _get_model(self.system_instruction)

        def call():
            return model.generate_content(
                prompt, generation_config=genai.GenerationConfig(temperature=self.temperature)
            )

        response = _call_with_rate_limit_retry(call)
        return (response.text or "").strip()
