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

    assert "## 待测仓库功能" in report
    assert '### 老师要求（可以为空，为空则表示"学生任意发挥"）' in report
    assert "- /health 可返回正确 JSON" in report
    assert "### 学生自述功能" in report
    assert "class-01" in report


def test_generate_test_report_keeps_failed_output_fence_before_functionality_section(tmp_path):
    report_path = tmp_path / "TEST_REPORT_class-01.md"

    asyncio.run(
        _generate_test_report(
            report_path=report_path,
            repo_name="demo",
            total=2,
            passed=1,
            failed=1,
            score=29,
            test_results=[
                {
                    "name": "curl http://localhost:8000/health",
                    "status": "passed",
                    "duration": 0.02,
                    "output": "",
                },
                {
                    "name": "curl http://localhost:8200/health",
                    "status": "failed",
                    "duration": 0.02,
                    "output": (
                        "  % Total    % Received % Xferd  Average Speed   Time\n"
                        "\n"
                        "  0     0    0     0    0     0      0      0\n"
                        "curl: (7) Failed to connect to localhost port 8200\n"
                    ),
                },
            ],
            feature_coverage={
                "covered": ["Health endpoint"],
                "not_covered": ["Homepage loads"],
                "coverage_ratio": 0.5,
                "test_files_found": [],
            },
            tag_message="## Course tag requirements\n\n- /health 可返回正确 JSON",
        )
    )

    report = report_path.read_text(encoding="utf-8")
    failed_section_start = report.index("### ❌ 失败的测试")
    functionality_section_start = report.index("## 功能验收")
    failed_section = report[failed_section_start:functionality_section_start]

    assert "\n```\n" in failed_section
    assert "\n```\n\n## 功能验收" in report
    assert "\n  ```\n" not in failed_section


def test_generate_test_report_uses_absolute_runtime_artifact_urls(tmp_path, monkeypatch):
    report_path = tmp_path / "TEST_REPORT_class-01.md"
    monkeypatch.setenv("RUNNER_PUBLIC_BASE_URL", "http://localhost:8001/")

    asyncio.run(
        _generate_test_report(
            report_path=report_path,
            repo_name="demo",
            total=1,
            passed=1,
            failed=0,
            score=100,
            test_results=[],
            runtime_evidence={
                "summary": {"passed": 1, "total": 1},
                "checks": [
                    {
                        "id": "homepage_opens",
                        "label": "homepage opens",
                        "passed": True,
                        "evidence": "http://127.0.0.1:3003",
                        "screenshots": [
                            "TEST_ARTIFACTS_class-01/runtime-evidence/screenshots/homepage.png"
                        ],
                    }
                ],
            },
        )
    )

    report = report_path.read_text(encoding="utf-8")

    assert (
        "![homepage_opens](http://localhost:8001/api/runner/artifact?"
        "repo_name=demo&path=TEST_ARTIFACTS_class-01%2Fruntime-evidence%2Fscreenshots%2Fhomepage.png)"
        in report
    )
    assert "![homepage_opens](/api/runner/artifact?" not in report
