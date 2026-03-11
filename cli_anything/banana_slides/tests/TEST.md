# TEST.md — Banana Slides CLI Harness Test Plan

## Overview

Two test suites:

| Suite | File | Deps |
|-------|------|------|
| Unit  | `test_core.py` | stdlib + `unittest.mock` only |
| E2E   | `test_full_e2e.py` | Running Banana Slides server at `http://localhost:5000` |

---

## Unit Test Plan (`test_core.py`)

### Config utilities
- `test_load_config_defaults` — fresh state returns default base_url / access_code
- `test_save_and_load_config` — round-trip persists values
- `test_env_var_overrides_config_file` — env var `BANANA_SLIDES_BASE_URL` wins

### BananaSlidesClient
- `test_client_sets_access_code_header` — header present when code given
- `test_client_raises_api_error_on_4xx` — non-200 raises `APIError`
- `test_client_raises_api_error_on_5xx` — 500 raises `APIError`
- `test_client_get_returns_body` — mock 200 returns dict

### Project API
- `test_list_projects_empty` — empty list returned
- `test_create_project` — POST sent with correct payload
- `test_get_project` — GET to correct URL
- `test_delete_project` — DELETE to correct URL
- `test_generate_descriptions_returns_task` — task_id present in result
- `test_generate_images_returns_task` — task_id present in result

### Page API
- `test_list_pages` — GET returns list
- `test_create_page_minimal` — only order_index required
- `test_create_page_with_outline` — outline_content included
- `test_generate_page_description` — POST to correct URL
- `test_generate_page_image_returns_task` — async, returns task_id
- `test_edit_page_image_returns_task` — async, returns task_id

### Task API
- `test_get_task` — GET task by id
- `test_wait_for_task_completes_immediately` — COMPLETED on first poll
- `test_wait_for_task_polls_until_done` — 3 PENDING then COMPLETED
- `test_wait_for_task_raises_on_fail` — FAILED raises APIError
- `test_wait_for_task_raises_on_timeout` — TimeoutError after exceeded time

### Export API
- `test_export_pptx` — GET with filename param
- `test_export_pdf` — GET with filename param
- `test_export_images` — GET, no extra params
- `test_export_editable_pptx_returns_task` — POST, task_id present

### Settings API
- `test_get_settings` — GET `/api/settings`
- `test_update_settings` — PUT with partial payload

---

## E2E Test Plan (`test_full_e2e.py`)

Requires: running server, `BANANA_SLIDES_E2E=1` env var.

### Health check
- `test_health_check` — `/health` returns status=ok

### Full project workflow
1. `test_create_and_list_project` — create, then find in list
2. `test_generate_outline` — outline is generated, pages count > 0
3. `test_page_list` — pages present after outline
4. `test_generate_descriptions_task` — task submitted and completes
5. `test_generate_images_task` — task submitted and completes (small # of slides)
6. `test_export_pptx` — download URL returned, contains `.pptx`
7. `test_export_pdf` — download URL returned, contains `.pdf`
8. `test_delete_project` — project removed from list

### Settings workflow
- `test_get_settings` — non-empty dict returned
- `test_update_settings_language` — set language, verify change

---

## Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.0.2
collected 32 items

test_core.py::TestConfig::test_env_var_overrides_config_file PASSED [  3%]
test_core.py::TestConfig::test_load_config_defaults PASSED [  6%]
test_core.py::TestBananaSlidesClient::test_client_get_returns_body PASSED [  9%]
test_core.py::TestBananaSlidesClient::test_client_no_header_when_no_code PASSED [ 12%]
test_core.py::TestBananaSlidesClient::test_client_raises_api_error_on_4xx PASSED [ 15%]
test_core.py::TestBananaSlidesClient::test_client_raises_api_error_on_5xx PASSED [ 18%]
test_core.py::TestBananaSlidesClient::test_client_sets_access_code_header PASSED [ 21%]
test_core.py::TestProjectAPI::test_create_project_includes_style PASSED [ 25%]
test_core.py::TestProjectAPI::test_create_project_sends_topic PASSED [ 28%]
test_core.py::TestProjectAPI::test_delete_project PASSED [ 31%]
test_core.py::TestProjectAPI::test_generate_descriptions_returns_task PASSED [ 34%]
test_core.py::TestProjectAPI::test_generate_images_returns_task PASSED [ 37%]
test_core.py::TestProjectAPI::test_get_project PASSED [ 40%]
test_core.py::TestProjectAPI::test_list_projects_empty PASSED [ 43%]
test_core.py::TestProjectAPI::test_list_projects_returns_list PASSED [ 46%]
test_core.py::TestPageAPI::test_create_page_minimal PASSED [ 50%]
test_core.py::TestPageAPI::test_create_page_with_outline PASSED [ 53%]
test_core.py::TestPageAPI::test_edit_page_image_returns_task PASSED [ 56%]
test_core.py::TestPageAPI::test_generate_page_description PASSED [ 59%]
test_core.py::TestPageAPI::test_generate_page_image_returns_task PASSED [ 62%]
test_core.py::TestPageAPI::test_list_pages PASSED [ 65%]
test_core.py::TestTaskAPI::test_get_task PASSED [ 68%]
test_core.py::TestTaskAPI::test_wait_for_task_completes_immediately PASSED [ 71%]
test_core.py::TestTaskAPI::test_wait_for_task_polls_until_done PASSED [ 75%]
test_core.py::TestTaskAPI::test_wait_for_task_raises_on_fail PASSED [ 78%]
test_core.py::TestTaskAPI::test_wait_for_task_raises_on_timeout PASSED [ 81%]
test_core.py::TestExportAPI::test_export_editable_pptx_returns_task PASSED [ 84%]
test_core.py::TestExportAPI::test_export_images PASSED [ 87%]
test_core.py::TestExportAPI::test_export_pdf PASSED [ 90%]
test_core.py::TestExportAPI::test_export_pptx_with_filename PASSED [ 93%]
test_core.py::TestSettingsAPI::test_get_settings PASSED [ 96%]
test_core.py::TestSettingsAPI::test_update_settings_sends_partial PASSED [100%]

============================= 32 passed in 0.05s ==============================
```
