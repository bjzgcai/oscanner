"""Tests for forwarded feature requirement messages in run-all."""

import asyncio
import json

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

    async def _fake_clone_repository(_repo_url, _sha, _tag):
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

    async def _fake_clone_repository(_repo_url, _sha, _tag):
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
