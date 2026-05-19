"""Tests for preserving repo artifacts during fresh clone."""

import asyncio
import subprocess
from pathlib import Path

from repos_runner.services.repo_service import clone as clone_module
from repos_runner.services.repo_service.clone import clone_repository


class _FakeCompletedProcess:
    stdout = ""
    stderr = ""
    returncode = 0


def _fake_run_git(command, *, timeout, cwd=None):
    clone_path = Path(command[-1])
    clone_path.mkdir(parents=True, exist_ok=True)
    (clone_path / "README.md").write_text("cloned")
    return _FakeCompletedProcess()


def _fake_git_output(command, *, timeout, cwd):
    if command == ["git", "rev-parse", "HEAD"]:
        return "abc123"
    if command == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
        return "main"
    raise AssertionError(f"unexpected git output command: {command}")


def test_clone_repository_preserves_existing_reports_and_overviews(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    clone_path = repos_dir / "github" / "owner" / "demo-repo" / "default" / "source"
    clone_path.mkdir(parents=True)

    report_default = clone_path / "TEST_REPORT.md"
    report_tagged = clone_path / "TEST_REPORT_Coursework_Submit_5.2.md"
    overview_default = clone_path / "REPO_OVERVIEW.md"
    overview_tagged = clone_path / "REPO_OVERVIEW_Coursework_Submit_5.2.md"
    non_report = clone_path / "notes.txt"

    report_default.write_text("old default report")
    report_tagged.write_text("old tagged report")
    overview_default.write_text("old default overview")
    overview_tagged.write_text("old tagged overview")
    non_report.write_text("should not be preserved")

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.parse_repo_url",
        lambda _repo_url: ("github", "owner", "demo-repo"),
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda repo_url: repo_url,
    )
    monkeypatch.setattr(clone_module, "_run_git", _fake_run_git)
    monkeypatch.setattr(clone_module, "_git_output", _fake_git_output)

    result = asyncio.run(clone_repository("https://github.com/owner/demo-repo"))

    assert result["repo_name"] == "github/owner/demo-repo/default"
    assert result["display_name"] == "demo-repo"
    assert report_default.read_text() == "old default report"
    assert report_tagged.read_text() == "old tagged report"
    assert overview_default.read_text() == "old default overview"
    assert overview_tagged.read_text() == "old tagged overview"
    assert (clone_path / "README.md").exists()
    assert not non_report.exists()


def test_clone_repository_preserves_report_artifact_directories(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    clone_path = repos_dir / "github" / "owner" / "demo-repo" / "default" / "source"
    artifact_dir = clone_path / "TEST_ARTIFACTS_Coursework_Submit_5.2"
    screenshot = artifact_dir / "runtime-evidence" / "screenshots" / "docs.png"
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"png")

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.parse_repo_url",
        lambda _repo_url: ("github", "owner", "demo-repo"),
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda repo_url: repo_url,
    )
    monkeypatch.setattr(clone_module, "_run_git", _fake_run_git)
    monkeypatch.setattr(clone_module, "_git_output", _fake_git_output)

    result = asyncio.run(clone_repository("https://github.com/owner/demo-repo"))

    assert result["repo_name"] == "github/owner/demo-repo/default"
    assert result["display_name"] == "demo-repo"
    assert screenshot.read_bytes() == b"png"


def test_clone_repository_times_out_stuck_clone(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.parse_repo_url",
        lambda _repo_url: ("github", "owner", "demo-repo"),
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda repo_url: repo_url,
    )

    def _timeout_run(cmd, **kwargs):
        if cmd[:2] == ["git", "clone"]:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"])
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(clone_module, "subprocess", subprocess, raising=False)
    monkeypatch.setattr(clone_module.subprocess, "run", _timeout_run)

    try:
        asyncio.run(clone_repository("https://github.com/owner/demo-repo", timeout=7))
    except Exception as error:
        message = str(error)
    else:
        raise AssertionError("clone_repository should fail when git clone times out")

    assert "timed out after 7s" in message


def test_clone_repository_masks_auth_url_in_git_errors(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.parse_repo_url",
        lambda _repo_url: ("github", "owner", "demo-repo"),
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda _repo_url: "https://oauth2:super-secret-token@github.com/owner/demo-repo.git",
    )

    def _failed_run(cmd, **_kwargs):
        raise subprocess.CalledProcessError(
            returncode=128,
            cmd=cmd,
            stderr=(
                "fatal: unable to access "
                "'https://oauth2:super-secret-token@github.com/owner/demo-repo.git/'"
            ),
        )

    monkeypatch.setattr(clone_module.subprocess, "run", _failed_run)

    try:
        asyncio.run(clone_repository("https://github.com/owner/demo-repo"))
    except Exception as error:
        message = str(error)
    else:
        raise AssertionError("clone_repository should fail when git clone fails")

    assert "super-secret-token" not in message
    assert "https://***:***@github.com/owner/demo-repo.git" in message
