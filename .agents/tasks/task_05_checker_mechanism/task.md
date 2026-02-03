# 闭环描述

## 基础

1. 插件系统（`plugins/`）已实现，插件通过 `scan/__init__.py` 的 `CommitEvaluatorModerate` 评估提交
2. 评估流程：插件从 commit message、文件内容、repo 结构构建上下文，调用 LLM 进行评分
3. 后端提供 `/api/evaluate` 等接口，支持插件化评估

## 设计

### 目标资源：Checker（代码质量检测器）

Checker 是一类"可被后端发现、可被插件动态调用、可扩展"的资源，用于：
- **代码质量检测**：对特定 commit 的代码执行自动化检测（如圈复杂度、代码规范等）
- **元数据管理**：checker id、名称、描述、执行入口等
- **结果集成**：检测结果以 JSON 格式返回，被插件评估上下文使用，影响检查点评分

### 分析闭环：Checker 的"全部环节"与责任边界

> 目标：从 commit message 中识别 checker 需求 → 执行检测 → 结果集成到评估上下文的完整流程。

#### Checker 发现与调用流程

1. **Checker 注册（后端固化）**
   - 后端扫描 `checkers/checker_list.yaml`，发现所有可用 checker
   - 提供 API `/api/checkers/list` 返回 checker 清单（id、name、description、keyword 等）

2. **Commit Message 解析（插件化）**
   - 插件在 `CommitEvaluatorModerate._build_commit_context` 中解析 commit message
   - 提取 `/check:xxx` 或 `/checker:xxx` 格式的关键字（如 `/checker:ccn`）
   - 匹配 checker_list 中的 keyword，确定需要执行的 checker

3. **Checker 执行请求（插件 → 后端）**
   - 插件调用后端 API `/api/checkers/run`，传递：
     - `checker_id`: checker 标识
     - `platform`, `owner`, `repo`: 仓库信息
     - `commit_sha`: 目标 commit SHA
     - `files`: 可选，指定检测的文件列表（默认检测该 commit 涉及的所有文件）
     - `worktree_base`: 可选，工作目录位置（`'build'` 或 `'temp'`，默认 `'build'`）
       - `'build'`: 在项目根目录的 `build/worktrees/` 下创建 worktree（便于调试）
       - `'temp'`: 在系统临时目录创建 worktree（自动清理）

4. **Checker 执行（后端固化）**
   - 后端接收请求后：
     - 加载对应 checker 目录的 Python 代码
     - **自动安装依赖**：如果 checker 目录存在 `requirements.txt`，自动安装依赖
     - **Git 仓库管理**：
       - 检查 `data_dir/repo/` 是否存在 git 仓库
       - 如果不存在，使用浅层克隆（depth=1）创建 git 仓库
       - 使用 git worktree 创建隔离的工作目录，checkout 到目标 commit
     - 调用 checker 的 `run_checker(commit_sha, files, data_dir, worktree_path=worktree_path)` 方法
     - 返回检测结果 JSON
     - 清理临时 worktree（如果使用临时目录）

5. **结果集成（插件化）**
   - 插件将 checker 结果添加到评估上下文
   - 在 `_build_commit_context` 中追加 checker 结果摘要
   - LLM 评估时可以看到 checker 检测结果，影响评分

6. **检查点评分（插件化）**
   - 在检查点评估时，所有相关 commit 的 checker 结果被汇总
   - 插件根据 checker 结果调整评分（例如：圈复杂度达标率影响代码质量维度）

#### 哪些环节"固化在后端"，哪些"被插件化"（总览）

- **后端固化（core，不随插件变化）**
  - checker 发现机制（扫描 `checkers/checker_list.yaml`）
  - checker 执行接口（`/api/checkers/list`, `/api/checkers/run`）
  - checker 代码加载与执行（动态 import checker 模块）
  - **checker 依赖自动安装**（从 `checkers/<id>/requirements.txt`）
  - **Git 仓库管理**：
    - 浅层克隆（depth=1，最小化数据传输）
    - Git worktree 创建与管理（确保检查特定 commit 版本）
    - 工作目录隔离（支持并发执行多个 checker）
  - commit 代码快照获取（通过 worktree 或 data_dir）
  - checker 结果 JSON 格式验证

