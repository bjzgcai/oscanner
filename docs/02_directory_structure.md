# 项目目录结构设计指南

## 概述

本文档详细说明 oscanner 项目的目录结构设计，包括各个目录的作用、组织原则和使用指南。

## 目录结构总览

```
oscanner/
├── README.md                   # 项目主文档
├── pyproject.toml              # Python 项目配置（依赖管理）
├── uv.lock                     # 依赖锁定文件（版本固定）
│
├── backend/                    # 后端服务目录
│   ├── evaluator/              # 主评估服务（端口 8000，必需）
│   └── repos_runner/           # 仓库测试服务（端口 8001，可选）
│
├── frontend/                   # 前端应用目录
│   ├── webapp/                 # Next.js 主应用（端口 3000，必需）
│   └── pages/                  # GitHub Pages 静态站点（可选）
│
├── cli/                        # CLI 工具（可安装包）
│   ├── __init__.py
│   ├── cli.py                  # CLI 入口
│   └── __main__.py
│
├── plugins/                    # 插件系统（共享）
│   ├── zgc_simple/             # 默认插件（传统六维度）
│   ├── zgc_ai_native_2026/     # AI-Native 2026 插件（四维度）
│   └── _shared/                 # 共享组件
│
├── checkers/                   # 检查器系统
│   ├── checker_list.yaml       # 检查器列表配置
│   └── ccn/                    # 圈复杂度检查器示例
│
├── scripts/                    # 工具脚本
│   ├── start_dev.sh           # 启动开发环境
│   ├── start_production.sh    # 启动生产环境
│   ├── stop_dev.sh            # 停止开发环境
│   └── deploy.sh              # 部署脚本
│
├── tests/                      # 测试目录
│   ├── evaluator/             # 评估服务测试
│   ├── repos_runner/          # 仓库测试服务测试
│   ├── checkers/              # 检查器测试
│   └── routes/                # API 路由测试
│
├── docs/                       # 文档目录
│   ├── 01_architecture.md      # 项目架构说明
│   ├── 02_directory_structure.md  # 本文件
│   └── ...                    # 其他文档
│
├── .agents/                    # AI 辅助开发配置
│   ├── rules/                 # Cursor 规则
│   ├── skills/                # Cursor 技能
│   └── tasks/                 # 任务文档
│
├── .claude/                    # Claude 配置
│   ├── rules/                 # Claude 规则
│   └── skills/                # Claude 技能
│
└── .workflow/                  # CI/CD 工作流配置
    ├── master-pipeline.yml    # 主分支流水线
    ├── pr-pipeline.yml        # PR 流水线
    └── branch-pipeline.yml    # 分支流水线
```

## 目录详细说明

### 1. 根目录文件

#### `README.md`
- **作用**：项目主文档，包含快速开始、功能介绍、使用说明
- **维护**：项目维护者
- **更新频率**：随主要功能变更更新

#### `pyproject.toml`
- **作用**：Python 项目配置文件，定义依赖、包结构、脚本入口
- **维护**：开发团队
- **更新频率**：添加/更新依赖时

#### `uv.lock`
- **作用**：依赖版本锁定文件，确保环境一致性
- **维护**：自动生成（`uv lock`）
- **更新频率**：依赖变更时

### 2. backend/ - 后端服务目录

**设计原则**：所有后端服务统一放在 `backend/` 目录下，清晰分离前后端。

#### `backend/evaluator/` - 主评估服务

**作用**：核心评估服务，提供工程师能力评估、数据提取、轨迹分析等功能。

**关键子目录**：
- `routes/` - FastAPI 路由定义
  - `evaluation.py` - 评估相关 API
  - `trajectory.py` - 轨迹分析 API
  - `data.py` - 数据提取 API
  - `checkers.py` - 检查器管理 API
  - `plugins.py` - 插件管理 API
  - `batch.py` - 批量处理 API
  - `benchmark.py` - 基准测试 API
  - `config.py` - 配置管理 API
  - `external.py` - 外部服务 API

