#!/usr/bin/env python
"""
make_ppt_from_md.py — 把 Markdown 文件一键转成 PPT

用法：
    python make_ppt_from_md.py <markdown文件路径>
    python make_ppt_from_md.py <markdown文件路径> --slides 8 --lang zh --out 输出名
    python make_ppt_from_md.py <markdown文件路径> --url http://localhost:5000
    python make_ppt_from_md.py <markdown文件路径> --mode local
"""

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cli_anything.banana_slides.utils.config import get_mode, get_local_config


# ─── 输出 ──────────────────────────────────────────────────────────────────

def _step(n, total, msg):
    print(f"\n[{n}/{total}] {msg}", flush=True)

def _ok(msg):
    print(f"  [OK] {msg}", flush=True)

def _info(msg):
    print(f"  -- {msg}", flush=True)

def _fail(msg):
    print(f"\n[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def _progress_callback(data):
    prog = data.get("progress") or {}
    total = prog.get("total", 0)
    done = prog.get("completed", 0)
    failed = prog.get("failed", 0)
    if total:
        filled = "#" * done
        empty = "." * max(0, total - done)
        _info(f"[{filled}{empty}] {done}/{total}  failed:{failed}")


# ─── 远程模式 ──────────────────────────────────────────────────────────────

def _make_ppt_from_md_remote(
    md_path, topic, md_content, slides, lang, out, base_url, access_code,
) -> str:
    from cli_anything.banana_slides.core.client import BananaSlidesClient, APIError
    from cli_anything.banana_slides.core import task as task_api
    from export_pptx_from_descriptions import build_pptx, fetch_project_pages

    client = BananaSlidesClient(base_url, access_code, timeout=600)
    md_file = Path(md_path)
    filename = (out or md_file.stem) + ".pptx"
    total_steps = 3

    _step(1, total_steps, f"创建项目：{topic}")
    payload = {
        "name": topic[:80],
        "topic": topic,
        "creation_type": "idea",
        "idea_prompt": md_content,
        "image_aspect_ratio": "16:9",
    }
    if slides:
        payload["num_pages"] = slides
    try:
        body = client.post("/api/projects", json=payload)
        project = body.get("data", body)
    except APIError as e:
        _fail(f"创建项目失败：{e}")
    pid = project.get("id") or project.get("project_id")
    _ok(f"项目 ID：{pid}")
    _info(f"内容长度：{len(md_content)} 字")

    _step(2, total_steps, "根据文档内容生成幻灯片大纲…")
    try:
        payload2 = {"language": lang}
        if slides:
            payload2["num_pages"] = slides
        body = client.post(f"/api/projects/{pid}/generate/outline", json=payload2)
        data = body.get("data", body)
        pages = data.get("pages", [])
    except APIError as e:
        _fail(f"大纲生成失败：{e}")
    _ok(f"共生成 {len(pages)} 张幻灯片")

    _step(3, total_steps, "为每张幻灯片生成详细描述…")
    try:
        resp = client.post(
            f"/api/projects/{pid}/generate/descriptions",
            json={"language": lang},
        )
        result = resp.get("data", resp)
    except APIError as e:
        _fail(f"描述生成请求失败：{e}")
    task_id = result.get("task_id")
    if task_id:
        _info(f"任务 ID：{task_id}")
        _poll_remote(client, pid, task_id, timeout=300, label="描述")
    _ok("描述生成完成")

    _info("构建 PPTX 文件…")
    out_path = Path(filename) if Path(filename).is_absolute() else md_file.parent / filename
    try:
        all_pages = fetch_project_pages(base_url, pid)
        build_pptx(all_pages, out_path, title=topic)
    except Exception as e:
        _fail(f"构建 PPTX 失败：{e}")
    _ok("文件已生成")
    return str(out_path.absolute())


def _poll_remote(client, project_id, task_id, timeout=600, label=""):
    from cli_anything.banana_slides.core import task as task_api
    from cli_anything.banana_slides.core.client import APIError
    last = {}

    def _cb(t):
        nonlocal last
        prog = t.get("progress") or {}
        total = prog.get("total", 0)
        done = prog.get("completed", 0)
        failed = prog.get("failed", 0)
        status = t.get("status", "")
        if prog != last:
            filled = "#" * done
            empty = "." * max(0, total - done)
            _info(f"{label} {status}  [{filled}{empty}] {done}/{total}  failed:{failed}")
            last = prog

    try:
        task_api.wait_for_task(
            client, project_id, task_id,
            interval=4, timeout=timeout,
            progress_callback=_cb,
        )
    except TimeoutError:
        _fail(f"{label}任务超时（>{timeout}s）")
    except APIError as e:
        _fail(str(e))


# ─── 本地模式 ──────────────────────────────────────────────────────────────

def _make_ppt_from_md_local(
    md_path, topic, md_content, slides, lang, out,
    with_images=True, export_mode="image",
) -> str:
    from cli_anything.banana_slides.engine.local_backend import LocalBackend

    local_cfg = get_local_config()
    max_workers = local_cfg.pop("max_workers", 4)
    backend = LocalBackend(config=local_cfg, max_workers=max_workers)

    md_file = Path(md_path)
    filename = (out or md_file.stem) + ".pptx"
    total_steps = 4 if with_images else 3
    step = 0

    step += 1
    _step(step, total_steps, f"创建项目：{topic}")
    try:
        project = backend.create_project(
            topic=topic, idea_prompt=md_content,
            num_pages=slides, creation_type="idea",
        )
    except Exception as e:
        _fail(f"创建项目失败：{e}")
    pid = project["id"]
    _ok(f"项目 ID：{pid}")
    _info(f"内容长度：{len(md_content)} 字")

    step += 1
    _step(step, total_steps, "根据文档内容生成幻灯片大纲…")
    try:
        pages = backend.generate_outline(pid, num_pages=slides, language=lang)
    except Exception as e:
        _fail(f"大纲生成失败：{e}")
    _ok(f"共生成 {len(pages)} 张幻灯片")

    step += 1
    _step(step, total_steps, "为每张幻灯片生成详细描述…")
    try:
        result = backend.generate_descriptions(pid, language=lang, progress_callback=_progress_callback)
    except Exception as e:
        _fail(f"描述生成失败：{e}")
    _ok("描述生成完成")

    effective_export_mode = "text"
    if with_images:
        step += 1
        _step(step, total_steps, "为每张幻灯片生成图片（可能需要几分钟）…")
        try:
            img_result = backend.generate_images(
                pid, language=lang, progress_callback=_progress_callback,
            )
            img_done = img_result.get("completed", 0)
            img_failed = img_result.get("failed", 0)
            _ok(f"图片生成完成：成功 {img_done}，失败 {img_failed}")
            if img_done > 0:
                effective_export_mode = export_mode  # use requested mode
            else:
                _info("无图片生成成功，回退到纯文本模式")
        except Exception as e:
            _info(f"图片生成失败（{e}），回退到纯文本模式")

    if effective_export_mode == "editable":
        _info("分析幻灯片图片，提取可编辑元素…")

    _info("构建 PPTX 文件…")
    try:
        output_path = backend.export_pptx(
            pid, filename=filename, mode=effective_export_mode,
            progress_callback=_progress_callback,
        )
    except Exception as e:
        _fail(f"导出 PPTX 失败：{e}")
    _ok("文件已生成")
    return output_path


# ─── 主入口 ────────────────────────────────────────────────────────────────

def make_ppt_from_md(
    md_path: str,
    slides: int = 0,
    lang: str = "zh",
    out: str = "",
    base_url: str = "http://localhost:5000",
    access_code: str = "",
    fmt: str = "pptx",
    mode: str = "",
    with_images: bool = True,
    export_mode: str = "image",
) -> str:
    md_file = Path(md_path)
    if not md_file.exists():
        _fail(f"文件不存在：{md_path}")

    md_content = md_file.read_text(encoding="utf-8")

    # 从 markdown 中提取标题作为 topic
    topic = ""
    for line in md_content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            topic = line[2:].strip()
            break
        if line.startswith("## "):
            topic = line[3:].strip()
            break
    if not topic:
        topic = md_file.stem

    effective_mode = mode or get_mode()
    if effective_mode == "local":
        return _make_ppt_from_md_local(
            md_path, topic, md_content, slides, lang, out,
            with_images=with_images, export_mode=export_mode,
        )
    return _make_ppt_from_md_remote(
        md_path, topic, md_content, slides, lang, out, base_url, access_code,
    )


# ─── 入口 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="将 Markdown 文档一键转为 PPT")
    parser.add_argument("file", help="Markdown 文件路径")
    parser.add_argument("--slides", type=int, default=0, help="幻灯片数（0=AI 决定）")
    parser.add_argument("--lang", default="zh", choices=["zh", "en", "ja", "auto"])
    parser.add_argument("--out", default="", help="导出文件名（不含扩展名）")
    parser.add_argument("--url", default="http://localhost:5000", help="后端地址")
    parser.add_argument("--key", default="", help="访问码")
    parser.add_argument("--format", dest="fmt", default="pptx", choices=["pptx", "pdf"])
    parser.add_argument("--mode", default="", choices=["local", "remote", ""],
                        help="运行模式：local / remote（默认读取配置）")
    parser.add_argument("--no-images", action="store_true",
                        help="跳过图片生成，只生成纯文本幻灯片")
    parser.add_argument("--export-mode", default="image",
                        choices=["image", "text", "editable"],
                        help="导出模式：image（纯图片）/ text（纯文本）/ editable（可编辑）")
    args = parser.parse_args()

    md_path = Path(args.file)
    effective_mode = args.mode or get_mode()
    print("=" * 58)
    print("  [Banana Slides] Markdown 转 PPT")
    print("=" * 58)
    print(f"  输入：{md_path.name}")
    print(f"  页数：{'AI 自动决定' if args.slides == 0 else args.slides}")
    print(f"  语言：{args.lang}  格式：{args.fmt.upper()}  模式：{effective_mode}  导出：{args.export_mode}")
    print("=" * 58)

    result = make_ppt_from_md(
        md_path=str(md_path),
        slides=args.slides,
        lang=args.lang,
        out=args.out or md_path.stem,
        base_url=args.url,
        access_code=args.key,
        fmt=args.fmt,
        mode=args.mode,
        with_images=not args.no_images,
        export_mode=args.export_mode,
    )

    print("\n" + "=" * 58)
    print("  [DONE]")
    print(f"  文件路径：{result}")
    print("=" * 58)


if __name__ == "__main__":
    main()
