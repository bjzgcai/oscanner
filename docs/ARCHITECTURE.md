# 项目架构说明

## 目录结构

```
oscanner/
├── README.md                   # 主 README
├── pyproject.toml              # Python 项目配置
├── uv.lock                     # 依赖锁定文件
│
├── backend/                    # 后端服务目录
│   ├── evaluator/              # 主评估服务（端口 8000，必需）
│   │   ├── __init__.py
│   │   ├── server.py           # FastAPI 服务器
│   │   ├── routes/             # API 路由
│   │   ├── services/            # 业务逻辑服务
│   │   ├── collectors/         # 数据收集器（GitHub/Gitee）
│   │   ├── tools/              # 数据提取工具
│   │   └── README.md
│   │
│   └── repos_runner/           # 仓库测试服务（端口 8001，可选）
│       ├── __init__.py
│       ├── server.py           # FastAPI 服务器
│       ├── routes/             # API 路由
│       ├── services/           # 业务逻辑服务
│       └── README.md
│
├── frontend/                   # 前端应用目录
│   ├── webapp/                 # Next.js 主应用（端口 3000，必需）
│   │   ├── app/                # Next.js App Router
│   │   ├── components/         # React 组件
│   │   ├── package.json
│   │   └── README.md
│   │
│   └── pages/                  # GitHub Pages 静态站点（可选）
│       ├── index.html
│       └── README.md
│
├── cli/                        # CLI 工具（可安装包）
│   ├── __init__.py
│   ├── cli.py                  # CLI 入口
│   └── __main__.py
│
├── plugins/                    # 插件系统（共享）
│   ├── zgc_simple/            # 默认插件
│   ├── zgc_ai_native_2026/    # AI-Native 2026 插件
│   └── _shared/               # 共享组件
│
├── scripts/                    # 工具脚本
│   ├── start_dev.sh           # 启动开发环境
│   ├── start_production.sh    # 启动生产环境
│   ├── stop_dev.sh            # 停止开发环境
│   ├── deploy.sh              # 部署脚本
│   └── ...
│
├── tests/                      # 测试目录
│   ├── evaluator/
│   ├── repos_runner/
│   └── ...
│
└── docs/                       # 文档目录
    ├── ARCHITECTURE.md        # 本文件
    └── ...
```

## 服务说明

### 后端服务

#### evaluator（主评估服务）
- **端口**: 8000
- **路径**: `backend/evaluator/`
- **功能**: 
  - 工程师能力评估
  - 数据提取（GitHub/Gitee）
  - 轨迹分析
  - 批量分析
- **依赖**: 
  - LLM API（必需）
  - GitHub/Gitee API（可选，但强烈推荐）
- **必需性**: ✅ **必需**（主要功能依赖此服务）
- **启动方式**: 
  ```bash
  uv run oscanner serve
  # 或
  cd backend/evaluator && python server.py
  ```

#### repos_runner（仓库测试服务）
- **端口**: 8001
- **路径**: `backend/repos_runner/`
- **功能**: 
  - 仓库克隆（浅克隆）
  - 仓库探索（AI 生成文档）
  - 自动测试运行
- **依赖**: 
  - Claude API（必需）
  - 共享 `backend/evaluator/venv` 虚拟环境
- **必需性**: ⚠️ **可选**（只有前端 `/runner` 页面需要）
- **启动方式**: 
  ```bash
  cd backend/repos_runner && python server.py
  # 或
  cd backend/repos_runner && ./start_server.sh
  ```

### 前端应用

#### webapp（Next.js 主应用）
- **端口**: 3000
- **路径**: `frontend/webapp/`
- **功能**: 
  - 单仓库分析
  - 多仓库分析
  - 轨迹分析
  - 验证测试
  - Repository Runner（可选功能）
- **依赖**: 
  - `backend/evaluator`（必需，端口 8000）
  - `backend/repos_runner`（可选，端口 8001，仅 `/runner` 页面）
- **必需性**: ✅ **必需**（如果使用前端界面）
- **启动方式**: 
  ```bash
  cd frontend/webapp && npm run dev
  # 或
  uv run oscanner dashboard
  ```

