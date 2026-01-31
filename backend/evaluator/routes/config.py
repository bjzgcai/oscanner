"""LLM configuration routes."""

import os
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from evaluator.config import (
    get_llm_api_key,
    get_user_env_path,
    parse_env_file,
    write_env_file,
    apply_env_to_process,
    mask_secret,
    DEFAULT_LLM_MODEL,
    get_github_token,
    get_gitee_token,
)
from evaluator.utils import parse_repo_url

router = APIRouter()


@router.get("/api/config/llm")
async def get_llm_config():
    """
    Read current LLM config from user dotfile + process env (masked).
    """
    path = get_user_env_path()
    file_env = parse_env_file(path) if path.exists() else {}
    api_key = get_llm_api_key()
    cfg = {
        "configured": bool(api_key),
        "path": str(path),
        "mode": "openrouter" if (file_env.get("OPEN_ROUTER_KEY") or os.getenv("OPEN_ROUTER_KEY")) else "openai",
        "openrouter_key_masked": mask_secret(file_env.get("OPEN_ROUTER_KEY") or os.getenv("OPEN_ROUTER_KEY")),
        "oscanner_llm_api_key_masked": mask_secret(file_env.get("OSCANNER_LLM_API_KEY") or os.getenv("OSCANNER_LLM_API_KEY")),
        "gitee_token_masked": mask_secret(file_env.get("GITEE_TOKEN") or os.getenv("GITEE_TOKEN")),
        "github_token_masked": mask_secret(file_env.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")),
        "oscanner_llm_base_url": file_env.get("OSCANNER_LLM_BASE_URL") or os.getenv("OSCANNER_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "",
        "oscanner_llm_chat_completions_url": file_env.get("OSCANNER_LLM_CHAT_COMPLETIONS_URL") or os.getenv("OSCANNER_LLM_CHAT_COMPLETIONS_URL") or "",
        "oscanner_llm_model": file_env.get("OSCANNER_LLM_MODEL") or os.getenv("OSCANNER_LLM_MODEL") or DEFAULT_LLM_MODEL,
        "oscanner_llm_fallback_models": file_env.get("OSCANNER_LLM_FALLBACK_MODELS") or os.getenv("OSCANNER_LLM_FALLBACK_MODELS") or "",
    }
    return cfg


@router.post("/api/config/llm")
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
    env = parse_env_file(path) if path.exists() else {}

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

    write_env_file(path, env)
    # Load into current process env
    load_dotenv(str(path), override=True)
    apply_env_to_process(env)

    return {"success": True, "path": str(path), "configured": bool(get_llm_api_key())}


@router.get("/api/llm/status")
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


@router.post("/api/config/check-platform-tokens")
async def check_platform_tokens(payload: Dict[str, Any]):
    """
    Check if required platform tokens are configured for given repository URLs.
    
    Request body:
    {
        "repo_urls": ["https://github.com/owner/repo", "https://gitee.com/owner/repo"]
    }
    
    Returns:
    {
        "all_configured": bool,
        "missing_tokens": {
            "github": bool,
            "gitee": bool
        },
        "repo_requirements": [
            {
                "repo_url": str,
                "platform": str,
                "token_configured": bool,
                "token_required": bool
            }
        ]
    }
    """
    repo_urls = payload.get("repo_urls", [])
    if not isinstance(repo_urls, list) or len(repo_urls) == 0:
        raise HTTPException(status_code=400, detail="repo_urls must be a non-empty list")
    
    github_token = get_github_token()
    gitee_token = get_gitee_token()
    
    repo_requirements = []
    missing_platforms = set()
    
    for repo_url in repo_urls:
        parsed = parse_repo_url(repo_url)
        if not parsed:
            repo_requirements.append({
                "repo_url": repo_url,
                "platform": "unknown",
                "token_configured": False,
                "token_required": True,
                "error": "Invalid repository URL format"
            })
            continue
        
        platform, owner, repo = parsed
        token_configured = False
        token_required = True
        
        if platform == "github":
            token_configured = bool(github_token)
            if not token_configured:
                missing_platforms.add("github")
        elif platform == "gitee":
            token_configured = bool(gitee_token)
            if not token_configured:
                missing_platforms.add("gitee")
        
        repo_requirements.append({
            "repo_url": repo_url,
            "platform": platform,
            "token_configured": token_configured,
            "token_required": token_required
        })
    
    all_configured = len(missing_platforms) == 0
    
    return {
        "all_configured": all_configured,
        "missing_tokens": {
            "github": "github" in missing_platforms,
            "gitee": "gitee" in missing_platforms
        },
        "repo_requirements": repo_requirements
    }