- **插件化（per plugin，可替换/可演进）**
  - commit message 解析策略（如何提取 `/check:xxx`）
  - checker 结果如何集成到评估上下文（格式、摘要方式）
  - checker 结果如何影响评分（权重、计算方式）

### 生命周期（增/删/查/改）

- **增（Create）**
  - 在根目录 `checkers/<checker_id>/` 创建 checker 目录
  - 提供 `checker.py` 实现（必须导出 `run_checker(commit_sha, files, data_dir) -> dict`）
  - 在 `checkers/checker_list.yaml` 中注册元数据（id、name、keyword、description 等）

- **查（Read/Discover）**
  - 后端在启动/运行时扫描 `checkers/checker_list.yaml`，构建 checker registry
  - 提供 API `/api/checkers/list` 返回 checker 清单，供插件查询

- **改（Update/Evolve）**
  - 允许新增 checker、升级 checker 版本
  - 允许修改 checker 检测逻辑（不影响接口契约）

- **删（Remove/Disable）**
  - checker 目录被删除/缺失时，后端 registry 自动不返回该 checker
  - 若请求了不存在 checker，后端返回明确错误并提示可用 checker 列表

### Checker 目录规范

```
checkers/
├── checker_list.yaml          # Checker 元数据清单（必读）
├── ccn/                       # 圈复杂度检测器（示例）
│   ├── checker.py            # Checker 实现（必须导出 run_checker）
│   ├── requirements.txt      # Python 依赖（如 lizard>=1.17.0），自动安装
│   └── README.md             # 可选：Checker 说明文档
└── <checker_id>/             # 其他 checker
    ├── checker.py
    ├── requirements.txt      # 可选：Python 依赖，自动安装
    └── ...
```

**依赖管理**：
- 如果 checker 目录存在 `requirements.txt`，后端会在加载 checker 时自动安装依赖
- 使用 `pip install -q -r requirements.txt` 安装，失败时打印警告但不阻止 checker 加载

#### checker_list.yaml 格式

```yaml
checkers:
  - id: ccn
    name: Cyclomatic Complexity Checker
    keyword: ccn                    # commit message 中匹配的关键字（/checker:ccn）
    description: Check cyclomatic complexity of functions (threshold: 20)
    entry: checker.py              # 默认 checker.py
    version: 1.0.0
    enabled: true
```

#### checker.py 接口契约

每个 checker 必须实现：

```python
def run_checker(
    commit_sha: str,
    files: Optional[List[str]],
    data_dir: Path,
    worktree_path: Optional[Path] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    执行检测并返回结果。
    
    Args:
        commit_sha: 目标 commit SHA
        files: 可选，指定检测的文件列表（None 表示检测该 commit 涉及的所有文件）
        data_dir: 仓库数据目录（包含 commits、files 等）
        worktree_path: 可选，git worktree 路径，指向已 checkout 到 commit_sha 的工作目录。
                      如果提供，checker 应优先使用此路径中的代码进行分析，确保检查的是
                      特定 commit 版本的代码，而不是当前仓库状态。
        **kwargs: 其他可选参数
    
    Returns:
        {
            "success": bool,
            "score": float,          # 0-100 的得分（达标比例 * 100）
            "passed": int,          # 通过检测的数量
            "total": int,           # 总检测数量
            "details": [...],       # 详细检测结果
            "message": str,         # 可读的检测结果摘要
            "analysis": str,        # 可选：详细分析报告
            "error": str            # 可选：错误信息
        }
    """
    pass
```

**重要说明：**
- `worktree_path` 参数用于确保 checker 分析的是**特定 commit 版本的代码**，而不是当前仓库状态
- 如果 `worktree_path` 提供，checker 应优先使用此路径中的文件进行分析
- 如果 `worktree_path` 为 None，checker 可以从 `data_dir` 中获取文件内容（向后兼容）

### 共享契约（给 checker 开发者的"明确输入/输出"）

> 目标：checker 开发者不需要阅读插件或后端实现，也能清楚知道：
> 1) `checker.py` 收到什么输入，必须返回什么输出；2) 如何获取 commit 代码快照。

#### Checker 输入/输出契约

- **输入**：
  - `commit_sha`: 目标 commit SHA（字符串）
  - `files`: 可选的文件列表（None 或 `List[str]`），None 表示检测该 commit 涉及的所有文件
  - `data_dir`: `Path` 对象，指向仓库数据目录（包含 `commits_list.json`、`files/` 等）

