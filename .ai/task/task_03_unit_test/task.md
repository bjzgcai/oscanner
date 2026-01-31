# 闭环描述

## 基础

1. 项目使用 `pytest` 作为单元测试框架
2. 测试目录位于 `tests/`，使用 `uv run pytest` 运行测试
3. 测试覆盖核心业务逻辑，确保代码质量和功能正确性

## 设计

### 目标资源：单元测试（Unit Test）

单元测试是一类“可执行、可验证、可维护”的资源，用于：
- **验证功能正确性**：确保代码按预期工作
- **防止回归**：新代码变更不会破坏现有功能
- **文档化行为**：测试用例作为代码行为的可执行文档
- **支持重构**：提供安全网，支持代码重构

### 测试生命周期（增/删/查/改）

#### 增（Create）- 添加新测试

- **新功能测试**：为新功能/模块添加对应的测试文件
  - 位置：`tests/<module_name>/test_<feature>.py`
  - 命名规范：`test_<functionality>.py`，测试类 `Test<Feature>`，测试方法 `test_<scenario>`
- **边界情况测试**：为现有功能补充边界条件、错误处理测试
- **集成测试**：为关键业务流程添加端到端测试（如 API 端点测试）

#### 查（Read/Discover）- 运行和查看测试

- **运行所有测试**：`uv run pytest`
- **运行特定测试**：`uv run pytest tests/<module>/test_<feature>.py`
- **查看覆盖率**：`uv run pytest --cov=evaluator --cov-report=html`
- **CI/CD 集成**：确保 CI 流程中包含测试执行

#### 改（Update/Evolve）- 更新和维护测试

- **同步代码变更**：当业务逻辑变更时，同步更新对应的测试
- **重构测试代码**：保持测试代码简洁、可读、可维护
- **优化测试性能**：减少不必要的 mock、优化测试执行时间
- **更新测试文档**：保持 `tests/README.md` 与测试结构同步

#### 删（Remove/Disable）- 清理过时测试

- **删除废弃功能测试**：当功能被移除时，删除对应的测试
- **合并重复测试**：识别并合并重复的测试用例
- **标记跳过测试**：对于暂时无法修复的测试，使用 `@pytest.mark.skip` 标记

### 测试目录结构

```
tests/
├── __init__.py              # 标记为 Python 包
├── conftest.py              # pytest 配置和共享 fixtures
├── README.md                # 测试说明文档
├── gitee_api/               # Gitee API 相关测试
│   ├── __init__.py
│   └── test_extraction.py   # Gitee 数据提取测试
├── github_api/              # GitHub API 相关测试（待补充）
│   └── test_extraction.py
├── evaluator/               # 评估服务测试（待补充）
│   ├── test_evaluation_service.py
│   ├── test_trajectory_service.py
│   └── test_extraction_service.py
├── routes/                  # API 路由测试（待补充）
│   ├── test_evaluation.py
│   ├── test_trajectory.py
│   └── test_config.py
├── collectors/              # 数据收集器测试（待补充）
│   ├── test_github.py
│   └── test_gitee.py
└── plugins/                 # 插件机制测试（待补充）
    └── test_plugin_registry.py
```

### 测试规范

#### 测试文件组织

- **按模块组织**：每个业务模块一个测试子目录
- **命名规范**：
  - 测试文件：`test_<feature>.py`
  - 测试类：`Test<Feature>`（使用类组织相关测试）
  - 测试方法：`test_<scenario>_<expected_behavior>`

#### 测试编写原则

1. **独立性**：每个测试应该独立运行，不依赖其他测试的执行顺序
2. **可重复性**：测试结果应该稳定，多次运行结果一致
3. **快速执行**：单元测试应该快速执行（避免真实网络请求、数据库操作等）
4. **Mock 外部依赖**：使用 `unittest.mock` 或 `pytest-mock` 模拟外部依赖
5. **清晰断言**：使用明确的断言消息，便于失败时定位问题

#### Mock 策略

- **网络请求**：所有 HTTP 请求必须 mock，避免真实 API 调用
- **文件系统**：使用临时目录（`tempfile`）进行文件操作测试
- **环境变量**：使用 `patch` 模拟环境变量
- **时间相关**：使用 `freezegun` 或 mock 时间函数

#### 测试覆盖率目标

