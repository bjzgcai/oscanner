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

from repos_runner.routes import runner

# Load environment variables
# Check server file directory first (repos_runner/.env.local), then CWD
_server_dir = Path(__file__).resolve().parent
_server_env = _server_dir / ".env.local"
if _server_env.exists():
    load_dotenv(_server_env, override=True)
elif Path(".env.local").exists():
    load_dotenv(".env.local", override=True)
load_dotenv(override=False)

app = FastAPI(title="Repository Runner API")

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
