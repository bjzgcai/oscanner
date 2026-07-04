import asyncio
import json

import pytest
from fastapi.responses import StreamingResponse

from evaluator.services.trajectory_poll_store import SQLiteTrajectoryPollStore
from evaluator.routes.trajectory import format_sse_event, router
from plugins.zgc_ai_native_2026.scan import extract_stream_delta


def test_format_sse_event_emits_named_json_event():
    assert format_sse_event("token", {"content": "hello"}) == (
        'event: token\n'
        'data: {"content":"hello"}\n\n'
    )


def test_extract_stream_delta_reads_openai_compatible_delta():
    line = "data: " + json.dumps({
        "choices": [
            {"delta": {"content": "partial text"}}
        ]
    })

    assert extract_stream_delta(line) == "partial text"


def test_extract_stream_delta_ignores_done_and_empty_lines():
    assert extract_stream_delta("data: [DONE]") is None
    assert extract_stream_delta("") is None


def test_regular_trajectory_stream_endpoint_is_registered():
    paths = {route.path for route in router.routes}

    assert "/api/trajectory/analyze_stream" in paths


def test_one_off_poll_endpoints_are_registered():
    route_methods = {
        (route.path, next(iter(route.methods)))
        for route in router.routes
        if getattr(route, "methods", None)
    }

    assert ("/api/trajectory/analyze_one_off_poll", "POST") in route_methods
    assert ("/api/trajectory/analyze_one_off_poll/{job_id}", "GET") in route_methods


@pytest.mark.anyio
async def test_trajectory_queue_status_endpoint(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route
    from evaluator.services.task_queue import EvaluatorQueue

    queue = EvaluatorQueue(max_concurrent=2, max_pending=7)
    monkeypatch.setattr(trajectory_route, "evaluator_queue", queue)

    assert await trajectory_route.get_trajectory_queue_status() == {
        "max_concurrent": 2,
        "running": 0,
        "pending": 0,
        "max_pending": 7,
    }


@pytest.mark.anyio
async def test_one_off_poll_endpoint_persists_stream_events(monkeypatch, tmp_path):
    from evaluator.routes import trajectory as trajectory_route

    async def fake_analyze_trajectory_one_off_stream(**_kwargs):
        async def body():
            yield format_sse_event("section", {"title": "connected"})
            yield format_sse_event("result", {"success": True})
            yield format_sse_event("done", {"finish_reason": "stop"})

        return StreamingResponse(body(), media_type="text/event-stream")

    store = SQLiteTrajectoryPollStore(db_path=tmp_path / "poll.sqlite3")
    monkeypatch.setattr(trajectory_route, "_trajectory_poll_store", store)
    monkeypatch.setattr(
        trajectory_route,
        "analyze_trajectory_one_off_stream",
        fake_analyze_trajectory_one_off_stream,
    )

    start_response = await trajectory_route.start_trajectory_analyze_one_off_poll(
        request_body={"repo_url": "https://github.com/org/repo", "username": "Ada"},
    )
    start_payload = json.loads(start_response.body)
    job_id = start_payload["job_id"]

    for _ in range(20):
        await asyncio.sleep(0.01)
        status_response = await trajectory_route.get_trajectory_analyze_one_off_poll(
            job_id,
            cursor=0,
        )
        status = json.loads(status_response.body)
        if status["done"]:
            break

    assert start_payload["poll_url"] == f"/api/trajectory/analyze_one_off_poll/{job_id}"
    assert status["done"] is True
    assert status["events"] == [
        {"id": 0, "event": "section", "data": {"title": "connected"}},
        {"id": 1, "event": "result", "data": {"success": True}},
        {"id": 2, "event": "done", "data": {"finish_reason": "stop"}},
    ]
