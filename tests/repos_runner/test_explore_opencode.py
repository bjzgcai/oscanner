"""Tests for opencode-based repository exploration."""

import asyncio

from repos_runner.services.repo_service import explore as explore_module


class _FakeProcess:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0):
        self._stdout = stdout.encode("utf-8")
        self._stderr = stderr.encode("utf-8")
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, self._stderr


def test_explore_repository_uses_opencode_cli(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    (clone_dir / "package.json").write_text('{"scripts":{"test":"vitest run"}}')
    captured = {}
    progress_messages = []

    async def _fake_create_subprocess_exec(*cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        return _FakeProcess(
            "# repo\n\n"
            "## Tag Message\ncourse requirements\n\n"
            "## Project Type\nNode app.\n\n"
            "## Test Framework\nVitest\n\n"
            "## Setup Commands\n```\nnpm install\n```\n\n"
            "## Test Commands\n```\nnpm test\n```\n"
        )

    async def _progress(message):
        progress_messages.append(message)

    monkeypatch.setenv("OPEN_ROUTER_KEY", "sk-or-v1-test")
    monkeypatch.delenv("REPOS_RUNNER_OPENCODE_MODEL", raising=False)
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setattr(explore_module.shutil, "which", lambda name: "/usr/bin/opencode")
    monkeypatch.setattr(
        explore_module.asyncio,
        "create_subprocess_exec",
        _fake_create_subprocess_exec,
    )

    overview_path = asyncio.run(
        explore_module.explore_repository(
            str(clone_dir),
            _progress,
            tag_message="course requirements",
            tag="class/01",
        )
    )

    overview_file = clone_dir / "REPO_OVERVIEW_class_01.md"
    assert overview_path == str(overview_file)
    assert overview_file.read_text(encoding="utf-8").startswith("# repo")
    assert captured["cmd"][:4] == ("opencode", "run", "--agent", "plan")
    model_index = captured["cmd"].index("--model")
    assert captured["cmd"][model_index + 1] == "openrouter/deepseek/deepseek-v4-pro"
    assert "--dir" in captured["cmd"]
    assert str(clone_dir) in captured["cmd"]
    assert captured["cwd"] == str(clone_dir)
    assert any("opencode" in message.lower() for message in progress_messages)
    assert not any("claude-code-sdk" in message for message in progress_messages)


def test_explore_repository_passes_openrouter_key_to_opencode(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    captured = {}

    async def _fake_create_subprocess_exec(*cmd, **kwargs):
        captured["env"] = kwargs.get("env")
        return _FakeProcess("# repo\n\n## Test Commands\n```\npytest\n```\n")

    monkeypatch.setenv("OPEN_ROUTER_KEY", "sk-or-v1-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(explore_module.shutil, "which", lambda name: "/usr/bin/opencode")
    monkeypatch.setattr(
        explore_module.asyncio,
        "create_subprocess_exec",
        _fake_create_subprocess_exec,
    )

    asyncio.run(explore_module.explore_repository(str(clone_dir)))

    assert captured["env"]["OPEN_ROUTER_KEY"] == "sk-or-v1-test"
    assert captured["env"]["OPENROUTER_API_KEY"] == "sk-or-v1-test"


def test_opencode_env_uses_project_openrouter_key_fallback(monkeypatch, tmp_path):
    fallback_env = tmp_path / ".env"
    fallback_env.write_text("OPEN_ROUTER_KEY=sk-or-v1-fallback\n", encoding="utf-8")

    monkeypatch.setenv("OPEN_ROUTER_KEY", "")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(explore_module, "_project_env_fallback_paths", lambda: [fallback_env])

    env = explore_module._build_opencode_env()

    assert env["OPEN_ROUTER_KEY"] == "sk-or-v1-fallback"
    assert env["OPENROUTER_API_KEY"] == "sk-or-v1-fallback"


def test_explore_repository_falls_back_when_openrouter_key_empty(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    progress_messages = []

    async def _fake_create_subprocess_exec(*cmd, **kwargs):
        raise AssertionError("opencode should not start without an OpenRouter key")

    async def _fake_messages_api(clone_path, progress_callback, tag_message=None, tag=None):
        overview = clone_dir / "REPO_OVERVIEW.md"
        overview.write_text("# fallback", encoding="utf-8")
        return str(overview)

    async def _progress(message):
        progress_messages.append(message)

    monkeypatch.setenv("OPEN_ROUTER_KEY", "")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("REPOS_RUNNER_OPENCODE_MODEL", raising=False)
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    monkeypatch.setattr(explore_module, "_project_env_fallback_paths", lambda: [])
    monkeypatch.setattr(explore_module.shutil, "which", lambda name: "/usr/bin/opencode")
    monkeypatch.setattr(
        explore_module.asyncio,
        "create_subprocess_exec",
        _fake_create_subprocess_exec,
    )
    monkeypatch.setattr(explore_module, "_explore_via_messages_api", _fake_messages_api)

    overview_path = asyncio.run(explore_module.explore_repository(str(clone_dir), _progress))

    assert overview_path == str(clone_dir / "REPO_OVERVIEW.md")
    assert any("OPEN_ROUTER_KEY is empty" in message for message in progress_messages)


def test_explore_repository_falls_back_when_opencode_missing(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    progress_messages = []

    async def _fake_messages_api(clone_path, progress_callback, tag_message=None, tag=None):
        assert clone_path == str(clone_dir)
        assert tag_message == "requirements"
        assert tag == "v1"
        overview = clone_dir / "REPO_OVERVIEW_v1.md"
        overview.write_text("# fallback", encoding="utf-8")
        return str(overview)

    async def _progress(message):
        progress_messages.append(message)

    monkeypatch.setattr(explore_module.shutil, "which", lambda name: None)
    monkeypatch.setattr(explore_module, "_explore_via_messages_api", _fake_messages_api)

    overview_path = asyncio.run(
        explore_module.explore_repository(
            str(clone_dir),
            _progress,
            tag_message="requirements",
            tag="v1",
        )
    )

    assert overview_path == str(clone_dir / "REPO_OVERVIEW_v1.md")
    assert any("opencode CLI not available" in message for message in progress_messages)
    assert not any("claude-code-sdk" in message for message in progress_messages)


def test_repos_runner_requirements_do_not_include_claude_code_sdk():
    requirements = (
        explore_module.Path(__file__).parents[2]
        / "backend"
        / "repos_runner"
        / "requirements.txt"
    ).read_text(encoding="utf-8")

    assert "claude-code-sdk" not in requirements
