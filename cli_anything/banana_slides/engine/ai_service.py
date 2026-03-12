"""
AI Service - handles all AI model interactions (standalone, no Flask)
"""
import os
import json
import re
import logging
from typing import List, Dict, Optional, Union
from textwrap import dedent
from PIL import Image
from tenacity import retry, stop_after_attempt, retry_if_exception_type
from .prompts import (
    get_outline_generation_prompt,
    get_outline_parsing_prompt,
    get_page_description_prompt,
    get_all_descriptions_stream_prompt,
    get_image_generation_prompt,
    get_description_to_outline_prompt,
    get_description_split_prompt,
    get_outline_generation_prompt_markdown,
    get_outline_parsing_prompt_markdown,
    get_description_to_outline_prompt_markdown,
)
from .ai_providers import get_text_provider, get_image_provider, TextProvider, ImageProvider

logger = logging.getLogger(__name__)


class ProjectContext:
    """Project context data class for AI prompts"""

    def __init__(self, project_or_dict, reference_files_content: Optional[List[Dict[str, str]]] = None):
        if hasattr(project_or_dict, 'idea_prompt'):
            self.idea_prompt = project_or_dict.idea_prompt
            self.outline_text = project_or_dict.outline_text
            self.description_text = project_or_dict.description_text
            self.creation_type = project_or_dict.creation_type or 'idea'
            self.outline_requirements = project_or_dict.outline_requirements
            self.description_requirements = project_or_dict.description_requirements
        else:
            self.idea_prompt = project_or_dict.get('idea_prompt')
            self.outline_text = project_or_dict.get('outline_text')
            self.description_text = project_or_dict.get('description_text')
            self.creation_type = project_or_dict.get('creation_type', 'idea')
            self.outline_requirements = project_or_dict.get('outline_requirements')
            self.description_requirements = project_or_dict.get('description_requirements')

        self.reference_files_content = reference_files_content or []

    def to_dict(self) -> Dict:
        return {
            'idea_prompt': self.idea_prompt,
            'outline_text': self.outline_text,
            'description_text': self.description_text,
            'creation_type': self.creation_type,
            'outline_requirements': self.outline_requirements,
            'description_requirements': self.description_requirements,
            'reference_files_content': self.reference_files_content,
        }


