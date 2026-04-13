"""
Repository cloning logic.
"""

import asyncio
import os
import shutil
import urllib.parse
from typing import Optional, Dict, Any

import git

from .paths import get_repos_dir, parse_repo_url


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
