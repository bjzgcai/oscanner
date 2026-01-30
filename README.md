# 工程师能力评估系统（Engineer Capability Assessment System）

[English README](README_en.md) | [中文 README](README.md)

基于 GitHub / Gitee 的 commit、diff、仓库结构与协作信号，对工程师贡献者进行 **多维度能力评估** 的工具链，包含 FastAPI 后端与可选的前端 Dashboard。
[评选标准参考](http://https://gitee.com/zgcai/oscanner/blob/main/engineer_level.md)

## 概览

- **后端**：`evaluator/`（FastAPI + 数据抽取 + LLM 评估 + 缓存）
- **前端（可选）**：`webapp/`（Next.js Dashboard）
- **CLI**：`oscanner`（统一命令行入口）
- **依赖管理**：推荐使用 `uv`（`pyproject.toml` + `uv.lock`）

## 评估标准 (Evaluation Standards)

本系统支持两套评估标准，通过 **插件机制** 实现不同的评估逻辑：

### 1. **传统六维度标准** (`zgc_simple`)
- **文档**: [engineer_level_old.md](engineer_level_old.md)
- **适用场景**: 传统软件工程能力评估
- **评估重点**: 技术广度和深度，基于量化指标（提交数、代码行数等）
- **评分方式**: 基础的关键词和模式匹配，适合快速评估
- **六维度**:
  1. AI 模型全栈开发 (AI Model Full-Stack Development)
  2. AI 原生架构设计 (AI Native Architecture Design)
  3. 云原生工程 (Cloud Native Engineering)
  4. 开源协作 (Open Source Collaboration)
  5. 智能开发 (Intelligent Development)
  6. 工程领导力 (Engineering Leadership)

### 2. **AI-Native 2026 标准** (`zgc_ai_native_2026`)
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

在 Dashboard 中，可以通过选择不同的插件来使用不同的评估标准：
- 使用 `zgc_simple` 插件 → 传统六维度评估
- 使用 `zgc_ai_native_2026` 插件 → AI-Native 2026 四维度评估

两种标准输出不同数量的维度分数，采用不同的评估标准和侧重点。

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
  --model qwen/qwen3-coder-flash \
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
- track：`~/.local/share/oscanner/track/cache`

## Author Aliases (作者别名) - 跨名称贡献聚合

### 功能说明

同一个工程师可能在不同的 commit 中使用不同的名称（如 "CarterWu"、"wu-yanbiao"、"吴炎标"等）。**Author Aliases** 功能可以将这些不同名称的贡献聚合到一起进行统一评估。

> **注意**：评估缓存文件名采用小写规范化（如 `CarterWu` / `carterwu` / `CARTERWU` 均使用 `carterwu.json`），确保不同大小写请求都能复用缓存。

### 使用方式

#### 1. **单仓库模式（Single Repo）**

在 Dashboard 的 "Author Aliases" 输入框中填入多个名称（逗号分隔）：

```
CarterWu, wu-yanbiao, 吴炎标
```

然后点击任意一个匹配的作者头像，系统会：

1. **分别评估每个名称**：
   - CarterWu (42 commits) → 评估结果 1
   - wu-yanbiao (3 commits) → 评估结果 2
   - 吴炎标 (5 commits) → 评估结果 3

2. **使用 LLM 合并分析**：
   - 根据 commit 数量计算权重：[42, 3, 5]
   - 对六维能力分数进行加权平均
   - 调用 `/api/merge-evaluations` 接口，使用 LLM 综合生成统一的分析总结

3. **展示合并结果**：
   - `.eval-header` 显示所有别名："CarterWu, wu-yanbiao, 吴炎标"
   - `.chart-container` 显示加权平均后的六维分数
   - `.reasoning-section` 显示 LLM 生成的综合分析

#### 2. **多仓库模式（Multi Repo）**

在分析多个仓库时，填入 Author Aliases 后：

- **Common Contributors** 表格会自动识别并分组同一个人的不同名称
- 显示格式："主要名称 (also known as: 别名1, 别名2)"
- 点击该贡献者进行跨仓库对比时，会聚合所有别名的 commits

### 技术实现

#### 核心优势：Token 效率优化

传统方式需要重新评估所有 commits（如 50 个 commits 的总 token 消耗），而采用 **分别评估 + LLM 合并** 的方式：

1. **复用缓存评估**：每个名称独立评估并缓存（`~/.local/share/oscanner/evaluations/cache/<repo>/<author>.json`）
2. **增量计算**：后续只需评估新增的 commits
3. **LLM 仅合并摘要**：只调用一次 LLM 来合并已有的分析文本（~1500 tokens），而不是重新分析所有 commits

**Token 节省示例**：

- 传统方式：50 commits × 平均 2000 tokens/commit = **100,000 tokens**
- 优化方式：
  - CarterWu (42 commits，已缓存) = 0 tokens
  - wu-yanbiao (3 commits，已缓存) = 0 tokens
  - 吴炎标 (5 commits，新评估) = 10,000 tokens
  - 合并摘要 (LLM) = 1,500 tokens
  - **总计：11,500 tokens（节省 88.5%）**

#### API 端点

##### `/api/evaluate/{owner}/{repo}/{author}` (POST)

**支持 Request Body**：

```json
{
  "aliases": ["CarterWu", "wu-yanbiao", "吴炎标"]
}
```

**处理流程**：

1. 如果提供 `aliases` 且数量 > 1：
   - 遍历每个别名，分别调用 `evaluate_author_incremental()`
   - 每个别名的评估结果独立缓存
   - 收集所有评估结果和对应的 commit 数量作为权重
   - 调用 `/api/merge-evaluations` 合并

2. 如果只有单个作者或未提供 aliases：
   - 按原有流程直接评估

##### `/api/merge-evaluations` (POST)

**Request Body**：

```json
{
  "evaluations": [
    {
      "author": "CarterWu",
      "weight": 42,
      "evaluation": { /* 完整的评估对象 */ }
    },
    {
      "author": "wu-yanbiao",
      "weight": 3,
      "evaluation": { /* 完整的评估对象 */ }
    }
  ],
  "model": "openai/gpt-4o"  // 可选
}
```

**处理逻辑**：

1. **加权平均分数**：
   ```python
   merged_score[dimension] = sum(eval[dimension] * weight) / total_weight
   ```

2. **LLM 合并摘要**：
   - 提示词包含所有别名的分析文本和权重比例
   - 要求 LLM 综合生成统一的、加权的分析报告
   - 自动处理权重较高的贡献者的影响力

3. **响应结果**：
   ```json
   {
     "success": true,
     "merged_evaluation": {
       "username": "CarterWu + wu-yanbiao + 吴炎标",
       "mode": "merged",
       "total_commits_analyzed": 50,
       "scores": { /* 加权平均后的六维分数 */ },
       "commits_summary": { /* 聚合的统计信息 */ }
     }
   }
   ```

##### `/api/batch/common-contributors` (POST)

**支持 `author_aliases` 参数**：

```json
{
  "repos": [
    { "owner": "facebook", "repo": "react" },
    { "owner": "vercel", "repo": "next.js" }
  ],
  "author_aliases": "John Doe, johndoe, John D, jdoe"
}
```

**处理流程**：

- Pass 1: 按 GitHub ID/login 分组
- **Pass 1.5**：如果提供了 `author_aliases`，合并所有匹配别名的身份组
- Pass 2: 模糊匹配孤立作者
- Pass 3: 按精确名称分组未匹配的作者

**响应新增字段**：

```json
{
  "common_contributors": [
    {
      "author": "John Doe",
      "aliases": ["John Doe", "johndoe", "John D"],  // 新增：所有匹配的名称
      "repos": [...],
      "total_commits": 225
    }
  ]
}
```

##### `/api/batch/compare-contributor` (POST)

**支持 `author_aliases` 参数**：

```json
{
  "contributor": "John Doe",
  "repos": [...],
  "author_aliases": "John Doe, johndoe, John D"
}
```

**处理逻辑**：

- 解析别名列表并归一化（lowercase + trim）
- 调用 `evaluate_author()` 时传入完整的别名列表
- 每个仓库都会聚合所有别名的 commits 进行评估

### 前端实现

#### 组件：`MultiRepoAnalysis.tsx`

**新增状态**：

```tsx
const [authorAliases, setAuthorAliases] = useState('');
```

**UI 输入**：

```tsx
<TextArea
  value={authorAliases}
  onChange={(e) => setAuthorAliases(e.target.value)}
  placeholder={'e.g., John Doe, John D, johndoe, jdoe\nGroup multiple names that belong to the same contributor'}
  rows={2}
/>
```

**API 调用更新**：

```tsx
// 单仓库评估
if (authorAliases.trim()) {
  const aliases = authorAliases.split(',').map(a => a.trim().toLowerCase());
  if (aliases.includes(author.author.toLowerCase())) {
    requestBody = { aliases };
  }
}

// 多仓库 Common Contributors
body: JSON.stringify({
  repos: [...],
  author_aliases: authorAliases.trim() ? authorAliases : undefined
})

// 跨仓库对比
body: JSON.stringify({
  contributor: contributorName,
  repos: [...],
  author_aliases: authorAliases.trim() ? authorAliases : undefined
})
```

**显示优化**：

```tsx
// .eval-header: 显示所有别名
<h2>
  {(() => {
    const currentAuthor = authorsData[selectedAuthorIndex]?.author;
    if (authorAliases.trim()) {
      const aliases = authorAliases.split(',').map(a => a.trim()).filter(a => a);
      if (aliases.some(a => a.toLowerCase() === currentAuthor?.toLowerCase())) {
        return aliases.join(', ');  // "CarterWu, wu-yanbiao, 吴炎标"
      }
    }
    return currentAuthor;
  })()}
</h2>

// Common Contributors 表格: "also known as"
render: (author, record) => {
  const otherAliases = record.aliases.filter(a => a !== author);
  return (
    <Space direction="vertical">
      <Space>
        <Avatar src={...} />
        <span>{author}</span>
      </Space>
      {otherAliases.length > 0 && (
        <span style={{ fontSize: '0.85em', color: 'rgba(0,0,0,0.45)' }}>
          also known as: {otherAliases.join(', ')}
        </span>
      )}
    </Space>
  );
}
```

### 最佳实践

1. **提前配置别名**：在 Dashboard 中分析前先填入已知的别名
2. **利用缓存**：系统会自动缓存每个名称的评估结果，后续合并几乎不消耗额外 token
3. **跨仓库一致性**：在多仓库分析中使用相同的别名配置，确保 Common Contributors 正确识别
4. **增量更新**：当某个别名有新 commits 时，只需重新评估该别名，然后重新合并即可

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


