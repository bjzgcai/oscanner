"""Token management and secret masking utilities."""

import os
from typing import Optional

# Default model for evaluation (can be overridden per-request by query param `model=...`)
DEFAULT_LLM_MODEL = os.getenv("OSCANNER_LLM_MODEL", "Pro/zai-org/GLM-4.7")


def get_github_token() -> Optional[str]:
    """Read from process env at call time so dashboard updates take effect without restart."""
    return os.getenv("GITHUB_TOKEN")


def get_gitee_token() -> Optional[str]:
    """Read from process env at call time so dashboard updates take effect without restart."""
    return os.getenv("GITEE_TOKEN")


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


def mask_secret(value: Optional[str]) -> str:
    """Mask secrets in logs (show first 4 + last 4 chars)."""
    s = (value or "").strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:4]}...{s[-4:]}"
