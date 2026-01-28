一、核心术语：课程结构与实体
首先，我们来定义与课程、学生和评估单元相关的核心实体。

课程：指一门完整的教学科目，例如《Vibe Coding 入门》。它的规范英文是 Course。

期次/班次：指课程在特定学期或时间开设的具体班级实例，例如“2025年秋季班”。一个课程可以包含多个班次。它的规范英文是 Session 或 Cohort。我们建议使用 Session。

学生：参与某个课程班次的学员。它的规范英文是 Student。

检查点：这是整个评估体系中最核心的概念。它指代一个具体的、需要学生交付成果并被Oscanner扫描评估的节点，通常对应一次作业。我们强烈建议使用 Checkpoint 作为其规范英文。

在检查点之下，有两种主要类型：

编程作业：需要学生提交代码的检查点。其规范英文是 Coding Assignment。

问答作业：需要学生回答问题（如PQ）的检查点。其规范英文是 Q&A Assignment。其中“PQ”可以作为产品专有名称保留。

二、核心术语：代码提交与评估过程
这部分定义了学生如何交付成果，以及系统如何评估这些成果。

代码仓库：学生存放和提交代码的版本库，如GitHub或Gitee项目。它的规范英文是 Repository，常缩写为 Repo。

标签：学生在其代码仓库的Git历史中，为标记与特定检查点对应的最终代码版本而打上的记号，例如 checkpoint-1。它的规范英文是 Tag。

提交：指一次代码变更被记录到版本库中的操作。它的规范英文是 Commit。

验证与确认：这是Oscanner对编程作业进行评估的核心流程。它的规范英文是 Verification and Validation，简称 V&V。

验证：指检查“事情是否做对”，例如代码是否能正确构建、测试是否全部通过。它的规范英文是 Verification。

确认：指检查“是否做了对的事情”，例如代码是否实现了要求的功能、代码质量如何。它的规范英文是 Validation。

扫描/运行评估：指Oscanner对一个指定的检查点执行完整的V&V流程的动作。它的规范英文是 Scan 或 Run Assessment。

扫描任务：指每一次扫描评估在后台产生的具体执行实例。它的规范英文是 Scan Job 或 Task。

截止日期：指学生提交作业的最终时间。它的规范英文是 Deadline 或 Due Date。

三、核心术语：评估结果与能力模型
这部分定义了系统输出的结果和背后的评估框架。

结果/报告：指单次扫描完成后，系统生成的详细评估产出。它的规范英文是 Result 或 Report。

分数/得分：指对评估结果的量化表示。它的规范英文是 Score 或 Grade。

指标：指用于衡量代码或表现的具体维度，例如“构建成功率”、“单元测试覆盖率”、“代码复杂度”。它的规范英文是 Metric。

分析摘要：指对评估结果的文字性总结、反馈和建议。它的规范英文是 Analysis Summary。

能力维度：指对学生能力的高层次分类，例如“编程实践”、“软件测试”、“工程规范”。它的规范英文是 Capability Dimension。

考察点：指在每个能力维度下的具体评估细项。它的规范英文是 Evaluation Point 或 Criterion。

能力画像：指综合多个维度和考察点后，形成的对学生能力的结构化描述。它的规范英文是 Capability Profile。

雷达图：指用于可视化展示能力画像的图表。它的规范英文是 Radar Chart。

成长轨迹：指展示学生在连续多个检查点上，其能力或分数变化的趋势图。它的规范英文是 Growth Trajectory。

四、核心术语：系统功能与界面
这部分定义了用户在系统中进行的操作和看到的界面。

仪表盘/总览：指老师登录后看到的、展示课程和作业整体情况的主界面。它的规范英文是 Dashboard 或 Overview。

批量操作：指能同时对多个学生或检查点执行的操作，例如“批量扫描”。它的规范英文是 Batch Operation。

列表视图：指以表格或列表形式展示学生、作业及其状态的界面。它的规范英文是 List View。

详情视图：指点击列表中的某一项后，进入的查看其全部详细信息的界面。它的规范英文是 Detail View。

总结关键句的规范表达：

“Oscanner要对打标签的代码进行V&V检查”应表述为：OScanner performs a V&V scan on the code submitted with the required Git tag.

“显示学生历次作业的分数变化”应表述为：Display the student‘s growth trajectory of scores across all checkpoints.

“创建一次编程作业”应表述为：Create a new Coding Assignment checkpoint.