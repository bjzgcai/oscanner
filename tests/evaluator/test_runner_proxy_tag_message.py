"""Tests for forwarding Courses feature requirements through evaluator proxy."""

import json

import pytest

from evaluator.routes import runner_proxy


@pytest.mark.anyio
async def test_run_all_proxy_forwards_tag_message(monkeypatch):
    captured = {}

    class _FakeRunnerResponse:
        status_code = 200
        text = ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aiter_bytes(self):
            yield (
                b'data: {"event": "status", "data": {"status": "completed", '
                b'"results": {"passed": 1, "failed": 0, "total": 1, "score": 100}}}\n\n'
            )

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, json, headers):
            captured["method"] = method
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _FakeRunnerResponse()

    monkeypatch.setattr(runner_proxy.httpx, "AsyncClient", _FakeClient)

    response = await runner_proxy.run_all_steps(
        runner_proxy.RunAllRequest(
            repo_url="https://gitee.com/org/repo",
            tag="class-01",
            tag_message="## Course tag requirements\n\n- /health returns JSON",
        )
    )

    async for _chunk in response.body_iterator:
        pass

    assert captured["url"] == "http://localhost:8001/api/runner/run-all"
    assert captured["json"]["tag"] == "class-01"
    assert captured["json"]["tag_message"] == "## Course tag requirements\n\n- /health returns JSON"
