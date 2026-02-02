"""
Proxy routes for Repository Runner API
Forwards requests from evaluator server to repos_runner service
"""

import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

router = APIRouter(prefix="/api/runner")

# Get runner service URL from environment or use default
RUNNER_SERVICE_URL = os.getenv("RUNNER_SERVICE_URL", "http://localhost:8001")


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
    async with httpx.AsyncClient(timeout=300.0) as client:
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
            else:
                # Return regular JSON response
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )

        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"Repository Runner service unavailable at {RUNNER_SERVICE_URL}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
