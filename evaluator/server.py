#!/usr/bin/env python3
"""
FastAPI Backend for Engineer Skill Evaluator
Integrates CommitEvaluatorModerate with dashboard.html
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from evaluator.paths import ensure_dirs, get_cache_dir, get_data_dir, get_eval_cache_dir

# Load environment variables
if Path(".env.local").exists():
    load_dotenv(".env.local")
else:
    # fallback to default dotenv behavior (.env if present)
    load_dotenv()

# Import evaluator
from evaluator.commit_evaluator_moderate import CommitEvaluatorModerate

app = FastAPI(title="Engineer Skill Evaluator API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_dirs()

# Optional: serve bundled dashboard static files (exported Next.js build) if present.
def _try_mount_bundled_dashboard() -> bool:
    try:
        import oscanner  # the CLI package; may include dashboard_dist/

        dash_dir = Path(oscanner.__file__).resolve().parent / "dashboard_dist"
        if dash_dir.is_dir() and (dash_dir / "index.html").exists():
            # Mount AFTER API routes are registered (Starlette route order matters).
            # We mount at /dashboard to avoid conflicts with the API root.
            app.mount("/dashboard", StaticFiles(directory=str(dash_dir), html=True), name="dashboard")
            return True
    except Exception:
        return False
    return False

# Cache directory for commits (default: user cache dir)
CACHE_DIR = get_cache_dir()

# Evaluation cache directory (default: user data dir)
EVAL_CACHE_DIR = get_eval_cache_dir()

# Data directory (default: user data dir)
DATA_DIR = get_data_dir()

# Repository evaluators cache (in-memory)
# Key: "{platform}_{owner}_{repo}", Value: CommitEvaluatorModerate instance
evaluators_cache: Dict[str, CommitEvaluatorModerate] = {}

# GitHub/Gitee API tokens
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITEE_TOKEN = os.getenv("GITEE_TOKEN")

# Default model for evaluation (can be overridden per-request by query param `model=...`)
DEFAULT_LLM_MODEL = os.getenv("OSCANNER_LLM_MODEL", "anthropic/claude-sonnet-4.5")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Engineer Skill Evaluator"}


@app.get("/")
async def root(request: Request):
    """
    Root endpoint.

    - For browsers, return a small HTML landing page (so "/" isn't a 404).
    - For scripts/clients, return JSON.
    """
    payload = {
        "service": "Engineer Skill Evaluator API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "dashboard": "/dashboard",
        "endpoints": {
            "authors": "/api/authors/{owner}/{repo}",
            "evaluate": "/api/evaluate/{owner}/{repo}/{author}",
            "batch_extract": "/api/batch/extract",
            "batch_common_contributors": "/api/batch/common-contributors",
            "batch_compare_contributor": "/api/batch/compare-contributor",
        },
    }

    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{payload["service"]}</title>
    <style>
      body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 40px; line-height: 1.5; }}
      code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }}
      a {{ color: #2563eb; text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
      .card {{ max-width: 780px; padding: 20px 22px; border: 1px solid #e5e7eb; border-radius: 12px; }}
      ul {{ padding-left: 18px; }}
    </style>
  </head>
  <body>
    <div class="card">
      <h2 style="margin: 0 0 10px 0;">{payload["service"]}</h2>
      <p style="margin: 0 0 14px 0;">Status: <code>{payload["status"]}</code></p>
      <ul>
        <li><a href="{payload["docs"]}">API Docs (Swagger)</a></li>
        <li><a href="{payload["health"]}">Health Check</a></li>
        <li><a href="{payload["dashboard"]}">Dashboard</a> (if bundled)</li>
      </ul>
      <p style="margin: 14px 0 6px 0;"><strong>Common endpoints</strong>:</p>
      <ul>
        <li><code>{payload["endpoints"]["authors"]}</code></li>
        <li><code>{payload["endpoints"]["evaluate"]}</code></li>
        <li><code>{payload["endpoints"]["batch_extract"]}</code></li>
        <li><code>{payload["endpoints"]["batch_common_contributors"]}</code></li>
        <li><code>{payload["endpoints"]["batch_compare_contributor"]}</code></li>
      </ul>
      <p style="margin: 14px 0 0 0; color: #6b7280;">
        Dashboard UI can be bundled into the Python package and served at <code>/dashboard</code>.
      </p>
    </div>
  </body>
</html>
"""
        return HTMLResponse(content=html, status_code=200)

    return payload


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Browsers request this automatically; avoid noisy 404 logs.
    return Response(status_code=204)


# Mount dashboard static files as late as possible (after route declarations above).
_DASHBOARD_MOUNTED = _try_mount_bundled_dashboard()


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

        # Construct command (module execution; does not rely on CWD)
        cmd = [
            sys.executable,
            "-m",
            "evaluator.tools.extract_repo_data_moderate",
            "--repo-url",
            repo_url,
            "--out",
            str(output_dir),
            "--max-commits",
            "500",  # Fetch enough to cover all contributors
        ]

        if GITHUB_TOKEN:
            cmd.extend(["--token", GITHUB_TOKEN])

        # Run extraction tool
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 minute timeout

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
    limit: int = Query(500, ge=1, le=1000),
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

    # Try GitHub/Gitee API format
    if "commit" in commit_data:
        author = commit_data.get("commit", {}).get("author", {}).get("name")
        if author:
            return author

        # Some APIs may populate committer name but not author name
        committer = commit_data.get("commit", {}).get("committer", {}).get("name")
        if committer:
            return committer

    # Some providers use nested dicts for author/committer
    if "author" in commit_data and isinstance(commit_data["author"], dict):
        name = commit_data["author"].get("name")
        if name:
            return name

    if "committer" in commit_data and isinstance(commit_data["committer"], dict):
        name = commit_data["committer"].get("name")
        if name:
            return name

    return None


def parse_repo_url(url: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse repository URL and return (platform, owner, repo).

    Supports:
    - GitHub: https://github.com/owner/repo, github.com/owner/repo, git@github.com:owner/repo(.git)
    - Gitee:  https://gitee.com/owner/repo(.git)
    """
    url = (url or "").strip()
    if not url:
        return None

    parsed = parse_github_url(url)
    if parsed:
        return ("github", parsed["owner"], parsed["repo"])

    import re

    patterns = [
        r'^https?://(?:www\.)?gitee\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'^gitee\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
    ]
    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            owner, repo = match.groups()
            repo = repo.replace('.git', '')
            return ("gitee", owner, repo)

    return None


def extract_gitee_data(owner: str, repo: str, max_commits: int = 200) -> bool:
    """
    Extract Gitee repository data into DATA_DIR/{owner}/{repo} similar to GitHub extractor.

    This is a minimal extractor used by the multi-repo compare workflow.
    It fetches commit list then fetches per-commit details (which may include files/diffs depending on API support).
    """
    try:
        data_dir = DATA_DIR / owner / repo
        data_dir.mkdir(parents=True, exist_ok=True)
        commits_dir = data_dir / "commits"
        commits_dir.mkdir(parents=True, exist_ok=True)

        # 1) Fetch commits list (paginated)
        commits: List[Dict[str, Any]] = []
        page = 1
        per_page = 100
        while len(commits) < max_commits:
            api_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/commits"
            params: Dict[str, Any] = {"per_page": per_page, "page": page}
            if GITEE_TOKEN:
                params["access_token"] = GITEE_TOKEN
            resp = requests.get(api_url, params=params, timeout=30)
            if resp.status_code != 200:
                print(f"✗ Gitee commits list failed: {resp.status_code} {resp.text[:200]}")
                return False
            batch = resp.json()
            if not isinstance(batch, list) or not batch:
                break
            commits.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        commits = commits[:max_commits]

        with open(data_dir / "commits_list.json", "w", encoding="utf-8") as f:
            json.dump(commits, f, indent=2, ensure_ascii=False)

        # 2) Fetch per-commit details
        commits_index = []
        for c in commits:
            sha = c.get("sha")
            if not sha:
                continue
            detail_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/commits/{sha}"
            params = {}
            if GITEE_TOKEN:
                params["access_token"] = GITEE_TOKEN
            dresp = requests.get(detail_url, params=params, timeout=30)
            if dresp.status_code != 200:
                # Fallback to list item
                detail = c
            else:
                detail = dresp.json()

            with open(commits_dir / f"{sha}.json", "w", encoding="utf-8") as f:
                json.dump(detail, f, indent=2, ensure_ascii=False)

            commit_msg = detail.get("commit", {}).get("message", "") if isinstance(detail, dict) else ""
            author_name = get_author_from_commit(detail) if isinstance(detail, dict) else ""
            commit_date = ""
            if isinstance(detail, dict):
                commit_date = detail.get("commit", {}).get("author", {}).get("date", "") or detail.get("commit", {}).get("committer", {}).get("date", "")
            file_list = []
            if isinstance(detail, dict):
                file_list = [fi.get("filename") for fi in (detail.get("files") or []) if isinstance(fi, dict) and fi.get("filename")]

            commits_index.append(
                {
                    "sha": sha,
                    "message": (commit_msg.split("\n")[0] if commit_msg else "")[:100],
                    "author": author_name or "",
                    "date": commit_date or "",
                    "files_changed": len(file_list),
                    "files": file_list,
                }
            )

        with open(data_dir / "commits_index.json", "w", encoding="utf-8") as f:
            json.dump(commits_index, f, indent=2, ensure_ascii=False)

        # 3) repo_info.json
        repo_info = {"name": f"{owner}/{repo}", "full_name": f"{owner}/{repo}", "owner": owner, "platform": "gitee"}
        with open(data_dir / "repo_info.json", "w", encoding="utf-8") as f:
            json.dump(repo_info, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"✗ Gitee extraction failed: {e}")
        return False


def get_data_dir(platform: str, owner: str, repo: str) -> Path:
    """Get or create data directory for repository"""
    data_dir = DATA_DIR / owner / repo
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
    1. Validate evaluation cache if it exists (clear if corrupted)
    2. Check if local data exists in data/{owner}/{repo}
    3. If no local data, extract it from GitHub
    4. Load ALL authors from commits (always scans all commits)
    5. Evaluate first author automatically (skip if already cached)
    6. Return complete authors list
    """
    try:
        data_dir = DATA_DIR / owner / repo

        # Step 1: Validate evaluation cache if it exists
        cached_evaluations = None
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
                                cached_evaluations = None
                                break
                        if not cache_valid:
                            break

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

        # Step 5: Evaluate first author automatically (if not already cached)
        first_author = authors_list[0]["author"]
        has_cached_data = bool(cached_evaluations and len(cached_evaluations) > 0)
        first_author_cached = (first_author in cached_evaluations) if cached_evaluations else False

        if not first_author_cached:
            print(f"\nAuto-evaluating first author: {first_author}")

            try:
                # Create evaluator
                api_key = os.getenv("OPEN_ROUTER_KEY")
                if not api_key:
                    raise HTTPException(status_code=500, detail="OPEN_ROUTER_KEY not configured")

                evaluator = CommitEvaluatorModerate(
                    data_dir=str(data_dir),
                    api_key=api_key,
                    mode="moderate",
                    model=DEFAULT_LLM_MODEL  # Use default model for auto-evaluation
                )

                # Load commits from local data
                commits = load_commits_from_local(data_dir, limit=None)
                if commits:
                    # Evaluate first author with limit of 150 commits
                    evaluation = evaluator.evaluate_engineer(
                        commits=commits,
                        username=first_author,
                        max_commits=150,  # Limit to 150 commits per contributor
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
        else:
            print(f"✓ First author {first_author} already cached, skipping evaluation")

        return {
            "success": True,
            "data": {
                "owner": owner,
                "repo": repo,
                "authors": authors_list,
                "total_authors": len(authors_list),
                "cached": has_cached_data
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
    use_chunking: bool = Query(True),
    model: str = Query(DEFAULT_LLM_MODEL)
):
    """
    Evaluate an author using local commit data with caching

    This endpoint evaluates up to 150 commits per contributor for optimal balance.
    It automatically uses chunked evaluation with accumulative context for large commit sets.

    Flow:
    1. Check if evaluation exists in cache
    2. If cached and use_cache=True, return cached result
    3. Otherwise, load commits and perform evaluation (max 150 per contributor)
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
        # When this function is called directly (not via FastAPI request handling),
        # parameters using `Query(...)` defaults may arrive as Query objects.
        # Normalize them here to avoid leaking non-JSON-serializable objects into the LLM call.
        if not isinstance(model, str):
            model = DEFAULT_LLM_MODEL

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
            mode="moderate",
            model=model
        )

        # Load commits from local data
        print(f"\n[Evaluation] Loading commits for {author}...")
        commits = load_commits_from_local(data_dir, limit=None)
        if not commits:
            raise HTTPException(
                status_code=404,
                detail=f"No commits found in local data for {owner}/{repo}"
            )

        print(f"[Evaluation] Loaded {len(commits)} total commits")

        # Evaluate author using moderate evaluator with chunking enabled
        # The evaluator will automatically chunk if there are >20 commits
        # Limit to 150 commits per contributor for optimal balance
        evaluation = evaluator.evaluate_engineer(
            commits=commits,
            username=author,
            max_commits=150,  # Limit to 150 commits per contributor
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
    limit: int = Query(150, ge=1, le=200),
    use_cache: bool = Query(True),
    is_enterprise: bool = Query(False)
):
    """Evaluate a Gitee contributor (max 150 commits per contributor)"""
    platform = "gitee"

    try:
        # 1. Get commits (from cache or API)
        if use_cache:
            commits = load_commits_cache(platform, owner, repo)
            if not commits:
                commits = fetch_gitee_commits(owner, repo, 500, is_enterprise)
                save_commits_cache(platform, owner, repo, commits)
        else:
            commits = fetch_gitee_commits(owner, repo, 500, is_enterprise)
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


def parse_github_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parse GitHub URL to extract owner and repo
    Supports formats:
    - https://github.com/owner/repo
    - http://github.com/owner/repo
    - github.com/owner/repo
    - git@github.com:owner/repo.git
    """
    import re

    url = url.strip()

    # Try different patterns
    patterns = [
        r'^https?://(?:www\.)?github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'^github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'^git@github\.com:([^/]+)/([^/\s]+?)(?:\.git)?$',
    ]

    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            owner, repo = match.groups()
            # Remove .git suffix if present
            repo = repo.replace('.git', '')
            return {"owner": owner, "repo": repo}

    return None


@app.post("/api/batch/extract")
async def batch_extract_repos(request: dict):
    """
    Batch extract multiple repositories (GitHub + Gitee)

    Request body:
    {
        "urls": ["https://github.com/owner/repo1", "https://gitee.com/owner/repo2"]
    }

    Response:
    {
        "success": true,
        "results": [
            {
                "url": "https://github.com/owner/repo1",
                "owner": "owner",
                "repo": "repo1",
                "status": "extracted" | "skipped" | "failed",
                "message": "...",
                "data_exists": true/false
            }
        ]
    }
    """
    urls = request.get("urls", [])

    if not urls:
        raise HTTPException(status_code=400, detail="No URLs provided")

    if len(urls) < 2:
        raise HTTPException(status_code=400, detail="Please provide at least 2 repository URLs")

    if len(urls) > 5:
        raise HTTPException(status_code=400, detail="Please provide at most 5 repository URLs")

    results = []

    for url in urls:
        result = {
            "url": url,
            "status": "failed",
            "message": "",
            "data_exists": False
        }

        parsed = parse_repo_url(url)
        if not parsed:
            result["message"] = "Invalid repository URL format"
            results.append(result)
            continue

        platform, owner, repo = parsed
        result["owner"] = owner
        result["repo"] = repo
        result["platform"] = platform

        # Check if data already exists
        data_dir = DATA_DIR / owner / repo
        commits_dir = data_dir / "commits"

        if data_dir.exists() and commits_dir.exists() and list(commits_dir.glob("*.json")):
            result["status"] = "skipped"
            result["message"] = "Repository data already exists"
            result["data_exists"] = True
            results.append(result)
            continue

        # Extract data
        try:
            if platform == "github":
                success = extract_github_data(owner, repo)
            else:
                success = extract_gitee_data(owner, repo)
            if success:
                result["status"] = "extracted"
                result["message"] = "Successfully extracted repository data"
                result["data_exists"] = True
            else:
                result["status"] = "failed"
                result["message"] = "Failed to extract repository data"
        except Exception as e:
            result["status"] = "failed"
            result["message"] = f"Error: {str(e)}"

        results.append(result)

    # Count statuses
    extracted_count = sum(1 for r in results if r["status"] == "extracted")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    return {
        "success": True,
        "results": results,
        "summary": {
            "total": len(results),
            "extracted": extracted_count,
            "skipped": skipped_count,
            "failed": failed_count
        }
    }


@app.post("/api/batch/common-contributors")
async def find_common_contributors(request: dict):
    """
    Find common contributors across multiple repositories

    Request body:
    {
        "repos": [
            {"owner": "facebook", "repo": "react"},
            {"owner": "vercel", "repo": "next.js"}
        ]
    }

    Response:
    {
        "success": true,
        "common_contributors": [
            {
                "author": "John Doe",
                "email": "john@example.com",
                "repos": [
                    {
                        "owner": "facebook",
                        "repo": "react",
                        "commits": 150
                    },
                    {
                        "owner": "vercel",
                        "repo": "next.js",
                        "commits": 75
                    }
                ],
                "total_commits": 225,
                "repo_count": 2
            }
        ],
        "summary": {
            "total_repos": 2,
            "total_common_contributors": 5
        }
    }
    """
    repos = request.get("repos", [])

    if not repos:
        raise HTTPException(status_code=400, detail="No repositories provided")

    if len(repos) < 2:
        raise HTTPException(status_code=400, detail="At least 2 repositories required to find common contributors")

    # Load authors from each repository
    repo_authors = {}  # {repo_key: {author: {commits, email}}}

    for repo_info in repos:
        owner = repo_info.get("owner")
        repo = repo_info.get("repo")

        if not owner or not repo:
            continue

        repo_key = f"{owner}/{repo}"
        data_dir = DATA_DIR / owner / repo
        commits_dir = data_dir / "commits"

        if not commits_dir.exists():
            print(f"⚠ No commit data found for {repo_key}")
            continue

        authors_map = {}

        # Load all commit files
        for commit_file in commits_dir.glob("*.json"):
            try:
                with open(commit_file, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    author = get_author_from_commit(commit_data)

                    # Get email and GitHub user ID
                    email = ""
                    github_id = None
                    github_login = None

                    if "commit" in commit_data:
                        email = commit_data.get("commit", {}).get("author", {}).get("email", "")

                    # Get GitHub user info if available
                    if "author" in commit_data and isinstance(commit_data["author"], dict):
                        github_id = commit_data["author"].get("id")
                        github_login = commit_data["author"].get("login")

                    if author:
                        if author not in authors_map:
                            authors_map[author] = {
                                "commits": 0,
                                "email": email,
                                "github_id": github_id,
                                "github_login": github_login
                            }
                        authors_map[author]["commits"] += 1
            except Exception as e:
                print(f"⚠ Error reading {commit_file}: {e}")
                continue

        if authors_map:
            repo_authors[repo_key] = authors_map
            print(f"✓ Loaded {len(authors_map)} authors from {repo_key}")

    if len(repo_authors) < 2:
        return {
            "success": True,
            "common_contributors": [],
            "summary": {
                "total_repos": len(repo_authors),
                "total_common_contributors": 0
            },
            "message": "Not enough repositories with data to find common contributors"
        }

    # Find common contributors using intelligent matching
    # Strategy: Two-pass matching
    # Pass 1: Group by GitHub ID/login (strong identity signals)
    # Pass 2: Match orphaned authors to existing groups by fuzzy name

    def normalize_name(name):
        """Normalize name for fuzzy matching"""
        normalized = name.lower().strip()
        parts = normalized.split()
        return parts[0] if parts else normalized

    def names_match_fuzzy(name1, name2):
        """Check if two names likely refer to the same person"""
        norm1 = normalize_name(name1)
        norm2 = normalize_name(name2)

        # Exact match on first name
        if norm1 == norm2:
            return True

        # One name contains the other as a word
        words1 = name1.lower().split()
        words2 = name2.lower().split()

        if norm1 in words2 or norm2 in words1:
            return True

        return False

    # Pass 1: Group by GitHub ID/login
    identity_groups = {}  # {canonical_key: [{"repo_key": str, "author": str, "data": dict}]}
    orphaned_authors = []  # Authors without GitHub ID/login

    for repo_key, authors_map in repo_authors.items():
        for author, author_data in authors_map.items():
            github_id = author_data.get("github_id")
            github_login = author_data.get("github_login")

            # Use GitHub ID/login as canonical identity
            if github_id:
                canonical_key = f"github_id:{github_id}"
            elif github_login:
                canonical_key = f"github_login:{github_login}"
            else:
                # No strong identity, mark as orphaned for second pass
                orphaned_authors.append({
                    "repo_key": repo_key,
                    "author": author,
                    "data": author_data
                })
                continue

            if canonical_key not in identity_groups:
                identity_groups[canonical_key] = []

            identity_groups[canonical_key].append({
                "repo_key": repo_key,
                "author": author,
                "data": author_data
            })

    # Pass 2: Try to match orphaned authors to existing groups by fuzzy name
    unmatched_orphans = []

    for orphan in orphaned_authors:
        matched = False

        # Try to match with existing groups by comparing names
        for canonical_key, identities in identity_groups.items():
            # Check if orphan name matches any name in this group
            for identity in identities:
                if names_match_fuzzy(orphan["author"], identity["author"]):
                    # Found a match! Add to this group
                    identity_groups[canonical_key].append(orphan)
                    matched = True
                    break

            if matched:
                break

        if not matched:
            unmatched_orphans.append(orphan)

    # Pass 3: Group remaining unmatched orphans by exact name
    for orphan in unmatched_orphans:
        canonical_key = f"name:{orphan['author'].lower().strip()}"

        if canonical_key not in identity_groups:
            identity_groups[canonical_key] = []

        identity_groups[canonical_key].append(orphan)

    # Build common contributors from identity groups
    common_contributors = []

    for canonical_key, identities in identity_groups.items():
        # Get unique repos for this identity
        repos_map = {}  # {repo_key: identity}

        for identity in identities:
            repo_key = identity["repo_key"]
            if repo_key not in repos_map:
                repos_map[repo_key] = identity

        # Consider common if appears in at least 2 repos
        if len(repos_map) >= 2:
            repos_with_author = []

            for repo_key, identity in repos_map.items():
                owner, repo = repo_key.split("/", 1)
                author_data = identity["data"]

                repos_with_author.append({
                    "owner": owner,
                    "repo": repo,
                    "commits": author_data["commits"],
                    "email": author_data.get("email", ""),
                    "github_login": author_data.get("github_login", ""),
                })

            total_commits = sum(r["commits"] for r in repos_with_author)

            # Use the most complete name and email
            primary_identity = identities[0]
            display_name = primary_identity["author"]
            email = primary_identity["data"].get("email", "")
            github_login = primary_identity["data"].get("github_login", "")

            # Try to find the most complete name
            for identity in identities:
                if identity["data"].get("github_login"):
                    github_login = identity["data"]["github_login"]
                    display_name = identity["author"]
                    break

            common_contributors.append({
                "author": display_name,
                "email": email,
                "github_login": github_login,
                "repos": repos_with_author,
                "total_commits": total_commits,
                "repo_count": len(repos_with_author),
                "matched_by": canonical_key.split(":")[0]  # "github_id", "github_login", or "name"
            })

    # Sort by repo_count (descending), then by total_commits (descending)
    common_contributors.sort(key=lambda x: (-x["repo_count"], -x["total_commits"]))

    return {
        "success": True,
        "common_contributors": common_contributors,
        "summary": {
            "total_repos": len(repo_authors),
            "total_common_contributors": len(common_contributors)
        }
    }


@app.post("/api/batch/compare-contributor")
async def compare_contributor_across_repos(request: dict):
    """
    Compare a contributor's six-dimensional scores across multiple repositories

    Request body:
    {
        "contributor": "John Doe",
        "repos": [
            {"owner": "facebook", "repo": "react"},
            {"owner": "vercel", "repo": "next.js"}
        ]
    }

    Response:
    {
        "success": true,
        "contributor": "John Doe",
        "comparisons": [
            {
                "repo": "facebook/react",
                "owner": "facebook",
                "repo_name": "react",
                "scores": {
                    "ai_model_fullstack": 85,
                    "ai_native_architecture": 70,
                    ...
                },
                "total_commits": 150
            }
        ],
        "dimension_names": [...],
        "dimension_display_names": [...]
    }
    """
    contributor = request.get("contributor")
    repos = request.get("repos", [])

    if not contributor:
        raise HTTPException(status_code=400, detail="Contributor name is required")

    if not repos:
        raise HTTPException(status_code=400, detail="At least one repository is required")

    if len(repos) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 repositories allowed")

    results = []
    failed_repos = []

    for repo_info in repos:
        owner = repo_info.get("owner")
        repo = repo_info.get("repo")

        if not owner or not repo:
            continue

        try:
            # Check if data exists for this repo
            data_dir = DATA_DIR / owner / repo
            if not data_dir.exists() or not (data_dir / "commits").exists():
                failed_repos.append({
                    "repo": f"{owner}/{repo}",
                    "reason": "Repository data not extracted yet"
                })
                continue

            # Evaluate contributor in this repo
            eval_result = await evaluate_author(owner, repo, contributor, use_cache=True, model=DEFAULT_LLM_MODEL)

            if eval_result.get("success"):
                evaluation = eval_result["evaluation"]
                scores = evaluation.get("scores", {})

                results.append({
                    "repo": f"{owner}/{repo}",
                    "owner": owner,
                    "repo_name": repo,
                    "scores": {
                        "ai_model_fullstack": scores.get("ai_fullstack", 0),
                        "ai_native_architecture": scores.get("ai_architecture", 0),
                        "cloud_native": scores.get("cloud_native", 0),
                        "open_source_collaboration": scores.get("open_source", 0),
                        "intelligent_development": scores.get("intelligent_dev", 0),
                        "engineering_leadership": scores.get("leadership", 0)
                    },
                    "total_commits": evaluation.get("total_commits_analyzed", 0),
                    "commits_summary": evaluation.get("commits_summary", {}),
                    "cached": eval_result.get("metadata", {}).get("cached", False)
                })
            else:
                failed_repos.append({
                    "repo": f"{owner}/{repo}",
                    "reason": "Evaluation failed"
                })

        except HTTPException as e:
            failed_repos.append({
                "repo": f"{owner}/{repo}",
                "reason": str(e.detail)
            })
        except Exception as e:
            print(f"✗ Failed to evaluate {contributor} in {owner}/{repo}: {e}")
            failed_repos.append({
                "repo": f"{owner}/{repo}",
                "reason": f"Error: {str(e)}"
            })

    if not results:
        return {
            "success": False,
            "message": "No evaluations found for this contributor across the specified repositories",
            "contributor": contributor,
            "failed_repos": failed_repos
        }

    # Calculate aggregate statistics
    avg_scores = {}
    dimension_keys = [
        "ai_model_fullstack",
        "ai_native_architecture",
        "cloud_native",
        "open_source_collaboration",
        "intelligent_development",
        "engineering_leadership"
    ]

    for dim in dimension_keys:
        scores_list = [r["scores"][dim] for r in results]
        avg_scores[dim] = sum(scores_list) / len(scores_list) if scores_list else 0

    total_commits_all_repos = sum(r["total_commits"] for r in results)

    return {
        "success": True,
        "contributor": contributor,
        "comparisons": results,
        "dimension_keys": dimension_keys,
        "dimension_names": [
            "AI Model Full-Stack & Trade-off Capability",
            "AI Native Architecture & Communication Design",
            "Cloud Native & Constraint Engineering",
            "Open Source Collaboration & Requirements Translation",
            "Intelligent Development & Human-Machine Collaboration",
            "Engineering Leadership & System Trade-offs"
        ],
        "aggregate": {
            "total_repos_evaluated": len(results),
            "total_commits": total_commits_all_repos,
            "average_scores": avg_scores
        },
        "failed_repos": failed_repos if failed_repos else None
    }


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
