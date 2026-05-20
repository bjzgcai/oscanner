"""
Proxy routes for Repository Runner API
Forwards requests from evaluator server to repos_runner service
"""

import os
import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pydantic import BaseModel, Field
import httpx

from evaluator.paths import get_data_dir
from evaluator.services.trajectory_poll_store import SQLiteTrajectoryPollStore

router = APIRouter(prefix="/api/runner")

# Get runner service URL from environment or use default
RUNNER_SERVICE_URL = os.getenv("RUNNER_SERVICE_URL", "http://localhost:8001")

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

_STREAMING_RUNNER_PATHS = {"explore", "run-tests"}
_RUNNER_POLL_INTERRUPTED_MESSAGE = "Runner job interrupted by server restart. Please start a new run."
_runner_poll_store = SQLiteTrajectoryPollStore(db_path=get_data_dir() / "runner_poll_jobs.sqlite3")
_runner_poll_store.mark_interrupted_jobs(time.time(), _RUNNER_POLL_INTERRUPTED_MESSAGE)


def _proxied_headers(headers):
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS | {"content-length"}
    }


def _is_streaming_runner_path(path: str) -> bool:
    return path.strip("/") in _STREAMING_RUNNER_PATHS


def _streaming_error_event(message: str) -> str:
    error = json.dumps({
        "event": "status",
        "data": {"status": "failed", "error": message},
    })
    return f"data: {error}\n\n"


def _parse_sse_frame(frame: str) -> tuple[str, Any] | None:
    event = "message"
    data_lines: list[str] = []

    for line in frame.splitlines():
        if not line or line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[6:].strip() or "message"
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    if not data_lines:
        return None

    raw_data = "\n".join(data_lines)
    try:
        data: Any = json.loads(raw_data)
    except json.JSONDecodeError:
        data = raw_data
    return event, data


def _parse_sse_buffer(buffer: str) -> tuple[list[tuple[str, Any]], str]:
    normalized = buffer.replace("\r\n", "\n")
    frames = normalized.split("\n\n")
    remaining = frames.pop() or ""
    events = [
        parsed
        for frame in frames
        if frame.strip()
        for parsed in [_parse_sse_frame(frame)]
        if parsed is not None
    ]
    return events, remaining


class RunAllRequest(BaseModel):
    """Request model for the combined clone → explore → test pipeline"""
    repo_url: str
    sha: str | None = None
    tag: str | None = None
    tag_message: str | None = None
    skip_clone: bool = False
    skip_explore: bool = False
    clone_timeout: int = Field(default=300, gt=0)
    setup_timeout: int = Field(default=300, gt=0)
    test_timeout: int = Field(default=600, gt=0)
    pipeline_timeout: float = Field(default=1800, gt=0)


async def _run_all_poll_job(job_id: str, request: RunAllRequest) -> None:
    buffer = ""
    try:
        response = await run_all_steps(request)
        async for chunk in response.body_iterator:
            text = (
                chunk.decode("utf-8", errors="replace")
                if isinstance(chunk, bytes)
                else str(chunk)
            )
            buffer += text
            events, buffer = _parse_sse_buffer(buffer)
            for event, data in events:
                _runner_poll_store.append_event(job_id, event, data)

        if buffer.strip():
            events, _ = _parse_sse_buffer(f"{buffer}\n\n")
            for event, data in events:
                _runner_poll_store.append_event(job_id, event, data)
    except Exception as exc:
        message = f"Runner poll job failed: {exc}"
        _runner_poll_store.append_event(job_id, "error", {"message": message})
        _runner_poll_store.finish_job(job_id, error=message)
        return

    _runner_poll_store.finish_job(job_id)


