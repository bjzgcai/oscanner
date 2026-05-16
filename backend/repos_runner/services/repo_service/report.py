"""
Test report generation (TEST_REPORT.md).
"""

from datetime import datetime
import os
from pathlib import Path
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

DEFAULT_CODE_TEST_WEIGHT = 30
DEFAULT_FUNCTIONALITY_WEIGHT = 70


def _split_tag_message(tag_message: Optional[str]) -> Dict[str, str]:
    text = str(tag_message or "").strip()
    if not text:
        return {"teacher": "", "student": ""}

    course_marker = re.search(
        r"^##\s*Course tag requirements\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    repo_marker = re.search(
        r"^##\s*Repository tag description\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if course_marker or repo_marker:
        teacher = ""
        student = ""
        if course_marker:
            start = course_marker.end()
            end = repo_marker.start() if repo_marker and repo_marker.start() > start else len(text)
            teacher = text[start:end].strip()
        if repo_marker:
            student = text[repo_marker.end():].strip()
        return {"teacher": teacher, "student": student}

    return {"teacher": "", "student": text}


def _format_features_to_test_section(tag_message: Optional[str]) -> str:
    parts = _split_tag_message(tag_message)
    teacher = parts["teacher"]
    student = parts["student"]
    if not teacher and not student:
        return ""

    section = "## 待测仓库功能\n\n"
    section += '### 老师要求（可以为空，为空则表示"学生任意发挥"）\n\n'
    section += f"{teacher}\n\n" if teacher else "> 未配置课程标签要求。\n\n"
    section += "### 学生自述功能\n\n"
    section += f"{student}\n\n" if student else "> 学生仓库标签未提供自述功能。\n\n"
    return section


def _check_group(check: Dict[str, Any]) -> str:
    check_id = str(check.get("id") or "")
    if check_id == "repository_static_inventory" or check_id.startswith("dynamic_static_"):
        return "静态功能检查"
    if check_id.startswith("dynamic_ui_"):
        return "UI Evidence"
    return "API / 服务运行验证"


def _format_fenced_block(content: str) -> str:
    fence = "```"
    while fence in content:
        fence += "`"
    return f"{fence}\n{content.rstrip()}\n{fence}\n"


def _format_execution_process_section(lines: Optional[List[str]]) -> str:
    clean_lines = []
    for line in lines or []:
        clean_line = str(line or "").strip()
        if clean_line:
            clean_lines.append(clean_line)
    if not clean_lines:
        return ""
    process_body = "\n".join(clean_lines)
    return (
        "## 执行过程\n\n"
        "```text\n"
        f"{process_body}\n"
        "```\n\n"
    )


def _artifact_image_url(repo_name: str, artifact_path: str) -> str:
    query = urlencode({"repo_name": repo_name, "path": artifact_path})
    base_url = os.getenv("RUNNER_PUBLIC_BASE_URL", "http://localhost:8001").rstrip("/")
    return f"{base_url}/api/runner/artifact?{query}"


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
    runtime_evidence: Optional[Dict[str, Any]] = None,
    score_breakdown: Optional[Dict[str, Any]] = None,
    execution_process: Optional[List[str]] = None,
) -> None:
    """Generate TEST_REPORT.md for analyzed repository."""
    pass_rate = (passed / total * 100) if total > 0 else 0
    fail_rate = (failed / total * 100) if total > 0 else 0
    has_functionality_score = bool(feature_coverage or tag_message)
    coverage_ratio = 0.0
    total_features = 0
    covered_features = []
    not_covered_features = []
    if feature_coverage:
        covered_features = feature_coverage.get("covered", [])
        not_covered_features = feature_coverage.get("not_covered", [])
        total_features = len(covered_features) + len(not_covered_features)
        coverage_ratio = float(feature_coverage.get("coverage_ratio", 1.0))
    if score_breakdown:
        code_max = int(score_breakdown.get("code_weight", 100 if not has_functionality_score else DEFAULT_CODE_TEST_WEIGHT))
        functionality_max = int(score_breakdown.get("functionality_weight", 0 if not has_functionality_score else DEFAULT_FUNCTIONALITY_WEIGHT))
        code_score = int(score_breakdown.get("code_score", 0))
        functionality_score = int(score_breakdown.get("functionality_score", 0))
        weight_explanation = str(score_breakdown.get("weight_explanation") or "").strip()
    else:
        code_max = 100 if not has_functionality_score else DEFAULT_CODE_TEST_WEIGHT
        functionality_max = 0 if not has_functionality_score else DEFAULT_FUNCTIONALITY_WEIGHT
        code_score = int((passed / total if total > 0 else 0) * code_max)
        functionality_score = int(coverage_ratio * functionality_max)
        weight_explanation = ""

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
- **代码测试分数**：{code_score}/{code_max}（通过 {passed} / 失败 {failed}）

"""

    if has_functionality_score:
        report += (
            f"- **功能测试分数**：{functionality_score}/{functionality_max}\n"
            f"- **总分**：代码测试 {code_score} + 功能测试 {functionality_score} = {score}/100\n"
            f"- **权重说明**：代码测试权重 {code_max}%，功能验收权重 {functionality_max}%。"
            f"{weight_explanation or '代码测试按通过率计分；功能验收按功能覆盖率计分。'}\n\n"
        )
    else:
        report += "- **功能测试分数**：未启用（未提供标签要求）\n"
        report += f"- **总分**：代码测试 {code_score} = {score}/100\n\n"

    report += _format_features_to_test_section(tag_message)
    report += _format_execution_process_section(execution_process)

    report += f"""

