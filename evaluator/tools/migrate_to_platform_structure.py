#!/usr/bin/env python3
"""
Migrate existing repository data to new platform-aware directory structure

OLD STRUCTURE:
  evaluator/data/{owner}/{repo}/
  evaluator/evaluations/cache/{owner}/

NEW STRUCTURE:
  evaluator/data/{platform}/{owner}/{repo}/
  evaluator/evaluations/{platform}/{owner}/{repo}/

This script:
1. Scans existing data directories
2. Detects platform from repo_info.json
3. Copies data to new platform-specific structure
4. Migrates evaluation cache
5. Creates backup and provides dry-run mode
"""

import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List


def detect_platform(repo_info_path: Path) -> str:
    """
    Detect platform from repo_info.json

    Args:
        repo_info_path: Path to repo_info.json

    Returns:
        Platform name (github, gitee, gitlab) or "github" as default
    """
    if not repo_info_path.exists():
        print(f"    ⚠ repo_info.json not found, defaulting to 'github'")
        return "github"

    try:
        with open(repo_info_path, 'r', encoding='utf-8') as f:
            repo_info = json.load(f)

        # Check if platform is already set
        if "platform" in repo_info:
            return repo_info["platform"]

        # Detect from URL fields
        for url_field in ["html_url", "url", "clone_url", "git_url"]:
            url = repo_info.get(url_field, "")
            if "gitee.com" in url or "z.gitee.cn" in url:
                return "gitee"
            elif "gitlab.com" in url:
                return "gitlab"
            elif "github.com" in url:
                return "github"

        # Default to github
        print(f"    ⚠ Could not detect platform from URLs, defaulting to 'github'")
        return "github"

    except Exception as e:
        print(f"    ⚠ Error reading repo_info.json: {e}, defaulting to 'github'")
        return "github"


def copy_directory(src: Path, dst: Path, dry_run: bool = False) -> bool:
    """
    Copy directory recursively

    Args:
        src: Source directory
        dst: Destination directory
        dry_run: If True, only print what would be done

    Returns:
        True if successful
    """
    if dry_run:
        print(f"    [DRY RUN] Would copy: {src} -> {dst}")
        return True

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return True
    except Exception as e:
        print(f"    ✗ Error copying directory: {e}")
        return False


