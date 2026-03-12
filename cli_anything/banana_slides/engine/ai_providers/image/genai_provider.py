"""
Google GenAI SDK -- image generation provider (standalone, no Flask)
"""
import logging
from typing import Optional, List
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import ImageProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2


def _make_client(api_key=None, api_base=None, timeout_s=300.0):
    timeout_ms = int(timeout_s * 1000)
    opts = types.HttpOptions(timeout=timeout_ms, base_url=api_base)
    return genai.Client(http_options=opts, api_key=api_key)


class GenAIImageProvider(ImageProvider):
    """Image generation via Google GenAI SDK (AI Studio)"""

    def __init__(self, model: str = "gemini-3-pro-image-preview",
                 api_key: str = None, api_base: str = None):
        self.client = _make_client(api_key=api_key, api_base=api_base)
        self.model = model

    @retry(
        stop=stop_after_attempt(_MAX_RETRIES + 1),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def generate_image(
        self,
        prompt: str,
        ref_images: Optional[List[Image.Image]] = None,
        aspect_ratio: str = "16:9",
        resolution: str = "2K",
        enable_thinking: bool = True,
        thinking_budget: int = 1024
    ) -> Optional[Image.Image]:
        try:
            contents = []
            if ref_images:
                for ref_img in ref_images:
                    contents.append(ref_img)
            contents.append(prompt)

            config_params = {
                'response_modalities': ['TEXT', 'IMAGE'],
                'image_config': types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=resolution,
                ),
            }
            if enable_thinking:
                config_params['thinking_config'] = types.ThinkingConfig(
                    thinking_budget=thinking_budget,
                    include_thoughts=True,
                )

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(**config_params),
            )

            last_image = None
            for i, part in enumerate(response.parts):
                if part.text is not None:
                    logger.debug("Part %d: TEXT - %s", i, part.text[:100])
                else:
                    try:
                        image = part.as_image()
                        if image:
                            if isinstance(image, Image.Image):
                                last_image = image
                            elif hasattr(image, 'image_bytes') and image.image_bytes:
                                last_image = Image.open(BytesIO(image.image_bytes))
                            elif hasattr(image, '_pil_image') and image._pil_image:
                                last_image = image._pil_image
                    except Exception as e:
                        logger.warning("Part %d: Failed to extract image - %s", i, e)

            if last_image:
                return last_image

            raise ValueError("No image found in API response.")

        except Exception as e:
            error_detail = f"Error generating image with GenAI: {type(e).__name__}: {e}"
            logger.error(error_detail, exc_info=True)
            raise Exception(error_detail) from e
