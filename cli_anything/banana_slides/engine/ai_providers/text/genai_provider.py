"""
Google GenAI SDK -- text generation provider (standalone, no Flask)
"""
import logging
from typing import Generator
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import TextProvider, strip_think_tags

logger = logging.getLogger(__name__)

# Default retry config (no Flask config dependency)
_MAX_RETRIES = 2


def _log_retry(retry_state):
    logger.warning(
        "GenAI request failed, retrying (%d/%d), error: %s",
        retry_state.attempt_number, _MAX_RETRIES + 1,
        retry_state.outcome.exception() if retry_state.outcome else 'unknown'
    )


def _validate_response(response):
    if response.text is None:
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                logger.warning("Response text is None, finish_reason: %s", candidate.finish_reason)
        raise ValueError("AI model returned empty response (response.text is None)")
    return strip_think_tags(response.text)


def _make_client(api_key=None, api_base=None, timeout_s=300.0):
    """Construct a genai.Client for AI Studio."""
    timeout_ms = int(timeout_s * 1000)
    opts = types.HttpOptions(timeout=timeout_ms, base_url=api_base)
    return genai.Client(http_options=opts, api_key=api_key)


class GenAITextProvider(TextProvider):
    """Text generation via Google GenAI SDK (AI Studio)"""

    def __init__(self, model: str = "gemini-3-flash-preview",
                 api_key: str = None, api_base: str = None):
        self.client = _make_client(api_key=api_key, api_base=api_base)
        self.model = model

    @retry(
        stop=stop_after_attempt(_MAX_RETRIES + 1),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
        before_sleep=_log_retry
    )
    def generate_text(self, prompt: str, thinking_budget: int = 0) -> str:
        config_params = {}
        if thinking_budget > 0:
            config_params['thinking_config'] = types.ThinkingConfig(thinking_budget=thinking_budget)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_params) if config_params else None,
        )
        return _validate_response(response)

    def generate_text_stream(self, prompt: str, thinking_budget: int = 0) -> Generator[str, None, None]:
        config_params = {}
        if thinking_budget > 0:
            config_params['thinking_config'] = types.ThinkingConfig(thinking_budget=thinking_budget)

        response = self.client.models.generate_content_stream(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_params) if config_params else None,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text
