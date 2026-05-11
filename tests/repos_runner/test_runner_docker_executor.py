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
        "pytest tests -v || true",
    ]
    assert all(str(sys.executable) not in command for command in commands_seen)
    assert result["report_path"].endswith("TEST_REPORT_v1.md")
