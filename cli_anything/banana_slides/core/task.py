"""Task status polling for async operations."""

import time
from typing import Dict
from .client import BananaSlidesClient, APIError


TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


def get_task(client: BananaSlidesClient, project_id: str, task_id: str) -> Dict:
    body = client.get(f"/api/projects/{project_id}/tasks/{task_id}")
    return body.get("data", body)


def wait_for_task(
    client: BananaSlidesClient,
    project_id: str,
    task_id: str,
    interval: float = 2.0,
    timeout: float = 600.0,
    progress_callback=None,
) -> Dict:
    """
    Poll until the task reaches a terminal state.

    Args:
        progress_callback: optional callable(task_data) called on each poll.

    Returns:
        Final task data dict.

    Raises:
        TimeoutError: if timeout is exceeded.
        APIError: if the task reports FAILED status.
    """
    elapsed = 0.0
    while elapsed < timeout:
        task = get_task(client, project_id, task_id)
        status = task.get("status", "").upper()
        if progress_callback:
            progress_callback(task)
        if status in TERMINAL_STATUSES:
            if status == "FAILED":
                error_msg = (task.get("result") or {}).get("error", "Task failed")
                raise APIError(f"Task {task_id} failed: {error_msg}")
            return task
        time.sleep(interval)
        elapsed += interval
    raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")
