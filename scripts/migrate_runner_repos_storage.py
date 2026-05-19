#!/usr/bin/env python3
"""Move legacy flat repos_runner checkouts into namespaced storage."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from repos_runner.services.repo_service.paths import (  # noqa: E402
    get_clone_source_dir,
    get_repos_dir,
    parse_repo_url,
)


def _is_namespaced_platform_dir(path: Path) -> bool:
    if path.name not in {"github", "gitee"}:
        return False
    for source_dir in path.glob("*/*/*/source"):
        if source_dir.is_dir():
            return True
    return False


def _origin_url(repo_dir: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def _result(status: str, source: Path, **fields: Any) -> dict[str, Any]:
    return {"status": status, "source": str(source), **fields}


def migrate_repos_dir(repos_dir: Path, *, dry_run: bool = True) -> list[dict[str, Any]]:
    repos_dir = repos_dir.expanduser()
    if not repos_dir.exists():
        return []

    results: list[dict[str, Any]] = []
    for child in sorted(repos_dir.iterdir()):
        if not child.is_dir():
            continue
        if _is_namespaced_platform_dir(child):
            continue
        if not (child / ".git").is_dir():
            results.append(_result("skipped", child, reason="not a git checkout"))
            continue

        try:
            origin_url = _origin_url(child)
            platform, owner, repo = parse_repo_url(origin_url)
        except (subprocess.CalledProcessError, ValueError) as exc:
            reason = str(exc).strip() or exc.__class__.__name__
            results.append(_result("skipped", child, reason=reason))
            continue

        destination = get_clone_source_dir(
            repos_dir,
            platform=platform,
            owner=owner,
            repo=repo,
        )
        if child.resolve() == destination.resolve():
            continue
        if destination.exists():
            results.append(
                _result(
                    "skipped",
                    child,
                    destination=str(destination),
                    reason="destination exists",
                )
            )
            continue

        results.append(_result("dry-run" if dry_run else "moved", child, destination=str(destination)))
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(child), str(destination))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repos-dir",
        type=Path,
        default=get_repos_dir(),
        help="repos_runner storage root. Defaults to OSCANNER_HOME/XDG repos path.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Move directories. Without this flag, only print planned changes.",
    )
    args = parser.parse_args()

    results = migrate_repos_dir(args.repos_dir, dry_run=not args.apply)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    moved = sum(1 for result in results if result["status"] == "moved")
    planned = sum(1 for result in results if result["status"] == "dry-run")
    skipped = sum(1 for result in results if result["status"] == "skipped")
    print(f"summary: moved={moved} planned={planned} skipped={skipped}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
