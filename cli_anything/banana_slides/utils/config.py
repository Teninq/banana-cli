"""Persistent CLI configuration stored in ~/.banana_slides_cli.json."""

import json
import os
from pathlib import Path

_CONFIG_PATH = Path.home() / ".banana_slides_cli.json"

_DEFAULTS = {
    "mode": "remote",
    "base_url": "http://localhost:5000",
    "access_code": "",
    "local": {
        "ai_provider_format": "openai",
        "api_key": "",
        "api_base": "https://aihubmix.com/v1",
        "text_model": "gemini-3-flash-preview",
        "image_model": "gemini-3-pro-image-preview",
        "max_workers": 4,
    },
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
    # Ensure nested 'local' dict always exists
    if "local" not in cfg or not isinstance(cfg.get("local"), dict):
        cfg["local"] = dict(_DEFAULTS["local"])
    else:
        merged_local = dict(_DEFAULTS["local"])
        merged_local.update(cfg["local"])
        cfg["local"] = merged_local
    # Environment variables override file
    if os.getenv("BANANA_SLIDES_BASE_URL"):
        cfg["base_url"] = os.environ["BANANA_SLIDES_BASE_URL"]
    if os.getenv("BANANA_SLIDES_ACCESS_CODE"):
        cfg["access_code"] = os.environ["BANANA_SLIDES_ACCESS_CODE"]
    if os.getenv("BANANA_SLIDES_MODE"):
        cfg["mode"] = os.environ["BANANA_SLIDES_MODE"]
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


def get_mode() -> str:
    """Return 'local' or 'remote'."""
    return load_config().get("mode", "remote")


def get_local_config() -> dict:
    """Return the 'local' section as a provider-compatible config dict."""
    cfg = load_config()
    local = cfg.get("local", {})
    # Translate to the keys expected by ai_providers factory
    result = {
        "AI_PROVIDER_FORMAT": local.get("ai_provider_format", "openai"),
        "TEXT_MODEL": local.get("text_model", "gemini-3-flash-preview"),
        "IMAGE_MODEL": local.get("image_model", "gemini-3-pro-image-preview"),
    }
    fmt = result["AI_PROVIDER_FORMAT"]
    api_key = local.get("api_key", "")
    api_base = local.get("api_base", "")

    if fmt == "openai":
        if api_key:
            result["OPENAI_API_KEY"] = api_key
        if api_base:
            result["OPENAI_API_BASE"] = api_base
    else:
        if api_key:
            result["GOOGLE_API_KEY"] = api_key
        if api_base:
            result["GOOGLE_API_BASE"] = api_base

    result["max_workers"] = local.get("max_workers", 4)
    return result
