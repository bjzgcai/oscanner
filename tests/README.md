# Tests

This directory contains test cases for the oscanner project.

## Structure

- `gitee_api/` - Tests for Gitee API extraction and DNS handling
- `github_api/` - Tests for GitHub API extraction and error handling
- `evaluator/` - Tests for evaluation and trajectory services

## Running Tests

### 前置条件

**重要**：运行测试前需要先安装项目依赖（包括开发依赖）。

#### 使用 uv（推荐）

如果使用 `uv` 管理依赖（项目包含 `uv.lock` 文件），应使用 `uv run pytest` 运行测试：

```bash
# 安装项目（开发模式）及开发依赖
uv pip install -e ".[dev]"

# 使用 uv run 运行测试（确保使用正确的虚拟环境）
uv run pytest

# 运行特定测试文件
uv run pytest tests/gitee_api/test_extraction.py -v

# 运行所有测试并显示详细信息
uv run pytest -v
```

**为什么使用 `uv run`？**
- `uv run` 自动使用 uv 管理的虚拟环境
- 直接运行 `pytest` 可能使用不同的 Python 环境（系统 Python 或 conda base）
- 确保与 `uv run oscanner dev` 使用相同的环境

#### 使用 pip/virtualenv

如果使用传统的 pip/virtualenv：

```bash
# 先激活虚拟环境
source .venv/bin/activate  # 或你的 venv 路径

# 安装项目（开发模式）及开发依赖
pip install -e ".[dev]"

# 然后运行测试
pytest tests/gitee_api/test_extraction.py -v
```

**注意**：测试会导入 `evaluator.services.extraction_service`，需要 `fastapi` 等依赖。请确保所有依赖都安装在同一个环境中。

### 运行所有测试

```bash
# 使用 uv（推荐，如果使用 uv 管理依赖）
uv run pytest

# 或使用传统 pip/virtualenv（激活 venv 后）
pytest
```

### 运行特定测试文件

```bash
uv run pytest tests/gitee_api/test_extraction.py
# 或（如果 venv 已激活）
pytest tests/gitee_api/test_extraction.py
```

### 运行特定测试类

```bash
uv run pytest tests/gitee_api/test_extraction.py::TestDNSResolution
```

### 运行特定测试方法

```bash
uv run pytest tests/gitee_api/test_extraction.py::TestDNSResolution::test_dns_resolution_success
```

### 显示详细输出

```bash
uv run pytest -v
```

### 生成覆盖率报告

```bash
uv run pytest --cov=evaluator --cov-report=html
```

## Test Coverage

### Gitee API Tests (`gitee_api/test_extraction.py`)

1. **DNS Resolution** (`TestDNSResolution`)
   - Successful DNS resolution
   - DNS resolution failure
   - DNS hijacking detection (baiduads.com)
   - Normal DNS resolution without hijacking

2. **Gitee Extraction** (`TestGiteeExtraction`)
   - Token validation (required)
   - DNS failure handling
   - Network error handling
   - Timeout error handling
   - API error handling (non-200 status codes)
   - Verification that Gitee API host gitee.com is used

### GitHub API Tests (`github_api/test_extraction.py`)

1. **GitHub Extraction** (`TestGitHubExtraction`)
   - Successful data extraction
   - Extraction without token
   - Subprocess failure handling
   - Timeout handling
   - Exception handling

2. **GitHub Commits Fetch** (`TestGitHubCommitsFetch`)
   - Successful commits fetch
   - Fetch without token
   - API error handling (401, etc.)
   - Network error handling
   - Timeout handling

### Evaluation Service Tests (`evaluator/test_evaluation_service.py`)

1. **Evaluator Creation** (`TestGetOrCreateEvaluator`)
   - Successful evaluator creation
   - Missing LLM key handling

2. **Incremental Evaluation** (`TestEvaluateAuthorIncremental`)
   - First evaluation (no previous)
   - Incremental evaluation with previous results
   - No commits for author
   - No new commits since last evaluation
   - Missing evaluator factory
   - LLM evaluation errors

3. **Empty Evaluation** (`TestGetEmptyEvaluation`)
   - Empty evaluation for user with no commits

### Trajectory Service Tests (`evaluator/test_trajectory_service.py`)

1. **Trajectory Cache** (`TestTrajectoryCache`)
   - Loading non-existent cache
   - Loading existing cache
   - Invalid JSON handling
   - Saving cache

2. **Commits by Date** (`TestGetCommitsByDate`)
   - Getting commits grouped by date
   - No matching commits
   - No repository data

3. **Repository Data Sync** (`TestEnsureRepoDataSynced`)
   - Successful GitHub sync
   - Successful Gitee sync
   - Extraction failure
   - Network error handling
   - Unsupported platform

## Notes

- Tests use mocking to avoid actual network calls
- Tests verify error messages and exception handling
- All tests can be run with `uv run pytest`
