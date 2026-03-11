"""Unit tests for the banana-slides CLI harness (no external dependencies)."""

import json
import os
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure the agent-harness root is importable when running directly
import sys
from pathlib import Path
_ROOT = Path(__file__).parent.parent.parent.parent  # agent-harness/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cli_anything.banana_slides.core.client import BananaSlidesClient, APIError
from cli_anything.banana_slides.core import project as proj_api
from cli_anything.banana_slides.core import page as page_api
from cli_anything.banana_slides.core import task as task_api
from cli_anything.banana_slides.core import export as export_api
from cli_anything.banana_slides.core import settings as settings_api


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(data, status=200):
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.ok = status < 400
    resp.status_code = status
    resp.reason = "OK" if status < 400 else "Error"
    resp.json.return_value = {"success": True, "data": data} if status < 400 else {"error": "bad"}
    return resp


def _client() -> BananaSlidesClient:
    return BananaSlidesClient("http://localhost:5000", access_code="test")


# ===========================================================================
# Config utils
# ===========================================================================

class TestConfig(unittest.TestCase):

    def test_load_config_defaults(self):
        from cli_anything.banana_slides.utils.config import load_config, _DEFAULTS
        with patch("cli_anything.banana_slides.utils.config._CONFIG_PATH") as cp:
            cp.exists.return_value = False
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("BANANA_SLIDES_BASE_URL", None)
                os.environ.pop("BANANA_SLIDES_ACCESS_CODE", None)
                cfg = load_config()
        self.assertEqual(cfg["base_url"], _DEFAULTS["base_url"])
        self.assertEqual(cfg["access_code"], "")

    def test_env_var_overrides_config_file(self):
        from cli_anything.banana_slides.utils.config import load_config
        with patch("cli_anything.banana_slides.utils.config._CONFIG_PATH") as cp:
            cp.exists.return_value = False
            with patch.dict(os.environ, {"BANANA_SLIDES_BASE_URL": "http://custom:9000"}):
                cfg = load_config()
        self.assertEqual(cfg["base_url"], "http://custom:9000")


# ===========================================================================
# BananaSlidesClient
# ===========================================================================

class TestBananaSlidesClient(unittest.TestCase):

    def test_client_sets_access_code_header(self):
        client = BananaSlidesClient("http://localhost:5000", access_code="secret")
        self.assertEqual(client.session.headers.get("X-Access-Code"), "secret")

    def test_client_no_header_when_no_code(self):
        client = BananaSlidesClient("http://localhost:5000", access_code="")
        self.assertNotIn("X-Access-Code", client.session.headers)

    def test_client_raises_api_error_on_4xx(self):
        client = _client()
        with patch.object(client.session, "get", return_value=_mock_response({}, 404)):
            with self.assertRaises(APIError) as ctx:
                client.get("/api/projects/nonexistent")
            self.assertEqual(ctx.exception.status_code, 404)

    def test_client_raises_api_error_on_5xx(self):
        client = _client()
        with patch.object(client.session, "get", return_value=_mock_response({}, 500)):
            with self.assertRaises(APIError) as ctx:
                client.get("/api/projects")
            self.assertEqual(ctx.exception.status_code, 500)

    def test_client_get_returns_body(self):
        client = _client()
        payload = [{"id": "abc", "name": "Test"}]
        with patch.object(client.session, "get", return_value=_mock_response(payload)):
            body = client.get("/api/projects")
        self.assertEqual(body["data"], payload)


# ===========================================================================
# Project API
# ===========================================================================

