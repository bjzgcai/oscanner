"""
Repository lifecycle management (list, delete).
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from .paths import get_repos_dir


def list_repos() -> List[Dict[str, Any]]:
    """
    List all cloned repositories with disk usage and last-modified time.

    Returns:
        List of dicts with repo_name, clone_path, size_mb, last_accessed, has_report
    """
    repos_dir = get_repos_dir()
    repos = []

    for repo_dir in sorted(repos_dir.iterdir()):
        if not repo_dir.is_dir():
            continue

        # Calculate total directory size
        total_bytes = sum(
            f.stat().st_size
            for f in repo_dir.rglob("*")
            if f.is_file()
        )

        # Get last modification time
        try:
            mtime = repo_dir.stat().st_mtime
            last_accessed = datetime.fromtimestamp(mtime).isoformat()
        except Exception:
            last_accessed = None

        repos.append({
            "repo_name": repo_dir.name,
            "clone_path": str(repo_dir),
            "size_mb": round(total_bytes / (1024 * 1024), 2),
            "last_accessed": last_accessed,
            "has_overview": (repo_dir / "REPO_OVERVIEW.md").exists(),
            "has_report": (repo_dir / "TEST_REPORT.md").exists(),
            "has_test_config": (repo_dir / "test_config.json").exists(),
        })

    return repos


def delete_repo(repo_name: str) -> Dict[str, Any]:
    """
    Delete a cloned repository and all associated files.

    Returns:
        Dict with status and freed_mb
    """
    repos_dir = get_repos_dir()
    repo_dir = repos_dir / repo_name

    if not repo_dir.exists():
        raise FileNotFoundError(f"Repository '{repo_name}' not found")

    # Measure size before deleting
    total_bytes = sum(
        f.stat().st_size for f in repo_dir.rglob("*") if f.is_file()
    )
    freed_mb = round(total_bytes / (1024 * 1024), 2)

    shutil.rmtree(repo_dir)

    return {
        "status": "deleted",
        "repo_name": repo_name,
        "freed_mb": freed_mb,
    }