#### pages（GitHub Pages 静态站点）
- **路径**: `frontend/pages/`
- **功能**: 静态文档站点
- **必需性**: ⚠️ **可选**

## 启动顺序

### 开发环境

**方式 1：使用脚本（推荐）**
```bash
./scripts/start_dev.sh
```

**方式 2：手动启动**
```bash
# 终端 1：启动 evaluator
uv run oscanner serve --reload

# 终端 2：启动 repos_runner（可选）
cd backend/repos_runner && python server.py

# 终端 3：启动前端
cd frontend/webapp && npm run dev
```

### 生产环境

```bash
./scripts/start_production.sh --daemon
```

## 依赖关系

```
frontend/webapp
    ├── 依赖 → backend/evaluator (必需，端口 8000)
    └── 依赖 → backend/repos_runner (可选，端口 8001，仅 /runner 页面)

backend/repos_runner
    └── 共享 → backend/evaluator/venv (虚拟环境)

cli (CLI 工具)
    ├── 管理 → backend/evaluator
    ├── 管理 → backend/repos_runner
    └── 管理 → frontend/webapp
```

## Python 包导入说明

### 包结构

- `cli` - CLI 工具包（位于 `cli/` 目录）
- `evaluator` - 评估服务包（位于 `backend/evaluator/`）
- `repos_runner` - 仓库测试服务包（位于 `backend/repos_runner/`）

### 导入路径

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
[project.scripts]
oscanner = "cli.cli:main"  # 命令行工具名称保持为 oscanner

[tool.setuptools.packages.find]
where = ["."]
include = ["cli*", "evaluator*", "repos_runner*"]
```

这确保了：
- `cli` 包可以从根目录导入
- `evaluator` 和 `repos_runner` 可以从 `backend/` 目录导入（运行时通过 `sys.path` 调整）
- 命令行工具名称保持为 `oscanner`（用户使用），但包名改为 `cli`（更清晰的目录结构）

## 数据存储

所有数据存储在 XDG 标准目录：

```
~/.local/share/oscanner/
├── data/                       # 提取的仓库数据
│   └── {platform}/{owner}/{repo}/
├── evaluations/                # 评估结果缓存
│   └── {platform}/{owner}/{repo}/
└── repos/                      # repos_runner 克隆的仓库
    └── {repo_name}/
```

## 端口分配

| 服务 | 端口 | 必需性 |
|------|------|--------|
| evaluator | 8000 | ✅ 必需 |
| repos_runner | 8001 | ⚠️ 可选 |
| webapp | 3000 | ✅ 必需（如果使用前端） |

## 环境变量

### evaluator 服务
- 配置文件：`backend/evaluator/.env.local`
- 必需变量：
  - `OPEN_ROUTER_KEY` 或 `OSCANNER_LLM_API_KEY`（LLM API）
- 可选变量：
  - `GITHUB_TOKEN`（提高 API 限制）
  - `GITEE_TOKEN`（Gitee API）

### repos_runner 服务
- 配置文件：`backend/repos_runner/.env.local`
- 必需变量：
  - `ANTHROPIC_API_KEY` 或 `OSCANNER_LLM_API_KEY`（Claude API）

### webapp 前端
- 配置文件：`frontend/webapp/.env.local`
- 可选变量：
  - `NEXT_PUBLIC_API_SERVER_URL`（后端 API 地址，默认：`http://localhost:8000`）
  - `PORT`（前端端口，默认：3000）

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

## 迁移指南

如果你是从旧版本迁移：

1. **更新脚本路径**：所有启动脚本已移动到 `scripts/` 目录
2. **更新环境变量路径**：`.env.local` 文件现在在 `backend/evaluator/` 和 `frontend/webapp/`
3. **更新导入路径**：Python 代码中的导入路径保持不变（通过 `sys.path` 调整）
4. **更新 CI/CD**：CI/CD 配置已更新路径引用

## 相关文档

- [README.md](../README.md) - 项目主文档
- [backend/evaluator/README.md](../backend/evaluator/README.md) - 评估服务文档
- [backend/repos_runner/README.md](../backend/repos_runner/README.md) - 仓库测试服务文档
- [frontend/webapp/README.md](../frontend/webapp/README.md) - 前端应用文档
