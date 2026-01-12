#!/usr/bin/env python3
"""
FastAPI Backend for Engineer Skill Evaluator
Integrates CommitEvaluatorModerate with dashboard.html
"""

import os
import json
import subprocess
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

# Evaluation cache directory
EVAL_CACHE_DIR = Path("evaluations/cache")
EVAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Data directory
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

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


def get_evaluation_cache_path(owner: str, repo: str) -> Path:
    """Get path to evaluation cache file"""
    cache_dir = EVAL_CACHE_DIR / owner / repo
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "evaluations.json"


def load_evaluation_cache(owner: str, repo: str) -> Optional[Dict[str, Any]]:
    """Load evaluation cache for repository"""
    cache_path = get_evaluation_cache_path(owner, repo)
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠ Failed to load evaluation cache: {e}")
    return None


def save_evaluation_cache(owner: str, repo: str, evaluations: Dict[str, Any]):
    """Save evaluation cache for repository"""
    cache_path = get_evaluation_cache_path(owner, repo)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(evaluations, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved evaluation cache to {cache_path}")
    except Exception as e:
        print(f"⚠ Failed to save evaluation cache: {e}")


def add_evaluation_to_cache(owner: str, repo: str, author: str, evaluation: Dict[str, Any]):
    """Add or update evaluation for a specific author in cache"""
    cache = load_evaluation_cache(owner, repo) or {}
    cache[author] = {
        "evaluation": evaluation,
        "timestamp": datetime.now().isoformat(),
        "cached": True
    }
    save_evaluation_cache(owner, repo, cache)


def extract_github_data(owner: str, repo: str) -> bool:
    """Extract GitHub repository data using extraction tool"""
    try:
        repo_url = f"https://github.com/{owner}/{repo}"
        output_dir = DATA_DIR / owner / repo

        print(f"\n{'='*60}")
        print(f"Extracting GitHub data for {owner}/{repo}...")
        print(f"{'='*60}")

        # Construct command
        cmd = [
            "python3",
            "tools/extract_repo_data_moderate.py",
            "--repo-url", repo_url,
            "--out", str(output_dir),
            "--max-commits", "0"  # 0 = fetch all commits
        ]

        if GITHUB_TOKEN:
            cmd.extend(["--token", GITHUB_TOKEN])

        # Run extraction tool
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            print(f"✗ Extraction failed: {result.stderr}")
            return False

        print(f"✓ Extraction successful")
        print(result.stdout)
        return True

    except subprocess.TimeoutExpired:
        print(f"✗ Extraction timeout after 5 minutes")
        return False
    except Exception as e:
        print(f"✗ Extraction error: {e}")
        import traceback
        traceback.print_exc()
        return False


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


def load_commits_from_local(data_dir: Path, limit: int = None) -> List[Dict[str, Any]]:
    """
    Load commits from local extracted data

    Args:
        data_dir: Path to data directory (e.g., data/owner/repo)
        limit: Maximum commits to load (None = all commits)

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

    # Apply limit if specified
    commits_to_load = commits_index if limit is None else commits_index[:limit]

    for commit_info in commits_to_load:
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

    print(f"[Info] Loaded {len(commits)} commit details")
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


@app.get("/api/authors/{owner}/{repo}")
async def get_authors(owner: str, repo: str, use_cache: bool = Query(True)):
    """
    Get list of authors from commit data with smart caching

    Flow:
    1. Check if evaluations exist in cache - if yes, return cached data
    2. Check if local data exists in data/{owner}/{repo}
    3. If no local data, extract it from GitHub
    4. Load all authors from commits
    5. Evaluate first author automatically
    6. Cache and return results
    """
    try:
        data_dir = DATA_DIR / owner / repo

        # Step 1: Check evaluation cache first and validate
        if use_cache:
            cached_evaluations = load_evaluation_cache(owner, repo)
            if cached_evaluations:
                print(f"✓ Found cached evaluations for {owner}/{repo}")

                # Validate cache: check if different authors have identical stats (corrupted)
                cache_valid = True
                if len(cached_evaluations) > 1:
                    # Get stats from all evaluations
                    eval_stats = []
                    for author, eval_data in cached_evaluations.items():
                        evaluation = eval_data.get("evaluation", {})
                        summary = evaluation.get("commits_summary", {})
                        eval_stats.append({
                            "author": author,
                            "total_commits": evaluation.get("total_commits_analyzed", 0),
                            "additions": summary.get("total_additions", 0),
                            "deletions": summary.get("total_deletions", 0),
                            "files": summary.get("files_changed", 0)
                        })

                    # Check for duplicates
                    for i in range(len(eval_stats)):
                        for j in range(i + 1, len(eval_stats)):
                            if (eval_stats[i]["total_commits"] == eval_stats[j]["total_commits"] and
                                eval_stats[i]["additions"] == eval_stats[j]["additions"] and
                                eval_stats[i]["deletions"] == eval_stats[j]["deletions"] and
                                eval_stats[i]["files"] == eval_stats[j]["files"]):
                                print(f"⚠ Cache validation failed: {eval_stats[i]['author']} and {eval_stats[j]['author']} have identical stats")
                                print(f"  Clearing corrupted cache...")
                                cache_valid = False
                                cache_path = get_evaluation_cache_path(owner, repo)
                                if cache_path.exists():
                                    cache_path.unlink()
                                break
                        if not cache_valid:
                            break

                if cache_valid:
                    # Extract authors list from cache
                    authors_list = []
                    for author, eval_data in cached_evaluations.items():
                        evaluation = eval_data.get("evaluation", {})
                        authors_list.append({
                            "author": author,
                            "email": evaluation.get("email", ""),
                            "commits": evaluation.get("total_commits_analyzed", 0)
                        })

                    # Sort by commits
                    authors_list.sort(key=lambda x: x["commits"], reverse=True)

                    return {
                        "success": True,
                        "data": {
                            "owner": owner,
                            "repo": repo,
                            "authors": authors_list,
                            "total_authors": len(authors_list),
                            "cached": True
                        }
                    }

        # Step 2 & 3: Check if local data exists, if not extract it
        if not data_dir.exists() or not (data_dir / "commits").exists():
            print(f"No local data found for {owner}/{repo}, extracting from GitHub...")

            success = extract_github_data(owner, repo)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to extract GitHub data for {owner}/{repo}"
                )

        # Step 4: Load all authors from commits
        commits_dir = data_dir / "commits"
        if not commits_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No commit data found for {owner}/{repo}"
            )

        authors_map = {}

        # Check for direct .json files in commits directory
        for commit_file in commits_dir.glob("*.json"):
            try:
                with open(commit_file, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    author = get_author_from_commit(commit_data)

                    # Get email from commit data
                    email = ""
                    if "commit" in commit_data:
                        email = commit_data.get("commit", {}).get("author", {}).get("email", "")

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
            raise HTTPException(
                status_code=404,
                detail=f"No commit authors found in {commits_dir}"
            )

        # Sort by commit count
        authors_list = sorted(
            authors_map.values(),
            key=lambda x: x["commits"],
            reverse=True
        )

        # Step 5: Evaluate first author automatically
        first_author = authors_list[0]["author"]
        print(f"\nAuto-evaluating first author: {first_author}")

        try:
            # Create evaluator
            api_key = os.getenv("OPEN_ROUTER_KEY")
            if not api_key:
                raise HTTPException(status_code=500, detail="OPEN_ROUTER_KEY not configured")

            evaluator = CommitEvaluatorModerate(
                data_dir=str(data_dir),
                api_key=api_key,
                mode="moderate"
            )

            # Load ALL commits
            commits = load_commits_from_local(data_dir, limit=None)
            if commits:
                # Evaluate first author with all their commits
                evaluation = evaluator.evaluate_engineer(
                    commits=commits,
                    username=first_author,
                    max_commits=None,  # Evaluate all commits
                    load_files=True,
                    use_chunking=True  # Enable chunked evaluation
                )

                if evaluation and "scores" in evaluation:
                    # Add email to evaluation
                    evaluation["email"] = authors_list[0]["email"]

                    # Cache the evaluation
                    add_evaluation_to_cache(owner, repo, first_author, evaluation)
                    print(f"✓ Cached evaluation for {first_author}")

        except Exception as e:
            print(f"⚠ Failed to auto-evaluate first author: {e}")
            # Continue even if evaluation fails

        return {
            "success": True,
            "data": {
                "owner": owner,
                "repo": repo,
                "authors": authors_list,
                "total_authors": len(authors_list),
                "cached": False
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Failed to get authors: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get authors: {str(e)}")


@app.post("/api/evaluate/{owner}/{repo}/{author}")
async def evaluate_author(
    owner: str,
    repo: str,
    author: str,
    use_cache: bool = Query(True),
    use_chunking: bool = Query(True)
):
    """
    Evaluate an author using local commit data with caching

    This endpoint evaluates ALL commits from the author. If there are many commits,
    it automatically uses chunked evaluation with accumulative context.

    Flow:
    1. Check if evaluation exists in cache
    2. If cached and use_cache=True, return cached result
    3. Otherwise, load ALL commits and perform evaluation
    4. Use chunked evaluation if needed (automatic for >20 commits)
    5. Cache the result
    6. Return evaluation

    Args:
        owner: Repository owner
        repo: Repository name
        author: Author/username to evaluate
        use_cache: Whether to use cached evaluation if available
        use_chunking: Whether to enable chunked evaluation for large commit sets
    """
    try:
        # Step 1 & 2: Check cache first and validate
        if use_cache:
            cached_evaluations = load_evaluation_cache(owner, repo)
            if cached_evaluations and author in cached_evaluations:
                cached_data = cached_evaluations[author]
                cached_eval = cached_data.get("evaluation", {})

                # Validate cached data to prevent serving corrupted cache
                # Check if cache was created with buggy code (all authors having same stats)
                cache_valid = True
                if len(cached_evaluations) > 1:
                    # Compare with other cached evaluations
                    for other_author, other_data in cached_evaluations.items():
                        if other_author != author:
                            other_eval = other_data.get("evaluation", {})
                            other_summary = other_eval.get("commits_summary", {})
                            current_summary = cached_eval.get("commits_summary", {})

                            # If two different authors have IDENTICAL stats, cache is corrupted
                            if (other_summary.get("total_additions") == current_summary.get("total_additions") and
                                other_summary.get("total_deletions") == current_summary.get("total_deletions") and
                                other_summary.get("files_changed") == current_summary.get("files_changed") and
                                other_eval.get("total_commits_analyzed") == cached_eval.get("total_commits_analyzed")):
                                print(f"⚠ Cache validation failed: {author} and {other_author} have identical stats")
                                print(f"  This indicates corrupted cache data. Clearing cache and re-evaluating...")
                                cache_valid = False
                                break

                if cache_valid:
                    print(f"✓ Using validated cached evaluation for {author}")
                    return {
                        "success": True,
                        "evaluation": cached_data["evaluation"],
                        "metadata": {
                            "cached": True,
                            "timestamp": cached_data.get("timestamp", datetime.now().isoformat()),
                            "source": "cache"
                        }
                    }
                else:
                    # Clear corrupted cache and continue to re-evaluate
                    print(f"Clearing corrupted cache for {owner}/{repo}")
                    cache_path = get_evaluation_cache_path(owner, repo)
                    if cache_path.exists():
                        cache_path.unlink()

        # Step 3: Perform evaluation
        data_dir = DATA_DIR / owner / repo

        if not data_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No local data found for {owner}/{repo}"
            )

        # Create evaluator
        api_key = os.getenv("OPEN_ROUTER_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPEN_ROUTER_KEY not configured")

        evaluator = CommitEvaluatorModerate(
            data_dir=str(data_dir),
            api_key=api_key,
            mode="moderate"
        )

        # Load ALL commits from local data (no limit)
        print(f"\n[Evaluation] Loading all commits for {author}...")
        commits = load_commits_from_local(data_dir, limit=None)
        if not commits:
            raise HTTPException(
                status_code=404,
                detail=f"No commits found in local data for {owner}/{repo}"
            )

        print(f"[Evaluation] Loaded {len(commits)} total commits")

        # Evaluate author using moderate evaluator with chunking enabled
        # The evaluator will automatically chunk if there are >20 commits
        evaluation = evaluator.evaluate_engineer(
            commits=commits,
            username=author,
            max_commits=None,  # Evaluate ALL commits
            load_files=True,
            use_chunking=use_chunking
        )

        if not evaluation or "scores" not in evaluation:
            raise HTTPException(
                status_code=404,
                detail=f"Author '{author}' not found in commits"
            )

        # Step 4: Cache the evaluation
        add_evaluation_to_cache(owner, repo, author, evaluation)

        # Step 5: Format and return response
        result = {
            "success": True,
            "evaluation": {
                "username": evaluation.get("username", author),
                "mode": evaluation.get("mode", "moderate"),
                "total_commits_analyzed": evaluation.get("total_commits_analyzed", 0),
                "files_loaded": evaluation.get("files_loaded", 0),
                "chunked": evaluation.get("chunked", False),
                "chunks_processed": evaluation.get("chunks_processed", 0),
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
