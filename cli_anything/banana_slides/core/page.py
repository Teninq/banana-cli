"""Page-level API operations."""

from typing import Any, Dict, List, Optional
from .client import BananaSlidesClient


def list_pages(client: BananaSlidesClient, project_id: str) -> List[Dict]:
    body = client.get(f"/api/projects/{project_id}/pages")
    return body.get("data", [])


def create_page(
    client: BananaSlidesClient,
    project_id: str,
    order_index: int,
    part: Optional[str] = None,
    outline_content: Optional[Dict] = None,
) -> Dict:
    payload: Dict = {"order_index": order_index}
    if part:
        payload["part"] = part
    if outline_content:
        payload["outline_content"] = outline_content
    body = client.post(f"/api/projects/{project_id}/pages", json=payload)
    return body.get("data", body)


def delete_page(client: BananaSlidesClient, project_id: str, page_id: str) -> Dict:
    body = client.delete(f"/api/projects/{project_id}/pages/{page_id}")
    return body


def update_page_outline(
    client: BananaSlidesClient,
    project_id: str,
    page_id: str,
    outline_content: Dict,
) -> Dict:
    body = client.put(
        f"/api/projects/{project_id}/pages/{page_id}/outline",
        json={"outline_content": outline_content},
    )
    return body.get("data", body)


def update_page_description(
    client: BananaSlidesClient,
    project_id: str,
    page_id: str,
    description_content: Dict,
) -> Dict:
    body = client.put(
        f"/api/projects/{project_id}/pages/{page_id}/description",
        json={"description_content": description_content},
    )
    return body.get("data", body)


def generate_page_description(
    client: BananaSlidesClient,
    project_id: str,
    page_id: str,
    force: bool = False,
    language: str = "zh",
) -> Dict:
    body = client.post(
        f"/api/projects/{project_id}/pages/{page_id}/generate/description",
        json={"force_regenerate": force, "language": language},
    )
    return body.get("data", body)


def generate_page_image(
    client: BananaSlidesClient,
    project_id: str,
    page_id: str,
    force: bool = False,
    use_template: bool = True,
) -> Dict:
    """Returns task info (async)."""
    body = client.post(
        f"/api/projects/{project_id}/pages/{page_id}/generate/image",
        json={"force_regenerate": force, "use_template": use_template},
    )
    return body.get("data", body)


def edit_page_image(
    client: BananaSlidesClient,
    project_id: str,
    page_id: str,
    instruction: str,
    use_template: bool = False,
) -> Dict:
    """Returns task info (async)."""
    body = client.post(
        f"/api/projects/{project_id}/pages/{page_id}/edit/image",
        json={
            "edit_instruction": instruction,
            "context_images": {"use_template": use_template, "desc_image_urls": []},
        },
    )
    return body.get("data", body)


def get_image_versions(
    client: BananaSlidesClient, project_id: str, page_id: str
) -> List[Dict]:
    body = client.get(f"/api/projects/{project_id}/pages/{page_id}/image-versions")
    return (body.get("data") or {}).get("versions", [])
