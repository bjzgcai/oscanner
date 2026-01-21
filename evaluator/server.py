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
from dotenv import load_dotenv

from evaluator.paths import ensure_dirs, get_data_dir, get_home_dir, get_platform_data_dir, get_platform_eval_dir
from evaluator.plugin_registry import discover_plugins, get_default_plugin_id, load_scan_module, PluginLoadError

def get_user_env_path() -> Path:
    # Store config under oscanner home dir (user-local dotfile).
    return get_home_dir() / ".env.local"

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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_dirs()


def _plugins_snapshot():
    plugins = discover_plugins()
    default_id = get_default_plugin_id(plugins)
    return plugins, default_id


@app.get("/api/plugins")
async def list_plugins():
    """
    List available scan plugins discovered from the local `plugins/` directory.
    """
    plugins, default_id = _plugins_snapshot()
    return {
        "success": True,
        "default": default_id,
        "plugins": [
            {
                "id": meta.plugin_id,
                "name": meta.name,
                "version": meta.version,
                "description": meta.description,
                "default": bool(meta.default),
                "scan_entry": meta.scan_entry,
                "view_single_entry": meta.view_single_entry,
                "has_view_single": bool((plugin_dir / meta.view_single_entry).exists()),
                "view_compare_entry": meta.view_compare_entry,
                "has_view_compare": bool((plugin_dir / meta.view_compare_entry).exists()),
                # Legacy (compat) single-view entry
                "view_entry": meta.view_entry,
                "has_view": bool((plugin_dir / meta.view_entry).exists()),
            }
            for meta, plugin_dir in plugins
        ],
    }


@app.get("/api/plugins/default")
async def get_default_plugin():
    plugins, default_id = _plugins_snapshot()
    _ = plugins
    return {"success": True, "default": default_id}


def _resolve_plugin_id(requested: Optional[str]) -> str:
    plugins, default_id = _plugins_snapshot()
    requested_id = (requested or "").strip()
    if requested_id:
        # Validate existence early for clearer errors.
        if requested_id in {m.plugin_id for m, _ in plugins}:
            return requested_id
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unknown plugin '{requested_id}'",
                "available": [m.plugin_id for m, _ in plugins],
                "default": default_id,
            },
        )
    if default_id:
        return default_id
    raise HTTPException(status_code=500, detail="No plugins discovered (plugins/ directory missing?)")


def _evaluation_cache_path(eval_dir: Path, author: str, plugin_id: str, default_id: Optional[str]) -> Path:
    safe_author = (author or "").strip().lower()
    if not safe_author:
        safe_author = "unknown"
    # Keep legacy path for default plugin to preserve existing caches.
    if default_id and plugin_id == default_id:
        return eval_dir / f"{safe_author}.json"
    if plugin_id in ("", "builtin"):
        return eval_dir / f"{safe_author}.json"
    return eval_dir / f"{safe_author}__{plugin_id}.json"

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

def get_github_token() -> Optional[str]:
    # Read from process env at call time so dashboard updates take effect without restart.
    return os.getenv("GITHUB_TOKEN")


def get_gitee_token() -> Optional[str]:
    # Read from process env at call time so dashboard updates take effect without restart.
    return os.getenv("GITEE_TOKEN")

# Default model for evaluation (can be overridden per-request by query param `model=...`)
DEFAULT_LLM_MODEL = os.getenv("OSCANNER_LLM_MODEL", "Pro/zai-org/GLM-4.7")

def get_llm_api_key() -> Optional[str]:
    """
    Resolve an API key for LLM calls without leaking secrets.

    Priority matches the plugin evaluator contract:
    - OSCANNER_LLM_API_KEY (OpenAI-compatible bearer token)
    - OPENAI_API_KEY
    - OPEN_ROUTER_KEY
    """
    return (
        os.getenv("OSCANNER_LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("OPEN_ROUTER_KEY")
    )

def _mask_secret(value: Optional[str]) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:4]}...{s[-4:]}"

def _parse_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    except FileNotFoundError:
        return {}
    except Exception:
        return env
    return env

def _write_env_file(path: Path, env: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "# Generated by oscanner dashboard LLM settings",
        "# - Do NOT commit real keys to git.",
        "",
    ]
    order = [
        "GITEE_TOKEN",
        "GITHUB_TOKEN",
        "OPEN_ROUTER_KEY",
        "OSCANNER_LLM_API_KEY",
        "OSCANNER_LLM_BASE_URL",
        "OSCANNER_LLM_CHAT_COMPLETIONS_URL",
        "OSCANNER_LLM_MODEL",
        "OSCANNER_LLM_FALLBACK_MODELS",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]
    lines: List[str] = []
    lines.extend(header)
    for k in order:
        if k in env and env[k] != "":
            lines.append(f"{k}={env[k]}")
    # keep any other keys stable (avoid losing tokens like GITHUB_TOKEN if user adds here)
    for k in sorted(env.keys()):
        if k in order:
            continue
        if env[k] == "":
            continue
        lines.append(f"{k}={env[k]}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")

def _apply_env_to_process(env: Dict[str, str]) -> None:
    # Update current process env so changes take effect without restart.
    for k, v in env.items():
        if v is None:
            continue
        if v == "":
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

