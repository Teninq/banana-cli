#!/usr/bin/env python
"""
make_ppt.py — 一键生成 PPT

用法：
    python make_ppt.py --topic "气候变化与新能源" --slides 8 --lang zh
    python make_ppt.py --topic "AI in Healthcare" --slides 6 --lang en --out my_deck
    python make_ppt.py --topic "..." --url http://localhost:5000 --key sk-xxx
    python make_ppt.py --topic "..." --mode local   (使用本地 AI 管道)

参数说明：
    --topic     幻灯片主题（必填）
    --slides    页数，0 = AI 自动决定（默认 0）
    --lang      输出语言：zh / en / ja / auto（默认 zh）
    --style     视觉风格描述（可选）
    --out       导出文件名（不含扩展名，默认用主题）
    --url       banana-slides 后端地址（默认 http://localhost:5000）
    --key       API 访问码（服务端设置了 ACCESS_CODE 才需要）
    --format    导出格式：pptx / pdf（默认 pptx）
    --mode      运行模式：local（本地 AI）/ remote（远程服务器，默认）
"""

import argparse
import json
import sys
import time
from pathlib import Path

# 允许不安装直接运行
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cli_anything.banana_slides.utils.config import get_mode, get_local_config, load_config


# ─── 彩色输出 ──────────────────────────────────────────────────────────────

def _step(n: int, msg: str):
    print(f"\n[{n}/5] {msg}", flush=True)

def _ok(msg: str):
    print(f"  ✓ {msg}", flush=True)

def _info(msg: str):
    print(f"  · {msg}", flush=True)

def _fail(msg: str):
    print(f"\n✗ 失败：{msg}", file=sys.stderr)
    sys.exit(1)


# ─── 进度回调 ──────────────────────────────────────────────────────────────

def _progress_callback(data):
    prog = data.get("progress") or {}
    total = prog.get("total", 0)
    done = prog.get("completed", 0)
    failed = prog.get("failed", 0)
    if total:
        bar = f"[{'█' * done}{'░' * max(0, total - done)}]"
        _info(f"{done}/{total} {bar}  失败:{failed}")


# ─── 远程模式 ──────────────────────────────────────────────────────────────

def _make_ppt_remote(
    topic, slides, lang, style, out, base_url, access_code, fmt,
) -> str:
    from cli_anything.banana_slides.core.client import BananaSlidesClient, APIError
    from cli_anything.banana_slides.core import project as proj_api
    from cli_anything.banana_slides.core import page as page_api
    from cli_anything.banana_slides.core import task as task_api
    from cli_anything.banana_slides.core import export as export_api

    client = BananaSlidesClient(base_url, access_code, timeout=600)
    filename = out or topic[:40].replace(" ", "_")

    _step(1, f"创建项目：{topic}")
    try:
        project = proj_api.create_project(
            client, topic=topic, style=style or None, aspect_ratio="16:9",
        )
    except APIError as e:
        _fail(f"创建项目失败：{e}")
    pid = project["id"]
    _ok(f"项目 ID：{pid}")

    _step(2, "生成幻灯片大纲…")
    try:
        proj_api.generate_outline(client, pid, num_pages=slides, language=lang)
    except Exception as e:
        _info(f"大纲流式响应：{e}（继续）")
    for _ in range(10):
        pages = page_api.list_pages(client, pid)
        if pages:
            break
        time.sleep(2)
    else:
        _fail("大纲生成后未找到页面，请检查服务器日志")
    _ok(f"共 {len(pages)} 张幻灯片")

    _step(3, "为每张幻灯片生成文字描述…")
    try:
        result = proj_api.generate_descriptions(client, pid, language=lang)
    except APIError as e:
        _fail(f"描述生成请求失败：{e}")
    task_id = result.get("task_id")
    if task_id:
        _info(f"任务 ID：{task_id}，等待完成…")
        _poll_task(client, pid, task_id, timeout=300)
    _ok("描述生成完成")

    _step(4, "为每张幻灯片生成图片（这步最耗时）…")
    try:
        result = proj_api.generate_images(client, pid, language=lang)
    except APIError as e:
        _fail(f"图片生成请求失败：{e}")
    task_id = result.get("task_id")
    if task_id:
        _info(f"任务 ID：{task_id}，等待完成（可能需要 5-15 分钟）…")
        _poll_task(client, pid, task_id, timeout=3600)
    _ok("图片生成完成")

    _step(5, f"导出 {fmt.upper()}…")
    try:
        if fmt == "pdf":
            data = export_api.export_pdf(client, pid, filename=filename)
        else:
            data = export_api.export_pptx(client, pid, filename=filename)
    except APIError as e:
        _fail(f"导出失败：{e}")

    url = data.get("download_url_absolute") or data.get("download_url", "")
    _ok("导出成功！")
    return url


def _poll_task(client, project_id, task_id, timeout=600):
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
            bar = f"[{'█' * done}{'░' * max(0, total - done)}]" if total else ""
            _info(f"{status}  {done}/{total} {bar}  失败:{failed}")
            last = prog

    try:
        task_api.wait_for_task(
            client, project_id, task_id,
            interval=4, timeout=timeout,
            progress_callback=_cb,
        )
    except TimeoutError:
        _fail(f"任务超时（>{timeout}s）")
    except APIError as e:
        _fail(str(e))


