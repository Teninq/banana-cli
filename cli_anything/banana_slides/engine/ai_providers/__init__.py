"""
AI Providers factory module (standalone, no Flask dependency)

Configuration priority (highest -> lowest):
    1. Explicit config dict passed to factory functions
    2. Environment variables (.env file)
    3. Hard-coded defaults

Supported provider formats:
    gemini  -- Google AI Studio (API key auth)
    openai  -- OpenAI-compatible endpoints
"""
import os
import logging
from typing import Any, Dict, Optional

from .text import TextProvider, GenAITextProvider, OpenAITextProvider
from .image import ImageProvider, GenAIImageProvider, OpenAIImageProvider

logger = logging.getLogger(__name__)

__all__ = [
    'TextProvider', 'GenAITextProvider', 'OpenAITextProvider',
    'ImageProvider', 'GenAIImageProvider', 'OpenAIImageProvider',
    'get_text_provider', 'get_image_provider',
]


def _resolve_setting(key: str, config: Optional[Dict[str, Any]] = None,
                     fallback: Optional[str] = None) -> Optional[str]:
    """Look up a configuration value: config dict -> env var -> fallback."""
    if config and key in config:
        val = config[key]
        if val is not None:
            return str(val)
    env_val = os.getenv(key)
    if env_val is not None:
        return env_val
    return fallback


def _get_provider_format(config: Optional[Dict[str, Any]] = None) -> str:
    fmt = _resolve_setting('AI_PROVIDER_FORMAT', config, 'gemini')
    return fmt.lower() if fmt else 'gemini'


def _build_provider_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assemble provider-specific configuration dict."""
    fmt = _get_provider_format(config)
    cfg: Dict[str, Any] = {'format': fmt}

    if fmt == 'openai':
        cfg['api_key'] = (_resolve_setting('OPENAI_API_KEY', config)
                          or _resolve_setting('GOOGLE_API_KEY', config))
        cfg['api_base'] = _resolve_setting('OPENAI_API_BASE', config, 'https://aihubmix.com/v1')
        if not cfg['api_key']:
            raise ValueError(
                "OPENAI_API_KEY or GOOGLE_API_KEY is required when AI_PROVIDER_FORMAT=openai."
            )
        logger.info("Provider config -- format: openai, api_base: %s", cfg['api_base'])

    else:
        # gemini (default)
        if fmt != 'gemini':
            logger.warning("Unknown provider format '%s', falling back to gemini", fmt)
            cfg['format'] = 'gemini'
        cfg['api_key'] = _resolve_setting('GOOGLE_API_KEY', config)
        cfg['api_base'] = _resolve_setting('GOOGLE_API_BASE', config)
        if not cfg['api_key']:
            raise ValueError("GOOGLE_API_KEY is required for gemini provider.")
        logger.info("Provider config -- format: gemini, api_base: %s", cfg['api_base'])

    return cfg


def _get_model_type_provider_config(model_type: str,
                                    config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get provider config for a specific model type, with fallback to global config."""
    prefix = model_type.upper()
    source = _resolve_setting(f'{prefix}_MODEL_SOURCE', config)

    if not source:
        return _build_provider_config(config)

    source_lower = source.lower()

    if source_lower == 'gemini':
        api_key = (_resolve_setting(f'{prefix}_API_KEY', config)
                   or _resolve_setting('GOOGLE_API_KEY', config))
        api_base = (_resolve_setting(f'{prefix}_API_BASE', config)
                    or _resolve_setting('GOOGLE_API_BASE', config))
        if not api_key:
            raise ValueError(f"API key required for {model_type} with Gemini provider.")
        return {'format': 'gemini', 'api_key': api_key, 'api_base': api_base}

    elif source_lower == 'openai':
        api_key = (_resolve_setting(f'{prefix}_API_KEY', config)
                   or _resolve_setting('OPENAI_API_KEY', config)
                   or _resolve_setting('GOOGLE_API_KEY', config))
        api_base = (_resolve_setting(f'{prefix}_API_BASE', config)
                    or _resolve_setting('OPENAI_API_BASE', config, 'https://aihubmix.com/v1'))
        if not api_key:
            raise ValueError(f"API key required for {model_type} with OpenAI provider.")
        return {'format': 'openai', 'api_key': api_key, 'api_base': api_base}

    else:
        return _build_provider_config(config)


def get_text_provider(model: str = "gemini-3-flash-preview",
                      config: Optional[Dict[str, Any]] = None) -> TextProvider:
    """Factory: return the appropriate text-generation provider."""
    pcfg = _get_model_type_provider_config('text', config)
    fmt = pcfg['format']

    if fmt == 'openai':
        logger.info("Text provider: OpenAI, model=%s", model)
        return OpenAITextProvider(api_key=pcfg['api_key'], api_base=pcfg['api_base'], model=model)
    else:
        logger.info("Text provider: Gemini, model=%s", model)
        return GenAITextProvider(api_key=pcfg['api_key'], api_base=pcfg['api_base'], model=model)


def get_image_provider(model: str = "gemini-3-pro-image-preview",
                       config: Optional[Dict[str, Any]] = None) -> ImageProvider:
    """Factory: return the appropriate image-generation provider."""
    pcfg = _get_model_type_provider_config('image', config)
    fmt = pcfg['format']

    if fmt == 'openai':
        logger.info("Image provider: OpenAI, model=%s", model)
        return OpenAIImageProvider(api_key=pcfg['api_key'], api_base=pcfg['api_base'], model=model)
    else:
        logger.info("Image provider: Gemini, model=%s", model)
        return GenAIImageProvider(api_key=pcfg['api_key'], api_base=pcfg['api_base'], model=model)
