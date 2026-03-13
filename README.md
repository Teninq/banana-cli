# Banana Slides Agent Harness

CLI 工具集，用于驱动 [Banana Slides](http://localhost:5000) AI 幻灯片生成后端。支持一键生成 PPT、从 Markdown 转 PPT、以及细粒度 CLI 操作。

## 前置条件

- Python >= 3.9
- **远程模式**：Banana Slides 后端运行在 `http://localhost:5000`（或自定义地址）
- **本地模式**：配置 AI API 密钥（OpenAI 兼容 或 Google Gemini）
- 如需本地构建 PPTX，需额外安装 `python-pptx`、`Pillow`

## 安装

```bash
pip install -e .
```

这会安装 `cli-anything-banana-slides` 命令行工具及其依赖（click、requests、rich）。

## 快速开始

### 1. 一键生成 PPT（推荐）

```bash
# 远程模式（默认）
python make_ppt.py --topic "气候变化与新能源" --slides 8 --lang zh

# 本地模式 + 可编辑导出
python make_ppt.py --topic "AI in Healthcare" --mode local --export-mode editable
```

参数说明：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--topic` | 幻灯片主题（必填） | - |
| `--slides` | 页数，0 表示 AI 自动决定 | `0` |
| `--lang` | 输出语言：zh / en / ja / auto | `zh` |
| `--style` | 视觉风格描述 | 空 |
| `--out` | 导出文件名（不含扩展名） | 主题名 |
| `--url` | 后端地址 | `http://localhost:5000` |
| `--key` | 访问码（服务端 ACCESS_CODE） | 空 |
| `--format` | 导出格式：pptx / pdf | `pptx` |
| `--mode` | 运行模式：local / remote | 配置文件 |
| `--export-mode` | 导出模式：image / text / editable | `image` |

流程：创建项目 → 生成大纲 → 生成描述 → 生成图片 → 导出文件。

### 2. Markdown 转 PPT

```bash
python make_ppt_from_md.py my_document.md --lang zh
python make_ppt_from_md.py my_document.md --mode local --export-mode editable
```

从 Markdown 文件提取内容，AI 自动生成大纲和描述。支持 `--export-mode` 参数选择导出模式。

参数与 `make_ppt.py` 类似，第一个位置参数为 Markdown 文件路径。

### 3. 从已有项目导出纯文字 PPTX

```bash
python export_pptx_from_descriptions.py <project_id> --title "标题" --out output.pptx
```

对已完成描述生成的项目，直接在本地构建深色风格的纯文字 PPTX。

### 4. CLI 细粒度操作

```bash
# 创建项目
cli-anything-banana-slides project create --topic "AI in Healthcare"

# 生成大纲
cli-anything-banana-slides project generate-outline <project_id>

# 生成描述（异步，--wait 等待完成）
cli-anything-banana-slides project generate-descriptions <project_id> --wait

# 生成图片（异步）
cli-anything-banana-slides project generate-images <project_id> --wait

# 导出
cli-anything-banana-slides export pptx <project_id> --filename my_deck

# 等待任务完成
cli-anything-banana-slides task wait <task_id>
```

## 项目结构

```
agent-harness/
├── make_ppt.py                      # 一键生成脚本（主题 → PPT）
├── make_ppt_from_md.py              # Markdown → PPT
├── export_pptx_from_descriptions.py # 本地 PPTX 构建（纯文字）
├── setup.py                         # 包安装配置
├── BANANA-SLIDES.md                 # API 参考文档
└── cli_anything/banana_slides/
    ├── banana_slides_cli.py         # Click CLI 入口
    ├── core/                        # 远程 HTTP API 层
    │   ├── client.py                # HTTP 客户端封装
    │   ├── project.py               # 项目 API
    │   ├── page.py                  # 页面 API
    │   ├── task.py                  # 异步任务轮询
    │   ├── export.py                # 导出 API
    │   └── settings.py              # 设置 API
    ├── engine/                      # 本地 AI 引擎
    │   ├── local_backend.py         # LocalBackend（SlidesBackend 实现）
    │   ├── ai_service.py            # AI 编排（大纲/描述/图片）
    │   ├── export.py                # PPTX 导出（text/image/editable）
    │   ├── pptx_builder.py          # 可编辑 PPTX 构建器
    │   ├── image_analyzer.py        # AI 视觉分析（提取可编辑元素）
    │   ├── local_store.py           # JSON 文件存储
    │   ├── prompts.py               # LLM 提示词模板
    │   └── ai_providers/            # 可插拔 AI 提供商
    │       ├── text/                # 文本生成（GenAI/OpenAI，含视觉）
    │       └── image/               # 图片生成（GenAI/OpenAI）
    ├── utils/
    │   └── config.py                # 配置管理
    └── tests/
        ├── test_core.py             # 核心模块测试
        └── test_full_e2e.py         # 端到端测试
```

## 导出模式

| 模式 | 说明 | 文字可编辑 | 需要图片 |
|------|------|:---:|:---:|
| `image` | 每页一张全尺寸 PNG | ✗ | ✓ |
| `text` | 深色主题纯文字幻灯片 | ✓ | ✗ |
| `editable` | 原图背景 + AI 提取的可编辑文字覆盖层 | ✓ | ✓ |

`editable` 模式的工作原理：
1. 用 AI 视觉模型分析每张幻灯片图片，提取文字元素的位置、内容和样式
2. 以原图作为全尺寸背景
3. 在文字区域放置与背景色匹配的不透明矩形遮盖原始文字
4. 在矩形上方放置可编辑的文本框

## 工作流说明

Banana Slides 的页面经历三个阶段：

1. **大纲（Outline）** — AI 生成标题和要点
2. **描述（Description）** — AI 生成详细文字描述（用于图片生成提示词）
3. **图片（Image）** — AI 生成幻灯片图片

其中描述生成和图片生成是异步任务，通过 Task 系统提交后轮询等待完成。

## 环境变量

| 变量 | 说明 |
|------|------|
| `BANANA_SLIDES_URL` | 后端地址（可用 `--url` 覆盖） |
| `ACCESS_CODE` | 服务端访问码（可用 `--key` 覆盖） |
