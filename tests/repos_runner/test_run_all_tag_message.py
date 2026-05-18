"""Tests for forwarded feature requirement messages in run-all."""

import asyncio
import json
import time

from fastapi.responses import JSONResponse

from repos_runner.routes import runner as runner_route
from repos_runner.schemas import RunAllRequest
from repos_runner.services.repo_service.llm import record_token_usage


def test_run_all_request_accepts_forwarded_tag_message():
    request = RunAllRequest(
        repo_url="https://github.com/org/repo",
        tag="class-01",
        tag_message="Merged course and repository requirements",
    )

    assert request.tag_message == "Merged course and repository requirements"


def test_run_all_request_accepts_runner_timeouts():
    request = RunAllRequest(
        repo_url="https://github.com/org/repo",
        clone_timeout=12,
        pipeline_timeout=0.05,
    )

    assert request.clone_timeout == 12
    assert request.pipeline_timeout == 0.05


def test_run_all_uses_forwarded_tag_message(monkeypatch, tmp_path):
    calls = {
        "fetched_remote": 0,
        "explore_tag_message": None,
        "run_tag_message": None,
    }
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    report_path = clone_dir / "TEST_REPORT_class-01.md"
    report_path.write_text("report body", encoding="utf-8")

    async def _fake_clone_repository(_repo_url, _sha, _tag, timeout=300):
        return {"clone_path": str(clone_dir), "repo_name": "repo"}

    async def _fake_fetch_gitee_tag_message(_repo_url, _tag):
        calls["fetched_remote"] += 1
        return "remote message that should not replace request tag_message"

    async def _fake_explore_repository(_clone_path, _progress_callback, tag_message, tag=None):
        calls["explore_tag_message"] = tag_message
        overview_path = clone_dir / f"REPO_OVERVIEW_{tag}.md"
        overview_path.write_text("overview", encoding="utf-8")
        return str(overview_path)

    async def _fake_run_tests(
        _clone_path,
        _overview_path,
        _progress_callback,
        setup_timeout,
        test_timeout,
        tag_message=None,
        tag=None,
    ):
        calls["run_tag_message"] = tag_message
        return {
            "repo_name": "org/repo",
            "passed": 1,
            "failed": 0,
            "total": 1,
            "score": 100,
            "report_path": str(report_path),
        }

    monkeypatch.setattr(runner_route, "clone_repository", _fake_clone_repository)
    monkeypatch.setattr(runner_route, "fetch_gitee_tag_message", _fake_fetch_gitee_tag_message)
    monkeypatch.setattr(runner_route, "explore_repository", _fake_explore_repository)
    monkeypatch.setattr(runner_route, "run_tests", _fake_run_tests)

    response = asyncio.run(
        runner_route.run_all_stream(
            RunAllRequest(
                repo_url="https://github.com/org/repo",
                tag="class-01",
                tag_message="Forwarded feature requirements",
            )
        )
    )

    async def _collect_events():
        events = []
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for line in text.splitlines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
        return events

    events = asyncio.run(_collect_events())
    completed = [
        event
        for event in events
        if event["event"] == "status" and event["data"]["status"] == "completed"
    ]

    assert completed
    assert calls["fetched_remote"] == 0
    assert calls["explore_tag_message"] == "Forwarded feature requirements"
    assert calls["run_tag_message"] == "Forwarded feature requirements"


