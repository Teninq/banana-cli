"""
OpenAI SDK implementation for text generation (standalone, no Flask)
"""
import logging
from typing import Generator
from openai import OpenAI
from .base import TextProvider, strip_think_tags

logger = logging.getLogger(__name__)

# Default config (no Flask dependency)
_TIMEOUT = 300.0
_MAX_RETRIES = 2


class OpenAITextProvider(TextProvider):
    """Text generation using OpenAI SDK (compatible with Gemini via proxy)"""

    def __init__(self, api_key: str, api_base: str = None,
                 model: str = "gemini-3-flash-preview"):
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=_TIMEOUT,
            max_retries=_MAX_RETRIES,
        )
        self.model = model

    def generate_text(self, prompt: str, thinking_budget: int = 0) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return strip_think_tags(response.choices[0].message.content)

    def generate_text_stream(self, prompt: str, thinking_budget: int = 0) -> Generator[str, None, None]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
