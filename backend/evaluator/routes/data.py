"""Data extraction and author discovery routes."""

import json
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Response

from evaluator.config import get_gitee_token, get_github_token
from evaluator.paths import get_platform_data_dir
from evaluator.services import (
    extract_github_data,
    extract_gitee_data,
    fetch_gitee_commits,
)
from evaluator.services.extraction_service import get_requests_session
from evaluator.utils import get_author_from_commit, get_emails_from_commit

router = APIRouter()


GITHUB_COMMIT_AUTHORS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              author {
                name
                email
                user {
                  login
                  avatarUrl
                  url
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


def _author_identity_key(name: str, email: str) -> str:
    email = str(email or "").strip().lower()
    if email:
        return f"email:{email}"
    return f"name:{str(name or '').strip().lower()}"


def _merge_author_group(
    authors_map: Dict[str, Dict[str, Any]],
    *,
    name: str,
    email: str,
    commits: int = 1,
    provider_login: str = "",
    avatar_url: str = "",
    html_url: str = "",
) -> None:
    name = str(name or "").strip()
    email = str(email or "").strip()
    if not name and not email:
        return

    key = _author_identity_key(name, email)
    name_key = _author_identity_key(name, "")
    if email and name and key not in authors_map and name_key in authors_map:
        authors_map[key] = authors_map.pop(name_key)
    elif not email and name:
        for existing_key, existing in authors_map.items():
            if existing_key.startswith("email:") and name in existing.get("aliases", []):
                key = existing_key
                break

    if key not in authors_map:
        authors_map[key] = {
            "author": name or email,
            "email": email,
            "commits": 0,
            "aliases": [],
        }

    group = authors_map[key]
    if name and name not in group["aliases"]:
        group["aliases"].append(name)
    if name and (not group.get("author") or group.get("author") == group.get("email")):
        group["author"] = name
    if email and not group.get("email"):
        group["email"] = email
    if provider_login and not group.get("provider_login"):
        group["provider_login"] = provider_login
    if avatar_url and not group.get("avatar_url"):
        group["avatar_url"] = avatar_url
    if html_url and not group.get("html_url"):
        group["html_url"] = html_url

    group["commits"] += commits


def _finalize_author_groups(authors_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for item in authors_map.values():
        if len(item.get("aliases") or []) <= 1:
            item.pop("aliases", None)
        results.append(item)
    return sorted(results, key=lambda x: x["commits"], reverse=True)


def _extract_platform_data(platform: str, owner: str, repo: str) -> bool:
    """Extract repository data from the given platform."""
    if platform == "gitee":
        print(f"Extracting latest data from Gitee for {owner}/{repo}...")
        return extract_gitee_data(owner, repo)
    print(f"Extracting latest data from GitHub for {owner}/{repo}...")
    return extract_github_data(owner, repo, include_file_context=False)


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
        _merge_author_group(authors_map, name=str(author or ""), email=str(email or ""), commits=commits)

    return _finalize_author_groups(authors_map)

def _normalize_github_commit_author_nodes(nodes: Any) -> List[Dict[str, Any]]:
    if not isinstance(nodes, list):
        return []

    authors_map: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue

        author_data = node.get("author")
        if not isinstance(author_data, dict):
            continue

        name = str(author_data.get("name") or "").strip()
        email = str(author_data.get("email") or "").strip()
        user_data = author_data.get("user")
        if not isinstance(user_data, dict):
            user_data = {}

        _merge_author_group(
            authors_map,
            name=name,
            email=email,
            commits=1,
            provider_login=str(user_data.get("login") or ""),
            avatar_url=str(user_data.get("avatarUrl") or ""),
            html_url=str(user_data.get("url") or ""),
        )

    for item in authors_map.values():
        item.setdefault("provider_login", "")
        item.setdefault("avatar_url", "")
        item.setdefault("html_url", "")
    return _finalize_author_groups(authors_map)

def _fetch_github_contributors_authors(owner: str, repo: str) -> List[Dict[str, Any]]:
    """
    Fetch GitHub authors through GraphQL commit history.

    GitHub's REST contributors API groups by GitHub account/email. For evaluator
    identity selection, use raw Git commit author name + email instead.
    """
    github_token = get_github_token()
    if not github_token:
        print("[GitHub Authors] GitHub token not configured; skipping GraphQL author API")
        return []

    graphql_url = "https://api.github.com/graphql"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "oscanner-skill-evaluator",
        "Authorization": f"Bearer {github_token}",
    }

    nodes: List[Dict[str, Any]] = []
    cursor = None
    while True:
        try:
            response = get_requests_session().post(
                graphql_url,
                headers=headers,
                json={
                    "query": GITHUB_COMMIT_AUTHORS_QUERY,
                    "variables": {
                        "owner": owner,
                        "name": repo,
                        "cursor": cursor,
                    },
                },
                timeout=10,
            )
        except Exception as exc:
            print(f"[GitHub Authors] GraphQL author API request failed for {owner}/{repo}: {exc}")
            return [] if not nodes else _normalize_github_commit_author_nodes(nodes)

        if response.status_code != 200:
            print(f"[GitHub Authors] GraphQL author API returned {response.status_code} for {owner}/{repo}")
            return [] if not nodes else _normalize_github_commit_author_nodes(nodes)

        try:
            payload = response.json()
        except Exception as exc:
            print(f"[GitHub Authors] Failed to parse GraphQL author response for {owner}/{repo}: {exc}")
            return [] if not nodes else _normalize_github_commit_author_nodes(nodes)

        if not isinstance(payload, dict) or payload.get("errors"):
            print(f"[GitHub Authors] GraphQL author API returned errors for {owner}/{repo}: {payload.get('errors') if isinstance(payload, dict) else payload}")
            return [] if not nodes else _normalize_github_commit_author_nodes(nodes)

        history = (
            payload.get("data", {})
            .get("repository", {})
            .get("defaultBranchRef", {})
            .get("target", {})
            .get("history", {})
        )
        if not isinstance(history, dict):
            return [] if not nodes else _normalize_github_commit_author_nodes(nodes)

        page_nodes = history.get("nodes")
        if isinstance(page_nodes, list):
            nodes.extend(page_nodes)

        page_info = history.get("pageInfo") if isinstance(history.get("pageInfo"), dict) else {}
        if not page_info.get("hasNextPage") or not page_info.get("endCursor"):
            break
        cursor = page_info.get("endCursor")

    return _normalize_github_commit_author_nodes(nodes)


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
                author = (get_author_from_commit(commit_data) or "").strip()
                emails = get_emails_from_commit(commit_data)
                email = emails[0] if emails else ""
                _merge_author_group(authors_map, name=author, email=email, commits=1)
        except Exception as e:
            print(f"⚠ Error reading {commit_file}: {e}")
            continue

    return _finalize_author_groups(authors_map)

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
        elif plat == "github":
            contributors_authors = _fetch_github_contributors_authors(owner, repo)
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
