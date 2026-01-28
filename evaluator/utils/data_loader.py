"""Data loading utilities for local commit data."""

import json
from pathlib import Path
from typing import List, Dict, Any


def load_commits_from_local(data_dir: Path, limit: int = None) -> List[Dict[str, Any]]:
    """
    Load commits from local extracted data

    Args:
        data_dir: Path to data directory (e.g., data/owner/repo)
        limit: Maximum commits to load (None = all commits)

    Returns:
        List of commit data
    """
    commits_index_path = data_dir / "commits_index.json"

    if not commits_index_path.exists():
        print(f"[Warning] Commits index not found: {commits_index_path}")
        return []

    # Load commits index
    with open(commits_index_path, 'r', encoding='utf-8') as f:
        commits_index = json.load(f)

    # Load detailed commit data
    commits = []
    commits_dir = data_dir / "commits"

    # Apply limit if specified
    commits_to_load = commits_index if limit is None else commits_index[:limit]

    for commit_info in commits_to_load:
        commit_sha = commit_info.get("hash") or commit_info.get("sha")

        if not commit_sha:
            continue

        # Try to load commit JSON
        commit_json_path = commits_dir / f"{commit_sha}.json"

        if commit_json_path.exists():
            try:
                with open(commit_json_path, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    commits.append(commit_data)
            except Exception as e:
                print(f"[Warning] Failed to load {commit_sha}: {e}")

    print(f"[Info] Loaded {len(commits)} commit details")
    return commits
