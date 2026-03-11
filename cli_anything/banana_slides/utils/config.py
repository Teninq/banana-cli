"""Persistent CLI configuration stored in ~/.banana_slides_cli.json."""

import json
import os
from pathlib import Path

_CONFIG_PATH = Path.home() / ".banana_slides_cli.json"

_DEFAULTS = {
    "base_url": "http://localhost:5000",
    "access_code": "",
}


def load_config() -> dict:
    """Load config from disk, merging with defaults."""
    cfg = dict(_DEFAULTS)
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            cfg.update(data)
        except (json.JSONDecodeError, OSError):
            pass
    # Environment variables override file
    if os.getenv("BANANA_SLIDES_BASE_URL"):
        cfg["base_url"] = os.environ["BANANA_SLIDES_BASE_URL"]
    if os.getenv("BANANA_SLIDES_ACCESS_CODE"):
        cfg["access_code"] = os.environ["BANANA_SLIDES_ACCESS_CODE"]
    return cfg


def save_config(cfg: dict) -> None:
    """Persist config to disk."""
    _CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_base_url() -> str:
    return load_config()["base_url"].rstrip("/")


def get_access_code() -> str:
    return load_config().get("access_code", "")
