"""Resolve the internal-primary / OpenRouter-fallback LLM provider chain."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


DEFAULT_INTERNAL_BASE_URL = "https://llm.inner.bza.edu.cn/hub/v1"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_LLM_FALLBACK_MODEL = "deepseek/deepseek-v4.1-flash-1017"


def _first_nonempty(*keys: str) -> str:
    for key in keys:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def _chat_url(base_url: str) -> str:
    base = (base_url or DEFAULT_INTERNAL_BASE_URL).rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def get_internal_provider_config(model: Optional[str] = None) -> Dict[str, str]:
    base_url = _first_nonempty(
        "OSCANNER_LLM_BASE_URL",
        "INTERNAL_LLM_BASE_URL",
        "OPENAI_BASE_URL",
    ) or DEFAULT_INTERNAL_BASE_URL
    chat_url = _first_nonempty(
        "OSCANNER_LLM_CHAT_COMPLETIONS_URL",
        "INTERNAL_LLM_CHAT_COMPLETIONS_URL",
    ) or _chat_url(base_url)
    return {
        "provider": "internal",
        "api_key": _first_nonempty(
            "OSCANNER_LLM_API_KEY",
            "INTERNAL_LLM_API_KEY",
            "OPENAI_API_KEY",
        ),
        "base_url": base_url,
        "chat_completions_url": chat_url,
        "model": (model or _first_nonempty(
            "OSCANNER_LLM_MODEL",
            "INTERNAL_LLM_QUESTION_MODEL",
        ) or "glm").strip(),
    }


def get_openrouter_provider_config() -> Optional[Dict[str, str]]:
    api_key = _first_nonempty("OPEN_ROUTER_KEY", "OPENROUTER_API_KEY")
    if not api_key:
        return None
    base_url = _first_nonempty(
        "OPEN_ROUTER_BASE_URL",
        "OPENROUTER_BASE_URL",
    ) or DEFAULT_OPENROUTER_BASE_URL
    model = _first_nonempty(
        "OSCANNER_LLM_FALLBACK_MODEL",
    ) or DEFAULT_LLM_FALLBACK_MODEL
    if model.startswith("openrouter/"):
        model = model.split("/", 1)[1]
    return {
        "provider": "openrouter",
        "api_key": api_key,
        "base_url": base_url,
        "chat_completions_url": _chat_url(base_url),
        "model": model,
    }


def get_provider_chain(model: Optional[str] = None) -> List[Dict[str, str]]:
    primary = get_internal_provider_config(model)
    fallback = get_openrouter_provider_config()
    return [
        provider
        for provider in [primary if primary["api_key"] else None, fallback]
        if provider is not None
    ]


def get_plugin_provider_kwargs(model: Optional[str] = None) -> Dict[str, Any]:
    primary = get_internal_provider_config(model)
    if not primary["api_key"]:
        fallback = get_openrouter_provider_config()
        if fallback:
            return {
                "api_base_url": fallback["base_url"],
                "chat_completions_url": fallback["chat_completions_url"],
                "provider_name": "openrouter",
                "provider_fallbacks": [],
            }
    fallbacks = [
        {
            "provider": fallback["provider"],
            "api_key": fallback["api_key"],
            "base_url": fallback["base_url"],
            "chat_completions_url": fallback["chat_completions_url"],
            "model": fallback["model"],
        }
        for fallback in get_provider_chain(model)[1:]
    ]
    return {
        "api_base_url": primary["base_url"],
        "chat_completions_url": primary["chat_completions_url"],
        "provider_name": "internal",
        "provider_fallbacks": fallbacks,
    }