## 代码测试

- **代码测试权重**：{code_max}/100
- **代码测试得分**：{code_score}/{code_max}
- **代码测试通过率**：{pass_rate:.1f}%（{passed}/{total}）

"""

    if total == 0:
        report += """⚠️ **未检测到测试用例**

该仓库似乎没有配置任何自动化测试。

"""

    passed_tests = [t for t in test_results if t["status"] == "passed"]
    failed_tests = [t for t in test_results if t["status"] == "failed"]
    no_test_commands = [t for t in test_results if t["status"] == "no_tests"]

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
                report += f"\n{_format_fenced_block(truncated_output)}"
        report += "\n"

    if no_test_commands:
        report += f"### ⚠️ 未收集到测试用例的命令（{len(no_test_commands)}）\n\n"
        for t in no_test_commands:
            duration = t.get("duration", 0)
            report += f"- `{t['name']}` （{duration:.2f}s）\n"
            output = t.get("output", "")
            if output:
                truncated_output = output[-500:] if len(output) > 500 else output
                report += f"\n{_format_fenced_block(truncated_output)}"
        report += "\n"

    if feature_coverage:
        covered = covered_features
        not_covered = not_covered_features
        coverage_pct = coverage_ratio * 100
        test_files_found = feature_coverage.get("test_files_found", [])

        report += f"## 功能验收\n\n"
        report += f"- **功能验收权重**：{functionality_max}/100\n"
        report += f"- **功能验收得分**：{functionality_score}/{functionality_max}\n"
        report += f"- **功能覆盖率**：{len(covered)}/{total_features} 个功能（{coverage_pct:.0f}%）\n\n"
        report += f"### 功能覆盖（{len(covered)}/{total_features} — {coverage_pct:.0f}%）\n\n"

        report += (
            "功能列表从上方“待测仓库功能”提取，并与仓库测试文件、静态检查、"
            "服务运行验证和 UI evidence 交叉比对。每个功能只计入一次。\n\n"
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
        report += "## 功能验收\n\n"
        report += f"- **功能验收权重**：{functionality_max}/100\n"
        report += f"- **功能验收得分**：0/{functionality_max}\n\n"
        report += "> ⚠️ 无法从标签说明中提取可测试的功能点。\n\n"
        report += "> 功能验收部分计为 0 分；代码测试部分仍按通过率计分。\n\n"

    if runtime_evidence:
        checks = runtime_evidence.get("checks", [])
        summary = runtime_evidence.get("summary") or {}
        passed_checks = summary.get(
            "passed",
            len([check for check in checks if check.get("passed")]),
        )
        total_checks = summary.get("total", len(checks))

        report += "## 运行时功能验证\n\n"
        report += f"- **验证结果**：{passed_checks}/{total_checks} 项通过\n"
        if runtime_evidence.get("commands"):
            report += "- **启动来源**：README/文档中的安全启动命令\n"
        for warning in (runtime_evidence.get("warnings") or [])[:3]:
            report += f"- **警告**：{warning}\n"
        report += "\n"

        for group_name in ["静态功能检查", "API / 服务运行验证", "UI Evidence"]:
            group_checks = [check for check in checks if _check_group(check) == group_name]
            if not group_checks:
                continue
            report += f"### {group_name}\n\n"
            for check in group_checks:
                icon = "✅" if check.get("passed") else "❌"
                label = check.get("label") or check.get("id") or "runtime check"
                report += f"#### {icon} {label}\n\n"
                evidence = str(check.get("evidence") or "").strip()
                if evidence:
                    report += f"- 证据：{evidence}\n"
                for screenshot in check.get("screenshots") or []:
                    image_url = _artifact_image_url(repo_name, str(screenshot))
                    report += f"- 截图：![{check.get('id', 'screenshot')}]({image_url})\n"
                report += "\n"

    report += "## 得分明细\n\n"
    if has_functionality_score:
        report += (
            f"- **代码测试得分**：{code_score}/{code_max} "
            f"（通过率 {pass_rate:.1f}% × 权重 {code_max}）\n"
            f"- **功能验收得分**：{functionality_score}/{functionality_max} "
            f"（功能覆盖率 {coverage_ratio * 100:.0f}% × 权重 {functionality_max}）\n"
            f"- **最终得分**：{score}/100\n"
            f"- **评分公式**：代码测试 × 代码测试权重 + 功能验收 × 功能验收权重 = "
            f"{code_score} + {functionality_score} = {score}/100\n\n"
            f"> 权重：代码测试权重 {code_max}%，功能验收权重 {functionality_max}%。"
            f"代码测试按通过率计分，功能验收按功能覆盖率计分。\n\n"
        )
    else:
        report += (
            f"- **通过率**：{pass_rate:.1f}%（{passed}/{total}）\n"
            f"- **最终得分**：{score}/100\n"
            f"- **评分公式**：代码测试通过率（{pass_rate:.1f}%）× 100 = {score}/100\n\n"
        )

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
