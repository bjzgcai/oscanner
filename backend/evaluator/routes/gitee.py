"""Gitee profile repository aggregation and evaluation routes."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from evaluator.config import DEFAULT_LLM_MODEL, get_gitee_token, get_llm_api_key
from evaluator.paths import get_data_dir, get_platform_data_dir
from evaluator.plugin_registry import PluginLoadError, load_scan_module
from evaluator.services import resolve_plugin_id
from evaluator.services.collaboration_evidence import fetch_collaboration_evidence
from evaluator.services.evaluation_service import build_evidence_links
from evaluator.services.extraction_service import extract_gitee_data, sync_gitee_data_incremental
from evaluator.utils import (
    get_author_from_commit,
    get_emails_from_commit,
    is_commit_by_author,
    is_valid_email_identity,
    load_commits_from_local,
    normalize_email_identity,
)


router = APIRouter()

GITEE_API_BASE = "https://gitee.com/api/v5"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
DEFAULT_COMMIT_LIMIT = 10
MAX_COMMIT_LIMIT = 100
DEFAULT_SYNC_COMMITS_PER_REPO = 100
MAX_PROFILE_REPOS = 200
DEFAULT_EVIDENCE_SOURCES = [
    "commit_diffs",
    "pr_discussions",
    "review_comments",
    "issue_triage",
    "approvals",
    "maintainer_decisions",
]


def _wants_sse(request: Optional[Request]) -> bool:
    accept = request.headers.get("accept", "").lower() if request is not None else ""
    return "text/event-stream" in accept


def _format_sse_event(event: str, data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _parse_username(value: Any) -> str:
    username = str(value or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if not USERNAME_RE.fullmatch(username):
        raise HTTPException(status_code=400, detail="Invalid Gitee username")
    return username


def _parse_commit_limit(value: Any) -> int:
    try:
        return min(MAX_COMMIT_LIMIT, max(1, int(value if value is not None else DEFAULT_COMMIT_LIMIT)))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="commit_limit must be an integer")


def _parse_optional_email_list(value: Any) -> List[str]:
    if value is None:
        return []
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
    return emails


def _repo_parts_from_gitee_url(repo_url: str) -> tuple[str, str]:
    raw = str(repo_url or "").strip()
    if not raw:
        raise ValueError("repo_url is required")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    parsed = urlsplit(raw)
    if parsed.netloc.lower() not in {"gitee.com", "www.gitee.com"}:
        raise ValueError(f"Expected Gitee repository URL: {repo_url}")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError(f"Expected Gitee repository URL: {repo_url}")
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not USERNAME_RE.fullmatch(owner) or not USERNAME_RE.fullmatch(repo):
        raise ValueError(f"Invalid Gitee repository path: {repo_url}")
    return owner, repo


def _commit_sha(commit: Dict[str, Any]) -> str:
    return str(commit.get("sha") or commit.get("hash") or "").strip()


def _commit_message(commit: Dict[str, Any]) -> str:
    nested = commit.get("commit") if isinstance(commit.get("commit"), dict) else {}
    return str(nested.get("message") or commit.get("message") or "").strip()


def _commit_date(commit: Dict[str, Any]) -> str:
    nested = commit.get("commit") if isinstance(commit.get("commit"), dict) else {}
    author = nested.get("author") if isinstance(nested.get("author"), dict) else {}
    committer = nested.get("committer") if isinstance(nested.get("committer"), dict) else {}
    return str(
        author.get("date")
        or committer.get("date")
        or commit.get("date")
        or commit.get("created_at")
        or commit.get("committed_date")
        or ""
    )


def _sort_key(item: Dict[str, Any]) -> datetime:
    value = str(item.get("date") or item.get("updated_at") or "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _identity_value(commit: Dict[str, Any], role: str, key: str) -> str:
    top = commit.get(role) if isinstance(commit.get(role), dict) else {}
    nested = commit.get("commit") if isinstance(commit.get("commit"), dict) else {}
    nested_identity = nested.get(role) if isinstance(nested.get(role), dict) else {}
    return str(nested_identity.get(key) or top.get(key) or "").strip()


def _matched_roles_for_email(commit: Dict[str, Any], email: str) -> List[Dict[str, str]]:
    normalized = normalize_email_identity(email)
    roles: List[Dict[str, str]] = []
    if not normalized:
        return roles
    for role in ("author", "committer"):
        role_email = normalize_email_identity(_identity_value(commit, role, "email"))
        if role_email == normalized:
            roles.append({
                "role": role,
                "email": role_email,
                "name": _identity_value(commit, role, "name"),
                "date": _identity_value(commit, role, "date"),
            })
    return roles


def _commit_stats(commit: Dict[str, Any]) -> Dict[str, int]:
    stats = commit.get("stats") if isinstance(commit.get("stats"), dict) else {}
    return {
        "additions": int(stats.get("additions") or 0),
        "deletions": int(stats.get("deletions") or 0),
        "total": int(stats.get("total") or stats.get("changes") or 0),
        "files_changed": len(commit.get("files") or []),
    }


def _commit_url(owner: str, repo: str, sha: str, commit: Dict[str, Any]) -> str:
    existing = str(commit.get("html_url") or commit.get("url") or "").strip()
    if existing:
        return existing
    return f"https://gitee.com/{quote(owner, safe='')}/{quote(repo, safe='')}/commit/{quote(sha, safe='')}"


def _dedupe_commits(commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for commit in commits:
        key = (commit.get("platform"), commit.get("repo_full_name"), commit.get("sha"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(commit)
    return deduped


def _serialize_commit(
    commit: Dict[str, Any],
    *,
    owner: str,
    repo: str,
    username: str,
    matched_email: str = "",
) -> Dict[str, Any]:
    sha = _commit_sha(commit)
    message = _commit_message(commit)
    author = {
        "name": _identity_value(commit, "author", "name"),
        "email": _identity_value(commit, "author", "email"),
        "date": _identity_value(commit, "author", "date"),
        "login": _identity_value(commit, "author", "login"),
    }
    committer = {
        "name": _identity_value(commit, "committer", "name"),
        "email": _identity_value(commit, "committer", "email"),
        "date": _identity_value(commit, "committer", "date"),
        "login": _identity_value(commit, "committer", "login"),
    }
    return {
        "platform": "gitee",
        "owner": owner,
        "repo": repo,
        "repo_full_name": f"{owner}/{repo}",
        "repo_url": f"https://gitee.com/{owner}/{repo}",
        "sha": sha,
        "short_sha": sha[:8],
        "message": message,
        "title": message.splitlines()[0] if message else "",
        "author": get_author_from_commit(commit) or "",
        "commit": {
            "author": author,
            "committer": committer,
            "message": message,
        },
        "emails": get_emails_from_commit(commit),
        "matched_email": matched_email,
        "matched_identity": username,
        "matched_roles": _matched_roles_for_email(commit, matched_email),
        "date": _commit_date(commit),
        "url": _commit_url(owner, repo, sha, commit),
        "stats": _commit_stats(commit),
        "files": commit.get("files") or [],
    }


def _repo_from_api_item(item: Dict[str, Any], username: str) -> Optional[Dict[str, str]]:
    namespace = item.get("namespace") if isinstance(item.get("namespace"), dict) else {}
    owner_item = item.get("owner") if isinstance(item.get("owner"), dict) else {}
    owner = str(namespace.get("path") or namespace.get("name") or owner_item.get("login") or "").strip()
    repo = str(item.get("path") or item.get("name") or "").strip()
    if not owner:
        owner = username
    if not repo:
        return None
    return {
        "platform": "gitee",
        "owner": owner,
        "repo": repo,
        "repo_full_name": f"{owner}/{repo}",
        "repo_url": str(item.get("html_url") or f"https://gitee.com/{owner}/{repo}"),
    }


def _gitee_params(token: str, **extra: Any) -> Dict[str, Any]:
    return {"access_token": token, **extra}


def _fetch_profile_repositories(username: str, token: str) -> List[Dict[str, str]]:
    repositories: List[Dict[str, str]] = []
    seen = set()
    page = 1

    with httpx.Client(timeout=httpx.Timeout(25.0, connect=5.0)) as client:
        while len(repositories) < MAX_PROFILE_REPOS:
            response = client.get(
                f"{GITEE_API_BASE}/users/{username}/repos",
                params=_gitee_params(token, type="all", page=page, per_page=100),
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Gitee user '{username}' not found")
            try:
                response.raise_for_status()
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Failed to list Gitee repositories: {exc}")

            payload = response.json()
            if not isinstance(payload, list) or not payload:
                break
            for item in payload:
                if not isinstance(item, dict):
                    continue
                repo = _repo_from_api_item(item, username)
                if not repo:
                    continue
                key = repo["repo_full_name"].lower()
                if key in seen:
                    continue
                seen.add(key)
                repositories.append(repo)
                if len(repositories) >= MAX_PROFILE_REPOS:
                    break
            if len(payload) < 100:
                break
            page += 1

    return repositories


def _sync_one_repo(
    repo: Dict[str, str],
    *,
    sync_commits_per_repo: int,
    emails: Optional[List[str]] = None,
) -> Dict[str, Any]:
    owner = repo["owner"]
    name = repo["repo"]
    data_dir = get_platform_data_dir("gitee", owner, name)
    commits_index = data_dir / "commits_index.json"

    if commits_index.exists():
        changed = sync_gitee_data_incremental(owner, name, max_commits=sync_commits_per_repo)
        mode = "incremental"
    else:
        changed = extract_gitee_data(owner, name, max_commits=sync_commits_per_repo)
        mode = "extract"

    collaboration_cache = data_dir / "collaboration_evidence.json"
    if collaboration_cache.exists():
        collaboration_cache.unlink()

    evidence = fetch_collaboration_evidence(
        platform="gitee",
        owner=owner,
        repo=name,
        data_dir=data_dir,
        evidence_sources=DEFAULT_EVIDENCE_SOURCES,
        cache_ttl_hours=1,
    )

    commits = load_commits_from_local(data_dir, limit=None)
    if emails is not None:
        author_commits = []
        for commit in commits:
            for email in emails:
                if not _matched_roles_for_email(commit, email):
                    continue
                author_commits.append(
                    _serialize_commit(
                        commit,
                        owner=owner,
                        repo=name,
                        username=email,
                        matched_email=email,
                    )
                )
    else:
        author_commits = [
            _serialize_commit(commit, owner=owner, repo=name, username=repo.get("username", ""))
            for commit in commits
            if is_commit_by_author(commit, repo.get("username", ""))
        ]
    serialized = author_commits
    serialized.sort(key=_sort_key, reverse=True)

    evidence_items: List[Dict[str, Any]] = []
    for item in evidence.get("items") or []:
        if not isinstance(item, dict):
            continue
        evidence_items.append({
            **item,
            "platform": "gitee",
            "owner": owner,
            "repo": name,
            "repo_full_name": f"{owner}/{name}",
            "repo_url": repo["repo_url"],
        })

    return {
        "repo": repo,
        "data_dir": str(data_dir),
        "changed": bool(changed),
        "mode": mode,
        "commits": serialized,
        "collaboration_evidence": evidence_items,
        "warnings": [str(warning) for warning in evidence.get("warnings") or [] if warning],
    }


def _profile_evidence_links(commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    seen = set()
    for commit in commits:
        owner = str(commit.get("owner") or "")
        repo = str(commit.get("repo") or "")
        sha = str(commit.get("sha") or "")
        if not owner or not repo or not sha:
            continue
        for link in build_evidence_links([commit], platform="gitee", owner=owner, repo=repo):
            key = (link.get("type"), link.get("url"), link.get("sha"), link.get("commit_sha"), link.get("path"))
            if key in seen:
                continue
            seen.add(key)
            links.append(link)
    return links[:500]


def _evaluate_profile_commits(
    *,
    username: str,
    commit_limit: int,
    model: str,
    plugin_id: str,
    language: str,
    meta: Any,
    scan_mod: Any,
    commits: List[Dict[str, Any]],
    collaboration_items: List[Dict[str, Any]],
    scope: str = "gitee_profile",
) -> Dict[str, Any]:
    evaluator = scan_mod.create_commit_evaluator(
        data_dir=str(get_data_dir() / "gitee_profile" / username),
        api_key=get_llm_api_key(),
        model=model,
        language=language,
        collaboration_evidence={
            "requested_sources": DEFAULT_EVIDENCE_SOURCES,
            "items": collaboration_items,
        },
    )
    evaluation = evaluator.evaluate_engineer(
        commits=commits,
        username=username,
        max_commits=commit_limit,
        load_files=False,
    )
    evaluation["username"] = username
    evaluation["plugin"] = plugin_id
    evaluation["scope"] = scope
    if meta:
        evaluation["plugin_version"] = meta.version
    evidence_links = _profile_evidence_links(commits)
    if evidence_links:
        evaluation["evidence_links"] = evidence_links
    return evaluation


async def _build_profile_payload(request_body: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    token = get_gitee_token()
    if not token:
        raise HTTPException(status_code=400, detail="Missing Gitee Token (GITEE_TOKEN). Please configure it before analyzing.")
    if not get_llm_api_key():
        raise HTTPException(
            status_code=500,
            detail="LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init).",
        )

    username = _parse_username(request_body.get("username"))
    commit_limit = _parse_commit_limit(request_body.get("commit_limit"))
    sync_commits_per_repo = min(1000, max(DEFAULT_SYNC_COMMITS_PER_REPO, commit_limit))
    model = str(request_body.get("model") or DEFAULT_LLM_MODEL)
    plugin_id = resolve_plugin_id(str(request_body.get("plugin") or ""))
    language = str(request_body.get("language") or "zh-CN")

    try:
        meta, scan_mod, scan_path = load_scan_module(plugin_id)
    except PluginLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    repositories = await asyncio.to_thread(_fetch_profile_repositories, username, token)
    if not repositories:
        raise HTTPException(status_code=404, detail=f"No repositories found for Gitee user '{username}'")

    sync_results: List[Dict[str, Any]] = []
    warnings: List[str] = []
    all_commits: List[Dict[str, Any]] = []
    collaboration_items: List[Dict[str, Any]] = []

    for repo in repositories:
        repo_with_username = {**repo, "username": username}
        try:
            sync_result = await asyncio.to_thread(
                _sync_one_repo,
                repo_with_username,
                sync_commits_per_repo=sync_commits_per_repo,
            )
        except Exception as exc:
            warnings.append(f"{repo['repo_full_name']}: {exc}")
            sync_results.append({**repo, "success": False, "message": str(exc)})
            continue

        repo_commits = sync_result["commits"]
        all_commits.extend(repo_commits)
        collaboration_items.extend(sync_result["collaboration_evidence"])
        warnings.extend(sync_result["warnings"])
        sync_results.append({
            **repo,
            "success": True,
            "mode": sync_result["mode"],
            "changed": sync_result["changed"],
            "commit_count": len(repo_commits),
            "data_dir": sync_result["data_dir"],
        })

    all_commits = _dedupe_commits(all_commits)
    all_commits.sort(key=_sort_key, reverse=True)
    selected_commits = all_commits[:commit_limit]
    collaboration_items.sort(key=_sort_key, reverse=True)

    if not selected_commits:
        raise HTTPException(status_code=404, detail=f"No Gitee commits found for '{username}' in profile repositories")

    evaluation = await asyncio.to_thread(
        _evaluate_profile_commits,
        username=username,
        commit_limit=commit_limit,
        model=model,
        plugin_id=plugin_id,
        language=language,
        meta=meta,
        scan_mod=scan_mod,
        commits=selected_commits,
        collaboration_items=collaboration_items,
    )

    matched_repos = [
        item for item in sync_results
        if item.get("success") and item.get("commit_count", 0) > 0
    ]
    return {
        "success": True,
        "username": username,
        "scope": "gitee_profile",
        "repos_scanned": len(repositories),
        "matched_repos": matched_repos,
        "summary": {
            "repo_count": len(repositories),
            "matched_repo_count": len(matched_repos),
            "commit_count": len(selected_commits),
            "available_commit_count": len(all_commits),
            "collaboration_evidence_count": len(collaboration_items),
            "commit_limit": commit_limit,
        },
        "commits": selected_commits,
        "collaboration_evidence": collaboration_items,
        "evaluation": evaluation,
        "warnings": warnings,
        "limitations": [
            "Gitee profile mode evaluates repositories returned by /api/v5/users/{username}/repos?type=all.",
            f"Evaluation uses the latest {commit_limit} matching commits sorted by commit author/committer date.",
        ],
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "gitee_profile_evaluation",
            "plugin": plugin_id,
            "scan": str(scan_path),
        },
    }


async def _build_repo_payload(request_body: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    token = get_gitee_token()
    if not token:
        raise HTTPException(status_code=400, detail="Missing Gitee Token (GITEE_TOKEN). Please configure it before analyzing.")
    if not get_llm_api_key():
        raise HTTPException(
            status_code=500,
            detail="LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init).",
        )

    raw_repo_url = (
        request_body.get("repo_url")
        or request_body.get("gitee_repo")
        or request_body.get("repository")
        or request_body.get("username")
    )
    try:
        owner, repo_name = _repo_parts_from_gitee_url(str(raw_repo_url or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    emails = _parse_optional_email_list(request_body.get("emails") or request_body.get("email") or request_body.get("author_emails"))
    commit_limit = _parse_commit_limit(request_body.get("commit_limit"))
    sync_commits_per_repo = min(1000, max(DEFAULT_SYNC_COMMITS_PER_REPO, commit_limit))
    model = str(request_body.get("model") or DEFAULT_LLM_MODEL)
    plugin_id = resolve_plugin_id(str(request_body.get("plugin") or ""))
    language = str(request_body.get("language") or "zh-CN")

    try:
        meta, scan_mod, scan_path = load_scan_module(plugin_id)
    except PluginLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    repo_item = {
        "platform": "gitee",
        "owner": owner,
        "repo": repo_name,
        "repo_full_name": f"{owner}/{repo_name}",
        "repo_url": f"https://gitee.com/{owner}/{repo_name}",
    }
    warnings: List[str] = []
    sync_result = await asyncio.to_thread(
        _sync_one_repo,
        repo_item,
        sync_commits_per_repo=sync_commits_per_repo,
        emails=emails,
    )
    warnings.extend(sync_result["warnings"])

    all_commits = _dedupe_commits(sync_result["commits"])
    all_commits.sort(key=_sort_key, reverse=True)
    selected_commits = all_commits[:commit_limit]
    collaboration_items = sync_result["collaboration_evidence"]
    collaboration_items.sort(key=_sort_key, reverse=True)

    if not selected_commits:
        raise HTTPException(
            status_code=404,
            detail="No Gitee commits matched the supplied emails in this repository",
        )

    identity_label = emails[0] if len(emails) == 1 else "email identities"
    evaluation = await asyncio.to_thread(
        _evaluate_profile_commits,
        username=identity_label,
        commit_limit=commit_limit,
        model=model,
        plugin_id=plugin_id,
        language=language,
        meta=meta,
        scan_mod=scan_mod,
        commits=selected_commits,
        collaboration_items=collaboration_items,
        scope="gitee_repository",
    )

    matched_repos = [{
        **repo_item,
        "success": True,
        "mode": sync_result["mode"],
        "changed": sync_result["changed"],
        "commit_count": len(selected_commits),
        "data_dir": sync_result["data_dir"],
    }]
    return {
        "success": True,
        "username": identity_label,
        "emails": emails,
        "scope": "gitee_repository",
        "repos_scanned": 1,
        "matched_repos": matched_repos,
        "summary": {
            "repo_count": 1,
            "matched_repo_count": 1,
            "commit_count": len(selected_commits),
            "available_commit_count": len(all_commits),
            "collaboration_evidence_count": len(collaboration_items),
            "commit_limit": commit_limit,
        },
        "commits": selected_commits,
        "collaboration_evidence": collaboration_items,
        "evaluation": evaluation,
        "warnings": warnings,
        "limitations": [
            "Gitee repository mode only scans the supplied repository URL.",
            "Commits are matched only by supplied emails against author.email and committer.email.",
        ],
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "gitee_repository_evaluation",
            "plugin": plugin_id,
            "scan": str(scan_path),
        },
    }


def _request_is_repo_mode(request_body: Dict[str, Any]) -> bool:
    if not isinstance(request_body, dict):
        return False
    if request_body.get("repo_url") or request_body.get("gitee_repo") or request_body.get("repository"):
        return True
    raw = str(request_body.get("username") or "").strip()
    if not raw:
        return False
    try:
        return len([part for part in urlsplit(raw if raw.startswith(("http://", "https://")) else f"https://{raw}").path.split("/") if part]) >= 2
    except Exception:
        return False


async def _stream_profile_evaluation(request_body: Dict[str, Any]):
    try:
        is_repo_mode = _request_is_repo_mode(request_body)
        if is_repo_mode:
            raw_repo_url = request_body.get("repo_url") or request_body.get("gitee_repo") or request_body.get("repository") or request_body.get("username")
            owner, repo = _repo_parts_from_gitee_url(str(raw_repo_url or ""))
            username = f"{owner}/{repo}"
        else:
            username = _parse_username(request_body.get("username") if isinstance(request_body, dict) else None)
        commit_limit = _parse_commit_limit(request_body.get("commit_limit") if isinstance(request_body, dict) else None)
        yield _format_sse_event("section", {
            "title": "准备 Gitee 仓库评估" if is_repo_mode else "准备 Gitee 个人仓库评估",
            "status": "running",
            "username": username,
            "commit_limit": commit_limit,
        })
        yield _format_sse_event("section", {
            "title": "同步 Gitee 仓库与协作证据",
            "status": "running",
            "username": username,
        })
        payload = await (_build_repo_payload(request_body) if is_repo_mode else _build_profile_payload(request_body))
        yield _format_sse_event("section", {
            "title": "Gitee 数据同步完成",
            "status": "done",
            "repo_count": payload["summary"]["repo_count"],
            "commit_count": payload["summary"]["commit_count"],
            "collaboration_evidence_count": payload["summary"]["collaboration_evidence_count"],
        })
        yield _format_sse_event("section", {
            "title": "能力评估完成",
            "status": "done",
            "total_commits_analyzed": payload.get("evaluation", {}).get("total_commits_analyzed"),
        })
        yield _format_sse_event("result", payload)
    except HTTPException as exc:
        yield _format_sse_event("error", {"message": exc.detail, "status_code": exc.status_code})
    except Exception as exc:
        yield _format_sse_event("error", {"message": str(exc), "status_code": 500})


@router.post("/api/gitee/profile/evaluate")
async def evaluate_gitee_profile(request_body: Dict[str, Any], request: Request = None) -> Any:
    """Sync and evaluate the latest commits across a Gitee profile's repositories."""
    if _wants_sse(request):
        return StreamingResponse(
            _stream_profile_evaluation(request_body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    if _request_is_repo_mode(request_body):
        return await _build_repo_payload(request_body)
    return await _build_profile_payload(request_body)
