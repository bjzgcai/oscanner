"""Growth trajectory API endpoints."""

from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query
import asyncio

from evaluator.config import DEFAULT_LLM_MODEL, get_llm_api_key, get_github_token, get_gitee_token
from evaluator.schemas import TrajectoryResponse
from evaluator.services import (
    load_trajectory_cache,
    analyze_growth_trajectory,
    resolve_plugin_id,
    get_commits_by_date
)
from evaluator.paths import get_trajectory_cache_path, get_platform_data_dir
from evaluator.services.trajectory_service import ensure_repo_data_synced
from evaluator.utils import parse_repo_url, load_commits_from_local, get_author_from_commit

router = APIRouter()
EXCLUDED_GITEE_AUTHORS_FOR_NULL_USERNAME = {"吴衍标"}


def _get_commit_datetime(commit: Dict[str, Any]) -> Optional[datetime]:
    """Extract commit datetime from known commit payload formats."""
    date_str = (
        commit.get("commit", {}).get("author", {}).get("date")
        or commit.get("date")
        or ""
    )
    if not date_str:
        return None

    try:
        parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _get_oldest_commit(commits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pick oldest commit by date when possible; otherwise fallback to list tail."""
    oldest_commit = commits[-1]
    oldest_date = _get_commit_datetime(oldest_commit)

    for commit in commits:
        commit_date = _get_commit_datetime(commit)
        if commit_date is None:
            continue
        if oldest_date is None or commit_date < oldest_date:
            oldest_date = commit_date
            oldest_commit = commit

    return oldest_commit


def _infer_username_from_first_commit(repo_urls: List[str]) -> Optional[str]:
    """
    Infer default username from the earliest ("first") commit author
    across all provided repositories.
    """
    inferred_username: Optional[str] = None
    inferred_commit_date: Optional[datetime] = None

    for repo_url in repo_urls:
        parsed = parse_repo_url(repo_url)
        if not parsed:
            continue

        platform, owner, repo = parsed

        try:
            # Ensure local data exists before reading commit history.
            ensure_repo_data_synced(repo_url, max_commits=500)
        except Exception as e:
            print(f"[Trajectory API One-Off] Warning: failed to sync {repo_url} for username inference: {e}")
            continue

        data_dir = get_platform_data_dir(platform, owner, repo)
        if not data_dir.exists():
            continue

        commits = load_commits_from_local(data_dir, limit=None)
        if not commits:
            continue

        oldest_commit = _get_oldest_commit(commits)
        author = (get_author_from_commit(oldest_commit) or "").strip()
        if not author:
            continue

        commit_date = _get_commit_datetime(oldest_commit)
        if inferred_username is None:
            inferred_username = author
            inferred_commit_date = commit_date
            continue

        if commit_date is not None and (inferred_commit_date is None or commit_date < inferred_commit_date):
            inferred_username = author
            inferred_commit_date = commit_date

    return inferred_username


def _infer_gitee_authors_from_commits(repo_urls: List[str]) -> List[str]:
    """
    Infer all author names from Gitee repositories in repo_urls.
    Authors are returned in descending commit-count order.
    """
    author_counts: Dict[str, int] = {}
    author_display_names: Dict[str, str] = {}

    for repo_url in repo_urls:
        parsed = parse_repo_url(repo_url)
        if not parsed:
            continue

        platform, owner, repo = parsed
        if platform != "gitee":
            continue

        try:
            ensure_repo_data_synced(repo_url, max_commits=500)
        except Exception as e:
            print(f"[Trajectory API One-Off] Warning: failed to sync {repo_url} for gitee author inference: {e}")
            continue

        data_dir = get_platform_data_dir(platform, owner, repo)
        if not data_dir.exists():
            continue

        commits = load_commits_from_local(data_dir, limit=None)
        if not commits:
            continue

        for commit in commits:
            author = (get_author_from_commit(commit) or "").strip()
            if not author:
                continue

            key = author.lower()
            if key not in author_counts:
                author_counts[key] = 0
                author_display_names[key] = author
            author_counts[key] += 1

    sorted_keys = sorted(
        author_counts.keys(),
        key=lambda k: (-author_counts[k], author_display_names[k].lower())
    )
    authors = [author_display_names[k] for k in sorted_keys]
    excluded = {name.strip().lower() for name in EXCLUDED_GITEE_AUTHORS_FOR_NULL_USERNAME}
    return [name for name in authors if name.strip().lower() not in excluded]


@router.post("/api/trajectory/analyze")
async def analyze_trajectory(
    request_body: Dict[str, Any],
    plugin: str = Query(""),
    model: str = Query(DEFAULT_LLM_MODEL),
    language: str = Query("zh-CN"),
    use_cache: bool = Query(True),
    parallel_chunking: bool = Query(True),
    max_parallel_workers: int = Query(3),
    forced_checker: str = Query(""),
    worktree_base: str = Query("build"),  # 'build' or 'temp', default 'build'
    checkpoint_strategy: str = Query("period")  # 'period' or 'none', default 'period'
) -> Dict[str, Any]:
    """
    Analyze user growth trajectory.

    Request body format:
    {
        "username": "CarterWu",
        "repo_urls": ["https://gitee.com/zgcai/oscanner"],
        "aliases": ["CarterWu", "wu-yanbiao"]
    }

    Returns TrajectoryResponse with:
    - success: bool
    - trajectory: TrajectoryCache (if successful)
    - new_checkpoint_created: bool
    - message: str
    - commits_pending: int (commits not yet forming a checkpoint)
    """
    try:
        # Validate request body
        if not isinstance(request_body, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")

        username = request_body.get("username")

        # Handle both repo_url (singular) and repo_urls (plural) for backwards compatibility
        repo_urls = request_body.get("repo_urls", [])
        if not repo_urls and request_body.get("repo_url"):
            # If repo_urls is empty but repo_url exists, use it
            repo_urls = [request_body.get("repo_url")]

        aliases = request_body.get("aliases", [])

        if not username:
            raise HTTPException(status_code=400, detail="Missing required field: username")

        if not isinstance(repo_urls, list):
            raise HTTPException(status_code=400, detail="repo_urls must be a list (can be empty)")

        # If repo_urls is empty, return empty trajectory
        if not repo_urls:
            return {
                "success": True,
                "trajectory": {
                    "username": username,
                    "repo_urls": [],
                    "checkpoints": [],
                    "total_checkpoints": 0,
                    "created_at": None,
                    "updated_at": None
                },
                "new_checkpoint_created": False,
                "message": "No repositories to analyze",
                "commits_pending": 0
            }

        # Ensure aliases includes username
        if username not in aliases:
            aliases = [username] + aliases

        # Check LLM configuration before analysis
        api_key = get_llm_api_key()
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init)."
            )

        # Check platform token configuration before analysis
        github_token = get_github_token()
        gitee_token = get_gitee_token()
        missing_platforms = []
        
        for repo_url in repo_urls:
            parsed = parse_repo_url(repo_url)
            if not parsed:
                continue  # Skip invalid URLs, they'll be handled later
            
            platform, owner, repo = parsed
            if platform == "github" and not github_token:
                if "github" not in missing_platforms:
                    missing_platforms.append("github")
            elif platform == "gitee" and not gitee_token:
                if "gitee" not in missing_platforms:
                    missing_platforms.append("gitee")
        
        if missing_platforms:
            missing_tokens = []
            if "github" in missing_platforms:
                missing_tokens.append("GitHub Token (GITHUB_TOKEN)")
            if "gitee" in missing_platforms:
                missing_tokens.append("Gitee Token (GITEE_TOKEN)")
            
            raise HTTPException(
                status_code=400,
                detail=f"Missing required platform tokens: {', '.join(missing_tokens)}. "
                       f"Please configure them in Settings (LLM Settings) before analyzing. "
                       f"Without tokens, API rate limits are very low (~60 requests/hour for GitHub, lower for Gitee)."
            )

        # Resolve plugin ID
        plugin_id = resolve_plugin_id(plugin)

        print(f"[Trajectory API] Analyzing trajectory for {username}")
        print(f"[Trajectory API] Repos: {repo_urls}")
        print(f"[Trajectory API] Aliases: {aliases}")

        # Call trajectory analysis service
        # Run synchronous blocking operations in thread pool to avoid blocking event loop
        forced_checker_id = forced_checker.strip() if forced_checker else None
        worktree_base_value = worktree_base.strip() if worktree_base else "build"
        if worktree_base_value not in ("build", "temp"):
            worktree_base_value = "build"  # Default to build

        checkpoint_strategy_value = checkpoint_strategy.strip() if checkpoint_strategy else "period"
        if checkpoint_strategy_value not in ("period", "none"):
            checkpoint_strategy_value = "period"  # Default to period

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            analyze_growth_trajectory,
            username,
            repo_urls,
            aliases,
            plugin_id,
            model,
            language,
            use_cache,
            parallel_chunking,
            max_parallel_workers,
            forced_checker_id,
            worktree_base_value,
            checkpoint_strategy_value,
            None,  # start_sha (not used in regular endpoint)
            None,  # end_sha (not used in regular endpoint)
            True  # save_to_cache=True
        )

        return response.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Trajectory API] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Trajectory analysis failed: {str(e)}")


@router.post("/api/trajectory/analyze_one-off")
async def analyze_trajectory_one_off(
    request_body: Dict[str, Any],
    plugin: str = Query("zgc_ai_native_2026"),
    model: str = Query(DEFAULT_LLM_MODEL),
    language: str = Query("zh-CN"),
    use_cache: bool = Query(False),
    parallel_chunking: bool = Query(True),
    max_parallel_workers: int = Query(3),
    forced_checker: str = Query(""),
    worktree_base: str = Query("build"),  # 'build' or 'temp', default 'build'
    checkpoint_strategy: str = Query("none"),  # 'period' or 'none', default 'none' for one-off
    start_sha: str = Query(""),  # Optional: commit hash to start from (INCLUDED)
    end_sha: str = Query("")  # Optional: commit hash to end at (INCLUDED)
) -> Dict[str, Any]:
    """
    Analyze user growth trajectory (one-off, doesn't save to cache).

    This endpoint is for external parties to call. It performs analysis for a specific
    commit range and returns a SINGLE checkpoint (not saved to cache).

    Request body format:
    {
        "username": "CarterWu",
        "repo_urls": ["https://gitee.com/zgcai/oscanner"],
        "aliases": ["CarterWu", "wu-yanbiao"],
        "expected_feature": "Optional feature description used as an evaluation baseline"
    }
    Note: `username` is optional.
    - If `username` is null and repo is from Gitee, all detected authors are used (no single-author filtering).
    - Otherwise, missing/empty username defaults to the first commit author.
    - `expected_feature` is optional. When omitted or blank, evaluation uses the normal rubric only.

    Query parameters:
    - checkpoint_strategy: 'none' (default) or 'period'. Use 'none' for analyzing any commit range.
    - start_sha: Optional commit hash to start from (INCLUDED in range)
    - end_sha: Optional commit hash to end at (INCLUDED in range)

    When checkpoint_strategy=none:
    - If start_sha not provided: start from first commit (included)
    - If end_sha not provided: use latest commit (included)
    - No minimum commit requirement

    Corner cases:
    - Both None: evaluate all commits
    - Only start_sha: evaluate from start_sha to latest
    - Only end_sha: evaluate from first to end_sha
    - start_sha == end_sha: single commit evaluation
    - start_sha newer than end_sha: error (invalid range)
    - SHA not found: error with clear message

    Returns:
    - success: bool
    - checkpoint: TrajectoryCheckpoint (single checkpoint object, if successful)
    - message: str
    - commits_analyzed: int (number of commits included in the checkpoint)
    """
    try:
        # Validate request body
        if not isinstance(request_body, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")

        username = request_body.get("username")
        username_is_explicit_null = "username" in request_body and request_body.get("username") is None

        # Handle both repo_url (singular) and repo_urls (plural) for backwards compatibility
        repo_urls = request_body.get("repo_urls", [])
        if not repo_urls and request_body.get("repo_url"):
            # If repo_urls is empty but repo_url exists, use it
            repo_urls = [request_body.get("repo_url")]

        aliases = request_body.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []

        expected_feature = request_body.get("expected_feature")
        if isinstance(expected_feature, str):
            expected_feature = expected_feature.strip() or None
        elif expected_feature is not None:
            raise HTTPException(status_code=400, detail="expected_feature must be a string")

        if isinstance(username, str):
            username = username.strip()
        elif username is not None:
            raise HTTPException(status_code=400, detail="username must be a string")

        if not isinstance(repo_urls, list):
            raise HTTPException(status_code=400, detail="repo_urls must be a list (can be empty)")

        # If repo_urls is empty, return error
        if not repo_urls:
            return {
                "success": False,
                "checkpoint": None,
                "message": "No repositories to analyze",
                "commits_analyzed": 0
            }

        # Check LLM configuration before analysis
        api_key = get_llm_api_key()
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init)."
            )

        # Check platform token configuration before analysis
        github_token = get_github_token()
        gitee_token = get_gitee_token()
        missing_platforms = []

        for repo_url in repo_urls:
            parsed = parse_repo_url(repo_url)
            if not parsed:
                continue  # Skip invalid URLs, they'll be handled later

            platform, owner, repo = parsed
            if platform == "github" and not github_token:
                if "github" not in missing_platforms:
                    missing_platforms.append("github")
            elif platform == "gitee" and not gitee_token:
                if "gitee" not in missing_platforms:
                    missing_platforms.append("gitee")

        if missing_platforms:
            missing_tokens = []
            if "github" in missing_platforms:
                missing_tokens.append("GitHub Token (GITHUB_TOKEN)")
            if "gitee" in missing_platforms:
                missing_tokens.append("Gitee Token (GITEE_TOKEN)")

            raise HTTPException(
                status_code=400,
                detail=f"Missing required platform tokens: {', '.join(missing_tokens)}. "
                       f"Please configure them in Settings (LLM Settings) before analyzing. "
                       f"Without tokens, API rate limits are very low (~60 requests/hour for GitHub, lower for Gitee)."
            )

        inferred_all_authors: List[str] = []

        # Username is optional for one-off mode.
        if not username:
            # Special mode: username=null + gitee repo means evaluate without single-author filtering.
            if username_is_explicit_null:
                inferred_all_authors = _infer_gitee_authors_from_commits(repo_urls)
                if inferred_all_authors:
                    username = inferred_all_authors[0]
                    print(
                        f"[Trajectory API One-Off] username=null for gitee repo, "
                        f"using {len(inferred_all_authors)} inferred authors"
                    )
                else:
                    print(
                        "[Trajectory API One-Off] username=null but no gitee authors inferred, "
                        "falling back to first-commit author inference"
                    )

            if not username:
                username = _infer_username_from_first_commit(repo_urls)
                if not username:
                    raise HTTPException(
                        status_code=400,
                        detail="Missing required field: username. Unable to infer default username from first commit author."
                    )
                print(f"[Trajectory API One-Off] Inferred username from first commit author: {username}")
            elif username_is_explicit_null and inferred_all_authors:
                print(f"[Trajectory API One-Off] Primary username set to first inferred gitee author: {username}")

        # Ensure aliases include username and (when enabled) all inferred Gitee authors.
        merged_aliases: List[str] = []
        seen_aliases = set()
        for candidate in [username, *inferred_all_authors, *aliases]:
            if not isinstance(candidate, str):
                continue
            cleaned = candidate.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen_aliases:
                continue
            seen_aliases.add(key)
            merged_aliases.append(cleaned)
        aliases = merged_aliases

        # Resolve plugin ID
        plugin_id = resolve_plugin_id(plugin)

        print(f"[Trajectory API One-Off] Analyzing trajectory for {username}")
        print(f"[Trajectory API One-Off] Repos: {repo_urls}")
        print(f"[Trajectory API One-Off] Aliases: {aliases}")

        # Call trajectory analysis service with save_to_cache=False
        # Run synchronous blocking operations in thread pool to avoid blocking event loop
        forced_checker_id = forced_checker.strip() if forced_checker else None
        worktree_base_value = worktree_base.strip() if worktree_base else "build"
        if worktree_base_value not in ("build", "temp"):
            worktree_base_value = "build"  # Default to build

        checkpoint_strategy_value = checkpoint_strategy.strip() if checkpoint_strategy else "none"
        if checkpoint_strategy_value not in ("period", "none"):
            checkpoint_strategy_value = "none"  # Default to none for one-off

        start_sha_value = start_sha.strip() if start_sha else None
        end_sha_value = end_sha.strip() if end_sha else None

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            analyze_growth_trajectory,
            username,
            repo_urls,
            aliases,
            plugin_id,
            model,
            language,
            use_cache,
            parallel_chunking,
            max_parallel_workers,
            forced_checker_id,
            worktree_base_value,
            checkpoint_strategy_value,
            start_sha_value,
            end_sha_value,
            False,  # save_to_cache=False
            expected_feature,
        )

        # Extract single checkpoint from trajectory response
        if response.success and response.trajectory and response.trajectory.checkpoints:
            checkpoint = response.trajectory.checkpoints[-1]  # Get the latest (or only) checkpoint
            return {
                "success": True,
                "checkpoint": checkpoint.model_dump(),
                "message": response.message,
                "commits_analyzed": checkpoint.commits_range.commit_count
            }
        else:
            return {
                "success": False,
                "checkpoint": None,
                "message": response.message,
                "commits_analyzed": 0
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Trajectory API One-Off] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Trajectory analysis failed: {str(e)}")


@router.get("/api/trajectory/{username}")
async def get_trajectory(username: str) -> Dict[str, Any]:
    """
    Get cached trajectory data for a user.

    Returns:
    {
        "success": bool,
        "trajectory": TrajectoryCache or null,
        "message": str
    }
    """
    try:
        trajectory = load_trajectory_cache(username)

        if trajectory is None:
            return {
                "success": False,
                "trajectory": None,
                "message": f"No trajectory data found for {username}"
            }

        return {
            "success": True,
            "trajectory": trajectory.model_dump(),
            "message": f"Found trajectory with {trajectory.total_checkpoints} checkpoints"
        }

    except Exception as e:
        print(f"[Trajectory API] Error loading trajectory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load trajectory: {str(e)}")


@router.delete("/api/trajectory/{username}")
async def clear_trajectory(username: str) -> Dict[str, Any]:
    """
    Clear trajectory cache for a user (for testing/reset).

    Returns:
    {
        "success": bool,
        "message": str
    }
    """
    try:
        cache_path = get_trajectory_cache_path(username)

        if not cache_path.exists():
            return {
                "success": False,
                "message": f"No trajectory cache found for {username}"
            }

        cache_path.unlink()

        return {
            "success": True,
            "message": f"Trajectory cache cleared for {username}"
        }

    except Exception as e:
        print(f"[Trajectory API] Error clearing trajectory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear trajectory: {str(e)}")


@router.get("/api/trajectory/{username}/commits-by-date")
async def get_commits_by_date_endpoint(username: str) -> Dict[str, Any]:
    """
    Get commits grouped by date for visualization.

    Returns:
    {
        "success": bool,
        "data": [{"date": "YYYY-MM-DD", "count": int}, ...],
        "message": str
    }
    """
    try:
        # Load trajectory to get repo_urls and aliases
        trajectory = load_trajectory_cache(username)

        if trajectory is None:
            return {
                "success": False,
                "data": [],
                "message": f"No trajectory data found for {username}. Please run trajectory analysis first."
            }

        # Get aliases from latest checkpoint if available
        aliases = [username]
        if trajectory.checkpoints:
            latest_checkpoint = trajectory.checkpoints[-1]
            if latest_checkpoint.aliases_used:
                aliases = latest_checkpoint.aliases_used

        # Get commits by date
        commits_data = get_commits_by_date(
            username=username,
            repo_urls=trajectory.repo_urls,
            aliases=aliases
        )

        return {
            "success": True,
            "data": commits_data,
            "message": f"Found {len(commits_data)} days with commits"
        }

    except Exception as e:
        print(f"[Trajectory API] Error getting commits by date: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get commits by date: {str(e)}")
