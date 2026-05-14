import asyncio
import sys
from pathlib import Path


def test_run_tests_uses_docker_session_without_host_venv_rewrite(monkeypatch, tmp_path):
    from repos_runner.services.repo_service import runner as runner_service

    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    overview = clone_dir / "REPO_OVERVIEW_v1.md"
    overview.write_text("overview", encoding="utf-8")

    commands_seen = []

    class _Result:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    class _FakeSession:
        is_docker = True

        def __init__(self, repo_dir):
            self.repo_dir = Path(repo_dir)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, cmd, *, cwd, timeout, env=None):
            commands_seen.append(cmd)
            return _Result()

    monkeypatch.setattr(runner_service, "create_execution_session", lambda repo_dir: _FakeSession(repo_dir))
    monkeypatch.setattr(
        runner_service,
        "_detect_frameworks_statically",
        lambda _clone_dir: {
            "language": "python",
            "setup_commands": ["pip install -r requirements.txt || true"],
            "test_commands": ["pytest tests -v || true"],
        },
    )
    monkeypatch.setattr(runner_service, "_find_test_files", lambda _clone_dir, _language: [])
    monkeypatch.setattr(runner_service, "ensure_repo_venv", lambda _clone_path: Path(sys.executable))
    monkeypatch.setattr(runner_service, "_parse_json_report", lambda _clone_dir: None)

    async def fake_parse(_output):
        return {"passed": 1, "failed": 0, "total": 1}

    monkeypatch.setattr(runner_service, "_parse_test_output", fake_parse)

    result = asyncio.run(
        runner_service.run_tests(
            str(clone_dir),
            str(overview),
            tag="v1",
        )
    )

    assert commands_seen == [
        "pip install -r requirements.txt || true",
        "pip install pytest pytest-json-report",
        "pytest tests -v",
    ]
    assert all(str(sys.executable) not in command for command in commands_seen)
    assert result["report_path"].endswith("TEST_REPORT_v1.md")


def test_run_tests_strips_shell_success_mask_and_counts_import_error_as_failure(monkeypatch, tmp_path):
    from repos_runner.services.repo_service import runner as runner_service

    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    overview = clone_dir / "REPO_OVERVIEW_v1.md"
    overview.write_text("overview", encoding="utf-8")

    commands_seen = []

    class _Result:
        returncode = 1
        stdout = ""
        stderr = (
            "ImportError while loading conftest '/workspace/tests/conftest.py'.\n"
            "E   ModuleNotFoundError: No module named 'fastapi'\n"
        )

    class _FakeSession:
        is_docker = True

        def __init__(self, repo_dir):
            self.repo_dir = Path(repo_dir)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, cmd, *, cwd, timeout, env=None):
            commands_seen.append(cmd)
            return _Result()

    monkeypatch.setattr(runner_service, "create_execution_session", lambda repo_dir: _FakeSession(repo_dir))
    monkeypatch.setattr(
        runner_service,
        "_detect_frameworks_statically",
        lambda _clone_dir: {
            "language": "python",
            "setup_commands": [],
            "test_commands": ["pytest tests -v || true"],
        },
    )
    monkeypatch.setattr(runner_service, "_find_test_files", lambda _clone_dir, _language: [])
    monkeypatch.setattr(runner_service, "_parse_json_report", lambda _clone_dir: None)

    async def fake_parse(_output):
        return None

    monkeypatch.setattr(runner_service, "_parse_test_output", fake_parse)

    result = asyncio.run(
        runner_service.run_tests(
            str(clone_dir),
            str(overview),
            tag="v1",
        )
    )

    assert commands_seen[-1] == "pytest tests -v"
    assert result["passed"] == 0
    assert result["failed"] == 1
    assert result["score"] == 0
    assert result["details"][0]["status"] == "failed"


