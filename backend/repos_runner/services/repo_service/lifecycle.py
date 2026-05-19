"""
Repository lifecycle management (list, delete).
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from .paths import get_repos_dir, source_dir_from_repo_key, workspace_dir_from_repo_key


def _iter_source_dirs(repos_dir: Path):
    """Yield (repo_key, source_dir, workspace_dir) for namespaced and legacy checkouts."""
    for platform_dir in sorted(repos_dir.iterdir()):
        if not platform_dir.is_dir():
            continue

        if (platform_dir / ".git").exists() or (platform_dir / "TEST_REPORT.md").exists():
            yield platform_dir.name, platform_dir, platform_dir
            continue

        found_namespaced_source = False
        for owner_dir in sorted(platform_dir.iterdir()):
            if not owner_dir.is_dir():
                continue
            for repo_dir in sorted(owner_dir.iterdir()):
                if not repo_dir.is_dir():
                    continue
                for ref_dir in sorted(repo_dir.iterdir()):
                    source_dir = ref_dir / "source"
                    if not source_dir.is_dir():
                        continue
                    found_namespaced_source = True
                    repo_key = "/".join(
                        [
                            platform_dir.name,
                            owner_dir.name,
                            repo_dir.name,
                            ref_dir.name,
                        ]
                    )
                    yield repo_key, source_dir, ref_dir
        if not found_namespaced_source:
            yield platform_dir.name, platform_dir, platform_dir


def list_repos() -> List[Dict[str, Any]]:
    """
    List all cloned repositories with disk usage and last-modified time.

    Returns:
        List of dicts with repo_name, clone_path, size_mb, last_accessed, has_report
    """
    repos_dir = get_repos_dir()
    repos = []

    for repo_key, repo_dir, _workspace_dir in _iter_source_dirs(repos_dir):

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
            "repo_name": repo_key,
            "display_name": repo_dir.parent.parent.name if repo_key.count("/") == 3 else repo_dir.name,
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
    workspace_dir = workspace_dir_from_repo_key(repo_name, repos_dir=repos_dir)
    repo_dir = source_dir_from_repo_key(repo_name, repos_dir=repos_dir)

    if not workspace_dir.exists() and not repo_dir.exists():
        raise FileNotFoundError(f"Repository '{repo_name}' not found")

    # Measure size before deleting
    total_bytes = sum(
        f.stat().st_size for f in workspace_dir.rglob("*") if f.is_file()
    )
    freed_mb = round(total_bytes / (1024 * 1024), 2)

    shutil.rmtree(workspace_dir)

    return {
        "status": "deleted",
        "repo_name": repo_name,
        "freed_mb": freed_mb,
    }
