"""
Repository cloning logic.
"""

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any

from .paths import get_clone_source_dir, get_repos_dir, parse_repo_url, repo_storage_key

_PRESERVED_FILE_PATTERNS = ("TEST_REPORT*.md", "REPO_OVERVIEW*.md")
_PRESERVED_DIR_PATTERNS = ("TEST_ARTIFACTS_*",)
_AUTH_URL_RE = re.compile(r"(https?://)[^/\s'\"@]+@")
_TRANSIENT_GIT_CLONE_ERRORS = (
    "GnuTLS recv error",
    "TLS connection was non-properly terminated",
    "curl 56",
    "early EOF",
    "remote end hung up unexpectedly",
    "Connection reset by peer",
    "Operation timed out",
    "Failed to connect",
    "The requested URL returned error: 502",
    "The requested URL returned error: 503",
    "The requested URL returned error: 504",
)
_GIT_CLONE_ATTEMPTS = 3


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


def _masked_command(command: list[str]) -> list[str]:
    masked = []
    for value in command:
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme in ("http", "https") and "@" in parsed.netloc:
            netloc = parsed.netloc.split("@", 1)[1]
            masked.append(
                urllib.parse.urlunsplit(
                    (parsed.scheme, f"***:***@{netloc}", parsed.path, parsed.query, parsed.fragment)
                )
            )
        else:
            masked.append(value)
    return masked


def _masked_git_output(text: str) -> str:
    return _AUTH_URL_RE.sub(r"\1***:***@", text or "")


def _run_git(command: list[str], *, timeout: int, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        action = " ".join(_masked_command(command[:3]))
        raise TimeoutError(f"{action} timed out after {timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        stderr = _masked_git_output(exc.stderr or exc.stdout or "").strip()
        command_text = " ".join(_masked_command(command))
        detail = f": {stderr}" if stderr else ""
        raise RuntimeError(f"{command_text} failed{detail}") from exc


def _git_output(command: list[str], *, timeout: int, cwd: Path) -> str:
    return _run_git(command, timeout=timeout, cwd=cwd).stdout.strip()


def _is_transient_git_clone_error(error: Exception) -> bool:
    text = str(error)
    return any(pattern in text for pattern in _TRANSIENT_GIT_CLONE_ERRORS)


def _run_git_clone_with_retries(command: list[str], *, timeout: int, clone_path: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(1, _GIT_CLONE_ATTEMPTS + 1):
        try:
            _run_git(command, timeout=timeout)
            return
        except RuntimeError as exc:
            last_error = exc
            if attempt >= _GIT_CLONE_ATTEMPTS or not _is_transient_git_clone_error(exc):
                raise
            if clone_path.exists():
                shutil.rmtree(clone_path)

    if last_error is not None:
        raise last_error


async def clone_repository(
    repo_url: str,
    sha: Optional[str] = None,
    tag: Optional[str] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """
    Clone a repository (shallow when no SHA/tag, full clone + checkout when SHA or tag given).

    Args:
        repo_url: Repository URL to clone
        sha: Optional commit SHA to checkout (takes priority over tag)
        tag: Optional tag to checkout (used only when sha is not provided)
        timeout: Seconds allowed per git operation

    Returns:
        Dictionary containing repo metadata
    """
    platform, owner, repo_name = parse_repo_url(repo_url)

    repos_dir = get_repos_dir()
    clone_path = get_clone_source_dir(
        repos_dir,
        platform=platform,
        owner=owner,
        repo=repo_name,
        sha=sha,
        tag=tag,
    )
    storage_key = repo_storage_key(platform, owner, repo_name, sha=sha, tag=tag)
    preserved_artifacts = _snapshot_preserved_artifacts(clone_path) if clone_path.exists() else _PreservedArtifacts()

    if clone_path.exists():
        await asyncio.to_thread(shutil.rmtree, clone_path)

    try:
        def _clone_sync():
            auth_url = _inject_auth_token(repo_url)
            if sha:
                _run_git_clone_with_retries(
                    ["git", "clone", auth_url, str(clone_path)],
                    timeout=timeout,
                    clone_path=clone_path,
                )
                _run_git(["git", "checkout", sha], timeout=timeout, cwd=clone_path)
            elif tag:
                _run_git_clone_with_retries(
                    ["git", "clone", auth_url, str(clone_path)],
                    timeout=timeout,
                    clone_path=clone_path,
                )
                _run_git(["git", "fetch", "--tags"], timeout=timeout, cwd=clone_path)
                _run_git(["git", "checkout", f"tags/{tag}"], timeout=timeout, cwd=clone_path)
            else:
                _run_git_clone_with_retries(
                    ["git", "clone", "--depth", "1", "--single-branch", auth_url, str(clone_path)],
                    timeout=timeout,
                    clone_path=clone_path,
                )

            checked_out_sha = _git_output(
                ["git", "rev-parse", "HEAD"], timeout=timeout, cwd=clone_path
            )
            default_branch = _git_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                timeout=timeout,
                cwd=clone_path,
            )
            if default_branch == "HEAD":
                default_branch = "detached"
            if preserved_artifacts.files or preserved_artifacts.dirs:
                _restore_preserved_artifacts(clone_path, preserved_artifacts)

            return {
                "repo_name": storage_key,
                "display_name": repo_name,
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
