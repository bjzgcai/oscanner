"""Evaluation orchestration service."""

import json
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from urllib.parse import quote
from fastapi import HTTPException

from evaluator.config import get_llm_api_key, DEFAULT_LLM_MODEL
from evaluator.plugin_registry import load_scan_module
from evaluator.utils import is_commit_by_author
from evaluator.services.plugin_service import resolve_plugin_id
from evaluator.services.extraction_service import get_repo_data_dir


MAX_REPO_EVALUATION_INPUT_TOKENS = 10_000_000
REPO_TOO_BIG_MESSAGE = "the repo is too big exceeding 10M tokens!"
MAX_EVIDENCE_LINKS = 500


def _plugin_filter_identity(author: str, aliases: Optional[List[str]]) -> str:
    identities = [*(aliases or []), author]
    unique: List[str] = []
    seen = set()
    for identity in identities:
        cleaned = str(identity or "").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    return ",".join(unique) if unique else author


def _estimate_text_tokens(text: str) -> int:
    return len(text or "")


def _commit_message(commit: Dict[str, Any]) -> str:
    raw = commit.get("message")
    if raw is None and isinstance(commit.get("commit"), dict):
        raw = commit.get("commit", {}).get("message")
    return str(raw or "")


def _commit_sha(commit: Dict[str, Any]) -> str:
    return str(commit.get("sha") or commit.get("hash") or "").strip()


def _commit_file_path(file_item: Any) -> str:
    if isinstance(file_item, dict):
        return str(file_item.get("filename") or file_item.get("path") or file_item.get("name") or "").strip()
    return str(file_item or "").strip()


def _parent_dir_paths(path: str) -> List[str]:
    parts = [part for part in str(path or "").replace("\\", "/").strip("/").split("/") if part]
    if len(parts) <= 1:
        return []
    return ["/".join(parts[:index]) + "/" for index in range(1, len(parts))]


def _review_base_url(platform: Optional[str], owner: Optional[str], repo: Optional[str]) -> Optional[str]:
    platform_key = str(platform or "").strip().lower()
    host = {"github": "github.com", "gitee": "gitee.com"}.get(platform_key)
    owner_text = str(owner or "").strip().strip("/")
    repo_text = str(repo or "").strip().strip("/")
    if not host or not owner_text or not repo_text:
        return None
    return f"https://{host}/{quote(owner_text, safe='')}/{quote(repo_text, safe='')}"


