# Banana Slides Agent Harness

CLI 工具集，用于驱动 [Banana Slides](http://localhost:5000) AI 幻灯片生成后端。支持一键生成 PPT、从 Markdown 转 PPT、以及细粒度 CLI 操作。

## 前置条件

- Python >= 3.9
- Banana Slides 后端运行在 `http://localhost:5000`（或自定义地址）
- 如需本地构建 PPTX，需额外安装 `python-pptx`

## 安装

```bash
pip install -e .
```

这会安装 `cli-anything-banana-slides` 命令行工具及其依赖（click、requests、rich）。

## 快速开始

### 1. 一键生成 PPT（推荐）

```bash
python make_ppt.py --topic "气候变化与新能源" --slides 8 --lang zh
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

流程：创建项目 → 生成大纲 → 生成描述 → 生成图片 → 导出文件。

### 2. Markdown 转 PPT

```bash
python make_ppt_from_md.py my_document.md --lang zh
```

从 Markdown 文件提取内容，AI 自动生成大纲和描述，再用 `python-pptx` 本地构建 PPTX（跳过图片生成，速度更快）。

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
    ├── core/
    │   ├── client.py                # HTTP 客户端封装
    │   ├── project.py               # 项目 API
    │   ├── page.py                  # 页面 API
    │   ├── task.py                  # 异步任务轮询
    │   ├── export.py                # 导出 API
    │   └── settings.py              # 设置 API
    ├── utils/
    │   └── config.py                # 配置管理
    └── tests/
        ├── test_core.py             # 核心模块测试
        └── test_full_e2e.py         # 端到端测试
```

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