- **输出**：
  - 必须返回包含以下字段的 dict：
    - `success`: bool（检测是否成功执行）
    - `score`: float（0-100 的得分，通常表示达标比例 * 100）
    - `passed`: int（通过检测的数量）
    - `total`: int（总检测数量）
    - `details`: List[dict]（详细检测结果，每个元素包含文件、函数、检测结果等）
    - `message`: str（可读的检测结果摘要，用于集成到评估上下文）
    - `error`: str（可选，错误信息）

- **代码快照获取**：
  - **推荐方式**：使用 `worktree_path` 参数，后端会通过 git worktree 创建隔离的工作目录，
    已 checkout 到目标 commit，checker 直接分析此路径中的代码
  - **兼容方式**：如果 `worktree_path` 为 None，checker 可以从 `data_dir/files/` 或
    `data_dir/commits/<commit_sha>/files/` 获取文件内容
  - **Git 仓库管理**：后端会自动处理 git 仓库的克隆（浅层克隆，depth=1）和 worktree 创建，
    checker 无需关心 git 操作细节

### 插件集成契约

插件在 `CommitEvaluatorModerate` 中集成 checker 结果：

1. **查询 checker 清单**：
   ```python
   # 调用后端 API
   checkers_list = requests.get(f"{api_base}/api/checkers/list").json()
   ```

2. **解析 commit message**：
   ```python
   # 从 commit message 中提取 /checker:xxx
   checker_keywords = extract_checker_keywords(commit_message)
   ```

3. **执行 checker**：
   ```python
   # 对每个匹配的 checker，调用后端执行
   checker_results = []
   for keyword in checker_keywords:
       checker_id = find_checker_by_keyword(checkers_list, keyword)
       result = requests.post(f"{api_base}/api/checkers/run", json={
           "checker_id": checker_id,
           "platform": platform,
           "owner": owner,
           "repo": repo,
           "commit_sha": commit_sha,
           "files": None  # 或指定文件列表
       }).json()
       checker_results.append(result)
   ```

4. **集成到上下文**：
   ```python
   # 在 _build_commit_context 中追加 checker 结果
   checker_summary = format_checker_results(checker_results)
   context += f"\n\n## Code Quality Checker Results\n{checker_summary}"
   ```

### 第一个 Checker 实现：CCN（圈复杂度）

- **Checker ID**: `ccn`
- **关键字**: `ccn`（commit message 中 `/checker:ccn`）
- **工具**: `lizard`（Python 圈复杂度分析工具）
- **依赖**: `lizard>=1.17.0`（在 `checkers/ccn/requirements.txt` 中定义，自动安装）
- **检测逻辑**：
  - 使用 `lizard` Python API（`lizard.analyze_file()`）分析 commit 涉及的所有 Python 文件
  - **注意**：使用 Python API 而非 CLI，因为 CLI 不支持 `--json` 参数
  - 检测每个函数的圈复杂度（Cyclomatic Complexity Number）
  - 阈值：圈复杂度 ≤ 20
  - 得分计算：`(通过检测的函数数 / 总函数数) * 100`
  - **支持 worktree_path**：如果提供，优先分析 worktree 中的代码，确保检查特定 commit 版本
- **返回结果示例**：
  ```json
  {
    "success": true,
    "score": 85.5,
    "passed": 47,
    "total": 55,
    "details": [
      {
        "file": "src/main.py",
        "function": "process_data",
        "complexity": 15,
        "nloc": 20,
        "line": 10,
        "parameters": ["data"],
        "passed": true
      },
      {
        "file": "src/utils.py",
        "function": "complex_logic",
        "complexity": 25,
        "nloc": 45,
        "line": 30,
        "parameters": ["x", "y"],
        "passed": false
      }
    ],
    "message": "47/55 functions passed complexity check (threshold: 20). 8 functions exceeded threshold.",
    "analysis": "Cyclomatic Complexity Analysis Report (Threshold: 20)\n..."
  }
  ```

## 实现

### 验收标准（Definition of Done）

