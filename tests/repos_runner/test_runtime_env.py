import asyncio
import json
from pathlib import Path

import pytest

from repos_runner.routes import runner as runner_route
from repos_runner.schemas import RunAllRequest
from repos_runner.services.repo_service.runtime_env import (
    build_runtime_env_context,
    detect_required_env_keys,
)


def test_detect_required_env_keys_from_examples_and_code(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env.example").write_text(
        "DATABASE_URL=\nOPENAI_API_KEY=\nJWT_SECRET=test\n",
        encoding="utf-8",
    )
    (repo / "package.json").write_text(
        '{"scripts":{"test":"node test.js"},"config":"process.env.REDIS_URL"}',
        encoding="utf-8",
    )
    (repo / "app.py").write_text(
        'import os\nvalue = os.getenv("SESSION_SECRET")\n',
        encoding="utf-8",
    )

    assert detect_required_env_keys(repo) == [
        "DATABASE_URL",
        "JWT_SECRET",
        "OPENAI_API_KEY",
        "REDIS_URL",
        "SESSION_SECRET",
    ]


def test_runtime_env_profile_loads_safe_values_and_blocks_paid_keys(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env.example").write_text(
        "DATABASE_URL=\nOPENAI_API_KEY=\nSTRIPE_SECRET_KEY=\nCUSTOM_TEST_VALUE=\n",
        encoding="utf-8",
    )
    profile_dir = tmp_path / "runtime-envs"
    profile_dir.mkdir()
    (profile_dir / "course-a.env").write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://app:app@postgres:5432/app_test",
                "CUSTOM_TEST_VALUE=present",
                "OPENAI_API_KEY=blocked-openai-marker",
                "STRIPE_SECRET_KEY=blocked-stripe-marker",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("REPOS_RUNNER_RUNTIME_ENV_DIR", str(profile_dir))

    context = build_runtime_env_context(repo, profile="course-a")
    report = context.as_report()

    assert context.env["DATABASE_URL"] == "postgresql://app:app@postgres:5432/app_test"
    assert context.env["CUSTOM_TEST_VALUE"] == "present"
    assert "JWT_SECRET" in context.env
    assert "OPENAI_API_KEY" not in context.env
    assert "STRIPE_SECRET_KEY" not in context.env
    assert report["blocked_secret_keys"] == ["OPENAI_API_KEY", "STRIPE_SECRET_KEY"]
    assert report["missing_required_keys"] == ["OPENAI_API_KEY", "STRIPE_SECRET_KEY"]
    assert set(report["safe_default_keys"]) >= {"CI", "DATABASE_URL", "JWT_SECRET"}


def test_runtime_env_strict_policy_fails_when_detected_env_missing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env.example").write_text("CUSTOM_REQUIRED_ENV=\n", encoding="utf-8")

    context = build_runtime_env_context(repo, required_policy="strict")

    assert context.should_fail_on_missing()
    assert context.missing_required_keys == ["CUSTOM_REQUIRED_ENV"]


def test_run_tests_passes_runtime_env_to_setup_and_test(monkeypatch, tmp_path):
    from repos_runner.services.repo_service import runner as runner_service

    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    (clone_dir / ".env.example").write_text("CUSTOM_REQUIRED_ENV=\n", encoding="utf-8")
    profile_dir = tmp_path / "runtime-envs"
    profile_dir.mkdir()
    (profile_dir / "course-a.env").write_text(
        "CUSTOM_REQUIRED_ENV=present\n",
        encoding="utf-8",
    )
    overview = clone_dir / "REPO_OVERVIEW.md"
    overview.write_text("overview", encoding="utf-8")
    monkeypatch.setenv("REPOS_RUNNER_RUNTIME_ENV_DIR", str(profile_dir))
    runtime_env = build_runtime_env_context(clone_dir, profile="course-a")

    captured_envs = []

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
            captured_envs.append(dict(env or {}))
            return _Result()

    monkeypatch.setattr(runner_service, "create_execution_session", lambda repo_dir: _FakeSession(repo_dir))
    monkeypatch.setattr(
        runner_service,
        "_detect_frameworks_statically",
        lambda _clone_dir: {
            "language": "python",
            "setup_commands": ["python -m pip install pytest"],
            "test_commands": ["pytest tests -v"],
        },
    )
    monkeypatch.setattr(runner_service, "_find_test_files", lambda _clone_dir, _language: [])
    monkeypatch.setattr(runner_service, "_parse_json_report", lambda _clone_dir: None)

    async def fake_parse(_output):
        return {"passed": 1, "failed": 0, "total": 1}

    monkeypatch.setattr(runner_service, "_parse_test_output", fake_parse)

    result = asyncio.run(
        runner_service.run_tests(
            str(clone_dir),
            str(overview),
            runtime_env=runtime_env,
        )
    )

    assert captured_envs
    assert all(env["CUSTOM_REQUIRED_ENV"] == "present" for env in captured_envs)
    assert all(env["JWT_SECRET"] for env in captured_envs)
    assert result["runtime_env"]["missing_required_keys"] == []
    assert result["runtime_env"]["profile"] == "course-a"


