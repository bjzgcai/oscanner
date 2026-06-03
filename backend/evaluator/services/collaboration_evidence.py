"""Fetch and cache repository collaboration evidence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx

from evaluator.config import get_gitee_token, get_github_token


COLLABORATION_EVIDENCE_SOURCES = {
    "commit_diffs",
    "pr_discussions",
    "review_comments",
    "issue_triage",
    "approvals",
    "maintainer_decisions",
}
DEFAULT_EVIDENCE_SOURCES = ["commit_diffs"]
CACHE_FILENAME = "collaboration_evidence.json"
DEFAULT_CACHE_TTL_HOURS = 24


def normalize_evidence_sources(value: Any) -> List[str]:
    if value is None:
        return list(DEFAULT_EVIDENCE_SOURCES)
    if isinstance(value, str):
        raw_items = [item.strip() for item in value.split(",")]
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, dict)):
        raw_items = [str(item).strip() for item in value]
    else:
        raise ValueError("evidence_sources must be a list or comma-separated string")

    normalized: List[str] = []
    seen = set()

    for source in DEFAULT_EVIDENCE_SOURCES:
        seen.add(source)
        normalized.append(source)

    for item in raw_items:
        if not item:
            continue
        if item not in COLLABORATION_EVIDENCE_SOURCES:
            raise ValueError(f"Unsupported evidence source: {item}")
        if item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized or list(DEFAULT_EVIDENCE_SOURCES)


def fetch_collaboration_evidence(
    *,
    platform: str,
    owner: str,
    repo: str,
    data_dir: Path | str,
    evidence_sources: Any = None,
    cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
) -> Dict[str, Any]:
    sources = normalize_evidence_sources(evidence_sources)
    api_sources = [source for source in sources if source != "commit_diffs"]
    data_path = Path(data_dir)
    cache_path = data_path / CACHE_FILENAME

    cached = _read_cache(cache_path)
    if _cache_covers(cached, platform, owner, repo, api_sources, cache_ttl_hours):
        cached = dict(cached or {})
        cached["requested_sources"] = sources
        cached["items"] = _filter_items_by_sources(cached.get("items"), api_sources)
        cached["cache"] = {"hit": True, "path": str(cache_path)}
        return cached

    if not api_sources:
        return {
            "platform": platform,
            "owner": owner,
            "repo": repo,
            "requested_sources": sources,
            "fetched_at": _utc_now_iso(),
            "items": [],
            "cache": {"hit": False, "skipped": True, "path": str(cache_path)},
        }

    fetched = _fetch_platform_evidence(
        platform=platform,
        owner=owner,
        repo=repo,
        evidence_sources=api_sources,
    )
    fetched = {
        **fetched,
        "platform": platform,
        "owner": owner,
        "repo": repo,
        "requested_sources": sources,
        "fetched_at": _utc_now_iso(),
        "cache": {"hit": False, "path": str(cache_path)},
    }
    _write_cache(cache_path, fetched)
    return fetched


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _cache_covers(
    cached: Optional[Dict[str, Any]],
    platform: str,
    owner: str,
    repo: str,
    api_sources: List[str],
    ttl_hours: int,
) -> bool:
    if not cached:
        return False
    if cached.get("platform") != platform or cached.get("owner") != owner or cached.get("repo") != repo:
        return False
    if not set(api_sources).issubset(set(cached.get("requested_sources") or [])):
        return False
    fetched_at = _parse_datetime(cached.get("fetched_at"))
    if fetched_at is None:
        return False
    return datetime.now(timezone.utc) - fetched_at <= timedelta(hours=max(1, ttl_hours))


def _read_cache(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _write_cache(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _filter_items_by_sources(items: Any, sources: List[str]) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    source_set = set(sources)
    return [
        item
        for item in items
        if isinstance(item, dict) and item.get("source") in source_set
    ]


def _fetch_platform_evidence(
    *,
    platform: str,
    owner: str,
    repo: str,
    evidence_sources: List[str],
) -> Dict[str, Any]:
    try:
        if platform == "github":
            return _fetch_github_evidence(owner, repo, evidence_sources)
        if platform == "gitee":
            return _fetch_gitee_evidence(owner, repo, evidence_sources)
        return {"items": [], "warnings": [f"Unsupported platform for collaboration evidence: {platform}"]}
    except Exception as exc:
        return {"items": [], "warnings": [f"Failed to fetch collaboration evidence: {exc}"]}


def _fetch_github_evidence(owner: str, repo: str, sources: List[str]) -> Dict[str, Any]:
    token = get_github_token()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    items: List[Dict[str, Any]] = []
    warnings: List[str] = []

    with httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        pulls = _get_json_list(
            client,
            f"{base_url}/pulls",
            headers=headers,
            params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 20},
            warnings=warnings,
        )
        for pull in pulls[:20]:
            if not isinstance(pull, dict):
                continue
            number = pull.get("number")
            title = str(pull.get("title") or "").strip()
            pr_label = f"PR #{number}: {title}" if number else f"PR: {title}"
            pr_url = pull.get("html_url")

            issue_comments: List[Dict[str, Any]] = []
            if "pr_discussions" in sources and number:
                issue_comments = _get_json_list(client, f"{base_url}/issues/{number}/comments", headers=headers, warnings=warnings)
                if issue_comments:
                    items.append(_item("pr_discussions", pr_label, f"{len(issue_comments)} discussion comments", pr_url, pull.get("updated_at")))

            reviews: List[Dict[str, Any]] = []
            if number and ({"review_comments", "approvals"} & set(sources)):
                reviews = _get_json_list(client, f"{base_url}/pulls/{number}/reviews", headers=headers, warnings=warnings)

            if "review_comments" in sources and number:
                review_comments = _get_json_list(client, f"{base_url}/pulls/{number}/comments", headers=headers, warnings=warnings)
                review_count = len(review_comments) + sum(1 for review in reviews if str(review.get("body") or "").strip())
                if review_count:
                    items.append(_item("review_comments", f"{pr_label} review discussion", f"{review_count} review comments", pr_url, pull.get("updated_at")))

            if "approvals" in sources:
                approvals = [review for review in reviews if str(review.get("state") or "").upper() == "APPROVED"]
                if approvals:
                    items.append(_item("approvals", f"{pr_label} approved", f"{len(approvals)} approval reviews", pr_url, pull.get("updated_at")))

            if "maintainer_decisions" in sources and (pull.get("merged_at") or pull.get("state") == "closed"):
                decision = "merged" if pull.get("merged_at") else "closed"
                items.append(_item("maintainer_decisions", f"{pr_label} {decision}", f"maintainer decision: {decision}", pr_url, pull.get("updated_at")))

        if "issue_triage" in sources:
            issues = _get_json_list(
                client,
                f"{base_url}/issues",
                headers=headers,
                params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 30},
                warnings=warnings,
            )
            for issue in issues[:30]:
                if not isinstance(issue, dict) or issue.get("pull_request"):
                    continue
                labels = [label.get("name") for label in issue.get("labels") or [] if isinstance(label, dict)]
                assignees = issue.get("assignees") or []
                if labels or assignees or issue.get("state") == "closed":
                    detail_parts = []
                    if labels:
                        detail_parts.append(f"labels: {', '.join(str(label) for label in labels[:4])}")
                    if assignees:
                        detail_parts.append(f"{len(assignees)} assignees")
                    if issue.get("state") == "closed":
                        detail_parts.append("closed")
                    items.append(_item("issue_triage", f"Issue #{issue.get('number')}: {issue.get('title')}", "; ".join(detail_parts), issue.get("html_url"), issue.get("updated_at")))

    return {"items": items[:100], "warnings": warnings}


def _fetch_gitee_evidence(owner: str, repo: str, sources: List[str]) -> Dict[str, Any]:
    token = get_gitee_token()
    base_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}"
    base_params = {"access_token": token} if token else {}
    items: List[Dict[str, Any]] = []
    warnings: List[str] = []

    with httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        pulls = _get_json_list(
            client,
            f"{base_url}/pulls",
            params={**base_params, "state": "all", "per_page": 20},
            warnings=warnings,
        )
        for pull in pulls[:20]:
            if not isinstance(pull, dict):
                continue
            number = pull.get("number") or pull.get("id")
            title = str(pull.get("title") or "").strip()
            label = f"PR #{number}: {title}" if number else f"PR: {title}"
            url = pull.get("html_url") or pull.get("url")
            comments_count = int(pull.get("comments") or pull.get("comments_count") or 0)
            if "pr_discussions" in sources and comments_count:
                items.append(_item("pr_discussions", label, f"{comments_count} discussion comments", url, pull.get("updated_at")))
            if "approvals" in sources and (pull.get("testers") or pull.get("assignees")):
                items.append(_item("approvals", f"{label} reviewed", "visible reviewer/tester assignment", url, pull.get("updated_at")))
            if "review_comments" in sources and number:
                review_comments = _get_json_list(
                    client,
                    f"{base_url}/pulls/{number}/comments",
                    params={**base_params, "per_page": 100},
                    warnings=warnings,
                )
                if review_comments:
                    items.append(_item("review_comments", f"{label} review discussion", f"{len(review_comments)} review comments", url, pull.get("updated_at")))
            if "maintainer_decisions" in sources and (pull.get("merged_at") or pull.get("state") in {"merged", "closed"}):
                decision = "merged" if pull.get("merged_at") or pull.get("state") == "merged" else "closed"
                items.append(_item("maintainer_decisions", f"{label} {decision}", f"maintainer decision: {decision}", url, pull.get("updated_at")))

        if "issue_triage" in sources:
            issues = _get_json_list(
                client,
                f"{base_url}/issues",
                params={**base_params, "state": "all", "per_page": 30},
                warnings=warnings,
            )
            for issue in issues[:30]:
                if not isinstance(issue, dict):
                    continue
                labels = [label.get("name") for label in issue.get("labels") or [] if isinstance(label, dict)]
                assignee = issue.get("assignee")
                if labels or assignee or issue.get("state") in {"closed", "done"}:
                    detail = "; ".join(
                        part for part in [
                            f"labels: {', '.join(str(label) for label in labels[:4])}" if labels else "",
                            "assigned" if assignee else "",
                            str(issue.get("state") or ""),
                        ]
                        if part
                    )
                    items.append(_item("issue_triage", f"Issue #{issue.get('number') or issue.get('id')}: {issue.get('title')}", detail, issue.get("html_url") or issue.get("url"), issue.get("updated_at")))

    return {"items": items[:100], "warnings": warnings}


def _get_json_list(
    client: httpx.Client,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    warnings: List[str],
) -> List[Dict[str, Any]]:
    try:
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []
    except Exception as exc:
        warnings.append(f"{url}: {exc}")
        return []


def _item(source: str, label: Any, detail: Any, url: Any = None, updated_at: Any = None) -> Dict[str, Any]:
    item = {
        "source": source,
        "label": str(label or "").strip(),
        "detail": str(detail or "").strip(),
    }
    if url:
        item["url"] = str(url)
    if updated_at:
        item["updated_at"] = str(updated_at)
    return item
