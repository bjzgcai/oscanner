import asyncio
import sys
from pathlib import Path


from repos_runner.services.repo_service import runtime_evidence
from repos_runner.services.repo_service.report import _generate_test_report


def test_discover_documented_start_commands_prefers_safe_readme_commands(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        """
## Start

```bash
python scripts/dev-frontend.py
python scripts/dev-app-backend.py
python scripts/start.py status
python scripts/tasks.py check
python scripts/check.py
rm -rf /
```
""",
        encoding="utf-8",
    )
    scripts = repo / "scripts"
    scripts.mkdir()
    for name in ["dev-frontend.py", "dev-app-backend.py", "start.py", "tasks.py", "check.py"]:
        (scripts / name).write_text("print('ok')\n", encoding="utf-8")

    commands = runtime_evidence.discover_documented_start_commands(repo)

    assert [item["command"] for item in commands] == [
        "python scripts/dev-frontend.py",
        "python scripts/dev-app-backend.py",
        "python scripts/check.py",
    ]
    assert all("rm -rf" not in item["command"] for item in commands)
    assert all("scripts/start.py status" not in item["command"] for item in commands)
    assert all("scripts/tasks.py check" not in item["command"] for item in commands)


def test_merge_runtime_feature_coverage_moves_proven_features():
    feature_coverage = {
        "covered": ["Health endpoint returns JSON"],
        "not_covered": [
            "Docs endpoint accessible",
            ".harness README.md created",
        ],
        "coverage_ratio": 1 / 3,
        "test_files_found": ["tests/test_app.py"],
    }
    evidence = {
        "covered_features": ["Docs endpoint accessible"],
        "checks": [
            {
                "id": "harness_readme",
                "passed": True,
                "features": [".harness README.md created"],
                "screenshots": [],
            }
        ],
    }

    merged = runtime_evidence.merge_runtime_feature_coverage(feature_coverage, evidence)

    assert merged["coverage_ratio"] == 1.0
    assert merged["not_covered"] == []
    assert merged["runtime_covered"] == [
        "Docs endpoint accessible",
        ".harness README.md created",
    ]


def test_runtime_subprocess_env_does_not_forward_tokens(monkeypatch):
    monkeypatch.setenv("GITEE_TOKEN", "secret")
    monkeypatch.setenv("OPEN_ROUTER_KEY", "secret")

    env = runtime_evidence.runtime_subprocess_env()

    assert "GITEE_TOKEN" not in env
    assert "OPEN_ROUTER_KEY" not in env
    assert env["CI"] == "1"


def test_generate_test_report_includes_runtime_evidence(tmp_path):
    report_path = tmp_path / "TEST_REPORT.md"

    asyncio.run(
        _generate_test_report(
            report_path=report_path,
            repo_name="demo",
            total=1,
            passed=1,
            failed=0,
            score=100,
            test_results=[
                {
                    "name": "pytest",
                    "status": "passed",
                    "duration": 0.1,
                    "output": "",
                }
            ],
            feature_coverage={
                "covered": ["Docs endpoint accessible"],
                "not_covered": [],
                "coverage_ratio": 1.0,
                "test_files_found": ["tests/test_app.py"],
            },
            tag_message="- `/docs` 可访问",
            runtime_evidence={
                "summary": {"passed": 1, "total": 1},
                "checks": [
                    {
                        "id": "docs_accessible",
                        "label": "/docs accessible",
                        "passed": True,
                        "evidence": "http://127.0.0.1:8000/docs",
                        "screenshots": ["TEST_ARTIFACTS/runtime/screenshots/docs.png"],
                    }
                ],
                "warnings": [],
            },
        )
    )

    report = report_path.read_text(encoding="utf-8")
    assert "## 运行时功能验证" in report
    assert "1/1 项通过" in report
    assert "TEST_ARTIFACTS/runtime/screenshots/docs.png" in report


def test_run_tests_applies_runtime_evidence_to_score(monkeypatch, tmp_path):
    from repos_runner.services.repo_service import runner as runner_service

    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    overview = clone_dir / "REPO_OVERVIEW_class-01.md"
    overview.write_text("overview", encoding="utf-8")

    monkeypatch.setattr(
        runner_service,
        "_detect_frameworks_statically",
        lambda _clone_dir: {
            "language": "python",
            "test_commands": ["pytest tests -v || true"],
            "setup_commands": [],
        },
    )
    monkeypatch.setattr(runner_service, "_find_test_files", lambda _clone_dir, _language: [])
    monkeypatch.setattr(runner_service, "ensure_repo_venv", lambda _clone_path: sys.executable)

    class _SandboxResult:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    monkeypatch.setattr(runner_service, "run_sandboxed", lambda *args, **kwargs: _SandboxResult())
    monkeypatch.setattr(runner_service, "_parse_json_report", lambda _clone_dir: None)

    async def _fake_parse_test_output(_output):
        return {"passed": 1, "failed": 0, "total": 1}

    async def _fake_extract_features(_message):
        return ["Health endpoint returns JSON", "Docs endpoint accessible"]

    async def _fake_check_feature_coverage(_clone_dir, _features):
        return {
            "covered": ["Health endpoint returns JSON"],
            "not_covered": ["Docs endpoint accessible"],
            "coverage_ratio": 0.5,
            "test_files_found": ["tests/test_app.py"],
        }

    async def _fake_collect_runtime_evidence(_clone_dir, tag="", progress_callback=None):
        return {
            "summary": {"passed": 1, "total": 1},
            "covered_features": ["Docs endpoint accessible"],
            "checks": [
                {
                    "id": "docs_accessible",
                    "label": "/docs accessible",
                    "passed": True,
                    "features": ["Docs endpoint accessible"],
                    "evidence": "HTTP 200",
                    "screenshots": ["TEST_ARTIFACTS/runtime/screenshots/docs.png"],
                }
            ],
        }

    monkeypatch.setattr(runner_service, "_parse_test_output", _fake_parse_test_output)
    monkeypatch.setattr(runner_service, "_extract_features_from_tag_message", _fake_extract_features)
    monkeypatch.setattr(runner_service, "_check_feature_coverage", _fake_check_feature_coverage)
    monkeypatch.setattr(runner_service, "collect_runtime_evidence", _fake_collect_runtime_evidence)

    result = asyncio.run(
        runner_service.run_tests(
            str(clone_dir),
            str(overview),
            tag_message="- `/health` and `/docs`",
            tag="class-01",
        )
    )

    assert result["score"] == 100
    assert result["feature_coverage"]["coverage_ratio"] == 1.0
    assert result["runtime_evidence"]["summary"] == {"passed": 1, "total": 1}
    assert "运行时功能验证" in Path(result["report_path"]).read_text(encoding="utf-8")
