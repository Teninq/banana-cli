"""
Image Analyzer — extract editable elements from slide images using AI vision.

Uses the existing text provider's vision capability to analyze slide images
and return structured element data (text boxes, image regions) with bounding
boxes and style information.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class BBox:
    """Bounding box in pixels: (x0, y0) top-left, (x1, y1) bottom-right."""
    x0: float
    y0: float
    x1: float
    y1: float

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass
class SlideElement:
    """A single editable element extracted from a slide image."""
    element_type: str  # "text" or "image"
    bbox: BBox
    content: str = ""
    style: dict = field(default_factory=dict)
    # style keys: color (hex), bold (bool), font_size (int), alignment (str)


_ANALYSIS_PROMPT = """\
You are analyzing a presentation slide image. Extract ALL visible text elements \
and their positions. Return a JSON array of elements.

For each text element, provide:
- "type": "text"
- "bbox": [x0, y0, x1, y1] — bounding box in pixel coordinates relative to the \
full image dimensions ({width}x{height} pixels)
- "content": the exact text content
- "style": an object with:
  - "color": hex color string like "#FFFFFF"
  - "bold": true/false
  - "font_size": estimated font size in points (integer)
  - "alignment": "left", "center", or "right"

For image/icon regions (non-text visual elements like photos, charts, icons), provide:
- "type": "image"
- "bbox": [x0, y0, x1, y1] — bounding box in pixels
- "content": brief description of the image

Rules:
1. Extract EVERY piece of visible text, including titles, subtitles, bullet points, \
captions, footer text, and page numbers.
2. Each distinct text block should be a separate element — don't merge text that is \
in different visual positions or has different styles.
3. Coordinates must be in pixels within the image bounds (0,0 to {width},{height}).
4. For multi-line text in the same text box, include all lines as one element with \
newlines in "content".
5. Be precise with bounding boxes — they should tightly encompass the text.

Return ONLY the JSON array, with no markdown fences or extra text.
Example:
[
  {{"type":"text","bbox":[50,30,900,120],"content":"Slide Title","style":{{"color":"#FFFFFF","bold":true,"font_size":36,"alignment":"center"}}}},
  {{"type":"text","bbox":[50,150,850,400],"content":"Bullet point 1\\nBullet point 2","style":{{"color":"#E0E0E0","bold":false,"font_size":18,"alignment":"left"}}}}
]
"""


def analyze_slide_image(image_path: str, text_provider,
                        thinking_budget: int = 0) -> List[SlideElement]:
    """
    Analyze a slide image and extract editable elements.

    Args:
        image_path: Path to the slide image file.
        text_provider: A TextProvider instance with vision support.
        thinking_budget: Thinking budget for the AI model.

    Returns:
        List of SlideElement objects with bounding boxes and content.
    """
    img = Image.open(image_path)
    width, height = img.size
    img.close()

    prompt = _ANALYSIS_PROMPT.format(width=width, height=height)

    logger.info("Analyzing slide image: %s (%dx%d)", image_path, width, height)
    raw_response = text_provider.generate_text_with_image(
        prompt=prompt,
        image_path=image_path,
        thinking_budget=thinking_budget,
    )

    return _parse_elements(raw_response, width, height)


def _parse_elements(raw_text: str, img_width: int,
                    img_height: int) -> List[SlideElement]:
    """Parse JSON response into SlideElement list, with validation."""
    # Strip markdown code fences if present
    cleaned = raw_text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse vision response as JSON: %s\nRaw: %s",
                     e, cleaned[:500])
        return []

    if not isinstance(data, list):
        logger.error("Expected JSON array, got %s", type(data).__name__)
        return []

    elements: List[SlideElement] = []
    for item in data:
        try:
            elem = _parse_single_element(item, img_width, img_height)
            if elem:
                elements.append(elem)
        except Exception as e:
            logger.warning("Skipping malformed element: %s — %s", item, e)

    logger.info("Extracted %d elements from slide image", len(elements))
    return elements


def _parse_single_element(item: dict, img_width: int,
                          img_height: int) -> Optional[SlideElement]:
    """Parse a single element dict into a SlideElement."""
    elem_type = item.get("type", "text")
    if elem_type not in ("text", "image"):
        return None

    raw_bbox = item.get("bbox")
    if not raw_bbox or len(raw_bbox) != 4:
        return None

    x0, y0, x1, y1 = [float(v) for v in raw_bbox]

    # Clamp to image bounds
    x0 = max(0, min(x0, img_width))
    y0 = max(0, min(y0, img_height))
    x1 = max(0, min(x1, img_width))
    y1 = max(0, min(y1, img_height))

    # Ensure positive dimensions
    if x1 <= x0 or y1 <= y0:
        return None

    bbox = BBox(x0=x0, y0=y0, x1=x1, y1=y1)
    content = item.get("content", "")
    style = item.get("style", {})

    # Normalize style values
    if "bold" in style:
        style["bold"] = bool(style["bold"])
    if "font_size" in style:
        try:
            style["font_size"] = int(style["font_size"])
        except (ValueError, TypeError):
            del style["font_size"]

    return SlideElement(
        element_type=elem_type,
        bbox=bbox,
        content=content,
        style=style,
    )


def get_dominant_color_around_bbox(image_path: str,
                                   bbox: BBox,
                                   sample_margin: int = 5) -> Tuple[int, int, int]:
    """
    Sample pixels around a bbox to determine the background color for overlay.

    Returns (R, G, B) tuple of the dominant color near the bbox edges.
    """
    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    # Sample pixels from edges around the bbox
    pixels = []
    x0, y0, x1, y1 = int(bbox.x0), int(bbox.y0), int(bbox.x1), int(bbox.y1)

    # Sample from left/right/top/bottom edges just outside the bbox
    for offset in range(1, sample_margin + 1):
        # Left edge
        sx = max(0, x0 - offset)
        for sy in range(max(0, y0), min(h, y1), max(1, (y1 - y0) // 10)):
            pixels.append(img.getpixel((sx, sy)))
        # Right edge
        sx = min(w - 1, x1 + offset)
        for sy in range(max(0, y0), min(h, y1), max(1, (y1 - y0) // 10)):
            pixels.append(img.getpixel((sx, sy)))
        # Top edge
        sy = max(0, y0 - offset)
        for sx_i in range(max(0, x0), min(w, x1), max(1, (x1 - x0) // 10)):
            pixels.append(img.getpixel((sx_i, sy)))
        # Bottom edge
        sy = min(h - 1, y1 + offset)
        for sx_i in range(max(0, x0), min(w, x1), max(1, (x1 - x0) // 10)):
            pixels.append(img.getpixel((sx_i, sy)))

    img.close()

    if not pixels:
        return (0, 0, 0)

    # Average color
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)
    return (r, g, b)
