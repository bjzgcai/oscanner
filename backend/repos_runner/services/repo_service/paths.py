"""
Path helpers and platform-specific URL/API utilities.
"""

import os
import asyncio
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Tuple, Optional, Dict


def get_repos_dir() -> Path:
    """Get the directory for storing cloned repositories"""
    base_dir = Path.home() / ".local" / "share" / "oscanner" / "repos"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def parse_repo_url(repo_url: str) -> Tuple[str, str, str]:
    """
    Parse repository URL to extract platform, owner, and repo name.

    Returns:
        Tuple of (platform, owner, repo_name)
    """
    repo_url = repo_url.rstrip("/").replace(".git", "")

    if "github.com" in repo_url:
        parts = repo_url.split("github.com/")[-1].split("/")
        return "github", parts[0], parts[1]
    elif "gitee.com" in repo_url:
        parts = repo_url.split("gitee.com/")[-1].split("/")
        return "gitee", parts[0], parts[1]
    else:
        raise ValueError(f"Unsupported repository URL: {repo_url}")


async def fetch_gitee_tag_message(repo_url: str, tag: str) -> Optional[str]:
    """
    Fetch the annotation message for a specific tag from the Gitee API.

    Returns the tag message string, or None if not found / not a Gitee repo.
    """
    if "gitee.com" not in repo_url:
        return None
    try:
        _, owner, repo_name = parse_repo_url(repo_url)
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
