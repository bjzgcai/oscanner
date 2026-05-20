"""
Path helpers and platform-specific URL/API utilities.
"""

import os
import asyncio
import re
import json
import urllib.request
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Optional, Dict


_SAFE_STORAGE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class RepoUrlParts:
    platform: str
    owner: str
    repo: str
    branch: Optional[str] = None

    @property
    def clone_url(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.repo}.git"

    @property
    def host(self) -> str:
        if self.platform == "github":
            return "github.com"
        if self.platform == "gitee":
            return "gitee.com"
        raise ValueError(f"Unsupported repository platform: {self.platform}")


def _xdg_dir(env_key: str, fallback: Path) -> Path:
    value = os.getenv(env_key)
    if value:
        return Path(value).expanduser()
    return fallback


def get_home_dir() -> Path:
    """
    Base dir for oscanner-related runner state.

    Priority:
    1) OSCANNER_HOME
    2) XDG_DATA_HOME/oscanner
    3) ~/.local/share/oscanner
    """
    if os.getenv("OSCANNER_HOME"):
        return Path(os.environ["OSCANNER_HOME"]).expanduser()
    data_home = _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")
    return data_home / "oscanner"


def get_repos_dir() -> Path:
    """Get the directory for storing cloned repositories"""
    base_dir = get_home_dir() / "repos"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def _safe_storage_segment(value: str, *, fallback: str = "default") -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return segment or fallback


def repo_ref_segment(
    sha: Optional[str] = None,
    tag: Optional[str] = None,
    branch: Optional[str] = None,
) -> str:
    if sha:
        return f"sha-{_safe_storage_segment(sha)}"
    if tag:
        return f"tag-{_safe_storage_segment(tag)}"
    if branch:
        return f"branch-{_safe_storage_segment(branch)}"
    return "default"


def repo_storage_key(
    platform: str,
    owner: str,
    repo: str,
    sha: Optional[str] = None,
    tag: Optional[str] = None,
    branch: Optional[str] = None,
) -> str:
    """Return the opaque runner key for a stored repository checkout."""
    return "/".join(
        [
            _safe_storage_segment(platform),
            _safe_storage_segment(owner),
            _safe_storage_segment(repo),
            repo_ref_segment(sha=sha, tag=tag, branch=branch),
        ]
    )


def get_clone_source_dir(
    repos_dir: Path,
    *,
    platform: str,
    owner: str,
    repo: str,
    sha: Optional[str] = None,
    tag: Optional[str] = None,
    branch: Optional[str] = None,
) -> Path:
    """Return repos/{platform}/{owner}/{repo}/{ref}/source."""
    return repos_dir / repo_storage_key(platform, owner, repo, sha=sha, tag=tag, branch=branch) / "source"


def get_clone_source_dir_for_url(
    repo_url: str,
    *,
    sha: Optional[str] = None,
    tag: Optional[str] = None,
    branch: Optional[str] = None,
    repos_dir: Optional[Path] = None,
) -> Path:
    parsed = parse_repo_url_with_ref(repo_url)
    effective_branch = branch or (None if sha or tag else parsed.branch)
    return get_clone_source_dir(
        repos_dir or get_repos_dir(),
        platform=parsed.platform,
        owner=parsed.owner,
        repo=parsed.repo,
        sha=sha,
        tag=tag,
        branch=effective_branch,
    )


def source_dir_from_repo_key(repo_key: str, *, repos_dir: Optional[Path] = None) -> Path:
    """Resolve a stored runner repo key to its source directory."""
    raw_key = str(repo_key or "").strip().replace("\\", "/")
    parts = [part for part in raw_key.split("/") if part]
    if len(parts) == 1 and _SAFE_STORAGE_SEGMENT_RE.fullmatch(parts[0]):
        return (repos_dir or get_repos_dir()) / parts[0]
    if len(parts) != 4 or any(not _SAFE_STORAGE_SEGMENT_RE.fullmatch(part) for part in parts):
        raise ValueError("Invalid repository storage key")
    return (repos_dir or get_repos_dir()).joinpath(*parts) / "source"


def repo_key_from_source_dir(source_dir: Path, *, repos_dir: Optional[Path] = None) -> str:
    """Return the stored repo key for a source dir, falling back to the dir name."""
    root = (repos_dir or get_repos_dir()).resolve()
    source = Path(source_dir).resolve()
    try:
        parts = source.relative_to(root).parts
    except ValueError:
        return source.name
    if len(parts) == 5 and parts[-1] == "source":
        return "/".join(parts[:4])
    return source.name


