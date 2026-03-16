"""
Test report generation (TEST_REPORT.md).
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


async def _generate_test_report(
    report_path: Path,
    repo_name: str,
    total: int,
    passed: int,
    failed: int,
    score: int,
    test_results: list,
    feature_coverage: Optional[Dict[str, Any]] = None,
    tag_message: Optional[str] = None,
) -> None:
    """Generate TEST_REPORT.md for analyzed repository."""
    pass_rate = (passed / total * 100) if total > 0 else 0
    fail_rate = (failed / total * 100) if total > 0 else 0

    if score >= 90:
        grade = "优秀 ⭐⭐⭐⭐⭐"
    elif score >= 70:
        grade = "良好 ⭐⭐⭐⭐"
    elif score >= 50:
        grade = "一般 ⭐⭐⭐"
    else:
        grade = "较差 ⭐"

    report = f"""# 测试报告：{repo_name}

**生成时间**：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**综合评分**：{score}/100（{grade}）

## 概览
- **测试总数**：{total}
- **通过**：{passed}（{pass_rate:.1f}%）
- **失败**：{failed}（{fail_rate:.1f}%）
- **跳过**：0（0%）
- **得分**：{score}/100

## 测试结果

"""

    if total == 0:
        report += """⚠️ **未检测到测试用例**

该仓库似乎没有配置任何自动化测试。

"""

    passed_tests = [t for t in test_results if t["status"] == "passed"]
    failed_tests = [t for t in test_results if t["status"] == "failed"]

    if passed_tests:
        report += f"### ✅ 通过的测试（{len(passed_tests)}）\n\n"
        for t in passed_tests:
            duration = t.get("duration", 0)
            report += f"- `{t['name']}` （{duration:.2f}s）\n"
        report += "\n"

    if failed_tests:
        report += f"### ❌ 失败的测试（{len(failed_tests)}）\n\n"
        for t in failed_tests:
            duration = t.get("duration", 0)
            report += f"- `{t['name']}` （{duration:.2f}s）\n"
            output = t.get("output", "")
            if output:
                truncated_output = output[-500:] if len(output) > 500 else output
                report += f"  ```\n  {truncated_output}\n  ```\n"
        report += "\n"

    report += f"""## 得分明细

- **通过率**：{pass_rate:.1f}%（{passed}/{total}）
- **最终得分**：{score}/100
"""

    if feature_coverage:
        covered = feature_coverage.get("covered", [])
        not_covered = feature_coverage.get("not_covered", [])
        total_features = len(covered) + len(not_covered)
        coverage_pct = feature_coverage.get("coverage_ratio", 1.0) * 100
        report += f"""- **功能覆盖率**：{len(covered)}/{total_features} 个功能（{coverage_pct:.0f}%）
- **评分公式**：通过率（{pass_rate:.1f}%）× 功能覆盖率（{coverage_pct:.0f}%）= {score}/100
"""
    report += "\n"

    if feature_coverage:
        covered = feature_coverage.get("covered", [])
        not_covered = feature_coverage.get("not_covered", [])
        total_features = len(covered) + len(not_covered)
        coverage_pct = feature_coverage.get("coverage_ratio", 1.0) * 100
        test_files_found = feature_coverage.get("test_files_found", [])

        report += f"## 功能覆盖（{len(covered)}/{total_features} — {coverage_pct:.0f}%）\n\n"

        if tag_message:
            report += f"> **标签说明**：{tag_message}\n\n"

        report += (
            "功能列表从标签说明中提取，并与仓库中的测试文件进行交叉比对。"
            "每个未覆盖的功能将按比例降低最高可得分数。\n\n"
        )

        if covered:
            report += f"### ✅ 已覆盖（{len(covered)}）\n\n"
            for f in covered:
                report += f"- {f}\n"
            report += "\n"

        if not_covered:
            report += f"### ❌ 未覆盖（{len(not_covered)}）\n\n"
            for f in not_covered:
                report += f"- {f}\n"
            report += "\n"

        if test_files_found:
            report += f"### 已扫描的测试文件（{len(test_files_found)}）\n\n"
            for tf in test_files_found:
                report += f"- `{tf}`\n"
            report += "\n"
        else:
            report += "> ⚠️ 未找到测试文件——所有功能均计为未覆盖。\n\n"

    elif tag_message:
        # tag_message present but no feature_coverage (extraction returned nothing)
        report += f"## 功能覆盖\n\n> **标签说明**：{tag_message}\n\n"
        report += "> ⚠️ 无法从标签说明中提取可测试的功能点。\n\n"
        report += "> **得分设为 0** ——已提供标签说明，但无法从中识别出可评估的功能。\n\n"

    report += """### 评级标准
- 90-100：优秀 ⭐⭐⭐⭐⭐（可投入生产）
- 70-89：良好 ⭐⭐⭐⭐（少量缺口可接受）
- 50-69：一般 ⭐⭐⭐（需要改进）
- 0-49：较差 ⭐（存在明显缺陷）

## 改进建议

"""

    if total == 0:
        report += """### 开始编写测试
1. 选择适合当前语言/技术栈的测试框架
2. 优先为核心功能编写测试
3. 争取达到至少 70% 的代码覆盖率
4. 配置持续集成以自动运行测试

"""
    elif score < 70:
        report += """### 优先事项
1. 修复所有失败的测试
2. 排查失败的根本原因
3. 补充关键路径的测试覆盖
4. 重新运行测试直至得分 >= 70

"""

    if failed_tests:
        report += "### 需修复的失败测试\n"
        for idx, t in enumerate(failed_tests[:5], 1):
            report += f"{idx}. `{t['name']}`\n"
        if len(failed_tests) > 5:
            report += f"\n...以及另外 {len(failed_tests) - 5} 个\n"
        report += "\n"

    report += """## 后续步骤

"""
    if total == 0:
        report += """1. 为项目搭建测试框架
2. 为核心功能编写初始测试
3. 重新运行分析：`/api/runner/run-tests`

"""
    else:
        report += """1. 排查失败测试并修复底层问题
2. 重新运行测试：`/api/runner/run-tests`
3. 目标：通过率达到 70%+（良好评级）
4. 目标：通过率达到 90%+（优秀评级）

"""

    report += "---\n\n*由 repos_runner 自动生成 - 仓库测试服务*\n"

    report_path.write_text(report)
