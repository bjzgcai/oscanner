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
    assert "--dir" in captured["cmd"]
    assert str(clone_dir) in captured["cmd"]
    assert captured["cwd"] == str(clone_dir)
    assert any("opencode" in message.lower() for message in progress_messages)
    assert not any("claude-code-sdk" in message for message in progress_messages)


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
