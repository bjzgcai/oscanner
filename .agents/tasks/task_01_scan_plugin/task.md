# 闭环描述

## 基础

1. evaluator/ 后端提供了针对 repo 的扫描能力
2. webapp/ 前端提供了扫描功能并支持输入1-N个repo开始扫描并展示扫描结果

## 设计

### 目标资源：Scan Plugin（扫描分析引擎插件）

一个 Scan Plugin 是一类“可被后端发现、可被前端选择、可替换/可演进”的资源，用于定义：
- **扫描/评估策略**：同一份 repo 数据，用不同标准（rubric）给出不同维度/结论
- **元数据**：插件 id、名称、版本、默认插件等
- **可选的前端 view**：将插件的输出结果用定制 UI 展示（第一版允许留空）

### 分析闭环：单 repo / 多 repo 的“全部环节”与责任边界

> 目标：无论单 repo 还是多 repo，用户输入 → 产出结果的所有环节都要可枚举、可定位；并明确哪些逻辑固化在后端，哪些被插件化。

#### 单 repo（SingleRepoAnalysis）端到端流程

1. **输入解析（前端固化）**
  - 用户输入 repo（URL / owner/repo / path 等），前端解析出 `platform/owner/repo`。
2. **数据准备（后端固化）**
  - 若本地数据不存在：触发抓取/抽取 commits（GitHub/Gitee），落地到 data_dir。
  - 若存在：使用本地 commits（可选择 auto-sync）。
  - 这一层与插件无关：平台 API、限流、增量同步都属于后端固化能力。
3. **作者列表/候选贡献者（后端固化）**
  - 从本地 commits 构建作者/邮箱列表，供前端选择。
4. **评估请求（前端固化 + 可配置参数）**
  - 选择 author + 选择 plugin + cache toggle + model 等，调用后端评估接口（如 `/api/evaluate`）。
5. **插件选择与加载（后端固化，但依据插件目录动态）**
  - 后端 `plugin_registry` 扫描 `plugins/*/index.yaml` → 得到可用插件与默认插件。
  - 根据请求 `plugin=<id>` 决定实际使用的插件（未传则默认）。
6. **评估执行（插件化：scan）**
  - 后端通过插件的 `scan_entry` 动态 import scan module，并调用其 `create_commit_evaluator(...)` / `evaluate_engineer(...)`。
  - **这里是核心插件化点**：维度定义、prompt/rubric、LLM 调用策略（是否允许 fallback）、输出结构细节（在“兼容字段”约束内）都由插件 scan 决定。
7. **缓存（后端固化 + 按插件隔离）**
  - 后端负责缓存读写与命中控制（`use_cache`）。
  - 缓存 key 必须包含 plugin id（避免不同 rubric 互相覆盖）。
8. **响应与可验证性（后端固化）**
  - 响应中必须包含：`plugin` / `plugin_version` / `plugin_scan_path`，用于确认“后端确实执行了哪个插件 scan 代码”。
9. **结果渲染（插件化：view + 固化 fallback）**
  - 若插件提供 `view/single_repo.tsx`：前端动态加载该组件渲染结果（插件化）。
  - 若缺失/加载失败：使用 webapp 内置 fallback（雷达图 + cards + markdown）（前端固化）。

##### 单 repo 前端渲染闭环（必须可解释/可验收）

> 目标：用户在页面上能明确看到“渲染用了哪个插件 view”，并且当插件 view 不存在/加载失败时有稳定回退。

- **入口组件（固化）**：`webapp/components/SingleRepoAnalysis.tsx`
- **渲染决策（固化）**：
  - 当拿到后端返回的 `evaluation` 后：
    1. 读取当前 UI 选择的 `pluginId`（来自 `AppSettingsContext`）
    2. 调用 `PluginViewRenderer(pluginId, evaluation, fallback)`
    3. `PluginViewRenderer` 仅负责“按 pluginId 动态 import 插件 view 并渲染”，不做业务聚合
- **插件可提供的渲染部分（插件化）**：
  - `plugins/<id>/view/single_repo.tsx`：**仅负责**把 `evaluation` 渲染成插件特有 UI
  - 必须在 UI 明显位置显示：`PLUGIN VIEW ACTIVE` + `plugin id` + `plugin_version`（或至少 id）
- **回退渲染（固化）**：
  - 当插件 view 缺失/加载失败：渲染 fallback（雷达图/维度卡片/markdown reasoning）
  - 回退视图的存在确保“插件 view 可选，但产品可用性不被插件破坏”

#### 多 repo（MultiRepoAnalysis）端到端流程

多 repo 分两条用户路径：

