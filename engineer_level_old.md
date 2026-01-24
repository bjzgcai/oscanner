# 工程师能力评估标准（六维度框架）
**Engineer Capability Assessment Standard (Six-Dimensional Framework)**

## 概述 (Overview)

本文档描述了传统的六维度工程能力评估标准，用于评估软件工程师在不同技术领域的综合能力。该标准通过分析工程师的开源贡献、代码质量、架构设计等数字足迹，对其能力进行量化评估。

This document describes the traditional six-dimensional engineering capability assessment standard, used to evaluate software engineers' comprehensive capabilities across different technical areas. This standard quantifies engineers' abilities by analyzing their open source contributions, code quality, architecture design, and other digital footprints.

---

## 评分体系 (Scoring System)

每个维度的评分范围为 **0-100 分**，根据以下标准划分等级：

Each dimension is scored on a **0-100 scale**, with levels defined as follows:

- **0-30分 (初级 / Junior)**: 基础认知，依赖他人指导，能力有限
- **30-50分 (合格 / Competent)**: 能独立完成基本任务，符合基本规范
- **50-70分 (熟练 / Proficient)**: 具备较强的独立能力，能处理复杂问题
- **70-85分 (专家 / Expert)**: 在该领域有深入理解，能指导他人
- **85-100分 (大师 / Master)**: 行业领先水平，定义标准和最佳实践

---

## 维度一：AI 模型全栈开发与权衡能力
**Dimension 1: AI Model Full-Stack Development & Trade-off Capability**

### 核心考察点 (Core Assessment Points)

1. **机器学习框架经验** - Experience with ML frameworks (TensorFlow, PyTorch, etc.)
2. **模型优化与调优** - Model optimization and tuning
3. **端到端 ML 流水线** - End-to-end ML pipeline implementation
4. **模型选择与权衡决策** - Model selection and trade-off decisions

### 评分标准 (Scoring Criteria)

#### 高分特征 (High Score Indicators)
- 熟练使用多个主流 ML 框架
- 有模型性能优化的实际案例
- 实现过完整的训练-评估-部署流程
- 在文档/PR 中清晰说明模型选择理由和性能权衡

#### 低分特征 (Low Score Indicators)
- 仅接触过基础 ML 库
- 缺少模型优化经验
- 没有完整的 ML 项目经验
- 缺乏对模型权衡的文档记录

### 取证依据 (Evidence Sources)
- 代码中的 ML 框架引用 (PyTorch, TensorFlow, scikit-learn, etc.)
- 模型训练、评估相关的提交
- 模型配置文件、超参数调优记录
- 性能优化相关的文档和讨论

---

## 维度二：AI 原生架构与通信设计
**Dimension 2: AI Native Architecture & Communication Design**

### 核心考察点 (Core Assessment Points)

1. **AI 服务 API 设计** - AI service API design
2. **架构文档质量** - Architecture documentation quality
3. **分布式 AI 系统** - Distributed AI systems
4. **技术沟通能力** - Technical communication quality

### 评分标准 (Scoring Criteria)

#### 高分特征 (High Score Indicators)
- 设计过多个 AI 服务的 API 接口
- 有完善的架构设计文档
- 有分布式训练/推理系统经验
- 在 Issue/PR 中展现出色的技术沟通能力

#### 低分特征 (Low Score Indicators)
- 缺少 API 设计经验
- 架构文档缺失或不完整
- 仅有单机 AI 系统经验
- 技术沟通简略或不清晰

### 取证依据 (Evidence Sources)
- API 设计相关的代码和文档
- 架构图、设计文档 (ADR, RFC, etc.)
- 微服务、分布式系统相关配置
- Issue、PR 中的讨论质量

---

## 维度三：云原生与约束工程
**Dimension 3: Cloud Native & Constraint Engineering**

### 核心考察点 (Core Assessment Points)

1. **容器化** - Containerization (Docker, etc.)
2. **容器编排** - Container orchestration (Kubernetes, etc.)
3. **CI/CD 流水线** - CI/CD pipelines
4. **基础设施即代码 (IaC)** - Infrastructure as Code
5. **资源优化** - Resource optimization

### 评分标准 (Scoring Criteria)

