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
