#!/usr/bin/env python3
"""
Migrate existing repositories to incremental sync system

This script creates sync_state.json for existing repositories
that have commits_index.json but no sync_state.json
"""

import json
from pathlib import Path
from datetime import datetime


def migrate_repository(repo_path: Path) -> bool:
    """
    Migrate a single repository to incremental sync

    Args:
        repo_path: Path to repository data directory (e.g., data/owner/repo)

    Returns:
        True if migrated, False if skipped or failed
    """
    commits_index_path = repo_path / "commits_index.json"
    sync_state_path = repo_path / "sync_state.json"

    # Skip if no commits_index.json
    if not commits_index_path.exists():
        return False

    # Skip if sync_state.json already exists
    if sync_state_path.exists():
        print(f"  Skipped {repo_path.parent.name}/{repo_path.name} (already migrated)")
        return False

    try:
        # Load commits index
        with open(commits_index_path, 'r', encoding='utf-8') as f:
            commits_index = json.load(f)

        if not commits_index:
            print(f"  Skipped {repo_path.parent.name}/{repo_path.name} (empty commits index)")
            return False

        # Get first commit (most recent)
        first_commit = commits_index[0]
        commit_sha = first_commit.get("sha") or first_commit.get("hash")

        # Create sync_state.json
        sync_state = {
            "last_synced_at": datetime.now().isoformat(),
            "last_commit_sha": commit_sha,
            "last_commit_date": first_commit.get("date", ""),
            "total_commits_fetched": len(commits_index),
            "sync_history": [{
                "synced_at": datetime.now().isoformat(),
                "commits_added": len(commits_index),
                "last_sha": commit_sha,
                "mode": "migration"
            }]
        }

        # Save sync_state.json
        with open(sync_state_path, 'w', encoding='utf-8') as f:
            json.dump(sync_state, f, indent=2, ensure_ascii=False)

        print(f"  ✓ Migrated {repo_path.parent.name}/{repo_path.name} ({len(commits_index)} commits, last: {commit_sha[:8]})")
        return True

    except Exception as e:
        print(f"  ✗ Failed to migrate {repo_path.parent.name}/{repo_path.name}: {e}")
        return False


def main():
    """Migrate all existing repositories"""
    # Try to find data directory
    data_dir = Path.home() / ".local/share/oscanner/data"

    if not data_dir.exists():
        # Try relative path
        data_dir = Path("evaluator/data")

    if not data_dir.exists():
        print("✗ No data directory found")
        print("  Looked in:")
        print(f"    - {Path.home() / '.local/share/oscanner/data'}")
        print("    - evaluator/data")
        return

    print(f"Migrating repositories in {data_dir}...")
    print()

    migrated_count = 0
    skipped_count = 0

    # Iterate through owner directories
    for owner_dir in sorted(data_dir.iterdir()):
        if not owner_dir.is_dir():
            continue

        # Iterate through repo directories
        for repo_dir in sorted(owner_dir.iterdir()):
            if not repo_dir.is_dir():
                continue

            # Attempt migration
            if migrate_repository(repo_dir):
                migrated_count += 1
            else:
                if (repo_dir / "commits_index.json").exists():
                    skipped_count += 1

    print()
    print("="*60)
    print("Migration Summary")
    print("="*60)
    print(f"  Migrated: {migrated_count} repositories")
    print(f"  Skipped: {skipped_count} repositories (already migrated)")
    print()

    if migrated_count > 0:
        print("✓ Migration complete!")
        print()
        print("Next steps:")
        print("  1. Test incremental sync: Evaluate an author to trigger auto-sync")
        print("  2. Monitor sync_state.json files for updates")
        print("  3. Clean up old cache directories if needed")
        print()
    elif skipped_count > 0:
        print("✓ All repositories already migrated")
    else:
        print("No repositories found to migrate")


if __name__ == "__main__":
    main()
