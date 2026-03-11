# BANANA-SLIDES.md — CLI Harness SOP

## Overview

Banana Slides is an AI-powered PPT generation service built on a Flask REST backend.
Users create **Projects**, which contain **Pages**. Each page goes through three stages:
1. **Outline** – Title + bullet points
2. **Description** – Rich text prompt for AI image generation
3. **Image** – The final slide image (PNG/WebP)

Long-running steps (bulk description generation, image generation, editable PPTX export)
are handled by the **Task** system. Tasks are submitted and then polled for completion.

## API Base URL

Default: `http://localhost:5000`

## Authentication

Optional `X-Access-Code` header (set `ACCESS_CODE` env var on server to enable).

## Key Entities

| Entity   | Fields                                                 |
|----------|--------------------------------------------------------|
| Project  | id, name, topic, creation_type, image_aspect_ratio, status |
| Page     | id, project_id, order_index, part, status, outline_content, description_content, generated_image_path |
| Task     | id, project_id, task_type, status, progress, result   |
| Settings | api_key, api_base_url, ai_provider_format, text_model, image_model |

## Page Status Flow

```
DRAFT → OUTLINE_GENERATED → DESCRIPTION_GENERATED → IMAGE_GENERATED
```

## Key Endpoints

### Projects
- `GET  /api/projects`                          List all
- `POST /api/projects`                          Create (topic, creation_type, ...)
- `GET  /api/projects/{id}`                     Get one
- `DELETE /api/projects/{id}`                   Delete
- `POST /api/projects/{id}/generate-outline`    AI outline generation (stream SSE)
- `POST /api/projects/{id}/generate-descriptions` Bulk description gen (async task)
- `POST /api/projects/{id}/generate-images`     Bulk image gen (async task)

### Pages
- `GET  /api/projects/{pid}/pages`              List pages
- `POST /api/projects/{pid}/pages`              Add page
- `DELETE /api/projects/{pid}/pages/{page_id}`  Delete page
- `PUT  /api/projects/{pid}/pages/{page_id}/outline`     Update outline
- `PUT  /api/projects/{pid}/pages/{page_id}/description` Update description
- `POST /api/projects/{pid}/pages/{page_id}/generate/description` Single desc gen
- `POST /api/projects/{pid}/pages/{page_id}/generate/image`       Single image gen (async)
- `POST /api/projects/{pid}/pages/{page_id}/edit/image`           Edit image (async)

### Tasks
- `GET  /api/projects/{pid}/tasks/{task_id}`    Get task status

### Export
- `GET  /api/projects/{id}/export/pptx`         Export PPTX (sync, returns download URL)
- `GET  /api/projects/{id}/export/pdf`          Export PDF (sync, returns download URL)
- `GET  /api/projects/{id}/export/images`       Export images/ZIP (sync)
- `POST /api/projects/{id}/export/editable-pptx` Editable PPTX (async task)

### Settings
- `GET  /api/settings`                          Get current settings
- `PUT  /api/settings`                          Update settings

## CLI Usage Patterns

### Full Workflow (new project)
```bash
# 1. Create project
ID=$(cli-anything-banana-slides project create --topic "AI in Healthcare" --json | python -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# 2. Generate outline (streaming – waits for completion)
cli-anything-banana-slides project generate-outline $ID

# 3. Generate all descriptions
cli-anything-banana-slides project generate-descriptions $ID --wait

# 4. Generate all images
cli-anything-banana-slides project generate-images $ID --wait

# 5. Export
cli-anything-banana-slides export pptx $ID --filename my_presentation
```

### Check task status
```bash
cli-anything-banana-slides task wait TASK_ID
```