- ✅ 后端提供 `/api/checkers/list` 接口，返回 checker 清单（从 `checkers/checker_list.yaml` 读取）
- ✅ 后端提供 `/api/checkers/run` 接口，支持执行指定 checker 并返回 JSON 结果
- ✅ **Checker 依赖自动安装**：加载 checker 时自动安装 `requirements.txt` 中的依赖
- ✅ `checkers/ccn/checker.py` 实现圈复杂度检测，使用 `lizard` Python API，阈值 20
- ✅ `checkers/checker_list.yaml` 包含 `ccn` checker 的元数据
- ✅ **Git worktree 支持**：
  - 后端自动创建 git worktree，确保检查特定 commit 版本的代码
  - 支持浅层克隆（depth=1）最小化数据传输
  - 支持并发执行（每个 checker 使用独立的 worktree）
- ✅ 插件 `CommitEvaluatorModerate` 能够：
  - 从 commit message 中提取 `/checker:xxx` 关键字
  - 查询 checker 清单并匹配可用 checker
  - 调用后端 API 执行 checker（支持 `worktree_base` 参数）
  - 将 checker 结果集成到评估上下文（包括失败结果）
- ✅ 检查点评估时，checker 结果被正确汇总并影响评分
- ✅ **前端工作目录选项**：支持选择 worktree 创建位置（build 目录或临时目录）
- ✅ **单元测试**：`tests/checkers/test_ccn_checker.py` 验证 lizard API 使用
- ✅ **单元测试**：`tests/routes/test_checkers.py` 验证浅层克隆功能
- 可验证性：
  - 后端日志打印 `[Checker] Running checker=ccn for commit=...`
  - 后端日志打印 `[GitWorktree] Creating worktree at: ...`
  - 插件评估上下文包含 checker 结果摘要（包括失败信息）
  - 检查点评分反映 checker 检测结果
  - 前端显示 checker 评估结果（包括失败情况）
- checker 开发者可读性：
  - `checkers/ccn/README.md` 说明如何使用和扩展
  - checker 接口契约清晰（输入/输出格式，包括 `worktree_path` 参数）
  - 单元测试作为使用示例

# TODO_LIST

> 只维护最新版本；完成后清空 TODO，仅保留"完成记录 + 日期"。

## 完成记录

- 2026-02-02：完成 checker 机制核心实现
  - ✅ 创建 `checkers/` 目录结构和 `checker_list.yaml` 格式定义
  - ✅ 实现后端 checker registry（`backend/evaluator/checker_registry.py`）
  - ✅ 实现 `/api/checkers/list` 和 `/api/checkers/run` 接口（`backend/evaluator/routes/checkers.py`）
  - ✅ 实现 checker 代码加载机制（动态 import `checkers/<id>/checker.py`）
  - ✅ **实现 checker 依赖自动安装**（`install_checker_requirements()` 函数）
  - ✅ 创建 `checkers/ccn/` checker（使用 `lizard` Python API 检测圈复杂度，阈值 20）
  - ✅ 在 `CommitEvaluatorModerate` 中集成 checker 功能（两个插件均已更新）
  - ✅ 插件支持从 commit message 提取 `/checker:xxx` 并执行检测
  - ✅ Checker 结果集成到评估上下文，影响 LLM 评分
  - ✅ **实现 Git worktree 支持**（`backend/evaluator/utils/git_worktree.py`）
    - 确保 checker 检查特定 commit 版本的代码，而非当前仓库状态
    - 支持并发执行多个 checker（每个 checker 使用独立的 worktree）
  - ✅ **实现浅层克隆优化**（`clone_repo_shallow()` 函数）
    - 使用 `--depth 1` 最小化数据传输
    - Fetch 失败时回退到 `--depth 10`（不再使用 unshallow）
  - ✅ **修复 lizard 集成问题**
    - 从 CLI `--json` 参数改为使用 Python API `lizard.analyze_file()`
    - 添加单元测试验证修复（`tests/checkers/test_ccn_checker.py`）
  - ✅ **增强错误处理**
    - Checker 失败时（`success=False`）结果也会传递给前端显示
    - 超时时间优化（checker API: 60s → 120s，git 操作: 30s → 60s）
  - ✅ **前端工作目录选项**
    - 添加"工作目录"下拉选项（服务build子目录 / 临时目录）
    - 支持通过 `worktree_base` 参数控制 worktree 创建位置
