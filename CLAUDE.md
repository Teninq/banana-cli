# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI-driven AI slide generation tool with two operating modes: **remote** (Banana Slides Flask backend) and **local** (standalone AI pipeline using OpenAI-compatible or Gemini APIs directly).

## Architecture

```
Entry Scripts (make_ppt.py, make_ppt_from_md.py)
        │
        ├── mode=remote ──► engine/remote.py (RemoteBackend)
        │                       └── core/ (HTTP client layer)
        │                            ├── client.py  → BananaSlidesClient (auth + requests)
        │                            ├── project.py → project CRUD + generate operations
        │                            ├── page.py    → page CRUD
        │                            ├── task.py    → async task polling (4s interval)
        │                            └── export.py  → download PPTX/PDF
        │
        └── mode=local ───► engine/local_backend.py (LocalBackend)
                                ├── ai_service.py → AI orchestration (outline, descriptions, images)
                                ├── local_store.py → JSON file-based project storage
                                ├── export.py → python-pptx builder (text + image modes)
                                ├── prompts.py → all LLM prompt templates
                                └── ai_providers/ → pluggable provider factory
                                     ├── text/ → GenAI + OpenAI text providers
                                     └── image/ → GenAI + OpenAI image providers
```

**Key abstraction**: `engine/base.py` defines `SlidesBackend` Protocol. Both `RemoteBackend` and `LocalBackend` implement this interface, so entry scripts are mode-agnostic.

**Pipeline flow** (5 steps): Create project → Generate outline → Generate descriptions → Generate images → Export PPTX

**Export modes** (`--export-mode`):
  - `image` (default) — each slide is a full-bleed PNG, not editable in PowerPoint
  - `text` — dark-themed styled text slides, no images
  - `editable` — background image + AI-extracted editable text overlays (uses vision model to analyze slide images, places color-matched rectangles over original text, then adds editable text boxes)

**Page state machine**: `DRAFT` → `OUTLINE_GENERATED` → `DESCRIPTION_GENERATED` → `IMAGE_GENERATED`

## Configuration

Config file: `~/.banana_slides_cli.json` (merged with defaults from `utils/config.py`).

Environment variable overrides:
- `BANANA_SLIDES_MODE` → `local` or `remote`
- `BANANA_SLIDES_BASE_URL` → remote server URL
- `BANANA_SLIDES_ACCESS_CODE` → API auth code

Local mode AI config keys (in `local` section of config JSON):
- `ai_provider_format`: `openai` or `gemini`
- `api_key`, `api_base`, `text_model`, `image_model`, `max_workers`

## Commands

```bash
# Install (editable)
pip install -e .

# Install with local AI dependencies
pip install -e ".[local]"

# One-shot PPT generation
python make_ppt.py --topic "主题" --lang zh
python make_ppt.py --topic "Topic" --mode local
python make_ppt.py --topic "Topic" --mode local --export-mode editable

# Markdown to PPT
python make_ppt_from_md.py doc.md
python make_ppt_from_md.py doc.md --mode local --export-mode editable

# Export existing project to local PPTX
python export_pptx_from_descriptions.py

# Run tests
python -m pytest cli_anything/banana_slides/tests/
python -m pytest cli_anything/banana_slides/tests/test_core.py -v

# CLI (after pip install)
cli-anything-banana-slides --help
```

## Development Notes

- Windows environment: use `python` not `python3`; always specify `encoding="utf-8"` for file I/O
- Remote API base: `http://localhost:5000`, all endpoints prefixed `/api/`
- Async operations return `task_id`, polled via `task.wait_for_task()` at 4s intervals
- Image generation is slow (5-15 min), timeout set to 3600s
- `BananaSlidesClient` adds `X-Access-Code` header for auth
- Scripts work both installed (`pip install -e .`) and standalone (via `sys.path` injection)
- AI provider factory (`ai_providers/__init__.py`) resolves config: explicit dict → env vars → defaults
- `export_pptx_from_descriptions.py` produces dark-themed PPTX (dark blue background + white text)
- `BANANA-SLIDES.md` contains complete API endpoint reference
