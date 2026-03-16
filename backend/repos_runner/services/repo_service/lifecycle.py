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

        # Collect all tag-versioned reports, e.g. TEST_REPORT_v1.0.md → tag "v1.0"
        reports = {}
        for f in sorted(repo_dir.glob("TEST_REPORT*.md")):
            name = f.stem  # e.g. "TEST_REPORT_v1.0" or "TEST_REPORT"
            tag_key = name[len("TEST_REPORT_"):] if name.startswith("TEST_REPORT_") else ""
            reports[tag_key or "default"] = f.name

        repos.append({
            "repo_name": repo_dir.name,
            "clone_path": str(repo_dir),
            "size_mb": round(total_bytes / (1024 * 1024), 2),
            "last_accessed": last_accessed,
            "has_overview": any(repo_dir.glob("REPO_OVERVIEW*.md")),
            "has_report": bool(reports),
            "has_test_config": (repo_dir / "test_config.json").exists(),
            "reports": reports,  # {"v1.0": "TEST_REPORT_v1.0.md", "default": "TEST_REPORT.md"}
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