**A) 单仓评估卡片（multi 页面里选一个 repo/作者做评估）**
- 流程与“单 repo”一致（只是 UI 在 MultiRepo 页面内），因此：
  - **评估执行仍由插件 scan 决定**
  - **渲染用 `view/single_repo.tsx`**

**B) 跨仓对比（compare contributor across repos）**
1. **输入解析（前端固化）**
  - 用户输入 N 个 repos，选择 contributor（以及可选 aliases）。
2. **数据准备（后端固化）**
  - 对每个 repo：检查本地数据 → 必要时实时抽取/同步。
3. **逐仓评估（插件化：scan；后端负责调度）**
  - 后端对每个 repo 调用“单仓评估接口/逻辑”，并把同一个 `plugin=<id>` 传下去，确保所有 repo 使用一致的评估策略。
4. **聚合/对齐（后端固化）**
  - 将每个 repo 的评估结果抽取为对比所需结构（scores、commits_summary、total_commits 等），计算 aggregate（均值、总 commits 等）。
  - 如果某个 repo 失败（抽取失败/评估失败），写入 `failed_repos` 但不影响其他 repo 成功的结果。
5. **对比渲染（插件化：view + 固化 fallback）**
  - 若插件提供 `view/multi_repo_compare.tsx`：动态加载该组件渲染 compare（插件化）。
  - 否则回退到 webapp 固化的 `ContributorComparison`（前端固化）。

##### 多 repo 前端渲染闭环（必须可解释/可验收）

> 多 repo 页面有两块“结果渲染”，都需要闭环清楚，并明确插件能替换哪一块。

**1) multi 页面的单仓评估卡片渲染**
- **入口组件（固化）**：`webapp/components/MultiRepoAnalysis.tsx`（single 模式下的 evaluation card）
- **渲染决策（固化）**：
  - 与单 repo 完全一致：`PluginViewRenderer(pluginId, evaluation, loading, error)`
- **前端插件注册（自动生成，固化机制）**
  - `webapp/components/generated/pluginViewMap.ts` **不是手写文件**，由脚本自动生成：
    - 生成脚本：`webapp/scripts/gen-plugin-view-map.mjs`
    - 扫描来源：仓库根目录 `plugins/*/index.yaml`
    - 使用字段：`id` / `view_single_entry` / `view_compare_entry`（并检查对应文件存在）
    - 生成内容：把上述信息转成静态 `import()` 映射（Next.js 可打包），供 `PluginViewRenderer/PluginComparisonRenderer` 读取
  - 触发时机（webapp scripts）：`predev` / `prebuild` / `prestart` / `prelint`（启动/构建/生产启动/lint 前都会生成一次）
  - 插件开发者只需要在 `plugins/<id>/` 下提供目录与 `index.yaml + view/*.tsx`，无需改 webapp 源码注册
- **插件可提供的渲染部分（插件化）**：
  - 同样使用 `plugins/<id>/view/single_repo.tsx`

**2) compare 对比区域渲染**
- **入口组件（固化）**：`webapp/components/MultiRepoAnalysis.tsx`（compare 视图下）
- **渲染决策（固化）**：
  - 当拿到后端 `comparisonData` 后：
    1. 读取当前 UI 选择的 `pluginId`
    2. 调用 `PluginComparisonRenderer(pluginId, data, loading, error)`
    3. `PluginComparisonRenderer` 仅负责动态加载插件的 `view/multi_repo_compare.tsx` 并渲染
- **插件可提供的渲染部分（插件化）**：
  - `plugins/<id>/view/multi_repo_compare.tsx`：**仅负责**包装/渲染 compare 数据（可以复用 fallback 图表或完全自定义）
  - 必须在 UI 明显位置显示：`MULTI-REPO COMPARE VIEW ACTIVE` + `plugin id` + `plugin_version`（或至少 id）
- **回退渲染（固化）**：
  - 当插件 compare view 缺失/加载失败：渲染 `ContributorComparison`（固化）

#### 插件“提供哪些渲染插件 view”（最终约束）

插件前端 view 的责任边界只包含两类可替换视图，其余 UI 均由 webapp 固化：

- **必须可选、不可破坏**：插件 view 缺失/失败时必须自动回退到固化视图
- **插件可提供（可选）**
  - `view/single_repo.tsx`：单仓评估结果视图（SingleRepoAnalysis + MultiRepo 单仓卡片）
  - `view/multi_repo_compare.tsx`：多仓对比视图（MultiRepo compare）
- **webapp 固化（不插件化）**
  - 输入/校验/历史记录、repo 列表与选择、作者列表与选择、下载 PDF、错误态与 loading、表格/筛选 UI
  - 插件下拉框与 cache toggle（全局设置）

#### 哪些环节“固化在后端”，哪些“被插件化”（总览）

