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


def test_discover_documented_start_commands_follows_readme_cd_context_for_uvicorn(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        """
### 启动后端服务

```bash
# app_backend (端口 8000)
cd services/app_backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 启动前端

```bash
cd frontend
npm install
npm run dev
```
""",
        encoding="utf-8",
    )
    (repo / "services" / "app_backend" / "app").mkdir(parents=True)
    (repo / "services" / "app_backend" / "requirements.txt").write_text(
        "fastapi\nuvicorn\n",
        encoding="utf-8",
    )
    (repo / "services" / "app_backend" / "app" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )
    (repo / "frontend").mkdir()
    (repo / "frontend" / "package.json").write_text(
        '{"scripts":{"dev":"vite"}}',
        encoding="utf-8",
    )

    commands = runtime_evidence.discover_documented_start_commands(repo)

    assert commands == [
        {
            "command": (
                "python -m venv .venv && . .venv/bin/activate && "
                "python -m pip install -r requirements.txt && "
                "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
            ),
            "cwd": "services/app_backend",
            "source": "README.md",
        },
        {
            "command": "npm run dev -- --host 127.0.0.1",
            "cwd": "frontend",
            "source": "README.md",
        },
    ]


def test_start_process_runs_canonical_shell_commands_through_sh(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    artifact_dir = repo / "artifacts"
    captured = {}

    class _FakeProcess:
        pass

    def _fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr(runtime_evidence.subprocess, "Popen", _fake_popen)

    command = "python -m venv .venv && . .venv/bin/activate && python -m uvicorn app.main:app --port 8000"
    proc = runtime_evidence._start_process(
        {"command": command, "cwd": ".", "source": "README.md"},
        repo,
        artifact_dir,
    )

    assert isinstance(proc, _FakeProcess)
    assert captured["args"] == ["/bin/sh", "-c", command]
    assert captured["kwargs"]["cwd"] == repo


def test_ai_compatible_commands_are_validated_and_normalized(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    (repo / "services" / "domain_layer" / "app").mkdir(parents=True)
    (repo / "services" / "domain_layer" / "requirements.txt").write_text(
        "fastapi\nuvicorn\n",
        encoding="utf-8",
    )
    (repo / "services" / "domain_layer" / "app" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )

    class _Message:
        content = [
            {
                "text": """
[
  {"command": "uvicorn app.main:app --reload --port 8200", "cwd": "services/domain_layer", "source": "README.md"},
  {"command": "rm -rf /", "cwd": ".", "source": "README.md"}
]
"""
            }
        ]

    monkeypatch.setenv("REPOS_RUNNER_RUNTIME_COMPAT_LLM", "true")
    monkeypatch.setattr(runtime_evidence, "_messages_create_with_fallback", lambda **_kwargs: _Message())

    commands = runtime_evidence.discover_documented_start_commands(repo)

    assert commands == [
        {
            "command": (
                "python -m pip install -r requirements.txt && "
                "python -m uvicorn app.main:app --host 127.0.0.1 --port 8200"
            ),
            "cwd": "services/domain_layer",
            "source": "README.md",
        }
    ]


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


def test_static_runtime_checks_cover_broad_scaffold_harness_and_env_features(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    (repo / ".env").write_text("ARCHIVE_SCENE=college\n", encoding="utf-8")
    (repo / "frontend").mkdir()
    (repo / "services" / "app_backend").mkdir(parents=True)
    (repo / "services" / "domain_layer").mkdir(parents=True)
    (repo / "scripts").mkdir()
    harness = repo / ".harness"
    harness.mkdir()
    (harness / "README.md").write_text("harness\n", encoding="utf-8")
    (harness / "ROADMAP.md").write_text("roadmap\n", encoding="utf-8")
    for dirname in ["rules", "specs", "datasets", "eval", "logs"]:
        (harness / dirname).mkdir()

    checks = runtime_evidence._static_feature_checks(repo)
    evidence = {"covered_features": [], "checks": checks}
    feature_coverage = {
        "covered": [],
        "not_covered": [
            "Project skeleton initialization",
            "Harness directory setup",
            "Environment configuration",
        ],
        "coverage_ratio": 0.0,
        "test_files_found": [],
    }

    merged = runtime_evidence.merge_runtime_feature_coverage(feature_coverage, evidence)

    assert merged["not_covered"] == []
    assert merged["runtime_covered"] == [
        "Project skeleton initialization",
        "Harness directory setup",
        "Environment configuration",
    ]


def test_runtime_subprocess_env_does_not_forward_tokens(monkeypatch):
    monkeypatch.setenv("GITEE_TOKEN", "secret")
    monkeypatch.setenv("OPEN_ROUTER_KEY", "secret")

    env = runtime_evidence.runtime_subprocess_env()

    assert "GITEE_TOKEN" not in env
    assert "OPEN_ROUTER_KEY" not in env
    assert env["CI"] == "1"


def test_collect_runtime_evidence_uses_docker_session_for_ports(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        """
```bash
python scripts/dev-app-backend.py
python scripts/dev-frontend.py
```
""",
        encoding="utf-8",
    )
    scripts = repo / "scripts"
    scripts.mkdir()
    (scripts / "dev-app-backend.py").write_text("print('backend')\n", encoding="utf-8")
    (scripts / "dev-frontend.py").write_text("print('frontend')\n", encoding="utf-8")

    class _FakeDockerSession:
        is_docker = True

        def __init__(self):
            self.started = []
            self.probed = []
            self.screenshots = []

        def start_background(self, command, *, cwd, log_path, env=None):
            self.started.append((command, Path(cwd).relative_to(repo), log_path.name))

        def http_get(self, url, *, expect_json=False, timeout=5):
            self.probed.append((url, expect_json))
            return True, url, "HTTP 200"

        def http_text(self, url, *, timeout=5):
            return "server html without rendered app"

        def dump_dom(self, url, *, timeout=10):
            return "<html><body>scene selection</body></html>"

        def capture_screenshot(self, url, screenshot_path, *, timeout=20):
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
            Path(screenshot_path).write_bytes(b"png")
            self.screenshots.append((url, Path(screenshot_path).name))
            return True

    session = _FakeDockerSession()
    monkeypatch.setattr(
        runtime_evidence,
        "_listening_pids",
        lambda _port: (_ for _ in ()).throw(AssertionError("host ports should not be probed")),
    )

    evidence = asyncio.run(
        runtime_evidence.collect_runtime_evidence(
            repo,
            tag="v1",
            service_timeout=0.1,
            execution_session=session,
        )
    )

    assert evidence["executor"] == "docker"
    assert [item[0] for item in session.started] == [
        "python scripts/dev-app-backend.py",
        "python scripts/dev-frontend.py",
    ]
    assert ("http://127.0.0.1:8000/health", True) in session.probed
    assert any(check["id"] == "app_backend_starts" and check["passed"] for check in evidence["checks"])
    assert ("http://127.0.0.1:8000/docs", "docs.png") in session.screenshots
    assert ("http://127.0.0.1:5173", "homepage.png") in session.screenshots
    assert any(
        check["id"] == "homepage_scene_placeholder"
        and check["passed"]
        and check["screenshots"]
        for check in evidence["checks"]
    )


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
            tag_message=(
                "## Course tag requirements\n\n"
                "- `/docs` 可访问\n\n"
                "## Repository tag description\n\n"
                "项目启动与统一骨架"
            ),
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
            score_breakdown={
                "score": 100,
                "code_score": 40,
                "code_weight": 40,
                "functionality_score": 60,
                "functionality_weight": 60,
                "code_pass_rate": 1.0,
                "functionality_coverage_ratio": 1.0,
                "code_relevance_ratio": 1.0,
                "weight_explanation": "test fixture",
            },
        )
    )

    report = report_path.read_text(encoding="utf-8")
    assert report.index("## 待测仓库功能") < report.index("## 代码测试")
    assert '### 老师要求（可以为空，为空则表示"学生任意发挥"）' in report
    assert "### 学生自述功能" in report
    assert "## 代码测试" in report
    assert "## 功能验收" in report
    assert "代码测试权重" in report
    assert "功能验收权重" in report
    assert "## 运行时功能验证" in report
    assert "1/1 项通过" in report
    assert "TEST_ARTIFACTS/runtime/screenshots/docs.png" in report


def test_generate_test_report_marks_missing_static_runtime_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".harness").mkdir()

    report_path = tmp_path / "TEST_REPORT.md"
    checks = runtime_evidence._static_feature_checks(repo)
    datasets_check = next(check for check in checks if check["id"] == "harness_datasets")

    asyncio.run(
        _generate_test_report(
            report_path=report_path,
            repo_name="demo",
            total=0,
            passed=0,
            failed=0,
            score=0,
            test_results=[],
            runtime_evidence={
                "summary": {"passed": 0, "total": 1},
                "checks": [datasets_check],
                "warnings": [],
            },
        )
    )

    report = report_path.read_text(encoding="utf-8")

    assert "#### ❌ .harness datasets/ exists" in report
    assert "- 证据：.harness/datasets/ 不存在" in report


