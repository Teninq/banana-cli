"""
RemoteBackend -- wraps existing HTTP client to implement SlidesBackend.
"""
import logging
from typing import Callable, List, Optional

from cli_anything.banana_slides.core.client import BananaSlidesClient, APIError
from cli_anything.banana_slides.core import project as proj_api
from cli_anything.banana_slides.core import page as page_api
from cli_anything.banana_slides.core import task as task_api
from cli_anything.banana_slides.core import export as export_api

logger = logging.getLogger(__name__)


class RemoteBackend:
    """SlidesBackend implementation via HTTP to Flask backend."""

    def __init__(self, base_url: str = "http://localhost:5000",
                 access_code: str = "", timeout: int = 600):
        self.client = BananaSlidesClient(base_url, access_code, timeout=timeout)
        self.base_url = base_url

    def create_project(self, topic: str, name: str = "",
                       style: str = "", aspect_ratio: str = "16:9",
                       creation_type: str = "idea",
                       num_pages: int = 0,
                       idea_prompt: str = "") -> dict:
        if idea_prompt and idea_prompt != topic:
            # Use raw POST to pass idea_prompt
            payload = {
                "name": name or topic[:80],
                "topic": topic,
                "creation_type": "idea",
                "idea_prompt": idea_prompt,
                "image_aspect_ratio": aspect_ratio,
            }
            if style:
                payload["style"] = style
            if num_pages:
                payload["num_pages"] = num_pages
            body = self.client.post("/api/projects", json=payload)
            return body.get("data", body)
        return proj_api.create_project(
            self.client, topic=topic, name=name,
            creation_type=creation_type, aspect_ratio=aspect_ratio, style=style,
        )

    def get_project(self, project_id: str) -> dict:
        return proj_api.get_project(self.client, project_id)

    def list_projects(self) -> List[dict]:
        return proj_api.list_projects(self.client)

    def delete_project(self, project_id: str) -> dict:
        return proj_api.delete_project(self.client, project_id)

    def generate_outline(self, project_id: str, num_pages: int = 0,
                         language: str = "zh") -> List[dict]:
        proj_api.generate_outline(self.client, project_id, num_pages, language)
        # Wait for pages to appear
        import time
        for _ in range(10):
            pages = page_api.list_pages(self.client, project_id)
            if pages:
                return pages
            time.sleep(2)
        return []

    def generate_descriptions(self, project_id: str, language: str = "zh",
                              progress_callback: Optional[Callable] = None) -> dict:
        result = proj_api.generate_descriptions(self.client, project_id, language)
        task_id = result.get("task_id")
        if task_id:
            task_api.wait_for_task(
                self.client, project_id, task_id,
                interval=4, timeout=600,
                progress_callback=progress_callback,
            )
        return result

    def generate_images(self, project_id: str, language: str = "zh",
                        progress_callback: Optional[Callable] = None) -> dict:
        result = proj_api.generate_images(self.client, project_id, language)
        task_id = result.get("task_id")
        if task_id:
            task_api.wait_for_task(
                self.client, project_id, task_id,
                interval=4, timeout=3600,
                progress_callback=progress_callback,
            )
        return result

    def list_pages(self, project_id: str) -> List[dict]:
        return page_api.list_pages(self.client, project_id)

    def export_pptx(self, project_id: str, filename: str = "",
                    mode: str = "image") -> str:
        if mode == "text":
            # Use local text export via remote page data
            from .export import export_text_pptx
            import requests
            resp = requests.get(
                f"{self.base_url}/api/projects/{project_id}", timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            pages = data.get("pages", [])
            output = filename or f"{project_id[:8]}.pptx"
            if not output.endswith(".pptx"):
                output += ".pptx"
            return export_text_pptx(pages, output, title=data.get("name", "Presentation"))

        result = export_api.export_pptx(self.client, project_id, filename=filename)
        return result.get("download_url_absolute") or result.get("download_url", "")
