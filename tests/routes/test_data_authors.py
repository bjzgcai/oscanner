"""Tests for author discovery routes."""

from unittest.mock import Mock

import pytest
from fastapi import Response

from evaluator.routes import data


def test_fetch_gitee_contributors_authors_normalizes_committers(monkeypatch):
    """Gitee contributors should become the existing authors response shape."""
    monkeypatch.setattr(data, "get_gitee_token", lambda: "fake-token")

    response = Mock()
    response.status_code = 200
    response.json.return_value = [
        {"name": "Alice", "email": "alice@example.com", "commits": 7},
        {"name": "Bob", "email": "", "contributions": 3},
    ]

    session = Mock()
    session.get.return_value = response
    monkeypatch.setattr(data, "get_requests_session", lambda: session)

    authors = data._fetch_gitee_contributors_authors("zgcai", "oscanner")

    assert authors == [
        {"author": "Alice", "email": "alice@example.com", "commits": 7},
        {"author": "Bob", "email": "", "commits": 3},
    ]
    session.get.assert_called_once_with(
        "https://gitee.com/api/v5/repos/zgcai/oscanner/contributors",
        params={"access_token": "fake-token", "type": "committers"},
        timeout=10,
    )


def test_fetch_gitee_contributors_authors_deduplicates_and_sorts(monkeypatch):
    """Duplicate contributor names should be merged and sorted by commit count."""
    monkeypatch.setattr(data, "get_gitee_token", lambda: "fake-token")

    response = Mock()
    response.status_code = 200
    response.json.return_value = [
        {"name": "Bob", "commits": 2},
        {"name": "Alice", "commits": 1},
        {"name": "Bob", "email": "bob@example.com", "commits": 3},
    ]

    session = Mock()
    session.get.return_value = response
    monkeypatch.setattr(data, "get_requests_session", lambda: session)

    authors = data._fetch_gitee_contributors_authors("zgcai", "oscanner")

    assert authors == [
        {"author": "Bob", "email": "bob@example.com", "commits": 5},
        {"author": "Alice", "email": "", "commits": 1},
    ]


def test_fetch_gitee_contributors_authors_returns_empty_without_token(monkeypatch):
    """Missing Gitee token should let callers fall back to local/extraction paths."""
    monkeypatch.setattr(data, "get_gitee_token", lambda: None)

    session = Mock()
    monkeypatch.setattr(data, "get_requests_session", lambda: session)

    assert data._fetch_gitee_contributors_authors("zgcai", "oscanner") == []
    session.get.assert_not_called()


def test_extract_platform_data_uses_commit_only_github_extraction(monkeypatch):
    """Author discovery should skip file context downloads for GitHub."""
    calls = []

    def fake_extract_github(owner, repo, *, include_file_context=True):
        calls.append((owner, repo, include_file_context))
        return True

    monkeypatch.setattr(data, "extract_github_data", fake_extract_github)

    assert data._extract_platform_data("github", "bjzgcai", "AI-History-Show") is True
    assert calls == [("bjzgcai", "AI-History-Show", False)]


@pytest.mark.anyio
async def test_get_authors_returns_gitee_contributors_without_extraction(monkeypatch, tmp_path):
    """Fast Gitee contributors should bypass full repository extraction."""
    authors = [{"author": "Alice", "email": "", "commits": 9}]
    monkeypatch.setattr(data, "get_platform_data_dir", lambda platform, owner, repo: tmp_path)
    monkeypatch.setattr(data, "_fetch_gitee_contributors_authors", lambda owner, repo: authors)
    monkeypatch.setattr(
        data,
        "_extract_platform_data",
        lambda platform, owner, repo: (_ for _ in ()).throw(AssertionError("should not extract")),
    )

    result = await data.get_authors("zgcai", "oscanner", Response(), platform="gitee")

    assert result["data"]["authors"] == authors


@pytest.mark.anyio
async def test_get_authors_refreshes_when_contributors_empty(monkeypatch, tmp_path):
    """A contributors miss should refresh repository data before reading authors."""
    commits_dir = tmp_path / "commits"
    commits_dir.mkdir()
    extraction_calls = []

    monkeypatch.setattr(data, "get_platform_data_dir", lambda platform, owner, repo: tmp_path)
    monkeypatch.setattr(data, "_fetch_gitee_contributors_authors", lambda owner, repo: [])

    def fake_extract(platform, owner, repo):
        extraction_calls.append((platform, owner, repo))
        (commits_dir / "abc.json").write_text(
            '{"commit": {"author": {"name": "Fresh Author", "email": "fresh@example.com"}}}',
            encoding="utf-8",
        )
        return True

    monkeypatch.setattr(data, "_extract_platform_data", fake_extract)

    result = await data.get_authors("zgcai", "oscanner", Response(), platform="gitee")

    assert extraction_calls == [("gitee", "zgcai", "oscanner")]
    assert result["data"]["authors"] == [
        {"author": "Fresh Author", "email": "fresh@example.com", "commits": 1}
    ]
