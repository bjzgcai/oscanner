"""Security-focused tests for repo URL parsing and auth token injection."""

import pytest

from repos_runner.services.repo_service.clone import _inject_auth_token
from repos_runner.services.repo_service.paths import parse_repo_url


def test_parse_repo_url_accepts_exact_github_hosts():
    assert parse_repo_url("https://github.com/octocat/hello-world.git") == (
        "github",
        "octocat",
        "hello-world",
    )
    assert parse_repo_url("github.com/octocat/hello-world") == (
        "github",
        "octocat",
        "hello-world",
    )


def test_parse_repo_url_rejects_substring_host_attack():
    with pytest.raises(ValueError):
        parse_repo_url("https://evilgithub.com/octocat/hello-world")

    with pytest.raises(ValueError):
        parse_repo_url("https://notgitee.com/org/repo")


def test_inject_auth_token_only_for_exact_allowed_host(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret_token")

    good = _inject_auth_token("https://github.com/octocat/hello-world.git")
    bad = _inject_auth_token("https://evilgithub.com/octocat/hello-world.git")

    assert "oauth2:ghp_secret_token@" in good
    assert bad == "https://evilgithub.com/octocat/hello-world.git"


def test_inject_auth_token_skips_urls_with_existing_userinfo(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret_token")
    original = "https://user:pass@github.com/octocat/hello-world.git"

    assert _inject_auth_token(original) == original
