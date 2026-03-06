# Review Comments on engineer_level.md

## 2026标准评估标准,囊括了 代码静态分析\代码动态测试, 在实际代码评估分析中, 部分无法直接使用

## 2026标准评估标准, 聚焦比较广阔的工程能力评估, 但是对于初级工程师的评估, 可能过于宽泛, 无法区分真正的初级工程师和 AI 搬运工等初阶. 比如

## Overall Assessment

The L1-L5 level definitions in `engineer_level.md` are well-structured. The "AI搬运工" (AI porter) metaphor for L1 is vivid, and the progression from L1 (blind dependency) to L5 (ecosystem leadership) is clear and meaningful. The forensic evidence approach — judging engineers by repo artifacts rather than interviews — is the document's core strength.

However, there is a gap between some L1 判断依据 (judgment criteria) and what the automated evaluation system can actually measure.

---

## Issue: L1 判断依据 Contains Non-Observable Criteria

The current L1 definition (`engineer_level.md`, lines 25-28) lists three types of judgment criteria:

> 代码中常出现低级的逻辑错误或未使用的导入（Unused Imports）；在 Code Review 被问到"为什么这里这么写"时，只能回答"AI 是这么生成的"，无法解释底层逻辑。

### Signal Detectability Analysis

| Signal | Observable from repo? | Notes |
|---|---|---|
| Unused imports / dead code | **Yes** | Static analysis tools (ruff, pylint) |
| Low-level logic errors | **Partially** | LLM can review diffs, but not reliably |
| Files >500 lines, CCN >15 | **Yes** | CCN checker already implemented in codebase |
| Vague commit messages | **Yes** | Pattern matching or LLM scoring |
| "AI是这么生成的" in code review | **No** | Interpersonal signal, not a repo artifact |
| Cannot explain underlying logic | **No** | Interview signal, not a repo artifact |

The last two criteria contradict the document's own preamble (lines 11-13):

> 本标准建立在一个核心假设之上：**代码是不会撒谎的，特别是在开源社区。**
> 我们不再依赖面试中的口头陈述，而是将目光聚焦于...数字足迹 (Digital Footprints)。

If the standard is built on repo forensics, the L1 判断依据 should not rely on interview-time responses.

### Additional Concern: "Unused Imports" as a Weak Signal

Unused imports appear at all levels — during refactoring, from IDE auto-import, or from incomplete cleanup. As a standalone indicator, it is noisy. Notably, the L2 definition (line 64) lists "removed unused imports" as positive evidence, which creates a reasonable contrast, but the presence of unused imports alone does not reliably indicate L1.

---

## Recommendation: Replace Non-Observable Criteria with Repo-Based Proxies

Instead of relying on interview responses, use equivalent signals that are visible in repository history:

### Proposed Revised 判断依据 for L1

> 代码中常出现低级的逻辑错误或未使用的导入；Commit 为单次大量代码提交且消息模糊（如"update"、"fix"）；无 PR 描述或 Review 讨论记录；代码注释残留 AI 生成的解释性文本（如重复函数名的注释）；无测试目录或仅含空测试。

### Mapping of Replaced Criteria

| Original (interview-based) | Proposed replacement (repo-based) |
|---|---|
| 回答"AI是这么生成的" | Commit messages are vague/generic; no PR descriptions |
| 无法解释底层逻辑 | No iterative refinement in commit history (single large dumps); AI-generated boilerplate comments left intact |

### Additional Automatable Signals Worth Considering

These could strengthen L1 detection across all four dimensions:

1. **Commit pattern analysis** — L1 tends to show single large commits rather than incremental, logical progression
2. **Dead code ratio per commit** — High ratio suggests copy-paste without review
3. **Commit message quality scoring** — Length, specificity, presence of "why" vs just "what"
4. **AI comment residue detection** — Patterns like `# This function does X` that merely restate the obvious

---

## Impact on Current System

The evaluation plugin (`plugins/zgc_ai_native_2026/scan/__init__.py`) translates the rubric into LLM prompts. The `_RUBRIC_SUMMARY` block (line ~28) already summarizes L1 as:

> "L1: blind copy/paste, cannot explain, low-level errors, no quality gates"

The LLM evaluator works by detecting **absence** of quality signals (no tests, no refactors, no type discipline). This approach is sound for repo-based assessment, but the rubric document (`engineer_level.md`) should align with it — all listed 判断依据 should be things the system can actually observe and verify.

---

## Summary

- The L1 definition is conceptually sound
- Two of its 判断依据 depend on interview context, contradicting the document's own "digital footprints" philosophy
- "Unused imports" is a valid but noisy signal that should be combined with stronger indicators
- Recommend replacing interview-dependent criteria with repo-observable proxies
- The automated evaluation system already operates on this principle; the rubric document should catch up