def test_run_tests_scores_code_and_functionality_independently(monkeypatch, tmp_path):
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
            "test_commands": ["curl http://localhost:8000/health"],
            "setup_commands": [],
        },
    )
    monkeypatch.setattr(runner_service, "_find_test_files", lambda _clone_dir, _language: [])
    monkeypatch.setattr(runner_service, "ensure_repo_venv", lambda _clone_path: sys.executable)

    class _SandboxResult:
        returncode = 7
        stdout = ""
        stderr = "curl: (7) Failed to connect"

    monkeypatch.setattr(runner_service, "run_sandboxed", lambda *args, **kwargs: _SandboxResult())
    monkeypatch.setattr(runner_service, "_parse_json_report", lambda _clone_dir: None)

    async def _fake_parse_test_output(_output):
        return None

    async def _fake_extract_features(_message):
        return ["Health endpoint returns JSON", "Docs endpoint accessible"]

    async def _fake_check_feature_coverage(_clone_dir, _features):
        return {
            "covered": [],
            "not_covered": ["Health endpoint returns JSON", "Docs endpoint accessible"],
            "coverage_ratio": 0.0,
            "test_files_found": [],
        }

    async def _fake_collect_runtime_evidence(_clone_dir, tag="", progress_callback=None, execution_session=None):
        return {
            "summary": {"passed": 2, "total": 2},
            "covered_features": ["Health endpoint returns JSON", "Docs endpoint accessible"],
            "checks": [],
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

    assert result["score"] == 70
    assert result["score_breakdown"]["code_weight"] == 30
    assert result["score_breakdown"]["functionality_weight"] == 70
    assert result["score_breakdown"]["code_relevance_ratio"] == 0.0
    report = Path(result["report_path"]).read_text(encoding="utf-8")
    assert "代码测试得分**：0/30" in report
    assert "功能验收得分**：70/70" in report


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

    async def _fake_collect_runtime_evidence(_clone_dir, tag="", progress_callback=None, execution_session=None):
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

    assert result["score"] == 82
    assert result["score_breakdown"]["code_weight"] == 35
    assert result["score_breakdown"]["functionality_weight"] == 65
    assert result["score_breakdown"]["code_relevance_ratio"] == 0.5
    assert result["feature_coverage"]["coverage_ratio"] == 1.0
    assert result["runtime_evidence"]["summary"] == {"passed": 1, "total": 1}
    assert "运行时功能验证" in Path(result["report_path"]).read_text(encoding="utf-8")
