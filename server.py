#!/usr/bin/env python3
"""
FastAPI server for GitHub and Gitee data collection with caching
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from pathlib import Path
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv('.env.local')

# Import collectors directly
import importlib.util

github_module_path = Path(__file__).parent / "evaluator" / "collectors" / "github.py"
spec = importlib.util.spec_from_file_location("github_collector", github_module_path)
github_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(github_module)

GitHubCollector = github_module.GitHubCollector

gitee_module_path = Path(__file__).parent / "evaluator" / "collectors" / "gitee.py"
spec = importlib.util.spec_from_file_location("gitee_collector", gitee_module_path)
gitee_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gitee_module)

GiteeCollector = gitee_module.GiteeCollector

# Import CommitEvaluator
evaluator_module_path = Path(__file__).parent / "evaluator" / "commit_evaluator.py"
spec = importlib.util.spec_from_file_location("commit_evaluator", evaluator_module_path)
evaluator_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator_module)

CommitEvaluator = evaluator_module.CommitEvaluator

# Initialize FastAPI app
app = FastAPI(
    title="GitHub & Gitee Data Collector API",
    description="API for collecting GitHub and Gitee data with caching support",
    version="1.0.0"
)

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize GitHub collector
# Token can be set via environment variable: GITHUB_TOKEN
github_token = os.getenv("GITHUB_TOKEN")
github_collector = GitHubCollector(token=github_token, cache_dir="data")

# Initialize Gitee collector
# GITEE_TOKEN for enterprise (z.gitee.cn)
# PUBLIC_GITEE_TOKEN for public (gitee.com)
gitee_token = os.getenv("GITEE_TOKEN")
public_gitee_token = os.getenv("PUBLIC_GITEE_TOKEN")
gitee_collector = GiteeCollector(token=gitee_token, public_token=public_gitee_token, cache_dir="data")

# Initialize Commit Evaluator
# API key can be set via environment variable: OPEN_ROUTER_KEY
openrouter_key = os.getenv("OPEN_ROUTER_KEY")
commit_evaluator = CommitEvaluator(api_key=openrouter_key)


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "GitHub & Gitee Data Collector API",
        "version": "1.0.0",
        "endpoints": {
            "github": {
                "repo_data": "/api/github/repo/{owner}/{repo}",
                "user_data": "/api/github/user/{username}",
                "commits_list": "/api/github/commits/{owner}/{repo}",
                "commit_detail": "/api/github/commits/{owner}/{repo}/{commit_sha}",
                "fetch_all_commits": "/api/github/commits/{owner}/{repo}/fetch-all",
                "evaluate_engineer": "/api/github/evaluate/{owner}/{repo}/{username}",
            },
            "gitee": {
                "repo_data": "/api/gitee/repo/{owner}/{repo}",
                "user_data": "/api/gitee/user/{username}",
                "commits_list": "/api/gitee/commits/{owner}/{repo}",
                "commit_detail": "/api/gitee/commits/{owner}/{repo}/{commit_sha}",
                "fetch_all_commits": "/api/gitee/commits/{owner}/{repo}/fetch-all",
                "collaborators": "/api/gitee/collaborators/{owner}/{repo}",
                "contributors": "/api/gitee/contributors/{owner}/{repo}",
                "evaluate_engineer": "/api/gitee/evaluate/{owner}/{repo}/{username}",
            },
            "cache": {
                "stats": "/api/cache/stats",
                "clear_github_repo": "/api/cache/github/repo/{owner}/{repo}",
                "clear_github_user": "/api/cache/github/user/{username}",
                "clear_github_evaluation": "/api/cache/github/evaluation/{owner}/{repo}/{username}",
                "clear_gitee_repo": "/api/cache/gitee/repo/{owner}/{repo}",
                "clear_gitee_user": "/api/cache/gitee/user/{username}",
                "clear_gitee_evaluation": "/api/cache/gitee/evaluation/{owner}/{repo}/{username}",
                "clear_all": "/api/cache/clear"
            },
            "legacy_github": {
                "note": "Legacy GitHub endpoints (without /github/ prefix) are still supported for backward compatibility",
                "repo_data": "/api/repo/{owner}/{repo}",
                "user_data": "/api/user/{username}",
                "commits_list": "/api/commits/{owner}/{repo}",
                "commit_detail": "/api/commits/{owner}/{repo}/{commit_sha}",
                "fetch_all_commits": "/api/commits/{owner}/{repo}/fetch-all",
                "evaluate_engineer": "/api/evaluate/{owner}/{repo}/{username}",
            }
        }
    }


@app.get("/api/repo/{owner}/{repo}")
async def get_repo_data(
    owner: str,
    repo: str,
    use_cache: bool = Query(True, description="Whether to use cached data")
):
    """
    Get repository data with optional caching

    Args:
        owner: Repository owner
        repo: Repository name
        use_cache: Whether to use cache (default: True)

    Returns:
        Repository data
    """
    try:
        repo_url = f"https://github.com/{owner}/{repo}"
        data = github_collector.collect_repo_data(repo_url, use_cache=use_cache)

        cache_path = github_collector._get_cache_path(repo_url)
        is_cached = cache_path.exists()

        return {
            "success": True,
            "data": data,
            "metadata": {
                "repo_url": repo_url,
                "cached": is_cached,
                "cache_path": str(cache_path) if is_cached else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/user/{username}")
async def get_user_data(
    username: str,
    use_cache: bool = Query(True, description="Whether to use cached data")
):
    """
    Get user data with optional caching

    Args:
        username: GitHub username
        use_cache: Whether to use cache (default: True)

    Returns:
        User data
    """
    try:
        data = github_collector.collect_user_data(username, use_cache=use_cache)

        user_url = f"https://github.com/{username}"
        cache_path = github_collector._get_cache_path(user_url)
        is_cached = cache_path.exists()

        return {
            "success": True,
            "data": data,
            "metadata": {
                "username": username,
                "cached": is_cached,
                "cache_path": str(cache_path) if is_cached else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics

    Returns:
        Cache statistics including file count, total size, etc.
    """
    try:
        cache_dir = Path("data")

        if not cache_dir.exists():
            return {
                "success": True,
                "stats": {
                    "total_files": 0,
                    "total_size_bytes": 0,
                    "total_size_mb": 0,
                    "repos_cached": 0,
                    "users_cached": 0,
                    "cache_dir": str(cache_dir)
                }
            }

        # Count files and calculate sizes
        total_files = 0
        total_size = 0
        repos_cached = 0
        users_cached = 0
        cache_entries = []

        for root, dirs, files in os.walk(cache_dir):
            for file in files:
                if file.endswith('.json'):
                    total_files += 1
                    file_path = Path(root) / file
                    file_size = file_path.stat().st_size
                    total_size += file_size

                    # Categorize
                    if '/users/' in str(file_path):
                        users_cached += 1
                    else:
                        repos_cached += 1

                    # Load cache metadata
                    try:
                        with open(file_path, 'r') as f:
                            cache_data = json.load(f)
                            cache_entries.append({
                                "path": str(file_path.relative_to(cache_dir)),
                                "cached_at": cache_data.get("cached_at"),
                                "url": cache_data.get("repo_url"),
                                "size_bytes": file_size
                            })
                    except:
                        pass

        return {
            "success": True,
            "stats": {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "repos_cached": repos_cached,
                "users_cached": users_cached,
                "cache_dir": str(cache_dir),
                "entries": cache_entries
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cache/repo/{owner}/{repo}")
async def clear_repo_cache(owner: str, repo: str):
    """
    Clear cache for a specific repository

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        Success status
    """
    try:
        repo_url = f"https://github.com/{owner}/{repo}"
        cache_path = github_collector._get_cache_path(repo_url)

        if cache_path.exists():
            cache_path.unlink()
            return {
                "success": True,
                "message": f"Cache cleared for {owner}/{repo}",
                "cache_path": str(cache_path)
            }
        else:
            return {
                "success": False,
                "message": f"No cache found for {owner}/{repo}"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cache/user/{username}")
async def clear_user_cache(username: str):
    """
    Clear cache for a specific user

    Args:
        username: GitHub username

    Returns:
        Success status
    """
    try:
        user_url = f"https://github.com/{username}"
        cache_path = github_collector._get_cache_path(user_url)

        if cache_path.exists():
            cache_path.unlink()
            return {
                "success": True,
                "message": f"Cache cleared for user {username}",
                "cache_path": str(cache_path)
            }
        else:
            return {
                "success": False,
                "message": f"No cache found for user {username}"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cache/evaluation/{owner}/{repo}/{username}")
async def clear_evaluation_cache(owner: str, repo: str, username: str):
    """
    Clear cached evaluation for a specific user in a repository

    Args:
        owner: Repository owner
        repo: Repository name
        username: GitHub username

    Returns:
        Success status
    """
    try:
        cache_path = _get_evaluation_cache_path(owner, repo, username)

        if cache_path.exists():
            cache_path.unlink()
            return {
                "success": True,
                "message": f"Evaluation cache cleared for {username} in {owner}/{repo}",
                "cache_path": str(cache_path)
            }
        else:
            return {
                "success": False,
                "message": f"No evaluation cache found for {username} in {owner}/{repo}"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cache/clear")
async def clear_all_cache():
    """
    Clear all cached data

    Returns:
        Success status with count of cleared files
    """
    try:
        cache_dir = Path("data")

        if not cache_dir.exists():
            return {
                "success": True,
                "message": "Cache directory does not exist",
                "files_cleared": 0
            }

        files_cleared = 0
        for root, dirs, files in os.walk(cache_dir):
            for file in files:
                if file.endswith('.json'):
                    file_path = Path(root) / file
                    file_path.unlink()
                    files_cleared += 1

        return {
            "success": True,
            "message": f"All cache cleared",
            "files_cleared": files_cleared
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/commits/{owner}/{repo}")
async def get_commits_list(
    owner: str,
    repo: str,
    limit: int = Query(100, description="Maximum number of commits to fetch"),
    use_cache: bool = Query(True, description="Whether to use cached data")
):
    """
    Get list of commits from a repository

    Args:
        owner: Repository owner
        repo: Repository name
        limit: Maximum number of commits to fetch (default: 100)
        use_cache: Whether to use cache (default: True)

    Returns:
        List of commits
    """
    try:
        commits = github_collector.fetch_commits_list(owner, repo, limit=limit, use_cache=use_cache)

        cache_path = github_collector._get_commits_list_cache_path(owner, repo)
        is_cached = cache_path.exists()

        return {
            "success": True,
            "data": commits,
            "metadata": {
                "owner": owner,
                "repo": repo,
                "count": len(commits),
                "cached": is_cached,
                "cache_path": str(cache_path) if is_cached else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/commits/{owner}/{repo}/{commit_sha}")
async def get_commit_detail(
    owner: str,
    repo: str,
    commit_sha: str,
    use_cache: bool = Query(True, description="Whether to use cached data")
):
    """
    Get detailed information about a specific commit

    Args:
        owner: Repository owner
        repo: Repository name
        commit_sha: Commit SHA hash
        use_cache: Whether to use cache (default: True)

    Returns:
        Detailed commit data including files changed and diffs
    """
    try:
        commit_data = github_collector.fetch_commit_data(owner, repo, commit_sha, use_cache=use_cache)

        cache_path = github_collector._get_commit_cache_path(owner, repo, commit_sha)
        is_cached = cache_path.exists()

        return {
            "success": True,
            "data": commit_data,
            "metadata": {
                "owner": owner,
                "repo": repo,
                "commit_sha": commit_sha,
                "cached": is_cached,
                "cache_path": str(cache_path) if is_cached else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/commits/{owner}/{repo}/fetch-all")
async def fetch_all_commits(
    owner: str,
    repo: str,
    limit: int = Query(100, description="Maximum number of commits to fetch"),
    use_cache: bool = Query(True, description="Whether to use cached data for commit list")
):
    """
    Fetch all commits and their detailed data for a repository

    This endpoint will:
    1. Fetch the list of commits
    2. Fetch detailed data for each commit
    3. Store all data in the cache

    Args:
        owner: Repository owner
        repo: Repository name
        limit: Maximum number of commits to fetch (default: 100)
        use_cache: Whether to use cache for commit list (default: True)

    Returns:
        Summary of fetched commits
    """
    try:
        # First, get the list of commits
        commits_list = github_collector.fetch_commits_list(owner, repo, limit=limit, use_cache=use_cache)

        # Then, fetch detailed data for each commit
        fetched_commits = []
        errors = []

        for commit_summary in commits_list:
            commit_sha = commit_summary.get("sha")
            if not commit_sha:
                continue

            try:
                # Fetch detailed commit data (will be cached automatically)
                commit_data = github_collector.fetch_commit_data(owner, repo, commit_sha, use_cache=use_cache)
                fetched_commits.append({
                    "sha": commit_sha,
                    "message": commit_summary.get("commit", {}).get("message", ""),
                    "author": commit_summary.get("commit", {}).get("author", {}).get("name", ""),
                    "date": commit_summary.get("commit", {}).get("author", {}).get("date", ""),
                    "files_changed": len(commit_data.get("files", []))
                })
            except Exception as e:
                errors.append({
                    "sha": commit_sha,
                    "error": str(e)
                })

        return {
            "success": True,
            "summary": {
                "owner": owner,
                "repo": repo,
                "total_commits": len(commits_list),
                "fetched_commits": len(fetched_commits),
                "errors": len(errors)
            },
            "commits": fetched_commits,
            "errors": errors if errors else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_evaluation_cache_path(owner: str, repo: str, username: str) -> Path:
    """
    Get the cache path for an evaluation result

    Args:
        owner: Repository owner
        repo: Repository name
        username: GitHub username

    Returns:
        Path to the evaluation cache file
    """
    cache_dir = Path("data") / owner / repo / "evaluations"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{username}.json"


def _load_evaluation_from_cache(owner: str, repo: str, username: str) -> Optional[Dict[str, Any]]:
    """
    Load evaluation result from cache

    Args:
        owner: Repository owner
        repo: Repository name
        username: GitHub username

    Returns:
        Cached evaluation data or None if not cached
    """
    cache_path = _get_evaluation_cache_path(owner, repo, username)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
            print(f"[Cache Hit] Loaded evaluation for {username} from cache")
            return cached_data
    except Exception as e:
        print(f"[Cache Error] Failed to load evaluation cache: {e}")
        return None


def _save_evaluation_to_cache(owner: str, repo: str, username: str, evaluation: Dict[str, Any]) -> None:
    """
    Save evaluation result to cache

    Args:
        owner: Repository owner
        repo: Repository name
        username: GitHub username
        evaluation: Evaluation result to cache
    """
    cache_path = _get_evaluation_cache_path(owner, repo, username)

    try:
        cache_data = {
            "cached_at": datetime.now().isoformat(),
            "owner": owner,
            "repo": repo,
            "username": username,
            "evaluation": evaluation
        }

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)

        print(f"[Cache Save] Saved evaluation for {username} to cache")
    except Exception as e:
        print(f"[Cache Error] Failed to save evaluation cache: {e}")


@app.post("/api/evaluate/{owner}/{repo}/{username}")
async def evaluate_engineer(
    owner: str,
    repo: str,
    username: str,
    limit: int = Query(30, description="Maximum number of commits to analyze"),
    use_cache: bool = Query(True, description="Whether to use cached evaluation and commit data")
):
    """
    Evaluate an engineer's skill based on their commits in a repository

    This endpoint:
    1. Checks cache for previous evaluation (if use_cache=True)
    2. Fetches commits by the specified author
    3. Analyzes commits using LLM (if not cached)
    4. Caches evaluation results for future use
    5. Returns evaluation scores across six dimensions

    Args:
        owner: Repository owner
        repo: Repository name
        username: GitHub username to evaluate
        limit: Maximum number of commits to analyze (default: 30)
        use_cache: Whether to use cached data (default: True)

    Returns:
        Evaluation results with scores for each dimension
    """
    try:
        # Check evaluation cache first
        if use_cache:
            cached_evaluation = _load_evaluation_from_cache(owner, repo, username)
            if cached_evaluation:
                return {
                    "success": True,
                    "evaluation": cached_evaluation.get("evaluation"),
                    "metadata": {
                        "owner": owner,
                        "repo": repo,
                        "username": username,
                        "cached": True,
                        "cached_at": cached_evaluation.get("cached_at")
                    }
                }

        # First, get commits by this author
        commits_list = github_collector.fetch_commits_list(owner, repo, limit=limit, use_cache=use_cache)

        # Fetch detailed commit data for each commit
        detailed_commits = []
        for commit_summary in commits_list:
            commit_sha = commit_summary.get("sha")
            commit_author = commit_summary.get("commit", {}).get("author", {}).get("name", "")

            # Get GitHub author login (handle null author field)
            author_obj = commit_summary.get("author")
            author_login = author_obj.get("login", "") if author_obj else ""

            # Check if commit is by this user (case-insensitive match)
            if commit_author.lower() == username.lower() or \
               author_login.lower() == username.lower():

                try:
                    # Fetch detailed commit with files and diffs
                    commit_data = github_collector.fetch_commit_data(owner, repo, commit_sha, use_cache=use_cache)
                    detailed_commits.append(commit_data)

                    # Stop if we have enough commits
                    if len(detailed_commits) >= limit:
                        break
                except Exception as e:
                    print(f"[Warning] Failed to fetch commit {commit_sha}: {e}")
                    continue

        if not detailed_commits:
            return {
                "success": False,
                "error": f"No commits found for user {username} in {owner}/{repo}",
                "evaluation": commit_evaluator._get_empty_evaluation(username)
            }

        # Evaluate using LLM
        evaluation = commit_evaluator.evaluate_engineer(detailed_commits, username)

        # Save evaluation to cache for future use
        _save_evaluation_to_cache(owner, repo, username, evaluation)

        return {
            "success": True,
            "evaluation": evaluation,
            "metadata": {
                "owner": owner,
                "repo": repo,
                "username": username,
                "commits_analyzed": len(detailed_commits),
                "cached": False
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GITEE ENDPOINTS
# ============================================================================

@app.get("/api/gitee/repo/{owner}/{repo}")
async def get_gitee_repo_data(
    owner: str,
    repo: str,
    use_cache: bool = Query(True, description="Whether to use cached data")
):
    """
    Get Gitee repository data with optional caching

    Args:
        owner: Repository owner
        repo: Repository name
        use_cache: Whether to use cache (default: True)

    Returns:
        Repository data
    """
    try:
        repo_url = f"https://gitee.com/{owner}/{repo}"
        data = gitee_collector.collect_repo_data(repo_url, use_cache=use_cache)

        cache_path = gitee_collector._get_cache_path(repo_url)
        is_cached = cache_path.exists()

        return {
            "success": True,
            "data": data,
            "metadata": {
                "repo_url": repo_url,
                "cached": is_cached,
                "cache_path": str(cache_path) if is_cached else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gitee/user/{username}")
async def get_gitee_user_data(
    username: str,
    use_cache: bool = Query(True, description="Whether to use cached data")
):
    """
    Get Gitee user data with optional caching

    Args:
        username: Gitee username
        use_cache: Whether to use cache (default: True)

    Returns:
        User data
    """
    try:
        data = gitee_collector.collect_user_data(username, use_cache=use_cache)

        user_url = f"https://gitee.com/{username}"
        cache_path = gitee_collector._get_cache_path(user_url)
        is_cached = cache_path.exists()

        return {
            "success": True,
            "data": data,
            "metadata": {
                "username": username,
                "cached": is_cached,
                "cache_path": str(cache_path) if is_cached else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gitee/commits/{owner}/{repo}")
async def get_gitee_commits_list(
    owner: str,
    repo: str,
    limit: int = Query(100, description="Maximum number of commits to fetch"),
    use_cache: bool = Query(True, description="Whether to use cached data"),
    is_enterprise: bool = Query(False, description="Whether this is an enterprise (z.gitee.cn) repository")
):
    """
    Get list of commits from a Gitee repository

    Args:
        owner: Repository owner
        repo: Repository name
        limit: Maximum number of commits to fetch (default: 100)
        use_cache: Whether to use cache (default: True)
        is_enterprise: Whether this is an enterprise repository (default: False)

    Returns:
        List of commits
    """
    try:
        commits = gitee_collector.fetch_commits_list(owner, repo, limit=limit, use_cache=use_cache, is_enterprise=is_enterprise)

        cache_path = gitee_collector._get_commits_list_cache_path(owner, repo)
        is_cached = cache_path.exists()

        return {
            "success": True,
            "data": commits,
            "metadata": {
                "owner": owner,
                "repo": repo,
                "count": len(commits),
                "cached": is_cached,
                "cache_path": str(cache_path) if is_cached else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gitee/commits/{owner}/{repo}/{commit_sha}")
async def get_gitee_commit_detail(
    owner: str,
    repo: str,
    commit_sha: str,
    use_cache: bool = Query(True, description="Whether to use cached data"),
    is_enterprise: bool = Query(False, description="Whether this is an enterprise (z.gitee.cn) repository")
):
    """
    Get detailed information about a specific Gitee commit

    Args:
        owner: Repository owner
        repo: Repository name
        commit_sha: Commit SHA hash
        use_cache: Whether to use cache (default: True)
        is_enterprise: Whether this is an enterprise repository (default: False)

    Returns:
        Detailed commit data including files changed and diffs
    """
    try:
        commit_data = gitee_collector.fetch_commit_data(owner, repo, commit_sha, use_cache=use_cache, is_enterprise=is_enterprise)

        cache_path = gitee_collector._get_commit_cache_path(owner, repo, commit_sha)
        is_cached = cache_path.exists()

        return {
            "success": True,
            "data": commit_data,
            "metadata": {
                "owner": owner,
                "repo": repo,
                "commit_sha": commit_sha,
                "cached": is_cached,
                "cache_path": str(cache_path) if is_cached else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gitee/commits/{owner}/{repo}/fetch-all")
async def fetch_all_gitee_commits(
    owner: str,
    repo: str,
    limit: int = Query(100, description="Maximum number of commits to fetch"),
    use_cache: bool = Query(True, description="Whether to use cached data for commit list"),
    is_enterprise: bool = Query(False, description="Whether this is an enterprise (z.gitee.cn) repository")
):
    """
    Fetch all commits and their detailed data for a Gitee repository

    This endpoint will:
    1. Fetch the list of commits
    2. Fetch detailed data for each commit
    3. Store all data in the cache

    Args:
        owner: Repository owner
        repo: Repository name
        limit: Maximum number of commits to fetch (default: 100)
        use_cache: Whether to use cache for commit list (default: True)
        is_enterprise: Whether this is an enterprise repository (default: False)

    Returns:
        Summary of fetched commits
    """
    try:
        # First, get the list of commits
        commits_list = gitee_collector.fetch_commits_list(owner, repo, limit=limit, use_cache=use_cache, is_enterprise=is_enterprise)

        # Then, fetch detailed data for each commit
        fetched_commits = []
        errors = []

        for commit_summary in commits_list:
            commit_sha = commit_summary.get("sha")
            if not commit_sha:
                continue

            try:
                # Fetch detailed commit data (will be cached automatically)
                commit_data = gitee_collector.fetch_commit_data(owner, repo, commit_sha, use_cache=use_cache, is_enterprise=is_enterprise)
                fetched_commits.append({
                    "sha": commit_sha,
                    "message": commit_summary.get("commit", {}).get("message", ""),
                    "author": commit_summary.get("commit", {}).get("author", {}).get("name", ""),
                    "date": commit_summary.get("commit", {}).get("author", {}).get("date", ""),
                    "files_changed": len(commit_data.get("files", []))
                })
            except Exception as e:
                errors.append({
                    "sha": commit_sha,
                    "error": str(e)
                })

        return {
            "success": True,
            "summary": {
                "owner": owner,
                "repo": repo,
                "total_commits": len(commits_list),
                "fetched_commits": len(fetched_commits),
                "errors": len(errors)
            },
            "commits": fetched_commits,
            "errors": errors if errors else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gitee/evaluate/{owner}/{repo}/{username}")
async def evaluate_gitee_engineer(
    owner: str,
    repo: str,
    username: str,
    limit: int = Query(30, description="Maximum number of commits to analyze"),
    use_cache: bool = Query(True, description="Whether to use cached evaluation and commit data"),
    is_enterprise: bool = Query(False, description="Whether this is an enterprise (z.gitee.cn) repository")
):
    """
    Evaluate an engineer's skill based on their Gitee commits in a repository

    This endpoint:
    1. Checks cache for previous evaluation (if use_cache=True)
    2. Fetches commits by the specified author
    3. Analyzes commits using LLM (if not cached)
    4. Caches evaluation results for future use
    5. Returns evaluation scores across six dimensions

    Args:
        owner: Repository owner
        repo: Repository name
        username: Gitee username to evaluate
        limit: Maximum number of commits to analyze (default: 30)
        use_cache: Whether to use cached data (default: True)
        is_enterprise: Whether this is an enterprise repository (default: False)

    Returns:
        Evaluation results with scores for each dimension
    """
    try:
        # Check evaluation cache first
        if use_cache:
            cached_evaluation = _load_gitee_evaluation_from_cache(owner, repo, username)
            if cached_evaluation:
                return {
                    "success": True,
                    "evaluation": cached_evaluation.get("evaluation"),
                    "metadata": {
                        "owner": owner,
                        "repo": repo,
                        "username": username,
                        "cached": True,
                        "cached_at": cached_evaluation.get("cached_at")
                    }
                }

        # First, get commits by this author
        commits_list = gitee_collector.fetch_commits_list(owner, repo, limit=limit, use_cache=use_cache, is_enterprise=is_enterprise)

        # Fetch detailed commit data for each commit
        detailed_commits = []
        for commit_summary in commits_list:
            commit_sha = commit_summary.get("sha")
            commit_author = commit_summary.get("commit", {}).get("author", {}).get("name", "")

            # Get Gitee author login (handle null author field)
            author_obj = commit_summary.get("author")
            author_login = author_obj.get("login", "") if author_obj else ""

            # Check if commit is by this user (case-insensitive match)
            if commit_author.lower() == username.lower() or \
               author_login.lower() == username.lower():

                try:
                    # Fetch detailed commit with files and diffs
                    commit_data = gitee_collector.fetch_commit_data(owner, repo, commit_sha, use_cache=use_cache, is_enterprise=is_enterprise)
                    detailed_commits.append(commit_data)

                    # Stop if we have enough commits
                    if len(detailed_commits) >= limit:
                        break
                except Exception as e:
                    print(f"[Warning] Failed to fetch commit {commit_sha}: {e}")
                    continue

        if not detailed_commits:
            return {
                "success": False,
                "error": f"No commits found for user {username} in {owner}/{repo}",
                "evaluation": commit_evaluator._get_empty_evaluation(username)
            }

        # Evaluate using LLM
        evaluation = commit_evaluator.evaluate_engineer(detailed_commits, username)

        # Save evaluation to cache for future use
        _save_gitee_evaluation_to_cache(owner, repo, username, evaluation)

        return {
            "success": True,
            "evaluation": evaluation,
            "metadata": {
                "owner": owner,
                "repo": repo,
                "username": username,
                "commits_analyzed": len(detailed_commits),
                "cached": False
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gitee/collaborators/{owner}/{repo}")
async def get_gitee_collaborators(
    owner: str,
    repo: str,
    use_cache: bool = Query(True, description="Whether to use cached data"),
    is_enterprise: bool = Query(False, description="Whether this is an enterprise (z.gitee.cn) repository")
):
    """
    Get list of collaborators/members from a Gitee repository

    This endpoint fetches the list of repository collaborators (members) using
    the Gitee API /repos/{owner}/{repo}/collaborators endpoint. This is useful
    for repositories where contributor information is not available in the
    commit data.

    Args:
        owner: Repository owner
        repo: Repository name
        use_cache: Whether to use cache (default: True)
        is_enterprise: Whether this is an enterprise repository (default: False)

    Returns:
        List of collaborators with their information
    """
    try:
        collaborators = gitee_collector.fetch_collaborators(owner, repo, use_cache=use_cache, is_enterprise=is_enterprise)

        cache_path = gitee_collector._get_collaborators_cache_path(owner, repo)
        is_cached = cache_path.exists()

        return {
            "success": True,
            "data": collaborators,
            "metadata": {
                "owner": owner,
                "repo": repo,
                "count": len(collaborators),
                "cached": is_cached,
                "cache_path": str(cache_path) if is_cached else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gitee/contributors/{owner}/{repo}")
async def get_gitee_contributors_from_commits(
    owner: str,
    repo: str,
    limit: int = Query(100, description="Maximum number of commits to analyze"),
    use_cache: bool = Query(True, description="Whether to use cached commit data"),
    is_enterprise: bool = Query(False, description="Whether this is an enterprise (z.gitee.cn) repository")
):
    """
    Extract contributors from commit data (commit.author.name and commit.committer.name)

    This endpoint analyzes commits to extract contributors based on the
    commit.author.name and commit.committer.name fields. This is useful for
    Gitee repositories where the top-level author/committer fields are null,
    but the commit metadata still contains author information.

    Unlike /collaborators which gets official repository members, this endpoint
    shows who actually made commits to the repository.

    Args:
        owner: Repository owner
        repo: Repository name
        limit: Maximum number of commits to analyze (default: 100)
        use_cache: Whether to use cached commit data (default: True)
        is_enterprise: Whether this is an enterprise repository (default: False)

    Returns:
        List of contributors extracted from commits with their commit counts
    """
    try:
        # Fetch commits list
        commits_list = gitee_collector.fetch_commits_list(owner, repo, limit=limit, use_cache=use_cache, is_enterprise=is_enterprise)

        # Extract contributors from commit.author.name and commit.committer.name
        from collections import Counter

        authors = []
        committers = []
        author_emails = {}
        committer_emails = {}

        for commit in commits_list:
            commit_obj = commit.get("commit", {})

            # Extract author info
            author_info = commit_obj.get("author", {})
            author_name = author_info.get("name")
            author_email = author_info.get("email")

            # Extract committer info
            committer_info = commit_obj.get("committer", {})
            committer_name = committer_info.get("name")
            committer_email = committer_info.get("email")

            if author_name:
                authors.append(author_name)
                author_emails[author_name] = author_email
            if committer_name:
                committers.append(committer_name)
                committer_emails[committer_name] = committer_email

        # Count contributions
        author_counts = Counter(authors)
        committer_counts = Counter(committers)

        # Create contributor list
        contributors = []

        # Combine authors and committers
        all_names = set(authors + committers)
        for name in all_names:
            contributors.append({
                "name": name,
                "author_commits": author_counts.get(name, 0),
                "committer_commits": committer_counts.get(name, 0),
                "total_commits": author_counts.get(name, 0) + committer_counts.get(name, 0),
                "email": author_emails.get(name) or committer_emails.get(name)
            })

        # Sort by total commits
        contributors.sort(key=lambda x: x["total_commits"], reverse=True)

        return {
            "success": True,
            "data": contributors,
            "metadata": {
                "owner": owner,
                "repo": repo,
                "commits_analyzed": len(commits_list),
                "unique_contributors": len(contributors),
                "unique_authors": len(author_counts),
                "unique_committers": len(committer_counts)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GITEE CACHE MANAGEMENT
# ============================================================================

def _get_gitee_evaluation_cache_path(owner: str, repo: str, username: str) -> Path:
    """Get the cache path for a Gitee evaluation result"""
    cache_dir = Path("data") / "gitee" / owner / repo / "evaluations"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{username}.json"


def _load_gitee_evaluation_from_cache(owner: str, repo: str, username: str) -> Optional[Dict[str, Any]]:
    """Load Gitee evaluation result from cache"""
    cache_path = _get_gitee_evaluation_cache_path(owner, repo, username)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
            print(f"[Cache Hit] Loaded Gitee evaluation for {username} from cache")
            return cached_data
    except Exception as e:
        print(f"[Cache Error] Failed to load Gitee evaluation cache: {e}")
        return None


def _save_gitee_evaluation_to_cache(owner: str, repo: str, username: str, evaluation: Dict[str, Any]) -> None:
    """Save Gitee evaluation result to cache"""
    cache_path = _get_gitee_evaluation_cache_path(owner, repo, username)

    try:
        cache_data = {
            "cached_at": datetime.now().isoformat(),
            "owner": owner,
            "repo": repo,
            "username": username,
            "evaluation": evaluation
        }

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)

        print(f"[Cache Save] Saved Gitee evaluation for {username} to cache")
    except Exception as e:
        print(f"[Cache Error] Failed to save Gitee evaluation cache: {e}")


@app.delete("/api/cache/gitee/repo/{owner}/{repo}")
async def clear_gitee_repo_cache(owner: str, repo: str):
    """Clear cache for a specific Gitee repository"""
    try:
        repo_url = f"https://gitee.com/{owner}/{repo}"
        cache_path = gitee_collector._get_cache_path(repo_url)

        if cache_path.exists():
            cache_path.unlink()
            return {
                "success": True,
                "message": f"Cache cleared for Gitee {owner}/{repo}",
                "cache_path": str(cache_path)
            }
        else:
            return {
                "success": False,
                "message": f"No cache found for Gitee {owner}/{repo}"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cache/gitee/user/{username}")
async def clear_gitee_user_cache(username: str):
    """Clear cache for a specific Gitee user"""
    try:
        user_url = f"https://gitee.com/{username}"
        cache_path = gitee_collector._get_cache_path(user_url)

        if cache_path.exists():
            cache_path.unlink()
            return {
                "success": True,
                "message": f"Cache cleared for Gitee user {username}",
                "cache_path": str(cache_path)
            }
        else:
            return {
                "success": False,
                "message": f"No cache found for Gitee user {username}"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cache/gitee/evaluation/{owner}/{repo}/{username}")
async def clear_gitee_evaluation_cache(owner: str, repo: str, username: str):
    """Clear cached Gitee evaluation for a specific user in a repository"""
    try:
        cache_path = _get_gitee_evaluation_cache_path(owner, repo, username)

        if cache_path.exists():
            cache_path.unlink()
            return {
                "success": True,
                "message": f"Gitee evaluation cache cleared for {username} in {owner}/{repo}",
                "cache_path": str(cache_path)
            }
        else:
            return {
                "success": False,
                "message": f"No Gitee evaluation cache found for {username} in {owner}/{repo}"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache_enabled": True,
        "github_token_configured": github_token is not None,
        "gitee_token_configured": gitee_token is not None,
        "public_gitee_token_configured": public_gitee_token is not None,
        "llm_configured": openrouter_key is not None
    }


def find_available_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """
    Find an available port starting from start_port

    Args:
        start_port: Port to start checking from
        max_attempts: Maximum number of ports to try

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found
    """
    import socket

    for port in range(start_port, start_port + max_attempts):
        try:
            # Try to bind to the port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
                return port
        except OSError:
            # Port is in use, try next one
            continue

    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts - 1}")


if __name__ == "__main__":
    import uvicorn

    # Get port from environment variable or find available port
    try:
        port = int(os.getenv("PORT", "8000"))
    except ValueError:
        port = 8000

    # Find available port if specified port is in use
    try:
        available_port = find_available_port(port, max_attempts=10)
    except RuntimeError as e:
        print(f"Error: {e}")
        exit(1)

    if available_port != port:
        print(f"Port {port} is in use, using port {available_port} instead")

    print("=" * 60)
    print("Starting GitHub Data Collector API Server")
    print("=" * 60)
    print(f"Server URL: http://localhost:{available_port}")
    print(f"API Documentation: http://localhost:{available_port}/docs")
    print(f"Health Check: http://localhost:{available_port}/health")
    print(f"Cache directory: data/")
    print(f"GitHub token configured: {github_token is not None}")
    print(f"Hot reload: enabled")
    print("=" * 60)

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=available_port,
        log_level="info",
        reload=True
    )