- **核心业务逻辑**：目标覆盖率 ≥ 80%
- **关键路径**：100% 覆盖（错误处理、边界条件）
- **工具函数**：≥ 70% 覆盖

### 当前测试覆盖情况

#### 已实现

- ✅ Gitee API 数据提取测试（`tests/gitee_api/test_extraction.py`）
  - DNS 解析测试
  - Token 验证测试
  - 网络错误处理测试
  - API 错误处理测试
  - 超时处理测试

#### 待补充（优先级排序）

1. **GitHub API 提取测试**（高优先级）
   - 数据提取流程测试
   - 错误处理测试
   - Token 验证测试

2. **评估服务测试**（高优先级）
   - `evaluation_service.py` 核心逻辑测试
   - `trajectory_service.py` 成长轨迹分析测试
   - 缓存机制测试

3. **API 路由测试**（中优先级）
   - `/api/evaluate` 端点测试
   - `/api/trajectory` 端点测试
   - `/api/config` 端点测试
   - 错误响应格式测试

4. **数据收集器测试**（中优先级）
   - `collectors/github.py` 测试
   - `collectors/gitee.py` 测试
   - 缓存机制测试

5. **插件机制测试**（中优先级）
   - 插件注册与发现测试
   - 插件加载与执行测试
   - 插件元数据验证测试

6. **工具函数测试**（低优先级）
   - `utils/commit_utils.py` 测试
   - `utils/repo_parser.py` 测试
   - `paths.py` 路径处理测试

### CI/CD 集成

- **自动运行测试**：每次 PR 和 main 分支推送时自动运行测试
- **覆盖率报告**：生成并上传覆盖率报告
- **测试失败阻断**：测试失败时阻止合并

# TODO_LIST

> 只维护最新版本；完成后清空 TODO，仅保留"完成记录 + 日期"。
- （进行中，持续补充和完善测试覆盖）

## 当前待办

### 高优先级

- [x] 添加 GitHub API 提取测试（`tests/github_api/test_extraction.py`）✅ 2026-01-28
  - [x] 测试 `extract_github_data()` 函数
  - [x] 测试网络错误处理
  - [x] 测试 Token 验证
  - [x] 测试超时处理
  - [x] 测试 `fetch_github_commits()` 函数

- [x] 添加评估服务测试（`tests/evaluator/test_evaluation_service.py`）✅ 2026-01-28
  - [x] 测试 `get_or_create_evaluator()` 函数
  - [x] 测试 `evaluate_author_incremental()` 核心逻辑
  - [x] 测试 LLM 调用错误处理
  - [x] 测试增量评估逻辑
  - [x] 测试 `get_empty_evaluation()` 函数

- [x] 添加成长轨迹服务测试（`tests/evaluator/test_trajectory_service.py`）✅ 2026-01-28
  - [x] 测试轨迹缓存加载和保存
  - [x] 测试 `get_commits_by_date()` 函数
  - [x] 测试 `ensure_repo_data_synced()` 函数
  - [x] 测试错误处理

### 中优先级

- [ ] 添加 API 路由测试（`tests/routes/`）
  - [ ] 测试 `/api/evaluate` 端点
  - [ ] 测试 `/api/trajectory` 端点
  - [ ] 测试 `/api/config` 端点
  - [ ] 测试错误响应格式

- [ ] 添加数据收集器测试（`tests/collectors/`）
  - [ ] 测试 GitHub 收集器
  - [ ] 测试 Gitee 收集器
  - [ ] 测试缓存机制

- [ ] 添加插件机制测试（`tests/plugins/`）
  - [ ] 测试插件注册与发现
  - [ ] 测试插件加载
  - [ ] 测试插件执行

### 低优先级

- [ ] 添加工具函数测试（`tests/utils/`）
  - [ ] 测试 `commit_utils.py`
  - [ ] 测试 `repo_parser.py`
  - [ ] 测试 `paths.py`

### 基础设施

- [ ] 设置 CI/CD 自动运行测试
- [ ] 配置覆盖率报告生成
- [ ] 添加测试性能监控（识别慢测试）

## 维护原则

1. **新功能必须带测试**：添加新功能时，同步添加对应的测试
2. **测试先行**：对于复杂功能，考虑 TDD（测试驱动开发）
3. **定期审查**：定期审查测试覆盖率，识别测试盲点
4. **保持测试简洁**：避免过度复杂的测试，保持可读性
5. **及时更新**：代码变更时，同步更新相关测试
