"""Repository URL parsing utilities."""

import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional, Dict, Tuple


@dataclass(frozen=True)
class RepoUrlParts:
    platform: str
    owner: str
    repo: str
    branch: Optional[str] = None

    @property
    def clone_url(self) -> str:
        host = "github.com" if self.platform == "github" else "gitee.com"
        return f"https://{host}/{self.owner}/{self.repo}.git"


_ALLOWED_REPO_HOSTS = {
    "github.com": "github",
    "www.github.com": "github",
    "gitee.com": "gitee",
    "www.gitee.com": "gitee",
}

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


def parse_repo_url_with_ref(url: str) -> Optional[RepoUrlParts]:
    """Parse a GitHub/Gitee repository URL, including optional /tree/<branch> refs."""
    candidate = (url or "").strip()
    if not candidate:
        return None

    ssh_match = re.match(
        r"^git@(?P<host>github\.com|gitee\.com):(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?$",
        candidate,
        re.IGNORECASE,
    )
    if ssh_match:
        platform = _ALLOWED_REPO_HOSTS.get(ssh_match.group("host").lower())
        if not platform:
            return None
        try:
            owner, repo = _normalize_owner_repo(ssh_match.group("owner"), ssh_match.group("repo"))
        except ValueError:
            return None
        return RepoUrlParts(platform=platform, owner=owner, repo=repo)

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urllib.parse.urlparse(candidate)
    platform = _ALLOWED_REPO_HOSTS.get((parsed.hostname or "").lower())
    if not platform:
        return None

    path_parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        return None
    if len(path_parts) > 2 and path_parts[2] != "tree":
        return None

    try:
        owner, repo = _normalize_owner_repo(path_parts[0], path_parts[1])
    except ValueError:
        return None

    branch = None
    if len(path_parts) > 2:
        if len(path_parts) == 3:
            return None
        branch = "/".join(path_parts[3:]).strip("/") or None
        if not branch:
            return None

    return RepoUrlParts(platform=platform, owner=owner, repo=repo, branch=branch)


def parse_github_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parse GitHub URL to extract owner and repo
    Supports formats:
    - https://github.com/owner/repo
    - http://github.com/owner/repo
    - github.com/owner/repo
    - git@github.com:owner/repo.git
    """
    parsed = parse_repo_url_with_ref(url)
    if parsed and parsed.platform == "github":
        return {"owner": parsed.owner, "repo": parsed.repo}

    url = url.strip()

    # Try different patterns
    patterns = [
        r'^https?://(?:www\.)?github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'^github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'^git@github\.com:([^/]+)/([^/\s]+?)(?:\.git)?$',
    ]

    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            owner, repo = match.groups()
            # Remove .git suffix if present
            repo = repo.replace('.git', '')
            return {"owner": owner, "repo": repo}

    return None


def parse_repo_url(url: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse repository URL and return (platform, owner, repo).

    Supports:
    - GitHub: https://github.com/owner/repo, github.com/owner/repo, git@github.com:owner/repo(.git)
    - Gitee:  https://gitee.com/owner/repo(.git)
    """
    parsed = parse_repo_url_with_ref(url)
    if not parsed:
        return None
    return (parsed.platform, parsed.owner, parsed.repo)
