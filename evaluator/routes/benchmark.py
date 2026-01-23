"""Benchmark and validation routes."""

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path

# Import validation modules
try:
    from evaluator.validation.benchmark_dataset import get_benchmark_repos_list, get_benchmark_dataset_path
    from evaluator.validation.validation_runner import ValidationRunner
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False

router = APIRouter()


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
        "repos": repos[:10]  # Preview first 10
    }


@router.get("/api/benchmark/repos")
async def get_benchmark_repos(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100)
):
    """Get paginated list of benchmark repos."""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Validation module not available")

    repos = get_benchmark_repos_list()
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

    plugin_id = request.get("plugin_id", "")
    model = request.get("model", "")
    max_repos = request.get("max_repos", 10)

    try:
        runner = ValidationRunner()
        run_id = runner.start_validation(
            plugin_id=plugin_id,
            model=model,
            max_repos=max_repos
        )

        return {
            "success": True,
            "run_id": run_id,
            "message": f"Validation started for {max_repos} repos"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start validation: {str(e)}")


@router.get("/api/benchmark/validation/runs")
async def list_validation_runs():
    """List all validation runs."""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Validation module not available")

    try:
        runner = ValidationRunner()
        runs = runner.list_runs()

        return {
            "success": True,
            "runs": runs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list runs: {str(e)}")


@router.get("/api/benchmark/validation/runs/{run_id}")
async def get_validation_run(run_id: str):
    """Get specific validation run details."""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Validation module not available")

    try:
        runner = ValidationRunner()
        run_data = runner.get_run(run_id)

        if not run_data:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        return {
            "success": True,
            "run": run_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get run: {str(e)}")


@router.get("/api/benchmark/repo/{platform}/{owner}/{repo}/{author}")
async def get_benchmark_repo_evaluation(
    platform: str,
    owner: str,
    repo: str,
    author: str,
    plugin_id: str = Query(""),
):
    """Get benchmark evaluation for specific repo/author."""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Validation module not available")

    try:
        from evaluator.validation.benchmark_dataset import load_benchmark_evaluation

        evaluation = load_benchmark_evaluation(platform, owner, repo, author, plugin_id)

        if not evaluation:
            raise HTTPException(
                status_code=404,
                detail=f"No benchmark evaluation found for {platform}/{owner}/{repo}/{author}"
            )

        return {
            "success": True,
            "evaluation": evaluation
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load evaluation: {str(e)}")
