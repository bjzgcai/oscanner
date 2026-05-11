"""Tests for displaying full feature requirement text in TEST_REPORT markdown."""

import asyncio

from repos_runner.services.repo_service.report import _generate_test_report


def test_generate_test_report_displays_full_multiline_tag_message(tmp_path):
    report_path = tmp_path / "TEST_REPORT_class-01.md"

    asyncio.run(
        _generate_test_report(
            report_path=report_path,
            repo_name="demo",
            total=1,
            passed=1,
            failed=0,
            score=0,
            test_results=[
                {
                    "name": "pytest services",
                    "status": "passed",
                    "duration": 0.1,
                    "output": "",
                }
            ],
            feature_coverage={
                "covered": [],
                "not_covered": ["Health endpoint"],
                "coverage_ratio": 0.0,
                "test_files_found": ["services/test_app.py"],
            },
            tag_message="## Course tag requirements\n\n- /health 可返回正确 JSON\n\n## Repository tag description\n\nclass-01",
        )
    )

    report = report_path.read_text(encoding="utf-8")

    assert "### 标签说明" in report
    assert "## Course tag requirements" in report
    assert "- /health 可返回正确 JSON" in report
    assert "## Repository tag description" in report
    assert "class-01" in report
