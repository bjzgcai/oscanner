"""Tests for preserving repo artifacts during fresh clone."""

import asyncio
from pathlib import Path

from repos_runner.services.repo_service.clone import clone_repository


class _FakeCommit:
    hexsha = "abc123"


class _FakeHead:
    commit = _FakeCommit()
    is_detached = False


class _FakeBranch:
    name = "main"


class _FakeRepo:
    head = _FakeHead()
    active_branch = _FakeBranch()


class _FakeGit:
    def checkout(self, *_args, **_kwargs):
        return None


def _fake_clone_from(_url: str, clone_path: Path, **_kwargs):
    clone_path.mkdir(parents=True, exist_ok=True)
    (clone_path / "README.md").write_text("cloned")
    repo = _FakeRepo()
    repo.git = _FakeGit()
    return repo


def test_clone_repository_preserves_existing_reports_and_overviews(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    clone_path = repos_dir / "demo-repo"
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
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.git.Repo.clone_from",
        _fake_clone_from,
    )

    result = asyncio.run(clone_repository("https://github.com/owner/demo-repo"))

    assert result["repo_name"] == "demo-repo"
    assert report_default.read_text() == "old default report"
    assert report_tagged.read_text() == "old tagged report"
    assert overview_default.read_text() == "old default overview"
    assert overview_tagged.read_text() == "old tagged overview"
    assert (clone_path / "README.md").exists()
    assert not non_report.exists()