def test_run_all_reports_accumulated_token_usage(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    report_path = clone_dir / "TEST_REPORT.md"
    report_path.write_text("report body", encoding="utf-8")

    async def _fake_clone_repository(_repo_url, _sha, _tag, timeout=300):
        return {"clone_path": str(clone_dir), "repo_name": "repo"}

    async def _fake_explore_repository(_clone_path, _progress_callback, _tag_message, tag=None):
        record_token_usage({"input_tokens": 100, "output_tokens": 20, "total_tokens": 120})
        overview_path = clone_dir / "REPO_OVERVIEW.md"
        overview_path.write_text("overview", encoding="utf-8")
        return str(overview_path)

    async def _fake_run_tests(
        _clone_path,
        _overview_path,
        _progress_callback,
        setup_timeout,
        test_timeout,
        tag_message=None,
        tag=None,
    ):
        record_token_usage({"input_tokens": 7, "output_tokens": 3, "total_tokens": 10})
        return {
            "repo_name": "org/repo",
            "passed": 1,
            "failed": 0,
            "total": 1,
            "score": 100,
            "report_path": str(report_path),
        }

    monkeypatch.setattr(runner_route, "clone_repository", _fake_clone_repository)
    monkeypatch.setattr(runner_route, "explore_repository", _fake_explore_repository)
    monkeypatch.setattr(runner_route, "run_tests", _fake_run_tests)

    response = asyncio.run(
        runner_route.run_all_stream(RunAllRequest(repo_url="https://github.com/org/repo"))
    )

    async def _collect_completed():
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for line in text.splitlines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    if event["event"] == "status" and event["data"]["status"] == "completed":
                        return event["data"]
        raise AssertionError("completed status event not found")

    completed = asyncio.run(_collect_completed())

    assert completed["token_usage"] == {
        "input_tokens": 107,
        "output_tokens": 23,
        "total_tokens": 130,
        "source": "provider",
    }
    assert completed["results"]["token_usage"] == completed["token_usage"]


def test_run_all_times_out_entire_pipeline(monkeypatch):
    async def _slow_clone_repository(_repo_url, _sha, _tag, timeout=300):
        await asyncio.sleep(1)
        return {"clone_path": "/tmp/never", "repo_name": "never"}

    monkeypatch.setattr(runner_route, "clone_repository", _slow_clone_repository)

    response = asyncio.run(
        runner_route.run_all_stream(
            RunAllRequest(
                repo_url="https://github.com/org/repo",
                pipeline_timeout=0.01,
            )
        )
    )

    async def _collect_failed():
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for line in text.splitlines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    if event["event"] == "status" and event["data"]["status"] == "failed":
                        return event["data"]
        raise AssertionError("failed status event not found")

    failed = asyncio.run(_collect_failed())

    assert failed["error"] == "Pipeline timed out after 0.01s"


def test_run_all_keeps_event_loop_responsive_during_blocking_test(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    overview_path = clone_dir / "REPO_OVERVIEW.md"
    overview_path.write_text("overview", encoding="utf-8")
    report_path = clone_dir / "TEST_REPORT.md"
    report_path.write_text("report body", encoding="utf-8")

    async def _fake_clone_repository(_repo_url, _sha, _tag, timeout=300):
        return {"clone_path": str(clone_dir), "repo_name": "repo"}

    async def _fake_explore_repository(_clone_path, _progress_callback, _tag_message, tag=None):
        return str(overview_path)

    async def _blocking_run_tests(
        _clone_path,
        _overview_path,
        _progress_callback,
        setup_timeout,
        test_timeout,
        tag_message=None,
        tag=None,
    ):
        time.sleep(0.12)
        return {
            "repo_name": "org/repo",
            "passed": 1,
            "failed": 0,
            "total": 1,
            "score": 100,
            "report_path": str(report_path),
        }

    monkeypatch.setattr(runner_route, "clone_repository", _fake_clone_repository)
    monkeypatch.setattr(runner_route, "explore_repository", _fake_explore_repository)
    monkeypatch.setattr(runner_route, "run_tests", _blocking_run_tests)

    async def _consume_response(response):
        async for _chunk in response.body_iterator:
            pass

    async def _assert_responsive():
        response = await runner_route.run_all_stream(
            RunAllRequest(repo_url="https://github.com/org/repo")
        )
        consumer = asyncio.create_task(_consume_response(response))
        started_at = time.perf_counter()
        await asyncio.sleep(0.03)
        elapsed = time.perf_counter() - started_at
        await consumer
        assert elapsed < 0.08

    asyncio.run(_assert_responsive())


def test_get_report_returns_testing_status_for_active_run(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()

    monkeypatch.setattr(runner_route, "get_repos_dir", lambda: repos_dir)
    monkeypatch.setattr(
        runner_route,
        "parse_repo_url",
        lambda _repo_url: ("github", "org", "repo"),
    )

    key = runner_route._active_report_key("https://github.com/org/repo", "class-01")
    runner_route._ACTIVE_RUN_ALL_REPORTS.add(key)
    try:
        response = asyncio.run(
            runner_route.get_report("https://github.com/org/repo", tag="class-01")
        )
    finally:
        runner_route._ACTIVE_RUN_ALL_REPORTS.discard(key)

    assert isinstance(response, JSONResponse)
    assert response.status_code == 202
