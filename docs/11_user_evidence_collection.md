# GitHub / Gitee 用户证据采集与合并工作流

本文档是“按用户身份采集工程证据并进行能力评估”的独立规范。实现、API 返回值、管理端展示和测试必须使用相同语义。

## 1. 核心原则

1. 身份输入是证据归属声明，不是只用于搜索的关键字。
2. 同一请求中的 email、profile URL 和 repository URL 是并集关系，不得因为存在 email 而丢弃 profile/repository 身份。
3. 采集阶段必须在每条证据上保留归属信息，如 `matched_email`、`matched_login`、`matched_identity` 和 `matched_roles`。
4. 评估阶段先按归属筛选，再应用 commit 数量上限。不允许无关的较新 commit 挤掉属于用户的较旧 commit。
5. Commit 数量只使用 `available_commit_count` 和 `total_commits_analyzed`，前端和 API 不得混用。

## 2. 身份输入语义

### Email

- GitHub：使用 `author-email` 和 `committer-email` 进行全局搜索，并从命中 commit 解析 GitHub login，继续采集 PR、review、issue、approval 和 maintainer decision。
- Gitee：在指定或缓存的仓库中匹配 author/committer email。
- email 匹配忽略大小写，但必须是精确地址匹配。

### Profile URL

- `https://github.com/<owner>` 表示该 GitHub owner/profile 是要评估的用户。系统采用较积极的归属策略：枚举该 owner 下的所有可见 repositories，并假设这些 repositories 中采集到的所有 commits 都归属于该 owner，即归属于本次要评估的用户。
- `https://gitee.com/<username>` 使用相同策略：该 username/profile 是要评估的用户，profile API 返回的所有 repositories 及其采集到的所有 commits 都归属于该用户。
- Profile 模式不再要求 commit 的 author/committer email、username 或 login 与 profile 完全一致。实际使用中，同一用户可能长期使用多个 email、本地 Git username、GitHub/Gitee noreply email 或不同设备默认身份。以 profile 仓库范围进行全量归属，可以减少因 commit identity 变化导致的用户证据丢失。
- 该规则是本系统为提高评估证据覆盖率采用的业务假设，不表示对 repository 或 commit 法律所有权的判定。如果 owner/profile 是多人共用的组织账号，评估结果可能包含他人提交，这是 Profile 模式有意接受的取舍。

### Repository URL

- Repository URL 是精确范围，只识别该仓库，不得因 owner/org 相同而自动合并其他仓库。
- Repository 模式采用较保守的归属策略，因为仓库 owner 可能是组织、班级、团队或共享账号，不能仅根据 repository URL 推断其中每个 commit 的个人归属。
- 未提供 email，或 email 为空时：将该 repository 中采集到的所有 commits 归属于当前要评估的用户。
- 提供一个或多个 email 时：仅当 commit 的 author email 或 committer email 与任一输入 email 精确匹配时，才将该 commit 归属于当前用户。
- 已提供 email 但 repository 中没有 commit 匹配时：该 repository 不产生归属于当前用户的 commit 证据，不得退回到“全部 commits 归属用户”的兜底逻辑。

## 3. GitHub 采集流程

1. 解析并去重 email、GitHub profile URL 和 repository URL。
2. 对每个 email 分别执行 author-email 和 committer-email 搜索，获取 commit detail 后再次验证可见 email。
3. 对 profile URL 解析 owner/login，枚举 profile 的所有可见仓库，采集这些仓库的所有 commits，并统一使用 profile owner identity 记录归属。Profile 采集不受请求中 email 的过滤。
4. 对 repository URL 按仓库采集 commit；没有 email 时保留所有 commits 并记录 repository identity；有 email 时仅保留 author/committer email 匹配的 commits 并记录 email role。
5. 从匹配 commit 中解析 login，采集 commit-associated PR、PR discussion、review comment、issue triage、approval 和 maintainer decision。
6. 按 `(platform, repo_full_name, sha)` 去重 commit，按时间倒序排列。协作证据按来源、URL、login 和 commit SHA 等字段去重。
7. 将采集结果写入 XDG 数据目录，供评估、链接展示和后续轨迹分析使用。
8. 评分身份是 email、`github:<login>`、裸 login 和 repository identity 的并集。评估器必须优先识别 commit 上的显式 `matched_*` 归属，然后才使用 author/committer 名称或 email 兜底。
9. 归属筛选完成后，再取最新的评分上限。请求上限最高为 1000 commits，`total_commits_analyzed` 记录实际进入评分的数量。

