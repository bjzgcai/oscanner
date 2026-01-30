# 闭环描述

## 基础

1. 当前项目目录结构混乱，前后端不清晰
2. 两个后端服务（`evaluator/` 和 `repos_runner/`）混在根目录
3. 两个前端应用（`webapp/` 和 `pages/`）混在一起
4. 脚本和文档散落在根目录
5. 新开发者难以理解项目结构

## 设计

### 目标资源：项目目录结构（Project Directory Structure）

项目目录结构是一种"组织资源"，用于：
- **清晰分离前后端**：后端服务统一在 `backend/`，前端应用统一在 `frontend/`
- **明确服务职责**：每个服务的端口、依赖关系、必需性都有清晰说明
- **统一管理脚本**：所有启动/部署脚本集中在 `scripts/`
- **集中管理文档**：项目文档集中在 `docs/`

### 重构闭环：目录重组与路径更新的"全部环节"

#### 1. 目录创建（新增资源）
- 创建 `backend/` 目录，用于统一管理后端服务
- 创建 `frontend/` 目录，用于统一管理前端应用
- 创建 `scripts/` 目录，用于统一管理工具脚本
- 创建 `docs/` 目录，用于统一管理项目文档

#### 2. 文件移动（资源迁移）
- 移动 `evaluator/` → `backend/evaluator/`
- 移动 `repos_runner/` → `backend/repos_runner/`
- 移动 `webapp/` → `frontend/webapp/`
- 移动 `pages/` → `frontend/pages/`
- 移动 `oscanner/` → `cli/oscanner/`
- 移动启动脚本 → `scripts/`
- 移动项目文档 → `docs/`

#### 3. 路径更新（资源引用修正）
- 更新所有 Python 导入路径（`evaluator.*` → `backend.evaluator.*`）
- 更新所有脚本中的路径引用
- 更新 CLI 工具中的服务路径
- 更新 CI/CD 配置中的路径
- 更新配置文件中的路径引用

#### 4. 文档更新（资源说明）
- 更新主 `README.md` 中的目录结构说明
- 创建 `docs/ARCHITECTURE.md` 详细架构文档
- 更新各服务的 `README.md` 路径说明
- 更新 `pyproject.toml` 中的包路径

#### 5. 测试验证（资源验证）
- 验证所有服务可以正常启动
- 验证前端可以正常连接后端
- 验证 CLI 工具可以正常工作
- 验证 CI/CD 流程正常

### 目标目录结构

```
oscanner/
├── README.md                   # 主 README
├── pyproject.toml              # Python 项目配置
├── uv.lock                     # 依赖锁定文件
│
├── backend/                    # 后端服务目录
│   ├── evaluator/              # 主评估服务（端口 8000，必需）
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── routes/
│   │   ├── services/
│   │   ├── collectors/
│   │   ├── tools/
│   │   └── README.md
│   │
│   └── repos_runner/           # 仓库测试服务（端口 8001，可选）
│       ├── __init__.py
│       ├── server.py
│       ├── routes/
│       ├── services/
│       └── README.md
│
├── frontend/                   # 前端应用目录
│   ├── webapp/                 # Next.js 主应用（端口 3000，必需）
│   │   ├── app/
│   │   ├── components/
│   │   ├── package.json
│   │   └── README.md
│   │
│   └── pages/                   # GitHub Pages 静态站点（可选）
│       ├── index.html
│       └── README.md
│
├── cli/                        # CLI 工具（可安装包）
│   ├── __init__.py
│   ├── cli.py
│   └── __main__.py
│
├── plugins/                    # 插件系统（共享）
│   ├── zgc_simple/
│   ├── zgc_ai_native_2026/
│   └── _shared/
│
├── scripts/                    # 工具脚本
│   ├── start_dev.sh
│   ├── start_production.sh
│   ├── deploy.sh
│   └── ...
│
├── tests/                      # 测试目录
│   ├── evaluator/
│   ├── repos_runner/
│   └── ...
│
└── docs/                       # 文档目录
    ├── ARCHITECTURE.md         # 架构说明
    ├── API.md                  # API 文档
    └── ...
```

## TODO_LIST

> 只维护最新版本；完成后清空 TODO，仅保留"完成记录 + 日期"。
- （本轮已完成，TODO 清空）

## 完成记录

- 2026-01-30：项目目录结构重构完成，所有服务测试验证通过
  - 创建 `backend/`、`frontend/`、`scripts/`、`docs/` 目录
  - 移动 `evaluator/` → `backend/evaluator/`，`repos_runner/` → `backend/repos_runner/`
  - 移动 `webapp/` → `frontend/webapp/`，`pages/` → `frontend/pages/`
  - 重命名 `oscanner/` → `cli/`
  - 更新所有导入路径、配置文件、CI/CD 配置和文档
  - 修复测试文件路径引用，添加 `backend/` 目录到 `sys.path`
  - 修复 `backend/evaluator/__init__.py` 和 `backend/repos_runner/__init__.py` 的路径调整
  - 修复 CLI 工具启动时的 `PYTHONPATH` 设置
