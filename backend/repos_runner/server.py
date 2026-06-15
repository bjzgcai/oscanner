#!/usr/bin/env python3
"""
FastAPI Backend for Repository Runner
Handles repository cloning, exploration, and test running
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from dotenv import load_dotenv

# Add backend directory to Python path to allow 'repos_runner' imports
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# Load environment variables
# Check an explicit runner env file first, then server/CWD defaults.
_server_dir = Path(__file__).resolve().parent
_explicit_env = os.getenv("REPOS_RUNNER_ENV_FILE", "").strip()
_env_candidates = []
if _explicit_env:
    _env_candidates.append(Path(_explicit_env).expanduser())
_env_candidates.extend(
    (
        _server_dir / ".env",
        _server_dir / ".env.local",
        Path(".env"),
        Path(".env.local"),
    )
)
for _env_path in _env_candidates:
    if _env_path.exists():
        load_dotenv(_env_path, override=True)
        break
load_dotenv(override=False)

from oscanner_logging import configure_service_logging
from repos_runner.routes import runner

LOG_PATH = configure_service_logging("repos-runner")

OPENAPI_TAGS = [
    {
        "name": "runner",
        "description": (
            "Clone repositories, explore project structure, detect test commands, "
            "run tests, and serve runner artifacts."
        ),
    },
]

app = FastAPI(
    title="Oscanner Repository Runner API",
    summary="Repository clone, exploration, and test execution service",
    description=(
        "Clone public GitHub and Gitee repositories, generate repository overviews, "
        "detect test commands, execute controlled test workflows, and expose "
        "reports and runtime evidence artifacts."
    ),
    version="0.1.6",
    license_info={"name": "Apache-2.0"},
    servers=[{"url": "http://localhost:8001", "description": "Local repository runner service"}],
    openapi_tags=OPENAPI_TAGS,
)

# Middleware to strip trailing slashes from API requests
class TrailingSlashMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path != "/" and request.url.path.endswith("/"):
            new_path = request.url.path.rstrip("/")
            request.scope["path"] = new_path
        return await call_next(request)

app.add_middleware(TrailingSlashMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(runner.router, tags=["runner"])


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Repository Runner"}


@app.get("/version")
async def version():
    """Return deployed git commit"""
    import subprocess
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        commit = "unknown"
    return {"commit": commit, "service": "Repository Runner"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("RUNNER_PORT", 8001))
    print(f"\n{'='*80}")
    print(f"🚀 Repository Runner API Server")
    print(f"{'='*80}")
    print(f"📍 Server: http://localhost:{port}")
    print(f"🏥 Health: http://localhost:{port}/health")
    print(f"📚 API Docs: http://localhost:{port}/docs")
    print(f"{'='*80}\n")

    # Get the repos_runner directory path
    repos_runner_dir = Path(__file__).parent

    uvicorn.run(
        "repos_runner.server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=[str(repos_runner_dir)]
    )