- `services/` - 业务逻辑服务层
  - `evaluation_service.py` - 评估服务核心逻辑
  - `trajectory_service.py` - 轨迹分析服务
  - `extraction_service.py` - 数据提取服务
  - `plugin_service.py` - 插件管理服务
  - `merge_service.py` - 结果合并服务

- `collectors/` - 数据收集器
  - `github.py` - GitHub API 数据收集
  - `gitee.py` - Gitee API 数据收集

- `tools/` - 数据提取工具
  - `extract_repo_data.py` - 仓库数据提取主工具
  - `extract_repo_data_moderate.py` - 提取提交差异和相关文件上下文
  - `extract_repo_data_api.py` - API 模式提取

- `analyzers/` - 代码分析器
  - `code_analyzer.py` - 代码质量分析
  - `commit_analyzer.py` - 提交分析
  - `collaboration_analyzer.py` - 协作分析

- `utils/` - 工具函数
  - `data_loader.py` - 数据加载工具
  - `commit_utils.py` - 提交处理工具
  - `repo_parser.py` - 仓库解析工具
  - `git_worktree.py` - Git 工作树工具

- `schemas/` - 数据模型定义
  - `evaluation.py` - 评估结果模型
  - `trajectory.py` - 轨迹数据模型

- `validation/` - 验证测试
  - `validators.py` - 验证器实现
  - `validation_runner.py` - 验证运行器
  - `benchmark_dataset.py` - 基准数据集

- `config/` - 配置管理
  - `env.py` - 环境变量配置
  - `tokens.py` - Token 管理

**端口**：8000  
**必需性**：✅ 必需（主要功能依赖此服务）  
**依赖**：LLM API（必需）、GitHub/Gitee API（可选但推荐）

#### `backend/repos_runner/` - 仓库测试服务

**作用**：仓库克隆、探索、自动测试运行服务。

**关键子目录**：
- `routes/` - FastAPI 路由
  - `runner.py` - 仓库运行相关 API
- `services/` - 业务逻辑
  - `repo_service.py` - 仓库服务逻辑
- `schemas/` - 数据模型

**端口**：8001  
**必需性**：⚠️ 可选（只有前端 `/runner` 页面需要）  
**依赖**：Claude API（必需）、共享 `backend/evaluator/venv` 虚拟环境

### 3. frontend/ - 前端应用目录

**设计原则**：所有前端应用统一放在 `frontend/` 目录下。

#### `frontend/webapp/` - Next.js 主应用

**作用**：主要的前端 Dashboard，提供单仓库分析、多仓库分析、轨迹分析等功能。

**关键子目录**：
- `app/` - Next.js App Router 页面
- `components/` - React 组件
- `lib/` - 工具函数和配置
- `public/` - 静态资源

**端口**：3000  
**必需性**：✅ 必需（如果使用前端界面）  
**依赖**：`backend/evaluator`（必需，端口 8000）、`backend/repos_runner`（可选，端口 8001）

#### `frontend/pages/` - GitHub Pages 静态站点

**作用**：GitHub Pages 静态文档站点。

**必需性**：⚠️ 可选

### 4. cli/ - CLI 工具目录

**作用**：命令行工具，提供统一的命令行入口，管理所有服务。

**关键文件**：
- `cli.py` - CLI 主入口，包含所有命令实现
- `__main__.py` - 包入口，支持 `python -m cli` 运行

**主要命令**：
- `oscanner init` - 初始化配置
- `oscanner serve` - 启动评估服务
- `oscanner dev` - 启动开发环境（所有服务）
- `oscanner dashboard` - 启动前端 Dashboard

### 5. plugins/ - 插件系统目录

**作用**：插件系统，支持不同的评估标准和前端视图。

**设计原则**：
- 每个插件是独立的目录
- 插件包含 `scan/`（评估逻辑）和 `view/`（前端视图）
- `_shared/` 目录存放共享组件

#### `plugins/zgc_simple/` - 默认插件

**作用**：传统六维度评估标准插件。

