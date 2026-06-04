"""Regression tests for email-based evaluation identities."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from evaluator.routes import evaluation


pytestmark = pytest.mark.anyio


def _commit(sha: str, email: str, name: str = "Alice"):
    return {
        "sha": sha,
        "commit": {
            "author": {"name": name, "email": email},
            "committer": {"name": name, "email": email},
            "message": "feat: work",
        },
    }


async def test_evaluate_author_merges_multiple_emails_with_email_commit_weights(monkeypatch, tmp_path):
    commits = [
        _commit("a1", "alice@example.com"),
        _commit("a2", "alice@work.com"),
        _commit("b1", "bob@example.com", name="Bob"),
    ]
    calls = []
    captured_merge = {}

    class ScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            return object()

    def fake_incremental(**kwargs):
        calls.append({"author": kwargs["author"], "aliases": kwargs.get("aliases")})
        return {
            "username": kwargs["author"],
            "total_commits_evaluated": 1,
            "scores": {
                "spec_quality": 80,
                "cloud_architecture": 70,
                "ai_engineering": 60,
                "mastery_professionalism": 90,
                "reasoning": f"reasoning for {kwargs['author']}",
            },
            "commits_summary": {
                "total_additions": 1,
                "total_deletions": 0,
                "files_changed": 1,
                "languages": ["Python"],
            },
        }

    def fake_merge(evaluations_data, model):
        captured_merge["evaluations_data"] = evaluations_data
        return {
            "username": "alice@example.com + alice@work.com",
            "scores": {"spec_quality": 80, "reasoning": "merged"},
            "total_commits_analyzed": 2,
            "commits_summary": {},
        }

    monkeypatch.setattr(evaluation, "get_llm_api_key", lambda: "fake-key")
    monkeypatch.setattr(evaluation, "resolve_plugin_id", lambda plugin: "zgc_ai_native_2026")
    monkeypatch.setattr(evaluation, "load_scan_module", lambda plugin_id: (SimpleNamespace(version="0.1.0"), ScanModule(), "scan.py"))
    monkeypatch.setattr(evaluation, "get_platform_data_dir", lambda platform, owner, repo, ref=None: tmp_path)
    monkeypatch.setattr(evaluation, "load_commits_from_local", lambda data_dir, limit=None: commits)
    monkeypatch.setattr(evaluation, "evaluate_author_incremental", fake_incremental)
    monkeypatch.setattr(evaluation, "merge_evaluations_logic", fake_merge)

    result = await evaluation.evaluate_author(
        "owner",
        "repo",
        "alice@example.com",
        model="test-model",
        platform="github",
        plugin="zgc_ai_native_2026",
        request_body={"emails": ["alice@example.com", "alice@work.com"]},
    )

    assert result["success"] is True
    assert [call["author"] for call in calls] == ["alice@example.com", "alice@work.com"]
    assert [item["weight"] for item in captured_merge["evaluations_data"]] == [1, 1]
    assert result["evaluation"]["email"] == "alice@example.com"
    assert result["metadata"]["source"] == "merged_emails"


async def test_evaluate_author_accepts_primary_email_field(monkeypatch, tmp_path):
    commits = [_commit("a1", "alice@example.com")]
    calls = []

    class ScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            return object()

    def fake_incremental(**kwargs):
        calls.append(kwargs)
        return {
            "username": kwargs["author"],
            "total_commits_evaluated": 1,
            "scores": {
                "spec_quality": 80,
                "cloud_architecture": 70,
                "ai_engineering": 60,
                "mastery_professionalism": 90,
                "reasoning": "email result",
            },
            "commits_summary": {
                "total_additions": 1,
                "total_deletions": 0,
                "files_changed": 1,
                "languages": ["Python"],
            },
        }

    monkeypatch.setattr(evaluation, "get_llm_api_key", lambda: "fake-key")
    monkeypatch.setattr(evaluation, "resolve_plugin_id", lambda plugin: "zgc_ai_native_2026")
    monkeypatch.setattr(evaluation, "load_scan_module", lambda plugin_id: (SimpleNamespace(version="0.1.0"), ScanModule(), "scan.py"))
    monkeypatch.setattr(evaluation, "get_platform_data_dir", lambda platform, owner, repo, ref=None: tmp_path)
    monkeypatch.setattr(evaluation, "load_commits_from_local", lambda data_dir, limit=None: commits)
    monkeypatch.setattr(evaluation, "evaluate_author_incremental", fake_incremental)

    result = await evaluation.evaluate_author(
        "owner",
        "repo",
        "legacy-route-identity",
        model="test-model",
        platform="github",
        plugin="zgc_ai_native_2026",
        request_body={"email": "Alice@Example.COM"},
    )

    assert calls[0]["author"] == "alice@example.com"
    assert result["evaluation"]["username"] == "alice@example.com"
    assert result["evaluation"]["email"] == "alice@example.com"


async def test_evaluate_author_rejects_invalid_email_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluation, "get_llm_api_key", lambda: "fake-key")
    monkeypatch.setattr(evaluation, "resolve_plugin_id", lambda plugin: "zgc_ai_native_2026")
    monkeypatch.setattr(evaluation, "get_platform_data_dir", lambda platform, owner, repo, ref=None: tmp_path)
    monkeypatch.setattr(
        evaluation,
        "load_scan_module",
        lambda plugin_id: (SimpleNamespace(version="0.1.0"), SimpleNamespace(create_commit_evaluator=lambda **kwargs: object()), "scan.py"),
    )
    monkeypatch.setattr(evaluation, "load_commits_from_local", lambda data_dir, limit=None: [])

    with pytest.raises(HTTPException) as exc_info:
        await evaluation.evaluate_author(
            "owner",
            "repo",
            "alice@example.com",
            model="test-model",
            platform="github",
            plugin="zgc_ai_native_2026",
            request_body={"emails": ["alice@example.com", "not-an-email"]},
        )

    assert exc_info.value.status_code == 400
    assert "Invalid email" in str(exc_info.value.detail)