#### 高分特征 (High Score Indicators)
- 熟练使用 Docker 进行多阶段构建
- 有 Kubernetes 配置和运维经验
- 实现过复杂的 CI/CD 流水线
- 使用 Terraform/Pulumi 等 IaC 工具
- 有资源成本优化的实际案例

#### 低分特征 (Low Score Indicators)
- Dockerfile 简单或冗余
- 缺少容器编排经验
- 没有 CI/CD 配置
- 不了解 IaC 概念
- 缺少资源优化意识

### 取证依据 (Evidence Sources)
- Dockerfile, docker-compose.yml
- Kubernetes manifests (deployment.yaml, service.yaml, etc.)
- CI/CD 配置文件 (.github/workflows/, .gitlab-ci.yml, etc.)
- Terraform/Pulumi 代码
- 资源限制、优化相关的提交

---

## 维度四：开源协作与需求转化
**Dimension 4: Open Source Collaboration & Requirements Translation**

### 核心考察点 (Core Assessment Points)

1. **贡献频率** - Contribution frequency
2. **代码审查参与度** - Code review participation
3. **Issue 管理** - Issue management
4. **跨项目协作** - Cross-project collaboration
5. **需求到代码的转化** - Requirements-to-code translation

### 评分标准 (Scoring Criteria)

#### 高分特征 (High Score Indicators)
- 在多个项目中有持续贡献
- 积极参与代码审查，提供建设性意见
- 创建和解决 Issue，推动问题闭环
- 在多个仓库/组织中有协作记录
- 能准确理解需求并实现功能

#### 低分特征 (Low Score Indicators)
- 贡献零散或不活跃
- 很少参与代码审查
- Issue 管理能力弱
- 仅在单一项目中活动
- 需求理解不到位，实现偏差大

### 取证依据 (Evidence Sources)
- GitHub/Gitee 贡献统计
- PR review 记录
- Issue 创建和解决记录
- 跨仓库的协作痕迹
- 从 Issue 到 PR 的功能实现链路

---

## 维度五：智能开发与人机协作
**Dimension 5: Intelligent Development & Human-Machine Collaboration**

### 核心考察点 (Core Assessment Points)

1. **自动化工具** - Automation tools
2. **AI 辅助开发** - AI-assisted development
3. **代码生成** - Code generation patterns
4. **测试自动化** - Test automation
5. **自定义工具开发** - Custom tooling development

### 评分标准 (Scoring Criteria)

#### 高分特征 (High Score Indicators)
- 开发过多个自动化脚本和工具
- 有效利用 AI 辅助开发工具
- 合理使用代码生成提高效率
- 建立完善的自动化测试体系
- 开发定制化的开发工具链

#### 低分特征 (Low Score Indicators)
- 自动化意识薄弱
- 不了解 AI 辅助开发工具
- 手动重复劳动多
- 测试自动化程度低
- 缺少工具开发经验

### 取证依据 (Evidence Sources)
- 自动化脚本 (scripts/, tools/, etc.)
- AI 工具配置文件 (.copilot, .cursor, etc.)
- 代码生成相关的模式
- 测试覆盖率报告
- 自定义 CLI 工具、构建脚本

---

## 维度六：工程领导力与系统权衡
**Dimension 6: Engineering Leadership & System Trade-offs**

### 核心考察点 (Core Assessment Points)

1. **导师与指导** - Mentorship and guidance
2. **架构决策** - Architectural decisions
3. **技术权衡文档** - Trade-off documentation
4. **项目所有权** - Project ownership
5. **团队协作** - Team collaboration

### 评分标准 (Scoring Criteria)

#### 高分特征 (High Score Indicators)
- 在 Code Review 中指导他人
- 做出关键架构决策并有文档支撑
- 清晰记录技术选型的利弊权衡
- 拥有和维护多个项目
- 展现出强大的团队协作能力

#### 低分特征 (Low Score Indicators)
- 很少指导他人
- 缺少架构级别的贡献
- 技术决策缺乏文档
- 没有明确的项目所有权
- 团队协作意识弱

### 取证依据 (Evidence Sources)
- Code Review 中的指导性评论
- 架构相关的提交和文档
- ADR (Architecture Decision Records)
- 项目维护者身份
- PR/Issue 中的协作互动