@app.get("/api/config/llm")
async def get_llm_config():
    """
    Read current LLM config from user dotfile + process env (masked).
    """
    path = get_user_env_path()
    file_env = _parse_env_file(path) if path.exists() else {}
    api_key = get_llm_api_key()
    cfg = {
        "configured": bool(api_key),
        "path": str(path),
        "mode": "openrouter" if (file_env.get("OPEN_ROUTER_KEY") or os.getenv("OPEN_ROUTER_KEY")) else "openai",
        "openrouter_key_masked": _mask_secret(file_env.get("OPEN_ROUTER_KEY") or os.getenv("OPEN_ROUTER_KEY")),
        "oscanner_llm_api_key_masked": _mask_secret(file_env.get("OSCANNER_LLM_API_KEY") or os.getenv("OSCANNER_LLM_API_KEY")),
        "gitee_token_masked": _mask_secret(file_env.get("GITEE_TOKEN") or os.getenv("GITEE_TOKEN")),
        "github_token_masked": _mask_secret(file_env.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")),
        "oscanner_llm_base_url": file_env.get("OSCANNER_LLM_BASE_URL") or os.getenv("OSCANNER_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "",
        "oscanner_llm_chat_completions_url": file_env.get("OSCANNER_LLM_CHAT_COMPLETIONS_URL") or os.getenv("OSCANNER_LLM_CHAT_COMPLETIONS_URL") or "",
        "oscanner_llm_model": file_env.get("OSCANNER_LLM_MODEL") or os.getenv("OSCANNER_LLM_MODEL") or DEFAULT_LLM_MODEL,
        "oscanner_llm_fallback_models": file_env.get("OSCANNER_LLM_FALLBACK_MODELS") or os.getenv("OSCANNER_LLM_FALLBACK_MODELS") or "",
    }
    return cfg

@app.post("/api/config/llm")
async def set_llm_config(payload: Dict[str, Any]):
    """
    Configure LLM settings and persist to user dotfile, then load into current process env.

    payload:
      mode: "openrouter" | "openai"
      openrouter_key: str (for openrouter)
      base_url: str, api_key: str, model: str (for openai-compatible)
      chat_completions_url?: str
      fallback_models?: str (comma-separated)
    """
    mode = str(payload.get("mode") or "").strip().lower()
    path = get_user_env_path()
    env = _parse_env_file(path) if path.exists() else {}

    if mode == "openrouter":
        # NOTE: The dashboard intentionally does NOT hydrate secrets back into inputs.
        # So when users click "save" to update *other* fields (e.g. tokens),
        # openrouter_key may be omitted/empty. In that case, keep the existing key if present.
        key = str(payload.get("openrouter_key") or "").strip()
        existing_key = (env.get("OPEN_ROUTER_KEY") or os.getenv("OPEN_ROUTER_KEY") or "").strip()
        if key:
            env["OPEN_ROUTER_KEY"] = key
        elif not existing_key:
            raise HTTPException(status_code=400, detail="openrouter_key is required")
        # allow optional model override
        model = str(payload.get("model") or "").strip()
        if model:
            env["OSCANNER_LLM_MODEL"] = model
        # clear openai-compatible fields only when a mode is explicitly selected
        # (keeps config consistent and avoids ambiguity)
        env.pop("OSCANNER_LLM_API_KEY", None)
        env.pop("OSCANNER_LLM_BASE_URL", None)
        env.pop("OSCANNER_LLM_CHAT_COMPLETIONS_URL", None)
    elif mode == "openai":
        # Same idea: allow saving other settings without re-entering secrets,
        # as long as an existing OpenAI-compatible config already exists.
        api_key = str(payload.get("api_key") or "").strip()
        base_url = str(payload.get("base_url") or "").strip()
        model = str(payload.get("model") or "").strip()
        chat_url = str(payload.get("chat_completions_url") or "").strip()
        fb = str(payload.get("fallback_models") or "").strip()

        existing_api_key = (env.get("OSCANNER_LLM_API_KEY") or os.getenv("OSCANNER_LLM_API_KEY") or "").strip()
        existing_base_url = (env.get("OSCANNER_LLM_BASE_URL") or os.getenv("OSCANNER_LLM_BASE_URL") or "").strip()
        existing_model = (env.get("OSCANNER_LLM_MODEL") or os.getenv("OSCANNER_LLM_MODEL") or "").strip()

        if api_key:
            env["OSCANNER_LLM_API_KEY"] = api_key
        elif not existing_api_key:
            raise HTTPException(status_code=400, detail="api_key is required")

        if base_url:
            env["OSCANNER_LLM_BASE_URL"] = base_url
        elif not existing_base_url:
            raise HTTPException(status_code=400, detail="base_url is required")

        if model:
            env["OSCANNER_LLM_MODEL"] = model
        elif not existing_model:
            raise HTTPException(status_code=400, detail="model is required")

        if chat_url:
            env["OSCANNER_LLM_CHAT_COMPLETIONS_URL"] = chat_url
        else:
            env.pop("OSCANNER_LLM_CHAT_COMPLETIONS_URL", None)
        if fb:
            env["OSCANNER_LLM_FALLBACK_MODELS"] = fb
        else:
            env.pop("OSCANNER_LLM_FALLBACK_MODELS", None)
        # clear openrouter key to avoid ambiguity
        env.pop("OPEN_ROUTER_KEY", None)
    elif mode in ("", "none"):
        # Allow partial updates for non-LLM fields (e.g., platform tokens) without forcing users
        # to re-enter LLM secrets (inputs are intentionally not hydrated in the UI).
        pass
    else:
        raise HTTPException(status_code=400, detail="mode must be openrouter or openai (or omitted for partial updates)")

    # Platform tokens (optional, can be updated independently)
    if "gitee_token" in payload:
        gitee_token = str(payload.get("gitee_token") or "").strip()
        if gitee_token:
            env["GITEE_TOKEN"] = gitee_token
        else:
            env.pop("GITEE_TOKEN", None)
    if "github_token" in payload:
        github_token = str(payload.get("github_token") or "").strip()
        if github_token:
            env["GITHUB_TOKEN"] = github_token
        else:
            env.pop("GITHUB_TOKEN", None)

    # If nothing changed, still return success to keep the UI simple/idempotent.
    # (Users may click "save" without modifying fields.)

    _write_env_file(path, env)
    # Load into current process env
    load_dotenv(str(path), override=True)
    _apply_env_to_process(env)

    return {"success": True, "path": str(path), "configured": bool(get_llm_api_key())}

@app.get("/api/llm/status")
async def llm_status():
    """
    Return whether LLM credentials appear configured.
    This endpoint never returns secret values.
    """
    api_key = get_llm_api_key()
    return {
        "configured": bool(api_key),
        "has_openrouter_key": bool(os.getenv("OPEN_ROUTER_KEY")),
        "has_openai_api_key": bool(os.getenv("OPENAI_API_KEY")),
        "has_oscanner_llm_api_key": bool(os.getenv("OSCANNER_LLM_API_KEY")),
        "default_model": DEFAULT_LLM_MODEL,
    }


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


def extract_github_data(owner: str, repo: str) -> bool:
    """Extract GitHub repository data using extraction tool"""
    try:
        repo_url = f"https://github.com/{owner}/{repo}"
        output_dir = get_platform_data_dir("github", owner, repo)

        print(f"\n{'='*60}")
        print(f"Extracting GitHub data for {owner}/{repo}...")
        print(f"{'='*60}")

        # Construct command (module execution; does not rely on CWD)
        cmd = [
            sys.executable,
            "-m",
            "evaluator.tools.extract_repo_data_moderate",
            "--repo-url",
            repo_url,
            "--out",
            str(output_dir),
            "--max-commits",
            "500",  # Fetch enough to cover all contributors
        ]

        gh_token = get_github_token()
        if gh_token:
            cmd.extend(["--token", gh_token])

        # Run extraction tool
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 minute timeout

        if result.returncode != 0:
            print(f"✗ Extraction failed: {result.stderr}")
            return False

        print(f"✓ Extraction successful")
        print(result.stdout)
        return True

    except subprocess.TimeoutExpired:
        print(f"✗ Extraction timeout after 5 minutes")
        return False
    except Exception as e:
        print(f"✗ Extraction error: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_commits_from_local(data_dir: Path, limit: int = None) -> List[Dict[str, Any]]:
    """
    Load commits from local extracted data

    Args:
        data_dir: Path to data directory (e.g., data/owner/repo)
        limit: Maximum commits to load (None = all commits)

    Returns:
        List of commit data
    """
    commits_index_path = data_dir / "commits_index.json"

    if not commits_index_path.exists():
        print(f"[Warning] Commits index not found: {commits_index_path}")
        return []

    # Load commits index
    with open(commits_index_path, 'r', encoding='utf-8') as f:
        commits_index = json.load(f)

    print(f"[Info] Found {len(commits_index)} commits in index")

    # Load detailed commit data
    commits = []
    commits_dir = data_dir / "commits"

    # Apply limit if specified
    commits_to_load = commits_index if limit is None else commits_index[:limit]

    for commit_info in commits_to_load:
        commit_sha = commit_info.get("hash") or commit_info.get("sha")

        if not commit_sha:
            continue

        # Try to load commit JSON
        commit_json_path = commits_dir / f"{commit_sha}.json"

        if commit_json_path.exists():
            try:
                with open(commit_json_path, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    commits.append(commit_data)
            except Exception as e:
                print(f"[Warning] Failed to load {commit_sha}: {e}")

    print(f"[Info] Loaded {len(commits)} commit details")
    return commits


def fetch_github_commits(owner: str, repo: str, limit: int = 100) -> list:
    """Fetch commits from GitHub API"""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    headers = {}
    gh_token = get_github_token()
    if gh_token:
        headers["Authorization"] = f"token {gh_token}"

    params = {"per_page": min(limit, 100)}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch GitHub commits: {str(e)}")


def fetch_gitee_commits(owner: str, repo: str, limit: int = 100, is_enterprise: bool = False) -> list:
    """Fetch commits from Gitee API"""
    if is_enterprise:
        url = f"https://api.gitee.com/enterprises/{owner}/repos/{repo}/commits"
    else:
        url = f"https://api.gitee.com/repos/{owner}/{repo}/commits"

    # Gitee uses `access_token` query param (Authorization header is not reliable for v5 APIs).
    headers = {}
    params = {"per_page": min(limit, 100)}
    gitee_token = get_gitee_token()
    if gitee_token:
        params["access_token"] = gitee_token

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Gitee commits: {str(e)}")


@app.get("/api/gitee/commits/{owner}/{repo}")
async def get_gitee_commits(
    owner: str,
    repo: str,
    limit: int = Query(500, ge=1, le=1000),
    use_cache: bool = Query(True),
    is_enterprise: bool = Query(False)
):
    """Fetch commits for a Gitee repository"""
    # Fetch from Gitee API
    commits = fetch_gitee_commits(owner, repo, limit, is_enterprise)

    return {
        "success": True,
        "data": commits,
        "cached": False
    }


def get_author_from_commit(commit_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract author name from commit data, supporting both formats:
    1. GitHub API format: commit_data["commit"]["author"]["name"]
    2. Custom extraction format: commit_data["author"]
    """
    # Try custom extraction format first (more common in local data)
    if "author" in commit_data and isinstance(commit_data["author"], str):
        return commit_data["author"]

    # Try GitHub/Gitee API format
    if "commit" in commit_data:
        author = commit_data.get("commit", {}).get("author", {}).get("name")
        if author:
            return author

        # Some APIs may populate committer name but not author name
        committer = commit_data.get("commit", {}).get("committer", {}).get("name")
        if committer:
            return committer

    # Some providers use nested dicts for author/committer
    if "author" in commit_data and isinstance(commit_data["author"], dict):
        name = commit_data["author"].get("name")
        if name:
            return name

    if "committer" in commit_data and isinstance(commit_data["committer"], dict):
        name = commit_data["committer"].get("name")
        if name:
            return name

    return None


def parse_repo_url(url: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse repository URL and return (platform, owner, repo).

    Supports:
    - GitHub: https://github.com/owner/repo, github.com/owner/repo, git@github.com:owner/repo(.git)
    - Gitee:  https://gitee.com/owner/repo(.git)
    """
    url = (url or "").strip()
    if not url:
        return None

    parsed = parse_github_url(url)
    if parsed:
        return ("github", parsed["owner"], parsed["repo"])

    import re

    patterns = [
        r'^https?://(?:www\.)?gitee\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'^gitee\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
    ]
    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            owner, repo = match.groups()
            repo = repo.replace('.git', '')
            return ("gitee", owner, repo)

    return None


def extract_gitee_data(owner: str, repo: str, max_commits: int = 200) -> bool:
    """
    Extract Gitee repository data into platform-specific directory similar to GitHub extractor.

    This is a minimal extractor used by the multi-repo compare workflow.
    It fetches commit list then fetches per-commit details (which may include files/diffs depending on API support).
    """
    try:
        data_dir = get_platform_data_dir("gitee", owner, repo)
        data_dir.mkdir(parents=True, exist_ok=True)
        commits_dir = data_dir / "commits"
        commits_dir.mkdir(parents=True, exist_ok=True)

        # 1) Fetch commits list (paginated)
        commits: List[Dict[str, Any]] = []
        page = 1
        per_page = 100
        while len(commits) < max_commits:
            api_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/commits"
            params: Dict[str, Any] = {"per_page": per_page, "page": page}
            gitee_token = get_gitee_token()
            if gitee_token:
                params["access_token"] = gitee_token
            resp = requests.get(api_url, params=params, timeout=30)
            if resp.status_code != 200:
                print(f"✗ Gitee commits list failed: {resp.status_code} {resp.text[:200]}")
                return False
            batch = resp.json()
            if not isinstance(batch, list) or not batch:
                break
            commits.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        commits = commits[:max_commits]

        with open(data_dir / "commits_list.json", "w", encoding="utf-8") as f:
            json.dump(commits, f, indent=2, ensure_ascii=False)

        # 2) Fetch per-commit details
        commits_index = []
        for c in commits:
            sha = c.get("sha")
            if not sha:
                continue
            detail_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/commits/{sha}"
            params = {}
            gitee_token = get_gitee_token()
            if gitee_token:
                params["access_token"] = gitee_token
            dresp = requests.get(detail_url, params=params, timeout=30)
            if dresp.status_code != 200:
                # Fallback to list item
                detail = c
            else:
                detail = dresp.json()

            with open(commits_dir / f"{sha}.json", "w", encoding="utf-8") as f:
                json.dump(detail, f, indent=2, ensure_ascii=False)

            commit_msg = detail.get("commit", {}).get("message", "") if isinstance(detail, dict) else ""
            author_name = get_author_from_commit(detail) if isinstance(detail, dict) else ""
            commit_date = ""
            if isinstance(detail, dict):
                commit_date = detail.get("commit", {}).get("author", {}).get("date", "") or detail.get("commit", {}).get("committer", {}).get("date", "")
            file_list = []
            if isinstance(detail, dict):
                file_list = [fi.get("filename") for fi in (detail.get("files") or []) if isinstance(fi, dict) and fi.get("filename")]

            commits_index.append(
                {
                    "sha": sha,
                    "message": (commit_msg.split("\n")[0] if commit_msg else "")[:100],
                    "author": author_name or "",
                    "date": commit_date or "",
                    "files_changed": len(file_list),
                    "files": file_list,
                }
            )

        with open(data_dir / "commits_index.json", "w", encoding="utf-8") as f:
            json.dump(commits_index, f, indent=2, ensure_ascii=False)

        # 3) repo_info.json
        repo_info = {"name": f"{owner}/{repo}", "full_name": f"{owner}/{repo}", "owner": owner, "platform": "gitee"}
        with open(data_dir / "repo_info.json", "w", encoding="utf-8") as f:
            json.dump(repo_info, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"✗ Gitee extraction failed: {e}")
        return False


def get_repo_data_dir(platform: str, owner: str, repo: str) -> Path:
    """Get or create platform-specific data directory for repository"""
    data_dir = get_platform_data_dir(platform, owner, repo)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_or_create_evaluator(
    platform: str,
    owner: str,
    repo: str,
    commits: list,
    use_cache: bool = True,
    plugin_id: str = "",
    model: str = DEFAULT_LLM_MODEL,
):
    """
    Legacy helper (kept for compatibility).

    Persists commit JSONs into the repo data dir, then returns a plugin evaluator instance.
    """
    _ = use_cache
    data_dir = get_repo_data_dir(platform, owner, repo)

    # Create commits_index.json
    commits_index = [{"sha": c.get("sha"), "hash": c.get("sha")} for c in commits]
    with open(data_dir / "commits_index.json", "w", encoding="utf-8") as f:
        json.dump(commits_index, f, indent=2, ensure_ascii=False)

    # Save individual commits
    commits_dir = data_dir / "commits"
    commits_dir.mkdir(exist_ok=True)
    for commit in commits:
        sha = commit.get("sha")
        if sha:
            with open(commits_dir / f"{sha}.json", "w", encoding="utf-8") as f:
                json.dump(commit, f, indent=2, ensure_ascii=False)

    # repo_info.json
    repo_info = {"name": f"{owner}/{repo}", "full_name": f"{owner}/{repo}", "owner": owner, "platform": platform}
    with open(data_dir / "repo_info.json", "w", encoding="utf-8") as f:
        json.dump(repo_info, f, indent=2, ensure_ascii=False)

    pid = _resolve_plugin_id(plugin_id)
    meta, scan_mod, scan_path = load_scan_module(pid)
    api_key = get_llm_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM not configured")

    evaluator = scan_mod.create_commit_evaluator(
        data_dir=str(data_dir),
        api_key=api_key,
        model=model,
        mode="moderate",
    )
    print(f"✓ Created evaluator for {owner}/{repo} via plugin={pid} scan={scan_path}")
    _ = meta
    return evaluator


@app.get("/api/authors/{owner}/{repo}")
async def get_authors(owner: str, repo: str, platform: str = Query("github"), use_cache: bool = Query(True)):
    """
    Get list of authors from commit data

    Flow:
    1. Check if local data exists in platform-specific directory
    2. If no local data, extract it from GitHub/Gitee
    3. Load ALL authors from commits (always scans all commits)
    4. Return complete authors list
    """
    try:
        data_dir = get_platform_data_dir(platform, owner, repo)

        # Step 1 & 2: Check if local data exists, if not extract it
        if not data_dir.exists() or not (data_dir / "commits").exists():
            plat = (platform or "github").strip().lower()
            if plat == "gitee":
                print(f"No local data found for {owner}/{repo}, extracting from Gitee...")
                success = extract_gitee_data(owner, repo)
                if not success:
                    raise HTTPException(status_code=500, detail=f"Failed to extract Gitee data for {owner}/{repo}")
            else:
                print(f"No local data found for {owner}/{repo}, extracting from GitHub...")
                success = extract_github_data(owner, repo)
                if not success:
                    raise HTTPException(status_code=500, detail=f"Failed to extract GitHub data for {owner}/{repo}")

        # Step 3: Load all authors from commits
        commits_dir = data_dir / "commits"
        if not commits_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No commit data found for {owner}/{repo}"
            )

        authors_map = {}

        # Check for direct .json files in commits directory
        for commit_file in commits_dir.glob("*.json"):
            try:
                with open(commit_file, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    author = get_author_from_commit(commit_data)

                    # Get email from commit data (GitHub/Gitee shapes differ)
                    email = ""
                    if "commit" in commit_data:
                        email = commit_data.get("commit", {}).get("author", {}).get("email", "") or ""
                    if not email and isinstance(commit_data.get("author"), dict):
                        email = commit_data.get("author", {}).get("email", "") or ""
                    if not email and isinstance(commit_data.get("committer"), dict):
                        email = commit_data.get("committer", {}).get("email", "") or ""

                    if author:
                        if author not in authors_map:
                            authors_map[author] = {
                                "author": author,
                                "email": email,
                                "commits": 0
                            }
                        authors_map[author]["commits"] += 1
            except Exception as e:
                print(f"⚠ Error reading {commit_file}: {e}")
                continue

        if not authors_map:
            raise HTTPException(
                status_code=404,
                detail=f"No commit authors found in {commits_dir}"
            )

        # Sort by commit count
        authors_list = sorted(
            authors_map.values(),
            key=lambda x: x["commits"],
            reverse=True
        )

        return {
            "success": True,
            "data": {
                "owner": owner,
                "repo": repo,
                "authors": authors_list,
                "total_authors": len(authors_list),
                "cached": False
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Failed to get authors: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get authors: {str(e)}")


def evaluate_author_incremental(
    commits: List[Dict[str, Any]],
    author: str,
    previous_evaluation: Optional[Dict[str, Any]],
    data_dir: Path,
    model: str,
    use_chunking: bool,
    api_key: str,
    aliases: Optional[List[str]] = None,
    evaluator_factory=None,
) -> Dict[str, Any]:
    """
    Evaluate author incrementally with weighted merge

    Args:
        commits: All commits from repository
        author: Author username to evaluate
        previous_evaluation: Previous evaluation if exists
        data_dir: Path to repository data directory
        model: LLM model to use
        use_chunking: Whether to enable chunked evaluation
        api_key: LLM API key
        aliases: Optional list of author name aliases (normalized/lowercase)

    Returns:
        Evaluation result with merged scores
    """
    # Filter commits by author (including aliases)
    if aliases:
        author_commits = [
            c for c in commits
            if any(_is_commit_by_author(c, alias) for alias in aliases)
        ]
        print(f"[Incremental] Filtering commits by {len(aliases)} aliases: {aliases}")
    else:
        author_commits = [c for c in commits if _is_commit_by_author(c, author)]

    if not author_commits:
        return _get_empty_evaluation(author)

    if evaluator_factory is None:
        raise HTTPException(status_code=500, detail="Evaluator factory not provided (plugin load failed?)")

    # Case 1: No previous evaluation → evaluate all commits
    if not previous_evaluation:
        print(f"[Incremental] First evaluation: {len(author_commits)} commits")

        evaluator = evaluator_factory()

        # Heartbeat progress logs: LLM evaluation can take a while with no stdout.
        stop_event = threading.Event()
        started_at = time.time()

        def _heartbeat():
            while not stop_event.wait(15):
                elapsed = int(time.time() - started_at)
                print(f"[LLM] Evaluating... elapsed={elapsed}s (author={author}, commits={len(author_commits)}, chunking={use_chunking})")

        hb = threading.Thread(target=_heartbeat, daemon=True)
        hb.start()

        try:
            print(f"[LLM] Starting evaluation (author={author}, commits={len(author_commits)}, chunking={use_chunking})")
            evaluation = evaluator.evaluate_engineer(
                commits=author_commits,
                username=author,
                max_commits=150,
                load_files=True,
                use_chunking=use_chunking
            )
        except Exception as e:
            stop_event.set()
            raise HTTPException(status_code=502, detail=f"LLM evaluation failed: {str(e)}")
        finally:
            stop_event.set()
            elapsed = int(time.time() - started_at)
            print(f"[LLM] Evaluation finished in {elapsed}s (author={author})")

        evaluation["last_commit_sha"] = author_commits[0].get("sha") or author_commits[0].get("hash")
        evaluation["total_commits_evaluated"] = len(author_commits) if len(author_commits) <= 150 else 150
        evaluation["new_commits_count"] = evaluation["total_commits_evaluated"]
        evaluation["evaluated_at"] = datetime.now().isoformat()
        evaluation["incremental"] = False

        return evaluation

    # Case 2: Find new commits since last evaluation
    last_sha = previous_evaluation.get("last_commit_sha")

    if not last_sha:
        # Previous evaluation has no SHA, re-evaluate all
        print(f"[Incremental] No last SHA found, re-evaluating all commits")
        previous_evaluation = None
        return evaluate_author_incremental(commits, author, None, data_dir, model, use_chunking, api_key)

    # Find new commits
    new_commits = []
    for commit in author_commits:
        commit_sha = commit.get("sha") or commit.get("hash")
        if commit_sha == last_sha:
            break
        new_commits.append(commit)

    if not new_commits:
        print(f"[Incremental] No new commits since last evaluation")
        return previous_evaluation

    print(f"[Incremental] Found {len(new_commits)} new commits, evaluating...")

    # Evaluate new commits only
    evaluator = evaluator_factory()

    # Heartbeat progress logs for incremental run
    stop_event = threading.Event()
    started_at = time.time()

    def _heartbeat():
        while not stop_event.wait(15):
            elapsed = int(time.time() - started_at)
            print(f"[LLM] Evaluating incremental... elapsed={elapsed}s (author={author}, new_commits={len(new_commits)}, chunking={use_chunking})")

    hb = threading.Thread(target=_heartbeat, daemon=True)
    hb.start()

    try:
        print(f"[LLM] Starting incremental evaluation (author={author}, new_commits={len(new_commits)}, chunking={use_chunking})")
        new_evaluation = evaluator.evaluate_engineer(
            commits=new_commits,
            username=author,
            max_commits=len(new_commits),
            load_files=True,
            use_chunking=use_chunking
        )
    except Exception as e:
        stop_event.set()
        raise HTTPException(status_code=502, detail=f"LLM evaluation failed: {str(e)}")
    finally:
        stop_event.set()
        elapsed = int(time.time() - started_at)
        print(f"[LLM] Incremental evaluation finished in {elapsed}s (author={author})")

    # Weighted merge of scores
    prev_count = previous_evaluation.get("total_commits_evaluated", 0)
    new_count = len(new_commits)
    total_count = prev_count + new_count

    print(f"[Incremental] Merging scores: {prev_count} previous + {new_count} new = {total_count} total")

    merged_scores = {}
    prev_scores = previous_evaluation.get("scores", {})
    new_scores = new_evaluation.get("scores", {})

    for key in prev_scores.keys():
        if key == "reasoning":
            # Prepend new reasoning
            merged_scores[key] = (
                f"**Recent Activity ({new_count} new commits):**\n{new_scores.get(key, '')}\n\n"
                f"---\n\n"
                f"**Previous Assessment ({prev_count} commits):**\n{prev_scores[key]}"
            )
        else:
            # Weighted average for scores
            prev_val = prev_scores.get(key, 0)
            new_val = new_scores.get(key, 0)
            merged_val = (prev_val * prev_count + new_val * new_count) / total_count
            merged_scores[key] = int(merged_val)

    # Merge commit summaries
    prev_summary = previous_evaluation.get("commits_summary", {})
    new_summary = new_evaluation.get("commits_summary", {})

    merged_summary = {
        "total_additions": prev_summary.get("total_additions", 0) + new_summary.get("total_additions", 0),
        "total_deletions": prev_summary.get("total_deletions", 0) + new_summary.get("total_deletions", 0),
        "files_changed": prev_summary.get("files_changed", 0) + new_summary.get("files_changed", 0),
        "languages": list(set(prev_summary.get("languages", []) + new_summary.get("languages", [])))[:10]
    }

    return {
        "username": author,
        "total_commits_evaluated": total_count,
        "new_commits_count": new_count,
        "last_commit_sha": author_commits[0].get("sha") or author_commits[0].get("hash"),
        "evaluated_at": datetime.now().isoformat(),
        "scores": merged_scores,
        "commits_summary": merged_summary,
        "mode": "moderate",
        "incremental": True,
        "files_loaded": new_evaluation.get("files_loaded", 0),
        "chunked": new_evaluation.get("chunked", False),
        "chunks_processed": new_evaluation.get("chunks_processed", 0)
    }


def _is_commit_by_author(commit: Dict[str, Any], username: str) -> bool:
    """Check if commit is by the specified author"""
    # Try custom extraction format first
    if "author" in commit and isinstance(commit["author"], str):
        return commit["author"].lower() == username.lower()

    # Try GitHub API format
    if "commit" in commit:
        author = commit.get("commit", {}).get("author", {}).get("name", "")
        if author:
            return author.lower() == username.lower()

    return False


def _get_empty_evaluation(username: str) -> Dict[str, Any]:
    """Return empty evaluation for author with no commits"""
    return {
        "username": username,
        "total_commits_evaluated": 0,
        "new_commits_count": 0,
        "scores": {
            "ai_fullstack": 0,
            "ai_architecture": 0,
            "cloud_native": 0,
            "open_source": 0,
            "intelligent_dev": 0,
            "leadership": 0,
            "reasoning": "No commits found for this author."
        },
        "commits_summary": {
            "total_additions": 0,
            "total_deletions": 0,
            "files_changed": 0,
            "languages": []
        },
        "mode": "moderate",
        "incremental": False
    }


@app.post("/api/evaluate/{owner}/{repo}/{author}")
async def evaluate_author(
    owner: str,
    repo: str,
    author: str,
    use_chunking: bool = Query(True),
    use_cache: bool = Query(True),
    model: str = Query(DEFAULT_LLM_MODEL),
    platform: str = Query("github"),
    plugin: str = Query(""),
    request_body: Optional[Dict[str, Any]] = None
):
    """
    Evaluate an author with auto-sync and incremental evaluation

    This endpoint:
    1. Auto-syncs new commits from remote repository
    2. Loads previous evaluation if exists
    3. Evaluates only new commits incrementally
    4. Merges scores using weighted average
    5. Stores evaluation persistently

    Request body (optional):
    {
        "aliases": ["name1", "name2", "name3"]  // Optional list of author name aliases
    }

    Flow:
    1. Auto-sync: Fetch new commits from remote
    2. Load all commits from local data
    3. Load previous evaluation (if exists)
    4. Incremental evaluation: Evaluate only new commits
    5. Weighted merge: Combine new scores with previous scores
    6. Save evaluation persistently
    7. Return evaluation

    Args:
        owner: Repository owner
        repo: Repository name
        author: Author/username to evaluate
        use_chunking: Whether to enable chunked evaluation for large commit sets
        model: LLM model to use
        platform: Platform (github or gitee)
    """
    try:
        plugin_id = _resolve_plugin_id(plugin)

        # Load plugin scan module (if available)
        scan_mod = None
        meta = None
        scan_path = None
        default_plugin_id = get_default_plugin_id(discover_plugins())
        try:
            meta, scan_mod, scan_path = load_scan_module(plugin_id)
        except PluginLoadError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Parse aliases from request body
        aliases = None
        if request_body and isinstance(request_body, dict):
            aliases_list = request_body.get("aliases")
            if aliases_list and isinstance(aliases_list, list):
                # Normalize aliases to lowercase
                aliases = [str(a).lower().strip() for a in aliases_list if a]
                print(f"[Aliases] Using {len(aliases)} aliases: {aliases}")

        # Normalize model parameter
        if not isinstance(model, str):
            model = DEFAULT_LLM_MODEL

        # Step 1: Auto-sync new commits
        data_dir = get_platform_data_dir(platform, owner, repo)

        if not data_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No local data found for {platform}/{owner}/{repo}. Please extract data first."
            )

        # If aliases provided, evaluate each separately and merge
        if aliases and len(aliases) > 1:
            print(f"\n[Aliases] Evaluating {len(aliases)} identities separately then merging...")

            evaluations_to_merge = []

            for alias in aliases:
                print(f"\n[Aliases] Evaluating identity: {alias}")

                # Load commits
                commits = load_commits_from_local(data_dir, limit=None)
                if not commits:
                    print(f"[Aliases] ⚠ No commits found, skipping {alias}")
                    continue

                # Filter by this alias
                alias_commits = [c for c in commits if _is_commit_by_author(c, alias)]
                if not alias_commits:
                    print(f"[Aliases] ⚠ No commits found for {alias}, skipping")
                    continue

                print(f"[Aliases] Found {len(alias_commits)} commits for {alias}")

                # Load previous evaluation for this alias
                # Normalize alias to lowercase for file path to avoid case sensitivity issues
                eval_dir = get_platform_eval_dir(platform, owner, repo)
                eval_path = _evaluation_cache_path(eval_dir, alias, plugin_id, default_plugin_id)
                previous_evaluation = None

                if use_cache and eval_path.exists():
                    try:
                        with open(eval_path, 'r', encoding='utf-8') as f:
                            previous_evaluation = json.load(f)
                        print(f"[Aliases] Found cached evaluation for {alias}")
                    except Exception as e:
                        print(f"[Aliases] ⚠ Failed to load cached evaluation: {e}")

                # Evaluate this alias
                api_key = get_llm_api_key()
                if not api_key:
                    raise HTTPException(status_code=500, detail="LLM not configured")

                evaluator_factory = None
                if scan_mod is not None:
                    def _factory():
                        return scan_mod.create_commit_evaluator(
                            data_dir=str(data_dir),
                            api_key=api_key,
                            model=model,
                            mode="moderate",
                        )
                    evaluator_factory = _factory

                evaluation = evaluate_author_incremental(
                    commits=commits,
                    author=alias,
                    previous_evaluation=previous_evaluation,
                    data_dir=data_dir,
                    model=model,
                    use_chunking=use_chunking,
                    api_key=api_key,
                    aliases=[alias],  # Evaluate this single alias
                    evaluator_factory=evaluator_factory,
                )
                evaluation["plugin"] = plugin_id
                if meta is not None:
                    evaluation["plugin_version"] = meta.version

                # Save evaluation for this alias (optional)
                if use_cache:
                    eval_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(eval_path, 'w', encoding='utf-8') as f:
                        json.dump(evaluation, f, indent=2, ensure_ascii=False)

                # Collect for merging
                evaluations_to_merge.append({
                    "author": alias,
                    "weight": len(alias_commits),
                    "evaluation": evaluation
                })

                print(f"[Aliases] ✓ Evaluated {alias}: {len(alias_commits)} commits")

            # Merge all evaluations
            if len(evaluations_to_merge) < 2:
                # If only one alias had commits, return that evaluation
                if len(evaluations_to_merge) == 1:
                    result = {
                        "success": True,
                        "evaluation": evaluations_to_merge[0]["evaluation"],
                        "metadata": {
                            "cached": False,
                            "timestamp": datetime.now().isoformat(),
                            "source": "single_alias"
                        }
                    }
                    return result
                else:
                    raise HTTPException(status_code=404, detail="No commits found for any of the provided aliases")

            # Call merge API
            print(f"[Aliases] Merging {len(evaluations_to_merge)} evaluations...")
            merge_response = await merge_evaluations({
                "evaluations": evaluations_to_merge,
                "model": model
            })

            merged_eval = merge_response["merged_evaluation"]

            # Return merged result
            result = {
                "success": True,
                "evaluation": merged_eval,
                "metadata": {
                    "cached": False,
                    "timestamp": datetime.now().isoformat(),
                    "source": "merged_aliases",
                    "merged_from": len(evaluations_to_merge)
                }
            }

            return result

        # Original flow: single author evaluation
        print(f"\n[Auto-Sync] Checking for new commits in {owner}/{repo}...")

        try:
            from evaluator.sync_manager import SyncManager
            from evaluator.collectors.github import GitHubCollector
            from evaluator.collectors.gitee import GiteeCollector

            sync_manager = SyncManager(
                data_dir=data_dir,
                platform=platform,
                owner=owner,
                repo=repo
            )

            # Choose collector based on platform
            if platform == "gitee":
                # GiteeCollector distinguishes enterprise token vs public token.
                # Our dashboard config provides a single GITEE_TOKEN; use it for both.
                _tk = get_gitee_token()
                collector = GiteeCollector(token=_tk, public_token=_tk, cache_dir=str(data_dir))
            else:
                collector = GitHubCollector(token=get_github_token(), cache_dir=str(data_dir))

            sync_result = sync_manager.sync_incremental(collector)
            print(f"[Auto-Sync] ✓ {sync_result['commits_added']} new commits fetched")

        except Exception as sync_error:
            print(f"[Auto-Sync] ⚠ Sync failed: {sync_error}")
            print("[Auto-Sync] Continuing with existing local data...")

        # Step 2: Load ALL commits from local data
        print(f"\n[Evaluation] Loading commits for {author}...")
        commits = load_commits_from_local(data_dir, limit=None)
        if not commits:
            raise HTTPException(
                status_code=404,
                detail=f"No commits found in local data for {owner}/{repo}"
            )

        print(f"[Evaluation] Loaded {len(commits)} total commits")

        # Step 3: Load previous evaluation
        # Normalize author name to lowercase for file path to avoid case sensitivity issues
        eval_dir = get_platform_eval_dir(platform, owner, repo)
        eval_path = _evaluation_cache_path(eval_dir, author, plugin_id, default_plugin_id)
        previous_evaluation = None

        if use_cache and eval_path.exists():
            try:
                with open(eval_path, 'r', encoding='utf-8') as f:
                    previous_evaluation = json.load(f)
                print(f"[Evaluation] Found previous evaluation for {author}")
            except Exception as e:
                print(f"[Evaluation] ⚠ Failed to load previous evaluation: {e}")

        # Step 4: Incremental evaluation
        api_key = get_llm_api_key()
        if not api_key:
            raise HTTPException(status_code=500, detail="LLM not configured")

        # Plugin contract: create_commit_evaluator(data_dir, api_key, model, mode, **kwargs)
        def _factory():
            return scan_mod.create_commit_evaluator(
                data_dir=str(data_dir),
                api_key=api_key,
                model=model,
                mode="moderate",
            )
        evaluator_factory = _factory

        evaluation = evaluate_author_incremental(
            commits=commits,
            author=author,
            previous_evaluation=previous_evaluation,
            data_dir=data_dir,
            model=model,
            use_chunking=use_chunking,
            api_key=api_key,
            aliases=aliases,
            evaluator_factory=evaluator_factory,
        )
        evaluation["plugin"] = plugin_id
        if meta is not None:
            evaluation["plugin_version"] = meta.version
        if scan_path is not None:
            evaluation["plugin_scan_path"] = str(scan_path)
            print(f"[Plugin] Using plugin={plugin_id} scan={scan_path}")

        # Step 5: Save evaluation persistently (optional)
        if use_cache:
            eval_path.parent.mkdir(parents=True, exist_ok=True)
            with open(eval_path, 'w', encoding='utf-8') as f:
                json.dump(evaluation, f, indent=2, ensure_ascii=False)
            print(f"[Evaluation] ✓ Saved evaluation to {eval_path}")
        else:
            print(f"[Evaluation] (no-cache) Skipping save to {eval_path}")

        # Step 6: Return response
        result = {
            "success": True,
            "evaluation": {
                "username": evaluation.get("username", author),
                "mode": evaluation.get("mode", "moderate"),
                "total_commits_evaluated": evaluation.get("total_commits_evaluated", 0),
                "new_commits_count": evaluation.get("new_commits_count", 0),
                "files_loaded": evaluation.get("files_loaded", 0),
                "chunked": evaluation.get("chunked", False),
                "chunks_processed": evaluation.get("chunks_processed", 0),
                "scores": evaluation.get("scores", {}),
                "commits_summary": evaluation.get("commits_summary", {}),
                "incremental": evaluation.get("incremental", False),
                "plugin": evaluation.get("plugin", plugin_id),
                "plugin_version": evaluation.get("plugin_version", ""),
                "plugin_scan_path": evaluation.get("plugin_scan_path", ""),
            },
            "metadata": {
                "synced": True,
                "commits_added": sync_result.get("commits_added", 0) if 'sync_result' in locals() else 0,
                "timestamp": datetime.now().isoformat(),
                "source": "persistent_storage" if use_cache else "no_cache",
                "use_cache": bool(use_cache),
            }
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@app.post("/api/merge-evaluations")
async def merge_evaluations(request: dict):
    """
    Merge multiple evaluations into one using LLM-based weighted combination

    This is more efficient than re-evaluating all commits from scratch.
    Each author is evaluated separately (potentially using cached results),
    then their summaries are merged with weights based on commit count.

    Request body:
    {
        "evaluations": [
            {
                "author": "CarterWu",
                "weight": 42,
                "evaluation": {...}  // Full evaluation object
            },
            {
                "author": "wu-yanbiao",
                "weight": 3,
                "evaluation": {...}
            }
        ],
        "model": "openai/gpt-4o"  // Optional
    }

    Response:
    {
        "success": true,
        "merged_evaluation": {
            "scores": {...},  // Weighted average scores
            "reasoning": "...",  // LLM-generated merged summary
            "total_commits_analyzed": 45,
            ...
        }
    }
    """
    evaluations_data = request.get("evaluations", [])
    model = request.get("model", DEFAULT_LLM_MODEL)

    if not evaluations_data or len(evaluations_data) < 2:
        raise HTTPException(status_code=400, detail="At least 2 evaluations required for merging")

    try:
        # Extract evaluations and weights
        evaluations = []
        weights = []
        authors = []

        for item in evaluations_data:
            author = item.get("author", "Unknown")
            weight = item.get("weight", 0)
            evaluation = item.get("evaluation", {})

            authors.append(author)
            weights.append(weight)
            evaluations.append(evaluation)

        total_weight = sum(weights)
        if total_weight == 0:
            raise HTTPException(status_code=400, detail="Total weight cannot be zero")

        print(f"[Merge] Merging {len(evaluations)} evaluations with weights: {weights}")

        # Step 1: Calculate weighted average scores
        merged_scores = {}
        dimension_keys = ['ai_fullstack', 'ai_architecture', 'cloud_native', 'open_source', 'intelligent_dev', 'leadership']

        for key in dimension_keys:
            weighted_sum = 0
            for eval_data, weight in zip(evaluations, weights):
                scores = eval_data.get("scores", {})
                score_value = scores.get(key, 0)
                # Handle both numeric and string scores
                if isinstance(score_value, str):
                    try:
                        score_value = float(score_value)
                    except:
                        score_value = 0
                weighted_sum += score_value * weight

            merged_scores[key] = round(weighted_sum / total_weight, 1)

        # Step 2: Merge commit summaries
        total_commits = sum(eval_data.get("total_commits_analyzed", 0) for eval_data in evaluations)

        merged_commits_summary = {
            "total_additions": sum(eval_data.get("commits_summary", {}).get("total_additions", 0) for eval_data in evaluations),
            "total_deletions": sum(eval_data.get("commits_summary", {}).get("total_deletions", 0) for eval_data in evaluations),
            "files_changed": sum(eval_data.get("commits_summary", {}).get("files_changed", 0) for eval_data in evaluations),
            "languages": list(set(
                lang
                for eval_data in evaluations
                for lang in eval_data.get("commits_summary", {}).get("languages", [])
            ))
        }

        # Step 3: Use LLM to merge reasoning/analysis summaries
        print(f"[Merge] Using LLM to merge analysis summaries...")

        # Build prompt for LLM
        summaries_text = ""
        for author, weight, eval_data in zip(authors, weights, evaluations):
            reasoning = eval_data.get("scores", {}).get("reasoning", "")
            percentage = round((weight / total_weight) * 100, 1)
            summaries_text += f"\n### {author} ({weight} commits, {percentage}% weight):\n{reasoning}\n"

        merge_prompt = f"""You are analyzing a software engineer who uses multiple names/identities in their commits. You have separate evaluations for each identity, and you need to create a unified, comprehensive analysis.

Below are the individual analyses with their weights (based on commit count):

{summaries_text}

Total commits: {total_commits}
Weighted average scores:
- AI Model Full-Stack: {merged_scores['ai_fullstack']}/100
- AI Native Architecture: {merged_scores['ai_architecture']}/100
- Cloud Native Engineering: {merged_scores['cloud_native']}/100
- Open Source Collaboration: {merged_scores['open_source']}/100
- Intelligent Development: {merged_scores['intelligent_dev']}/100
- Engineering Leadership: {merged_scores['leadership']}/100

Create a unified analysis that:
1. Synthesizes insights from all identities
2. Gives more weight to analyses with higher commit counts
3. Identifies common patterns and themes across all identities
4. Presents a coherent narrative about this engineer's capabilities
5. Maintains a professional, objective tone

Write the unified analysis (3-5 paragraphs):"""

        # Call LLM to merge summaries
        api_key = get_llm_api_key()
        if not api_key:
            # Fallback: simple concatenation
            merged_reasoning = f"Combined analysis from {len(authors)} identities ({', '.join(authors)}):\n\n"
            merged_reasoning += summaries_text
        else:
            try:
                llm_response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "user", "content": merge_prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1500
                    },
                    timeout=60
                )

                if llm_response.ok:
                    response_data = llm_response.json()
                    merged_reasoning = response_data["choices"][0]["message"]["content"]
                    print(f"[Merge] ✓ LLM successfully merged summaries ({len(merged_reasoning)} chars)")
                else:
                    print(f"[Merge] ⚠ LLM request failed, using concatenation fallback")
                    merged_reasoning = f"Combined analysis from {len(authors)} identities:\n\n" + summaries_text

            except Exception as e:
                print(f"[Merge] ⚠ LLM merge failed: {e}, using concatenation fallback")
                merged_reasoning = f"Combined analysis from {len(authors)} identities:\n\n" + summaries_text

        # Add merged reasoning to scores
        merged_scores["reasoning"] = merged_reasoning

        # Build final merged evaluation
        merged_evaluation = {
            "username": " + ".join(authors),
            "mode": "merged",
            "total_commits_analyzed": total_commits,
            "merged_from": len(evaluations),
            "authors": authors,
            "weights": weights,
            "scores": merged_scores,
            "commits_summary": merged_commits_summary,
            "files_loaded": sum(eval_data.get("files_loaded", 0) for eval_data in evaluations)
        }

        return {
            "success": True,
            "merged_evaluation": merged_evaluation
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Merge failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")


@app.post("/api/gitee/evaluate/{owner}/{repo}/{contributor}")
async def evaluate_gitee_contributor(
    owner: str,
    repo: str,
    contributor: str,
    limit: int = Query(150, ge=1, le=200),
    use_cache: bool = Query(True),
    is_enterprise: bool = Query(False),
    plugin: str = Query(""),
):
    """Evaluate a Gitee contributor (max 150 commits per contributor)"""
    platform = "gitee"

    try:
        # 1. Get commits from API
        commits = fetch_gitee_commits(owner, repo, 500, is_enterprise)

        # 2. Get or create evaluator
        # Use selected plugin evaluator (default if not provided)
        plugin_id = _resolve_plugin_id(plugin)
        meta, scan_mod, scan_path = load_scan_module(plugin_id)
        api_key = get_llm_api_key()
        if not api_key:
            raise HTTPException(status_code=500, detail="LLM not configured")
        evaluator = scan_mod.create_commit_evaluator(
            data_dir=str(get_repo_data_dir(platform, owner, repo)),
            api_key=api_key,
            model=DEFAULT_LLM_MODEL,
            mode="moderate",
        )
        print(f"[Plugin] Using plugin={plugin_id} scan={scan_path}")

        # 3. Evaluate contributor using moderate evaluator
        try:
            evaluation = evaluator.evaluate_engineer(
                commits=commits,
                username=contributor,
                max_commits=limit,
                load_files=True
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"LLM evaluation failed: {str(e)}")

        if not evaluation or "scores" not in evaluation:
            raise HTTPException(status_code=404, detail=f"Contributor '{contributor}' not found")

        # Format response for dashboard
        # The moderate evaluator already returns the correct structure
        result = {
            "success": True,
            "evaluation": {
                "username": evaluation.get("username", contributor),
                "mode": evaluation.get("mode", "moderate"),
                "total_commits_analyzed": evaluation.get("total_commits_analyzed", 0),
                "files_loaded": evaluation.get("files_loaded", 0),
                "scores": evaluation.get("scores", {}),
                "commits_summary": evaluation.get("commits_summary", {}),
                "plugin": plugin_id,
                "plugin_version": meta.version,
                "plugin_scan_path": str(scan_path),
            },
            "metadata": {
                "cached": False,
                "timestamp": datetime.now().isoformat()
            }
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


# NOTE: Score normalization endpoints disabled (ScoreNormalizer module removed)
# @app.get("/api/local/normalized/{owner}/{repo}")
# @app.get("/api/local/compare/{owner}/{repo}")


def parse_github_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parse GitHub URL to extract owner and repo
    Supports formats:
    - https://github.com/owner/repo
    - http://github.com/owner/repo
    - github.com/owner/repo
    - git@github.com:owner/repo.git
    """
    import re

    url = url.strip()

    # Try different patterns
    patterns = [
        r'^https?://(?:www\.)?github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'^github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'^git@github\.com:([^/]+)/([^/\s]+?)(?:\.git)?$',
    ]

    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            owner, repo = match.groups()
            # Remove .git suffix if present
            repo = repo.replace('.git', '')
            return {"owner": owner, "repo": repo}

    return None


@app.post("/api/batch/extract")
async def batch_extract_repos(request: dict):
    """
    Batch extract multiple repositories (GitHub + Gitee)

    Request body:
    {
        "urls": ["https://github.com/owner/repo1", "https://gitee.com/owner/repo2"]
    }

    Response:
    {
        "success": true,
        "results": [
            {
                "url": "https://github.com/owner/repo1",
                "owner": "owner",
                "repo": "repo1",
                "status": "extracted" | "skipped" | "failed",
                "message": "...",
                "data_exists": true/false
            }
        ]
    }
    """
    urls = request.get("urls", [])

    if not urls:
        raise HTTPException(status_code=400, detail="No URLs provided")

    if len(urls) < 2:
        raise HTTPException(status_code=400, detail="Please provide at least 2 repository URLs")

    if len(urls) > 5:
        raise HTTPException(status_code=400, detail="Please provide at most 5 repository URLs")

    results = []

    for url in urls:
        result = {
            "url": url,
            "status": "failed",
            "message": "",
            "data_exists": False
        }

        parsed = parse_repo_url(url)
        if not parsed:
            result["message"] = "Invalid repository URL format"
            results.append(result)
            continue

        platform, owner, repo = parsed
        result["owner"] = owner
        result["repo"] = repo
        result["platform"] = platform

        # Check if data already exists
        data_dir = get_platform_data_dir(platform, owner, repo)
        commits_dir = data_dir / "commits"

        if data_dir.exists() and commits_dir.exists() and list(commits_dir.glob("*.json")):
            result["status"] = "skipped"
            result["message"] = "Repository data already exists"
            result["data_exists"] = True
            results.append(result)
            continue

        # Extract data
        try:
            if platform == "github":
                success = extract_github_data(owner, repo)
            else:
                success = extract_gitee_data(owner, repo)
            if success:
                result["status"] = "extracted"
                result["message"] = "Successfully extracted repository data"
                result["data_exists"] = True
            else:
                result["status"] = "failed"
                result["message"] = "Failed to extract repository data"
        except Exception as e:
            result["status"] = "failed"
            result["message"] = f"Error: {str(e)}"

        results.append(result)

    # Count statuses
    extracted_count = sum(1 for r in results if r["status"] == "extracted")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    return {
        "success": True,
        "results": results,
        "summary": {
            "total": len(results),
            "extracted": extracted_count,
            "skipped": skipped_count,
            "failed": failed_count
        }
    }


@app.post("/api/batch/common-contributors")
async def find_common_contributors(request: dict):
    """
    Find common contributors across multiple repositories

    Request body:
    {
        "repos": [
            {"owner": "facebook", "repo": "react"},
            {"owner": "vercel", "repo": "next.js"}
        ]
    }

    Response:
    {
        "success": true,
        "common_contributors": [
            {
                "author": "John Doe",
                "email": "john@example.com",
                "repos": [
                    {
                        "owner": "facebook",
                        "repo": "react",
                        "commits": 150
                    },
                    {
                        "owner": "vercel",
                        "repo": "next.js",
                        "commits": 75
                    }
                ],
                "total_commits": 225,
                "repo_count": 2
            }
        ],
        "summary": {
            "total_repos": 2,
            "total_common_contributors": 5
        }
    }
    """
    repos = request.get("repos", [])
    author_aliases = request.get("author_aliases", "")  # Comma-separated list of names belonging to the same person

    if not repos:
        raise HTTPException(status_code=400, detail="No repositories provided")

    if len(repos) < 2:
        raise HTTPException(status_code=400, detail="At least 2 repositories required to find common contributors")

    # Parse author aliases into a set of normalized names
    user_defined_aliases = set()
    if author_aliases and isinstance(author_aliases, str):
        # Split by comma and normalize
        aliases = [name.strip().lower() for name in author_aliases.split(',') if name.strip()]
        user_defined_aliases = set(aliases)
        if user_defined_aliases:
            print(f"📝 User-defined aliases: {user_defined_aliases}")

    # Load authors from each repository
    repo_authors = {}  # {repo_key: {author: {commits, email}}}

    for repo_info in repos:
        owner = repo_info.get("owner")
        repo = repo_info.get("repo")
        platform = repo_info.get("platform", "github")  # Default to github if not specified

        if not owner or not repo:
            continue

        repo_key = f"{owner}/{repo}"
        data_dir = get_platform_data_dir(platform, owner, repo)
        commits_dir = data_dir / "commits"

        if not commits_dir.exists():
            print(f"⚠ No commit data found for {repo_key}")
            continue

        authors_map = {}

        # Load all commit files
        for commit_file in commits_dir.glob("*.json"):
            try:
                with open(commit_file, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    author = get_author_from_commit(commit_data)

                    # Get email and GitHub user ID
                    email = ""
                    github_id = None
                    github_login = None

                    if "commit" in commit_data:
                        email = commit_data.get("commit", {}).get("author", {}).get("email", "")

                    # Get GitHub user info if available
                    if "author" in commit_data and isinstance(commit_data["author"], dict):
                        github_id = commit_data["author"].get("id")
                        github_login = commit_data["author"].get("login")

                    if author:
                        if author not in authors_map:
                            authors_map[author] = {
                                "commits": 0,
                                "email": email,
                                "github_id": github_id,
                                "github_login": github_login
                            }
                        authors_map[author]["commits"] += 1
            except Exception as e:
                print(f"⚠ Error reading {commit_file}: {e}")
                continue

        if authors_map:
            repo_authors[repo_key] = authors_map
            print(f"✓ Loaded {len(authors_map)} authors from {repo_key}")

    if len(repo_authors) < 2:
        return {
            "success": True,
            "common_contributors": [],
            "summary": {
                "total_repos": len(repo_authors),
                "total_common_contributors": 0
            },
            "message": "Not enough repositories with data to find common contributors"
        }

    # Find common contributors using intelligent matching
    # Strategy: Two-pass matching
    # Pass 1: Group by GitHub ID/login (strong identity signals)
    # Pass 2: Match orphaned authors to existing groups by fuzzy name

    def normalize_name(name):
        """Normalize name for fuzzy matching"""
        normalized = name.lower().strip()
        parts = normalized.split()
        return parts[0] if parts else normalized

    def names_match_fuzzy(name1, name2):
        """Check if two names likely refer to the same person"""
        norm1 = normalize_name(name1)
        norm2 = normalize_name(name2)

        # Exact match on first name
        if norm1 == norm2:
            return True

        # One name contains the other as a word
        words1 = name1.lower().split()
        words2 = name2.lower().split()

        if norm1 in words2 or norm2 in words1:
            return True

        return False

    # Pass 1: Group by GitHub ID/login
    identity_groups = {}  # {canonical_key: [{"repo_key": str, "author": str, "data": dict}]}
    orphaned_authors = []  # Authors without GitHub ID/login

    for repo_key, authors_map in repo_authors.items():
        for author, author_data in authors_map.items():
            github_id = author_data.get("github_id")
            github_login = author_data.get("github_login")

            # Use GitHub ID/login as canonical identity
            if github_id:
                canonical_key = f"github_id:{github_id}"
            elif github_login:
                canonical_key = f"github_login:{github_login}"
            else:
                # No strong identity, mark as orphaned for second pass
                orphaned_authors.append({
                    "repo_key": repo_key,
                    "author": author,
                    "data": author_data
                })
                continue

            if canonical_key not in identity_groups:
                identity_groups[canonical_key] = []

            identity_groups[canonical_key].append({
                "repo_key": repo_key,
                "author": author,
                "data": author_data
            })

    # Pass 1.5: Handle user-defined aliases
    # Merge all identity groups that match any of the user-defined aliases
    if user_defined_aliases:
        print(f"🔗 Grouping identities by user-defined aliases...")
        matched_keys = []

        # Find all identity groups that contain names matching the user-defined aliases
        for canonical_key, identities in identity_groups.items():
            for identity in identities:
                if identity["author"].lower().strip() in user_defined_aliases:
                    matched_keys.append(canonical_key)
                    break

        # Also check orphaned authors
        orphaned_matches = []
        for orphan in orphaned_authors:
            if orphan["author"].lower().strip() in user_defined_aliases:
                orphaned_matches.append(orphan)

        # If we found multiple groups/orphans matching the aliases, merge them
        if len(matched_keys) > 0 or len(orphaned_matches) > 0:
            # Create or use the first matched group as the primary group
            if matched_keys:
                primary_key = f"aliases:{','.join(sorted(user_defined_aliases))}"
                # Merge all matched groups into the primary group
                merged_identities = []
                for key in matched_keys:
                    merged_identities.extend(identity_groups[key])
                    if key != primary_key:
                        del identity_groups[key]

                # Add orphaned matches
                merged_identities.extend(orphaned_matches)

                # Remove orphaned matches from the orphaned_authors list
                orphaned_authors = [o for o in orphaned_authors if o not in orphaned_matches]

                identity_groups[primary_key] = merged_identities
                print(f"✓ Merged {len(matched_keys)} groups + {len(orphaned_matches)} orphans by aliases")
            else:
                # Only orphaned matches - create new group
                primary_key = f"aliases:{','.join(sorted(user_defined_aliases))}"
                identity_groups[primary_key] = orphaned_matches
                orphaned_authors = [o for o in orphaned_authors if o not in orphaned_matches]
                print(f"✓ Created group from {len(orphaned_matches)} orphaned authors matching aliases")

    # Pass 2: Try to match orphaned authors to existing groups by fuzzy name
    unmatched_orphans = []

    for orphan in orphaned_authors:
        matched = False

        # Try to match with existing groups by comparing names
        for canonical_key, identities in identity_groups.items():
            # Check if orphan name matches any name in this group
            for identity in identities:
                if names_match_fuzzy(orphan["author"], identity["author"]):
                    # Found a match! Add to this group
                    identity_groups[canonical_key].append(orphan)
                    matched = True
                    break

            if matched:
                break

        if not matched:
            unmatched_orphans.append(orphan)

    # Pass 3: Group remaining unmatched orphans by exact name
    for orphan in unmatched_orphans:
        canonical_key = f"name:{orphan['author'].lower().strip()}"

        if canonical_key not in identity_groups:
            identity_groups[canonical_key] = []

        identity_groups[canonical_key].append(orphan)

    # Build common contributors from identity groups
    common_contributors = []

    for canonical_key, identities in identity_groups.items():
        # Get unique repos for this identity
        repos_map = {}  # {repo_key: identity}

        for identity in identities:
            repo_key = identity["repo_key"]
            if repo_key not in repos_map:
                repos_map[repo_key] = identity

        # Consider common if appears in at least 2 repos
        if len(repos_map) >= 2:
            repos_with_author = []

            for repo_key, identity in repos_map.items():
                owner, repo = repo_key.split("/", 1)
                author_data = identity["data"]

                repos_with_author.append({
                    "owner": owner,
                    "repo": repo,
                    "commits": author_data["commits"],
                    "email": author_data.get("email", ""),
                    "github_login": author_data.get("github_login", ""),
                })

            total_commits = sum(r["commits"] for r in repos_with_author)

            # Use the most complete name and email
            primary_identity = identities[0]
            display_name = primary_identity["author"]
            email = primary_identity["data"].get("email", "")
            github_login = primary_identity["data"].get("github_login", "")

            # Try to find the most complete name
            for identity in identities:
                if identity["data"].get("github_login"):
                    github_login = identity["data"]["github_login"]
                    display_name = identity["author"]
                    break

            # Collect all unique author names for this identity
            all_names = list(set(identity["author"] for identity in identities))

            common_contributors.append({
                "author": display_name,
                "aliases": all_names,  # All names associated with this person
                "email": email,
                "github_login": github_login,
                "repos": repos_with_author,
                "total_commits": total_commits,
                "repo_count": len(repos_with_author),
                "matched_by": canonical_key.split(":")[0]  # "github_id", "github_login", "aliases", or "name"
            })

    # Sort by repo_count (descending), then by total_commits (descending)
    common_contributors.sort(key=lambda x: (-x["repo_count"], -x["total_commits"]))

    return {
        "success": True,
        "common_contributors": common_contributors,
        "summary": {
            "total_repos": len(repo_authors),
            "total_common_contributors": len(common_contributors)
        }
    }


@app.post("/api/batch/compare-contributor")
async def compare_contributor_across_repos(request: dict):
    """
    Compare a contributor's six-dimensional scores across multiple repositories

    Request body:
    {
        "contributor": "John Doe",
        "repos": [
            {"owner": "facebook", "repo": "react"},
            {"owner": "vercel", "repo": "next.js"}
        ]
    }

    Response:
    {
        "success": true,
        "contributor": "John Doe",
        "comparisons": [
            {
                "repo": "facebook/react",
                "owner": "facebook",
                "repo_name": "react",
                "scores": {
                    "ai_model_fullstack": 85,
                    "ai_native_architecture": 70,
                    ...
                },
                "total_commits": 150
            }
        ],
        "dimension_names": [...],
        "dimension_display_names": [...]
    }
    """
    contributor = request.get("contributor")
    repos = request.get("repos", [])
    use_cache = bool(request.get("use_cache", False))
    model = request.get("model") or DEFAULT_LLM_MODEL
    requested_plugin_id = str(request.get("plugin") or "").strip()
    plugin_id = _resolve_plugin_id(requested_plugin_id)
    if not isinstance(model, str):
        model = DEFAULT_LLM_MODEL

    # Parse author aliases
    author_aliases_str = request.get("author_aliases", "")
    contributor_aliases = None

    if author_aliases_str and isinstance(author_aliases_str, str):
        # Split by comma and normalize
        aliases = [name.strip().lower() for name in author_aliases_str.split(',') if name.strip()]
        # Check if contributor matches any of the aliases
        if contributor.lower().strip() in aliases:
            contributor_aliases = aliases
            print(f"🔗 Using {len(contributor_aliases)} aliases for contributor '{contributor}': {contributor_aliases}")
        else:
            # Contributor not in aliases list, just use the contributor name
            contributor_aliases = [contributor.lower().strip()]
    else:
        # No aliases provided, use contributor name only
        contributor_aliases = [contributor.lower().strip()]

    if not contributor:
        raise HTTPException(status_code=400, detail="Contributor name is required")

    if not repos:
        raise HTTPException(status_code=400, detail="At least one repository is required")

    if len(repos) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 repositories allowed")

    results = []
    failed_repos = []

    for repo_info in repos:
        owner = repo_info.get("owner")
        repo = repo_info.get("repo")
        repo_platform = repo_info.get("platform", "github")  # Default to github if not specified

        if not owner or not repo:
            continue

        try:
            # Check if data exists for this repo
            data_dir = get_platform_data_dir(repo_platform, owner, repo)
            if not data_dir.exists() or not (data_dir / "commits").exists():
                # Try to extract data in real-time
                print(f"⚡ Data not found for {owner}/{repo}, triggering real-time extraction...")
                try:
                    if repo_platform == "github":
                        extraction_success = extract_github_data(owner, repo)
                    else:
                        extraction_success = extract_gitee_data(owner, repo)

                    if not extraction_success:
                        failed_repos.append({
                            "repo": f"{owner}/{repo}",
                            "reason": "Failed to extract repository data in real-time"
                        })
                        continue

                    print(f"✓ Successfully extracted data for {owner}/{repo}")
                except Exception as extract_error:
                    print(f"✗ Extraction failed for {owner}/{repo}: {extract_error}")
                    failed_repos.append({
                        "repo": f"{owner}/{repo}",
                        "reason": f"Extraction error: {str(extract_error)}"
                    })
                    continue

            # Evaluate contributor in this repo
            eval_result = await evaluate_author(
                owner,
                repo,
                contributor,
                use_chunking=True,
                use_cache=use_cache,
                model=model,
                platform=repo_platform,
                plugin=plugin_id,
                request_body={"aliases": contributor_aliases},
            )

            if eval_result.get("success"):
                evaluation = eval_result["evaluation"]
                scores = evaluation.get("scores", {})

                results.append({
                    "repo": f"{owner}/{repo}",
                    "owner": owner,
                    "repo_name": repo,
                    "scores": {
                        "ai_model_fullstack": scores.get("ai_fullstack", 0),
                        "ai_native_architecture": scores.get("ai_architecture", 0),
                        "cloud_native": scores.get("cloud_native", 0),
                        "open_source_collaboration": scores.get("open_source", 0),
                        "intelligent_development": scores.get("intelligent_dev", 0),
                        "engineering_leadership": scores.get("leadership", 0)
                    },
                    "total_commits": evaluation.get("total_commits_analyzed", 0),
                    "commits_summary": evaluation.get("commits_summary", {}),
                    "cached": eval_result.get("metadata", {}).get("cached", False),
                    "plugin": evaluation.get("plugin", plugin_id),
                    "plugin_version": evaluation.get("plugin_version", ""),
                    "plugin_scan_path": evaluation.get("plugin_scan_path", ""),
                })
            else:
                error_msg = eval_result.get("message", "Evaluation failed")
                failed_repos.append({
                    "repo": f"{owner}/{repo}",
                    "reason": error_msg
                })

        except HTTPException as e:
            failed_repos.append({
                "repo": f"{owner}/{repo}",
                "reason": str(e.detail)
            })
        except Exception as e:
            print(f"✗ Failed to evaluate {contributor} in {owner}/{repo}: {e}")
            failed_repos.append({
                "repo": f"{owner}/{repo}",
                "reason": f"Error: {str(e)}"
            })

    if not results:
        return {
            "success": False,
            "message": "No evaluations found for this contributor across the specified repositories",
            "contributor": contributor,
            "failed_repos": failed_repos
        }

    # Calculate aggregate statistics
    avg_scores = {}
    dimension_keys = [
        "ai_model_fullstack",
        "ai_native_architecture",
        "cloud_native",
        "open_source_collaboration",
        "intelligent_development",
        "engineering_leadership"
    ]

    for dim in dimension_keys:
        scores_list = [r["scores"][dim] for r in results]
        avg_scores[dim] = sum(scores_list) / len(scores_list) if scores_list else 0

    total_commits_all_repos = sum(r["total_commits"] for r in results)

    return {
        "success": True,
        "contributor": contributor,
        "plugin_requested": requested_plugin_id or None,
        "plugin_used": plugin_id,
        "comparisons": results,
        "dimension_keys": dimension_keys,
        "dimension_names": [
            "AI Model Full-Stack & Trade-off Capability",
            "AI Native Architecture & Communication Design",
            "Cloud Native & Constraint Engineering",
            "Open Source Collaboration & Requirements Translation",
            "Intelligent Development & Human-Machine Collaboration",
            "Engineering Leadership & System Trade-offs"
        ],
        "aggregate": {
            "total_repos_evaluated": len(results),
            "total_commits": total_commits_all_repos,
            "average_scores": avg_scores
        },
        "failed_repos": failed_repos if failed_repos else None
    }


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
