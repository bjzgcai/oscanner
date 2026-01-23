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
from dotenv import load_dotenv

from evaluator.paths import ensure_dirs, get_data_dir, get_home_dir, get_platform_data_dir, get_platform_eval_dir
from evaluator.plugin_registry import discover_plugins, get_default_plugin_id, load_scan_module, PluginLoadError
from evaluator.config import (
    get_github_token, get_gitee_token, get_llm_api_key, mask_secret, DEFAULT_LLM_MODEL,
    get_user_env_path, parse_env_file, write_env_file, apply_env_to_process
)
from evaluator.utils import (
    parse_repo_url, parse_github_url,
    get_author_from_commit, is_commit_by_author,
    load_commits_from_local
)
from evaluator.services import (
    get_plugins_snapshot, resolve_plugin_id, get_evaluation_cache_path,
    extract_github_data, extract_gitee_data, fetch_github_commits, fetch_gitee_commits, get_repo_data_dir,
    get_or_create_evaluator, evaluate_author_incremental, get_empty_evaluation,
    merge_evaluations_logic
)
from evaluator.routes import plugins, config, data, evaluation, batch, benchmark

# Load environment variables
#
# Order:
# 1) CWD .env.local (project-local overrides)
# 2) User config dotfile (~/.local/share/oscanner/.env.local by default)
# 3) Default dotenv behavior (.env if present)
if Path(".env.local").exists():
    load_dotenv(".env.local", override=False)
user_env_path = get_user_env_path()
if user_env_path.exists():
    load_dotenv(str(user_env_path), override=False)
load_dotenv(override=False)

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


# Optional: serve bundled dashboard static files (exported Next.js build) if present.
def _try_mount_bundled_dashboard() -> bool:
    try:
        import oscanner  # the CLI package; may include dashboard_dist/

        dash_dir = Path(oscanner.__file__).resolve().parent / "dashboard_dist"
        if dash_dir.is_dir() and (dash_dir / "index.html").exists():
            # Mount AFTER API routes are registered (Starlette route order matters).
            # We mount at /dashboard to avoid conflicts with the API root.
            app.mount("/dashboard", StaticFiles(directory=str(dash_dir), html=True), name="dashboard")
            return True
    except Exception:
        return False
    return False

# Data directory (default: user data dir)
DATA_DIR = get_data_dir()


# NOTE: Cache endpoints disabled (cache functionality removed)
# @app.get("/api/evaluation-cache/status/{owner}/{repo}")
# async def evaluation_cache_status(owner: str, repo: str):
#     """
#     Return whether evaluation cache file exists for this repo, and how many authors are cached.
#     Never returns any evaluation contents.
#     """
#     return {
#         "exists": False,
#         "authors_cached": 0,
#         "path": "",
#     }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Engineer Skill Evaluator"}


@app.get("/")
async def root():
    """
    Root endpoint - client-side redirect to dashboard.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="0; url=/dashboard">
    <title>Redirecting...</title>
    <script>
        window.location.href = '/dashboard';
    </script>
</head>
<body>
    <p>Redirecting to <a href="/dashboard">dashboard</a>...</p>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Browsers request this automatically; avoid noisy 404 logs.
    return Response(status_code=204)


# Mount dashboard static files as late as possible (after route declarations above).
_DASHBOARD_MOUNTED = _try_mount_bundled_dashboard()


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
