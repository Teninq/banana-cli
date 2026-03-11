"""Project-level API operations."""

from typing import Dict, List, Optional
from .client import BananaSlidesClient


def list_projects(client: BananaSlidesClient) -> List[Dict]:
    body = client.get("/api/projects")
    return body.get("data", [])


def create_project(
    client: BananaSlidesClient,
    *,
    topic: str,
    name: Optional[str] = None,
    creation_type: str = "scratch",
    aspect_ratio: str = "16:9",
    style: Optional[str] = None,
    extra_requirements: Optional[str] = None,
    num_pages: int = 0,
) -> Dict:
    payload: Dict = {
        "topic": topic,
        "name": name or topic[:80],
        "creation_type": creation_type,
        "image_aspect_ratio": aspect_ratio,
    }
    if style:
        payload["template_style"] = style
    if extra_requirements:
        payload["extra_requirements"] = extra_requirements
    if num_pages:
        payload["num_pages"] = num_pages
    body = client.post("/api/projects", json=payload)
    return body.get("data", body)


def get_project(client: BananaSlidesClient, project_id: str) -> Dict:
    body = client.get(f"/api/projects/{project_id}")
    return body.get("data", body)


def delete_project(client: BananaSlidesClient, project_id: str) -> Dict:
    body = client.delete(f"/api/projects/{project_id}")
    return body


def generate_outline(
    client: BananaSlidesClient,
    project_id: str,
    num_pages: int = 0,
    language: str = "zh",
) -> str:
    """
    Stream the outline generation SSE and return the accumulated text.
    The server sends chunked data; we collect all content.
    """
    params: Dict = {"language": language}
    if num_pages:
        params["num_pages"] = num_pages

    # The endpoint accepts POST based on project_controller review
    resp = client.session.post(
        client._url(f"/api/projects/{project_id}/generate-outline"),
        json={"language": language, "num_pages": num_pages} if num_pages else {"language": language},
        stream=True,
        timeout=300,
    )
    resp.raise_for_status()

    chunks = []
    for line in resp.iter_lines(decode_unicode=True):
        if line:
            chunks.append(line)
    return "\n".join(chunks)


def generate_descriptions(
    client: BananaSlidesClient,
    project_id: str,
    language: str = "zh",
    page_ids: Optional[List[str]] = None,
) -> Dict:
    """Start bulk description generation. Returns task info."""
    payload: Dict = {"language": language}
    if page_ids:
        payload["page_ids"] = page_ids
    body = client.post(f"/api/projects/{project_id}/generate-descriptions", json=payload)
    return body.get("data", body)


def generate_images(
    client: BananaSlidesClient,
    project_id: str,
    language: str = "zh",
    page_ids: Optional[List[str]] = None,
) -> Dict:
    """Start bulk image generation. Returns task info."""
    payload: Dict = {"language": language}
    if page_ids:
        payload["page_ids"] = page_ids
    body = client.post(f"/api/projects/{project_id}/generate-images", json=payload)
    return body.get("data", body)