@router.post("/run-all")
async def run_all_steps(request: RunAllRequest):
    """
    Proxy the full clone → explore → run-tests pipeline to the runner service.

    Forwards the SSE stream from the runner's /api/runner/run-all directly to
    the caller so progress events and the final status event are all visible.
    """
    print(f"[run-all] repo_url={request.repo_url} tag={request.tag} sha={request.sha}", flush=True)

    payload = {
        "repo_url": request.repo_url,
        "sha": request.sha,
        "tag": request.tag,
        "tag_message": request.tag_message,
        "skip_clone": request.skip_clone,
        "skip_explore": request.skip_explore,
        "clone_timeout": request.clone_timeout,
        "setup_timeout": request.setup_timeout,
        "test_timeout": request.test_timeout,
        "pipeline_timeout": request.pipeline_timeout,
    }

    async def stream_from_runner():
        try:
            async with httpx.AsyncClient(timeout=request.pipeline_timeout + 60.0) as client:
                async with client.stream(
                    "POST",
                    f"{RUNNER_SERVICE_URL}/api/runner/run-all",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status_code != 200:
                        await response.aread()
                        error = json.dumps({
                            "event": "status",
                            "data": {"status": "failed", "error": response.text},
                        })
                        yield f"data: {error}\n\n"
                        return
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except httpx.ConnectError:
            error = json.dumps({
                "event": "status",
                "data": {"status": "failed", "error": f"Runner unavailable at {RUNNER_SERVICE_URL}"},
            })
            yield f"data: {error}\n\n"
        except Exception as e:
            error = json.dumps({
                "event": "status",
                "data": {"status": "failed", "error": f"Runner connection lost: {e}"},
            })
            yield f"data: {error}\n\n"

    return StreamingResponse(
        stream_from_runner(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/run-all_poll")
async def start_run_all_poll(request: RunAllRequest) -> JSONResponse:
    """Start a durable clone → explore → test runner job and return its poll URL."""
    _runner_poll_store.cleanup()
    job_id = uuid.uuid4().hex
    _runner_poll_store.create_job(job_id)
    asyncio.create_task(_run_all_poll_job(job_id, request))

    return JSONResponse(
        {
            "job_id": job_id,
            "poll_url": f"/api/runner/run-all_poll/{job_id}",
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/run-all_poll/{job_id}")
async def get_run_all_poll(job_id: str, cursor: int = Query(0, ge=0)) -> JSONResponse:
    """Return stored events for a durable runner job."""
    _runner_poll_store.cleanup()
    status = _runner_poll_store.get_job(job_id, cursor=cursor)
    if status is None:
        raise HTTPException(status_code=404, detail="Runner job not found")

    return JSONResponse(status, headers={"Cache-Control": "no-store"})


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_runner_request(path: str, request: Request):
    """
    Proxy all /api/runner/* requests to the repos_runner service

    Args:
        path: The path after /api/runner/
        request: The incoming request

    Returns:
        Proxied response from repos_runner service
    """
    # Build target URL
    target_url = f"{RUNNER_SERVICE_URL}/api/runner/{path}"

    # Preserve query parameters
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    # Get request body if present
    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ["host", "connection"]
    }

    if _is_streaming_runner_path(path):
        async def stream_from_runner():
            try:
                async with httpx.AsyncClient(timeout=660.0) as client:
                    async with client.stream(
                        method=request.method,
                        url=target_url,
                        headers=headers,
                        content=body,
                    ) as response:
                        if response.status_code != 200:
                            await response.aread()
                            yield _streaming_error_event(response.text)
                            return
                        async for chunk in response.aiter_bytes():
                            yield chunk
            except httpx.ConnectError:
                yield _streaming_error_event(f"Repository Runner service unavailable at {RUNNER_SERVICE_URL}")
            except Exception as e:
                yield _streaming_error_event(str(e))

        return StreamingResponse(
            stream_from_runner(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Forward the request
    async with httpx.AsyncClient(timeout=660.0) as client:
        try:
            # Make the proxied request
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )

            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    media_type=content_type or None,
                    headers=_proxied_headers(response.headers),
                )
            else:
                # Return regular JSON response
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                    headers=_proxied_headers(response.headers),
                )

        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"Repository Runner service unavailable at {RUNNER_SERVICE_URL}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
