"""Cross-platform GitHub/Gitee evidence aggregation routes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException

from evaluator.paths import get_data_dir
from evaluator.services.collaboration_evidence import fetch_collaboration_evidence
from evaluator.utils import (
    get_author_from_commit,
    get_emails_from_commit,
    is_commit_by_author,
    is_valid_email_identity,
    load_commits_from_local,
    normalize_email_identity,
)


router = APIRouter()

DEFAULT_EVIDENCE_SOURCES = [
    "commit_diffs",
    "pr_discussions",
    "review_comments",
    "issue_triage",
    "approvals",
    "maintainer_decisions",
]
MAX_COMMITS_PER_REPO_EMAIL = 200


def _parse_email_list(value: Any) -> List[str]:
    if isinstance(value, list):
        raw_items = [str(item or "").strip() for item in value]
    elif isinstance(value, str):
        raw_items = [part.strip() for part in value.split(",")]
    else:
        raise HTTPException(status_code=400, detail="emails must be a comma-separated string or list")

    emails: List[str] = []
    seen = set()
    invalid: List[str] = []

    for item in raw_items:
        if not item:
            continue
        normalized = normalize_email_identity(item)
        if not is_valid_email_identity(normalized):
            invalid.append(item)
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        emails.append(normalized)

    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid email format: {', '.join(invalid)}")
    if not emails:
        raise HTTPException(status_code=400, detail="At least one email is required")
    return emails


def _iter_cached_repositories() -> List[Dict[str, Any]]:
    data_dir = get_data_dir()
    repositories: List[Dict[str, Any]] = []

    for platform in ("github", "gitee"):
        platform_dir = data_dir / platform
        if not platform_dir.exists() or not platform_dir.is_dir():
            continue

        for owner_dir in sorted(item for item in platform_dir.iterdir() if item.is_dir()):
            for repo_dir in sorted(item for item in owner_dir.iterdir() if item.is_dir()):
                if (repo_dir / "commits_index.json").exists():
                    repositories.append({
                        "platform": platform,
                        "owner": owner_dir.name,
                        "repo": repo_dir.name,
                        "data_dir": repo_dir,
                    })

    return repositories


def _commit_sha(commit: Dict[str, Any]) -> str:
    return str(commit.get("sha") or commit.get("hash") or "").strip()


def _commit_message(commit: Dict[str, Any]) -> str:
    if isinstance(commit.get("commit"), dict):
        return str(commit.get("commit", {}).get("message") or commit.get("message") or "")
    return str(commit.get("message") or "")


def _commit_date(commit: Dict[str, Any]) -> str:
    if isinstance(commit.get("commit"), dict):
        nested = commit.get("commit", {})
        author = nested.get("author") if isinstance(nested.get("author"), dict) else {}
        committer = nested.get("committer") if isinstance(nested.get("committer"), dict) else {}
        value = author.get("date") or committer.get("date")
        if value:
            return str(value)
    return str(commit.get("date") or commit.get("created_at") or commit.get("committed_date") or "")


def _commit_url(platform: str, owner: str, repo: str, sha: str, commit: Dict[str, Any]) -> str:
    existing = str(commit.get("html_url") or "").strip()
    if existing:
        return existing
    host = "github.com" if platform == "github" else "gitee.com"
    return f"https://{host}/{quote(owner, safe='')}/{quote(repo, safe='')}/commit/{quote(sha, safe='')}"


def _commit_stats(commit: Dict[str, Any]) -> Dict[str, int]:
    stats = commit.get("stats") if isinstance(commit.get("stats"), dict) else {}
    return {
        "additions": int(stats.get("additions") or 0),
        "deletions": int(stats.get("deletions") or 0),
        "total": int(stats.get("total") or stats.get("changes") or 0),
        "files_changed": len(commit.get("files") or []),
    }


def _serialize_commit(
    *,
    commit: Dict[str, Any],
    platform: str,
    owner: str,
    repo: str,
    matched_email: str,
) -> Dict[str, Any]:
    sha = _commit_sha(commit)
    message = _commit_message(commit).strip()
    return {
        "platform": platform,
        "owner": owner,
        "repo": repo,
        "repo_full_name": f"{owner}/{repo}",
        "repo_url": f"https://{'github.com' if platform == 'github' else 'gitee.com'}/{owner}/{repo}",
        "sha": sha,
        "short_sha": sha[:8],
        "message": message,
        "title": message.splitlines()[0] if message else "",
        "author": get_author_from_commit(commit) or "",
        "emails": get_emails_from_commit(commit),
        "matched_email": matched_email,
        "date": _commit_date(commit),
        "url": _commit_url(platform, owner, repo, sha, commit),
        "stats": _commit_stats(commit),
    }


def _sort_key(item: Dict[str, Any]) -> datetime:
    value = str(item.get("date") or item.get("updated_at") or "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _collaboration_items_for_repo(
    *,
    platform: str,
    owner: str,
    repo: str,
    data_dir: Path,
    evidence_sources: List[str],
) -> tuple[List[Dict[str, Any]], List[str]]:
    evidence = fetch_collaboration_evidence(
        platform=platform,
        owner=owner,
        repo=repo,
        data_dir=data_dir,
        evidence_sources=evidence_sources,
    )
    items = []
    for item in evidence.get("items") or []:
        if not isinstance(item, dict):
            continue
        items.append({
            **item,
            "platform": platform,
            "owner": owner,
            "repo": repo,
            "repo_full_name": f"{owner}/{repo}",
            "repo_url": f"https://{'github.com' if platform == 'github' else 'gitee.com'}/{owner}/{repo}",
        })
    warnings = [str(warning) for warning in evidence.get("warnings") or [] if warning]
    return items, warnings


@router.post("/api/gitee-github/analyze")
async def analyze_gitee_github(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Collect cached commit and collaboration evidence for emails across GitHub/Gitee repos."""
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    emails = _parse_email_list(request_body.get("emails"))
    fetch_collaboration = bool(request_body.get("fetch_collaboration", True))
    repositories = _iter_cached_repositories()

    commits_by_email: Dict[str, List[Dict[str, Any]]] = {email: [] for email in emails}
    matched_repo_keys = set()
    matched_repos: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []

    for repository in repositories:
        platform = repository["platform"]
        owner = repository["owner"]
        repo = repository["repo"]
        data_dir = repository["data_dir"]
        repo_key = f"{platform}:{owner}/{repo}"

        try:
            commits = load_commits_from_local(data_dir, limit=None)
        except Exception as exc:
            warnings.append(f"{platform}/{owner}/{repo}: failed to load commits: {exc}")
            continue

        for email in emails:
            matched = [commit for commit in commits if is_commit_by_author(commit, email)]
            if not matched:
                continue

            matched_repo_keys.add(repo_key)
            matched_repos[repo_key] = {
                "platform": platform,
                "owner": owner,
                "repo": repo,
                "repo_full_name": f"{owner}/{repo}",
                "repo_url": f"https://{'github.com' if platform == 'github' else 'gitee.com'}/{owner}/{repo}",
            }
            serialized = [
                _serialize_commit(
                    commit=commit,
                    platform=platform,
                    owner=owner,
                    repo=repo,
                    matched_email=email,
                )
                for commit in matched[:MAX_COMMITS_PER_REPO_EMAIL]
            ]
            commits_by_email[email].extend(serialized)

    collaboration_items: List[Dict[str, Any]] = []
    if fetch_collaboration:
        for repo_key in sorted(matched_repo_keys):
            platform, path = repo_key.split(":", 1)
            owner, repo = path.split("/", 1)
            data_dir = get_data_dir() / platform / owner / repo
            items, repo_warnings = _collaboration_items_for_repo(
                platform=platform,
                owner=owner,
                repo=repo,
                data_dir=data_dir,
                evidence_sources=DEFAULT_EVIDENCE_SOURCES,
            )
            collaboration_items.extend(items)
            warnings.extend(repo_warnings)

    for email in emails:
        commits_by_email[email].sort(key=_sort_key, reverse=True)

    collaboration_items.sort(key=_sort_key, reverse=True)
    all_commits = [
        commit
        for email in emails
        for commit in commits_by_email[email]
    ]
    all_commits.sort(key=_sort_key, reverse=True)

    return {
        "success": True,
        "emails": emails,
        "scope": "cached_github_gitee_repositories",
        "repos_scanned": len(repositories),
        "matched_repos": sorted(matched_repos.values(), key=lambda item: (item["platform"], item["repo_full_name"])),
        "summary": {
            "matched_repo_count": len(matched_repos),
            "commit_count": len(all_commits),
            "collaboration_evidence_count": len(collaboration_items),
        },
        "commits_by_email": commits_by_email,
        "commits": all_commits,
        "collaboration_evidence": collaboration_items,
        "warnings": warnings,
        "limitations": [
            "Commit matching is exact by author/committer email.",
            "Issue/PR/review APIs usually expose account identities rather than raw emails, so collaboration evidence is repository-scoped for repos where the email has commits.",
            "The scan covers repositories already present in the local Oscanner data cache.",
        ],
    }
