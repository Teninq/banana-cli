"""
OpenAI SDK implementation for image generation (standalone, no Flask)
"""
import logging
import base64
import re
import requests
from io import BytesIO
from typing import Optional, List
from openai import OpenAI
from PIL import Image
from .base import ImageProvider

logger = logging.getLogger(__name__)

_TIMEOUT = 300.0
_MAX_RETRIES = 2


class OpenAIImageProvider(ImageProvider):
    """Image generation using OpenAI SDK (compatible with Gemini via proxy)"""

    def __init__(self, api_key: str, api_base: str = None,
                 model: str = "gemini-3-pro-image-preview"):
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=_TIMEOUT,
            max_retries=_MAX_RETRIES,
        )
        self.api_base = api_base or ""
        self.model = model

    def _encode_image_to_base64(self, image: Image.Image) -> str:
        buffered = BytesIO()
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        image.save(buffered, format="JPEG", quality=95)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def _build_extra_body(self, aspect_ratio: str, resolution: str) -> dict:
        resolution_upper = resolution.upper()
        return {
            "aspect_ratio": aspect_ratio,
            "resolution": resolution_upper,
            "generationConfig": {
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                    "imageSize": resolution_upper,
                }
            },
        }

    def generate_image(
        self,
        prompt: str,
        ref_images: Optional[List[Image.Image]] = None,
        aspect_ratio: str = "16:9",
        resolution: str = "2K",
        enable_thinking: bool = False,
        thinking_budget: int = 0
    ) -> Optional[Image.Image]:
        try:
            content = []
            if ref_images:
                for ref_img in ref_images:
                    base64_image = self._encode_image_to_base64(ref_img)
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    })
            content.append({"type": "text", "text": prompt})

            extra_body = self._build_extra_body(aspect_ratio, resolution)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"aspect_ratio={aspect_ratio}, resolution={resolution}"},
                    {"role": "user", "content": content},
                ],
                modalities=["text", "image"],
                extra_body=extra_body,
            )

            message = response.choices[0].message

            # Try 'images' field (OpenRouter / newer API format)
            raw = message.model_dump() if hasattr(message, 'model_dump') else {}
            images_list = raw.get('images') or getattr(message, 'images', None)
            if images_list:
                for img_item in images_list:
                    if isinstance(img_item, dict):
                        url = (img_item.get('image_url') or {}).get('url', '')
                    elif hasattr(img_item, 'image_url'):
                        iu = img_item.image_url
                        url = iu.get('url', '') if isinstance(iu, dict) else getattr(iu, 'url', '')
                    else:
                        continue
                    if url.startswith('data:image'):
                        base64_data = url.split(',', 1)[1]
                        return Image.open(BytesIO(base64.b64decode(base64_data)))
                    elif url.startswith('http'):
                        resp = requests.get(url, timeout=60, stream=True)
                        resp.raise_for_status()
                        img = Image.open(BytesIO(resp.content))
                        img.load()
                        return img

            # Try multi_mod_content (Google AI Studio format)
            if hasattr(message, 'multi_mod_content') and message.multi_mod_content:
                for part in message.multi_mod_content:
                    if "inline_data" in part:
                        image_data = base64.b64decode(part["inline_data"]["data"])
                        return Image.open(BytesIO(image_data))

            # Try standard content format
            if hasattr(message, 'content') and message.content:
                if isinstance(message.content, list):
                    for part in message.content:
                        if isinstance(part, dict):
                            if part.get('type') == 'image_url':
                                image_url = part.get('image_url', {}).get('url', '')
                                if image_url.startswith('data:image'):
                                    base64_data = image_url.split(',', 1)[1]
                                    return Image.open(BytesIO(base64.b64decode(base64_data)))
                        elif hasattr(part, 'type') and part.type == 'image_url':
                            image_url = getattr(part, 'image_url', {})
                            url = image_url.get('url', '') if isinstance(image_url, dict) else getattr(image_url, 'url', '')
                            if url.startswith('data:image'):
                                base64_data = url.split(',', 1)[1]
                                return Image.open(BytesIO(base64.b64decode(base64_data)))

                elif isinstance(message.content, str):
                    content_str = message.content
                    # Try markdown image URL
                    md_matches = re.findall(r'!\[.*?\]\((https?://[^\s\)]+)\)', content_str)
                    if md_matches:
                        resp = requests.get(md_matches[0], timeout=30, stream=True)
                        resp.raise_for_status()
                        img = Image.open(BytesIO(resp.content))
                        img.load()
                        return img

                    # Try base64 data URL
                    b64_matches = re.findall(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', content_str)
                    if b64_matches:
                        return Image.open(BytesIO(base64.b64decode(b64_matches[0])))

            raise ValueError("No valid multimodal response received from OpenAI API")

        except Exception as e:
            error_detail = f"Error generating image with OpenAI (model={self.model}): {type(e).__name__}: {e}"
            logger.error(error_detail, exc_info=True)
            raise Exception(error_detail) from e
