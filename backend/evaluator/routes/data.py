"""Data extraction and author discovery routes."""

import json
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path

from evaluator.paths import get_platform_data_dir
from evaluator.services import (
    extract_github_data,
    extract_gitee_data,
    fetch_gitee_commits,
    fetch_github_commits,
)
from evaluator.utils import get_author_from_commit

router = APIRouter()


def _extract_platform_data(platform: str, owner: str, repo: str) -> bool:
    """Extract repository data from the given platform."""
    if platform == "gitee":
        print(f"Extracting latest data from Gitee for {owner}/{repo}...")
        return extract_gitee_data(owner, repo)
    print(f"Extracting latest data from GitHub for {owner}/{repo}...")
    return extract_github_data(owner, repo)


def _get_latest_local_sha(data_dir: Path) -> str:
    """Read newest cached commit SHA from commits_index.json."""
    index_path = data_dir / "commits_index.json"
    if not index_path.exists():
        return ""

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
        if isinstance(index_data, list) and index_data and isinstance(index_data[0], dict):
            return (index_data[0].get("sha") or index_data[0].get("hash") or "").strip()
    except Exception as e:
        print(f"⚠ Failed to read local commits_index.json at {index_path}: {e}")

    return ""


def _get_latest_remote_sha(platform: str, owner: str, repo: str) -> str:
    """Read newest remote commit SHA with a lightweight API call."""
    try:
        if platform == "gitee":
            commits = fetch_gitee_commits(owner, repo, limit=1)
        else:
            commits = fetch_github_commits(owner, repo, limit=1)
        if isinstance(commits, list) and commits and isinstance(commits[0], dict):
            return (commits[0].get("sha") or commits[0].get("hash") or "").strip()
    except Exception as e:
        print(f"⚠ Failed to fetch latest remote SHA for {platform}/{owner}/{repo}: {e}")
    return ""


@router.get("/api/gitee/commits/{owner}/{repo}")
async def get_gitee_commits(
    owner: str,
    repo: str,
    limit: int = Query(500, ge=1, le=1000),
    use_cache: bool = Query(True),
    is_enterprise: bool = Query(False)
):
    """Fetch commits for a Gitee repository"""
    # Fetch from Gitee API
    commits = fetch_gitee_commits(owner, repo, limit, is_enterprise)

    return {
        "success": True,
        "data": commits,
        "cached": False
    }


@router.get("/api/authors/{owner}/{repo}")
async def get_authors(owner: str, repo: str, platform: str = Query("github"), use_cache: bool = Query(True)):
    """
    Get list of authors from commit data

    Flow:
    1. Check if local data exists in platform-specific directory
    2. If no local data, extract it from GitHub/Gitee
    3. Load ALL authors from commits (always scans all commits)
    4. Return complete authors list
    """
    try:
        plat = (platform or "github").strip().lower()
        data_dir = get_platform_data_dir(plat, owner, repo)
        commits_dir = data_dir / "commits"
        has_local_data = commits_dir.exists() and any(commits_dir.glob("*.json"))
        used_cached_data = has_local_data

        # Step 1 & 2: Ensure data exists and refresh when requested or stale
        should_refresh = False
        if not has_local_data:
            should_refresh = True
            print(f"No local commit data found for {plat}/{owner}/{repo}; will fetch from remote")
        elif not use_cache:
            should_refresh = True
            print(f"use_cache=False for {plat}/{owner}/{repo}; forcing refresh")
        else:
            local_latest_sha = _get_latest_local_sha(data_dir)
            remote_latest_sha = _get_latest_remote_sha(plat, owner, repo)
            if local_latest_sha and remote_latest_sha and local_latest_sha != remote_latest_sha:
                should_refresh = True
                print(
                    f"Detected stale cache for {plat}/{owner}/{repo}: "
                    f"local={local_latest_sha[:8]} remote={remote_latest_sha[:8]}"
                )

        if should_refresh:
            try:
                success = _extract_platform_data(plat, owner, repo)
                if not success and not has_local_data:
                    raise HTTPException(status_code=500, detail=f"Failed to extract {plat} data for {owner}/{repo}")
                if success:
                    used_cached_data = False
            except Exception as e:
                if not has_local_data:
                    raise HTTPException(status_code=500, detail=f"Failed to extract {plat} data for {owner}/{repo}: {e}")
                print(f"⚠ Refresh failed for {plat}/{owner}/{repo}, falling back to local cache: {e}")

        # Step 3: Load all authors from commits
        if not commits_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No commit data found for {owner}/{repo}"
            )

        authors_map = {}

        # Check for direct .json files in commits directory
        for commit_file in commits_dir.glob("*.json"):
            try:
                with open(commit_file, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    author = get_author_from_commit(commit_data)

                    # Get email from commit data (GitHub/Gitee shapes differ)
                    email = ""
                    if "commit" in commit_data:
                        email = commit_data.get("commit", {}).get("author", {}).get("email", "") or ""
                    if not email and isinstance(commit_data.get("author"), dict):
                        email = commit_data.get("author", {}).get("email", "") or ""
                    if not email and isinstance(commit_data.get("committer"), dict):
                        email = commit_data.get("committer", {}).get("email", "") or ""

                    if author:
                        author = author.strip()
                        if author not in authors_map:
                            authors_map[author] = {
                                "author": author,
                                "email": email,
                                "commits": 0
                            }
                        elif not authors_map[author].get("email") and email:
                            authors_map[author]["email"] = email
                        authors_map[author]["commits"] += 1
            except Exception as e:
                print(f"⚠ Error reading {commit_file}: {e}")
                continue

        if not authors_map:
            raise HTTPException(
                status_code=404,
                detail=f"No commit authors found in {commits_dir}"
            )

        # Sort by commit count
        authors_list = sorted(
            authors_map.values(),
            key=lambda x: x["commits"],
            reverse=True
        )

        return {
            "success": True,
            "data": {
                "owner": owner,
                "repo": repo,
                "authors": authors_list,
                "total_authors": len(authors_list),
                "cached": used_cached_data
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Failed to get authors: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get authors: {str(e)}")