## 4. Gitee 采集流程

1. 解析 Gitee profile/repository URL、username 和 email。
2. Profile 模式通过 `/api/v5/users/<username>/repos?type=all` 枚举可见仓库。
3. 对每个仓库进行增量同步或首次提取，commit detail、文件变更和索引保存在 XDG 数据目录。
4. 从仓库缓存/API 采集 commit diff、PR discussion、review、issue、approval 和 maintainer decision；企业 Gitee 使用对应 enterprise URL/token。
5. 按 SHA 去重 commit，按 author/committer 时间倒序排列。
6. 对明确 profile 范围，username/profile 是评分身份，profile 下所有 repositories 的所有 commits 均归属该用户；对明确 repository 范围，无 email 时归属全部 commits，有 email 时仅归属 author/committer email 匹配的 commits。
7. 归属后应用 `commit_limit`，不得用未归属的候选数量代替实际评分数量。

## 5. GitHub 与 Gitee 合并

1. 各 provider 先独立完成采集、归属、去重和评分，保留 provider-specific 原始结果。
2. 用户身份合并使用显式输入和已验证别名的并集。不同仓库不得仅因 owner/org 相同而合并。
3. Commit 跨平台去重键至少包含 provider/platform、repository 和 SHA；不得仅按 SHA 跨平台去重。
4. 证据链接保留 provider、type、repository、SHA/issue/PR 编号和 URL。
5. 维度分数使用各 provider 的实际 `total_commits_analyzed` 加权；不得使用未进入评分的采集数量加权。如果某 provider 没有可评分 commit，其 commit 权重为 0，但可保留独立的协作证据。
6. 合并结果必须同时返回并展示：
   - 采集仓库数；
   - 采集 commit 数；
   - 实际评分 commit 数；
   - 协作证据数；
   - provider 独立结果和合并后结果。
7. 部分 provider 失败时，保留成功 provider 的结果，同时显式返回失败数和可操作错误。

## 6. 计数字段契约

| 字段 | 含义 |
| --- | --- |
| `matched_repo_count` / `repo_count` | 身份范围内采集或命中的仓库数 |
| `available_commit_count` | 完成身份归属和去重后、应用本次评估上限前，可用于评分的 commit 数 |
| `total_commits_analyzed` | 应用评估上限后，实际进入 rubric/LLM 评分的 commit 数；该值不大于 `available_commit_count` |

示例：身份归属和去重后有 820 个可用 commits，本次上限为 500，则 `available_commit_count` 为 820，`total_commits_analyzed` 为 500。
| `collaboration_evidence_count` | 去重后的非 commit 协作证据数 |

## 7. 必须覆盖的测试

- 仅 email、仅 profile、仅 repository、email + profile、email + repository、多 provider 混合输入。
- Profile 模式必须覆盖 owner/username 下所有 repositories 的所有 commits，并验证 email/login 变化不会丢失 commit。
- Repository 模式必须分别覆盖“无 email 时全量归属”、“有 email 时仅匹配归属”和“有 email 但零匹配时不得全量兜底”。
- GitHub public email、private email、`users.noreply.github.com` 和 login 归属。
- author 与 committer 两种 role。
- 同 commit 被多个身份命中后只评分一次。
- 归属筛选必须早于 commit 上限截断。
- 采集数量与实际评分数量在 API 和 UI 中不得混淆。
