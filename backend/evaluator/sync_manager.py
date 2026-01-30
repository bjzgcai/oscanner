"""
Sync Manager for Incremental Repository Fetch

This module handles incremental synchronization of repository commits.
It compares remote commits with local data and fetches only new commits.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class SyncManager:
    """Manages incremental synchronization of repository commits"""

    def __init__(self, data_dir: Path, platform: str, owner: str, repo: str):
        """
        Initialize SyncManager

        Args:
            data_dir: Path to repository data directory (evaluator/data/{owner}/{repo})
            platform: Platform name (github, gitee)
            owner: Repository owner
            repo: Repository name
        """
        self.data_dir = Path(data_dir)
        self.platform = platform
        self.owner = owner
        self.repo = repo
        self.sync_state_path = self.data_dir / "sync_state.json"
        self.commits_index_path = self.data_dir / "commits_index.json"
        self.commits_dir = self.data_dir / "commits"

    def load_sync_state(self) -> Dict[str, Any]:
        """
        Load sync state from sync_state.json

        Returns:
            Sync state dictionary with last_synced_at, last_commit_sha, etc.
            Returns default state if file doesn't exist.
        """
        if not self.sync_state_path.exists():
            return {
                "last_synced_at": None,
                "last_commit_sha": None,
                "last_commit_date": None,
                "total_commits_fetched": 0,
                "sync_history": []
            }

        try:
            with open(self.sync_state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[SyncManager] Error loading sync_state.json: {e}")
            return {
                "last_synced_at": None,
                "last_commit_sha": None,
                "last_commit_date": None,
                "total_commits_fetched": 0,
                "sync_history": []
            }

    def save_sync_state(self, state: Dict[str, Any]):
        """
        Save sync state to sync_state.json atomically

        Args:
            state: Sync state dictionary to save
        """
        # Ensure directory exists
        self.sync_state_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write using temporary file
        temp_path = self.sync_state_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            temp_path.rename(self.sync_state_path)
            print(f"[SyncManager] Saved sync state to {self.sync_state_path}")
        except IOError as e:
            print(f"[SyncManager] Error saving sync_state.json: {e}")
            if temp_path.exists():
                temp_path.unlink()

    def get_new_commits(self, collector) -> List[Dict[str, Any]]:
        """
        Get new commits from remote that don't exist locally

        Args:
            collector: GitHub or Gitee collector instance

        Returns:
            List of new commit summaries (not detailed data)
        """
        sync_state = self.load_sync_state()

        # Fetch commits from remote
        # Use 'since' parameter if we have a last commit date
        params = {}
        if sync_state.get("last_commit_date"):
            params["since"] = sync_state["last_commit_date"]

        print(f"[SyncManager] Fetching commits from remote (since: {sync_state.get('last_commit_date', 'beginning')})")

        try:
            # Fetch commits list (up to 100)
            remote_commits = collector.fetch_commits_list(
                self.owner,
                self.repo,
                limit=100,
                **params
            )
        except Exception as e:
            print(f"[SyncManager] Error fetching commits: {e}")
            return []

        # Find boundary - stop when we hit last_commit_sha
        if not sync_state.get("last_commit_sha"):
            # First sync - take all commits
            print(f"[SyncManager] First sync: found {len(remote_commits)} commits")
            return remote_commits

        last_sha = sync_state["last_commit_sha"]
        new_commits = []

        for commit in remote_commits:
            commit_sha = commit.get("sha") or commit.get("hash")
            if commit_sha == last_sha:
                # Found boundary, stop here
                break
            new_commits.append(commit)

        print(f"[SyncManager] Found {len(new_commits)} new commits")
        return new_commits

    def sync_incremental(self, collector) -> Dict[str, Any]:
        """
        Perform incremental sync: fetch new commits and merge into local data

        Args:
            collector: GitHub or Gitee collector instance

        Returns:
            Dictionary with sync result:
            - commits_added: Number of new commits fetched
            - total_commits: Total commits in repository
            - status: 'synced', 'up_to_date', or 'error'
        """
        # Ensure commits directory exists
        self.commits_dir.mkdir(parents=True, exist_ok=True)

        # Get new commits
        new_commits = self.get_new_commits(collector)

        if not new_commits:
            print("[SyncManager] No new commits to sync")
            return {
                "commits_added": 0,
                "total_commits": self.load_sync_state()["total_commits_fetched"],
                "status": "up_to_date"
            }

        # Fetch detailed data for each new commit
        detailed_commits = []
        print(f"[SyncManager] Fetching detailed data for {len(new_commits)} commits...")

        for i, commit_summary in enumerate(new_commits):
            sha = commit_summary.get("sha") or commit_summary.get("hash")
            print(f"[SyncManager] Fetching commit {i+1}/{len(new_commits)}: {sha[:8]}...")

            try:
                commit_data = collector.fetch_commit_data(
                    self.owner,
                    self.repo,
                    sha
                )
                detailed_commits.append(commit_data)

                # Save commit JSON
                commit_file = self.commits_dir / f"{sha}.json"
                with open(commit_file, 'w', encoding='utf-8') as f:
                    json.dump(commit_data, f, indent=2, ensure_ascii=False)

                # Save diff
                diff_content = self._extract_diff(commit_data)
                if diff_content:
                    diff_file = self.commits_dir / f"{sha}.diff"
                    with open(diff_file, 'w', encoding='utf-8') as f:
                        f.write(diff_content)

            except Exception as e:
                print(f"[SyncManager] Error fetching commit {sha}: {e}")
                continue

        if not detailed_commits:
            print("[SyncManager] No commits were successfully fetched")
            return {
                "commits_added": 0,
                "total_commits": self.load_sync_state()["total_commits_fetched"],
                "status": "error"
            }

        # Merge into commits_index.json
        commits_added = self.merge_commits(detailed_commits)

        # Update sync_state.json
        sync_state = self.load_sync_state()
        first_commit = new_commits[0]
        first_commit_sha = first_commit.get("sha") or first_commit.get("hash")

        sync_state["last_synced_at"] = datetime.now().isoformat()
        sync_state["last_commit_sha"] = first_commit_sha
        sync_state["last_commit_date"] = self._get_commit_date(first_commit)
        sync_state["total_commits_fetched"] += commits_added

        # Add to sync history (keep last 50 entries)
        sync_state["sync_history"].append({
            "synced_at": datetime.now().isoformat(),
            "commits_added": commits_added,
            "last_sha": first_commit_sha
        })
        if len(sync_state["sync_history"]) > 50:
            sync_state["sync_history"] = sync_state["sync_history"][-50:]

        self.save_sync_state(sync_state)

        print(f"[SyncManager] ✓ Sync complete: {commits_added} commits added")

        return {
            "commits_added": commits_added,
            "total_commits": sync_state["total_commits_fetched"],
            "status": "synced"
        }

    def merge_commits(self, new_commits: List[Dict]) -> int:
        """
        Merge new commits into commits_index.json

        Prepends new commits to existing index and removes duplicates.

        Args:
            new_commits: List of detailed commit data

        Returns:
            Number of commits actually added (excluding duplicates)
        """
        # Load existing index
        existing_commits = []
        if self.commits_index_path.exists():
            try:
                with open(self.commits_index_path, 'r', encoding='utf-8') as f:
                    existing_commits = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[SyncManager] Error loading commits_index.json: {e}")
                existing_commits = []

        # Build set of existing SHAs for deduplication
        existing_shas = set()
        for commit in existing_commits:
            sha = commit.get("sha") or commit.get("hash")
            if sha:
                existing_shas.add(sha)

        # Create entries for new commits
        new_entries = []
        for commit in new_commits:
            sha = commit.get("sha") or commit.get("hash")
            if not sha or sha in existing_shas:
                continue

            # Extract commit info
            commit_info = commit.get("commit", {})
            author_info = commit_info.get("author", {})
            message = commit_info.get("message", "")

            entry = {
                "sha": sha,
                "message": message.split('\n')[0][:100],  # First line, max 100 chars
                "author": author_info.get("name", ""),
                "date": author_info.get("date", ""),
                "files_changed": len(commit.get("files", [])),
                "additions": commit.get("stats", {}).get("additions", 0),
                "deletions": commit.get("stats", {}).get("deletions", 0),
                "files": [f.get("filename", "") for f in commit.get("files", [])]
            }
            new_entries.append(entry)
            existing_shas.add(sha)  # Mark as added

        # Prepend new commits (newest first)
        merged_commits = new_entries + existing_commits

        # Save merged index
        try:
            with open(self.commits_index_path, 'w', encoding='utf-8') as f:
                json.dump(merged_commits, f, indent=2, ensure_ascii=False)
            print(f"[SyncManager] Updated commits_index.json: {len(new_entries)} new commits")
        except IOError as e:
            print(f"[SyncManager] Error saving commits_index.json: {e}")
            return 0

        return len(new_entries)

    def _extract_diff(self, commit_data: Dict[str, Any]) -> str:
        """
        Extract diff content from commit data

        Args:
            commit_data: Detailed commit data from API

        Returns:
            Diff content as string
        """
        diff_lines = []

        files = commit_data.get("files", [])
        for file_data in files:
            filename = file_data.get("filename", "")
            status = file_data.get("status", "modified")
            patch = file_data.get("patch", "")

            diff_lines.append(f"diff --git a/{filename} b/{filename}")
            diff_lines.append(f"--- a/{filename}")
            diff_lines.append(f"+++ b/{filename}")
            diff_lines.append(f"status: {status}")

            if patch:
                diff_lines.append(patch)
            else:
                diff_lines.append("(binary file or no diff available)")

            diff_lines.append("")

        return "\n".join(diff_lines)

    def _get_commit_date(self, commit: Dict[str, Any]) -> str:
        """
        Extract commit date from commit summary

        Args:
            commit: Commit summary from API

        Returns:
            ISO timestamp string
        """
        # Try different date formats from API response
        if "commit" in commit:
            author = commit["commit"].get("author", {})
            date = author.get("date")
            if date:
                return date

        # Fallback to current time if date not found
        return datetime.now().isoformat()
