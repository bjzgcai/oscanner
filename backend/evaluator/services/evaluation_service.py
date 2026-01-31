"""Evaluation orchestration service."""

import json
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import HTTPException

from evaluator.config import get_llm_api_key, DEFAULT_LLM_MODEL
from evaluator.plugin_registry import load_scan_module
from evaluator.utils import is_commit_by_author
from evaluator.services.plugin_service import resolve_plugin_id
from evaluator.services.extraction_service import get_repo_data_dir


def get_or_create_evaluator(
    platform: str,
    owner: str,
    repo: str,
    commits: list,
    use_cache: bool = True,
    plugin_id: str = "",
    model: str = DEFAULT_LLM_MODEL,
    parallel_chunking: bool = True,
    max_parallel_workers: int = 3,
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
        mode="moderate",
        parallel_chunking=parallel_chunking,
        max_parallel_workers=max_parallel_workers,
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
    use_chunking: bool,
    api_key: str,
    aliases: Optional[List[str]] = None,
    evaluator_factory=None,
    parallel_chunking: bool = True,
    max_parallel_workers: int = 3,
) -> Dict[str, Any]:
    """
    Evaluate author incrementally with weighted merge

    Args:
        commits: All commits from repository
        author: Author username to evaluate
        previous_evaluation: Previous evaluation if exists
        data_dir: Path to repository data directory
        model: LLM model to use
        use_chunking: Whether to enable chunked evaluation
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

    if evaluator_factory is None:
        raise HTTPException(status_code=500, detail="Evaluator factory not provided (plugin load failed?)")

    # Case 1: No previous evaluation → evaluate all commits
    if not previous_evaluation:
        print(f"[Incremental] First evaluation: {len(author_commits)} commits")

        evaluator = evaluator_factory()

        # Heartbeat progress logs: LLM evaluation can take a while with no stdout.
        stop_event = threading.Event()
        started_at = time.time()

        def _heartbeat():
            while not stop_event.wait(15):
                elapsed = int(time.time() - started_at)
                print(f"[LLM] Evaluating... elapsed={elapsed}s (author={author}, commits={len(author_commits)}, chunking={use_chunking})")

        hb = threading.Thread(target=_heartbeat, daemon=True)
        hb.start()

        try:
            print(f"[LLM] Starting evaluation (author={author}, commits={len(author_commits)}, chunking={use_chunking})")
            evaluation = evaluator.evaluate_engineer(
                commits=author_commits,
                username=author,
                max_commits=150,
                load_files=True,
                use_chunking=use_chunking
            )
        except Exception as e:
            stop_event.set()
            raise HTTPException(status_code=502, detail=f"LLM evaluation failed: {str(e)}")
        finally:
            stop_event.set()
            elapsed = int(time.time() - started_at)
            print(f"[LLM] Evaluation finished in {elapsed}s (author={author})")

        evaluation["last_commit_sha"] = author_commits[0].get("sha") or author_commits[0].get("hash")
        evaluation["total_commits_evaluated"] = len(author_commits) if len(author_commits) <= 150 else 150
        evaluation["new_commits_count"] = evaluation["total_commits_evaluated"]
        evaluation["evaluated_at"] = datetime.now().isoformat()
        evaluation["incremental"] = False

        return evaluation

    # Case 2: Find new commits since last evaluation
    last_sha = previous_evaluation.get("last_commit_sha")

    if not last_sha:
        # Previous evaluation has no SHA, re-evaluate all
        print(f"[Incremental] No last SHA found, re-evaluating all commits")
        previous_evaluation = None
        return evaluate_author_incremental(commits, author, None, data_dir, model, use_chunking, api_key)

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

    # Evaluate new commits only
    evaluator = evaluator_factory()

    # Heartbeat progress logs for incremental run
    stop_event = threading.Event()
    started_at = time.time()

    def _heartbeat():
        while not stop_event.wait(15):
            elapsed = int(time.time() - started_at)
            print(f"[LLM] Evaluating incremental... elapsed={elapsed}s (author={author}, new_commits={len(new_commits)}, chunking={use_chunking})")

    hb = threading.Thread(target=_heartbeat, daemon=True)
    hb.start()

    try:
        print(f"[LLM] Starting incremental evaluation (author={author}, new_commits={len(new_commits)}, chunking={use_chunking})")
        new_evaluation = evaluator.evaluate_engineer(
            commits=new_commits,
            username=author,
            max_commits=len(new_commits),
            load_files=True,
            use_chunking=use_chunking
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

    return {
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


def get_empty_evaluation(username: str) -> Dict[str, Any]:
    """Return empty evaluation for author with no commits"""
    return {
        "username": username,
        "total_commits_evaluated": 0,
        "new_commits_count": 0,
        "scores": {
            "ai_fullstack": 0,
            "ai_architecture": 0,
            "cloud_native": 0,
            "open_source": 0,
            "intelligent_dev": 0,
            "leadership": 0,
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
