#!/usr/bin/env python3
"""
FastAPI Backend for Engineer Skill Evaluator
"""

import os
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException, Query, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# Add backend directory to Python path to allow 'evaluator' imports
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from evaluator.paths import ensure_dirs, get_data_dir, get_home_dir, get_platform_data_dir
from evaluator.plugin_registry import discover_plugins, get_default_plugin_id, load_scan_module, PluginLoadError
from evaluator.config import (
    get_github_token, get_gitee_token, get_llm_api_key, mask_secret, DEFAULT_LLM_MODEL,
    load_runtime_env
)
from evaluator.utils import (
    parse_repo_url, parse_github_url,
    get_author_from_commit, is_commit_by_author,
    load_commits_from_local
)
from evaluator.services import (
    get_plugins_snapshot, resolve_plugin_id,
    extract_github_data, extract_gitee_data, fetch_github_commits, fetch_gitee_commits, get_repo_data_dir,
    get_or_create_evaluator, evaluate_author_incremental, get_empty_evaluation,
    merge_evaluations_logic
)
from evaluator.routes import plugins, config, data, evaluation, batch, benchmark, trajectory, runner_proxy, checkers

# Load environment variables
#
# Order:
# 1) Evaluator server directory `.env`
# 2) Evaluator server directory `.env.local` (legacy)
# 3) CWD `.env` / `.env.local` (when different)
# 4) User config dotfile (~/.local/share/oscanner/.env.local by default)
# 5) Default dotenv behavior (`.env` if present)
load_runtime_env(server_file=Path(__file__), cwd=Path.cwd())

app = FastAPI(title="Engineer Skill Evaluator API")

# Middleware to strip trailing slashes from API requests
# (Next.js uses trailingSlash: true for static export, but FastAPI routes don't have trailing slashes)
class TrailingSlashMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path != "/" and request.url.path.endswith("/"):
            # Strip trailing slash and redirect internally
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

ensure_dirs()

# Include routers
app.include_router(plugins.router, tags=["plugins"])
app.include_router(config.router, tags=["config"])
app.include_router(data.router, tags=["data"])
app.include_router(evaluation.router, tags=["evaluation"])
app.include_router(batch.router, tags=["batch"])
app.include_router(benchmark.router, tags=["benchmark"])
app.include_router(trajectory.router, tags=["trajectory"])
app.include_router(runner_proxy.router, tags=["runner"])
app.include_router(checkers.router, tags=["checkers"])


# Optional: serve bundled dashboard static files (exported Next.js build) if present.
def _try_mount_bundled_dashboard() -> Optional[Path]:
    try:
        import cli  # the CLI package; may include dashboard_dist/

        dash_dir = Path(cli.__file__).resolve().parent / "dashboard_dist"
        if dash_dir.is_dir() and (dash_dir / "index.html").exists():
            # Mount AFTER API routes are registered (Starlette route order matters).
            app.mount("/", StaticFiles(directory=str(dash_dir), html=True), name="dashboard")
            return dash_dir
    except Exception:
        return None
    return None

# Data directory (default: user data dir)
DATA_DIR = get_data_dir()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Engineer Skill Evaluator"}


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
    return {"commit": commit, "service": "Engineer Skill Evaluator"}


@app.get("/")
async def root():
    """
    Root endpoint - serves bundled dashboard if available.
    """
    if _DASHBOARD_DIR and (_DASHBOARD_DIR / "index.html").exists():
        return HTMLResponse(content=(_DASHBOARD_DIR / "index.html").read_text(encoding="utf-8"), status_code=200)
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oscanner API</title>
</head>
<body>
    <h1>Oscanner API</h1>
    <p>The dashboard is not bundled in this install.</p>
    <ul>
        <li><a href="/docs">API Docs</a></li>
        <li><a href="/health">Health Check</a></li>
    </ul>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Browsers request this automatically; avoid noisy 404 logs.
    return Response(status_code=204)


# Mount dashboard static files as late as possible (after route declarations above).
_DASHBOARD_DIR = _try_mount_bundled_dashboard()


# NOTE: Score normalization endpoints disabled (ScoreNormalizer module removed)
# @app.get("/api/local/normalized/{owner}/{repo}")
# @app.get("/api/local/compare/{owner}/{repo}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    print(f"\n{'='*80}")
    print(f"🚀 Engineer Skill Evaluator API Server")
    print(f"{'='*80}")
    print(f"📍 Server: http://localhost:{port}")
    print(f"📊 Dashboard: Open dashboard.html in your browser")
    print(f"🏥 Health: http://localhost:{port}/health")
    print(f"📚 API Docs: http://localhost:{port}/docs")
    print(f"{'='*80}\n")

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