# ─── 本地模式 ──────────────────────────────────────────────────────────────

def _make_ppt_local(
    topic, slides, lang, style, out, fmt, export_mode="image",
) -> str:
    from cli_anything.banana_slides.engine.local_backend import LocalBackend

    local_cfg = get_local_config()
    max_workers = local_cfg.pop("max_workers", 4)
    backend = LocalBackend(config=local_cfg, max_workers=max_workers)
    filename = out or topic[:40].replace(" ", "_")

    _step(1, f"创建项目：{topic}")
    try:
        project = backend.create_project(
            topic=topic, style=style or "", aspect_ratio="16:9",
            num_pages=slides,
        )
    except Exception as e:
        _fail(f"创建项目失败：{e}")
    pid = project["id"]
    _ok(f"项目 ID：{pid}")

    _step(2, "生成幻灯片大纲…")
    try:
        pages = backend.generate_outline(pid, num_pages=slides, language=lang)
    except Exception as e:
        _fail(f"大纲生成失败：{e}")
    _ok(f"共 {len(pages)} 张幻灯片")

    _step(3, "为每张幻灯片生成文字描述…")
    try:
        result = backend.generate_descriptions(pid, language=lang, progress_callback=_progress_callback)
    except Exception as e:
        _fail(f"描述生成失败：{e}")
    _ok("描述生成完成")

    _step(4, "为每张幻灯片生成图片（这步最耗时）…")
    try:
        result = backend.generate_images(pid, language=lang, progress_callback=_progress_callback)
    except Exception as e:
        _fail(f"图片生成失败：{e}")
    completed = result.get("completed", 0)
    failed = result.get("failed", 0)
    _ok(f"图片生成完成（成功:{completed} 失败:{failed}）")

    _step(5, f"导出 {fmt.upper()}（{export_mode} 模式）…")
    try:
        output_path = backend.export_pptx(
            pid, filename=filename, mode=export_mode,
            progress_callback=_progress_callback,
        )
    except Exception as e:
        _fail(f"导出失败：{e}")
    _ok("导出成功！")
    return output_path


# ─── 核心入口 ──────────────────────────────────────────────────────────────

def make_ppt(
    topic: str,
    slides: int = 0,
    lang: str = "zh",
    style: str = "",
    out: str = "",
    base_url: str = "http://localhost:5000",
    access_code: str = "",
    fmt: str = "pptx",
    mode: str = "",
    export_mode: str = "image",
) -> str:
    """
    完整生成流程：创建项目 → 生成大纲 → 生成描述 → 生成图片 → 导出。
    mode='local' 使用本地 AI，mode='remote' 使用远程 HTTP API。
    export_mode: 'image' | 'text' | 'editable'
    """
    effective_mode = mode or get_mode()
    if effective_mode == "local":
        return _make_ppt_local(topic, slides, lang, style, out, fmt,
                               export_mode=export_mode)
    return _make_ppt_remote(topic, slides, lang, style, out, base_url, access_code, fmt)


# ─── CLI 入口 ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="一键生成 Banana Slides PPT")
    parser.add_argument("--topic", required=True, help="幻灯片主题")
    parser.add_argument("--slides", type=int, default=0, help="页数（0=AI决定）")
    parser.add_argument("--lang", default="zh", choices=["zh", "en", "ja", "auto"])
    parser.add_argument("--style", default="", help="视觉风格描述")
    parser.add_argument("--out", default="", help="导出文件名（不含扩展名）")
    parser.add_argument("--url", default="http://localhost:5000", help="服务器地址")
    parser.add_argument("--key", default="", help="访问码（ACCESS_CODE）")
    parser.add_argument("--format", dest="fmt", default="pptx", choices=["pptx", "pdf"])
    parser.add_argument("--mode", default="", choices=["local", "remote", ""],
                        help="运行模式：local / remote（默认读取配置）")
    parser.add_argument("--export-mode", default="image",
                        choices=["image", "text", "editable"],
                        help="导出模式：image（纯图片）/ text（纯文本）/ editable（可编辑）")
    args = parser.parse_args()

    effective_mode = args.mode or get_mode()

    print("=" * 55)
    print("  Banana Slides 一键生成 PPT")
    print("=" * 55)
    print(f"  主题：{args.topic}")
    print(f"  页数：{'AI决定' if args.slides == 0 else args.slides}")
    print(f"  语言：{args.lang}  格式：{args.fmt.upper()}  模式：{effective_mode}  导出：{args.export_mode}")
    print("=" * 55)

    result = make_ppt(
        topic=args.topic,
        slides=args.slides,
        lang=args.lang,
        style=args.style,
        out=args.out,
        base_url=args.url,
        access_code=args.key,
        fmt=args.fmt,
        mode=args.mode,
        export_mode=args.export_mode,
    )

    print("\n" + "=" * 55)
    if effective_mode == "local":
        print("  Done!")
        print(f"  文件路径：{result}")
    else:
        print("  Done! 下载地址：")
        print(f"  {result}")
    print("=" * 55)


if __name__ == "__main__":
    main()
