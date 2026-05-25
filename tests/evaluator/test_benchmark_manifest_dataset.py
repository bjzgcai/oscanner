import pytest

from evaluator.routes import benchmark
from evaluator.validation.benchmark_dataset import (
    get_benchmark_repos_list,
    load_benchmark_manifest_dataset,
)
from evaluator.validation.validation_runner import ValidationRunner
from evaluator.validation.validators import DimensionValidator


pytestmark = pytest.mark.anyio


def test_manifest_dataset_is_public_benchmark_source():
    dataset = load_benchmark_manifest_dataset()
    repos = dataset.get_all()

    assert len(repos) == 30
    assert repos[0].entry_id == "python-l1"
    assert repos[0].language == "python"
    assert repos[0].level == "L1"
    assert repos[0].category == "python"
    assert repos[0].skill_level.value == "novice"
    assert repos[0].repo_url == "https://github.com/mitsuhiko/twitterlog"


def test_benchmark_repo_list_filters_by_manifest_category():
    repos = get_benchmark_repos_list(category="python")

    assert len(repos) == 5
    assert {repo["language"] for repo in repos} == {"python"}
    assert {repo["level"] for repo in repos} == {"L1", "L2", "L3", "L4", "L5"}


async def test_benchmark_dataset_route_reports_manifest_path_and_stats():
    response = await benchmark.get_benchmark_dataset()

    assert response["success"] is True
    assert response["dataset_path"].endswith("benchmark/repos.yaml")
    assert response["total_repos"] == 30
    assert response["stats"]["total"] == 30
    assert response["pinning"] == {
        "total": 30,
        "pinned": 30,
        "unpinned": 0,
    }
    assert response["categories"] == [
        "cpp",
        "go",
        "java",
        "javascript-typescript",
        "python",
        "rust",
    ]


async def test_benchmark_repos_route_applies_category_filter():
    response = await benchmark.get_benchmark_repos(page=1, per_page=50, category="python")

    assert response["success"] is True
    assert response["total"] == 5
    assert {repo["category"] for repo in response["repos"]} == {"python"}


async def test_validation_subset_does_not_run_out_of_subset_temporal_groups():
    dataset = load_benchmark_manifest_dataset()
    calls = []

    async def fake_eval(repo_url: str, author: str):
        calls.append((repo_url, author))
        return {"overall_score": 50, "dimensions": []}

    runner = ValidationRunner(dataset=dataset, evaluation_function=fake_eval)
    result = await runner.run_full_validation(subset="python", quick_mode=True)

    assert result.evaluation_count == 5
    assert calls
    assert all("mitsuhiko" in repo_url for repo_url, _ in calls)


async def test_dimension_validator_fails_when_expected_dimension_score_misses_range():
    result = await DimensionValidator().validate(
        {
            "repo-a": {
                "actual_dimensions": {"ai_model": 40},
                "strong_dimensions": [],
                "weak_dimensions": [],
                "expected_dimension_scores": {"ai_model": (80, 90)},
            }
        }
    )

    assert result.passed is False
    assert result.score == 0
    assert result.errors == [
        "repo-a: ai_model score 40.0 outside expected [80, 90]"
    ]
