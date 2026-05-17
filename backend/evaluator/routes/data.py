"""Data extraction and author discovery routes."""

import json
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Response

from evaluator.config import get_gitee_token
from evaluator.paths import get_platform_data_dir
from evaluator.services import (
    extract_github_data,
    extract_gitee_data,
    fetch_gitee_commits,
)
from evaluator.services.extraction_service import get_requests_session
from evaluator.utils import get_author_from_commit

router = APIRouter()


def _extract_platform_data(platform: str, owner: str, repo: str) -> bool:
    """Extract repository data from the given platform."""
    if platform == "gitee":
        print(f"Extracting latest data from Gitee for {owner}/{repo}...")
        return extract_gitee_data(owner, repo)
    print(f"Extracting latest data from GitHub for {owner}/{repo}...")
    return extract_github_data(owner, repo)


def _coerce_commit_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _normalize_gitee_contributors(contributors: Any) -> List[Dict[str, Any]]:
    if not isinstance(contributors, list):
        return []

    authors_map: Dict[str, Dict[str, Any]] = {}
    for item in contributors:
        if not isinstance(item, dict):
            continue

        nested_author = item.get("author") if isinstance(item.get("author"), dict) else {}
        author = (
            item.get("name")
            or item.get("author_name")
            or item.get("login")
            or item.get("username")
            or nested_author.get("name")
            or nested_author.get("login")
            or nested_author.get("username")
            or ""
        )
        author = str(author).strip()
        if not author:
            continue

        email = (
            item.get("email")
            or item.get("author_email")
            or nested_author.get("email")
            or ""
        )
        commits = _coerce_commit_count(
            item.get("commits")
            or item.get("contributions")
            or item.get("commit_count")
            or item.get("total")
        )

        if author not in authors_map:
            authors_map[author] = {"author": author, "email": str(email or ""), "commits": 0}
        elif not authors_map[author].get("email") and email:
            authors_map[author]["email"] = str(email)

        authors_map[author]["commits"] += commits

    return sorted(authors_map.values(), key=lambda x: x["commits"], reverse=True)


def _fetch_gitee_contributors_authors(owner: str, repo: str) -> List[Dict[str, Any]]:
    """
    Fetch Gitee committers through the lightweight contributors API.

    This avoids full repository extraction for author discovery.
    """
    gitee_token = get_gitee_token()
    if not gitee_token:
        print("[Gitee Authors] Gitee token not configured; skipping contributors API")
        return []

    contributors_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/contributors"
    try:
        response = get_requests_session().get(
            contributors_url,
            params={"access_token": gitee_token, "type": "committers"},
            timeout=10,
        )
    except Exception as exc:
        print(f"[Gitee Authors] Contributors API request failed for {owner}/{repo}: {exc}")
        return []

    if response.status_code != 200:
        print(f"[Gitee Authors] Contributors API returned {response.status_code} for {owner}/{repo}")
        return []

    try:
        return _normalize_gitee_contributors(response.json())
    except Exception as exc:
        print(f"[Gitee Authors] Failed to parse contributors response for {owner}/{repo}: {exc}")
        return []


def _load_authors_from_commit_files(commits_dir) -> List[Dict[str, Any]]:
    authors_map: Dict[str, Dict[str, Any]] = {}

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

    return sorted(
        authors_map.values(),
        key=lambda x: x["commits"],
        reverse=True
    )


def _authors_response(owner: str, repo: str, authors_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "success": True,
        "data": {
            "owner": owner,
            "repo": repo,
            "authors": authors_list,
            "total_authors": len(authors_list)
        }
    }


@router.get("/api/gitee/commits/{owner}/{repo}")
async def get_gitee_commits(
    owner: str,
    repo: str,
    limit: int = Query(500, ge=1, le=1000),
    is_enterprise: bool = Query(False)
):
    """Fetch commits for a Gitee repository"""
    # Fetch from Gitee API
    commits = fetch_gitee_commits(owner, repo, limit, is_enterprise)

    return {
        "success": True,
        "data": commits
    }


@router.get("/api/authors/{owner}/{repo}")
async def get_authors(
    owner: str,
    repo: str,
    response: Response,
    platform: str = Query("github"),
):
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

        # Never allow HTTP-layer caching for this endpoint.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        if plat == "gitee":
            contributors_authors = _fetch_gitee_contributors_authors(owner, repo)
            if contributors_authors:
                return _authors_response(owner, repo, contributors_authors)

        try:
            success = _extract_platform_data(plat, owner, repo)
            if not success:
                raise HTTPException(status_code=500, detail=f"Failed to extract {plat} data for {owner}/{repo}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to extract {plat} data for {owner}/{repo}: {e}")

        # Step 3: Load all authors from commits
        if not commits_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No commit data found for {owner}/{repo}"
            )

        authors_list = _load_authors_from_commit_files(commits_dir)

        if not authors_list:
            raise HTTPException(
                status_code=404,
                detail=f"No commit authors found in {commits_dir}"
            )

        return _authors_response(owner, repo, authors_list)

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Failed to get authors: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get authors: {str(e)}")
