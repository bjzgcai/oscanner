## 评估功能规约为统一的数据结构

* 整个评估过程规约为 [(repo,committer),(repo,committer)...]->[repter1, repoter2, ...]
  * 单个(repo, commiter)只是这个输入列表只有1个元素的情况，不必特殊处理
* 一个(repo,committer)在一个repo里的分段机制：
  * 应该是按到从最早开始到目前为止的累积时间，例如: [0, 100), [0, 300) ...
    * 例如[0, 2026/01/27)
      * 去到今天为止的该用户的全部 [(timestamp, commit), ... ] 
      * 这是因为要同时评估 commit 里做了什么+时间序列的特征

* 一个 (repo,committer)的 repter 直接展示LLM分时间段的分析文本序列


## 最小场景用例：一个课程6周12个交付点（ 12个 checklist ）

在一个典型仓库上实现了这12个交付点，使用oscanner，评估出12个多repo多用户reporter

每个唯一的check点，在 oscanner 内有一个内置的 checker（markdown描述），llm 匹配用户在repo的 commit 里有包含 【/oscanner:xxxx】就根据xxx去匹配对应的checker，动态生成环境，拉代码，评估，出结论