def migrate_repo_data(
    old_data_dir: Path,
    new_data_root: Path,
    owner: str,
    repo: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Migrate a single repository's data

    Args:
        old_data_dir: Old data directory (data/{owner}/{repo})
        new_data_root: New data root (data/)
        owner: Repository owner
        repo: Repository name
        dry_run: If True, only print what would be done

    Returns:
        Migration result dictionary
    """
    result = {
        "owner": owner,
        "repo": repo,
        "platform": "unknown",
        "status": "failed",
        "message": ""
    }

    # Detect platform
    repo_info_path = old_data_dir / "repo_info.json"
    platform = detect_platform(repo_info_path)
    result["platform"] = platform

    # New directory path
    new_data_dir = new_data_root / platform / owner / repo

    # Check if already migrated
    if new_data_dir.exists() and not dry_run:
        result["status"] = "skipped"
        result["message"] = "Already exists in new location"
        return result

    # Copy repository data
    print(f"  Migrating {owner}/{repo} to {platform}/{owner}/{repo}...")
    success = copy_directory(old_data_dir, new_data_dir, dry_run)

    if success:
        result["status"] = "migrated"
        result["message"] = f"Copied to {new_data_dir}"
    else:
        result["status"] = "failed"
        result["message"] = "Failed to copy data"

    return result


def migrate_evaluations(
    old_eval_root: Path,
    new_eval_root: Path,
    repo_platforms: Dict[str, str],  # {owner/repo: platform}
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """
    Migrate evaluation cache from old to new structure

    OLD: evaluations/cache/{owner}/{author}.json
    NEW: evaluations/{platform}/{owner}/{repo}/{author}.json

    Args:
        old_eval_root: Old evaluation root (evaluations/)
        new_eval_root: New evaluation root (evaluations/)
        repo_platforms: Mapping of owner/repo to platform
        dry_run: If True, only print what would be done

    Returns:
        List of migration results
    """
    results = []
    old_cache_dir = old_eval_root / "cache"

    if not old_cache_dir.exists():
        print("  ⚠ No evaluation cache directory found")
        return results

    print("\nMigrating evaluation cache...")

    for owner_dir in old_cache_dir.iterdir():
        if not owner_dir.is_dir():
            continue

        owner = owner_dir.name

        for eval_file in owner_dir.glob("*.json"):
            author = eval_file.stem

            # Try to determine which repo this evaluation belongs to
            # This is a limitation: old structure doesn't include repo in path
            # We'll need to check the evaluation file content or make assumptions

            try:
                with open(eval_file, 'r', encoding='utf-8') as f:
                    eval_data = json.load(f)

                # Try to infer repo from evaluation data
                # This might not always work, so we log warnings
                print(f"  ⚠ Evaluation for {owner}/{author}: Cannot determine repo from old structure")
                print(f"    Old path: {eval_file}")
                print(f"    Suggestion: Manual migration may be needed")

                results.append({
                    "owner": owner,
                    "author": author,
                    "status": "needs_manual_migration",
                    "old_path": str(eval_file)
                })

            except Exception as e:
                print(f"  ✗ Error reading evaluation file {eval_file}: {e}")
                results.append({
                    "owner": owner,
                    "author": author,
                    "status": "error",
                    "message": str(e)
                })

    return results


def create_backup(data_dir: Path, backup_dir: Path) -> bool:
    """
    Create backup of data directory

    Args:
        data_dir: Data directory to backup
        backup_dir: Backup destination

    Returns:
        True if successful
    """
    try:
        print(f"\nCreating backup at {backup_dir}...")
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Backup data
        if (data_dir / "data").exists():
            shutil.copytree(data_dir / "data", backup_dir / "data", dirs_exist_ok=True)
            print(f"  ✓ Backed up data/")

        # Backup evaluations
        if (data_dir / "evaluations").exists():
            shutil.copytree(data_dir / "evaluations", backup_dir / "evaluations", dirs_exist_ok=True)
            print(f"  ✓ Backed up evaluations/")

        return True
    except Exception as e:
        print(f"  ✗ Backup failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Migrate to platform-aware directory structure')
    parser.add_argument('--data-dir', help='Base data directory (default: auto-detect)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup creation (not recommended)')
    args = parser.parse_args()

    # Determine data directory
    if args.data_dir:
        data_root = Path(args.data_dir).expanduser()
    else:
        # Try to detect
        possible_paths = [
            Path.home() / ".local/share/oscanner",
            Path("evaluator").parent if Path("evaluator").exists() else None,
            Path.cwd()
        ]
        data_root = None
        for path in possible_paths:
            if path and (path / "data").exists():
                data_root = path
                break

        if not data_root:
            print("✗ Could not find data directory. Use --data-dir to specify.")
            return

    data_dir = data_root / "data"
    eval_dir = data_root / "evaluations"

    print("="*70)
    print("Platform-Aware Directory Structure Migration")
    print("="*70)
    print(f"Data directory: {data_dir}")
    print(f"Evaluation directory: {eval_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("="*70)

    if not data_dir.exists():
        print("\n✗ Data directory not found")
        return

    # Create backup (unless in dry-run or --no-backup)
    if not args.dry_run and not args.no_backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = data_root / f"backup_{timestamp}"
        if not create_backup(data_root, backup_dir):
            print("\n✗ Backup failed. Aborting migration for safety.")
            return
        print(f"\n✓ Backup created at {backup_dir}")

    # Scan old data structure
    print("\nScanning existing repositories...")
    old_repos = []

    for owner_dir in data_dir.iterdir():
        if not owner_dir.is_dir():
            continue
        if owner_dir.name in ["github", "gitee", "gitlab"]:
            # Already migrated directory
            continue

        owner = owner_dir.name

        for repo_dir in owner_dir.iterdir():
            if not repo_dir.is_dir():
                continue

            repo = repo_dir.name
            old_repos.append((owner, repo, repo_dir))

    if not old_repos:
        print("  No repositories found to migrate (may already be migrated)")
        return

    print(f"  Found {len(old_repos)} repositories to migrate\n")

    # Migrate repositories
    results = []
    repo_platforms = {}  # Track owner/repo -> platform for evaluation migration

    for owner, repo, old_dir in old_repos:
        result = migrate_repo_data(old_dir, data_dir, owner, repo, args.dry_run)
        results.append(result)

        if result["status"] == "migrated" or result["status"] == "skipped":
            repo_platforms[f"{owner}/{repo}"] = result["platform"]

    # Migrate evaluations
    eval_results = migrate_evaluations(eval_dir, eval_dir, repo_platforms, args.dry_run)

    # Summary
    print("\n" + "="*70)
    print("Migration Summary")
    print("="*70)

    migrated = sum(1 for r in results if r["status"] == "migrated")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "failed")

    print(f"Repositories:")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")

    if eval_results:
        needs_manual = sum(1 for r in eval_results if r["status"] == "needs_manual_migration")
        print(f"\nEvaluations:")
        print(f"  Needs manual migration: {needs_manual}")

    # Platform breakdown
    platform_counts = {}
    for result in results:
        if result["status"] in ["migrated", "skipped"]:
            platform = result["platform"]
            platform_counts[platform] = platform_counts.get(platform, 0) + 1

    if platform_counts:
        print(f"\nBy platform:")
        for platform, count in sorted(platform_counts.items()):
            print(f"  {platform}: {count} repositories")

    if args.dry_run:
        print("\n✓ Dry run complete. Use without --dry-run to perform actual migration.")
    else:
        print("\n✓ Migration complete!")
        print("\nNext steps:")
        print("  1. Verify the new structure in data/{platform}/{owner}/{repo}/")
        print("  2. Test the application with migrated data")
        print("  3. If everything works, you can remove old directories:")
        print(f"     - Old owner directories in {data_dir}/")
        print(f"     - Old cache directory: {eval_dir}/cache/")
        print("\nNote: Evaluation cache migration needs manual attention.")
        print("  Old evaluations were stored by owner only, new structure requires repo.")


if __name__ == "__main__":
    main()
