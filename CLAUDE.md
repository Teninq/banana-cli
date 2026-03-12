# Banana Slides Agent Harness

## 项目概述

CLI 驱动的 AI 幻灯片生成工具，围绕 Banana Slides Flask 后端 API 构建。

## 技术栈

- Python 3.9+
- click（CLI 框架）
- requests（HTTP 客户端）
- rich（终端美化）
- python-pptx（本地 PPTX 构建）

## 架构

```
make_ppt.py / make_ppt_from_md.py   ← 一键入口脚本
        ↓
cli_anything/banana_slides/core/    ← API 封装层
  client.py   → HTTP 请求基础
  project.py  → 项目 CRUD + 生成操作
  page.py     → 页面 CRUD
  task.py     → 异步任务轮询
  export.py   → 导出 API
        ↓
Banana Slides Flask 后端 (localhost:5000)
```

## 开发约定

- 后端 API 基础地址默认 `http://localhost:5000`，所有 API 路径以 `/api/` 开头
- 异步操作返回 `task_id`，通过 `task.wait_for_task()` 轮询；轮询间隔 4 秒
- `client.py` 中的 `BananaSlidesClient` 封装了认证头（`X-Access-Code`）和超时
- 脚本同时支持 `pip install -e .` 安装后使用，也支持直接 `python make_ppt.py` 运行（通过 `sys.path` 注入）
- 文件使用 UTF-8 编码读写

## 关键文件

| 文件 | 用途 |
|------|------|
| `make_ppt.py` | 一键生成（主题→大纲→描述→图片→导出） |
| `make_ppt_from_md.py` | Markdown→大纲→描述→本地 PPTX |
| `export_pptx_from_descriptions.py` | 已有项目→本地纯文字 PPTX |
| `cli_anything/banana_slides/banana_slides_cli.py` | Click CLI 入口 |
| `BANANA-SLIDES.md` | API 端点参考文档 |

## 常用命令

```bash
# 安装
pip install -e .

# 一键生成
python make_ppt.py --topic "主题" --lang zh

# Markdown 转 PPT
python make_ppt_from_md.py doc.md

# 运行测试
python -m pytest cli_anything/banana_slides/tests/
```

## 注意事项

- Windows 环境，使用 `python` 而非 `python3`
- 图片生成耗时较长（5-15 分钟），超时设为 3600 秒
- `export_pptx_from_descriptions.py` 生成深色主题 PPTX（深蓝背景 + 白色文字）
- 页面状态流：DRAFT → OUTLINE_GENERATED → DESCRIPTION_GENERATED → IMAGE_GENERATED
