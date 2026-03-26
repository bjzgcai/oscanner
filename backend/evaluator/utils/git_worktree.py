"""
Git worktree management for concurrent checker execution.

This module provides utilities to create isolated git worktrees for checking
specific commits, enabling concurrent execution of checkers without conflicts.
"""

import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


class GitWorktreeManager:
    """Manages git worktrees for isolated commit checking."""
    
    def __init__(self, repo_path: Path):
        """
        Initialize worktree manager.
        
        Args:
            repo_path: Path to the git repository (must contain .git directory)
        """
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")
    
    def _run_git(self, *args, cwd: Optional[Path] = None) -> tuple[int, str, str]:
        """
        Run git command and return (returncode, stdout, stderr).
        
        Args:
            *args: Git command arguments
            cwd: Working directory (defaults to repo_path)
            
        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        cmd = ["git"] + list(args)
        result = subprocess.run(
            cmd,
            cwd=str(cwd or self.repo_path),
            capture_output=True,
            text=True,
            timeout=60,  # Increased timeout for git operations (clone, fetch, checkout)
        )
        return result.returncode, result.stdout, result.stderr
    
    @contextmanager
    def checkout_commit(self, commit_sha: str, worktree_base: Optional[Path] = None):
        """
        Context manager to create a worktree for a specific commit.
        
        Creates a temporary worktree, checks out the commit, yields the worktree path,
        and cleans up on exit.
        
        Args:
            commit_sha: Commit SHA to check out
            worktree_base: Base directory for worktrees. When omitted, a temporary
                directory is created and cleaned up automatically.
            
        Yields:
            Path to the worktree directory
            
        Example:
            with manager.checkout_commit("abc123") as worktree_path:
                # Run checker in worktree_path
                pass
        """
        # Include a random suffix so concurrent requests for the same commit
        # never contend for the same checkout path.
        worktree_name = f"checker_{commit_sha[:8]}_{uuid.uuid4().hex[:8]}"
        
        # Determine worktree base directory
        if worktree_base is None:
            # Use a dedicated temporary base directory for this checkout so concurrent
            # requests do not share state unless a caller explicitly opts into it.
            worktree_base = Path(tempfile.mkdtemp(prefix="git-worktrees-"))
            cleanup_base = True
        else:
            worktree_base = Path(worktree_base)
            worktree_base.mkdir(parents=True, exist_ok=True)
            cleanup_base = False
        
        worktree_path = worktree_base / worktree_name
        
        print(f"[GitWorktree] Creating worktree at: {worktree_path}")
        
        try:
            # Create worktree
            returncode, stdout, stderr = self._run_git(
                "worktree", "add", "--detach", str(worktree_path), commit_sha
            )
            
            if returncode != 0:
                # Check if worktree already exists (might happen in concurrent scenarios)
                if "already exists" in stderr.lower() or "already checked out" in stderr.lower():
                    # Try to remove and recreate
                    self._run_git("worktree", "remove", "--force", str(worktree_path))
                    returncode, stdout, stderr = self._run_git(
                        "worktree", "add", "--detach", str(worktree_path), commit_sha
                    )
                
                if returncode != 0:
                    raise RuntimeError(
                        f"Failed to create worktree for commit {commit_sha}: {stderr}"
                    )
            
            # Verify the commit is checked out
            returncode, checked_out_sha, _ = self._run_git(
                "rev-parse", "HEAD", cwd=worktree_path
            )
            if returncode != 0 or checked_out_sha.strip() != commit_sha:
                raise RuntimeError(
                    f"Worktree checkout verification failed: expected {commit_sha}, got {checked_out_sha.strip()}"
                )
            
            print(f"[GitWorktree] Worktree created successfully at: {worktree_path.absolute()}")
            print(f"[GitWorktree] Checked out commit: {commit_sha[:8]} ({checked_out_sha.strip()[:8]})")
            
            yield worktree_path
            
        finally:
            # Clean up worktree
            try:
                returncode, _, stderr = self._run_git(
                    "worktree", "remove", "--force", str(worktree_path)
                )
                if returncode != 0:
                    print(f"[GitWorktree] Warning: Failed to remove worktree {worktree_path}: {stderr}")
                    # Try manual cleanup if git worktree remove fails
                    if worktree_path.exists():
                        shutil.rmtree(worktree_path, ignore_errors=True)
            except Exception as e:
                print(f"[GitWorktree] Warning: Error cleaning up worktree {worktree_path}: {e}")
            
            # Clean up base directory if it was temporary
            if cleanup_base and worktree_base.exists():
                try:
                    shutil.rmtree(worktree_base, ignore_errors=True)
                except Exception as e:
                    print(f"[GitWorktree] Warning: Error cleaning up temp directory {worktree_base}: {e}")
    
    def list_worktrees(self) -> list[dict]:
        """
        List all existing worktrees.
        
        Returns:
            List of worktree info dictionaries
        """
        returncode, stdout, stderr = self._run_git("worktree", "list", "--porcelain")
        if returncode != 0:
            return []
        
        worktrees = []
        current = {}
        for line in stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line[9:]}
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]
        if current:
            worktrees.append(current)
        
        return worktrees


def find_git_repo(data_dir: Path) -> Optional[Path]:
    """
    Find git repository path from data directory.
    
    Checks for:
    1. data_dir/repo/.git
    2. data_dir/.git (if data_dir itself is the repo)
    
    Args:
        data_dir: Repository data directory
        
    Returns:
        Path to git repository, or None if not found
    """
    # Check data_dir/repo/.git (standard location from extract_repo_data.py)
    repo_path = data_dir / "repo"
    if (repo_path / ".git").exists():
        return repo_path
    
    # Check if data_dir itself is a git repo (fallback)
    if (data_dir / ".git").exists():
        return data_dir
    
    return None
