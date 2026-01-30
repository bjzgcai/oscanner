# 项目目录结构重构方案

## 当前问题分析

### 1. 前后端不清晰
- ❌ 两个后端服务（`evaluator/` 和 `repos_runner/`）混在根目录
- ❌ 前端（`webapp/`）和另一个前端（`pages/`）混在一起
- ❌ 没有清晰的 `backend/` 和 `frontend/` 目录结构
- ❌ 工具脚本散落在根目录

### 2. 服务职责混乱
- `evaluator/` - 主评估服务（端口 8000）
- `repos_runner/` - 仓库测试服务（端口 8001）
- `webapp/` - Next.js 前端（端口 3000）
- `pages/` - GitHub Pages 静态站点（？）

### 3. 依赖关系不明确
- `repos_runner` 使用 `evaluator/venv`
- 前端部分功能依赖 `repos_runner`，部分依赖 `evaluator`
- CLI 工具需要知道所有服务的路径

## 重构方案

### 方案 A：按服务类型分离（推荐）

```
oscanner/
├── README.md
├── pyproject.toml
├── uv.lock
│
├── backend/                          # 后端服务目录
│   ├── evaluator/                    # 主评估服务（端口 8000）
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── routes/
│   │   ├── services/
│   │   ├── collectors/
│   │   ├── tools/
│   │   └── ...
│   │
│   └── repos_runner/                 # 仓库测试服务（端口 8001）
│       ├── __init__.py
│       ├── server.py
│       ├── routes/
│       ├── services/
│       └── ...
│
├── frontend/                         # 前端应用目录
│   ├── webapp/                       # Next.js 主应用（端口 3000）
│   │   ├── app/
│   │   ├── components/
│   │   ├── package.json
│   │   └── ...
│   │
│   └── pages/                        # GitHub Pages 静态站点（可选）
│       ├── index.html
│       └── ...
│
├── cli/                              # CLI 工具
│   └── oscanner/
│       ├── __init__.py
│       ├── cli.py
│       └── ...
│
├── plugins/                          # 插件系统（共享）
│   ├── zgc_simple/
│   ├── zgc_ai_native_2026/
│   └── _shared/
│
├── scripts/                          # 工具脚本
│   ├── start_dev.sh
│   ├── start_production.sh
│   ├── deploy.sh
│   └── ...
│
├── tests/                            # 测试目录
│   ├── evaluator/
│   ├── repos_runner/
│   └── ...
│
└── docs/                             # 文档目录
    ├── architecture.md
    ├── api.md
    └── ...
```

**优点**：
- ✅ 前后端清晰分离
- ✅ 多个后端服务统一管理
- ✅ 脚本集中管理
- ✅ 符合常见项目结构

**缺点**：
- ⚠️ 需要大量文件移动和导入路径修改
- ⚠️ 可能影响现有 CI/CD 配置

### 方案 B：保持现状，添加清晰文档（保守）

保持当前结构，但添加清晰的文档说明：

```
oscanner/
├── README.md                         # 主 README（说明整体结构）
├── ARCHITECTURE.md                   # 架构说明文档
│
├── evaluator/                        # 后端服务 1：主评估服务
│   └── README.md                     # 说明：端口 8000，主服务
│
├── repos_runner/                     # 后端服务 2：仓库测试服务
│   └── README.md                     # 说明：端口 8001，可选服务
│
├── webapp/                           # 前端：Next.js 应用
│   └── README.md                     # 说明：端口 3000，主要前端
│
├── pages/                            # 前端：GitHub Pages 静态站点
│   └── README.md                     # 说明：静态站点，可选
│
└── ...
```

**优点**：
- ✅ 无需重构代码
- ✅ 风险低
- ✅ 通过文档说明结构

**缺点**：
- ❌ 结构仍然混乱
- ❌ 新人难以理解

### 方案 C：混合方案（折中）

只移动关键目录，保持最小改动：

```
oscanner/
├── README.md
│
├── services/                         # 后端服务统一目录
│   ├── evaluator/                    # 主评估服务
│   └── repos_runner/                 # 仓库测试服务
│
├── apps/                             # 前端应用统一目录
│   ├── webapp/                       # Next.js 主应用
│   └── pages/                        # GitHub Pages 静态站点
│
├── cli/                              # CLI 工具
│   └── oscanner/
│
├── plugins/                          # 插件系统
│
├── scripts/                          # 工具脚本
│
└── ...
```

**优点**：
- ✅ 前后端分离清晰
- ✅ 改动相对较小
- ✅ 结构更清晰

**缺点**：
- ⚠️ 仍需要修改导入路径
- ⚠️ 需要更新脚本路径

## 推荐方案：方案 A（按服务类型分离）

### 重构步骤

#### 1. 创建新目录结构

```bash
# 创建新目录
mkdir -p backend/evaluator
mkdir -p backend/repos_runner
mkdir -p frontend/webapp
mkdir -p frontend/pages
mkdir -p cli/oscanner
mkdir -p scripts
mkdir -p docs
```

#### 2. 移动文件

