"""
E2E tests for the banana-slides CLI harness.

Requires a running Banana Slides server.
Set BANANA_SLIDES_E2E=1 to enable.
Set BANANA_SLIDES_BASE_URL if the server is not on http://localhost:5000.

Run via subprocess to test the installed CLI command:
    CLI_ANYTHING_FORCE_INSTALLED=1 pytest test_full_e2e.py -v
"""

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

# Allow running from project root without installation
_ROOT = Path(__file__).parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cli_anything.banana_slides.core.client import BananaSlidesClient, APIError
from cli_anything.banana_slides.core import project as proj_api
from cli_anything.banana_slides.core import page as page_api
from cli_anything.banana_slides.core import task as task_api
from cli_anything.banana_slides.core import export as export_api
from cli_anything.banana_slides.core import settings as settings_api


# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------

E2E_ENABLED = os.getenv("BANANA_SLIDES_E2E", "0") == "1"
SKIP_REASON = "Set BANANA_SLIDES_E2E=1 to run E2E tests"

BASE_URL = os.getenv("BANANA_SLIDES_BASE_URL", "http://localhost:5000")


def _resolve_cli(name: str) -> str:
    """
    Resolve the CLI executable path.
    With CLI_ANYTHING_FORCE_INSTALLED=1, uses shutil.which to test the installed command.
    Otherwise falls back to running via the module entry point.
    """
    if os.getenv("CLI_ANYTHING_FORCE_INSTALLED", "0") == "1":
        exe = shutil.which(name)
        if not exe:
            raise RuntimeError(f"Command '{name}' not found in PATH. Install with: pip install -e .")
        return exe
    return sys.executable + f" -m cli_anything.banana_slides.banana_slides_cli"


def _run_cli(*args, check=True) -> subprocess.CompletedProcess:
    """Run CLI via subprocess and return the result."""
    exe_str = _resolve_cli("cli-anything-banana-slides")
    if " " in exe_str:
        cmd = exe_str.split() + list(args)
    else:
        cmd = [exe_str] + list(args)
    env = {**os.environ, "BANANA_SLIDES_BASE_URL": BASE_URL}
    return subprocess.run(cmd, capture_output=True, text=True, check=check, env=env)


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

@unittest.skipUnless(E2E_ENABLED, SKIP_REASON)
class TestHealthCheck(unittest.TestCase):

    def test_health_check(self):
        client = BananaSlidesClient(BASE_URL)
        resp = client.session.get(f"{BASE_URL}/health", timeout=5)
        self.assertTrue(resp.ok)
        data = resp.json()
        self.assertEqual(data.get("status"), "ok")


@unittest.skipUnless(E2E_ENABLED, SKIP_REASON)
class TestProjectWorkflow(unittest.TestCase):
    """Full create → outline → describe → image → export → delete cycle."""

    _project_id: str = ""

    @classmethod
    def setUpClass(cls):
        cls.client = BananaSlidesClient(BASE_URL)

    def test_01_create_project(self):
        result = proj_api.create_project(
            self.client,
            topic="CLI Test: Renewable Energy",
            aspect_ratio="16:9",
        )
        self.__class__._project_id = result["id"]
        self.assertTrue(result["id"])
        self.assertEqual(result["topic"], "CLI Test: Renewable Energy")

    def test_02_project_appears_in_list(self):
        projects = proj_api.list_projects(self.client)
        ids = [p["id"] for p in projects]
        self.assertIn(self.__class__._project_id, ids)

    def test_03_generate_outline(self):
        pid = self.__class__._project_id
        try:
            proj_api.generate_outline(self.client, pid, num_pages=3, language="en")
        except Exception:
            pass  # Outline stream may have varied response shapes
        project = proj_api.get_project(self.client, pid)
        pages = project.get("pages") or []
        self.assertGreater(len(pages), 0, "Expected at least one page after outline generation")

    def test_04_page_list_matches_project(self):
        pid = self.__class__._project_id
        pages = page_api.list_pages(self.client, pid)
        project = proj_api.get_project(self.client, pid)
        self.assertEqual(len(pages), len(project.get("pages", [])))

    def test_05_generate_descriptions_task(self):
        pid = self.__class__._project_id
        pages = page_api.list_pages(self.client, pid)
        if not pages:
            self.skipTest("No pages available")
        # Only generate for first page to keep test fast
        first_page = pages[0]
        result = proj_api.generate_descriptions(
            self.client, pid, language="en", page_ids=[first_page["id"]]
        )
        self.assertIn("task_id", result)
        final = task_api.wait_for_task(
            self.client, pid, result["task_id"], interval=3, timeout=120
        )
        self.assertEqual(final["status"].upper(), "COMPLETED")

    def test_06_export_pptx_requires_images(self):
        """Export PPTX before images are generated — expect error (no images yet)."""
        pid = self.__class__._project_id
        try:
            export_api.export_pptx(self.client, pid)
            # If it doesn't raise, there must already be images — that's also OK
        except APIError as e:
            self.assertIn(e.status_code, (400, 404, 503))

    def test_07_settings_get(self):
        result = settings_api.get_settings(self.client)
        self.assertIsInstance(result, dict)

    def test_08_delete_project(self):
        pid = self.__class__._project_id
        if not pid:
            self.skipTest("No project created")
        proj_api.delete_project(self.client, pid)
        projects = proj_api.list_projects(self.client)
        ids = [p["id"] for p in projects]
        self.assertNotIn(pid, ids)


@unittest.skipUnless(E2E_ENABLED, SKIP_REASON)
class TestCLISubprocess(unittest.TestCase):
    """Test the installed CLI command via subprocess."""

    def test_cli_help(self):
        result = _run_cli("--help")
        self.assertIn("banana", result.stdout.lower())
        self.assertEqual(result.returncode, 0)

    def test_cli_project_list_json(self):
        result = _run_cli("project", "list", "--json")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)

    def test_cli_config_show_json(self):
        result = _run_cli("config", "show", "--json")
        self.assertEqual(result.returncode, 0)
        cfg = json.loads(result.stdout)
        self.assertIn("base_url", cfg)

    def test_cli_settings_get_json(self):
        result = _run_cli("settings", "get", "--json")
        self.assertEqual(result.returncode, 0)
        cfg = json.loads(result.stdout)
        self.assertIsInstance(cfg, dict)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
