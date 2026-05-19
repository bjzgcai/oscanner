"""Regression tests for runner SSE streaming behavior."""

import asyncio
import json
import time

from repos_runner.routes import runner as runner_route


def test_run_tests_stream_flushes_progress_before_blocking_work(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    report_path = clone_dir / "TEST_REPORT.md"
    report_path.write_text("report body", encoding="utf-8")

    async def _fake_run_tests(
        _clone_path,
        _overview_path,
        progress_callback,
        setup_timeout,
        test_timeout,
        tag_message=None,
        tag=None,
    ):
        await progress_callback("first progress")
        time.sleep(0.2)
        return {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "score": 100,
            "report_path": str(report_path),
        }

    monkeypatch.setattr(runner_route, "run_tests", _fake_run_tests)

    async def _read_events():
        response = await runner_route.run_tests_stream(
            str(clone_dir),
            str(clone_dir / "REPO_OVERVIEW.md"),
        )
        iterator = response.body_iterator.__aiter__()

        start = time.monotonic()
        first_chunk = await iterator.__anext__()
        first_duration = time.monotonic() - start

        chunks = [first_chunk]
        async for chunk in iterator:
            chunks.append(chunk)

        events = []
        for chunk in chunks:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for line in text.splitlines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
        return first_duration, events

    first_duration, events = asyncio.run(_read_events())

    assert first_duration < 0.1
    assert events[0] == {
        "event": "progress",
        "data": {"message": "first progress"},
    }
    assert events[-1]["event"] == "status"
    assert events[-1]["data"]["status"] == "completed"


def test_explore_stream_forwards_feature_requirements(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    overview_path = clone_dir / "REPO_OVERVIEW.md"
    overview_path.write_text("overview", encoding="utf-8")
    calls = {}

    async def _fake_explore_repository(_clone_path, _progress_callback, tag_message=None, tag=None):
        calls["tag_message"] = tag_message
        calls["tag"] = tag
        return str(overview_path)

    monkeypatch.setattr(runner_route, "explore_repository", _fake_explore_repository)

    async def _collect_completed():
        response = await runner_route.explore_repo_stream(
            str(clone_dir),
            feature_requirements="Login\nReports export",
        )
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for line in text.splitlines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    if event["event"] == "status":
                        return event["data"]
        raise AssertionError("status event not found")

    completed = asyncio.run(_collect_completed())

    assert completed["status"] == "completed"
    assert calls == {"tag_message": "Login\nReports export", "tag": None}


def test_run_tests_stream_forwards_feature_requirements(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    report_path = clone_dir / "TEST_REPORT.md"
    report_path.write_text("report body", encoding="utf-8")
    calls = {}

    async def _fake_run_tests(
        _clone_path,
        _overview_path,
        _progress_callback,
        setup_timeout,
        test_timeout,
        tag_message=None,
        tag=None,
    ):
        calls["tag_message"] = tag_message
        calls["tag"] = tag
        return {
            "total": 2,
            "passed": 2,
            "failed": 0,
            "skipped": 0,
            "score": 100,
            "feature_coverage": {
                "covered": ["Login", "Reports export"],
                "not_covered": [],
                "coverage_ratio": 1.0,
            },
            "report_path": str(report_path),
        }

    monkeypatch.setattr(runner_route, "run_tests", _fake_run_tests)

    async def _collect_completed():
        response = await runner_route.run_tests_stream(
            str(clone_dir),
            str(clone_dir / "REPO_OVERVIEW.md"),
            feature_requirements="Login\nReports export",
        )
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for line in text.splitlines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    if event["event"] == "status":
                        return event["data"]
        raise AssertionError("status event not found")

    completed = asyncio.run(_collect_completed())

    assert completed["status"] == "completed"
    assert completed["results"]["feature_coverage"]["covered"] == ["Login", "Reports export"]
    assert calls == {"tag_message": "Login\nReports export", "tag": None}


def test_detect_tests_returns_validation_features(monkeypatch, tmp_path):
    clone_dir = tmp_path / "repo"
    clone_dir.mkdir()
    overview_path = clone_dir / "REPO_OVERVIEW.md"
    overview_path.write_text("overview", encoding="utf-8")

    async def _fake_detect_test_commands(_overview_path):
        return {
            "setup_commands": ["npm install"],
            "test_commands": ["npm test"],
            "language": "node",
        }

    monkeypatch.setattr(runner_route, "detect_test_commands", _fake_detect_test_commands)

    result = asyncio.run(
        runner_route.detect_tests(
            str(overview_path),
            feature_requirements="- Login\n- Reports export\n3. Audit log",
        )
    )

    assert result["test_commands"] == ["npm test"]
    assert result["validation_features"] == ["Login", "Reports export", "Audit log"]
