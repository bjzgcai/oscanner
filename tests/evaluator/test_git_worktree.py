"""Tests for git worktree isolation helpers."""

from pathlib import Path
import sys

# Add project root to path if not already there
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add backend directory to Python path so evaluator can be imported as top-level package
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from evaluator.utils.git_worktree import GitWorktreeManager


class TestGitWorktreeManager:
    """Verify worktrees stay isolated across requests."""

    def test_checkout_commit_uses_unique_worktree_path_per_invocation(self, tmp_path, monkeypatch):
        repo_path = tmp_path / "repo"
        (repo_path / ".git").mkdir(parents=True)
        manager = GitWorktreeManager(repo_path)
        commit_sha = "abcdef1234567890"
        calls = []

        def fake_run_git(*args, cwd=None):
            calls.append((args, cwd))
            if args[:2] == ("worktree", "add"):
                return 0, "", ""
            if args[:2] == ("worktree", "remove"):
                return 0, "", ""
            if args[0] == "rev-parse":
                return 0, f"{commit_sha}\n", ""
            raise AssertionError(f"Unexpected git command: {args}")

        monkeypatch.setattr(manager, "_run_git", fake_run_git)

        build_base = tmp_path / "build" / "worktrees"
        with manager.checkout_commit(commit_sha, worktree_base=build_base) as first_path:
            with manager.checkout_commit(commit_sha, worktree_base=build_base) as second_path:
                assert first_path != second_path
                assert first_path.parent == build_base
                assert second_path.parent == build_base
                assert first_path.name.startswith("checker_abcdef12_")
                assert second_path.name.startswith("checker_abcdef12_")

        add_paths = [
            Path(args[3])
            for args, _ in calls
            if args[:2] == ("worktree", "add")
        ]
        assert len(add_paths) == 2
        assert add_paths[0] != add_paths[1]

    def test_checkout_commit_without_base_uses_temp_directory_and_cleans_it_up(self, tmp_path, monkeypatch):
        repo_path = tmp_path / "repo"
        (repo_path / ".git").mkdir(parents=True)
        manager = GitWorktreeManager(repo_path)
        commit_sha = "1234567890abcdef"

        def fake_run_git(*args, cwd=None):
            if args[:2] == ("worktree", "add"):
                return 0, "", ""
            if args[:2] == ("worktree", "remove"):
                return 0, "", ""
            if args[0] == "rev-parse":
                return 0, f"{commit_sha}\n", ""
            raise AssertionError(f"Unexpected git command: {args}")

        monkeypatch.setattr(manager, "_run_git", fake_run_git)

        with manager.checkout_commit(commit_sha) as worktree_path:
            base_dir = worktree_path.parent
            assert base_dir.exists()
            assert base_dir.name.startswith("git-worktrees-")

        assert not base_dir.exists()
