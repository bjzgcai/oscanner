# 目录结构重构完成总结

## 重构日期
2026-01-30

## 重构目标
将混乱的目录结构重新组织，清晰分离前后端，提高项目的可维护性和可理解性。

## 已完成的工作

### ✅ 1. 目录结构重组

**创建的新目录**：
- `backend/` - 后端服务统一目录
- `frontend/` - 前端应用统一目录
- `scripts/` - 工具脚本统一目录
- `docs/` - 文档统一目录

**移动的文件**：
- `evaluator/` → `backend/evaluator/`
- `repos_runner/` → `backend/repos_runner/`
- `webapp/` → `frontend/webapp/`
- `pages/` → `frontend/pages/`
- `oscanner/` → `cli/` - CLI 工具目录
- 所有 `*.sh` 脚本 → `scripts/`
- 项目文档 → `docs/`

### ✅ 2. 路径引用更新

**脚本文件**：
- ✅ `scripts/start_dev.sh` - 更新所有路径引用
- ✅ `scripts/stop_dev.sh` - 更新所有路径引用
- ✅ `scripts/start_production.sh` - 更新所有路径引用
- ✅ `scripts/deploy.sh` - 更新路径引用
- ✅ `scripts/deploy_remote.sh` - 更新路径引用
- ✅ `scripts/setup_remote_server.sh` - 更新路径引用
- ✅ `backend/repos_runner/start_server.sh` - 更新路径引用

**CLI 工具**：
- ✅ `oscanner/cli.py` - 更新服务路径和导入路径

**配置文件**：
- ✅ `pyproject.toml` - 更新包查找路径
- ✅ `.workflow/master-pipeline.yml` - 更新构建路径
- ✅ `.workflow/pr-pipeline.yml` - 更新构建路径
- ✅ `.workflow/branch-pipeline.yml` - 更新构建路径

**后端服务**：
- ✅ `backend/evaluator/server.py` - 添加 `sys.path` 调整，保持 `evaluator` 作为顶级包
- ✅ `backend/repos_runner/server.py` - 添加 `sys.path` 调整，保持 `repos_runner` 作为顶级包

**文档**：
- ✅ `README.md` - 更新目录结构说明
- ✅ `docs/ARCHITECTURE.md` - 创建详细的架构文档

## 新的目录结构

```
oscanner/
├── backend/                    # 后端服务
│   ├── evaluator/              # 主评估服务（端口 8000）
│   └── repos_runner/           # 仓库测试服务（端口 8001）
├── frontend/                   # 前端应用
│   ├── webapp/                 # Next.js 主应用（端口 3000）
│   └── pages/                  # GitHub Pages 静态站点
├── cli/                        # CLI 工具（可安装包）
├── plugins/                    # 插件系统
├── scripts/                    # 工具脚本
├── tests/                      # 测试
└── docs/                       # 文档
```

## 技术实现细节

### Python 包导入处理

由于 `evaluator` 和 `repos_runner` 被移动到 `backend/` 目录，但需要保持作为顶级包导入，采用了以下方案：

1. **服务器启动时自动调整路径**：
   ```python
   # backend/evaluator/server.py
   _backend_dir = Path(__file__).resolve().parent.parent
   if str(_backend_dir) not in sys.path:
       sys.path.insert(0, str(_backend_dir))
   ```

2. **pyproject.toml 配置**：
   ```toml
   [tool.setuptools.packages.find]
   where = ["."]
   include = ["oscanner*", "evaluator*", "repos_runner*"]
   ```

这样既保持了目录结构的清晰，又保持了代码导入的兼容性。

## 使用方式变化

### 启动服务

**之前**：
```bash
cd evaluator && python server.py
cd repos_runner && python server.py
cd webapp && npm run dev
```

**现在**：
```bash
# 方式 1：使用脚本（推荐）
./scripts/start_dev.sh

# 方式 2：使用 CLI
uv run oscanner dev

# 方式 3：手动启动
cd backend/evaluator && python server.py
cd backend/repos_runner && python server.py
cd frontend/webapp && npm run dev
```

### 环境变量文件位置

**之前**：
- `evaluator/.env.local`
- `repos_runner/.env.local`
- `webapp/.env.local`

**现在**：
- `backend/evaluator/.env.local`
- `backend/repos_runner/.env.local`
- `frontend/webapp/.env.local`

## 待测试项目

- [ ] 测试 `backend/evaluator` 服务启动
- [ ] 测试 `backend/repos_runner` 服务启动
- [ ] 测试 `frontend/webapp` 应用启动
- [ ] 测试 CLI 工具功能（`oscanner serve`, `oscanner dev`）
- [ ] 验证前后端连接
- [ ] 验证 Repository Runner 功能（如果使用）

## 注意事项

1. **环境变量文件**：如果已有 `.env.local` 文件，需要手动移动到新位置或重新创建
2. **虚拟环境**：`backend/repos_runner` 使用 `backend/evaluator/venv`，路径已更新
3. **CI/CD**：已更新所有 CI/CD 配置文件，但需要在实际运行中验证
4. **导入路径**：Python 代码中的导入路径保持不变（通过 `sys.path` 调整），无需修改代码

## 回滚方案

如果遇到问题需要回滚：

1. 使用 git 恢复文件位置：
   ```bash
   git checkout HEAD -- evaluator repos_runner webapp pages oscanner
   ```

2. 恢复脚本路径引用：
   ```bash
   git checkout HEAD -- start_*.sh stop_*.sh deploy*.sh
   ```

3. 恢复配置文件：
   ```bash
   git checkout HEAD -- pyproject.toml .workflow/*.yml
   ```

## 后续优化建议

1. **环境变量配置化**：将 `RepositoryRunner.tsx` 中的硬编码 API 地址改为环境变量
2. **统一启动脚本**：考虑创建一个统一的启动脚本，自动检测并启动所需服务
3. **文档完善**：补充各服务的详细使用文档
4. **测试覆盖**：添加目录结构相关的测试用例

## 相关文档

- [ARCHITECTURE.md](ARCHITECTURE.md) - 详细架构说明
- [README.md](../README.md) - 项目主文档
- [.ai/task/task_04_project_structure/task.md](../.ai/task/task_04_project_structure/task.md) - 重构任务文档
