"""
SlidesBackend Protocol -- abstract interface for local/remote backends.
"""
from typing import Callable, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class SlidesBackend(Protocol):
    """Unified interface for Banana Slides operations."""

    def create_project(self, topic: str, name: str = "",
                       style: str = "", aspect_ratio: str = "16:9",
                       creation_type: str = "idea",
                       num_pages: int = 0,
                       idea_prompt: str = "") -> dict:
        ...

    def get_project(self, project_id: str) -> dict:
        ...

    def list_projects(self) -> List[dict]:
        ...

    def delete_project(self, project_id: str) -> dict:
        ...

    def generate_outline(self, project_id: str, num_pages: int = 0,
                         language: str = "zh") -> List[dict]:
        ...

    def generate_descriptions(self, project_id: str, language: str = "zh",
                              progress_callback: Optional[Callable] = None) -> dict:
        ...

    def generate_images(self, project_id: str, language: str = "zh",
                        progress_callback: Optional[Callable] = None) -> dict:
        ...

    def list_pages(self, project_id: str) -> List[dict]:
        ...

    def export_pptx(self, project_id: str, filename: str = "",
                    mode: str = "image") -> str:
        """Export to PPTX. mode: 'text' | 'image'. Returns output file path."""
        ...
