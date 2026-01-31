"""Repository URL parsing utilities."""

import re
from typing import Optional, Dict, Tuple


def parse_github_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parse GitHub URL to extract owner and repo
    Supports formats:
    - https://github.com/owner/repo
    - http://github.com/owner/repo
    - github.com/owner/repo
    - git@github.com:owner/repo.git
    """
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
    url = (url or "").strip()
    if not url:
        return None

    parsed = parse_github_url(url)
    if parsed:
        return ("github", parsed["owner"], parsed["repo"])

    patterns = [
        r'^https?://(?:www\.)?gitee\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'^gitee\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
    ]
    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            owner, repo = match.groups()
            repo = repo.replace('.git', '')
            return ("gitee", owner, repo)

    return None
