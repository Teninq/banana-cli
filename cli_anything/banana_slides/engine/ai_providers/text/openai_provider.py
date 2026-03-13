"""
OpenAI SDK implementation for text generation (standalone, no Flask)
"""
import base64
import logging
import mimetypes
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

    def generate_text_with_image(self, prompt: str, image_path: str,
                                 thinking_budget: int = 0) -> str:
        mime_type = mimetypes.guess_type(image_path)[0] or "image/png"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return strip_think_tags(response.choices[0].message.content)
