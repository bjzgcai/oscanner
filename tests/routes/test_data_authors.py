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
    assert result["data"]["cached"] is False


@pytest.mark.anyio
async def test_get_authors_uses_local_cache_when_contributors_empty(monkeypatch, tmp_path):
    """A contributors miss should not force full extraction when local cache exists."""
    commits_dir = tmp_path / "commits"
    commits_dir.mkdir()
    (commits_dir / "abc.json").write_text(
        '{"commit": {"author": {"name": "Cached Author", "email": "cached@example.com"}}}',
        encoding="utf-8",
    )

    monkeypatch.setattr(data, "get_platform_data_dir", lambda platform, owner, repo: tmp_path)
    monkeypatch.setattr(data, "_fetch_gitee_contributors_authors", lambda owner, repo: [])
    monkeypatch.setattr(
        data,
        "_extract_platform_data",
        lambda platform, owner, repo: (_ for _ in ()).throw(AssertionError("should not extract")),
    )

    result = await data.get_authors("zgcai", "oscanner", Response(), platform="gitee", use_cache=True)

    assert result["data"]["authors"] == [
        {"author": "Cached Author", "email": "cached@example.com", "commits": 1}
    ]