class AIService:
    """Service for AI model interactions using pluggable providers (no Flask)"""

    def __init__(self, config: Optional[Dict] = None,
                 text_provider: TextProvider = None,
                 image_provider: ImageProvider = None):
        """
        Initialize AI service.

        Args:
            config: Configuration dict with keys like TEXT_MODEL, IMAGE_MODEL, etc.
            text_provider: Optional pre-configured TextProvider.
            image_provider: Optional pre-configured ImageProvider.
        """
        config = config or {}

        self.text_model = config.get('TEXT_MODEL',
                                     os.getenv('TEXT_MODEL', 'gemini-3-flash-preview'))
        self.image_model = config.get('IMAGE_MODEL',
                                      os.getenv('IMAGE_MODEL', 'gemini-3-pro-image-preview'))
        self.enable_text_reasoning = config.get('ENABLE_TEXT_REASONING', False)
        self.text_thinking_budget = config.get('TEXT_THINKING_BUDGET', 1024)
        self.enable_image_reasoning = config.get('ENABLE_IMAGE_REASONING', False)
        self.image_thinking_budget = config.get('IMAGE_THINKING_BUDGET', 1024)

        self.text_provider = text_provider or get_text_provider(
            model=self.text_model, config=config)
        self.image_provider = image_provider or get_image_provider(
            model=self.image_model, config=config)

    def _get_text_thinking_budget(self) -> int:
        return self.text_thinking_budget if self.enable_text_reasoning else 0

    def _get_image_thinking_budget(self) -> int:
        return self.image_thinking_budget if self.enable_image_reasoning else 0

    @staticmethod
    def remove_markdown_images(text: str) -> str:
        if not text:
            return text
        def replace_image(match):
            alt_text = match.group(1).strip()
            return alt_text if alt_text else ''
        cleaned = re.sub(r'!\[(.*?)\]\([^\)]+\)', replace_image, text)
        return re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)

    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((json.JSONDecodeError, ValueError)),
        reraise=True,
    )
    def generate_json(self, prompt: str, thinking_budget: int = 1000) -> Union[Dict, List]:
        actual_budget = self._get_text_thinking_budget()
        response_text = self.text_provider.generate_text(prompt, thinking_budget=actual_budget)
        cleaned_text = response_text.strip().strip("```json").strip("```").strip()
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.warning("JSON parse failed, retrying. Text: %s... Error: %s",
                           cleaned_text[:200], e)
            raise

    def generate_outline_stream(self, project_context: ProjectContext, language: str = None):
        """Stream outline generation, yielding each page as it's detected."""
        creation_type = project_context.creation_type or 'idea'

        if creation_type == 'outline':
            prompt = get_outline_parsing_prompt_markdown(project_context, language)
        elif creation_type == 'descriptions':
            prompt = get_description_to_outline_prompt_markdown(project_context, language)
        else:
            prompt = get_outline_generation_prompt_markdown(project_context, language)

        actual_budget = self._get_text_thinking_budget()
        buffer = ""
        current_part = None
        current_page = None
        stream_complete = False

        for chunk in self.text_provider.generate_text_stream(prompt, thinking_budget=actual_budget):
            buffer += chunk
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped == '<!-- END -->':
                    stream_complete = True
                    continue
                if stripped.startswith('# ') and not stripped.startswith('## '):
                    current_part = stripped[2:].strip()
                elif stripped.startswith('## '):
                    if current_page:
                        yield current_page
                    current_page = {'title': stripped[3:].strip(), 'points': []}
                    if current_part:
                        current_page['part'] = current_part
                elif stripped.startswith('- ') and current_page is not None:
                    current_page['points'].append(stripped[2:].strip())

        # Process remaining buffer
        if buffer.strip():
            for line in (buffer + '\n').split('\n'):
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped == '<!-- END -->':
                    stream_complete = True
                    continue
                if stripped.startswith('# ') and not stripped.startswith('## '):
                    current_part = stripped[2:].strip()
                elif stripped.startswith('## '):
                    if current_page:
                        yield current_page
                    current_page = {'title': stripped[3:].strip(), 'points': []}
                    if current_part:
                        current_page['part'] = current_part
                elif stripped.startswith('- ') and current_page is not None:
                    current_page['points'].append(stripped[2:].strip())

        if current_page:
            yield current_page
        yield {'__stream_complete__': stream_complete}

    @staticmethod
    def flatten_outline(outline: List[Dict]) -> List[Dict]:
        pages = []
        for item in outline:
            if "part" in item and "pages" in item:
                for page in item["pages"]:
                    page_copy = dict(page)
                    page_copy["part"] = item["part"]
                    pages.append(page_copy)
            else:
                pages.append(item)
        return pages

    @staticmethod
    def _get_extra_field_names() -> list:
        return ['视觉元素', '视觉焦点', '排版布局', '演讲者备注']

    @staticmethod
    def _parse_extra_fields(text: str, field_names: list) -> tuple:
        if not field_names:
            return text, {}
        extra_fields = {}
        positions = []
        for name in field_names:
            match = re.search(rf'\n{re.escape(name)}[：:]\s*', text)
            if match:
                positions.append((match.start(), match.end(), name))
        if not positions:
            return text, {}
        positions.sort(key=lambda x: x[0])
        for i, (start, end, name) in enumerate(positions):
            if i + 1 < len(positions):
                value = text[end:positions[i + 1][0]].strip()
            else:
                value = text[end:].strip()
            value = re.sub(r'<!--.*?-->', '', value).strip()
            if value:
                extra_fields[name] = value
        cleaned_text = text[:positions[0][0]].strip()
        return cleaned_text, extra_fields

    @staticmethod
    def _build_extra_field_pattern(field_names: list):
        if not field_names:
            return None
        escaped = '|'.join(re.escape(name) for name in field_names)
        return re.compile(rf'^({escaped})[：:]\s*(.*)')

    def generate_descriptions_stream(self, project_context: ProjectContext,
                                     outline: List[Dict], flat_pages: List[Dict],
                                     language: str = 'zh',
                                     detail_level: str = 'default'):
        """Stream description generation for all pages."""
        extra_field_names = self._get_extra_field_names()

        prompt = get_all_descriptions_stream_prompt(
            project_context=project_context,
            outline=outline,
            flat_pages=flat_pages,
            language=language,
            detail_level=detail_level,
            extra_fields=extra_field_names,
        )

        field_pattern = self._build_extra_field_pattern(extra_field_names)
        actual_budget = self._get_text_thinking_budget()
        buffer = ""
        page_index = -1
        current_lines: list = []
        current_field: Optional[str] = None
        extra_fields: Dict[str, str] = {}
        stream_complete = False

        def _build_page_result():
            desc_text = "\n".join(current_lines).strip()
            result: Dict = {'page_index': page_index, 'description_text': desc_text}
            if extra_fields:
                result['extra_fields'] = dict(extra_fields)
            return result

        def _reset_page_state():
            nonlocal current_lines, current_field, extra_fields
            current_lines = []
            current_field = None
            extra_fields = {}

        def _process_line(line: str, stripped: str):
            nonlocal page_index, current_field, stream_complete
            if stripped == '<!-- BEGIN -->':
                if page_index < 0:
                    page_index = 0
                return 'continue'
            if stripped == '<!-- END -->':
                stream_complete = True
                return 'continue'
            if stripped == '<!-- PAGE_END -->':
                if page_index >= 0 and (current_lines or extra_fields):
                    return 'yield_page'
                return 'continue'
            if page_index < 0:
                return 'continue'
            if field_pattern:
                field_match = field_pattern.match(stripped)
                if field_match:
                    field_name = field_match.group(1)
                    current_field = field_name
                    value = field_match.group(2).strip()
                    if value:
                        extra_fields[field_name] = value
                    return 'continue'
            if not stripped:
                return 'continue'
            if current_field:
                if current_field in extra_fields:
                    extra_fields[current_field] += "\n" + stripped
                else:
                    extra_fields[current_field] = stripped
            else:
                current_lines.append(line.rstrip())
            return 'continue'

        for chunk in self.text_provider.generate_text_stream(prompt, thinking_budget=actual_budget):
            buffer += chunk
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                stripped = line.strip()
                action = _process_line(line, stripped)
                if action == 'yield_page':
                    yield _build_page_result()
                    _reset_page_state()
                    page_index += 1

        if buffer.strip():
            for line in buffer.split('\n'):
                stripped = line.strip()
                action = _process_line(line, stripped)
                if action == 'yield_page':
                    yield _build_page_result()
                    _reset_page_state()
                    page_index += 1

        if page_index >= 0 and current_lines:
            yield _build_page_result()

        yield {'__stream_complete__': stream_complete}

    def generate_outline_text(self, outline: List[Dict]) -> str:
        text_parts = []
        for i, item in enumerate(outline, 1):
            if "part" in item and "pages" in item:
                text_parts.append(f"{i}. {item['part']}")
            else:
                text_parts.append(f"{i}. {item.get('title', 'Untitled')}")
        return dedent("\n".join(text_parts))

    def generate_image_prompt(self, outline: List[Dict], page: Dict,
                              page_desc: str, page_index: int,
                              language='zh', aspect_ratio: str = "16:9") -> str:
        outline_text = self.generate_outline_text(outline)
        current_section = page.get('part', page.get('title', 'Untitled'))
        cleaned_page_desc = self.remove_markdown_images(page_desc)

        return get_image_generation_prompt(
            page_desc=cleaned_page_desc,
            outline_text=outline_text,
            current_section=current_section,
            has_material_images=False,
            language=language,
            has_template=False,
            page_index=page_index,
            aspect_ratio=aspect_ratio,
        )

    def generate_image(self, prompt: str, aspect_ratio: str = "16:9",
                       resolution: str = "2K") -> Optional[Image.Image]:
        try:
            return self.image_provider.generate_image(
                prompt=prompt,
                ref_images=None,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                enable_thinking=self.enable_image_reasoning,
                thinking_budget=self._get_image_thinking_budget(),
            )
        except Exception as e:
            error_detail = f"Error generating image: {type(e).__name__}: {e}"
            logger.error(error_detail, exc_info=True)
            raise Exception(error_detail) from e
