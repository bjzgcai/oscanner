# 闭环描述

## 基础

1. 当前系统包含：
  - `webapp/`（Next.js 前端）：页面与组件渲染、插件 view 动态加载
  - `evaluator/`（后端）：提供评估与对比 API
  - `plugins/*/view/`（前端插件视图）：可替换的结果展示 UI
2. 目前 UI 文案与错误提示缺乏统一的“可扩展多语言”机制，导致：
  - 同一概念在不同页面/组件重复 hardcode
  - 难以在不改业务逻辑的情况下引入新语言/术语表

## 设计

### 目标资源：Language Pack（语言包）

一个 Language Pack 是一类“可被前端发现、可在运行时选择、可演进并可回退”的资源，用于定义：
- **locale**：如 `zh-CN`、`en-US`
- **文案字典**：`key -> message`（支持参数插值）
- **fallback 策略**：缺 key 时回退到默认语言或回退文本（可配置策略）

Language Pack 的目标是让以下内容变成“数据/资源”，而不是散落的 hardcode：
- 顶部导航、表单标签、按钮文字、状态文案（loading/error/empty）
- 扫描/对比页面中的通用文案
- 插件 view 中的通用区域文案（插件特有文案可由插件自带或复用共享字典）

### 语言包目录结构与归属（核心 vs 插件）

目标：**核心 UI 的 i18n 由 `webapp/` 维护；插件文案由插件作者在 `plugins/<pluginId>/` 内独立维护**，避免插件文案散落在 `webapp/`，也避免在插件 view 中用 `isZh` 等方式硬编码中英文。

#### Core（webapp 内置语言包）

- 目录：`webapp/i18n/`
- 内容：
  - `zh-CN.ts` / `en-US.ts`：核心 UI 文案字典
  - `index.ts`：注册 `DEFAULT_LOCALE`、可选语言列表、`getMessages(locale)` 等
- 适用范围：导航、主页面、通用 loading/error/empty、LLM 设置等**非插件** UI

#### Plugin（插件自带语言包）

- 目录：`plugins/<pluginId>/i18n/`
  - `zh-CN.ts` / `en-US.ts`：插件文案字典
  - `index.ts`：导出 `default { pluginId, messages: { 'zh-CN': ..., 'en-US': ... } }`
- 供 webapp 动态加载的入口：`plugins/<pluginId>/view/i18n.ts`（仅 re-export `../i18n`，默认约定路径）
- key 命名空间：建议统一使用 `plugin.<pluginId>.*`（例如 `plugin.zgc_simple.single.title_default`），避免与 core key 冲突

#### 合并与优先级（运行时）

- webapp 启动时加载 core language pack
- 当插件被选中时，webapp 动态加载该插件的 language pack，并将其 messages **合并到** `t()` 的查找表中
  - 合并策略：`plugin` messages 覆盖/补充 `core`（同 key 时以 plugin 为准）
- 插件 view 渲染必须拿到 `t`（否则直接抛错），确保插件文案只需在插件目录维护一份

### 分析闭环：语言包在系统中的端到端路径

> 目标：用户“选择语言”后，所有前端固化 UI 与插件 view 的文本都能一致切换，并且缺失翻译时有稳定回退，不阻塞核心功能使用。

#### 运行时流程（前端）

1. **语言选择（前端固化）**
  - 在全局设置（`AppSettingsContext`）提供 `locale` 选择（并持久化到 localStorage）。
2. **语言包加载（前端固化机制）**
  - 应用启动时加载默认语言包；用户切换时加载目标语言包。
  - 语言包来源优先级（建议）：
    - `webapp` 内置语言包（核心 UI）
    - 插件自带语言包（插件 view 可选提供）
3. **文案消费（前端固化 + 插件可复用）**
  - 通过统一的 `t(key, params?)` API 获取文案，并支持：
    - 参数插值（如 `{count}`）
    - 回退（默认语言 / key 透传 / 明确的 missing 提示）
4. **插件 view 的语言一致性（前端固化机制）**
  - 插件 view 渲染时必须能够拿到当前 `locale` 与 `t`（或等价能力）。
  - 插件可：
    - 直接使用全局 `t`（共享字典 key）
    - 或者注册插件自带字典，在 `t` 中按命名空间解析（如 `plugin.zgc_simple.*`）

#### 后端边界（不做本地化，做稳定契约）

- 后端 API 返回的错误与状态应保持**稳定 code/字段**（供前端本地化展示），而不是返回“不可控的自然语言文案”。
- 后端可保留英文/中文 message，但前端展示应尽量使用 code→i18n 映射（本任务的目标是把展示侧本地化闭环做起来）。

### 生命周期（增/删/查/改）

- **增（Create）**
  - 新增一种语言：添加一个 language pack 文件（如 `zh-CN` / `en-US`），并在前端注册为可选语言。
  - 插件新增语言包：在插件目录提供可选的字典资源，并通过约定的命名空间合并。

- **查（Read/Discover）**
  - 前端能列出可用语言列表（至少包含默认语言 + 内置语言）。
  - 在 UI 显示当前生效的 locale（用于验收与排错）。

- **改（Update/Evolve）**
  - 允许增量补齐 key；允许调整术语（保持 key 稳定或提供迁移映射）。
  - 缺 key 不应导致页面崩溃（必须回退）。

- **删（Remove/Disable）**
  - 移除语言包文件后：该 locale 不再出现在列表；若用户本地保存的是被移除 locale，启动时自动回退默认 locale。

## 实现

### 验收标准（Definition of Done）

- 前端提供全局 `locale` 设置与持久化（刷新后仍生效）
- 所有 webapp 固化 UI 文案（导航/按钮/状态/错误/空态）不再硬编码字符串，统一走 `t(...)`
- 插件 view 能跟随全局语言切换（至少能拿到 `locale`，并可使用同一套 `t`）
- 缺少翻译 key 时：页面不崩溃，并按约定策略回退（默认语言或 key 透传），且开发模式可提示 missing key
- 不改变后端核心业务逻辑；后端若需配合，仅提供稳定 error code（可增量进行）

# TODO_LIST

> 只维护最新版本；完成后清空 TODO，仅保留“完成记录 + 日期”。

(已完成，TODO 已清空)

## 完成记录

- 2026-01-23：新增 `webapp/i18n/*` 语言包与 `I18nContext`（`t(key, params?)` 支持插值 + 默认语言 fallback；dev 环境缺 key 仅 warn 且返回 key，不阻塞渲染）；`AppSettingsContext` 增加 `locale` 并持久化到 localStorage（含浏览器语言兜底）；导航栏新增语言切换入口；主分析页关键 UI 文案接入 `t(...)`；`PluginViewRenderer` / `PluginComparisonRenderer` 将 `locale/t` 透传给插件 view，实现插件视图跟随全局语言切换
- 2026-01-23：明确并落地“插件自带 i18n”目录规范：插件文案迁移到 `plugins/<pluginId>/i18n/*`，由 webapp 运行时按 `pluginId` 动态加载并合并到 `t()`；插件 view 移除 `isZh`/硬编码 fallback，统一只维护一份 key→message