**结构**：
- `scan/__init__.py` - 评估逻辑实现
- `view/` - 前端视图组件
- `i18n/` - 国际化文件

#### `plugins/zgc_ai_native_2026/` - AI-Native 2026 插件

**作用**：AI-Native 2026 四维度评估标准插件。

**结构**：同 `zgc_simple/`

#### `plugins/_shared/` - 共享组件

**作用**：插件间共享的组件和工具。

**结构**：
- `scan/` - 共享的扫描逻辑
- `view/` - 共享的前端组件

### 6. checkers/ - 检查器系统目录

**作用**：代码检查器系统，支持动态加载检查器。

**关键文件**：
- `checker_list.yaml` - 检查器列表配置
- `ccn/` - 圈复杂度检查器示例
  - `checker.py` - 检查器实现
  - `requirements.txt` - 检查器依赖

**设计原则**：
- 每个检查器是独立的目录
- 检查器通过 `checker_list.yaml` 注册
- 检查器可以有自己的依赖

### 7. scripts/ - 工具脚本目录

**作用**：统一管理所有工具脚本。

**关键脚本**：
- `start_dev.sh` - 启动开发环境（所有服务）
- `start_production.sh` - 启动生产环境
- `stop_dev.sh` - 停止开发环境
- `deploy.sh` - 部署脚本
- `deploy_remote.sh` - 远程部署脚本
- `setup_remote_server.sh` - 远程服务器设置脚本

**设计原则**：
- 所有脚本统一放在 `scripts/` 目录
- 脚本使用相对路径，从项目根目录执行
- 脚本包含错误处理和日志输出

### 8. tests/ - 测试目录

**作用**：项目测试代码。

**结构**：
- `evaluator/` - 评估服务测试
- `repos_runner/` - 仓库测试服务测试
- `checkers/` - 检查器测试
- `routes/` - API 路由测试
- `conftest.py` - pytest 配置和共享 fixture

**设计原则**：
- 测试目录结构与源代码目录结构对应
- 使用 pytest 作为测试框架
- 测试文件命名：`test_*.py`

### 9. docs/ - 文档目录

**作用**：项目文档集中管理。

**文件命名规范**：
- 使用编号前缀：`01_`, `02_`, `03_` ...
- 使用小写下划线命名：`snake_case.md`
- 文件名要有描述性

**主要文档**：
- `01_architecture.md` - 项目架构说明
- `02_directory_structure.md` - 本文件（目录结构设计）
- `03_evaluation_architecture.md` - 评估功能架构
- `06_trajectory_evaluation.md` - 轨迹评估增强
- `07_refactor_summary.md` - 重构完成总结
- `08_project_structure_refactor_proposal.md` - 项目目录结构重构方案（历史文档）

### 10. .agents/ - AI 辅助开发配置

**作用**：Cursor IDE 的 AI 辅助开发配置。

**结构**：
- `rules/` - Cursor 规则文件
- `skills/` - Cursor 技能文件
- `tasks/` - 任务文档

### 11. .claude/ - Claude 配置

**作用**：Claude AI 的配置。

**结构**：
- `rules/` - Claude 规则文件
- `skills/` - Claude 技能文件

### 12. .workflow/ - CI/CD 工作流配置

**作用**：持续集成/持续部署配置。

**关键文件**：
- `master-pipeline.yml` - 主分支流水线
- `pr-pipeline.yml` - PR 流水线
- `branch-pipeline.yml` - 分支流水线

## 目录组织原则

### 1. 前后端分离
- 所有后端服务统一在 `backend/` 目录
- 所有前端应用统一在 `frontend/` 目录
- 清晰的职责划分，便于维护和扩展

### 2. 服务独立
- 每个服务是独立的目录
- 服务之间通过 API 通信
- 服务可以独立部署和扩展

### 3. 共享资源集中
- 插件系统在 `plugins/` 目录
- 检查器系统在 `checkers/` 目录
- 共享组件在 `_shared/` 目录

