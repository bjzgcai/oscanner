#!/usr/bin/env python3
"""
FastAPI Backend for Engineer Skill Evaluator
Integrates CommitEvaluatorModerate with dashboard.html
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Import evaluator
from commit_evaluator_moderate import CommitEvaluatorModerate

app = FastAPI(title="Engineer Skill Evaluator API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache directory for commits
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# Repository evaluators cache (in-memory)
# Key: "{platform}_{owner}_{repo}", Value: CommitEvaluatorModerate instance
evaluators_cache: Dict[str, CommitEvaluatorModerate] = {}

# GitHub/Gitee API tokens
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITEE_TOKEN = os.getenv("GITEE_TOKEN")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Engineer Skill Evaluator"}


def get_cache_key(platform: str, owner: str, repo: str) -> str:
    """Generate cache key for repository"""
    return f"{platform}_{owner}_{repo}"


def get_commits_cache_path(platform: str, owner: str, repo: str) -> Path:
    """Get cache file path for commits"""
    cache_key = get_cache_key(platform, owner, repo)
    return CACHE_DIR / f"{cache_key}_commits.json"


def load_commits_cache(platform: str, owner: str, repo: str) -> Optional[list]:
    """Load commits from cache"""
    cache_path = get_commits_cache_path(platform, owner, repo)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
            print(f"✓ Using cached commits")
            return cached_data.get('commits', [])
    except Exception as e:
        print(f"⚠ Failed to load commits cache: {e}")
        return None


def load_commits_from_local(data_dir: Path, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Load commits from local extracted data

    Args:
        data_dir: Path to data directory (e.g., data/owner/repo)
        limit: Maximum commits to load

    Returns:
        List of commit data
    """
    commits_index_path = data_dir / "commits_index.json"

    if not commits_index_path.exists():
        print(f"[Warning] Commits index not found: {commits_index_path}")
        return []

    # Load commits index
    with open(commits_index_path, 'r', encoding='utf-8') as f:
        commits_index = json.load(f)

    print(f"[Info] Found {len(commits_index)} commits in index")

    # Load detailed commit data
    commits = []
    commits_dir = data_dir / "commits"

    for commit_info in commits_index[:limit]:
        commit_sha = commit_info.get("hash") or commit_info.get("sha")

        if not commit_sha:
            continue

        # Try to load commit JSON
        commit_json_path = commits_dir / f"{commit_sha}.json"

        if commit_json_path.exists():
            try:
                with open(commit_json_path, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    commits.append(commit_data)
            except Exception as e:
                print(f"[Warning] Failed to load {commit_sha}: {e}")

    return commits


def fetch_github_commits(owner: str, repo: str, limit: int = 100) -> list:
    """Fetch commits from GitHub API"""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    params = {"per_page": min(limit, 100)}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch GitHub commits: {str(e)}")


def fetch_gitee_commits(owner: str, repo: str, limit: int = 100, is_enterprise: bool = False) -> list:
    """Fetch commits from Gitee API"""
    if is_enterprise:
        url = f"https://api.gitee.com/enterprises/{owner}/repos/{repo}/commits"
    else:
        url = f"https://api.gitee.com/repos/{owner}/{repo}/commits"

    headers = {}
    if GITEE_TOKEN:
        headers["Authorization"] = f"token {GITEE_TOKEN}"

    params = {"per_page": min(limit, 100)}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Gitee commits: {str(e)}")


@app.get("/api/commits/{owner}/{repo}")
async def get_commits(
    owner: str,
    repo: str,
    limit: int = Query(100, ge=1, le=100),
    use_cache: bool = Query(True)
):
    """Fetch commits for a GitHub repository"""
    platform = "github"

    # Check cache if enabled
    if use_cache:
        cached_commits = load_commits_cache(platform, owner, repo)
        if cached_commits:
            return {
                "success": True,
                "data": cached_commits[:limit],
                "cached": True
            }

    # Fetch from GitHub API
    commits = fetch_github_commits(owner, repo, limit)

    # Save to cache
    save_commits_cache(platform, owner, repo, commits)

    return {
        "success": True,
        "data": commits,
        "cached": False
    }


@app.get("/api/gitee/commits/{owner}/{repo}")
async def get_gitee_commits(
    owner: str,
    repo: str,
    limit: int = Query(100, ge=1, le=100),
    use_cache: bool = Query(True),
    is_enterprise: bool = Query(False)
):
    """Fetch commits for a Gitee repository"""
    platform = "gitee"

    # Check cache if enabled
    if use_cache:
        cached_commits = load_commits_cache(platform, owner, repo)
        if cached_commits:
            return {
                "success": True,
                "data": cached_commits[:limit],
                "cached": True
            }

    # Fetch from Gitee API
    commits = fetch_gitee_commits(owner, repo, limit, is_enterprise)

    # Save to cache
    save_commits_cache(platform, owner, repo, commits)

    return {
        "success": True,
        "data": commits,
        "cached": False
    }


def get_author_from_commit(commit_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract author name from commit data, supporting both formats:
    1. GitHub API format: commit_data["commit"]["author"]["name"]
    2. Custom extraction format: commit_data["author"]
    """
    # Try custom extraction format first (more common in local data)
    if "author" in commit_data and isinstance(commit_data["author"], str):
        return commit_data["author"]

    # Try GitHub API format
    if "commit" in commit_data:
        author = commit_data.get("commit", {}).get("author", {}).get("name")
        if author:
            return author

    return None


def get_data_dir(platform: str, owner: str, repo: str) -> Path:
    """Get or create data directory for repository"""
    data_dir = Path("data") / owner / repo
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_or_create_evaluator(
    platform: str,
    owner: str,
    repo: str,
    commits: list,
    use_cache: bool = True
) -> CommitEvaluatorModerate:
    """
    Get or create evaluator for repository
    Caches evaluator instance to reuse repository context
    """
    cache_key = get_cache_key(platform, owner, repo)

    # Return cached evaluator if exists
    if use_cache and cache_key in evaluators_cache:
        print(f"✓ Reusing cached evaluator for {owner}/{repo}")
        return evaluators_cache[cache_key]

    # Prepare data directory
    data_dir = get_data_dir(platform, owner, repo)

    # Create commits_index.json
    commits_index = [
        {
            "sha": c.get("sha"),
            "hash": c.get("sha"),
        }
        for c in commits
    ]
    with open(data_dir / "commits_index.json", 'w') as f:
        json.dump(commits_index, f, indent=2)

    # Save individual commits
    commits_dir = data_dir / "commits"
    commits_dir.mkdir(exist_ok=True)
    for commit in commits:
        sha = commit.get("sha")
        if sha:
            with open(commits_dir / f"{sha}.json", 'w') as f:
                json.dump(commit, f, indent=2)

    # Create repo_info.json
    repo_info = {
        "name": f"{owner}/{repo}",
        "full_name": f"{owner}/{repo}",
        "owner": owner,
        "platform": platform,
    }
    with open(data_dir / "repo_info.json", 'w') as f:
        json.dump(repo_info, f, indent=2)

    # Create evaluator with moderate mode
    api_key = os.getenv("OPEN_ROUTER_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPEN_ROUTER_KEY not configured")

    evaluator = CommitEvaluatorModerate(
        data_dir=str(data_dir),
        api_key=api_key,
        mode="moderate"
    )

    # Cache the evaluator
    evaluators_cache[cache_key] = evaluator

    print(f"✓ Created new evaluator for {owner}/{repo}")
    return evaluator


@app.get("/api/local/authors/{owner}/{repo}")
async def get_local_authors(owner: str, repo: str):
    """
    Get list of authors from local commit data
    Reads from data/{owner}/{repo}/commits/*.json files
    """
    try:
        data_dir = Path("data") / owner / repo
        commits_dir = data_dir / "commits"

        if not commits_dir.exists():
            raise HTTPException(status_code=404, detail=f"No local data found for {owner}/{repo}")

        # Collect authors from all commit.json files
        authors_map = {}

        # Look for commit directories (hash-based structure)
        for commit_hash_dir in commits_dir.iterdir():
            if commit_hash_dir.is_dir():
                commit_file = commit_hash_dir / f"{commit_hash_dir.name}.json"
                if commit_file.exists():
                    try:
                        with open(commit_file, 'r', encoding='utf-8') as f:
                            commit_data = json.load(f)
                            author = get_author_from_commit(commit_data)
                            email = commit_data.get("email", "")

                            if author:
                                if author not in authors_map:
                                    authors_map[author] = {
                                        "author": author,
                                        "email": email,
                                        "commits": 0
                                    }
                                authors_map[author]["commits"] += 1
                    except Exception as e:
                        print(f"⚠ Error reading {commit_file}: {e}")
                        continue

        # Also check for direct .json files in commits directory (alternative structure)
        for commit_file in commits_dir.glob("*.json"):
            try:
                with open(commit_file, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    author = get_author_from_commit(commit_data)
                    email = commit_data.get("email", "")

                    if author:
                        if author not in authors_map:
                            authors_map[author] = {
                                "author": author,
                                "email": email,
                                "commits": 0
                            }
                        authors_map[author]["commits"] += 1
            except Exception as e:
                print(f"⚠ Error reading {commit_file}: {e}")
                continue

        if not authors_map:
            raise HTTPException(status_code=404, detail=f"No commit data found in {commits_dir}")

        # Sort by commit count
        authors_list = sorted(
            authors_map.values(),
            key=lambda x: x["commits"],
            reverse=True
        )

        return {
            "success": True,
            "data": {
                "owner": owner,
                "repo": repo,
                "authors": authors_list,
                "total_authors": len(authors_list)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Failed to get local authors: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get authors: {str(e)}")


@app.post("/api/local/evaluate/{owner}/{repo}/{author}")
async def evaluate_local_author(
    owner: str,
    repo: str,
    author: str,
    limit: int = Query(30, ge=1, le=100),
    use_cache: bool = Query(True)
):
    """
    Evaluate an author using local commit data only
    No GitHub/Gitee API calls - works entirely with local data
    """
    try:
        data_dir = Path("data") / owner / repo

        if not data_dir.exists():
            raise HTTPException(status_code=404, detail=f"No local data found for {owner}/{repo}")

        # For local evaluation, directly create evaluator without modifying existing data
        cache_key = f"local_{owner}_{repo}"

        # Create evaluator
        api_key = os.getenv("OPEN_ROUTER_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPEN_ROUTER_KEY not configured")

        evaluator = CommitEvaluatorModerate(
            data_dir=str(data_dir),
            api_key=api_key,
            mode="moderate"
        )

        # Load commits from local data
        commits = load_commits_from_local(data_dir, limit=limit)
        if not commits:
            raise HTTPException(status_code=404, detail=f"No commits found in local data for {owner}/{repo}")

        # Evaluate author using moderate evaluator
        evaluation = evaluator.evaluate_engineer(
            commits=commits,
            username=author,
            max_commits=limit,
            load_files=True
        )

        if not evaluation or "scores" not in evaluation:
            raise HTTPException(status_code=404, detail=f"Author '{author}' not found in commits")

        # Format response for dashboard
        # The moderate evaluator already provides all the information we need
        result = {
            "success": True,
            "evaluation": {
                "username": evaluation.get("username", author),
                "mode": evaluation.get("mode", "moderate"),
                "total_commits_analyzed": evaluation.get("total_commits_analyzed", 0),
                "files_loaded": evaluation.get("files_loaded", 0),
                "scores": evaluation.get("scores", {}),
                "commits_summary": evaluation.get("commits_summary", {})
            },
            "metadata": {
                "cached": False,
                "timestamp": datetime.now().isoformat(),
                "source": "local_data"
            }
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Local evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Local evaluation failed: {str(e)}")


@app.post("/api/evaluate/{owner}/{repo}/{contributor}")
async def evaluate_contributor(
    owner: str,
    repo: str,
    contributor: str,
    limit: int = Query(30, ge=1, le=100),
    use_cache: bool = Query(True),
    is_enterprise: bool = Query(False)
):
    """
    Evaluate a contributor using full repository context

    Strategy:
    1. First request: Load repo data, cache evaluator, evaluate contributor, cache result
    2. Same contributor: Return cached evaluation
    3. Different contributor: Reuse cached evaluator (repo context), evaluate new contributor
    """
    platform = "github"

    try:
        # 1. Get commits (from cache or API)
        if use_cache:
            commits = load_commits_cache(platform, owner, repo)
            if not commits:
                commits = fetch_github_commits(owner, repo, 100)
                save_commits_cache(platform, owner, repo, commits)
        else:
            commits = fetch_github_commits(owner, repo, 100)
            save_commits_cache(platform, owner, repo, commits)

        # 2. Get or create evaluator (reuses repo context if cached)
        evaluator = get_or_create_evaluator(platform, owner, repo, commits, use_cache)

        # 3. Evaluate contributor using moderate evaluator
        evaluation = evaluator.evaluate_engineer(
            commits=commits,
            username=contributor,
            max_commits=limit,
            load_files=True
        )

        if not evaluation or "scores" not in evaluation:
            raise HTTPException(status_code=404, detail=f"Contributor '{contributor}' not found")

        # Format response for dashboard
        # The moderate evaluator already returns the correct structure
        result = {
            "success": True,
            "evaluation": {
                "username": evaluation.get("username", contributor),
                "mode": evaluation.get("mode", "moderate"),
                "total_commits_analyzed": evaluation.get("total_commits_analyzed", 0),
                "files_loaded": evaluation.get("files_loaded", 0),
                "scores": evaluation.get("scores", {}),
                "commits_summary": evaluation.get("commits_summary", {})
            },
            "metadata": {
                "cached": False,
                "timestamp": datetime.now().isoformat()
            }
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@app.post("/api/gitee/evaluate/{owner}/{repo}/{contributor}")
async def evaluate_gitee_contributor(
    owner: str,
    repo: str,
    contributor: str,
    limit: int = Query(30, ge=1, le=100),
    use_cache: bool = Query(True),
    is_enterprise: bool = Query(False)
):
    """Evaluate a Gitee contributor using full repository context"""
    platform = "gitee"

    try:
        # 1. Get commits (from cache or API)
        if use_cache:
            commits = load_commits_cache(platform, owner, repo)
            if not commits:
                commits = fetch_gitee_commits(owner, repo, 100, is_enterprise)
                save_commits_cache(platform, owner, repo, commits)
        else:
            commits = fetch_gitee_commits(owner, repo, 100, is_enterprise)
            save_commits_cache(platform, owner, repo, commits)

        # 2. Get or create evaluator (reuses repo context if cached)
        evaluator = get_or_create_evaluator(platform, owner, repo, commits, use_cache)

        # 3. Evaluate contributor using moderate evaluator
        evaluation = evaluator.evaluate_engineer(
            commits=commits,
            username=contributor,
            max_commits=limit,
            load_files=True
        )

        if not evaluation or "scores" not in evaluation:
            raise HTTPException(status_code=404, detail=f"Contributor '{contributor}' not found")

        # Format response for dashboard
        # The moderate evaluator already returns the correct structure
        result = {
            "success": True,
            "evaluation": {
                "username": evaluation.get("username", contributor),
                "mode": evaluation.get("mode", "moderate"),
                "total_commits_analyzed": evaluation.get("total_commits_analyzed", 0),
                "files_loaded": evaluation.get("files_loaded", 0),
                "scores": evaluation.get("scores", {}),
                "commits_summary": evaluation.get("commits_summary", {})
            },
            "metadata": {
                "cached": False,
                "timestamp": datetime.now().isoformat()
            }
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


# NOTE: Score normalization endpoints disabled (ScoreNormalizer module removed)
# @app.get("/api/local/normalized/{owner}/{repo}")
# @app.get("/api/local/compare/{owner}/{repo}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    print(f"\n{'='*80}")
    print(f"🚀 Engineer Skill Evaluator API Server")
    print(f"{'='*80}")
    print(f"📍 Server: http://localhost:{port}")
    print(f"📊 Dashboard: Open dashboard.html in your browser")
    print(f"🏥 Health: http://localhost:{port}/health")
    print(f"📚 API Docs: http://localhost:{port}/docs")
    print(f"\n💡 Caching Strategy:")
    print(f"   • First request: Loads full repo context, evaluates contributor")
    print(f"   • Same repo: Reuses cached repo context")
    print(f"   • Same contributor: Returns cached evaluation")
    print(f"   • New contributor: Only evaluates new contributor (reuses repo)")
    print(f"{'='*80}\n")

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
