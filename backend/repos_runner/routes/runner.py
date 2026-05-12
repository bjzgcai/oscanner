"""
API routes for Repository Runner
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
from fastapi.responses import StreamingResponse
from repos_runner.schemas import (
    RepoCloneRequest,
    RepoMetadata,
    TestSummary,
    RunAllRequest,
    BatchRunRequest,
)
from repos_runner.services import (
    clone_repository,
    explore_repository,
    run_tests,
    detect_test_commands,
    list_repos,
    delete_repo,
)
from repos_runner.services.repo_service import fetch_gitee_tag_message

router = APIRouter(prefix="/api/runner")


# ---------------------------------------------------------------------------
# Clone
# ---------------------------------------------------------------------------

@router.post("/clone")
async def clone_repo(request: RepoCloneRequest):
    """Clone a repository and return metadata."""
    try:
        metadata = await clone_repository(request.repo_url, request.sha, request.tag)
        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Explore (SSE)
# ---------------------------------------------------------------------------

@router.post("/explore")
async def explore_repo_stream(clone_path: str):
    """
    Explore repository and generate REPO_OVERVIEW.md with streaming progress.
    Uses Claude Code SDK for agentic exploration (falls back to messages API).
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(message: str):
            await progress_queue.put(message)

        async def explore_task():
            try:
                result = await explore_repository(clone_path, progress_callback)
                await progress_queue.put({"status": "completed", "overview_path": result})
            except Exception as e:
                await progress_queue.put({"status": "failed", "error": str(e)})
            finally:
                await progress_queue.put(None)

        task = asyncio.create_task(explore_task())

        while True:
            message = await progress_queue.get()
            if message is None:
                break
            if isinstance(message, str):
                event_data = json.dumps({"event": "progress", "data": {"message": message}})
            else:
                event_data = json.dumps({"event": "status", "data": message})
            yield f"data: {event_data}\n\n"

        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Detect test commands
# ---------------------------------------------------------------------------

@router.get("/detect-tests")
async def detect_tests(overview_path: str):
    """
    Detect test commands from REPO_OVERVIEW.md without running them.
    Uses static analysis first, falls back to LLM, caches result.
    """
    try:
        test_info = await detect_test_commands(overview_path)
        return test_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Run tests (SSE)
# ---------------------------------------------------------------------------