---

## 评估方法论 (Evaluation Methodology)

### 数据来源 (Data Sources)

1. **Git 提交历史** - Git commit history
   - 提交频率和质量
   - 代码变更的规模和复杂度
   - 提交信息的规范性

2. **代码仓库分析** - Repository analysis
   - 项目结构和组织
   - 代码质量指标
   - 依赖管理

3. **协作活动** - Collaboration activities
   - PR 创建和审查
   - Issue 管理
   - 讨论参与度

4. **文档质量** - Documentation quality
   - README 完整性
   - API 文档
   - 架构设计文档

### 评分算法 (Scoring Algorithm)

每个维度的评分基于：

1. **关键指标量化** (60%权重)
   - 提交数量、代码行数
   - 文件类型统计
   - 关键词匹配

2. **质量评估** (30%权重)
   - 代码结构复杂度
   - 测试覆盖率
   - 文档完整性

3. **影响力评估** (10%权重)
   - Star/Fork 数量
   - 项目活跃度
   - 社区影响力

---

## 与 AI-Native 2026 标准的区别
**Differences from AI-Native 2026 Standard**

### 旧标准（本文档）
- **评估重点**: 技术广度和深度
- **评分依据**: 主要基于量化指标（提交数、代码行数等）
- **能力模型**: 传统的技术能力分类
- **AI 时代适配**: 有限，未充分考虑 AI 辅助开发的影响

### AI-Native 2026 标准（engineer_level.md）
- **评估重点**: 在 AI 辅助时代区分"搬运工"与"构建者"
- **评分依据**: 强调行为证据（重构、测试、可复现性等）
- **能力模型**: L1-L5 行为画像，更细粒度的能力分层
- **AI 时代适配**: 高度适配，考虑了 Vibe Coding 时代的特点

### 使用场景建议
- **旧标准 (zgc_simple)**: 适用于传统软件工程能力评估
- **新标准 (zgc_ai_native_2026)**: 适用于 2026 年 AI 时代工程能力评估

---

## 附录：评估示例
**Appendix: Evaluation Examples**

### 示例 1: AI 全栈开发维度

**高分案例 (80分)**:
```
- 使用 PyTorch 和 TensorFlow 开发多个项目
- 实现过分布式训练系统
- 有模型量化和优化的提交记录
- 文档中详细说明了模型选择的 latency/accuracy trade-off
```

**中等案例 (50分)**:
```
- 使用过 scikit-learn 进行简单建模
- 有基本的模型训练代码
- 缺少优化和部署经验
- 文档简略
```

**低分案例 (20分)**:
```
- 仅有调用 API 的代码
- 没有模型训练经验
- 缺少相关文档
```

### 示例 2: 云原生维度

**高分案例 (85分)**:
```
- Dockerfile 使用多阶段构建，镜像优化到 < 100MB
- 完整的 Kubernetes 配置（含 HPA、资源限制）
- GitHub Actions/GitLab CI 完善的 CI/CD 流水线
- Terraform 管理云基础设施
- 有成本优化的实际案例
```

**中等案例 (55分)**:
```
- 有基本的 Dockerfile
- 简单的 CI 配置
- 没有容器编排经验
- 缺少 IaC 实践
```

**低分案例 (25分)**:
```
- Dockerfile 冗余，镜像 > 1GB
- 没有 CI/CD 配置
- 缺少云原生概念
```

---

## 总结 (Summary)

本六维度评估标准为传统软件工程能力评估提供了结构化框架。通过量化分析工程师在不同技术领域的贡献，可以客观评估其综合能力。

该标准适用于传统软件开发场景，但在 AI 辅助开发时代，建议结合 **AI-Native 2026 标准** 使用，以更准确地识别工程师在新时代的真实能力。

This six-dimensional assessment standard provides a structured framework for traditional software engineering capability evaluation. By quantifying engineers' contributions across different technical areas, it can objectively assess their comprehensive capabilities.

This standard is suitable for traditional software development scenarios. However, in the AI-assisted development era, it is recommended to use it in conjunction with the **AI-Native 2026 Standard** to more accurately identify engineers' true capabilities in the new era.
