#!/usr/bin/env python3
"""
FastAPI Backend for Engineer Skill Evaluator
Integrates FullContextCachedEvaluator with dashboard.html
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Import evaluator
from evaluator.full_context_cached_evaluator import FullContextCachedEvaluator

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
# Key: "{platform}_{owner}_{repo}", Value: FullContextCachedEvaluator instance
evaluators_cache: Dict[str, FullContextCachedEvaluator] = {}

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


def save_commits_cache(platform: str, owner: str, repo: str, commits: list):
    """Save commits to cache"""
    cache_path = get_commits_cache_path(platform, owner, repo)

    cache_data = {
        "platform": platform,
        "owner": owner,
        "repo": repo,
        "cached_at": datetime.now().isoformat(),
        "commits": commits
    }

    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved commits to cache")
    except Exception as e:
        print(f"⚠ Failed to save commits cache: {e}")


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
) -> FullContextCachedEvaluator:
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

    # Create evaluator
    api_key = os.getenv("OPEN_ROUTER_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPEN_ROUTER_KEY not configured")

    evaluator = FullContextCachedEvaluator(data_dir=str(data_dir), api_key=api_key)

    # Cache the evaluator
    evaluators_cache[cache_key] = evaluator

    print(f"✓ Created new evaluator for {owner}/{repo}")
    return evaluator


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

        # 3. Evaluate contributor (uses cache if available)
        evaluation = evaluator.evaluate_contributor(
            contributor_name=contributor,
            use_cache=use_cache,
            force_refresh=not use_cache
        )

        if not evaluation or "evaluation" not in evaluation:
            raise HTTPException(status_code=404, detail=f"Contributor '{contributor}' not found")

        eval_data = evaluation.get("evaluation", {})

        # Filter contributor commits first
        contributor_commits = [c for c in commits if c.get("commit", {}).get("author", {}).get("name") == contributor][:limit]

        # Format response for dashboard
        result = {
            "success": True,
            "evaluation": {
                "username": contributor,
                "mode": "full_context",
                "total_commits_analyzed": len(contributor_commits),
                "scores": {
                    "ai_fullstack": eval_data.get("scores", {}).get("ai_fullstack", 0),
                    "ai_architecture": eval_data.get("scores", {}).get("ai_architecture", 0),
                    "cloud_native": eval_data.get("scores", {}).get("cloud_native", 0),
                    "open_source": eval_data.get("scores", {}).get("open_source", 0),
                    "intelligent_dev": eval_data.get("scores", {}).get("intelligent_dev", 0),
                    "leadership": eval_data.get("scores", {}).get("leadership", 0),
                    "reasoning": eval_data.get("reasoning", "")
                },
                "commits_summary": {
                    "total_additions": sum(c.get("stats", {}).get("additions", 0) for c in contributor_commits),
                    "total_deletions": sum(c.get("stats", {}).get("deletions", 0) for c in contributor_commits),
                    "files_changed": len(set(
                        f.get("filename")
                        for c in contributor_commits
                        for f in c.get("files", [])
                        if f.get("filename")
                    )),
                    "languages": list(set(
                        f.get("filename", "").split(".")[-1]
                        for c in contributor_commits
                        for f in c.get("files", [])
                        if "." in f.get("filename", "")
                    ))[:10]
                }
            },
            "metadata": {
                "cached": evaluation.get("cached_at") is not None,
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

        # 3. Evaluate contributor (uses cache if available)
        evaluation = evaluator.evaluate_contributor(
            contributor_name=contributor,
            use_cache=use_cache,
            force_refresh=not use_cache
        )

        if not evaluation or "evaluation" not in evaluation:
            raise HTTPException(status_code=404, detail=f"Contributor '{contributor}' not found")

        eval_data = evaluation.get("evaluation", {})

        # Filter contributor commits first
        contributor_commits = [c for c in commits if c.get("commit", {}).get("author", {}).get("name") == contributor][:limit]

        # Format response for dashboard
        result = {
            "success": True,
            "evaluation": {
                "username": contributor,
                "mode": "full_context",
                "total_commits_analyzed": len(contributor_commits),
                "scores": {
                    "ai_fullstack": eval_data.get("scores", {}).get("ai_fullstack", 0),
                    "ai_architecture": eval_data.get("scores", {}).get("ai_architecture", 0),
                    "cloud_native": eval_data.get("scores", {}).get("cloud_native", 0),
                    "open_source": eval_data.get("scores", {}).get("open_source", 0),
                    "intelligent_dev": eval_data.get("scores", {}).get("intelligent_dev", 0),
                    "leadership": eval_data.get("scores", {}).get("leadership", 0),
                    "reasoning": eval_data.get("reasoning", "")
                },
                "commits_summary": {
                    "total_additions": sum(c.get("stats", {}).get("additions", 0) for c in contributor_commits),
                    "total_deletions": sum(c.get("stats", {}).get("deletions", 0) for c in contributor_commits),
                    "files_changed": len(set(
                        f.get("filename")
                        for c in contributor_commits
                        for f in c.get("files", [])
                        if f.get("filename")
                    )),
                    "languages": list(set(
                        f.get("filename", "").split(".")[-1]
                        for c in contributor_commits
                        for f in c.get("files", [])
                        if "." in f.get("filename", "")
                    ))[:10]
                }
            },
            "metadata": {
                "cached": evaluation.get("cached_at") is not None,
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


if __name__ == "__main__":
    import uvicorn

    port = 8000
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

    uvicorn.run(app, host="0.0.0.0", port=port)