class TestProjectAPI(unittest.TestCase):

    def setUp(self):
        self.client = _client()

    def test_list_projects_empty(self):
        with patch.object(self.client, "get", return_value={"success": True, "data": []}):
            result = proj_api.list_projects(self.client)
        self.assertEqual(result, [])

    def test_list_projects_returns_list(self):
        sample = [{"id": "p1", "name": "Alpha"}, {"id": "p2", "name": "Beta"}]
        with patch.object(self.client, "get", return_value={"data": sample}):
            result = proj_api.list_projects(self.client)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "p1")

    def test_create_project_sends_topic(self):
        expected = {"id": "new-id", "name": "My Topic"}
        with patch.object(self.client, "post", return_value={"data": expected}) as mock_post:
            result = proj_api.create_project(self.client, topic="My Topic")
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        self.assertEqual(payload["topic"], "My Topic")
        self.assertEqual(result["id"], "new-id")

    def test_create_project_includes_style(self):
        with patch.object(self.client, "post", return_value={"data": {}}) as mock_post:
            proj_api.create_project(self.client, topic="T", style="Dark minimal")
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload.get("template_style"), "Dark minimal")

    def test_get_project(self):
        sample = {"id": "abc", "name": "Test"}
        with patch.object(self.client, "get", return_value={"data": sample}) as mock_get:
            result = proj_api.get_project(self.client, "abc")
        mock_get.assert_called_once_with("/api/projects/abc")
        self.assertEqual(result["id"], "abc")

    def test_delete_project(self):
        with patch.object(self.client, "delete", return_value={"success": True}) as mock_del:
            proj_api.delete_project(self.client, "abc")
        mock_del.assert_called_once_with("/api/projects/abc")

    def test_generate_descriptions_returns_task(self):
        task_data = {"task_id": "t-001", "status": "PENDING"}
        with patch.object(self.client, "post", return_value={"data": task_data}):
            result = proj_api.generate_descriptions(self.client, "p1")
        self.assertIn("task_id", result)

    def test_generate_images_returns_task(self):
        task_data = {"task_id": "t-002", "status": "PENDING"}
        with patch.object(self.client, "post", return_value={"data": task_data}):
            result = proj_api.generate_images(self.client, "p1")
        self.assertIn("task_id", result)


# ===========================================================================
# Page API
# ===========================================================================

class TestPageAPI(unittest.TestCase):

    def setUp(self):
        self.client = _client()

    def test_list_pages(self):
        pages = [{"id": "pg1", "order_index": 0}, {"id": "pg2", "order_index": 1}]
        with patch.object(self.client, "get", return_value={"data": pages}):
            result = page_api.list_pages(self.client, "proj1")
        self.assertEqual(len(result), 2)

    def test_create_page_minimal(self):
        created = {"id": "new-page", "order_index": 3}
        with patch.object(self.client, "post", return_value={"data": created}) as mock_post:
            result = page_api.create_page(self.client, "proj1", 3)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["order_index"], 3)
        self.assertNotIn("part", payload)

    def test_create_page_with_outline(self):
        outline = {"title": "Intro", "points": ["p1", "p2"]}
        with patch.object(self.client, "post", return_value={"data": {}}) as mock_post:
            page_api.create_page(self.client, "proj1", 0, outline_content=outline)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["outline_content"]["title"], "Intro")

    def test_generate_page_description(self):
        page_data = {"id": "pg1", "status": "DESCRIPTION_GENERATED"}
        with patch.object(self.client, "post", return_value={"data": page_data}) as mock_post:
            result = page_api.generate_page_description(self.client, "proj1", "pg1")
        url = mock_post.call_args[0][0]
        self.assertIn("generate/description", url)

    def test_generate_page_image_returns_task(self):
        task_data = {"task_id": "img-task", "status": "PENDING"}
        with patch.object(self.client, "post", return_value={"data": task_data}):
            result = page_api.generate_page_image(self.client, "proj1", "pg1")
        self.assertEqual(result["task_id"], "img-task")

    def test_edit_page_image_returns_task(self):
        task_data = {"task_id": "edit-task", "status": "PENDING"}
        with patch.object(self.client, "post", return_value={"data": task_data}):
            result = page_api.edit_page_image(
                self.client, "proj1", "pg1", "Make background blue"
            )
        self.assertEqual(result["task_id"], "edit-task")


# ===========================================================================
# Task API
# ===========================================================================

