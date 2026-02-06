"""
Proxy routes for Repository Runner API
Forwards requests from evaluator server to repos_runner service
"""

import os
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import httpx

router = APIRouter(prefix="/api/runner")

# Get runner service URL from environment or use default
RUNNER_SERVICE_URL = os.getenv("RUNNER_SERVICE_URL", "http://localhost:8001")


class RunAllRequest(BaseModel):
    """Request model for running all repo analysis steps"""
    repo_url: str


class RunAllResponse(BaseModel):
    """Response model for all-in-one repo analysis"""
    passed: int
    failed: int
    total: int
    score: int
    repo_url: str
    report_path: str
    end_sha: str


async def _consume_sse_stream(response: httpx.Response) -> dict:
    """
    Consume a Server-Sent Events stream and return the final result.

    Args:
        response: httpx Response object with SSE stream

    Returns:
        Dictionary containing the final status/result

    Raises:
        Exception: If stream fails or returns error status
    """
    final_result = None

    async for line in response.aiter_lines():
        if not line or not line.startswith("data: "):
            continue

        try:
            # Parse SSE data
            data_str = line[6:]  # Remove "data: " prefix
            event_data = json.loads(data_str)

            # Check for status events (completed/failed)
            if event_data.get("event") == "status":
                final_result = event_data.get("data", {})

                # If failed, raise exception
                if final_result.get("status") == "failed":
                    error_msg = final_result.get("error", "Unknown error")
                    raise Exception(f"Stream failed: {error_msg}")

        except json.JSONDecodeError:
            # Skip malformed lines
            continue

    if final_result is None:
        raise Exception("Stream ended without final result")

    return final_result


@router.post("/run-all", response_model=RunAllResponse)
async def run_all_steps(request: RunAllRequest):
    """
    Execute all repository analysis steps in one call.

    Workflow:
    1. Clone repository
    2. Explore and generate REPO_OVERVIEW.md
    3. Run tests
    4. Return test results (passed/failed counts)

    Args:
        request: Repository URL to analyze

    Returns:
        Test results with passed/failed counts

    Raises:
        HTTPException: On any step failure with detailed error message
    """
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            # Step 1: Clone repository
            clone_response = await client.post(
                f"{RUNNER_SERVICE_URL}/api/runner/clone",
                json={"repo_url": request.repo_url},
                headers={"Content-Type": "application/json"}
            )

            if clone_response.status_code != 200:
                error_detail = clone_response.text
                raise HTTPException(
                    status_code=clone_response.status_code,
                    detail=f"Clone failed: {error_detail}"
                )

            clone_result = clone_response.json()
            clone_path = clone_result["clone_path"]
            repo_name = clone_result["repo_name"]
            end_sha = clone_result["latest_commit_id"]

        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"Repository Runner service unavailable at {RUNNER_SERVICE_URL}"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Clone step failed: {str(e)}"
            )

        try:
            # Step 2: Explore repository (SSE stream)
            explore_response = await client.post(
                f"{RUNNER_SERVICE_URL}/api/runner/explore",
                params={"clone_path": clone_path}
            )

            if explore_response.status_code != 200:
                error_detail = explore_response.text
                raise HTTPException(
                    status_code=explore_response.status_code,
                    detail=f"Explore failed: {error_detail}"
                )

            # Consume SSE stream and get final result
            explore_result = await _consume_sse_stream(explore_response)

            if explore_result.get("status") != "completed":
                raise HTTPException(
                    status_code=500,
                    detail=f"Explore failed: {explore_result.get('error', 'Unknown error')}"
                )

            overview_path = explore_result["overview_path"]

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Explore step failed: {str(e)}"
            )

        try:
            # Step 3: Run tests (SSE stream)
            test_response = await client.post(
                f"{RUNNER_SERVICE_URL}/api/runner/run-tests",
                params={
                    "clone_path": clone_path,
                    "overview_path": overview_path
                }
            )

            if test_response.status_code != 200:
                error_detail = test_response.text
                raise HTTPException(
                    status_code=test_response.status_code,
                    detail=f"Test execution failed: {error_detail}"
                )

            # Consume SSE stream and get final result
            test_result = await _consume_sse_stream(test_response)

            if test_result.get("status") != "completed":
                raise HTTPException(
                    status_code=500,
                    detail=f"Tests failed: {test_result.get('error', 'Unknown error')}"
                )

            # Extract test results
            results = test_result.get("results", {})

            return RunAllResponse(
                passed=results.get("passed", 0),
                failed=results.get("failed", 0),
                total=results.get("total", 0),
                score=results.get("score", 0),
                repo_url=request.repo_url,
                report_path=results.get("report_path", ""),
                end_sha=end_sha
            )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Test step failed: {str(e)}"
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
