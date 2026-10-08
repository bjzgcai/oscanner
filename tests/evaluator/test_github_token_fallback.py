"""Tests for GitHub fallback-token (GITHUB_TOKEN2) rotation."""

import sys
from pathlib import Path

import httpx

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from evaluator.config import tokens as tokens_mod
from evaluator.services import github_auth
from evaluator.tools import extract_repo_data_moderate as extract_tool


def test_get_github_tokens_orders_primary_before_fallbacks(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "primary")
    monkeypatch.setenv("GITHUB_TOKEN2", "fallback")
    monkeypatch.setenv("GITHUB_TOKEN3", "third")

    assert tokens_mod.get_github_tokens() == ["primary", "fallback", "third"]


def test_get_github_tokens_skips_empty_and_duplicates(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "same")
    monkeypatch.setenv("GITHUB_TOKEN2", "same")
    monkeypatch.setenv("GITHUB_TOKEN3", "")

    assert tokens_mod.get_github_tokens() == ["same"]


def test_get_github_tokens_empty_when_unset(monkeypatch):
    for key in tokens_mod.GITHUB_TOKEN_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    assert tokens_mod.get_github_tokens() == []


def test_github_token_candidates_puts_primary_first(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "primary")
    monkeypatch.setenv("GITHUB_TOKEN2", "fallback")

    assert github_auth.github_token_candidates("explicit") == ["explicit", "primary", "fallback"]
    assert github_auth.github_token_candidates("primary") == ["primary", "fallback"]
    assert github_auth.github_token_candidates(None) == ["primary", "fallback"]


def test_github_request_rotates_to_fallback_token(monkeypatch):
    monkeypatch.setattr(github_auth, "get_github_tokens", lambda: ["primary", "fallback"])

    seen_headers = []

    class FakeClient:
        def request(self, method, url, *, headers=None, params=None, json=None, content=None):
            seen_headers.append(headers.get("Authorization"))
            if headers.get("Authorization") == "Bearer primary":
                return httpx.Response(
                    403,
                    headers={"x-ratelimit-remaining": "0"},
                    json={"message": "API rate limit exceeded"},
                )
            return httpx.Response(200, json={"ok": True})

    response = github_auth.github_request(FakeClient(), "GET", "https://api.github.com/rate_limit")

    assert response.status_code == 200
    assert seen_headers == ["Bearer primary", "Bearer fallback"]


def test_github_request_waits_when_all_tokens_limited(monkeypatch):
    monkeypatch.setattr(github_auth, "get_github_tokens", lambda: ["only"])
    request = httpx.Request("GET", "https://api.github.com/x")
    responses = [
        httpx.Response(
            403,
            request=request,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "101"},
            json={"message": "API rate limit exceeded"},
        ),
        httpx.Response(200, request=request, json={"ok": True}),
    ]

    class FakeClient:
        def request(self, method, url, *, headers=None, params=None, json=None, content=None):
            return responses.pop(0)

    sleeps = []
    monkeypatch.setattr(github_auth.time, "time", lambda: 100)
    monkeypatch.setattr(github_auth.time, "sleep", sleeps.append)

    response = github_auth.github_request(FakeClient(), "GET", "https://api.github.com/x")

    assert response.status_code == 200
    assert sleeps == [2.0]


def test_extractor_tool_candidate_tokens_reads_env_fallbacks(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "primary")
    monkeypatch.setenv("GITHUB_TOKEN2", "fallback")

    assert extract_tool._candidate_tokens(None) == ["primary", "fallback"]
    assert extract_tool._candidate_tokens("explicit") == ["explicit", "primary", "fallback"]


def test_extractor_tool_http_get_rotates_on_rate_limit(monkeypatch):
    calls = []

    def fake_http_get_once(url, token=None):
        calls.append(token)
        if token == "primary":
            return None, None, True
        return "{}", [], False

    monkeypatch.setattr(extract_tool, "_http_get_once", fake_http_get_once)

    data, headers = extract_tool.http_get("https://api.github.com/x", ["primary", "fallback"])

    assert data == "{}"
    assert calls == ["primary", "fallback"]