class TestTaskAPI(unittest.TestCase):

    def setUp(self):
        self.client = _client()

    def test_get_task(self):
        sample = {"id": "t1", "status": "COMPLETED"}
        with patch.object(self.client, "get", return_value={"data": sample}):
            result = task_api.get_task(self.client, "proj1", "t1")
        self.assertEqual(result["status"], "COMPLETED")

    def test_wait_for_task_completes_immediately(self):
        sample = {"id": "t1", "status": "COMPLETED", "progress": {}}

        def _get(_path):
            return {"data": sample}

        with patch.object(self.client, "get", side_effect=_get):
            result = task_api.wait_for_task(self.client, "proj1", "t1", interval=0.01)
        self.assertEqual(result["status"], "COMPLETED")

    def test_wait_for_task_polls_until_done(self):
        responses = [
            {"id": "t1", "status": "PENDING", "progress": {"total": 3, "completed": 0}},
            {"id": "t1", "status": "PENDING", "progress": {"total": 3, "completed": 1}},
            {"id": "t1", "status": "COMPLETED", "progress": {"total": 3, "completed": 3}},
        ]
        call_count = {"n": 0}

        def _get(_path):
            resp = responses[min(call_count["n"], len(responses) - 1)]
            call_count["n"] += 1
            return {"data": resp}

        with patch.object(self.client, "get", side_effect=_get):
            with patch("time.sleep", return_value=None):
                result = task_api.wait_for_task(self.client, "proj1", "t1", interval=0.01)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertGreaterEqual(call_count["n"], 3)

    def test_wait_for_task_raises_on_fail(self):
        sample = {"id": "t1", "status": "FAILED", "result": {"error": "AI timeout"}}
        with patch.object(self.client, "get", return_value={"data": sample}):
            with self.assertRaises(APIError):
                task_api.wait_for_task(self.client, "proj1", "t1", interval=0.01)

    def test_wait_for_task_raises_on_timeout(self):
        sample = {"id": "t1", "status": "PENDING", "progress": {}}
        with patch.object(self.client, "get", return_value={"data": sample}):
            with patch("time.sleep", return_value=None):
                with self.assertRaises(TimeoutError):
                    task_api.wait_for_task(
                        self.client, "proj1", "t1", interval=0.001, timeout=0.005
                    )


# ===========================================================================
# Export API
# ===========================================================================

class TestExportAPI(unittest.TestCase):

    def setUp(self):
        self.client = _client()

    def test_export_pptx_with_filename(self):
        data = {"download_url": "/files/proj/exports/out.pptx"}
        with patch.object(self.client, "get", return_value={"data": data}) as mock_get:
            result = export_api.export_pptx(self.client, "proj1", filename="out")
        params = mock_get.call_args[1]["params"]
        self.assertEqual(params.get("filename"), "out")

    def test_export_pdf(self):
        data = {"download_url": "/files/proj/exports/out.pdf"}
        with patch.object(self.client, "get", return_value={"data": data}):
            result = export_api.export_pdf(self.client, "proj1")
        self.assertIn("download_url", result)

    def test_export_images(self):
        data = {"download_url": "/files/proj/exports/slides.zip"}
        with patch.object(self.client, "get", return_value={"data": data}):
            result = export_api.export_images(self.client, "proj1")
        self.assertIn("download_url", result)

    def test_export_editable_pptx_returns_task(self):
        task_data = {"task_id": "exp-task", "method": "recursive_analysis"}
        with patch.object(self.client, "post", return_value={"data": task_data}):
            result = export_api.export_editable_pptx(self.client, "proj1")
        self.assertEqual(result["task_id"], "exp-task")


# ===========================================================================
# Settings API
# ===========================================================================

class TestSettingsAPI(unittest.TestCase):

    def setUp(self):
        self.client = _client()

    def test_get_settings(self):
        sample = {"text_model": "gemini-3-flash-preview"}
        with patch.object(self.client, "get", return_value={"data": sample}):
            result = settings_api.get_settings(self.client)
        self.assertEqual(result["text_model"], "gemini-3-flash-preview")

    def test_update_settings_sends_partial(self):
        with patch.object(self.client, "put", return_value={"data": {}}) as mock_put:
            settings_api.update_settings(self.client, {"output_language": "en"})
        payload = mock_put.call_args[1]["json"]
        self.assertEqual(payload["output_language"], "en")
        self.assertNotIn("api_key", payload)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
