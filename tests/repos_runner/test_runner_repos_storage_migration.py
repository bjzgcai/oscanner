"""Tests for migrating legacy flat repos_runner checkouts."""

import subprocess
from pathlib import Path

from scripts.migrate_runner_repos_storage import migrate_repos_dir


def _init_repo(path: Path, remote_url: str) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        cwd=path,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    (path / "TEST_REPORT.md").write_text("report", encoding="utf-8")


def test_migrates_legacy_flat_git_checkout_to_namespaced_source(tmp_path):
    repos_dir = tmp_path / "repos"
    legacy_dir = repos_dir / "demo"
    _init_repo(legacy_dir, "https://github.com/owner/demo.git")

    results = migrate_repos_dir(repos_dir, dry_run=False)

    destination = repos_dir / "github" / "owner" / "demo" / "default" / "source"
    assert results == [
        {
            "status": "moved",
            "source": str(legacy_dir),
            "destination": str(destination),
        }
    ]
    assert not legacy_dir.exists()
    assert (destination / ".git").is_dir()
    assert (destination / "TEST_REPORT.md").read_text(encoding="utf-8") == "report"


def test_skips_namespaced_and_unparseable_legacy_dirs(tmp_path):
    repos_dir = tmp_path / "repos"
    namespaced_source = repos_dir / "github" / "owner" / "demo" / "default" / "source"
    _init_repo(namespaced_source, "https://github.com/owner/demo.git")
    unsupported = repos_dir / "unsupported"
    _init_repo(unsupported, "https://example.com/owner/unsupported.git")

    results = migrate_repos_dir(repos_dir, dry_run=False)

    assert results == [
        {
            "status": "skipped",
            "source": str(unsupported),
            "reason": "Unsupported repository URL: https://example.com/owner/unsupported.git",
        }
    ]
    assert namespaced_source.exists()
    assert unsupported.exists()


def test_skips_when_destination_exists(tmp_path):
    repos_dir = tmp_path / "repos"
    legacy_dir = repos_dir / "demo"
    destination = repos_dir / "github" / "owner" / "demo" / "default" / "source"
    _init_repo(legacy_dir, "https://github.com/owner/demo.git")
    destination.mkdir(parents=True)

    results = migrate_repos_dir(repos_dir, dry_run=False)

    assert results == [
        {
            "status": "skipped",
            "source": str(legacy_dir),
            "destination": str(destination),
            "reason": "destination exists",
        }
    ]
    assert legacy_dir.exists()
