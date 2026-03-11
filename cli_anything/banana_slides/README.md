# cli-anything-banana-slides

CLI harness for [Banana Slides](https://github.com/Anionex/banana-slides) — an AI-powered PPT generation service.

## Installation

```bash
cd banana-slides/agent-harness
pip install -e .
```

Verify:
```bash
cli-anything-banana-slides --help
```

## Quick Start

```bash
# Point to your Banana Slides server (default: http://localhost:5000)
cli-anything-banana-slides config set-url http://localhost:5000

# (Optional) set access code if your server requires it
cli-anything-banana-slides config set-access-code mysecret

# Create a project
cli-anything-banana-slides project create --topic "Climate Change Solutions"

# Generate outline (streaming)
cli-anything-banana-slides project generate-outline <PROJECT_ID>

# Generate all descriptions (wait for completion)
cli-anything-banana-slides project generate-descriptions <PROJECT_ID> --wait

# Generate all images (wait — this takes a while)
cli-anything-banana-slides project generate-images <PROJECT_ID> --wait --timeout 3600

# Export PPTX and get download URL
cli-anything-banana-slides export pptx <PROJECT_ID> --filename my_presentation
```

## All Commands

### config
```
config set-url URL            Set API base URL
config set-access-code CODE   Set access code
config show [--json]          Show current config
```

### project
```
project list [--json]
project create --topic TEXT [--name TEXT] [--style TEXT]
               [--aspect-ratio 16:9|4:3] [--type scratch|ppt_renovation]
project get PROJECT_ID [--json]
project delete PROJECT_ID [--yes]
project generate-outline PROJECT_ID [--slides N] [--language zh|en|ja|auto]
project generate-descriptions PROJECT_ID [--language] [--wait] [--timeout N]
project generate-images PROJECT_ID [--language] [--wait] [--timeout N]
```

### page
```
page list PROJECT_ID [--json]
page create PROJECT_ID --order-index N [--part TEXT] [--title TEXT]
page delete PROJECT_ID PAGE_ID [--yes]
page generate-description PROJECT_ID PAGE_ID [--force] [--language]
page generate-image PROJECT_ID PAGE_ID [--force] [--no-template] [--wait]
page edit-image PROJECT_ID PAGE_ID --instruction TEXT [--use-template] [--wait]
page image-versions PROJECT_ID PAGE_ID [--json]
```

### task
```
task status PROJECT_ID TASK_ID [--json]
task wait PROJECT_ID TASK_ID [--interval N] [--timeout N] [--json]
```

### export
```
export pptx PROJECT_ID [--filename NAME]
export pdf  PROJECT_ID [--filename NAME]
export images PROJECT_ID
export editable-pptx PROJECT_ID [--filename NAME] [--depth 1-5] [--workers N] [--wait]
```

### settings
```
settings get [--json]
settings update [--api-key K] [--api-base URL] [--provider gemini|openai|lazyllm]
               [--text-model M] [--image-model M] [--output-language zh|en|ja|auto]
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BANANA_SLIDES_BASE_URL` | API base URL | `http://localhost:5000` |
| `BANANA_SLIDES_ACCESS_CODE` | Access code | (empty) |

## JSON Output

Every command supports `--json` for machine-readable output:

```bash
ID=$(cli-anything-banana-slides project create --topic "AI" --json \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

## Running Tests

```bash
# Unit tests (no server required)
cd banana-slides/agent-harness
pip install pytest
pytest cli_anything/banana_slides/tests/test_core.py -v

# E2E tests (requires running server)
BANANA_SLIDES_E2E=1 pytest cli_anything/banana_slides/tests/test_full_e2e.py -v

# Subprocess tests with installed CLI
CLI_ANYTHING_FORCE_INSTALLED=1 BANANA_SLIDES_E2E=1 pytest cli_anything/banana_slides/tests/test_full_e2e.py::TestCLISubprocess -v
```