```bash
# 移动后端服务
mv evaluator/* backend/evaluator/
mv repos_runner/* backend/repos_runner/

# 移动前端应用
mv webapp/* frontend/webapp/
mv pages/* frontend/pages/

# 移动 CLI
mv oscanner/* cli/oscanner/

# 移动脚本
mv start_*.sh scripts/
mv deploy*.sh scripts/
mv stop_*.sh scripts/
mv setup_*.sh scripts/

# 移动文档
mv *.md docs/  # 除了 README.md
```

#### 3. 更新导入路径

需要修改的文件：
- `backend/evaluator/server.py` - 更新导入路径
- `backend/repos_runner/server.py` - 更新导入路径
- `cli/oscanner/cli.py` - 更新服务路径
- `scripts/*.sh` - 更新路径引用
- `frontend/webapp/**/*.tsx` - 更新 API 路径（如果需要）

#### 4. 更新配置文件

- `pyproject.toml` - 更新包路径
- `package.json` - 更新脚本路径
- `.github/workflows/*.yml` - 更新 CI/CD 路径
- `Dockerfile`（如果有）- 更新路径

#### 5. 更新文档

- `README.md` - 更新项目结构说明
- `docs/ARCHITECTURE.md` - 新增架构文档
- 各服务的 `README.md` - 更新路径说明

## 目录结构说明文档模板

### ARCHITECTURE.md

```markdown
# 项目架构说明

## 目录结构

```
oscanner/
├── backend/              # 后端服务
│   ├── evaluator/       # 主评估服务（端口 8000）
│   └── repos_runner/    # 仓库测试服务（端口 8001）
│
├── frontend/            # 前端应用
│   ├── webapp/          # Next.js 主应用（端口 3000）
│   └── pages/           # GitHub Pages 静态站点
│
├── cli/                 # CLI 工具
│   └── oscanner/
│
├── plugins/            # 插件系统
├── scripts/            # 工具脚本
├── tests/              # 测试
└── docs/               # 文档
```

## 服务说明

### 后端服务

#### evaluator（主评估服务）
- **端口**: 8000
- **功能**: 工程师能力评估、数据提取、轨迹分析
- **依赖**: LLM API、GitHub/Gitee API
- **必需性**: ✅ 必需

#### repos_runner（仓库测试服务）
- **端口**: 8001
- **功能**: 仓库克隆、探索、测试运行
- **依赖**: Claude API
- **必需性**: ⚠️ 可选（只有 `/runner` 页面需要）

### 前端应用

#### webapp（Next.js 主应用）
- **端口**: 3000
- **功能**: 主要的前端界面
- **依赖**: evaluator（必需）、repos_runner（可选）
- **必需性**: ✅ 必需（如果使用前端）

#### pages（GitHub Pages）
- **功能**: 静态文档站点
- **必需性**: ⚠️ 可选

## 启动顺序

1. **开发环境**：
   ```bash
   # 启动主服务
   cd backend/evaluator && python server.py
   
   # 启动可选服务（如果需要 Repository Runner）
   cd backend/repos_runner && python server.py
   
   # 启动前端
   cd frontend/webapp && npm run dev
   ```

2. **使用 CLI**：
   ```bash
   oscanner dev  # 自动启动所有服务
   ```

## 依赖关系

```
frontend/webapp
    ├── 依赖 → backend/evaluator (必需)
    └── 依赖 → backend/repos_runner (可选，仅 /runner 页面)

backend/repos_runner
    └── 共享 → backend/evaluator/venv (虚拟环境)

cli/oscanner
    ├── 管理 → backend/evaluator
    ├── 管理 → backend/repos_runner
    └── 管理 → frontend/webapp
```
```

## 实施建议

### 阶段 1：文档先行（1-2 天）
1. 创建 `docs/ARCHITECTURE.md`
2. 更新各服务的 `README.md`
3. 在主 `README.md` 中添加结构说明

### 阶段 2：小范围重构（3-5 天）
1. 先移动脚本到 `scripts/`
2. 移动文档到 `docs/`
3. 测试脚本是否正常工作

### 阶段 3：服务目录重构（1-2 周）
1. 创建 `backend/` 和 `frontend/` 目录
2. 移动服务文件
3. 更新所有导入路径
4. 更新 CI/CD 配置
5. 全面测试

### 阶段 4：清理和优化（1 周）
1. 删除旧目录
2. 更新所有文档
3. 代码审查
4. 发布新版本

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 导入路径错误 | 高 | 使用 IDE 全局替换，全面测试 |
| CI/CD 失败 | 中 | 提前更新 CI/CD 配置 |
| 文档过时 | 低 | 同步更新文档 |
| 用户困惑 | 低 | 提供迁移指南 |

## 总结

推荐采用**方案 A（按服务类型分离）**，虽然需要一定的工作量，但能带来：
- ✅ 清晰的项目结构
- ✅ 更好的可维护性
- ✅ 更容易理解的项目组织
- ✅ 符合行业最佳实践

如果时间紧迫，可以先采用**方案 B（文档先行）**，然后逐步迁移到方案 A。
