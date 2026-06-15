# 文档索引

本文档目录包含 oscanner 项目的所有技术文档，按编号顺序组织。

## 文档列表

### 01_architecture.md
**项目架构说明**

详细说明项目的整体架构、服务组成、依赖关系、启动方式等。

**主要内容**：
- 目录结构概览
- 服务说明（evaluator、repos_runner、webapp）
- 启动顺序和依赖关系
- 数据存储位置
- 端口分配
- 环境变量配置

---

### 02_directory_structure.md
**项目目录结构设计指南**

详细说明项目目录结构的设计原则、各目录的作用和使用指南。

**主要内容**：
- 完整的目录结构树
- 各目录的详细说明
- 目录组织原则
- 数据存储位置
- 导入路径说明
- 常见问题解答

---

### 03_evaluation_architecture.md
**评估功能架构**

说明评估功能的架构设计、需求规格和使用场景。

**主要内容**：
- 评估功能规约（数据结构）
- 评估需求详细说明
- 单个仓库评估流程
- 多个仓库评估流程
- 多用户名合并评估

---

### 06_trajectory_evaluation.md
**轨迹评估增强**

说明轨迹评估功能的增强实现，包括分数连续性、上下文感知等。

**主要内容**：
- 轨迹评估概述
- 增强的评分摘要
- 前一个检查点分数上下文
- 轨迹服务集成
- 分数连续性逻辑

---

### 07_refactor_summary.md
**重构完成总结**

记录项目目录结构重构的完成情况和工作总结。

**主要内容**：
- 重构日期和目标
- 已完成的工作
- 新的目录结构
- 技术实现细节
- 使用方式变化
- 注意事项

---

### 08_project_structure_refactor_proposal.md
**项目目录结构重构方案**

项目目录结构重构的提案文档（历史文档）。

**主要内容**：
- 当前问题分析
- 重构方案对比
- 推荐方案
- 重构步骤
- 风险评估

---

### 10_api_openapi.md
**API OpenAPI 使用指南**

面向外部系统集成的 evaluator 与 repos_runner OpenAPI 入口、端点摘要、请求示例和规范更新方式。

**主要内容**：
- OpenAPI JSON 文件位置
- evaluator API 端点摘要
- repos_runner API 端点摘要
- SSE 流式响应格式
- 规范重新生成命令

---

## 文档阅读顺序建议

### 新用户入门
1. [01_architecture.md](01_architecture.md) - 了解项目整体架构
2. [02_directory_structure.md](02_directory_structure.md) - 了解目录结构
3. [03_evaluation_architecture.md](03_evaluation_architecture.md) - 了解评估功能
4. [10_api_openapi.md](10_api_openapi.md) - 了解 API/OpenAPI 集成方式

### 开发者深入
1. [06_trajectory_evaluation.md](06_trajectory_evaluation.md) - 了解轨迹评估

### 项目历史
1. [07_refactor_summary.md](07_refactor_summary.md) - 了解重构历史
2. [08_project_structure_refactor_proposal.md](08_project_structure_refactor_proposal.md) - 了解重构提案

## 文档命名规范

- **编号前缀**：使用 `01_`, `02_`, `03_` 等编号前缀，便于排序和查找
- **命名风格**：使用小写下划线（snake_case），如 `trajectory_evaluation.md`
- **描述性**：文件名要有描述性，能清楚表达文档内容

## 更新文档

当更新文档时，请注意：
1. 保持编号顺序
2. 更新本文档索引
3. 更新相关文档中的交叉引用
4. 保持命名风格一致

## 相关资源

- [项目主 README](../README.md)
- [评估服务文档](../backend/evaluator/README.md)
- [仓库测试服务文档](../backend/repos_runner/README.md)
- [前端应用文档](../frontend/webapp/README.md)
