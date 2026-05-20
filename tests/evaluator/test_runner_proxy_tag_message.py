"""Tests for forwarding Courses feature requirements through evaluator proxy."""

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from evaluator.services.trajectory_poll_store import SQLiteTrajectoryPollStore
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
            clone_timeout=42,
            pipeline_timeout=123,
        )
    )

    async for _chunk in response.body_iterator:
        pass

    assert captured["url"] == "http://localhost:8001/api/runner/run-all"
    assert captured["json"]["tag"] == "class-01"
    assert captured["json"]["tag_message"] == "## Course tag requirements\n\n- /health returns JSON"
    assert captured["json"]["clone_timeout"] == 42
    assert captured["json"]["pipeline_timeout"] == 123


@pytest.mark.anyio
async def test_run_all_proxy_forwards_courses_branch(monkeypatch):
    captured = {}

    class _FakeRunnerResponse:
        status_code = 200
        text = ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aiter_bytes(self):
            yield b'data: {"event": "status", "data": {"status": "completed"}}\n\n'

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, json, headers):
            captured["json"] = json
            return _FakeRunnerResponse()

    monkeypatch.setattr(runner_proxy.httpx, "AsyncClient", _FakeClient)

    response = await runner_proxy.run_all_steps(
        runner_proxy.RunAllRequest(
            repo_url="https://gitee.com/zgcai/oscanner",
            branch="feat/update-gitee-ci-pipelines",
            tag_message="course requirements",
        )
    )

    async for _chunk in response.body_iterator:
        pass

    assert captured["json"]["repo_url"] == "https://gitee.com/zgcai/oscanner"
    assert captured["json"]["branch"] == "feat/update-gitee-ci-pipelines"
    assert captured["json"]["tag_message"] == "course requirements"


def test_runner_proxy_passes_image_artifacts_without_json_decoding(monkeypatch):
    class _FakeRunnerResponse:
        status_code = 200
        headers = {"content-type": "image/png"}
        content = b"png"

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, headers, content):
            return _FakeRunnerResponse()

    monkeypatch.setattr(runner_proxy.httpx, "AsyncClient", _FakeClient)

    app = FastAPI()
    app.include_router(runner_proxy.router)
    client = TestClient(app)

    response = client.get(
        "/api/runner/artifact",
        params={
            "repo_name": "demo-repo",
            "path": "TEST_ARTIFACTS_class-01/runtime-evidence/screenshots/homepage.png",
        },
    )

    assert response.status_code == 200
    assert response.content == b"png"
    assert response.headers["content-type"] == "image/png"


def test_runner_proxy_streams_explore_sse_without_buffering(monkeypatch):
    captured = {}

    class _FakeRunnerResponse:
        status_code = 200
        headers = {"content-type": "text/event-stream"}
        text = ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aiter_bytes(self):
            yield b'data: {"event": "progress", "data": {"message": "started"}}\n\n'
            yield b'data: {"event": "status", "data": {"status": "completed", "overview_path": "/tmp/REPO_OVERVIEW.md"}}\n\n'

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, headers=None, content=None):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = headers
            captured["content"] = content
            return _FakeRunnerResponse()

    monkeypatch.setattr(runner_proxy.httpx, "AsyncClient", _FakeClient)

    app = FastAPI()
    app.include_router(runner_proxy.router)
    client = TestClient(app)

    response = client.post(
        "/api/runner/explore/",
        params={"clone_path": "/tmp/repo"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert captured["method"] == "POST"
    assert captured["url"] == "http://localhost:8001/api/runner/explore/?clone_path=%2Ftmp%2Frepo"
    assert b'"message": "started"' in response.content
    assert b'"overview_path": "/tmp/REPO_OVERVIEW.md"' in response.content


@pytest.mark.anyio
async def test_run_all_poll_endpoint_persists_runner_events(monkeypatch, tmp_path):
    store = SQLiteTrajectoryPollStore(db_path=tmp_path / "runner-poll.sqlite3")
    monkeypatch.setattr(runner_proxy, "_runner_poll_store", store)

    async def fake_run_all_steps(_request):
        async def body():
            yield b'data: {"event":"progress","data":{"message":"Cloning repository"}}\n\n'
            yield (
                b'data: {"event":"status","data":{"status":"completed",'
                b'"results":{"passed":1,"failed":0,"total":1,"score":100}}}\n\n'
            )

        return StreamingResponse(body(), media_type="text/event-stream")

    monkeypatch.setattr(runner_proxy, "run_all_steps", fake_run_all_steps)

    start_response = await runner_proxy.start_run_all_poll(
        runner_proxy.RunAllRequest(repo_url="https://github.com/org/repo")
    )
    start_payload = json.loads(start_response.body)
    job_id = start_payload["job_id"]

    status = None
    for _ in range(20):
        await asyncio.sleep(0.01)
        status_response = await runner_proxy.get_run_all_poll(job_id, cursor=0)
        status = json.loads(status_response.body)
        if status["done"]:
            break

    assert start_payload["poll_url"] == f"/api/runner/run-all_poll/{job_id}"
    assert status["done"] is True
    assert status["events"] == [
        {
            "id": 0,
            "event": "message",
            "data": {"event": "progress", "data": {"message": "Cloning repository"}},
        },
        {
            "id": 1,
            "event": "message",
            "data": {
                "event": "status",
                "data": {
                    "status": "completed",
                    "results": {"passed": 1, "failed": 0, "total": 1, "score": 100},
                },
            },
        },
    ]