### 4. 工具脚本统一
- 所有脚本在 `scripts/` 目录
- 统一的命名和调用方式
- 便于 CI/CD 集成

### 5. 文档集中管理
- 所有文档在 `docs/` 目录
- 统一的命名规范
- 编号便于查找和阅读顺序

## 数据存储位置

所有数据存储在 XDG 标准目录：

```
~/.local/share/oscanner/
├── data/                       # 提取的仓库数据
│   └── {platform}/{owner}/{repo}/
└── repos/                      # repos_runner 克隆的仓库
    └── {platform}/{owner}/{repo}/{ref}/source/
```

## 端口分配

| 服务 | 端口 | 必需性 | 说明 |
|------|------|--------|------|
| evaluator | 8000 | ✅ 必需 | 主评估服务 |
| repos_runner | 8001 | ⚠️ 可选 | 仓库测试服务 |
| webapp | 3000 | ✅ 必需（如果使用前端） | Next.js 前端应用 |

## 环境变量配置位置

| 服务 | 配置文件位置 |
|------|------------|
| evaluator | `backend/evaluator/.env.local` |
| repos_runner | `backend/repos_runner/.env.local` |
| webapp | `frontend/webapp/.env.local` |

## 导入路径说明

### Python 包导入

由于 `evaluator` 和 `repos_runner` 位于 `backend/` 目录下，但在运行时需要作为顶级包导入，服务器启动文件会自动将 `backend/` 添加到 `sys.path`：

```python
# backend/evaluator/server.py
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# 之后可以正常导入
from evaluator.paths import ...
```

### pyproject.toml 配置

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["cli*", "evaluator*", "repos_runner*"]
```

这确保了：
- `cli` 包可以从根目录导入
- `evaluator` 和 `repos_runner` 可以从 `backend/` 目录导入（运行时通过 `sys.path` 调整）
- 命令行工具名称保持为 `oscanner`（用户使用），但包名改为 `cli`（更清晰的目录结构）

## 常见问题

### Q: 为什么 evaluator 和 repos_runner 都在 backend/ 目录下？

A: 为了清晰分离前后端，所有后端服务统一放在 `backend/` 目录。虽然它们运行在不同的端口，但都是后端服务。

### Q: 为什么 evaluator 和 repos_runner 的导入路径不是 `backend.evaluator`？

A: 为了保持向后兼容性和简化导入，服务器启动时会自动将 `backend/` 添加到 `sys.path`，使得 `evaluator` 和 `repos_runner` 可以作为顶级包导入。

### Q: 前端如何知道后端服务的地址？

A: 
- 主要功能（evaluator）：通过 `NEXT_PUBLIC_API_SERVER_URL` 环境变量或使用相对路径（同源）
- Repository Runner：硬编码为 `http://localhost:8001`（可改为环境变量）

### Q: 如何只运行部分服务？

A:
- **只运行主要功能**：只需启动 `evaluator` 和 `webapp`
- **完整功能**：启动所有三个服务（`evaluator`、`repos_runner`、`webapp`）

### Q: 插件如何添加？

A:
1. 在 `plugins/` 目录下创建新插件目录
2. 实现 `scan/__init__.py`（评估逻辑）和 `view/`（前端视图）
3. 在 `backend/evaluator/plugin_registry.py` 中注册插件
4. 前端会自动发现并加载插件

### Q: 检查器如何添加？

A:
1. 在 `checkers/` 目录下创建新检查器目录
2. 实现 `checker.py`（检查器逻辑）
3. 在 `checkers/checker_list.yaml` 中注册检查器
4. 系统会自动加载检查器

## 相关文档

- [01_architecture.md](01_architecture.md) - 项目架构说明
- [README.md](../README.md) - 项目主文档
- [backend/evaluator/README.md](../backend/evaluator/README.md) - 评估服务文档
- [backend/repos_runner/README.md](../backend/repos_runner/README.md) - 仓库测试服务文档
- [frontend/webapp/README.md](../frontend/webapp/README.md) - 前端应用文档
