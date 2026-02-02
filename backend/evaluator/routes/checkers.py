"""Checker management routes."""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio

from evaluator.checker_registry import (
    discover_checkers,
    load_checker_module,
    find_checker_by_keyword,
    CheckerLoadError,
)
from evaluator.paths import get_platform_data_dir
from evaluator.utils import parse_repo_url
from evaluator.utils.git_worktree import GitWorktreeManager, find_git_repo


router = APIRouter()


def build_repo_url(platform: str, owner: str, repo: str) -> str:
    """
    Build repository URL from platform, owner, and repo.
    
    Args:
        platform: Platform name (github, gitee)
        owner: Repository owner
        repo: Repository name
        
    Returns:
        Repository URL
    """
    if platform == "github":
        return f"https://github.com/{owner}/{repo}.git"
    elif platform == "gitee":
        return f"https://gitee.com/{owner}/{repo}.git"
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def clone_repo_shallow(repo_url: str, target_dir: Path, commit_sha: Optional[str] = None) -> bool:
    """
    Clone repository using shallow clone.
    
    Args:
        repo_url: Repository URL
        target_dir: Target directory to clone into
        commit_sha: Optional commit SHA to fetch (if None, clones default branch)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Remove existing directory if it exists
        if target_dir.exists():
            import shutil
            shutil.rmtree(target_dir)
        
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        
        if commit_sha:
            # Use minimal shallow clone (depth=1) for faster cloning
            # Then fetch only the specific commit we need
            cmd = ["git", "clone", "--depth", "1", "--no-single-branch", repo_url, str(target_dir)]
            print(f"[Checker] Cloning repository (minimal shallow, depth=1): {repo_url} -> {target_dir}")
        else:
            # Clone default branch shallow (depth=1)
            cmd = ["git", "clone", "--depth", "1", repo_url, str(target_dir)]
            print(f"[Checker] Cloning repository (minimal shallow, depth=1): {repo_url} -> {target_dir}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        
        if result.returncode != 0:
            print(f"[Checker] Git clone failed: {result.stderr}")
            return False
        
        # If specific commit is requested, fetch it with minimal depth
        if commit_sha:
            print(f"[Checker] Fetching commit {commit_sha[:8]} with minimal depth...")
            # Fetch only the specific commit with depth=1 to minimize data transfer
            # Use --depth=1 to fetch only the commit and its parent
            fetch_cmd = ["git", "fetch", "origin", "--depth", "1", commit_sha]
            fetch_result = subprocess.run(
                fetch_cmd,
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=60,  # Reduced timeout since we're fetching minimal data
            )
            
            if fetch_result.returncode != 0:
                # If fetch fails, try without depth limit (but still shallow)
                print(f"[Checker] Warning: Failed to fetch commit {commit_sha[:8]} with depth=1, trying with depth=10...")
                fetch_cmd_deep = ["git", "fetch", "origin", "--depth", "10", commit_sha]
                fetch_result = subprocess.run(
                    fetch_cmd_deep,
                    cwd=str(target_dir),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if fetch_result.returncode != 0:
                    print(f"[Checker] Warning: Commit {commit_sha[:8]} may not exist in repository or network issue")
        
        print(f"[Checker] Repository cloned successfully")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"[Checker] Git clone timeout")
        return False
    except Exception as e:
        print(f"[Checker] Git clone error: {e}")
        import traceback
        traceback.print_exc()
        return False


def ensure_git_repo(data_dir: Path, platform: str, owner: str, repo: str, commit_sha: Optional[str] = None) -> Optional[Path]:
    """
    Ensure git repository exists, cloning if necessary.
    
    Args:
        data_dir: Repository data directory
        platform: Platform name (github, gitee)
        owner: Repository owner
        repo: Repository name
        commit_sha: Optional commit SHA to ensure is available
        
    Returns:
        Path to git repository, or None if cloning failed
    """
    # Check if repo already exists
    git_repo_path = find_git_repo(data_dir)
    if git_repo_path:
        return git_repo_path
    
    # Clone repository
    repo_dir = data_dir / "repo"
    repo_url = build_repo_url(platform, owner, repo)
    
    if clone_repo_shallow(repo_url, repo_dir, commit_sha):
        return repo_dir
    
    return None


class CheckerRunRequest(BaseModel):
    """Request model for running a checker."""

    checker_id: str
    platform: str
    owner: str
    repo: str
    commit_sha: str
    files: Optional[List[str]] = None  # Optional: specific files to check (None = all files in commit)
    worktree_base: Optional[str] = None  # Optional: 'build' or 'temp' (default: 'temp')


@router.get("/api/checkers/list")
async def list_checkers():
    """
    List available checkers discovered from the local `checkers/` directory.
    """
    import time
    request_start = time.time()
    print(f"[Checker] [API] GET /api/checkers/list - Request received at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(request_start))}")
    
    try:
        # Run synchronous file I/O operations in thread pool to avoid blocking event loop
        executor_start = time.time()
        print(f"[Checker] [API] Starting discover_checkers() in thread pool executor")
        loop = asyncio.get_event_loop()
        checkers = await loop.run_in_executor(None, discover_checkers)
        executor_elapsed = time.time() - executor_start
        print(f"[Checker] [API] discover_checkers() completed in {executor_elapsed:.3f}s, found {len(checkers)} checkers")
        
        # Build response
        response_start = time.time()
        response_data = {
            "success": True,
            "checkers": [
                {
                    "id": meta.checker_id,
                    "name": meta.name,
                    "keyword": meta.keyword,
                    "description": meta.description,
                    "version": meta.version,
                    "enabled": meta.enabled,
                }
                for meta, checker_dir in checkers
            ],
        }
        response_elapsed = time.time() - response_start
        total_elapsed = time.time() - request_start
        
        print(f"[Checker] [API] Response built in {response_elapsed:.3f}s")
        print(f"[Checker] [API] GET /api/checkers/list - Total request time: {total_elapsed:.3f}s, returning {len(response_data['checkers'])} checkers")
        return response_data
        
    except Exception as e:
        total_elapsed = time.time() - request_start
        print(f"[Checker] [API] ERROR in /api/checkers/list after {total_elapsed:.3f}s: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to list checkers: {str(e)}")


@router.post("/api/checkers/run")
async def run_checker(request: CheckerRunRequest) -> Dict[str, Any]:
    """
    Run a checker on a specific commit.
    
    Args:
        request: CheckerRunRequest with checker_id, platform, owner, repo, commit_sha, and optional files
        
    Returns:
        Checker execution result (dict with success, score, passed, total, details, message, etc.)
    """
    try:
        print(f"[Checker] Running checker={request.checker_id} for commit={request.commit_sha}")

        # Load checker module
        try:
            meta, checker_mod, checker_path = load_checker_module(request.checker_id)
        except CheckerLoadError as e:
            raise HTTPException(status_code=404, detail=f"Checker not found: {str(e)}")

        # Get data directory
        data_dir = get_platform_data_dir(request.platform, request.owner, request.repo)
        if not data_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Repository data not found for {request.platform}/{request.owner}/{request.repo}. Please sync repository data first.",
            )

        # Get commit files if files not specified
        files_to_check = request.files
        if files_to_check is None:
            # Load commit data to get changed files
            commits_list_path = data_dir / "commits_list.json"
            if commits_list_path.exists():
                with open(commits_list_path, "r", encoding="utf-8") as f:
                    commits = json.load(f)
                # Find the commit
                commit_data = None
                for commit in commits:
                    sha = commit.get("sha") or commit.get("hash")
                    if sha == request.commit_sha:
                        commit_data = commit
                        break

                if commit_data:
                    # Extract changed files from commit
                    files = commit_data.get("files", [])
                    files_to_check = [f.get("filename") for f in files if f.get("filename")]
                else:
                    print(f"[Checker] Warning: Commit {request.commit_sha} not found in commits_list.json")
                    files_to_check = []
            else:
                print(f"[Checker] Warning: commits_list.json not found in {data_dir}")
                files_to_check = []

        # Ensure git repository exists (clone if necessary)
        git_repo_path = ensure_git_repo(
            data_dir,
            request.platform,
            request.owner,
            request.repo,
            request.commit_sha
        )
        
        if not git_repo_path:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to clone git repository for {request.platform}/{request.owner}/{request.repo}. Please check network connectivity and repository access.",
            )
        
        # Determine worktree base directory
        worktree_base_dir = None
        if request.worktree_base == 'build':
            # Use build directory in project root
            # Find project root (assuming we're in backend/evaluator/routes/)
            current_file = Path(__file__).resolve()
            # backend/evaluator/routes/checkers.py -> backend/evaluator -> backend -> repo root
            repo_root = current_file.parent.parent.parent.parent
            build_dir = repo_root / "build" / "worktrees"
            build_dir.mkdir(parents=True, exist_ok=True)
            worktree_base_dir = build_dir
            print(f"[Checker] Using build directory for worktrees: {worktree_base_dir}")
        # else: worktree_base is 'temp' or None, use tempfile (default)
        
        # Use worktree for accurate commit version checking
        try:
            worktree_manager = GitWorktreeManager(git_repo_path)
            
            # Run checker in isolated worktree
            with worktree_manager.checkout_commit(request.commit_sha, worktree_base=worktree_base_dir) as worktree_path:
                print(f"[Checker] Checked out commit {request.commit_sha[:8]} to worktree {worktree_path}")
                
                # Run checker with worktree path
                result = checker_mod.run_checker(
                    commit_sha=request.commit_sha,
                    files=files_to_check,
                    data_dir=data_dir,
                    worktree_path=worktree_path,  # Pass worktree path to checker
                )
        except Exception as e:
            print(f"[Checker] Error running checker {request.checker_id}: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Checker execution failed: {str(e)}",
            )

        # Validate result format
        if not isinstance(result, dict):
            raise HTTPException(
                status_code=500,
                detail=f"Checker returned invalid result type: {type(result)}",
            )

        # Ensure required fields
        if "success" not in result:
            result["success"] = True
        if "score" not in result:
            result["score"] = 0.0
        if "message" not in result:
            result["message"] = "Checker completed"

        print(f"[Checker] Checker {request.checker_id} completed: success={result.get('success')}, score={result.get('score')}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Checker] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
