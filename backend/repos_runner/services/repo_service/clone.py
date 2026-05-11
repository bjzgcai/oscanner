"""
Repository cloning logic.
"""

import asyncio
import os
import shutil
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any

import git

from .paths import get_repos_dir, parse_repo_url

_PRESERVED_FILE_PATTERNS = ("TEST_REPORT*.md", "REPO_OVERVIEW*.md")
_PRESERVED_DIR_PATTERNS = ("TEST_ARTIFACTS_*",)


@dataclass
class _PreservedArtifacts:
    files: Dict[str, bytes] = field(default_factory=dict)
    dirs: Dict[str, Path] = field(default_factory=dict)
    temp_dir: Optional[tempfile.TemporaryDirectory] = None

    def cleanup(self) -> None:
        if self.temp_dir is not None:
            self.temp_dir.cleanup()


def _inject_auth_token(repo_url: str) -> str:
    """Inject authentication token into the repo URL if available."""
    try:
        platform, _, _ = parse_repo_url(repo_url)
    except ValueError:
        return repo_url

    parsed = urllib.parse.urlsplit(repo_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return repo_url
    if "@" in parsed.netloc:
        return repo_url

    if platform == "gitee":
        token = os.getenv("GITEE_TOKEN") or os.getenv("GITEE_ENTERPRISE_TOKEN")
    elif platform == "github":
        token = os.getenv("GITHUB_TOKEN")
    else:
        token = None

    if not token:
        return repo_url

    quoted_token = urllib.parse.quote(token, safe="")
    auth_netloc = f"oauth2:{quoted_token}@{parsed.netloc}"
    return urllib.parse.urlunsplit(
        (parsed.scheme, auth_netloc, parsed.path, parsed.query, parsed.fragment)
    )


def _snapshot_preserved_artifacts(repo_dir: Path) -> _PreservedArtifacts:
    """Read existing report artifacts before a fresh clone."""
    artifacts = _PreservedArtifacts()
    if not repo_dir.exists():
        return artifacts

    for pattern in _PRESERVED_FILE_PATTERNS:
        for report_file in repo_dir.glob(pattern):
            if report_file.is_file():
                artifacts.files[report_file.name] = report_file.read_bytes()

    for pattern in _PRESERVED_DIR_PATTERNS:
        for artifact_dir in repo_dir.glob(pattern):
            if not artifact_dir.is_dir():
                continue
            if artifacts.temp_dir is None:
                artifacts.temp_dir = tempfile.TemporaryDirectory(prefix="oscanner_preserve_")
            backup_dir = Path(artifacts.temp_dir.name) / artifact_dir.name
            shutil.copytree(artifact_dir, backup_dir)
            artifacts.dirs[artifact_dir.name] = backup_dir

    return artifacts


def _restore_preserved_artifacts(repo_dir: Path, artifacts: _PreservedArtifacts) -> None:
    """Restore previously snapshotted report artifacts into cloned repo."""
    for dirname, source_dir in artifacts.dirs.items():
        target_dir = repo_dir / dirname
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)

    for filename, content in artifacts.files.items():
        (repo_dir / filename).write_bytes(content)


async def clone_repository(
    repo_url: str,
    sha: Optional[str] = None,
    tag: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Clone a repository (shallow when no SHA/tag, full clone + checkout when SHA or tag given).

    Args:
        repo_url: Repository URL to clone
        sha: Optional commit SHA to checkout (takes priority over tag)
        tag: Optional tag to checkout (used only when sha is not provided)

    Returns:
        Dictionary containing repo metadata
    """
    platform, owner, repo_name = parse_repo_url(repo_url)

    repos_dir = get_repos_dir()
    clone_path = repos_dir / repo_name
    preserved_artifacts = _snapshot_preserved_artifacts(clone_path) if clone_path.exists() else _PreservedArtifacts()

    if clone_path.exists():
        await asyncio.to_thread(shutil.rmtree, clone_path)

    try:
        def _clone_sync():
            auth_url = _inject_auth_token(repo_url)
            if sha:
                repo = git.Repo.clone_from(auth_url, clone_path)
                repo.git.checkout(sha)
                checked_out_sha = repo.head.commit.hexsha
            elif tag:
                repo = git.Repo.clone_from(auth_url, clone_path)
                repo.git.fetch("--tags")
                repo.git.checkout(f"tags/{tag}")
                checked_out_sha = repo.head.commit.hexsha
            else:
                repo = git.Repo.clone_from(
                    auth_url, clone_path, depth=1, single_branch=True
                )
                checked_out_sha = repo.head.commit.hexsha

            default_branch = (
                repo.active_branch.name
                if not repo.head.is_detached
                else "detached"
            )
            if preserved_artifacts.files or preserved_artifacts.dirs:
                _restore_preserved_artifacts(clone_path, preserved_artifacts)

            return {
                "repo_name": repo_name,
                "default_branch": default_branch,
                "latest_commit_id": checked_out_sha,
                "clone_path": str(clone_path),
                "platform": platform,
                "owner": owner,
            }

        return await asyncio.to_thread(_clone_sync)

    except Exception as e:
        raise Exception(f"Failed to clone repository: {str(e)}")
    finally:
        preserved_artifacts.cleanup()
