"""Tests for GitHub CI and quality signal collection helpers."""

from unittest.mock import Mock

import requests

from evaluator.collectors.github import GitHubCollector


def _response(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_fetch_ci_quality_signals_collects_checks_statuses_and_workflows(monkeypatch):
    collector = GitHubCollector(token="token")
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append((url, params))
        if url.endswith("/commits/abc123/check-runs"):
            return _response({"check_runs": [{"id": 10, "name": "ci", "status": "completed"}]})
        if url.endswith("/check-runs/10/annotations"):
            return _response([{"path": "src/app.py", "annotation_level": "failure"}])
        if url.endswith("/commits/abc123/statuses"):
            return _response([{"context": "legacy-ci", "state": "success"}])
        if url.endswith("/commits/abc123/status"):
            return _response({"state": "success", "total_count": 1})
        if url.endswith("/actions/runs"):
            return _response({"workflow_runs": [{"id": 20, "head_sha": "abc123"}]})
        if url.endswith("/actions/runs/20/jobs"):
            return _response({"jobs": [{"id": 30, "name": "test", "conclusion": "success"}]})
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(requests, "get", fake_get)

    signals = collector.fetch_ci_quality_signals(
        "owner",
        "repo",
        "abc123",
        include_annotations=True,
        include_workflow_jobs=True,
    )

    assert signals["repo"] == "owner/repo"
    assert signals["ref"] == "abc123"
    assert signals["check_runs"][0]["annotations"] == [
        {"path": "src/app.py", "annotation_level": "failure"}
    ]
    assert signals["commit_statuses"] == [{"context": "legacy-ci", "state": "success"}]
    assert signals["combined_status"] == {"state": "success", "total_count": 1}
    assert signals["workflow_runs"][0]["jobs"] == [
        {"id": 30, "name": "test", "conclusion": "success"}
    ]
    assert signals["warnings"] == []
    assert (
        "https://api.github.com/repos/owner/repo/actions/runs",
        {"per_page": 100, "head_sha": "abc123"},
    ) in calls


def test_fetch_workflow_returns_workflow_metadata(monkeypatch):
    collector = GitHubCollector(token="token")

    def fake_get(url, headers=None, params=None, timeout=None):
        assert url == "https://api.github.com/repos/owner/repo/actions/workflows/ci.yml"
        return _response({"id": 1, "name": "CI", "path": ".github/workflows/ci.yml"})

    monkeypatch.setattr(requests, "get", fake_get)

    assert collector.fetch_workflow("owner", "repo", "ci.yml") == {
        "id": 1,
        "name": "CI",
        "path": ".github/workflows/ci.yml",
    }


def test_fetch_ci_quality_signals_records_endpoint_warnings(monkeypatch):
    collector = GitHubCollector(token="token")

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/commits/abc123/check-runs"):
            raise requests.exceptions.Timeout("timeout")
        if url.endswith("/commits/abc123/statuses"):
            return _response([])
        if url.endswith("/commits/abc123/status"):
            return _response({})
        if url.endswith("/actions/runs"):
            return _response({"workflow_runs": []})
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(requests, "get", fake_get)

    signals = collector.fetch_ci_quality_signals("owner", "repo", "abc123")

    assert signals["check_runs"] == []
    assert signals["commit_statuses"] == []
    assert signals["combined_status"] == {}
    assert signals["workflow_runs"] == []
    assert len(signals["warnings"]) == 1
    assert signals["warnings"][0].startswith("check_runs:")
