"""cli-anything-banana-slides — CLI harness for the Banana Slides AI PPT service.

Usage:
    cli-anything-banana-slides [OPTIONS] COMMAND [ARGS]...

Groups: project, page, task, export, settings, config
"""

import json
import sys
import time
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from cli_anything.banana_slides.core.client import BananaSlidesClient, APIError
from cli_anything.banana_slides.core import project as proj_api
from cli_anything.banana_slides.core import page as page_api
from cli_anything.banana_slides.core import task as task_api
from cli_anything.banana_slides.core import export as export_api
from cli_anything.banana_slides.core import settings as settings_api
from cli_anything.banana_slides.utils.config import (
    load_config,
    save_config,
    get_base_url,
    get_access_code,
    get_mode,
    get_local_config,
)

console = Console()


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _out(data, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        rprint(data)


def _err(msg: str) -> None:
    console.print(f"[red]Error:[/red] {msg}", err=True)
    sys.exit(1)


def _make_client(ctx) -> BananaSlidesClient:
    base_url = ctx.obj.get("base_url") or get_base_url()
    access_code = ctx.obj.get("access_code") or get_access_code()
    return BananaSlidesClient(base_url, access_code)


def _make_backend(ctx):
    """Return a SlidesBackend (LocalBackend or RemoteBackend) based on mode."""
    mode = ctx.obj.get("mode") or get_mode()
    if mode == "local":
        from cli_anything.banana_slides.engine.local_backend import LocalBackend
        local_cfg = get_local_config()
        max_workers = local_cfg.pop("max_workers", 4)
        return LocalBackend(config=local_cfg, max_workers=max_workers)
    from cli_anything.banana_slides.engine.remote import RemoteBackend
    base_url = ctx.obj.get("base_url") or get_base_url()
    access_code = ctx.obj.get("access_code") or get_access_code()
    return RemoteBackend(base_url=base_url, access_code=access_code)


# ---------------------------------------------------------------------------
# Root CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.option("--base-url", envvar="BANANA_SLIDES_BASE_URL", default=None, help="API base URL")
@click.option("--access-code", envvar="BANANA_SLIDES_ACCESS_CODE", default=None, help="Access code")
@click.option("--mode", type=click.Choice(["local", "remote"]), default=None,
              envvar="BANANA_SLIDES_MODE", help="Backend mode: local (AI runs locally) or remote (HTTP API)")
@click.pass_context
def cli(ctx, base_url, access_code, mode):
    """CLI harness for Banana Slides – AI-powered PPT generation."""
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url
    ctx.obj["access_code"] = access_code
    ctx.obj["mode"] = mode


# ===========================================================================
# CONFIG group
# ===========================================================================

@cli.group()
def config():
    """Manage CLI configuration (base URL, access code)."""


@config.command("set-url")
@click.argument("url")
def config_set_url(url):
    """Set the Banana Slides API base URL."""
    cfg = load_config()
    cfg["base_url"] = url.rstrip("/")
    save_config(cfg)
    console.print(f"[green]Base URL set to:[/green] {cfg['base_url']}")


@config.command("set-access-code")
@click.argument("code")
def config_set_access_code(code):
    """Set the access code for the Banana Slides API."""
    cfg = load_config()
    cfg["access_code"] = code
    save_config(cfg)
    console.print("[green]Access code saved.[/green]")


@config.command("show")
@click.option("--json", "as_json", is_flag=True)
def config_show(as_json):
    """Show current CLI configuration."""
    cfg = load_config()
    # Mask access code and API key
    display = dict(cfg)
    if display.get("access_code"):
        display["access_code"] = "***"
    local = display.get("local", {})
    if local.get("api_key"):
        local = dict(local)
        local["api_key"] = "***"
        display["local"] = local
    _out(display, as_json)


@config.command("set-mode")
@click.argument("mode", type=click.Choice(["local", "remote"]))
def config_set_mode(mode):
    """Set the backend mode (local or remote)."""
    cfg = load_config()
    cfg["mode"] = mode
    save_config(cfg)
    console.print(f"[green]Mode set to:[/green] {mode}")


@config.command("set-local")
@click.option("--provider", type=click.Choice(["openai", "gemini"]), help="AI provider format")
@click.option("--api-key", help="API key for the AI provider")
@click.option("--api-base", help="API base URL")
@click.option("--text-model", help="Text generation model name")
@click.option("--image-model", help="Image generation model name")
@click.option("--max-workers", type=int, help="Max parallel workers for image generation")
def config_set_local(provider, api_key, api_base, text_model, image_model, max_workers):
    """Configure local mode settings (AI provider, models, etc.)."""
    cfg = load_config()
    local = cfg.get("local", {})
    if provider is not None:
        local["ai_provider_format"] = provider
    if api_key is not None:
        local["api_key"] = api_key
    if api_base is not None:
        local["api_base"] = api_base
    if text_model is not None:
        local["text_model"] = text_model
    if image_model is not None:
        local["image_model"] = image_model
    if max_workers is not None:
        local["max_workers"] = max_workers
    cfg["local"] = local
    save_config(cfg)
    console.print("[green]Local config updated.[/green]")
    # Show current local config (mask key)
    show = dict(local)
    if show.get("api_key"):
        show["api_key"] = show["api_key"][:8] + "***"
    rprint(show)


# ===========================================================================
# PROJECT group
# ===========================================================================

@cli.group()
def project():
    """Manage Banana Slides projects."""


@project.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output JSON")
@click.pass_context
def project_list(ctx, as_json):
    """List all projects."""
    client = _make_client(ctx)
    try:
        projects = proj_api.list_projects(client)
    except APIError as e:
        _err(str(e))
    if as_json:
        _out(projects, True)
        return
    if not projects:
        console.print("[yellow]No projects found.[/yellow]")
        return
    table = Table(title="Projects")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Type")
    table.add_column("Pages", justify="right")
    for p in projects:
        table.add_row(
            p.get("id", ""),
            p.get("name", ""),
            p.get("status", ""),
            p.get("creation_type", ""),
            str(len(p.get("pages", []))),
        )
    console.print(table)


@project.command("create")
@click.option("--topic", required=True, help="Presentation topic / subject")
@click.option("--name", default=None, help="Project name (defaults to topic)")
@click.option("--style", default=None, help="Visual style description")
@click.option("--aspect-ratio", default="16:9", show_default=True, help="Slide aspect ratio")
@click.option("--type", "creation_type", default="scratch", show_default=True,
              type=click.Choice(["scratch", "ppt_renovation"]),
              help="Creation type")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def project_create(ctx, topic, name, style, aspect_ratio, creation_type, as_json):
    """Create a new project."""
    client = _make_client(ctx)
    try:
        result = proj_api.create_project(
            client,
            topic=topic,
            name=name,
            creation_type=creation_type,
            aspect_ratio=aspect_ratio,
            style=style,
        )
    except APIError as e:
        _err(str(e))
    _out(result, as_json)
    if not as_json:
        console.print(f"[green]Created project:[/green] {result.get('id')}")


@project.command("get")
@click.argument("project_id")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def project_get(ctx, project_id, as_json):
    """Get project details."""
    client = _make_client(ctx)
    try:
        result = proj_api.get_project(client, project_id)
    except APIError as e:
        _err(str(e))
    _out(result, as_json)


@project.command("delete")
@click.argument("project_id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def project_delete(ctx, project_id, yes, as_json):
    """Delete a project."""
    if not yes:
        click.confirm(f"Delete project {project_id}?", abort=True)
    client = _make_client(ctx)
    try:
        result = proj_api.delete_project(client, project_id)
    except APIError as e:
        _err(str(e))
    _out(result, as_json)
    if not as_json:
        console.print(f"[green]Deleted project:[/green] {project_id}")


@project.command("generate-outline")
@click.argument("project_id")
@click.option("--slides", default=0, help="Number of slides (0 = let AI decide)")
@click.option("--language", default="zh", show_default=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def project_generate_outline(ctx, project_id, slides, language, as_json):
    """Generate AI outline for a project (streaming)."""
    client = _make_client(ctx)
    try:
        with console.status("Generating outline…"):
            result = proj_api.generate_outline(client, project_id, slides, language)
    except APIError as e:
        _err(str(e))
    if as_json:
        _out({"output": result}, True)
    else:
        console.print("[green]Outline generated.[/green]")
        console.print(result)


@project.command("generate-descriptions")
@click.argument("project_id")
@click.option("--language", default="zh", show_default=True)
@click.option("--wait", is_flag=True, help="Wait for task to complete")
@click.option("--timeout", default=600, show_default=True, help="Wait timeout in seconds")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def project_generate_descriptions(ctx, project_id, language, wait, timeout, as_json):
    """Start bulk page description generation."""
    client = _make_client(ctx)
    try:
        result = proj_api.generate_descriptions(client, project_id, language)
    except APIError as e:
        _err(str(e))
    task_id = result.get("task_id")
    if wait and task_id:
        _wait_and_report(client, project_id, task_id, timeout, as_json)
    else:
        _out(result, as_json)
        if not as_json:
            console.print(f"[green]Task submitted:[/green] {task_id}")


@project.command("generate-images")
@click.argument("project_id")
@click.option("--language", default="zh", show_default=True)
@click.option("--wait", is_flag=True, help="Wait for task to complete")
@click.option("--timeout", default=1800, show_default=True, help="Wait timeout in seconds")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def project_generate_images(ctx, project_id, language, wait, timeout, as_json):
    """Start bulk page image generation."""
    client = _make_client(ctx)
    try:
        result = proj_api.generate_images(client, project_id, language)
    except APIError as e:
        _err(str(e))
    task_id = result.get("task_id")
    if wait and task_id:
        _wait_and_report(client, project_id, task_id, timeout, as_json)
    else:
        _out(result, as_json)
        if not as_json:
            console.print(f"[green]Task submitted:[/green] {task_id}")


# ===========================================================================
# PAGE group
# ===========================================================================

@cli.group()
def page():
    """Manage pages within a project."""


@page.command("list")
@click.argument("project_id")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_list(ctx, project_id, as_json):
    """List pages in a project."""
    client = _make_client(ctx)
    try:
        pages = page_api.list_pages(client, project_id)
    except APIError as e:
        _err(str(e))
    if as_json:
        _out(pages, True)
        return
    if not pages:
        console.print("[yellow]No pages found.[/yellow]")
        return
    table = Table(title=f"Pages — {project_id}")
    table.add_column("#", justify="right")
    table.add_column("ID", style="cyan")
    table.add_column("Status")
    table.add_column("Part")
    table.add_column("Title")
    for p in pages:
        outline = p.get("outline_content") or {}
        if isinstance(outline, str):
            try:
                import json as _json
                outline = _json.loads(outline)
            except Exception:
                outline = {}
        table.add_row(
            str(p.get("order_index", "")),
            p.get("id", ""),
            p.get("status", ""),
            p.get("part") or "",
            outline.get("title", ""),
        )
    console.print(table)


@page.command("create")
@click.argument("project_id")
@click.option("--order-index", required=True, type=int)
@click.option("--part", default=None, help="Section/part name")
@click.option("--title", default=None, help="Outline title")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_create(ctx, project_id, order_index, part, title, as_json):
    """Add a new page to a project."""
    client = _make_client(ctx)
    outline = {"title": title, "points": []} if title else None
    try:
        result = page_api.create_page(client, project_id, order_index, part, outline)
    except APIError as e:
        _err(str(e))
    _out(result, as_json)
    if not as_json:
        console.print(f"[green]Created page:[/green] {result.get('id')}")


@page.command("delete")
@click.argument("project_id")
@click.argument("page_id")
@click.option("--yes", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_delete(ctx, project_id, page_id, yes, as_json):
    """Delete a page."""
    if not yes:
        click.confirm(f"Delete page {page_id}?", abort=True)
    client = _make_client(ctx)
    try:
        result = page_api.delete_page(client, project_id, page_id)
    except APIError as e:
        _err(str(e))
    _out(result, as_json)
    if not as_json:
        console.print(f"[green]Deleted page:[/green] {page_id}")


@page.command("generate-description")
@click.argument("project_id")
@click.argument("page_id")
@click.option("--force", is_flag=True, help="Force regeneration")
@click.option("--language", default="zh", show_default=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_gen_description(ctx, project_id, page_id, force, language, as_json):
    """Generate description for a single page."""
    client = _make_client(ctx)
    try:
        with console.status("Generating description…"):
            result = page_api.generate_page_description(
                client, project_id, page_id, force, language
            )
    except APIError as e:
        _err(str(e))
    _out(result, as_json)
    if not as_json:
        console.print("[green]Description generated.[/green]")


@page.command("generate-image")
@click.argument("project_id")
@click.argument("page_id")
@click.option("--force", is_flag=True)
@click.option("--no-template", is_flag=True, help="Don't use project template image")
@click.option("--wait", is_flag=True, help="Wait for task to complete")
@click.option("--timeout", default=300, show_default=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_gen_image(ctx, project_id, page_id, force, no_template, wait, timeout, as_json):
    """Generate image for a single page (async)."""
    client = _make_client(ctx)
    try:
        result = page_api.generate_page_image(
            client, project_id, page_id, force, not no_template
        )
    except APIError as e:
        _err(str(e))
    task_id = result.get("task_id")
    if wait and task_id:
        _wait_and_report(client, project_id, task_id, timeout, as_json)
    else:
        _out(result, as_json)
        if not as_json:
            console.print(f"[green]Image task submitted:[/green] {task_id}")


@page.command("edit-image")
@click.argument("project_id")
@click.argument("page_id")
@click.option("--instruction", required=True, help="Edit instruction in natural language")
@click.option("--use-template", is_flag=True)
@click.option("--wait", is_flag=True)
@click.option("--timeout", default=300, show_default=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_edit_image(ctx, project_id, page_id, instruction, use_template, wait, timeout, as_json):
    """Edit an existing page image with a natural-language instruction (async)."""
    client = _make_client(ctx)
    try:
        result = page_api.edit_page_image(
            client, project_id, page_id, instruction, use_template
        )
    except APIError as e:
        _err(str(e))
    task_id = result.get("task_id")
    if wait and task_id:
        _wait_and_report(client, project_id, task_id, timeout, as_json)
    else:
        _out(result, as_json)
        if not as_json:
            console.print(f"[green]Edit task submitted:[/green] {task_id}")


@page.command("image-versions")
@click.argument("project_id")
@click.argument("page_id")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def page_image_versions(ctx, project_id, page_id, as_json):
    """List image versions for a page."""
    client = _make_client(ctx)
    try:
        versions = page_api.get_image_versions(client, project_id, page_id)
    except APIError as e:
        _err(str(e))
    if as_json:
        _out(versions, True)
        return
    if not versions:
        console.print("[yellow]No versions found.[/yellow]")
        return
    table = Table(title=f"Image versions — page {page_id}")
    table.add_column("Version", justify="right")
    table.add_column("ID", style="cyan")
    table.add_column("Current")
    table.add_column("Path")
    for v in versions:
        table.add_row(
            str(v.get("version_number", "")),
            v.get("id", ""),
            "✓" if v.get("is_current") else "",
            v.get("image_path", ""),
        )
    console.print(table)


# ===========================================================================
# TASK group
# ===========================================================================

@cli.group()
def task():
    """Check or wait on async task status."""


@task.command("status")
@click.argument("project_id")
@click.argument("task_id")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def task_status(ctx, project_id, task_id, as_json):
    """Get the current status of a task."""
    client = _make_client(ctx)
    try:
        result = task_api.get_task(client, project_id, task_id)
    except APIError as e:
        _err(str(e))
    _out(result, as_json)


@task.command("wait")
@click.argument("project_id")
@click.argument("task_id")
@click.option("--interval", default=2.0, show_default=True, help="Polling interval (s)")
@click.option("--timeout", default=600, show_default=True, help="Max wait time (s)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def task_wait(ctx, project_id, task_id, interval, timeout, as_json):
    """Wait for a task to complete, showing live progress."""
    client = _make_client(ctx)
    _wait_and_report(client, project_id, task_id, timeout, as_json, interval=interval)


# ===========================================================================
# EXPORT group
# ===========================================================================

@cli.group()
def export():
    """Export project slides to various formats."""


@export.command("pptx")
@click.argument("project_id")
@click.option("--filename", default=None, help="Output filename (without extension)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def export_pptx(ctx, project_id, filename, as_json):
    """Export project as PPTX and get a download URL."""
    client = _make_client(ctx)
    try:
        with console.status("Exporting PPTX…"):
            result = export_api.export_pptx(client, project_id, filename)
    except APIError as e:
        _err(str(e))
    _out(result, as_json)
    if not as_json:
        url = result.get("download_url_absolute") or result.get("download_url")
        console.print(f"[green]Download URL:[/green] {url}")


@export.command("pdf")
@click.argument("project_id")
@click.option("--filename", default=None)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def export_pdf(ctx, project_id, filename, as_json):
    """Export project as PDF and get a download URL."""
    client = _make_client(ctx)
    try:
        with console.status("Exporting PDF…"):
            result = export_api.export_pdf(client, project_id, filename)
    except APIError as e:
        _err(str(e))
    _out(result, as_json)
    if not as_json:
        url = result.get("download_url_absolute") or result.get("download_url")
        console.print(f"[green]Download URL:[/green] {url}")


@export.command("images")
@click.argument("project_id")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def export_images(ctx, project_id, as_json):
    """Export all slide images as a ZIP archive."""
    client = _make_client(ctx)
    try:
        with console.status("Exporting images…"):
            result = export_api.export_images(client, project_id)
    except APIError as e:
        _err(str(e))
    _out(result, as_json)
    if not as_json:
        url = result.get("download_url_absolute") or result.get("download_url")
        console.print(f"[green]Download URL:[/green] {url}")


@export.command("editable-pptx")
@click.argument("project_id")
@click.option("--filename", default=None)
@click.option("--depth", default=1, show_default=True, help="Recursion depth (1-5)")
@click.option("--workers", default=4, show_default=True)
@click.option("--wait", is_flag=True, help="Wait for task to complete")
@click.option("--timeout", default=3600, show_default=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def export_editable_pptx(ctx, project_id, filename, depth, workers, wait, timeout, as_json):
    """Export editable PPTX (async, uses AI element extraction)."""
    client = _make_client(ctx)
    try:
        result = export_api.export_editable_pptx(
            client, project_id, filename, max_depth=depth, max_workers=workers
        )
    except APIError as e:
        _err(str(e))
    task_id = result.get("task_id")
    if wait and task_id:
        _wait_and_report(client, project_id, task_id, timeout, as_json)
    else:
        _out(result, as_json)
        if not as_json:
            console.print(f"[green]Editable PPTX task submitted:[/green] {task_id}")


# ===========================================================================
# SETTINGS group
# ===========================================================================

@cli.group()
def settings():
    """View or update Banana Slides server settings."""


@settings.command("get")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def settings_get(ctx, as_json):
    """Get current server settings."""
    client = _make_client(ctx)
    try:
        result = settings_api.get_settings(client)
    except APIError as e:
        _err(str(e))
    _out(result, as_json)


@settings.command("update")
@click.option("--api-key", default=None, help="AI provider API key")
@click.option("--api-base", default=None, help="AI API base URL")
@click.option("--provider", default=None, help="Provider format (gemini|openai|lazyllm)")
@click.option("--text-model", default=None)
@click.option("--image-model", default=None)
@click.option("--output-language", default=None, type=click.Choice(["zh", "en", "ja", "auto"]))
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def settings_update(ctx, api_key, api_base, provider, text_model, image_model, output_language, as_json):
    """Update server settings (only provided values are changed)."""
    updates = {}
    if api_key is not None:
        updates["api_key"] = api_key
    if api_base is not None:
        updates["api_base_url"] = api_base
    if provider is not None:
        updates["ai_provider_format"] = provider
    if text_model is not None:
        updates["text_model"] = text_model
    if image_model is not None:
        updates["image_model"] = image_model
    if output_language is not None:
        updates["output_language"] = output_language
    if not updates:
        _err("No settings to update – pass at least one option.")
    client = _make_client(ctx)
    try:
        result = settings_api.update_settings(client, updates)
    except APIError as e:
        _err(str(e))
    _out(result, as_json)
    if not as_json:
        console.print("[green]Settings updated.[/green]")


# ===========================================================================
# Internal helpers
# ===========================================================================

def _wait_and_report(
    client: BananaSlidesClient,
    project_id: str,
    task_id: str,
    timeout: float,
    as_json: bool,
    interval: float = 2.0,
) -> None:
    """Poll a task, show a progress bar, and print the final result."""
    last_progress: dict = {}

    def _show_progress(task_data: dict):
        nonlocal last_progress
        progress = task_data.get("progress") or {}
        if progress != last_progress:
            total = progress.get("total", 0)
            completed = progress.get("completed", 0)
            failed = progress.get("failed", 0)
            status = task_data.get("status", "")
            if not as_json:
                console.print(
                    f"[dim]Task {task_id[:8]}…  status={status}  "
                    f"completed={completed}/{total}  failed={failed}[/dim]"
                )
            last_progress = progress

    try:
        final = task_api.wait_for_task(
            client,
            project_id,
            task_id,
            interval=interval,
            timeout=timeout,
            progress_callback=_show_progress,
        )
    except TimeoutError as e:
        _err(str(e))
    except APIError as e:
        _err(str(e))

    _out(final, as_json)
    if not as_json:
        console.print(f"[green]Task completed:[/green] {task_id}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    cli()


if __name__ == "__main__":
    main()
