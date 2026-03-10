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
        grade = "Excellent ⭐⭐⭐⭐⭐"
    elif score >= 70:
        grade = "Good ⭐⭐⭐⭐"
    elif score >= 50:
        grade = "Fair ⭐⭐⭐"
    else:
        grade = "Poor ⭐"

    report = f"""# Test Report: {repo_name}

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Overall Score**: {score}/100 ({grade})

## Summary
- **Total Tests**: {total}
- **Passed**: {passed} ({pass_rate:.1f}%)
- **Failed**: {failed} ({fail_rate:.1f}%)
- **Skipped**: 0 (0%)
- **Score**: {score}/100

## Test Results

"""

    if total == 0:
        report += """⚠️ **No tests detected in this repository**

This repository does not appear to have any automated tests configured.

"""

    passed_tests = [t for t in test_results if t["status"] == "passed"]
    failed_tests = [t for t in test_results if t["status"] == "failed"]

    if passed_tests:
        report += f"### ✅ Passed Tests ({len(passed_tests)})\n\n"
        for t in passed_tests:
            duration = t.get("duration", 0)
            report += f"- `{t['name']}` ({duration:.2f}s)\n"
        report += "\n"

    if failed_tests:
        report += f"### ❌ Failed Tests ({len(failed_tests)})\n\n"
        for t in failed_tests:
            duration = t.get("duration", 0)
            report += f"- `{t['name']}` ({duration:.2f}s)\n"
            output = t.get("output", "")
            if output:
                truncated_output = output[-500:] if len(output) > 500 else output
                report += f"  ```\n  {truncated_output}\n  ```\n"
        report += "\n"

    report += f"""## Score Breakdown

- **Pass Rate**: {pass_rate:.1f}% ({passed}/{total})
- **Final Score**: {score}/100
"""

    if feature_coverage:
        covered = feature_coverage.get("covered", [])
        not_covered = feature_coverage.get("not_covered", [])
        total_features = len(covered) + len(not_covered)
        coverage_pct = feature_coverage.get("coverage_ratio", 1.0) * 100
        report += f"""- **Feature Coverage**: {len(covered)}/{total_features} features ({coverage_pct:.0f}%)
- **Score Formula**: pass_rate ({pass_rate:.1f}%) × feature_coverage ({coverage_pct:.0f}%) = {score}/100
"""
    report += "\n"

    if feature_coverage:
        covered = feature_coverage.get("covered", [])
        not_covered = feature_coverage.get("not_covered", [])
        total_features = len(covered) + len(not_covered)
        coverage_pct = feature_coverage.get("coverage_ratio", 1.0) * 100
        test_files_found = feature_coverage.get("test_files_found", [])

        report += f"## Feature Coverage ({len(covered)}/{total_features} — {coverage_pct:.0f}%)\n\n"

        if tag_message:
            report += f"> **Tag annotation**: {tag_message}\n\n"

        report += (
            "Features are extracted from the tag annotation message and cross-checked "
            "against the test files in the repository. Each uncovered feature reduces "
            "the maximum achievable score proportionally.\n\n"
        )

        if covered:
            report += f"### ✅ Covered ({len(covered)})\n\n"
            for f in covered:
                report += f"- {f}\n"
            report += "\n"

        if not_covered:
            report += f"### ❌ Not Covered ({len(not_covered)})\n\n"
            for f in not_covered:
                report += f"- {f}\n"
            report += "\n"

        if test_files_found:
            report += f"### Test Files Scanned ({len(test_files_found)})\n\n"
            for tf in test_files_found:
                report += f"- `{tf}`\n"
            report += "\n"
        else:
            report += "> ⚠️ No test files were found — all features counted as not covered.\n\n"

    elif tag_message:
        # tag_message present but no feature_coverage (extraction returned nothing)
        report += f"## Feature Coverage\n\n> **Tag annotation**: {tag_message}\n\n"
        report += "> ⚠️ No testable features could be extracted from the tag message.\n\n"

    report += """### Grade Scale
- 90-100: Excellent ⭐⭐⭐⭐⭐ (Production ready)
- 70-89: Good ⭐⭐⭐⭐ (Minor gaps acceptable)
- 50-69: Fair ⭐⭐⭐ (Needs improvement)
- 0-49: Poor ⭐ (Significant gaps)

## Recommendations

"""

    if total == 0:
        report += """### Get Started with Testing
1. Choose a testing framework appropriate for your language/stack
2. Write tests for critical functionality first
3. Aim for at least 70% code coverage
4. Set up continuous integration to run tests automatically

"""
    elif score < 70:
        report += """### Priority Actions
1. Fix all failing tests
2. Investigate root causes of failures
3. Add missing test coverage for critical paths
4. Re-run tests until score >= 70

"""

    if failed_tests:
        report += "### Failed Tests to Fix\n"
        for idx, t in enumerate(failed_tests[:5], 1):
            report += f"{idx}. `{t['name']}`\n"
        if len(failed_tests) > 5:
            report += f"\n...and {len(failed_tests) - 5} more\n"
        report += "\n"

    report += """## Next Steps

"""
    if total == 0:
        report += """1. Set up a testing framework for your project
2. Write initial tests for core functionality
3. Run analysis again: `/api/runner/run-tests`

"""
    else:
        report += """1. Review failed tests and fix underlying issues
2. Run tests again: `/api/runner/run-tests`
3. Aim for 70%+ pass rate (Good rating)
4. Target 90%+ pass rate (Excellent rating)

"""

    report += "---\n\n*Generated by repos_runner - Automated repository testing service*\n"

    report_path.write_text(report)
