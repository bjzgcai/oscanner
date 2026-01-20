# 工程师能力评估系统（Engineer Capability Assessment System）

[English README](README_en.md) | [中文 README](README.md)

基于 GitHub / Gitee 的 commit、diff、仓库结构与协作信号，对工程师贡献者进行**六维能力评估（0-100）**的工具链，包含 FastAPI 后端与可选的前端 Dashboard。

## 概览

- **后端**：`evaluator/`（FastAPI + 数据抽取 + LLM 评估 + 缓存）
- **前端（可选）**：`webapp/`（Next.js Dashboard）
- **CLI**：`oscanner`（统一命令行入口）
- **依赖管理**：推荐使用 `uv`（`pyproject.toml` + `uv.lock`）

## 快速开始

TODO: 增加 uv 和 npm 的安装说明

### 1) 安装依赖（推荐 uv）

本仓库使用 `pyproject.toml`：

```bash
# 首次使用（仓库没有提交 uv.lock 时）需要先生成 lock
uv lock

# 然后再同步依赖（创建/更新 .venv）
uv sync

# 如果你只是想快速跑起来、且不想生成/使用 lock：
# uv sync --no-lock
```

### 2) 配置环境变量

推荐直接用 CLI 交互式初始化（会生成/更新 `.env.local`；如已存在会提示你选择复用/合并/覆盖）：

```bash
uv run oscanner init
```

如果你需要无交互/CI 场景，可以用 `--non-interactive` 配合参数写入（示例）：

```bash
uv run oscanner init \
  --provider openai \
  --base-url https://api.siliconflow.cn/v1 \
  --api-key sk-your-key-here \
  --model Pro/zai-org/GLM-4.7 \
  --action overwrite \
  --non-interactive
```

> 说明：OpenAI-compatible 会默认请求 `.../chat/completions`；如服务商路径不标准，可在 `oscanner init` 里设置 `--chat-completions-url`（或对应环境变量）。

### 3) 启动后端 API

开发模式（自动 reload）：

```bash
uv run oscanner serve --reload
```

默认地址：
- **API**：`http://localhost:8000`
- **API Docs**：`http://localhost:8000/docs`

### 4) 启动 Dashboard（可选）

Dashboard 是独立的前端工程，不作为 pip 安装强依赖：

```bash
# 仅启动前端（会在需要时自动提示/安装依赖）
uv run oscanner dashboard --install

# 一键启动：后端 + 前端（开发模式）
uv run oscanner dev --reload --install
```

默认地址：
- **Dashboard**：`http://localhost:3000`

如果你是通过 PyPI 安装运行（本地没有 `webapp/` 目录），可以用：

```bash
oscanner dashboard --print
```

查看启动指引（需要 clone 仓库才能运行前端）。

## CLI 使用

### 启动服务

```bash
uv run oscanner serve --reload
```

### 启动前端 Dashboard

```bash
uv run oscanner dashboard --install
```

### 一键启动后端 + 前端

```bash
uv run oscanner dev --reload --install
```

### 抽取仓库数据（moderate：diff + file context）

```bash
uv run oscanner extract https://github.com/<owner>/<repo> --out /path/to/output --max-commits 500
```

> 说明：后端在需要时也会自动触发抽取（见 API 的 `/api/authors/{owner}/{repo}`）。

## 数据/缓存落盘位置（默认策略）

为了保证 **pip 安装后在任意目录运行都不会把数据写到当前工作目录**，本仓库已改为默认写入用户目录，并支持环境变量覆盖：

- **OSCANNER_HOME**：统一根目录（最高优先级）
- **OSCANNER_DATA_DIR**：抽取数据目录
- **OSCANNER_CACHE_DIR**：请求/中间缓存目录
- **OSCANNER_EVAL_CACHE_DIR**：评估缓存目录

默认值（未设置 env 时）：
- data：`~/.local/share/oscanner/data`（或 `XDG_DATA_HOME/oscanner/data`）
- cache：`~/.cache/oscanner/cache`（或 `XDG_CACHE_HOME/oscanner/cache`）
- evaluations：`~/.local/share/oscanner/evaluations/cache`

## 项目结构（简版）

```
.
├── pyproject.toml              # uv/packaging 元信息
├── evaluator/                  # 后端实现
├── oscanner/                   # CLI（oscanner）
└── webapp/                     # 可选 Dashboard（Next.js）
```

## 贡献指南

我们推荐通过 Gitee 自动生成 PR 的方式进行贡献。详细信息请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

**快速开始：**
1. 在 Gitee 上创建或选择一个 issue
2. 在 main 分支上直接开发
3. 提交时在 commit message 中引用 issue：`fix #issue_number` 或 `关闭 #issue_number`
4. 推送后会自动生成 PR 并关联到 issue