def test_run_tests_installs_nested_python_requirements(monkeypatch, tmp_path):
    from repos_runner.services.repo_service import runner as runner_service

    clone_dir = tmp_path / "repo"
    nested = clone_dir / "services" / "app_backend"
    nested.mkdir(parents=True)
    (nested / "requirements.txt").write_text("fastapi==0.116.1\n", encoding="utf-8")
    overview = clone_dir / "REPO_OVERVIEW_v1.md"
    overview.write_text("overview", encoding="utf-8")

    commands_seen = []

    class _Result:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    class _FakeSession:
        is_docker = True

        def __init__(self, repo_dir):
            self.repo_dir = Path(repo_dir)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, cmd, *, cwd, timeout, env=None):
            commands_seen.append(cmd)
            return _Result()

    monkeypatch.setattr(runner_service, "create_execution_session", lambda repo_dir: _FakeSession(repo_dir))
    monkeypatch.setattr(
        runner_service,
        "_detect_frameworks_statically",
        lambda _clone_dir: {
            "language": "python",
            "setup_commands": [],
            "test_commands": ["pytest services/app_backend/tests -v"],
        },
    )
    monkeypatch.setattr(runner_service, "_find_test_files", lambda _clone_dir, _language: [])
    monkeypatch.setattr(runner_service, "_parse_json_report", lambda _clone_dir: None)

    async def fake_parse(_output):
        return {"passed": 1, "failed": 0, "total": 1}

    monkeypatch.setattr(runner_service, "_parse_test_output", fake_parse)

    asyncio.run(
        runner_service.run_tests(
            str(clone_dir),
            str(overview),
            tag="v1",
        )
    )

    assert "pip install -r services/app_backend/requirements.txt" in commands_seen
    assert commands_seen[-1] == "pytest services/app_backend/tests -v"


def test_run_tests_warms_each_nested_service_venv_in_docker(monkeypatch, tmp_path):
    from repos_runner.services.repo_service import runner as runner_service

    clone_dir = tmp_path / "repo"
    app_backend = clone_dir / "services" / "app_backend"
    domain_layer = clone_dir / "services" / "domain_layer"
    app_backend.mkdir(parents=True)
    domain_layer.mkdir(parents=True)
    requirements = "fastapi==0.116.1\nuvicorn==0.35.0\n"
    (app_backend / "requirements.txt").write_text(requirements, encoding="utf-8")
    (domain_layer / "requirements.txt").write_text(requirements, encoding="utf-8")
    overview = clone_dir / "REPO_OVERVIEW_v1.md"
    overview.write_text("overview", encoding="utf-8")

    commands_seen = []

    class _Result:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    class _FakeSession:
        is_docker = True

        def __init__(self, repo_dir):
            self.repo_dir = Path(repo_dir)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, cmd, *, cwd, timeout, env=None):
            commands_seen.append(cmd)
            return _Result()

    monkeypatch.setattr(runner_service, "create_execution_session", lambda repo_dir: _FakeSession(repo_dir))
    monkeypatch.setattr(
        runner_service,
        "_detect_frameworks_statically",
        lambda _clone_dir: {
            "language": "python",
            "setup_commands": [],
            "test_commands": ["pytest services -v"],
        },
    )
    monkeypatch.setattr(runner_service, "_find_test_files", lambda _clone_dir, _language: [])
    monkeypatch.setattr(runner_service, "_parse_json_report", lambda _clone_dir: None)

    async def fake_parse(_output):
        return {"passed": 1, "failed": 0, "total": 1}

    monkeypatch.setattr(runner_service, "_parse_test_output", fake_parse)

    asyncio.run(
        runner_service.run_tests(
            str(clone_dir),
            str(overview),
            tag="v1",
        )
    )

    install_index = next(
        index
        for index, command in enumerate(commands_seen)
        if command.startswith("pip install -r services/")
    )
    app_venv_index = commands_seen.index(
        "python -m venv --clear --system-site-packages services/app_backend/.venv"
        " && services/app_backend/.venv/bin/python -m pip --version"
    )
    domain_venv_index = commands_seen.index(
        "python -m venv --clear --system-site-packages services/domain_layer/.venv"
        " && services/domain_layer/.venv/bin/python -m pip --version"
    )
    assert install_index < app_venv_index < commands_seen.index("pytest services -v")
    assert install_index < domain_venv_index < commands_seen.index("pytest services -v")
