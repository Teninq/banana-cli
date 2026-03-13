"""
LocalBackend -- runs the full AI pipeline locally, no remote server needed.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional

from .ai_service import AIService, ProjectContext
from .local_store import LocalStore
from .export import export_text_pptx, export_image_pptx, export_editable_pptx

logger = logging.getLogger(__name__)


class LocalBackend:
    """SlidesBackend implementation using local AI providers + file store."""

    def __init__(self, config: Optional[Dict] = None, max_workers: int = 4):
        self.config = config or {}
        self.store = LocalStore()
        self.ai = AIService(config=self.config)
        self.max_workers = max_workers

    def create_project(self, topic: str, name: str = "",
                       style: str = "", aspect_ratio: str = "16:9",
                       creation_type: str = "idea",
                       num_pages: int = 0,
                       idea_prompt: str = "") -> dict:
        return self.store.create_project(
            topic=topic, name=name, style=style,
            aspect_ratio=aspect_ratio, creation_type=creation_type,
            idea_prompt=idea_prompt or topic,
            num_pages=num_pages,
        )

    def get_project(self, project_id: str) -> dict:
        return self.store.get_project(project_id)

    def list_projects(self) -> List[dict]:
        return self.store.list_projects()

    def delete_project(self, project_id: str) -> dict:
        self.store.delete_project(project_id)
        return {"status": "deleted", "id": project_id}

    def generate_outline(self, project_id: str, num_pages: int = 0,
                         language: str = "zh") -> List[dict]:
        project = self.store.get_project(project_id)
        ctx = ProjectContext(project)

        # Collect pages from streaming outline
        pages = []
        for item in self.ai.generate_outline_stream(ctx, language):
            if '__stream_complete__' in item:
                continue
            pages.append(item)

        # Build structured outline from flat pages
        outline = list(pages)  # simple flat list
        flat_pages = pages

        self.store.save_outline(project_id, outline, flat_pages)
        self.store.update_project(project_id, {"status": "OUTLINE_GENERATED"})

        # Return pages in the same format as remote API
        return self.store.get_pages(project_id)

    def generate_descriptions(self, project_id: str, language: str = "zh",
                              progress_callback: Optional[Callable] = None) -> dict:
        project = self.store.get_project(project_id)
        outline = self.store.get_outline(project_id)
        flat_pages = self.ai.flatten_outline(outline) if outline else []
        if not flat_pages:
            flat_pages = [p.get("outline_content", {}) for p in self.store.get_pages(project_id)]

        ctx = ProjectContext(project)

        total = len(flat_pages)
        completed = 0

        for item in self.ai.generate_descriptions_stream(ctx, outline, flat_pages, language):
            if '__stream_complete__' in item:
                continue
            page_index = item.get('page_index', 0)
            desc_text = item.get('description_text', '')
            extra = item.get('extra_fields')

            updates = {
                "description_content": desc_text,
                "status": "DESCRIPTION_GENERATED",
            }
            if extra:
                updates["extra_fields"] = extra

            try:
                self.store.update_page(project_id, page_index, updates)
            except FileNotFoundError:
                logger.warning("Page %d not found, skipping description update", page_index)

            completed += 1
            if progress_callback:
                progress_callback({
                    "status": "running",
                    "progress": {"total": total, "completed": completed, "failed": 0},
                })

        self.store.update_project(project_id, {"status": "DESCRIPTIONS_GENERATED"})
        return {"status": "completed", "total": total, "completed": completed}

    def generate_images(self, project_id: str, language: str = "zh",
                        progress_callback: Optional[Callable] = None) -> dict:
        project = self.store.get_project(project_id)
        aspect_ratio = project.get("aspect_ratio", "16:9")
        outline = self.store.get_outline(project_id)
        pages = self.store.get_pages(project_id)

        total = len(pages)
        completed = 0
        failed = 0

        def _generate_one(page_data: dict) -> dict:
            idx = page_data["order_index"]
            oc = page_data.get("outline_content") or {}
            desc = page_data.get("description_content") or ""

            prompt = self.ai.generate_image_prompt(
                outline=outline,
                page=oc,
                page_desc=desc,
                page_index=idx + 1,
                language=language,
                aspect_ratio=aspect_ratio,
            )
            image = self.ai.generate_image(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                resolution="2K",
            )
            if image:
                self.store.save_page_image(project_id, idx, image)
            return {"index": idx, "success": image is not None}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(_generate_one, p): p for p in pages}

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result["success"]:
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error("Image generation failed: %s", e, exc_info=True)
                    failed += 1

                if progress_callback:
                    progress_callback({
                        "status": "running",
                        "progress": {
                            "total": total,
                            "completed": completed,
                            "failed": failed,
                        },
                    })

        self.store.update_project(project_id, {"status": "IMAGES_GENERATED"})
        return {"status": "completed", "total": total, "completed": completed, "failed": failed}

    def list_pages(self, project_id: str) -> List[dict]:
        return self.store.get_pages(project_id)

    def export_pptx(self, project_id: str, filename: str = "",
                    mode: str = "image",
                    progress_callback: Optional[Callable] = None) -> str:
        project = self.store.get_project(project_id)
        exports_dir = self.store.get_exports_dir(project_id)

        out_name = filename or project.get("name", project_id[:8])
        if not out_name.endswith(".pptx"):
            out_name += ".pptx"
        output_path = str(exports_dir / out_name)

        pages = self.store.get_pages(project_id)

        if mode == "text":
            title = project.get("name") or project.get("topic", "Presentation")
            return export_text_pptx(pages, output_path, title=title)

        # Collect image paths (shared by image and editable modes)
        image_paths = []
        for p in sorted(pages, key=lambda x: x.get("order_index", 0)):
            ip = p.get("image_path")
            if ip:
                image_paths.append(ip)

        if not image_paths:
            logger.warning("No images found, falling back to text mode")
            title = project.get("name") or project.get("topic", "Presentation")
            return export_text_pptx(pages, output_path, title=title)

        aspect_ratio = project.get("aspect_ratio", "16:9")

        if mode == "editable":
            return self._export_editable(
                image_paths, output_path, aspect_ratio,
                progress_callback=progress_callback,
            )

        # Default: image mode
        return export_image_pptx(image_paths, output_path, aspect_ratio=aspect_ratio)

    def _export_editable(self, image_paths: List[str], output_path: str,
                         aspect_ratio: str,
                         progress_callback: Optional[Callable] = None) -> str:
        """Analyze slide images and export editable PPTX."""
        from .image_analyzer import analyze_slide_image

        text_provider = self.ai.text_provider
        total = len(image_paths)
        analysis_results = []

        for idx, img_path in enumerate(image_paths):
            logger.info("Analyzing slide %d/%d: %s", idx + 1, total, img_path)
            try:
                elements = analyze_slide_image(img_path, text_provider)
            except Exception as e:
                logger.error("Failed to analyze slide %d: %s", idx + 1, e)
                elements = []
            analysis_results.append(elements)

            if progress_callback:
                progress_callback({
                    "status": "analyzing",
                    "progress": {"total": total, "completed": idx + 1, "failed": 0},
                })

        return export_editable_pptx(
            image_paths, analysis_results, output_path,
            aspect_ratio=aspect_ratio,
        )