def _dedupe_evidence_links(links: List[Dict[str, Any]], *, max_links: int = MAX_EVIDENCE_LINKS) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for link in links:
        if not isinstance(link, dict):
            continue
        key = (
            str(link.get("type") or ""),
            str(link.get("url") or ""),
            str(link.get("sha") or ""),
            str(link.get("commit_sha") or ""),
            str(link.get("path") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(link)
        if len(deduped) >= max_links:
            break
    return deduped


def build_evidence_links(
    commits: List[Dict[str, Any]],
    *,
    platform: Optional[str] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    max_links: int = MAX_EVIDENCE_LINKS,
) -> List[Dict[str, Any]]:
    """Build structured review links for evaluated commits and changed files."""
    base_url = _review_base_url(platform, owner, repo)
    if not base_url:
        return []

    links: List[Dict[str, Any]] = []
    for commit in commits:
        sha = _commit_sha(commit)
        if not sha:
            continue
        links.append({
            "type": "commit",
            "label": sha[:8],
            "sha": sha,
            "url": f"{base_url}/commit/{quote(sha, safe='')}",
        })

        for file_item in commit.get("files") or []:
            path = _commit_file_path(file_item).replace("\\", "/").strip("/")
            if not path:
                continue
            links.append({
                "type": "file",
                "label": path,
                "path": path,
                "commit_sha": sha,
                "url": f"{base_url}/blob/{quote(sha, safe='')}/{quote(path, safe='/')}",
            })
            for dir_path in _parent_dir_paths(path):
                links.append({
                    "type": "dir",
                    "label": dir_path,
                    "path": dir_path,
                    "commit_sha": sha,
                    "url": f"{base_url}/tree/{quote(sha, safe='')}/{quote(dir_path.strip('/'), safe='/')}",
                })
            if len(links) >= max_links:
                return _dedupe_evidence_links(links, max_links=max_links)

    return _dedupe_evidence_links(links, max_links=max_links)


def _merge_evidence_links(
    previous_links: Optional[List[Dict[str, Any]]],
    new_links: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return _dedupe_evidence_links([*(previous_links or []), *new_links])


def _repo_snapshot_file_paths(data_dir: Path):
    repo_files_dir = data_dir / "repo_files"
    manifest_path = data_dir / "repo_files_manifest.json"
    if not repo_files_dir.exists() or not repo_files_dir.is_dir() or not manifest_path.exists():
        return

    for abs_path in sorted(repo_files_dir.rglob("*")):
        if abs_path.is_file():
            yield abs_path


def estimate_repo_evaluation_input_tokens(
    *,
    commits: List[Dict[str, Any]],
    data_dir: Path,
    token_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Estimate repo snapshot file and commit-message tokens, stopping after the limit."""
    limit = MAX_REPO_EVALUATION_INPUT_TOKENS if token_limit is None else int(token_limit)
    total = 0

    for commit in commits:
        total += _estimate_text_tokens(_commit_message(commit))
        if total > limit:
            return {"tokens": total, "limit": limit, "exceeded": True}

    for file_path in _repo_snapshot_file_paths(data_dir):
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    total += _estimate_text_tokens(chunk)
                    if total > limit:
                        return {"tokens": total, "limit": limit, "exceeded": True}
        except OSError:
            continue

    return {"tokens": total, "limit": limit, "exceeded": False}


def ensure_repo_evaluation_input_within_limit(
    *,
    commits: List[Dict[str, Any]],
    data_dir: Path,
) -> Dict[str, Any]:
    stats = estimate_repo_evaluation_input_tokens(commits=commits, data_dir=data_dir)
    if stats["exceeded"]:
        raise HTTPException(status_code=413, detail=REPO_TOO_BIG_MESSAGE)
    return stats


def get_or_create_evaluator(
    platform: str,
    owner: str,
    repo: str,
    commits: list,
    plugin_id: str = "",
    model: str = DEFAULT_LLM_MODEL,
):
    """
    Legacy helper (kept for compatibility).

    Persists commit JSONs into the repo data dir, then returns a plugin evaluator instance.
    """
    data_dir = get_repo_data_dir(platform, owner, repo)

    # Create commits_index.json
    commits_index = [{"sha": c.get("sha"), "hash": c.get("sha")} for c in commits]
    with open(data_dir / "commits_index.json", "w", encoding="utf-8") as f:
        json.dump(commits_index, f, indent=2, ensure_ascii=False)

    # Save individual commits
    commits_dir = data_dir / "commits"
    commits_dir.mkdir(exist_ok=True)
    for commit in commits:
        sha = commit.get("sha")
        if sha:
            with open(commits_dir / f"{sha}.json", "w", encoding="utf-8") as f:
                json.dump(commit, f, indent=2, ensure_ascii=False)

    # repo_info.json
    repo_info = {"name": f"{owner}/{repo}", "full_name": f"{owner}/{repo}", "owner": owner, "platform": platform}
    with open(data_dir / "repo_info.json", "w", encoding="utf-8") as f:
        json.dump(repo_info, f, indent=2, ensure_ascii=False)

    pid = resolve_plugin_id(plugin_id)
    meta, scan_mod, scan_path = load_scan_module(pid)
    api_key = get_llm_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM not configured")

    evaluator = scan_mod.create_commit_evaluator(
        data_dir=str(data_dir),
        api_key=api_key,
        model=model,
    )
    print(f"✓ Created evaluator for {owner}/{repo} via plugin={pid} scan={scan_path}")
    _ = meta
    return evaluator


def evaluate_author_incremental(
    commits: List[Dict[str, Any]],
    author: str,
    previous_evaluation: Optional[Dict[str, Any]],
    data_dir: Path,
    model: str,
    api_key: str,
    aliases: Optional[List[str]] = None,
    evaluator_factory=None,
    platform: Optional[str] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate author incrementally with weighted merge

    Args:
        commits: All commits from repository
        author: Author username to evaluate
        previous_evaluation: Previous evaluation if exists
        data_dir: Path to repository data directory
        model: LLM model to use
        api_key: LLM API key
        aliases: Optional list of author name aliases (normalized/lowercase)

    Returns:
        Evaluation result with merged scores
    """
    # Filter commits by author (including aliases)
    if aliases:
        author_commits = [
            c for c in commits
            if any(is_commit_by_author(c, alias) for alias in aliases)
        ]
        print(f"[Incremental] Filtering commits by {len(aliases)} aliases: {aliases}")
    else:
        author_commits = [c for c in commits if is_commit_by_author(c, author)]

    if not author_commits:
        return get_empty_evaluation(author)

    # Case 1: No previous evaluation → evaluate all commits
    if not previous_evaluation:
        print(f"[Incremental] First evaluation: {len(author_commits)} commits")
        ensure_repo_evaluation_input_within_limit(commits=author_commits, data_dir=data_dir)

        if evaluator_factory is None:
            raise HTTPException(status_code=500, detail="Evaluator factory not provided (plugin load failed?)")

        evaluator = evaluator_factory()

        # Heartbeat progress logs: LLM evaluation can take a while with no stdout.
        stop_event = threading.Event()
        started_at = time.time()

        def _heartbeat():
            while not stop_event.wait(15):
                elapsed = int(time.time() - started_at)
                print(f"[LLM] Evaluating... elapsed={elapsed}s (author={author}, commits={len(author_commits)})")

        hb = threading.Thread(target=_heartbeat, daemon=True)
        hb.start()

        try:
            print(f"[LLM] Starting evaluation (author={author}, commits={len(author_commits)})")
            evaluation = evaluator.evaluate_engineer(
                commits=author_commits,
                username=_plugin_filter_identity(author, aliases),
                max_commits=150,
                load_files=True,
            )
        except Exception as e:
            stop_event.set()
            raise HTTPException(status_code=502, detail=f"LLM evaluation failed: {str(e)}")
        finally:
            stop_event.set()
            elapsed = int(time.time() - started_at)
            print(f"[LLM] Evaluation finished in {elapsed}s (author={author})")

        evaluation["username"] = author
        evaluation["last_commit_sha"] = author_commits[0].get("sha") or author_commits[0].get("hash")
        evaluation["total_commits_evaluated"] = len(author_commits) if len(author_commits) <= 150 else 150
        evaluation["new_commits_count"] = evaluation["total_commits_evaluated"]
        evaluation["evaluated_at"] = datetime.now().isoformat()
        evaluation["incremental"] = False
        evidence_links = build_evidence_links(
            author_commits[: evaluation["total_commits_evaluated"]],
            platform=platform,
            owner=owner,
            repo=repo,
        )
        if evidence_links:
            evaluation["evidence_links"] = evidence_links

        return evaluation

    # Case 2: Find new commits since last evaluation
    last_sha = previous_evaluation.get("last_commit_sha")

    if not last_sha:
        # Previous evaluation has no SHA, re-evaluate all
        print(f"[Incremental] No last SHA found, re-evaluating all commits")
        previous_evaluation = None
        return evaluate_author_incremental(
            commits=commits,
            author=author,
            previous_evaluation=None,
            data_dir=data_dir,
            model=model,
            api_key=api_key,
            aliases=aliases,
            evaluator_factory=evaluator_factory,
            platform=platform,
            owner=owner,
            repo=repo,
        )

    # Find new commits
    new_commits = []
    for commit in author_commits:
        commit_sha = commit.get("sha") or commit.get("hash")
        if commit_sha == last_sha:
            break
        new_commits.append(commit)

    if not new_commits:
        print(f"[Incremental] No new commits since last evaluation")
        return previous_evaluation

    print(f"[Incremental] Found {len(new_commits)} new commits, evaluating...")
    ensure_repo_evaluation_input_within_limit(commits=new_commits, data_dir=data_dir)

    if evaluator_factory is None:
        raise HTTPException(status_code=500, detail="Evaluator factory not provided (plugin load failed?)")

    # Evaluate new commits only
    evaluator = evaluator_factory()

    # Heartbeat progress logs for incremental run
    stop_event = threading.Event()
    started_at = time.time()

    def _heartbeat():
        while not stop_event.wait(15):
            elapsed = int(time.time() - started_at)
            print(f"[LLM] Evaluating incremental... elapsed={elapsed}s (author={author}, new_commits={len(new_commits)})")

    hb = threading.Thread(target=_heartbeat, daemon=True)
    hb.start()

    try:
        print(f"[LLM] Starting incremental evaluation (author={author}, new_commits={len(new_commits)})")
        new_evaluation = evaluator.evaluate_engineer(
            commits=new_commits,
            username=_plugin_filter_identity(author, aliases),
            max_commits=len(new_commits),
            load_files=True,
        )
    except Exception as e:
        stop_event.set()
        raise HTTPException(status_code=502, detail=f"LLM evaluation failed: {str(e)}")
    finally:
        stop_event.set()
        elapsed = int(time.time() - started_at)
        print(f"[LLM] Incremental evaluation finished in {elapsed}s (author={author})")

    # Weighted merge of scores
    prev_count = previous_evaluation.get("total_commits_evaluated", 0)
    new_count = len(new_commits)
    total_count = prev_count + new_count

    print(f"[Incremental] Merging scores: {prev_count} previous + {new_count} new = {total_count} total")

    merged_scores = {}
    prev_scores = previous_evaluation.get("scores", {})
    new_scores = new_evaluation.get("scores", {})

    # Merge all keys from both previous and new scores
    all_keys = set(prev_scores.keys()) | set(new_scores.keys())

    for key in all_keys:
        if key == "reasoning":
            # Combine reasoning from both evaluations
            prev_reasoning = prev_scores.get(key, '')
            new_reasoning = new_scores.get(key, '')

            if prev_reasoning and new_reasoning:
                merged_scores[key] = (
                    f"**Recent Activity ({new_count} new commits):**\n{new_reasoning}\n\n"
                    f"---\n\n"
                    f"**Previous Assessment ({prev_count} commits):**\n{prev_reasoning}"
                )
            elif new_reasoning:
                merged_scores[key] = new_reasoning
            elif prev_reasoning:
                merged_scores[key] = prev_reasoning
            else:
                merged_scores[key] = ""
        else:
            # Weighted average for numeric scores
            prev_val = prev_scores.get(key, 0)
            new_val = new_scores.get(key, 0)

            if prev_val and new_val:
                merged_val = (prev_val * prev_count + new_val * new_count) / total_count
                merged_scores[key] = int(merged_val)
            elif new_val:
                merged_scores[key] = int(new_val)
            elif prev_val:
                merged_scores[key] = int(prev_val)
            else:
                merged_scores[key] = 0

    # Merge commit summaries
    prev_summary = previous_evaluation.get("commits_summary", {})
    new_summary = new_evaluation.get("commits_summary", {})

    merged_summary = {
        "total_additions": prev_summary.get("total_additions", 0) + new_summary.get("total_additions", 0),
        "total_deletions": prev_summary.get("total_deletions", 0) + new_summary.get("total_deletions", 0),
        "files_changed": prev_summary.get("files_changed", 0) + new_summary.get("files_changed", 0),
        "languages": list(set(prev_summary.get("languages", []) + new_summary.get("languages", [])))[:10]
    }

    new_evidence_links = build_evidence_links(
        new_commits,
        platform=platform,
        owner=owner,
        repo=repo,
    )

    result = {
        "username": author,
        "total_commits_evaluated": total_count,
        "new_commits_count": new_count,
        "last_commit_sha": author_commits[0].get("sha") or author_commits[0].get("hash"),
        "evaluated_at": datetime.now().isoformat(),
        "scores": merged_scores,
        "commits_summary": merged_summary,
        "mode": "moderate",
        "incremental": True,
        "files_loaded": new_evaluation.get("files_loaded", 0),
        "chunked": new_evaluation.get("chunked", False),
        "chunks_processed": new_evaluation.get("chunks_processed", 0)
    }
    merged_evidence_links = _merge_evidence_links(previous_evaluation.get("evidence_links"), new_evidence_links)
    if merged_evidence_links:
        result["evidence_links"] = merged_evidence_links
    return result


def get_empty_evaluation(username: str) -> Dict[str, Any]:
    """Return empty evaluation for author with no commits"""
    return {
        "username": username,
        "total_commits_evaluated": 0,
        "new_commits_count": 0,
        "scores": {
            "reasoning": "No commits found for this author."
        },
        "commits_summary": {
            "total_additions": 0,
            "total_deletions": 0,
            "files_changed": 0,
            "languages": []
        },
        "mode": "moderate",
        "incremental": False
    }
