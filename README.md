# 工程师能力评估系统（Engineer Capability Assessment System）

[English README](README_en.md) | [中文 README](README.md)

基于 GitHub / Gitee 的 commit、diff、仓库结构与协作信号，对工程师贡献者进行 **多维度能力评估** 的工具链，包含 FastAPI 后端与可选的前端 Dashboard。
[评选标准参考](https://gitee.com/zgcai/oscanner/blob/main/engineer_level.md)

## 概览

- **后端服务**：
  - `backend/evaluator/` - 主评估服务（FastAPI，端口 8000，必需）
  - `backend/repos_runner/` - 仓库测试服务（FastAPI，端口 8001，可选）
- **前端应用**：
  - `frontend/webapp/` - Next.js Dashboard（端口 3000，必需）
  - `frontend/pages/` - GitHub Pages 静态站点（可选）
- **CLI**：`cli/`（统一命令行入口）
- **依赖管理**：推荐使用 `uv`（`pyproject.toml` + `uv.lock`）

> 📖 **详细架构说明**：请查看 [docs/01_architecture.md](docs/01_architecture.md)

## 评估标准 (Evaluation Standards)

本系统通过 **插件机制** 实现不同的评估逻辑。当前内置并默认启用的标准是 `zgc_ai_native_2026`。

### **AI-Native 2026 标准** (`zgc_ai_native_2026`)
- **文档**: [engineer_level.md](engineer_level.md)
- **适用场景**: 2026 年 AI 辅助开发时代的工程能力评估
- **评估重点**: 区分"AI 搬运工"与"系统构建者"，强调行为证据
- **四维度**:
  1. 规格实现与内建质量 (Specification & Built-in Quality)
  2. 云原生与架构演进 (Cloud-Native & Architecture Evolution)
  3. AI 工程与自动进化 (AI Engineering & Automated Evolution)
  4. 工程底座与职业操守 (Engineering Mastery & Professionalism)
- **L1-L5 行为画像**:
  - L1 (理论认知): 依赖 AI，无法鉴别代码正误
  - L2 (独立实践): 能独立完成任务，符合基本规范
  - L3 (一人全栈): 快速构建 MVP，熟练配合 AI 工具
  - L4 (团队基石): 建立质量门禁、测试体系、工程规范
  - L5 (领导者): 定义技术标准，影响开源生态
- **评分重点**:
  - 内建质量（测试/lint/重构/校验）
  - 可复现性（lockfiles/docker/一键运行）
  - 云原生就绪（CI/CD/IaC/部署配置）
  - 智能开发工作流（工具/脚本/agent 使用）
  - 专业性（文档/ADR/PR 规范/取舍说明）

### 如何选择标准？

在 Dashboard 或 API 中选择插件 ID 即可切换评估标准；未指定时使用 `zgc_ai_native_2026`。合并评估、导出和对比视图会根据插件实际输出的数字分数动态生成维度，不再依赖固定维度键。

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

**重要**：除了大模型 Token，强烈建议设置 GitHub Token 和 Gitee Token，以避免被 API 限流：

```bash
# 在 .env.local 中添加（可选但强烈推荐）
# 不设置 token：GitHub ~60 次/小时，Gitee 较低限制
# 设置 token：GitHub ~5000 次/小时，Gitee 较高限制
GITHUB_TOKEN=ghp_your-token-here
GITEE_TOKEN=your-gitee-token-here
```

如果你需要无交互/CI 场景，可以用 `--non-interactive` 配合参数写入（示例）：

```bash
uv run oscanner init \
  --provider openai \
  --base-url https://api.siliconflow.cn/v1 \
  --api-key sk-your-key-here \
  --model deepseek/deepseek-v4-pro \
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
- **Dashboard（dev）**：`http://localhost:3000/`
- **API（dev）**：`http://localhost:8000`

> 说明（很重要）：在开发模式下，前端（3000）和后端（8000）是两个不同的 origin。
> CLI 会自动注入 `NEXT_PUBLIC_API_SERVER_URL=http://localhost:8000`，让前端请求正确打到后端；
> 而在 **PyPI 发布后的包** 中，Dashboard 静态文件由后端同源挂载在 `http://localhost:8000/`，此时前端默认同源请求（不设置 `NEXT_PUBLIC_API_SERVER_URL`）才是期望行为。

如果你是通过 PyPI 安装运行（本地没有 `frontend/webapp/` 目录），可以用：

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

## 运行测试

项目使用 `pytest` 进行单元测试。推荐使用 `uv run pytest` 来运行测试，以确保使用正确的虚拟环境。

### 运行所有测试

```bash
uv run pytest
```

### 运行特定测试文件

```bash
# 运行 Gitee API 提取相关测试
uv run pytest tests/gitee_api/test_extraction.py -v

# 运行所有测试并显示详细信息
uv run pytest -v
```

### 运行特定测试类或测试方法

```bash
# 运行特定测试类
uv run pytest tests/gitee_api/test_extraction.py::TestDNSResolution

# 运行特定测试方法
uv run pytest tests/gitee_api/test_extraction.py::TestDNSResolution::test_dns_resolution_success
```

### 运行测试并生成覆盖率报告

```bash
uv run pytest --cov=evaluator --cov-report=html
```

更多测试相关信息请参阅 [tests/README.md](tests/README.md)。

## 数据落盘位置（默认策略）

为了保证 **pip 安装后在任意目录运行都不会把数据写到当前工作目录**，本仓库已改为默认写入用户目录，并支持环境变量覆盖：

- **OSCANNER_HOME**：统一根目录（最高优先级）
- **OSCANNER_DATA_DIR**：抽取数据目录

默认值（未设置 env 时）：
- data：`~/.local/share/oscanner/data`（或 `XDG_DATA_HOME/oscanner/data`）
- runner repos：`~/.local/share/oscanner/repos/{platform}/{owner}/{repo}/{ref}/source`

## Commit Email Identities（提交邮箱身份）

### 功能说明

Oscanner 现在以 commit email 作为贡献者评估身份。同一个工程师可能在不同仓库或不同时间使用多个邮箱，例如 `alice@example.com` 和 `alice@work.com`。Dashboard 和 API 都支持一次提交多个邮箱，并在合并结果时按各邮箱对应的 commit 数量加权。

前端会在发送请求前校验邮箱格式；后端也会拒绝格式不合法的 `emails` / `author_emails` 输入。

### 使用方式

#### 1. 单仓库模式

选择贡献者后，系统优先使用该贡献者的 commit email。也可以在 Dashboard 的 "Author Emails" 输入框中填写多个邮箱（逗号或换行分隔）：

```text
alice@example.com, alice@work.com
```

系统会分别评估每个邮箱身份，统计每个身份命中的 commit 数量，并调用 `/api/merge-evaluations` 合并为一个报告。合并分数根据插件实际输出的数字维度动态计算，不依赖固定维度名称。

#### 2. 多仓库模式

多仓库分析会把 `author_emails` 传给 Common Contributors 和 Compare Contributor 接口。跨仓库对比时，系统会聚合这些邮箱对应的 commits，并返回插件实际维度：

```json
{
  "dimension_keys": ["spec_quality", "cloud_architecture", "ai_engineering", "mastery_professionalism"],
  "dimension_names": ["Specification & Built-in Quality", "Cloud-Native & Architecture Evolution", "AI Engineering & Automated Evolution", "Engineering Mastery & Professionalism"]
}
```

### API 端点

##### `/api/evaluate/{owner}/{repo}/{identity}` (POST)

路径里的 `identity` 建议使用 URL 编码后的主邮箱；Body 中使用 `emails` 提供一个或多个邮箱：

```json
{
  "emails": ["alice@example.com", "alice@work.com"]
}
```

##### `/api/merge-evaluations` (POST)

```json
{
  "evaluations": [
    {
      "identity": "alice@example.com",
      "weight": 42,
      "evaluation": { "scores": { "spec_quality": 82 } }
    },
    {
      "identity": "alice@work.com",
      "weight": 8,
      "evaluation": { "scores": { "spec_quality": 74 } }
    }
  ],
  "model": "openai/gpt-4o"
}
```

合并服务会动态读取各评估结果中的数字分数键，跳过 `reasoning` 等非数字字段，并按 `weight` 加权平均。

##### `/api/batch/common-contributors` (POST)

```json
{
  "repos": [
    { "owner": "facebook", "repo": "react", "platform": "github" },
    { "owner": "vercel", "repo": "next.js", "platform": "github" }
  ],
  "author_emails": ["alice@example.com", "alice@work.com"]
}
```

##### `/api/batch/compare-contributor` (POST)

```json
{
  "contributor": "alice@example.com",
  "repos": [
    { "owner": "owner", "repo": "repo1", "platform": "github" },
    { "owner": "owner", "repo": "repo2", "platform": "gitee" }
  ],
  "author_emails": ["alice@example.com", "alice@work.com"],
  "plugin": "zgc_ai_native_2026"
}
```

### 最佳实践

1. **优先使用 commit email**：不要依赖 commit author name 作为主要身份。
2. **一次填入同一人的全部邮箱**：例如个人邮箱、公司邮箱和 GitHub noreply 邮箱。
3. **保持跨仓库一致**：单仓库评估、多仓库 Common Contributors 和对比分析使用同一组邮箱。
4. **利用缓存**：每个邮箱身份可独立缓存；只有新增或变更的邮箱身份需要重新评估。

## 项目结构

```
.
├── pyproject.toml              # uv/packaging 元信息
├── backend/                    # 后端服务目录
│   ├── evaluator/              # 主评估服务（端口 8000，必需）
│   └── repos_runner/           # 仓库测试服务（端口 8001，可选）
├── frontend/                   # 前端应用目录
│   ├── webapp/                 # Next.js Dashboard（端口 3000，必需）
│   └── pages/                  # GitHub Pages 静态站点（可选）
├── cli/                        # CLI 工具（可安装包）
├── plugins/                    # 插件系统
├── scripts/                    # 工具脚本
├── tests/                      # 测试目录
└── docs/                       # 文档目录
```

> 📖 **详细架构说明**：请查看 [docs/01_architecture.md](docs/01_architecture.md)

## 贡献指南

我们推荐通过 Gitee 自动生成 PR 的方式进行贡献。详细信息请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

**快速开始：**
1. 在 Gitee 上创建或选择一个 issue
2. 在 main 分支上直接开发
3. 提交时在 commit message 中引用 issue：`fix #issue_number` 或 `关闭 #issue_number`
4. 推送后会自动生成 PR 并关联到 issue