def workspace_dir_from_repo_key(repo_key: str, *, repos_dir: Optional[Path] = None) -> Path:
    """Resolve a stored runner repo key to its checkout workspace directory."""
    raw_key = str(repo_key or "").strip().replace("\\", "/")
    parts = [part for part in raw_key.split("/") if part]
    if len(parts) == 1 and _SAFE_STORAGE_SEGMENT_RE.fullmatch(parts[0]):
        return (repos_dir or get_repos_dir()) / parts[0]
    if len(parts) != 4 or any(not _SAFE_STORAGE_SEGMENT_RE.fullmatch(part) for part in parts):
        raise ValueError("Invalid repository storage key")
    return (repos_dir or get_repos_dir()).joinpath(*parts)


_ALLOWED_REPO_HOSTS = {
    "github.com": "github",
    "www.github.com": "github",
    "gitee.com": "gitee",
    "www.gitee.com": "gitee",
}

_SSH_REPO_URL_RE = re.compile(
    r"^git@(?P<host>github\.com|gitee\.com):(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?$",
    re.IGNORECASE,
)

_REPO_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _normalize_owner_repo(owner: str, repo: str) -> Tuple[str, str]:
    owner = owner.strip()
    repo = repo.strip()
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not owner or not repo:
        raise ValueError("Repository URL must include owner and repository name")
    if owner in {".", ".."} or repo in {".", ".."}:
        raise ValueError("Repository URL contains invalid path segment")
    if not _REPO_SEGMENT_RE.fullmatch(owner) or not _REPO_SEGMENT_RE.fullmatch(repo):
        raise ValueError("Repository URL contains invalid owner/repository characters")

    return owner, repo


def _parse_repo_url_parts(repo_url: str) -> RepoUrlParts:
    """
    Parse repository URL to extract platform, owner, and repo name.

    Returns:
        Tuple of (platform, owner, repo_name)
    """
    candidate = (repo_url or "").strip()
    if not candidate:
        raise ValueError("Repository URL is required")

    ssh_match = _SSH_REPO_URL_RE.match(candidate)
    if ssh_match:
        host = ssh_match.group("host").lower()
        platform = _ALLOWED_REPO_HOSTS.get(host)
        if not platform:
            raise ValueError(f"Unsupported repository URL: {repo_url}")
        owner, repo_name = _normalize_owner_repo(
            ssh_match.group("owner"),
            ssh_match.group("repo"),
        )
        return RepoUrlParts(platform=platform, owner=owner, repo=repo_name)

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urllib.parse.urlparse(candidate)
    host = (parsed.hostname or "").lower()
    platform = _ALLOWED_REPO_HOSTS.get(host)
    if not platform:
        raise ValueError(f"Unsupported repository URL: {repo_url}")

    path_parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise ValueError("Repository URL must include owner and repository name")
    if len(path_parts) > 2 and path_parts[2] != "tree":
        raise ValueError("Repository URL must include owner and repository name")

    owner, repo_name = _normalize_owner_repo(path_parts[0], path_parts[1])
    branch = None
    if len(path_parts) > 2:
        if len(path_parts) == 3:
            raise ValueError("Repository tree URL must include a branch name")
        branch = "/".join(path_parts[3:]).strip("/")
        if not branch:
            raise ValueError("Repository tree URL must include a branch name")

    return RepoUrlParts(platform=platform, owner=owner, repo=repo_name, branch=branch)


def parse_repo_url_with_ref(repo_url: str) -> RepoUrlParts:
    """Parse a GitHub/Gitee repo URL, including optional /tree/<branch> refs."""
    return _parse_repo_url_parts(repo_url)


def parse_repo_url(repo_url: str) -> Tuple[str, str, str]:
    """
    Parse repository URL to extract platform, owner, and repo name.

    Returns:
        Tuple of (platform, owner, repo_name)
    """
    parsed = _parse_repo_url_parts(repo_url)
    return parsed.platform, parsed.owner, parsed.repo


async def fetch_gitee_tag_message(repo_url: str, tag: str) -> Optional[str]:
    """
    Fetch the annotation message for a specific tag from the Gitee API.

    Returns the tag message string, or None if not found / not a Gitee repo.
    """
    try:
        platform, owner, repo_name = parse_repo_url(repo_url)
    except ValueError:
        return None

    if platform != "gitee":
        return None
    try:
        params = urllib.parse.urlencode({"per_page": 100, "page": 1})
        url = f"https://gitee.com/api/v5/repos/{owner}/{repo_name}/tags?{params}"

        headers: Dict[str, str] = {"Accept": "application/json"}
        gitee_token = os.getenv("GITEE_TOKEN") or os.getenv("GITEE_ENTERPRISE_TOKEN")
        if gitee_token:
            headers["Authorization"] = f"token {gitee_token}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            tags_data = json.loads(resp.read().decode())

        for t in tags_data:
            if t.get("name") == tag:
                return t.get("message") or ""
    except Exception:
        pass
    return None
