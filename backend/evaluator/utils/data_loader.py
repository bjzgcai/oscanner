"""Data loading utilities for local commit data."""

import json
from pathlib import Path
from typing import List, Dict, Any


EXCLUDED_PATH_PARTS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dataset",
    "datasets",
    "dist",
    "dist-packages",
    "env",
    "external",
    "htmlcov",
    "node_modules",
    "site-packages",
    "target",
    "third_party",
    "venv",
    "vendor",
}
EXCLUDED_EXTENSIONS = {
    ".7z",
    ".a",
    ".avi",
    ".bin",
    ".bmp",
    ".bz2",
    ".class",
    ".coverage",
    ".db",
    ".dll",
    ".dmg",
    ".doc",
    ".docx",
    ".dylib",
    ".eot",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".log",
    ".map",
    ".mov",
    ".mp3",
    ".mp4",
    ".o",
    ".ogg",
    ".otf",
    ".pdf",
    ".png",
    ".pyc",
    ".pyd",
    ".pyo",
    ".rar",
    ".sqlite",
    ".sqlite3",
    ".so",
    ".tar",
    ".tgz",
    ".tmp",
    ".ttf",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsx",
    ".zip",
}
EXCLUDED_FILENAMES = {
    ".DS_Store",
    ".env",
    ".env.local",
    ".env.production",
    ".npmrc",
    ".pypirc",
    "Desktop.ini",
    "Thumbs.db",
    "id_rsa",
    "id_rsa.pub",
}


def is_eval_relevant_path(path: str) -> bool:
    """Return True when a repo-relative path can provide useful evaluation evidence."""
    normalized = str(path or "").replace("\\", "/").strip("/")
    if not normalized:
        return False

    parts = normalized.split("/")
    if any(part in EXCLUDED_PATH_PARTS for part in parts):
        return False

    name = parts[-1]
    if name in EXCLUDED_FILENAMES:
        return False

    suffixes = Path(name).suffixes
    if suffixes:
        combined_suffix = "".join(suffixes[-2:]).lower()
        if combined_suffix in {".tar.gz", ".tar.bz2"}:
            return False
        if suffixes[-1].lower() in EXCLUDED_EXTENSIONS:
            return False

    return True


def _commit_file_path(file_item: Any) -> str:
    if isinstance(file_item, dict):
        return str(file_item.get("filename") or file_item.get("path") or "")
    return str(file_item or "")


def _filter_eval_relevant_files(commit_data: Dict[str, Any]) -> Dict[str, Any]:
    files = commit_data.get("files")
    if not isinstance(files, list):
        return commit_data

    filtered_files = [
        file_item
        for file_item in files
        if is_eval_relevant_path(_commit_file_path(file_item))
    ]
    if len(filtered_files) == len(files):
        return commit_data

    commit_data["files"] = filtered_files

    additions = 0
    deletions = 0
    saw_line_stats = False
    for file_item in filtered_files:
        if not isinstance(file_item, dict):
            continue
        if "additions" not in file_item and "deletions" not in file_item:
            continue
        try:
            additions += int(file_item.get("additions") or 0)
            deletions += int(file_item.get("deletions") or 0)
            saw_line_stats = True
        except (TypeError, ValueError):
            continue

    if saw_line_stats or not filtered_files:
        commit_data["stats"] = {
            "additions": additions,
            "deletions": deletions,
            "total": additions + deletions,
        }

    return commit_data


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
                    commits.append(_filter_eval_relevant_files(commit_data))
            except Exception as e:
                print(f"[Warning] Failed to load {commit_sha}: {e}")

    print(f"[Info] Loaded {len(commits)} commit details")
    return commits
