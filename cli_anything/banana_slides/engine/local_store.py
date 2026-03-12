"""
Local JSON file store for Banana Slides projects.

Storage layout: ~/.banana_slides/projects/{project_id}/
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image

logger = logging.getLogger(__name__)

_STORE_ROOT = Path.home() / ".banana_slides" / "projects"


class LocalStore:
    """File-system backed project store."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or _STORE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    def create_project(self, topic: str, name: str = "",
                       style: str = "", aspect_ratio: str = "16:9",
                       creation_type: str = "idea",
                       idea_prompt: str = "",
                       num_pages: int = 0) -> dict:
        project_id = uuid.uuid4().hex[:16]
        project_dir = self.root / project_id
        project_dir.mkdir(parents=True)
        (project_dir / "pages").mkdir()
        (project_dir / "images").mkdir()
        (project_dir / "exports").mkdir()

        now = datetime.now(timezone.utc).isoformat()
        project = {
            "id": project_id,
            "name": name or topic[:80],
            "topic": topic,
            "style": style,
            "aspect_ratio": aspect_ratio,
            "creation_type": creation_type,
            "idea_prompt": idea_prompt or topic,
            "outline_text": None,
            "description_text": None,
            "outline_requirements": None,
            "description_requirements": None,
            "num_pages": num_pages,
            "status": "CREATED",
            "created_at": now,
            "updated_at": now,
        }
        self._write_json(project_dir / "project.json", project)
        return project

    def get_project(self, project_id: str) -> dict:
        path = self.root / project_id / "project.json"
        if not path.exists():
            raise FileNotFoundError(f"Project not found: {project_id}")
        return self._read_json(path)

    def update_project(self, project_id: str, updates: dict) -> dict:
        project = self.get_project(project_id)
        project.update(updates)
        project["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_json(self.root / project_id / "project.json", project)
        return project

    def list_projects(self) -> List[dict]:
        projects = []
        if not self.root.exists():
            return projects
        for d in sorted(self.root.iterdir()):
            pf = d / "project.json"
            if pf.exists():
                projects.append(self._read_json(pf))
        return projects

    def delete_project(self, project_id: str):
        import shutil
        project_dir = self.root / project_id
        if project_dir.exists():
            shutil.rmtree(project_dir)

    # ------------------------------------------------------------------
    # Outline
    # ------------------------------------------------------------------

    def save_outline(self, project_id: str, outline: List[dict],
                     flat_pages: List[dict]):
        project_dir = self.root / project_id
        self._write_json(project_dir / "outline.json", outline)

        pages_dir = project_dir / "pages"
        pages_dir.mkdir(exist_ok=True)
        for i, page in enumerate(flat_pages):
            page_data = {
                "order_index": i,
                "outline_content": page,
                "part": page.get("part", ""),
                "description_content": None,
                "extra_fields": None,
                "status": "OUTLINE_GENERATED",
                "image_path": None,
            }
            self._write_json(pages_dir / f"page_{i}.json", page_data)

        self.update_project(project_id, {"status": "OUTLINE_GENERATED"})

    def get_outline(self, project_id: str) -> List[dict]:
        path = self.root / project_id / "outline.json"
        if not path.exists():
            return []
        return self._read_json(path)

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def get_pages(self, project_id: str) -> List[dict]:
        pages_dir = self.root / project_id / "pages"
        if not pages_dir.exists():
            return []
        pages = []
        for pf in sorted(pages_dir.glob("page_*.json")):
            pages.append(self._read_json(pf))
        return pages

    def update_page(self, project_id: str, page_index: int, updates: dict):
        path = self.root / project_id / "pages" / f"page_{page_index}.json"
        if not path.exists():
            raise FileNotFoundError(f"Page {page_index} not found in project {project_id}")
        page = self._read_json(path)
        page.update(updates)
        self._write_json(path, page)
        return page

    def save_page_image(self, project_id: str, page_index: int,
                        image: Image.Image) -> str:
        images_dir = self.root / project_id / "images"
        images_dir.mkdir(exist_ok=True)
        image_path = images_dir / f"page_{page_index}.png"
        image.save(str(image_path), format="PNG")
        # Update page record
        self.update_page(project_id, page_index, {
            "image_path": str(image_path),
            "status": "IMAGE_GENERATED",
        })
        return str(image_path)

    def get_exports_dir(self, project_id: str) -> Path:
        d = self.root / project_id / "exports"
        d.mkdir(exist_ok=True)
        return d

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_json(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, data):
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