@router.post("/run-tests")
async def run_tests_stream(
    clone_path: str,
    overview_path: str,
    setup_timeout: int = Query(default=300, description="Seconds allowed per setup command"),
    test_timeout: int = Query(default=600, description="Seconds allowed per test command"),
):
    """
    Run tests based on REPO_OVERVIEW.md with streaming progress.

    - setup_timeout: per-command timeout for dependency installation (default 300s)
    - test_timeout:  per-command timeout for test execution (default 600s)
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(message: str):
            await progress_queue.put(message)

        async def test_task():
            try:
                from pathlib import Path
                result = await run_tests(
                    clone_path,
                    overview_path,
                    progress_callback,
                    setup_timeout=setup_timeout,
                    test_timeout=test_timeout,
                )
                report_path = result.get("report_path", "")
                try:
                    report_content = Path(report_path).read_text() if report_path else ""
                except Exception:
                    report_content = ""
                await progress_queue.put({"status": "completed", "results": result, "report_content": report_content})
            except Exception as e:
                await progress_queue.put({"status": "failed", "error": str(e)})
            finally:
                await progress_queue.put(None)

        task = asyncio.create_task(test_task())

        while True:
            message = await progress_queue.get()
            if message is None:
                break
            if isinstance(message, str):
                event_data = json.dumps({"event": "progress", "data": {"message": message}})
            else:
                event_data = json.dumps({"event": "status", "data": message})
            yield f"data: {event_data}\n\n"

        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Run-all pipeline (SSE) with idempotency flags
# ---------------------------------------------------------------------------

@router.post("/run-all")
async def run_all_stream(request: RunAllRequest):
    """
    Combined clone → explore → run-tests pipeline with SSE streaming progress.

    Pipeline stages:
    1. Clone   — shallow clone (depth=1) into ~/.local/share/oscanner/repos/{repo_name}/
                 Optionally checks out a specific SHA or tag.
    2. Explore — generates REPO_OVERVIEW.md via Claude Sonnet LLM to understand
                 project structure, languages, and suggested test commands.
    3. Tests   — auto-detects test framework, sets up an isolated .venv, runs tests
                 inside a sandboxed subprocess. Produces TEST_REPORT.md with a
                 0–100 score based on pass/fail metrics.

    Idempotency flags:
    - skip_clone:   reuse existing clone (skip re-cloning)
    - skip_explore: reuse existing REPO_OVERVIEW.md (skip LLM exploration)

    Tag annotation scoring (Gitee only):
    - When `tag` is provided, fetches the annotated tag message from Gitee.
    - Extracts feature descriptions from the message and checks which features
      are exercised by the test suite (via LLM). Uncovered features reduce the
      maximum achievable score proportionally.

    SSE events emitted:
    - {"event": "progress", "data": {"message": "<msg>"}}   — pipeline log lines
    - {"event": "status",   "data": {"status": "completed", "results": {...}}}
    - {"event": "status",   "data": {"status": "failed",    "error": "<msg>"}}

    What is NOT covered:
    - Private repositories (no authentication support)
    - Tag annotation fetch for GitHub (Gitee-only)
    - Parallel test execution within a single repo
    - Docker / containerised test environments
    - Custom environment variable injection for test commands
    - Non-Git version control systems
    """
    logger.info("run-all request: repo_url=%s tag=%s sha=%s", request.repo_url, request.tag, request.sha)
    print(f"[run-all] repo_url={request.repo_url} tag={request.tag} sha={request.sha}", flush=True)

    async def event_generator() -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(message: str):
            await progress_queue.put(message)

        async def pipeline_task():
            try:
                from pathlib import Path
                from repos_runner.services.repo_service import get_repos_dir, parse_repo_url

                # -- Clone step --
                if request.skip_clone:
                    _, _, repo_name = parse_repo_url(request.repo_url)
                    clone_path = str(get_repos_dir() / repo_name)
                    await progress_callback(f"Skipping clone, reusing {clone_path}")
                    clone_metadata = {"clone_path": clone_path, "repo_name": repo_name}
                else:
                    await progress_callback("Cloning repository...")
                    clone_metadata = await clone_repository(
                        request.repo_url, request.sha, request.tag
                    )

                clone_path = clone_metadata["clone_path"]
                _safe_tag = request.tag.replace("/", "_").replace("\\", "_") if request.tag else None
                overview_filename = f"REPO_OVERVIEW_{_safe_tag}.md" if _safe_tag else "REPO_OVERVIEW.md"
                overview_path = str(Path(clone_path) / overview_filename)

                # -- Feature requirements / tag message --
                tag_message = str(request.tag_message or "").strip() or None
                if tag_message:
                    await progress_callback("Using forwarded feature requirements.")
                elif request.tag:
                    await progress_callback(
                        f"Fetching tag annotation for '{request.tag}' from Gitee..."
                    )
                    tag_message = await fetch_gitee_tag_message(request.repo_url, request.tag)
                    if tag_message:
                        await progress_callback(f"Tag message: {tag_message}")
                    else:
                        await progress_callback(
                            "No tag annotation message found; running standard scoring."
                        )

                # -- Explore step --
                if request.skip_explore and Path(overview_path).exists():
                    await progress_callback(
                        f"Skipping exploration, reusing existing {overview_filename}"
                    )
                else:
                    await progress_callback("Exploring repository...")
                    overview_path = await explore_repository(
                        clone_path, progress_callback, tag_message, tag=request.tag
                    )

                # -- Test step --
                await progress_callback("Running tests...")
                result = await run_tests(
                    clone_path,
                    overview_path,
                    progress_callback,
                    setup_timeout=request.setup_timeout,
                    test_timeout=request.test_timeout,
                    tag_message=tag_message,
                    tag=request.tag,
                )

                report_path = result.get("report_path", "")
                try:
                    from pathlib import Path as _Path
                    report_content = _Path(report_path).read_text() if report_path else ""
                except Exception:
                    report_content = ""
                await progress_queue.put({
                    "status": "completed",
                    "clone_metadata": clone_metadata,
                    "overview_path": overview_path,
                    "results": result,
                    "report_content": report_content,
                })

            except asyncio.CancelledError:
                progress_queue.put_nowait({"status": "failed", "error": "Pipeline was cancelled"})
                raise
            except Exception as e:
                await progress_queue.put({"status": "failed", "error": str(e)})
            finally:
                progress_queue.put_nowait(None)

        task = asyncio.create_task(pipeline_task())

        while True:
            message = await progress_queue.get()
            if message is None:
                break
            if isinstance(message, str):
                event_data = json.dumps({"event": "progress", "data": {"message": message}})
            else:
                event_data = json.dumps({"event": "status", "data": message})
            yield f"data: {event_data}\n\n"

        try:
            await task
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Batch run (SSE) — up to 3 concurrent pipelines
# ---------------------------------------------------------------------------

@router.post("/batch-run")
async def batch_run_stream(request: BatchRunRequest):
    """
    Run up to N repos through the clone → explore → test pipeline concurrently.
    Concurrency is capped at 3 (max_concurrency field, ignored if > 3).

    SSE events:
    - {"event": "progress", "data": {"repo": "<url>", "message": "<msg>"}}
    - {"event": "repo_done",  "data": {"repo": "<url>", "status": "completed"|"failed", ...}}
    - {"event": "batch_done", "data": {"total": N, "succeeded": N, "failed": N}}
    """
    concurrency = min(request.max_concurrency, 3)

    async def event_generator() -> AsyncGenerator[str, None]:
        from pathlib import Path
        from repos_runner.services.repo_service import get_repos_dir, parse_repo_url

        event_queue: asyncio.Queue = asyncio.Queue()
        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(repo_req: RunAllRequest):
            repo_url = repo_req.repo_url
            async with semaphore:
                async def cb(msg: str):
                    await event_queue.put({"_type": "progress", "repo": repo_url, "message": msg})

                try:
                    if repo_req.skip_clone:
                        _, _, repo_name = parse_repo_url(repo_url)
                        clone_path = str(get_repos_dir() / repo_name)
                        await cb(f"Skipping clone, reusing {clone_path}")
                        clone_metadata = {"clone_path": clone_path, "repo_name": repo_name}
                    else:
                        await cb("Cloning repository...")
                        clone_metadata = await clone_repository(repo_url, repo_req.sha, repo_req.tag)

                    clone_path = clone_metadata["clone_path"]
                    _safe_tag = repo_req.tag.replace("/", "_").replace("\\", "_") if repo_req.tag else None
                    overview_filename = f"REPO_OVERVIEW_{_safe_tag}.md" if _safe_tag else "REPO_OVERVIEW.md"
                    overview_path = str(Path(clone_path) / overview_filename)

                    # -- Feature requirements / tag message --
                    tag_message = str(repo_req.tag_message or "").strip() or None
                    if tag_message:
                        await cb("Using forwarded feature requirements.")
                    elif repo_req.tag:
                        await cb(f"Fetching tag annotation for '{repo_req.tag}' from Gitee...")
                        tag_message = await fetch_gitee_tag_message(repo_url, repo_req.tag)
                        if tag_message:
                            await cb(f"Tag message: {tag_message}")
                        else:
                            await cb(
                                "No tag annotation message found; running standard scoring."
                            )

                    if repo_req.skip_explore and Path(overview_path).exists():
                        await cb(f"Skipping exploration, reusing existing {overview_filename}")
                    else:
                        await cb("Exploring repository...")
                        overview_path = await explore_repository(
                            clone_path, cb, tag_message, tag=repo_req.tag
                        )

                    await cb("Running tests...")
                    result = await run_tests(
                        clone_path,
                        overview_path,
                        cb,
                        setup_timeout=repo_req.setup_timeout,
                        test_timeout=repo_req.test_timeout,
                        tag_message=tag_message,
                        tag=repo_req.tag,
                    )

                    await event_queue.put({
                        "_type": "repo_done",
                        "repo": repo_url,
                        "status": "completed",
                        "clone_metadata": clone_metadata,
                        "overview_path": overview_path,
                        "results": result,
                    })
                except Exception as e:
                    await event_queue.put({
                        "_type": "repo_done",
                        "repo": repo_url,
                        "status": "failed",
                        "error": str(e),
                    })

        tasks = [asyncio.create_task(run_one(r)) for r in request.repos]

        async def wait_all():
            await asyncio.gather(*tasks, return_exceptions=True)
            await event_queue.put(None)  # sentinel

        asyncio.create_task(wait_all())

        succeeded = 0
        failed = 0

        while True:
            item = await event_queue.get()
            if item is None:
                break

            event_type = item.pop("_type")

            if event_type == "progress":
                yield f"data: {json.dumps({'event': 'progress', 'data': item})}\n\n"
            elif event_type == "repo_done":
                if item.get("status") == "completed":
                    succeeded += 1
                else:
                    failed += 1
                yield f"data: {json.dumps({'event': 'repo_done', 'data': item})}\n\n"

        yield f"data: {json.dumps({'event': 'batch_done', 'data': {'total': len(request.repos), 'succeeded': succeeded, 'failed': failed}})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Resource lifecycle
# ---------------------------------------------------------------------------

@router.get("/repos")
async def list_cloned_repos():
    """
    List all cloned repositories with disk usage and status.

    Returns repo_name, clone_path, size_mb, last_accessed,
    has_overview, has_report, has_test_config.
    """
    try:
        return {"repos": list_repos()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/repo")
async def remove_repo(repo_name: str):
    """
    Delete a cloned repository and all associated files (venv, reports, etc.).

    Returns freed_mb.
    """
    try:
        result = delete_repo(repo_name)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_report(repo_url: str, tag: Optional[str] = None):
    """
    Return the content of TEST_REPORT_{tag}.md (or TEST_REPORT.md) for a cloned repo.
    """
    from repos_runner.services.repo_service import get_repos_dir, parse_repo_url
    try:
        _, _, repo_name = parse_repo_url(repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    clone_dir = get_repos_dir() / repo_name
    if not clone_dir.exists():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    if tag:
        safe_tag = tag.replace("/", "_").replace(" ", "_")
        report_path = clone_dir / f"TEST_REPORT_{safe_tag}.md"
    else:
        report_path = clone_dir / "TEST_REPORT.md"

    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {report_path.name}")

    return {"content": report_path.read_text(), "filename": report_path.name}