def test_run_tests_strict_runtime_env_missing_fails_before_commands(tmp_path):
    from repos_runner.services.repo_service import runner as runner_service

    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    (clone_dir / ".env.example").write_text("CUSTOM_REQUIRED_ENV=\n", encoding="utf-8")
    overview = clone_dir / "REPO_OVERVIEW.md"
    overview.write_text("overview", encoding="utf-8")
    runtime_env = build_runtime_env_context(clone_dir, required_policy="strict")

    with pytest.raises(RuntimeError, match="CUSTOM_REQUIRED_ENV"):
        asyncio.run(
            runner_service.run_tests(
                str(clone_dir),
                str(overview),
                runtime_env=runtime_env,
            )
        )


def test_run_all_builds_runtime_env_profile_and_reports_missing(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    (clone_dir / ".env.example").write_text(
        "CUSTOM_REQUIRED_ENV=\nOPENAI_API_KEY=\n",
        encoding="utf-8",
    )
    profile_dir = tmp_path / "runtime-envs"
    profile_dir.mkdir()
    (profile_dir / "course-a.env").write_text(
        "CUSTOM_REQUIRED_ENV=present\nOPENAI_API_KEY=blocked-openai-marker\n",
        encoding="utf-8",
    )
    report_path = clone_dir / "TEST_REPORT.md"
    report_path.write_text("report body", encoding="utf-8")
    monkeypatch.setenv("REPOS_RUNNER_RUNTIME_ENV_DIR", str(profile_dir))

    async def _fake_clone_repository(_repo_url, _sha, _tag, timeout=300):
        return {"clone_path": str(clone_dir), "repo_name": "repo"}

    async def _fake_explore_repository(_clone_path, _progress_callback, _tag_message, tag=None):
        overview_path = clone_dir / "REPO_OVERVIEW.md"
        overview_path.write_text("overview", encoding="utf-8")
        return str(overview_path)

    async def _fake_run_tests(
        _clone_path,
        _overview_path,
        _progress_callback,
        setup_timeout,
        test_timeout,
        tag_message=None,
        tag=None,
        grading_rubric=None,
        runtime_env=None,
    ):
        return {
            "repo_name": "org/repo",
            "passed": 1,
            "failed": 0,
            "total": 1,
            "score": 100,
            "report_path": str(report_path),
            "runtime_env": runtime_env.as_report(),
        }

    monkeypatch.setattr(runner_route, "clone_repository", _fake_clone_repository)
    monkeypatch.setattr(runner_route, "explore_repository", _fake_explore_repository)
    monkeypatch.setattr(runner_route, "run_tests", _fake_run_tests)

    response = asyncio.run(
        runner_route.run_all_stream(
            RunAllRequest(
                repo_url="https://github.com/org/repo",
                runtime_env_profile="course-a",
            )
        )
    )

    async def _collect_completed():
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for line in text.splitlines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    if event["event"] == "status" and event["data"]["status"] == "completed":
                        return event["data"]
        raise AssertionError("completed status event not found")

    completed = asyncio.run(_collect_completed())

    runtime_env = completed["results"]["runtime_env"]
    assert runtime_env["profile"] == "course-a"
    assert "CUSTOM_REQUIRED_ENV" in runtime_env["supplied_keys"]
    assert "OPENAI_API_KEY" in runtime_env["blocked_secret_keys"]
    assert runtime_env["missing_required_keys"] == ["OPENAI_API_KEY"]
    assert "blocked-openai-marker" not in json.dumps(completed)
