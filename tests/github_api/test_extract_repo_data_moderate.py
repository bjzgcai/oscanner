"""Tests for the moderate GitHub extraction tool."""

import socket
import urllib.request

from backend.evaluator.tools import extract_repo_data_moderate as extractor


def test_http_get_uses_timeout_and_returns_none_on_timeout(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        raise socket.timeout("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    data, headers = extractor.http_get("https://api.github.com/repos/example/repo")

    assert data is None
    assert headers is None
    assert captured["timeout"] == extractor.DEFAULT_HTTP_TIMEOUT_SECONDS
