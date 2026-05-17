"""Regression tests for removing Oscanner-owned cache strategy."""

import inspect

import pytest

from evaluator.routes import data, evaluation, trajectory
from evaluator.schemas.evaluation import EvaluationMetadata
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
    ]

    for callable_obj in public_callables:
        assert "use_cache" not in inspect.signature(callable_obj).parameters


def test_response_metadata_does_not_advertise_cache_state():
    """Responses should not report cache state when Oscanner no longer owns caching."""
    assert "cached" not in EvaluationMetadata.model_fields


def test_validation_runner_repository_evaluation_has_no_cache_switch():
    """Validation should evaluate through the supplied evaluator without result reuse."""
    assert "use_cache" not in inspect.signature(ValidationRunner.evaluate_repository).parameters


async def test_evaluate_author_does_not_touch_evaluation_cache(monkeypatch, tmp_path):
    """A repo evaluation should pass no previous evaluation and write no cache file."""
    commits_dir = tmp_path / "commits"
    commits_dir.mkdir()

    monkeypatch.setattr(evaluation, "get_llm_api_key", lambda: "fake-key")
    monkeypatch.setattr(evaluation, "resolve_plugin_id", lambda plugin: "zgc_simple")
    monkeypatch.setattr(evaluation, "get_platform_data_dir", lambda platform, owner, repo: tmp_path)
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