- **后端固化（core，不随插件变化）**
  - repo/platform 输入规范与数据目录组织
  - GitHub/Gitee 抽取/同步、限流处理与错误上抛语义
  - commits/作者聚合、compare 调度与聚合统计
  - 缓存机制与缓存隔离（按 plugin）
  - API 契约（参数：plugin/use_cache/model；响应：plugin_version/plugin_scan_path 等可验证字段）
  - 插件发现/元数据解析（扫描 `plugins/*/index.yaml`）
- **插件化（per plugin，可替换/可演进）**
  - **scan（Python）**：维度定义、rubric、prompt、LLM 调用策略、解析与评分逻辑（在“至少包含兼容的六维 scores + reasoning”的约束内）
  - **view（TSX）**：
    - `view/single_repo.tsx`：单仓分析结果展示
    - `view/multi_repo_compare.tsx`：多仓对比展示
  - 插件元数据：name/version/description/default + view entrypoints

### 生命周期（增/删/查/改）

- **增（Create）**
  - 在根目录 `plugins/<plugin_id>/` 创建插件目录
  - 提供 `index.yaml` 元数据（后端用于发现与路由；前端通过后端 API 获取元数据）
  - 提供 `scan/` Python 实现（后端运行扫描/评估）
  - （可选）提供 `view/` 前端实现（供 webapp 动态加载，第一版可空）

- **查（Read/Discover）**
  - 后端在启动/运行时扫描 `plugins/*/index.yaml`，构建 registry
  - 提供 API 返回插件列表与默认插件，供前端渲染“插件选择器”

- **改（Update/Evolve）**
  - 允许新增插件/升级插件版本
  - 允许在不破坏现有默认行为的前提下，让扫描接口支持 `plugin=<id>` 参数选择策略
  - **缓存隔离**：不同插件的评估结果缓存应隔离，避免不同 rubric 的结果互相覆盖

- **删（Remove/Disable）**
  - 插件目录被删除/缺失时，后端 registry 自动不返回该插件
  - 若请求了不存在插件，后端返回明确错误并提示可用插件列表

### 插件目录规范

1. 设计扫描分析引擎的插件机制，满足：
  - 在根目录的 `plugins/` 目录下，每个插件一个子目录，例如：
    - `plugins/zgc_simple`：把当前默认扫描能力（moderate evaluator）沉淀为默认插件
    - `plugins/zgc_ai_native_2026`：以 `engineer_level.md` 为 rubric 的扫描实现（第一版先做到“可跑 + 有初步差异化输出”）
2. `plugins/` 目录结构（包含共享契约 `_shared/`；view 第一版可空）：

```
plugins/
├── _shared
│   ├── scan
│   │   └── README.md               # 【必读】scan 插件契约：输入/输出/函数约定（给插件开发者）
│   └── view
│       ├── types.ts                # 【必读】view 输入数据类型：SingleRepo/MultiRepoCompare 的 props 与数据结构
│       └── ContributorComparisonBase.tsx
├── zgc_ai_native_2026
│   ├── index.yaml
│   ├── scan
│   │   └── __init__.py
│   └── view
│       ├── index.tsx
│       ├── multi_repo_compare.tsx
│       ├── README.md
│       └── single_repo.tsx
└── zgc_simple
    ├── index.yaml
    ├── scan
    │   └── __init__.py
    └── view
        ├── index.tsx
        ├── multi_repo_compare.tsx
        └── single_repo.tsx
```

其中 `index.yaml` 描述了该插件的元数据，方便后端和前端解析后加载。

其中 `scan/` 是扫描引擎实现（Python），后端真正执行的代码必须来自插件目录，不能依赖 `evaluator/commit_evaluator_moderate.py` 这类“内置实现”。

其中 `view/` 是前端插件实现（React/TSX）。**重要约束**：
- 插件视图不使用 `isMulti` 这类“同一组件内分支”来区分场景；而是使用两个清晰入口文件：
  - `view/single_repo.tsx`
  - `view/multi_repo_compare.tsx`
- 这样能让“单仓分析”和“多仓对比”在插件层面可独立演进、易维护、易验收。

### 共享契约（给插件开发者的“明确输入/输出”）

> 目标：插件开发者不需要阅读 webapp 或 server 实现，也能清楚知道：
> 1) `scan/` 收到什么输入，必须返回什么输出；2) `view/` 收到什么输入数据，应该怎么渲染。

#### View（前端渲染）输入契约：`plugins/_shared/view/types.ts`

- 插件 `view/single_repo.tsx` **必须**导出一个 React 组件，接收统一 props：
  - `PluginSingleRepoViewProps`（包含 `evaluation | loading | error | title`）
  - `evaluation` 的核心结构（兼容字段）：
    - `evaluation.scores`: 至少包含六维分数 + `reasoning`（string）
    - 可选包含：`total_commits_analyzed` / `commits_summary` / `plugin` / `plugin_version` / `plugin_scan_path`
