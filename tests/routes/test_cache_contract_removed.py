"""Regression tests for removing Oscanner-owned cache strategy."""

import inspect
import argparse

import pytest

from cli.cli import _add_common_env_help
from evaluator.routes import benchmark, data, evaluation, trajectory
from evaluator.schemas.evaluation import EvaluationMetadata
from evaluator.tools import migrate_to_platform_structure
from evaluator.validation.validation_runner import ValidationRunner

pytestmark = pytest.mark.anyio


def test_public_evaluator_routes_do_not_expose_use_cache():
    """Evaluator APIs should not make cache strategy part of Oscanner's contract."""
    public_callables = [
        evaluation.evaluate_author,
        evaluation.evaluate_gitee_contributor,
        data.get_gitee_commits,
        data.get_authors,
        trajectory.analyze_trajectory,
        trajectory.analyze_trajectory_stream,
        trajectory.analyze_trajectory_one_off,
        trajectory.analyze_trajectory_one_off_stream,
        trajectory.start_trajectory_analyze_one_off_poll,
        trajectory.get_trajectory_analyze_one_off_poll,
    ]

    for callable_obj in public_callables:
        assert "use_cache" not in inspect.signature(callable_obj).parameters


def test_response_metadata_does_not_advertise_cache_state():
    """Responses should not report cache state when Oscanner no longer owns caching."""
    assert "cached" not in EvaluationMetadata.model_fields


def test_validation_runner_repository_evaluation_has_no_cache_switch():
    """Validation should evaluate through the supplied evaluator without result reuse."""
    assert "use_cache" not in inspect.signature(ValidationRunner.evaluate_repository).parameters


def test_validation_runner_has_no_persistent_run_storage(tmp_path):
    """Validation runs should be returned to callers, not stored in validation_cache."""
    runner = ValidationRunner(storage_dir=tmp_path / "validation_cache")

    assert not hasattr(runner, "storage_dir")
    assert not hasattr(runner, "_save_run_result")
    assert not hasattr(runner, "list_validation_runs")
    assert not hasattr(runner, "get_validation_run")
    assert not (tmp_path / "validation_cache").exists()


def test_validation_routes_do_not_expose_saved_run_cache():
    """Benchmark validation should not expose cached run history endpoints."""
    route_paths = {
        getattr(route, "path", "")
        for route in benchmark.router.routes
    }

    assert "/api/benchmark/validation/runs" not in route_paths
    assert "/api/benchmark/validation/runs/{run_id}" not in route_paths


def test_frontend_validation_api_does_not_call_saved_run_cache():
    """Dashboard validation utilities should not call removed run-history APIs."""
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "frontend"
        / "webapp"
        / "utils"
        / "validationApi.ts"
    ).read_text(encoding="utf-8")

    assert "/api/benchmark/validation/runs" not in source
    assert "listRuns" not in source
    assert "getRun" not in source


def test_cli_help_does_not_advertise_evaluation_cache_env():
    """The CLI should not advertise removed evaluation-cache configuration."""
    parser = argparse.ArgumentParser(prog="oscanner")

    _add_common_env_help(parser)

    assert "OSCANNER_EVAL_CACHE_DIR" not in parser.epilog
    assert "evaluation cache" not in parser.epilog.lower()


def test_platform_migration_backup_ignores_removed_evaluation_cache(tmp_path):
    """Legacy platform migration should not preserve removed evaluator cache data."""
    data_root = tmp_path / "oscanner"
    (data_root / "data" / "owner" / "repo").mkdir(parents=True)
    (data_root / "evaluations" / "cache").mkdir(parents=True)
    (data_root / "evaluations" / "cache" / "ada.json").write_text("{}", encoding="utf-8")

    assert migrate_to_platform_structure.create_backup(data_root, tmp_path / "backup")

    assert (tmp_path / "backup" / "data").exists()
    assert not (tmp_path / "backup" / "evaluations").exists()


async def test_evaluate_author_does_not_touch_evaluation_cache(monkeypatch, tmp_path):
    """A repo evaluation should pass no previous evaluation and write no cache file."""
    commits_dir = tmp_path / "commits"
    commits_dir.mkdir()

    monkeypatch.setattr(evaluation, "get_llm_api_key", lambda: "fake-key")
    monkeypatch.setattr(evaluation, "resolve_plugin_id", lambda plugin: "zgc_ai_native_2026")
    monkeypatch.setattr(evaluation, "get_platform_data_dir", lambda platform, owner, repo, ref=None: tmp_path)
    monkeypatch.setattr(
        evaluation,
        "load_commits_from_local",
        lambda data_dir, limit=None: [
            {
                "sha": "abc123",
                "commit": {"author": {"name": "Ada", "email": "ada@example.com"}},
            }
        ],
    )

    class _ScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            return object()

    class _Meta:
        version = "1.0.0"

    monkeypatch.setattr(evaluation, "load_scan_module", lambda plugin_id: (_Meta(), _ScanModule(), "scan.py"))

    def fake_incremental(*, commits, author, previous_evaluation, **kwargs):
        assert author == "Ada"
        assert previous_evaluation is None
        return {
            "username": "Ada",
            "total_commits_analyzed": 1,
            "files_loaded": 0,
            "mode": "moderate",
            "scores": {"reasoning": "fresh"},
            "commits_summary": {
                "total_additions": 0,
                "total_deletions": 0,
                "files_changed": 0,
                "languages": [],
            },
            "evaluated_at": "2026-05-16T00:00:00",
        }

    monkeypatch.setattr(evaluation, "evaluate_author_incremental", fake_incremental)

    result = await evaluation.evaluate_author("owner", "repo", "Ada")

    assert result["success"] is True
    assert "cached" not in result["metadata"]
