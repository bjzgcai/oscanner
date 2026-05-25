"""Benchmark and validation routes."""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query

# Import validation modules
try:
    from evaluator.validation.benchmark_dataset import (
        benchmark_dataset,
        get_benchmark_repos_list,
        get_benchmark_dataset_path,
    )
    from evaluator.validation.validation_runner import ValidationRunner
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False

# Import evaluation dependencies
from evaluator.paths import get_platform_data_dir
from evaluator.plugin_registry import load_scan_module, PluginLoadError
from evaluator.config import get_llm_api_key, DEFAULT_LLM_MODEL
from evaluator.utils import load_commits_from_local
from evaluator.services import (
    resolve_plugin_id,
    evaluate_author_incremental,
    extract_github_data,
    extract_gitee_data,
)

router = APIRouter()


def _pinning_summary(repos):
    total = len(repos)
    pinned = sum(1 for repo in repos if repo.get("is_pinned"))
    return {
        "total": total,
        "pinned": pinned,
        "unpinned": total - pinned,
    }


async def extract_commits_from_platform(platform: str, owner: str, repo: str):
    """
    Extract commits from the specified platform

    Args:
        platform: "github" or "gitee"
        owner: Repository owner
        repo: Repository name
    """
    if platform == "github":
        return extract_github_data(owner, repo)
    elif platform == "gitee":
        return extract_gitee_data(owner, repo)
    else:
        raise ValueError(f"Unsupported platform: {platform}")


async def evaluation_function_wrapper(repo_url: str, author: str, plugin_id: str = "", model: str = DEFAULT_LLM_MODEL) -> Dict[str, Any]:
    """
    Wrapper function for ValidationRunner to evaluate a repository/author

    Args:
        repo_url: Repository URL (e.g., "https://github.com/owner/repo")
        author: Author username to evaluate
        plugin_id: Optional plugin ID to use
        model: LLM model to use

    Returns:
        Evaluation result dictionary
    """
    # Parse repo URL
    if "github.com" in repo_url:
        platform = "github"
        parts = repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
    elif "gitee.com" in repo_url:
        platform = "gitee"
        parts = repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
    else:
        raise ValueError(f"Unsupported platform in URL: {repo_url}")

    # Resolve plugin
    plugin_id = resolve_plugin_id(plugin_id)

    # Load plugin
    try:
        meta, scan_mod, scan_path = load_scan_module(plugin_id)
    except PluginLoadError as e:
        raise ValueError(f"Plugin load error: {e}")

    # Check/extract data
    data_dir = get_platform_data_dir(platform, owner, repo)
    if not data_dir.exists():
        # Auto-extract data
        print(f"[Benchmark] Extracting data for {platform}/{owner}/{repo}...")
        try:
            await extract_commits_from_platform(platform, owner, repo)
        except Exception as e:
            raise ValueError(f"Failed to extract data: {e}")

    # Load commits
    commits = load_commits_from_local(data_dir, limit=None)
    if not commits:
        return {
            "overall_score": 0,
            "dimensions": [],
            "error": "No commits found"
        }

    # Get API key
    api_key = get_llm_api_key()
    if not api_key:
        raise ValueError("LLM API key not configured")

    # Create evaluator factory
    def evaluator_factory():
        return scan_mod.create_commit_evaluator(
            data_dir=str(data_dir),
            api_key=api_key,
            model=model,
        )

    # Run evaluation
    result = evaluate_author_incremental(
        commits=commits,
        author=author,
        previous_evaluation=None,
        data_dir=data_dir,
        model=model,
        api_key=api_key,
        aliases=None,
        evaluator_factory=evaluator_factory,
    )

    return result


@router.get("/api/benchmark/dataset")
async def get_benchmark_dataset():
    """Get benchmark dataset metadata."""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Validation module not available")

    dataset_path = get_benchmark_dataset_path()
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail="Benchmark dataset not found")

    repos = get_benchmark_repos_list()

    return {
        "success": True,
        "dataset_path": str(dataset_path),
        "total_repos": len(repos),
        "stats": benchmark_dataset.get_stats(),
        "categories": sorted(benchmark_dataset.get_categories()),
        "pinning": _pinning_summary(repos),
        "repos": repos[:10]  # Preview first 10
    }


@router.get("/api/benchmark/repos")
async def get_benchmark_repos(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    category: Optional[str] = Query(None)
):
    """Get paginated list of benchmark repos."""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Validation module not available")

    repos = get_benchmark_repos_list(category=category)
    total = len(repos)
    start = (page - 1) * per_page
    end = start + per_page
    page_repos = repos[start:end]

    return {
        "success": True,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page,
        "repos": page_repos
    }


@router.post("/api/benchmark/validate")
async def run_validation(
    request: dict
):
    """Run validation on benchmark repos."""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Validation module not available")

    subset = request.get("subset", None)
    quick_mode = request.get("quick_mode", False)
    plugin_id = request.get("plugin_id", "")
    model = request.get("model", DEFAULT_LLM_MODEL)

    try:
        # Create evaluation function with plugin/model config
        async def eval_func(repo_url: str, author: str) -> Dict[str, Any]:
            return await evaluation_function_wrapper(repo_url, author, plugin_id, model)

        # Create runner with evaluation function
        runner = ValidationRunner(evaluation_function=eval_func)

        # Run validation
        result = await runner.run_full_validation(subset=subset, quick_mode=quick_mode)

        return {
            "success": True,
            "run_id": result.run_id,
            "message": f"Validation completed: {result.overall_score:.1f}/100",
            "result": result.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run validation: {str(e)}")