- 插件 `view/multi_repo_compare.tsx` **必须**导出一个 React 组件，接收统一 props：
  - `PluginMultiRepoCompareViewProps`（包含 `data | loading | error`）
  - `data` 对应后端 compare 接口返回（`ContributorComparisonData`）
- 插件 view 实现 **禁止**用 `any` 作为输入类型（除非有明确注释解释原因）；应从 `plugins/_shared/view/types.ts` import。

#### Scan（后端评估）输入/输出契约：`plugins/_shared/scan/README.md`

- 插件 `scan/__init__.py` **必须**导出 `create_commit_evaluator(...)`：
  - 输入：`data_dir`（本 repo 的数据目录）、`api_key`（LLM key）、`model`、`mode`
  - 返回：evaluator 对象（至少实现 `evaluate_engineer(commits, username, ...) -> dict`）
- evaluator 的 `evaluate_engineer(...)`：
  - 输入：`commits: List[dict]`（包含 commit message、files[].patch/stats 等）、`username: str`
  - 输出：dict（至少包含 `scores`，其内含六维分数 + `reasoning`）
- 后端会在最终响应中注入/回传：`plugin` / `plugin_version` / `plugin_scan_path`（用于可验证性）

### 元数据（index.yaml）建议 schema（扁平键）

> 注意：后端使用简化 YAML 解析（不引入 PyYAML），因此使用**扁平 key:value** 结构。

- `id` / `name` / `version` / `description` / `default`
- `scan_entry`: 默认 `scan/__init__.py`
- `view_single_entry`: 默认 `view/single_repo.tsx`
- `view_compare_entry`: 默认 `view/multi_repo_compare.tsx`
- （兼容旧字段）`view_entry`: 默认 `view/index.tsx`

## 实现

### 验收标准（Definition of Done）

- 后端能通过 registry 发现 `plugins/*/index.yaml` 并返回插件列表（含默认插件）
- 保持现有前端不改也能正常工作：默认行为等价于当前 `/api/evaluate` 的结果
- `/api/evaluate` 等关键接口支持 `plugin=<id>`（未传则走默认插件）
- `plugins/zgc_simple` 可用且为默认插件
- `plugins/zgc_ai_native_2026` 可用（第一版），能基于 `engineer_level.md` 产生可区分的 reasoning（并保持六维分数结构兼容前端）
- 后端提供插件列表元数据接口（包含插件 id/name/version/default/scan_entry，以及 view 的两个入口：`view_single_entry` / `view_compare_entry` + 对应存在性标记）
- 前端顶部菜单提供插件下拉框，切换后：
  - 扫描/评估请求携带选中 plugin（后端走对应扫描能力）
  - **单 repo 分析**：动态加载 `plugins/<id>/view/single_repo.tsx` 渲染结果（缺失则回退默认视图）
  - **多 repo 对比**：动态加载 `plugins/<id>/view/multi_repo_compare.tsx` 渲染对比（缺失则回退 `ContributorComparison`）
- 可验证性：
  - 后端 `POST /api/evaluate...` 响应 `evaluation` 内包含 `plugin` / `plugin_version` / `plugin_scan_path`，且后端日志打印 `[Plugin] Using plugin=... scan=...`
  - 前端插件视图在页面上展示明显标识：`PLUGIN VIEW ACTIVE`
  - 多 repo 对比区域同样有明显标识：`MULTI-REPO COMPARE VIEW ACTIVE`
- 插件开发者可读性：
  - `plugins/_shared/view/types.ts` 明确了 view 输入数据类型，并被现有插件 view 复用
  - `plugins/_shared/scan/README.md` 明确了 scan 输入/输出与函数契约
- 不引入“模块可能存在可能不存在”的 import 假设；不使用 `typing.TYPE_CHECKING`

# TODO_LIST

> 只维护最新版本；完成后清空 TODO，仅保留“完成记录 + 日期”。
- （本轮已完成，TODO 清空）

## 完成记录

- 2026-01-22：新增 `plugins/_shared/view/types.ts`（view 输入类型契约）与 `plugins/_shared/scan/README.md`（scan 输入/输出契约），并改造现有插件 view/compare 复用共享类型、移除 `any`/重复类型定义
- 2026-01-21：完成后端插件机制与两个示例插件（默认 `zgc_simple` + `zgc_ai_native_2026` 初版）
- 2026-01-21：将 evaluator 迁移为插件自包含实现（插件 scan 不再依赖 `evaluator/commit_evaluator_moderate.py`），并补齐可验证性字段/标识