"""Growth trajectory API endpoints."""

from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query

from evaluator.config import DEFAULT_LLM_MODEL, get_llm_api_key, get_github_token, get_gitee_token
from evaluator.schemas import TrajectoryResponse
from evaluator.services import (
    load_trajectory_cache,
    analyze_growth_trajectory,
    resolve_plugin_id,
    get_commits_by_date
)
from evaluator.paths import get_trajectory_cache_path
from evaluator.utils import parse_repo_url

router = APIRouter()


@router.post("/api/trajectory/analyze")
async def analyze_trajectory(
    request_body: Dict[str, Any],
    plugin: str = Query(""),
    model: str = Query(DEFAULT_LLM_MODEL),
    language: str = Query("en-US"),
    use_cache: bool = Query(True),
    parallel_chunking: bool = Query(True),
    max_parallel_workers: int = Query(3)
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
        repo_urls = request_body.get("repo_urls", [])
        aliases = request_body.get("aliases", [])

        if not username:
            raise HTTPException(status_code=400, detail="Missing required field: username")

        if not repo_urls or not isinstance(repo_urls, list):
            raise HTTPException(status_code=400, detail="repo_urls must be a non-empty list")

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
        response = analyze_growth_trajectory(
            username=username,
            repo_urls=repo_urls,
            aliases=aliases,
            plugin_id=plugin_id,
            model=model,
            language=language,
            use_cache=use_cache,
            parallel_chunking=parallel_chunking,
            max_parallel_workers=max_parallel_workers
        )

        return response.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Trajectory API] Error: {e}")
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

