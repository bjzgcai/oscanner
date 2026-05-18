"""
Proxy routes for Repository Runner API
Forwards requests from evaluator server to repos_runner service
"""

import os
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pydantic import BaseModel, Field
import httpx

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


def _proxied_headers(headers):
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS | {"content-length"}
    }


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

    # Forward the request
    async with httpx.AsyncClient(timeout=660.0) as client:
        try:
            # Make the proxied request
            response = await client.request(
                method=request.method,
                url=target_url,
                headers={
                    key: value
                    for key, value in request.headers.items()
                    if key.lower() not in ["host", "connection"]
                },
                content=body,
            )

            # Check if this is a streaming response (SSE)
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                # Stream the response
                async def stream_generator():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    stream_generator(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no"
                    }
                )
            elif "application/json" not in content_type:
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
