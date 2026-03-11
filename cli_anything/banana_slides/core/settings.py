"""Settings API operations."""

from typing import Any, Dict, Optional
from .client import BananaSlidesClient


def get_settings(client: BananaSlidesClient) -> Dict:
    body = client.get("/api/settings")
    return body.get("data", body)


def update_settings(client: BananaSlidesClient, updates: Dict) -> Dict:
    body = client.put("/api/settings", json=updates)
    return body.get("data", body)
