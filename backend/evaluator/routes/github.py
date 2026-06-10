"""GitHub global evidence aggregation routes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

import asyncio
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from evaluator.config import DEFAULT_LLM_MODEL, get_github_token, get_llm_api_key
from evaluator.paths import get_data_dir
from evaluator.plugin_registry import PluginLoadError, load_scan_module
from evaluator.services import resolve_plugin_id
from evaluator.services.collaboration_evidence import fetch_collaboration_evidence
from evaluator.utils import (
    get_author_from_commit,
    get_emails_from_commit,
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
MAX_COMMITS_PER_REPO_EMAIL = 100
GITHUB_API_BASE = "https://api.github.com"
GITHUB_SEARCH_COMMITS_PER_ROLE = 10
GITHUB_MAX_SEARCH_COMMITS_PER_ROLE = 100
GITHUB_SEARCH_EVIDENCE_PER_QUERY = 100


def _wants_sse(request: Optional[Request]) -> bool:
    accept = request.headers.get("accept", "").lower() if request is not None else ""
    return "text/event-stream" in accept


def _format_sse_event(event: str, data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


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


def _iter_cached_gitee_repositories() -> List[Dict[str, Any]]:
    return [repo for repo in _iter_cached_repositories() if repo.get("platform") == "gitee"]


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


def _nested_identity(commit: Dict[str, Any], role: str) -> Dict[str, Any]:
    nested = commit.get("commit")
    if not isinstance(nested, dict):
        return {}
    value = nested.get(role)
    return value if isinstance(value, dict) else {}


def _top_level_identity(commit: Dict[str, Any], role: str) -> Dict[str, Any]:
    value = commit.get(role)
    return value if isinstance(value, dict) else {}


def _identity_email(commit: Dict[str, Any], role: str) -> str:
    return str(_nested_identity(commit, role).get("email") or _top_level_identity(commit, role).get("email") or "").strip()


def _identity_name(commit: Dict[str, Any], role: str) -> str:
    return str(_nested_identity(commit, role).get("name") or _top_level_identity(commit, role).get("name") or "").strip()


def _identity_date(commit: Dict[str, Any], role: str) -> str:
    return str(_nested_identity(commit, role).get("date") or _top_level_identity(commit, role).get("date") or "").strip()


def _identity_login(commit: Dict[str, Any], role: str) -> str:
    return str(_top_level_identity(commit, role).get("login") or "").strip()


def _matched_roles_for_email(commit: Dict[str, Any], email: str) -> List[Dict[str, str]]:
    normalized = normalize_email_identity(email)
    roles: List[Dict[str, str]] = []
    for role in ("author", "committer"):
        role_email = normalize_email_identity(_identity_email(commit, role))
        if role_email == normalized:
            roles.append({
                "role": role,
                "email": role_email,
                "name": _identity_name(commit, role),
                "date": _identity_date(commit, role),
                "github_login": _identity_login(commit, role),
            })
    return roles


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
    matched_roles = _matched_roles_for_email(commit, matched_email)
    git_author = {
        "name": _identity_name(commit, "author"),
        "email": _identity_email(commit, "author"),
        "date": _identity_date(commit, "author"),
        "github_login": _identity_login(commit, "author") if platform == "github" else "",
    }
    git_committer = {
        "name": _identity_name(commit, "committer"),
        "email": _identity_email(commit, "committer"),
        "date": _identity_date(commit, "committer"),
        "github_login": _identity_login(commit, "committer") if platform == "github" else "",
    }
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
        "commit": {
            "author": git_author,
            "committer": git_committer,
            "message": message,
        },
        "emails": get_emails_from_commit(commit),
        "matched_email": matched_email,
        "matched_roles": matched_roles,
        "git_author": git_author,
        "git_committer": git_committer,
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


def _github_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = get_github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_repo_parts_from_item(item: Dict[str, Any]) -> tuple[str, str] | None:
    repository = item.get("repository") if isinstance(item.get("repository"), dict) else {}
    full_name = str(repository.get("full_name") or "").strip()
    if "/" not in full_name:
        return None
    owner, repo = full_name.split("/", 1)
    if not owner or not repo:
        return None
    return owner, repo


def _github_repo_item(platform: str, owner: str, repo: str) -> Dict[str, Any]:
    return {
        "platform": platform,
        "owner": owner,
        "repo": repo,
        "repo_full_name": f"{owner}/{repo}",
        "repo_url": f"https://github.com/{owner}/{repo}" if platform == "github" else f"https://gitee.com/{owner}/{repo}",
    }


def _github_search_items(
    client: httpx.Client,
    *,
    endpoint: str,
    q: str,
    warnings: List[str],
    sort: str = "updated",
    order: str = "desc",
    max_items: int = GITHUB_SEARCH_EVIDENCE_PER_QUERY,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    per_page = min(100, max(1, max_items))
    page = 1

    while len(items) < max_items:
        response = client.get(
            f"{GITHUB_API_BASE}/search/{endpoint}",
            params={
                "q": q,
                "sort": sort,
                "order": order,
                "per_page": per_page,
                "page": page,
            },
        )
        try:
            response.raise_for_status()
        except Exception as exc:
            warnings.append(f"github search {endpoint} failed for {q!r}: {exc}")
            break

        payload = response.json()
        if isinstance(payload, dict) and payload.get("incomplete_results"):
            warnings.append(f"github search {endpoint} returned incomplete results for {q!r}")
        page_items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(page_items, list) or not page_items:
            break
        items.extend(item for item in page_items if isinstance(item, dict))
        if len(page_items) < per_page:
            break
        page += 1

    return items[:max_items]


def _github_get_json(
    client: httpx.Client,
    url: str,
    *,
    warnings: List[str],
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        warnings.append(f"github get failed for {url}: {exc}")
        return None


def _github_commit_detail(
    client: httpx.Client,
    *,
    owner: str,
    repo: str,
    sha: str,
    warnings: List[str],
) -> Optional[Dict[str, Any]]:
    payload = _github_get_json(
        client,
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}",
        warnings=warnings,
    )
    return payload if isinstance(payload, dict) else None


def _dedupe_by_key(items: List[Dict[str, Any]], key_fields: tuple[str, ...]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in items:
        key = tuple(str(item.get(field) or "") for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _github_linked_pull_items(
    client: httpx.Client,
    *,
    owner: str,
    repo: str,
    sha: str,
    warnings: List[str],
) -> List[Dict[str, Any]]:
    payload = _github_get_json(
        client,
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}/pulls",
        warnings=warnings,
    )
    return payload if isinstance(payload, list) else []


def _github_issue_search_item(
    item: Dict[str, Any],
    *,
    source: str,
    detail: str,
    login: str,
) -> Dict[str, Any]:
    repository_url = str(item.get("repository_url") or "")
    repo_full_name = repository_url.rsplit("/repos/", 1)[-1] if "/repos/" in repository_url else ""
    owner, repo = (repo_full_name.split("/", 1) + [""])[:2] if "/" in repo_full_name else ("", "")
    return {
        "source": source,
        "label": f"#{item.get('number')}: {item.get('title') or ''}".strip(),
        "detail": detail,
        "url": item.get("html_url"),
        "updated_at": item.get("updated_at") or item.get("created_at"),
        "platform": "github",
        "owner": owner,
        "repo": repo,
        "repo_full_name": repo_full_name,
        "repo_url": f"https://github.com/{repo_full_name}" if repo_full_name else "",
        "github_login": login,
        "attribution": "github_login",
    }


def _github_evidence_for_logins(
    client: httpx.Client,
    *,
    logins: List[str],
    warnings: List[str],
    max_items_per_query: int = GITHUB_SEARCH_EVIDENCE_PER_QUERY,
) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    seen_logins = sorted({login for login in logins if login})
    queries = [
        ("issue_triage", "type:issue author:{login}", "issue created by GitHub login"),
        ("pr_discussions", "type:pr author:{login}", "pull request created by GitHub login"),
        ("review_comments", "type:pr reviewed-by:{login}", "pull request reviewed by GitHub login"),
        ("pr_discussions", "type:pr commenter:{login}", "pull request discussed by GitHub login"),
        ("issue_triage", "type:issue commenter:{login}", "issue commented by GitHub login"),
        ("maintainer_decisions", "type:pr merged-by:{login}", "pull request merged by GitHub login"),
    ]

    for login in seen_logins:
        for source, template, detail in queries:
            q = f"{template.format(login=login)} archived:false"
            items = _github_search_items(
                client,
                endpoint="issues",
                q=q,
                warnings=warnings,
                sort="updated",
                order="desc",
                max_items=max_items_per_query,
            )
            evidence.extend(
                _github_issue_search_item(item, source=source, detail=detail, login=login)
                for item in items
            )

    return _dedupe_by_key(evidence, ("source", "url", "github_login"))


def _github_commit_linked_evidence(
    client: httpx.Client,
    *,
    commits: List[Dict[str, Any]],
    warnings: List[str],
) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    seen_pr_urls = set()

    for commit in commits[:100]:
        owner = str(commit.get("owner") or "")
        repo = str(commit.get("repo") or "")
        sha = str(commit.get("sha") or "")
        if not owner or not repo or not sha:
            continue

        pulls = _github_linked_pull_items(client, owner=owner, repo=repo, sha=sha, warnings=warnings)
        for pull in pulls:
            if not isinstance(pull, dict):
                continue
            url = str(pull.get("html_url") or "")
            if url in seen_pr_urls:
                continue
            seen_pr_urls.add(url)
            number = pull.get("number")
            title = str(pull.get("title") or "").strip()
            label = f"PR #{number}: {title}" if number else f"PR: {title}"
            decision = "merged" if pull.get("merged_at") else str(pull.get("state") or "linked")
            evidence.append({
                "source": "maintainer_decisions",
                "label": label,
                "detail": f"commit {sha[:8]} is associated with PR decision: {decision}",
                "url": url,
                "updated_at": pull.get("updated_at") or pull.get("merged_at") or pull.get("closed_at"),
                "platform": "github",
                "owner": owner,
                "repo": repo,
                "repo_full_name": f"{owner}/{repo}",
                "repo_url": f"https://github.com/{owner}/{repo}",
                "commit_sha": sha,
                "attribution": "commit_association",
            })

            reviews = _github_get_json(
                client,
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{number}/reviews",
                warnings=warnings,
            ) if number else None
            if isinstance(reviews, list):
                approvals = [
                    review for review in reviews
                    if isinstance(review, dict) and str(review.get("state") or "").upper() == "APPROVED"
                ]
                if approvals:
                    evidence.append({
                        "source": "approvals",
                        "label": f"{label} approved",
                        "detail": f"{len(approvals)} approval review(s) on PR associated with commit {sha[:8]}",
                        "url": url,
                        "updated_at": pull.get("updated_at"),
                        "platform": "github",
                        "owner": owner,
                        "repo": repo,
                        "repo_full_name": f"{owner}/{repo}",
                        "repo_url": f"https://github.com/{owner}/{repo}",
                        "commit_sha": sha,
                        "attribution": "commit_association",
                    })

    return _dedupe_by_key(evidence, ("source", "url", "commit_sha"))


def _global_github_evidence_links(commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    for commit in commits:
        sha = str(commit.get("sha") or "").strip()
        url = str(commit.get("url") or "").strip()
        repo_url = str(commit.get("repo_url") or "").strip()
        if sha and url:
            links.append({
                "type": "commit",
                "label": f"{commit.get('repo_full_name') or 'github'}@{sha[:8]}",
                "sha": sha,
                "url": url,
            })

        for file_item in commit.get("files") or []:
            if isinstance(file_item, dict):
                path = str(file_item.get("filename") or file_item.get("path") or "").strip().strip("/")
            else:
                path = str(file_item or "").strip().strip("/")
            if not sha or not repo_url or not path:
                continue
            links.append({
                "type": "file",
                "label": path,
                "path": path,
                "commit_sha": sha,
                "url": f"{repo_url}/blob/{quote(sha, safe='')}/{quote(path, safe='/')}",
            })

    return _dedupe_by_key(links, ("type", "url", "sha", "commit_sha", "path"))[:500]


def _github_global_analysis_payload(
    *,
    emails: List[str],
    commits_by_email: Dict[str, List[Dict[str, Any]]],
    matched_repos: Dict[str, Dict[str, Any]],
    collaboration_items: List[Dict[str, Any]],
    warnings: List[str],
) -> Dict[str, Any]:
    for email in emails:
        commits_by_email[email].sort(key=_sort_key, reverse=True)

    collaboration_items.sort(key=_sort_key, reverse=True)
    all_commits = [
        commit
        for email in emails
        for commit in commits_by_email[email]
    ]
    all_commits = _dedupe_by_key(all_commits, ("platform", "repo_full_name", "sha"))
    all_commits.sort(key=_sort_key, reverse=True)

    return {
        "success": True,
        "emails": emails,
        "scope": "github_global",
        "repos_scanned": len(matched_repos),
        "matched_repos": sorted(matched_repos.values(), key=lambda item: item["repo_full_name"]),
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
            "GitHub commits are searched globally with author-email and committer-email qualifiers.",
            "GitHub issue/PR/review evidence uses GitHub logins resolved from matching commits; email-only accounts with no resolved login may only have commit and commit-associated PR evidence.",
            "GitHub search is limited to repositories visible to the configured token and to repository default branches.",
        ],
    }


def _fetch_global_github_evidence(
    emails: List[str],
    *,
    max_commits_per_role: int = GITHUB_SEARCH_COMMITS_PER_ROLE,
    max_evidence_per_query: int = GITHUB_SEARCH_EVIDENCE_PER_QUERY,
) -> tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    commits_by_email: Dict[str, List[Dict[str, Any]]] = {email: [] for email in emails}
    matched_repos: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []
    github_logins = set()

    with httpx.Client(headers=_github_headers(), timeout=httpx.Timeout(25.0, connect=5.0)) as client:
        for email in emails:
            found_by_sha: Dict[str, Dict[str, Any]] = {}
            for role, qualifier, sort in (
                ("author", "author-email", "author-date"),
                ("committer", "committer-email", "committer-date"),
            ):
                search_items = _github_search_items(
                    client,
                    endpoint="commits",
                    q=f"{qualifier}:{email}",
                    warnings=warnings,
                    sort=sort,
                    order="desc",
                    max_items=max_commits_per_role,
                )
                for item in search_items:
                    sha = _commit_sha(item)
                    repo_parts = _github_repo_parts_from_item(item)
                    if not sha or repo_parts is None:
                        continue
                    owner, repo = repo_parts
                    detail = _github_commit_detail(client, owner=owner, repo=repo, sha=sha, warnings=warnings)
                    commit = detail or item
                    roles = _matched_roles_for_email(commit, email)
                    if not roles:
                        warnings.append(f"github commit {owner}/{repo}@{sha[:8]} matched {qualifier} search but email was not visible in fetched commit")
                        continue

                    for matched_role in roles:
                        if matched_role.get("github_login"):
                            github_logins.add(matched_role["github_login"])

                    serialized = _serialize_commit(
                        commit=commit,
                        platform="github",
                        owner=owner,
                        repo=repo,
                        matched_email=email,
                    )
                    serialized["search_role"] = role
                    serialized["source"] = "github_global_commit_search"
                    found_by_sha[sha] = serialized
                    matched_repos[f"github:{owner}/{repo}"] = _github_repo_item("github", owner, repo)

            commits_by_email[email].extend(found_by_sha.values())

        github_commits = [
            commit
            for email_commits in commits_by_email.values()
            for commit in email_commits
        ]
        evidence = _github_commit_linked_evidence(client, commits=github_commits, warnings=warnings)
        evidence.extend(_github_evidence_for_logins(
            client,
            logins=sorted(github_logins),
            warnings=warnings,
            max_items_per_query=max_evidence_per_query,
        ))

    return commits_by_email, matched_repos, _dedupe_by_key(evidence, ("source", "url", "github_login", "commit_sha")), warnings


def _prepare_global_github_evaluation(request_body: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    api_key = get_llm_api_key()
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init).",
        )

    emails = _parse_email_list(request_body.get("emails"))
    model = str(request_body.get("model") or DEFAULT_LLM_MODEL)
    plugin_id = resolve_plugin_id(str(request_body.get("plugin") or ""))
    language = str(request_body.get("language") or "en-US")

    github_commit_limit = request_body.get("max_github_commits_per_role", GITHUB_SEARCH_COMMITS_PER_ROLE)
    github_evidence_limit = request_body.get("max_github_evidence_per_query", GITHUB_SEARCH_EVIDENCE_PER_QUERY)
    try:
        github_commit_limit = min(GITHUB_MAX_SEARCH_COMMITS_PER_ROLE, max(1, int(github_commit_limit)))
        github_evidence_limit = min(100, max(1, int(github_evidence_limit)))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="GitHub limits must be integers")

    try:
        meta, scan_mod, scan_path = load_scan_module(plugin_id)
    except PluginLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "api_key": api_key,
        "emails": emails,
        "model": model,
        "plugin_id": plugin_id,
        "language": language,
        "github_commit_limit": github_commit_limit,
        "github_evidence_limit": github_evidence_limit,
        "meta": meta,
        "scan_mod": scan_mod,
        "scan_path": scan_path,
    }


def _evaluate_global_github_commits(
    *,
    api_key: str,
    emails: List[str],
    model: str,
    plugin_id: str,
    language: str,
    meta: Any,
    scan_mod: Any,
    all_commits: List[Dict[str, Any]],
    collaboration_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    collaboration_payload = {
        "requested_sources": DEFAULT_EVIDENCE_SOURCES,
        "items": collaboration_items,
    }
    evaluator = scan_mod.create_commit_evaluator(
        data_dir=str(get_data_dir() / "github_global"),
        api_key=api_key,
        model=model,
        language=language,
        collaboration_evidence=collaboration_payload,
    )
    evaluation = evaluator.evaluate_engineer(
        commits=all_commits,
        username=",".join(emails),
        max_commits=150,
        load_files=False,
    )
    evaluation["email"] = emails[0]
    evaluation["emails"] = emails
    evaluation["plugin"] = plugin_id
    evaluation["scope"] = "github_global"
    if meta:
        evaluation["plugin_version"] = meta.version
    evidence_links = _global_github_evidence_links(all_commits)
    if evidence_links:
        evaluation["evidence_links"] = evidence_links
    return evaluation


async def _build_global_github_evaluation_payload(
    request_body: Dict[str, Any],
    *,
    progress: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    prepared = _prepare_global_github_evaluation(request_body)
    emails = prepared["emails"]

    if progress:
        progress("section", {
            "title": "采集 GitHub 证据",
            "status": "running",
            "emails": emails,
            "max_github_commits_per_role": prepared["github_commit_limit"],
        })

    commits_by_email, matched_repos, collaboration_items, warnings = await asyncio.to_thread(
        _fetch_global_github_evidence,
        emails,
        max_commits_per_role=prepared["github_commit_limit"],
        max_evidence_per_query=prepared["github_evidence_limit"],
    )
    payload = _github_global_analysis_payload(
        emails=emails,
        commits_by_email=commits_by_email,
        matched_repos=matched_repos,
        collaboration_items=collaboration_items,
        warnings=warnings,
    )

    all_commits = payload["commits"]
    if progress:
        progress("section", {
            "title": "GitHub 证据采集完成",
            "status": "done",
            "matched_repo_count": payload["summary"]["matched_repo_count"],
            "commit_count": payload["summary"]["commit_count"],
            "collaboration_evidence_count": payload["summary"]["collaboration_evidence_count"],
        })

    if not all_commits:
        raise HTTPException(status_code=404, detail="No GitHub commits found for the supplied email identities")

    if progress:
        progress("section", {
            "title": "运行能力评估",
            "status": "running",
            "commit_count": len(all_commits),
            "plugin": prepared["plugin_id"],
        })

    evaluation = await asyncio.to_thread(
        _evaluate_global_github_commits,
        api_key=prepared["api_key"],
        emails=emails,
        model=prepared["model"],
        plugin_id=prepared["plugin_id"],
        language=prepared["language"],
        meta=prepared["meta"],
        scan_mod=prepared["scan_mod"],
        all_commits=all_commits,
        collaboration_items=collaboration_items,
    )
    payload["evaluation"] = evaluation
    payload["metadata"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "github_global_email_evaluation",
        "plugin": prepared["plugin_id"],
        "scan": str(prepared["scan_path"]),
    }

    if progress:
        progress("section", {
            "title": "能力评估完成",
            "status": "done",
            "total_commits_analyzed": evaluation.get("total_commits_analyzed"),
        })

    return payload


async def _stream_global_github_evaluation(request_body: Dict[str, Any]):
    try:
        prepared = _prepare_global_github_evaluation(request_body)
        emails = prepared["emails"]

        yield _format_sse_event("section", {
            "title": "准备 GitHub 全局评估",
            "status": "running",
            "emails": emails,
        })

        yield _format_sse_event("section", {
            "title": "采集 GitHub 证据",
            "status": "running",
            "emails": emails,
            "max_github_commits_per_role": prepared["github_commit_limit"],
        })

        commits_by_email, matched_repos, collaboration_items, warnings = await asyncio.to_thread(
            _fetch_global_github_evidence,
            emails,
            max_commits_per_role=prepared["github_commit_limit"],
            max_evidence_per_query=prepared["github_evidence_limit"],
        )
        payload = _github_global_analysis_payload(
            emails=emails,
            commits_by_email=commits_by_email,
            matched_repos=matched_repos,
            collaboration_items=collaboration_items,
            warnings=warnings,
        )

        yield _format_sse_event("section", {
            "title": "GitHub 证据采集完成",
            "status": "done",
            "matched_repo_count": payload["summary"]["matched_repo_count"],
            "commit_count": payload["summary"]["commit_count"],
            "collaboration_evidence_count": payload["summary"]["collaboration_evidence_count"],
        })

        all_commits = payload["commits"]
        if not all_commits:
            raise HTTPException(status_code=404, detail="No GitHub commits found for the supplied email identities")

        yield _format_sse_event("section", {
            "title": "运行能力评估",
            "status": "running",
            "commit_count": len(all_commits),
            "plugin": prepared["plugin_id"],
        })

        evaluation = await asyncio.to_thread(
            _evaluate_global_github_commits,
            api_key=prepared["api_key"],
            emails=emails,
            model=prepared["model"],
            plugin_id=prepared["plugin_id"],
            language=prepared["language"],
            meta=prepared["meta"],
            scan_mod=prepared["scan_mod"],
            all_commits=all_commits,
            collaboration_items=collaboration_items,
        )
        payload["evaluation"] = evaluation
        payload["metadata"] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "github_global_email_evaluation",
            "plugin": prepared["plugin_id"],
            "scan": str(prepared["scan_path"]),
        }

        yield _format_sse_event("section", {
            "title": "能力评估完成",
            "status": "done",
            "total_commits_analyzed": evaluation.get("total_commits_analyzed"),
        })
        yield _format_sse_event("result", payload)
    except HTTPException as exc:
        yield _format_sse_event("error", {
            "message": exc.detail,
            "status_code": exc.status_code,
        })
    except Exception as exc:
        yield _format_sse_event("error", {
            "message": str(exc),
            "status_code": 500,
        })


@router.post("/api/github/evaluate")
@router.post("/api/gitee-github/evaluate", deprecated=True)
async def evaluate_global_github(request_body: Dict[str, Any], request: Request = None) -> Any:
    """Evaluate a contributor across globally visible GitHub repositories by commit email."""
    if _wants_sse(request):
        return StreamingResponse(
            _stream_global_github_evaluation(request_body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return await _build_global_github_evaluation_payload(request_body)


@router.post("/api/github/analyze")
@router.post("/api/gitee-github/analyze", deprecated=True)
async def analyze_github(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Collect global GitHub and cached Gitee evidence for emails."""
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    emails = _parse_email_list(request_body.get("emails"))
    fetch_collaboration = bool(request_body.get("fetch_collaboration", True))
    gitee_repositories = _iter_cached_gitee_repositories()

    github_commit_limit = request_body.get("max_github_commits_per_role", GITHUB_SEARCH_COMMITS_PER_ROLE)
    github_evidence_limit = request_body.get("max_github_evidence_per_query", GITHUB_SEARCH_EVIDENCE_PER_QUERY)
    try:
        github_commit_limit = min(GITHUB_MAX_SEARCH_COMMITS_PER_ROLE, max(1, int(github_commit_limit)))
        github_evidence_limit = min(100, max(1, int(github_evidence_limit)))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="GitHub limits must be integers")

    commits_by_email, matched_repos, collaboration_items, warnings = _fetch_global_github_evidence(
        emails,
        max_commits_per_role=github_commit_limit,
        max_evidence_per_query=github_evidence_limit,
    )
    matched_gitee_repo_keys = set()

    for repository in gitee_repositories:
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
            matched = [commit for commit in commits if _matched_roles_for_email(commit, email)]
            if not matched:
                continue

            matched_gitee_repo_keys.add(repo_key)
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
            for commit in serialized:
                commit["source"] = "gitee_local_cache"
            commits_by_email[email].extend(serialized)

    if fetch_collaboration:
        for repo_key in sorted(matched_gitee_repo_keys):
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
        "scope": "global_github_search_plus_cached_gitee",
        "repos_scanned": len(gitee_repositories),
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
            "GitHub commits are searched globally with author-email and committer-email qualifiers.",
            "GitHub issue/PR/review evidence uses GitHub logins resolved from matching commits; email-only accounts with no resolved login may only have commit and commit-associated PR evidence.",
            "Gitee remains limited to repositories already present in the local Oscanner data cache.",
        ],
    }
