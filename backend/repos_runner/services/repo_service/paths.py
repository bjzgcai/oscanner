"""
Path helpers and platform-specific URL/API utilities.
"""

import os
import asyncio
import json
import urllib.request
import urllib.parse
import re
from pathlib import Path
from typing import Tuple, Optional, Dict


def get_repos_dir() -> Path:
    """Get the directory for storing cloned repositories"""
    base_dir = Path.home() / ".local" / "share" / "oscanner" / "repos"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


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


def parse_repo_url(repo_url: str) -> Tuple[str, str, str]:
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
        return platform, owner, repo_name

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urllib.parse.urlparse(candidate)
    host = (parsed.hostname or "").lower()
    platform = _ALLOWED_REPO_HOSTS.get(host)
    if not platform:
        raise ValueError(f"Unsupported repository URL: {repo_url}")

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) != 2:
        raise ValueError("Repository URL must include owner and repository name")

    owner, repo_name = _normalize_owner_repo(path_parts[0], path_parts[1])
    return platform, owner, repo_name


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
