"""
API routes for Repository Runner
"""

import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from repos_runner.schemas import (
    RepoCloneRequest,
    RepoMetadata,
    TestSummary
)
from repos_runner.services import (
    clone_repository,
    explore_repository,
    run_tests
)

router = APIRouter(prefix="/api/runner")


@router.post("/clone")
async def clone_repo(request: RepoCloneRequest):
    """
    Clone a repository and return metadata.

    Args:
        request: Repository clone request with URL

    Returns:
        Repository metadata including name, branch, and commit info
    """
    try:
        metadata = await clone_repository(request.repo_url)
        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explore")
async def explore_repo_stream(clone_path: str):
    """
    Explore repository and generate REPO_OVERVIEW.md with streaming progress.

    Args:
        clone_path: Path to the cloned repository

    Returns:
        Server-Sent Events stream with progress updates
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for progress updates"""
        progress_queue = asyncio.Queue()

        async def progress_callback(message: str):
            """Callback to send progress updates"""
            await progress_queue.put(message)

        # Start the exploration task
        async def explore_task():
            try:
                result = await explore_repository(clone_path, progress_callback)
                await progress_queue.put({"status": "completed", "overview_path": result})
            except Exception as e:
                await progress_queue.put({"status": "failed", "error": str(e)})
            finally:
                await progress_queue.put(None)  # Signal completion

        # Run exploration in background
        task = asyncio.create_task(explore_task())

        # Stream progress updates
        while True:
            message = await progress_queue.get()

            if message is None:
                break

            if isinstance(message, str):
                # Progress message
                event_data = json.dumps({
                    "event": "progress",
                    "data": {"message": message}
                })
            else:
                # Status update (completed/failed)
                event_data = json.dumps({
                    "event": "status",
                    "data": message
                })

            yield f"data: {event_data}\n\n"

        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/run-tests")
async def run_tests_stream(clone_path: str, overview_path: str):
    """
    Run tests based on REPO_OVERVIEW.md with streaming progress.

    Args:
        clone_path: Path to the cloned repository
        overview_path: Path to REPO_OVERVIEW.md

    Returns:
        Server-Sent Events stream with test progress and results
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for test progress"""
        progress_queue = asyncio.Queue()

        async def progress_callback(message: str):
            """Callback to send progress updates"""
            await progress_queue.put(message)

        # Start the test task
        async def test_task():
            try:
                result = await run_tests(clone_path, overview_path, progress_callback)
                await progress_queue.put({"status": "completed", "results": result})
            except Exception as e:
                await progress_queue.put({"status": "failed", "error": str(e)})
            finally:
                await progress_queue.put(None)  # Signal completion

        # Run tests in background
        task = asyncio.create_task(test_task())

        # Stream progress updates
        while True:
            message = await progress_queue.get()

            if message is None:
                break

            if isinstance(message, str):
                # Progress message
                event_data = json.dumps({
                    "event": "progress",
                    "data": {"message": message}
                })
            else:
                # Status update (completed/failed)
                event_data = json.dumps({
                    "event": "status",
                    "data": message
                })

            yield f"data: {event_data}\n\n"

        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
