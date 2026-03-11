"""Export API operations (PPTX, PDF, images, editable PPTX)."""

from typing import Dict, List, Optional
from .client import BananaSlidesClient


def export_pptx(
    client: BananaSlidesClient,
    project_id: str,
    filename: Optional[str] = None,
    page_ids: Optional[List[str]] = None,
) -> Dict:
    params: Dict = {}
    if filename:
        params["filename"] = filename
    if page_ids:
        params["page_ids"] = ",".join(page_ids)
    body = client.get(f"/api/projects/{project_id}/export/pptx", params=params)
    return body.get("data", body)


def export_pdf(
    client: BananaSlidesClient,
    project_id: str,
    filename: Optional[str] = None,
    page_ids: Optional[List[str]] = None,
) -> Dict:
    params: Dict = {}
    if filename:
        params["filename"] = filename
    if page_ids:
        params["page_ids"] = ",".join(page_ids)
    body = client.get(f"/api/projects/{project_id}/export/pdf", params=params)
    return body.get("data", body)


def export_images(
    client: BananaSlidesClient,
    project_id: str,
    page_ids: Optional[List[str]] = None,
) -> Dict:
    params: Dict = {}
    if page_ids:
        params["page_ids"] = ",".join(page_ids)
    body = client.get(f"/api/projects/{project_id}/export/images", params=params)
    return body.get("data", body)


def export_editable_pptx(
    client: BananaSlidesClient,
    project_id: str,
    filename: Optional[str] = None,
    page_ids: Optional[List[str]] = None,
    max_depth: int = 1,
    max_workers: int = 4,
) -> Dict:
    """Start async editable-PPTX export. Returns task info."""
    payload: Dict = {"max_depth": max_depth, "max_workers": max_workers}
    if filename:
        payload["filename"] = filename
    if page_ids:
        payload["page_ids"] = page_ids
    body = client.post(
        f"/api/projects/{project_id}/export/editable-pptx", json=payload
    )
    return body.get("data", body)
