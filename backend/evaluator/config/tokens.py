"""Token management and secret masking utilities."""

import os
from typing import List, Optional

# Ordered list of GitHub token env keys. The first configured token is the
# primary; the rest act as automatic fallbacks when an earlier token exhausts
# its API rate limit (e.g. GITHUB_TOKEN2 when GITHUB_TOKEN is out of quota).
GITHUB_TOKEN_ENV_KEYS = (
    "GITHUB_TOKEN",
    "GITHUB_TOKEN2",
    "GITHUB_TOKEN3",
    "GITHUB_TOKEN4",
    "GITHUB_TOKEN5",
)

# Default model for evaluation (can be overridden per-request by query param `model=...`)
DEFAULT_LLM_MODEL = os.getenv("INTERNAL_LLM_QUESTION_MODEL") or os.getenv("OSCANNER_LLM_MODEL", "deepseek/deepseek-v4-pro")


def get_github_token() -> Optional[str]:
    """Read from process env at call time so dashboard updates take effect without restart."""
    return os.getenv("GITHUB_TOKEN")


def get_github_tokens() -> List[str]:
    """
    Return configured GitHub tokens in fallback priority order.

    Reads ``GITHUB_TOKEN`` first, then ``GITHUB_TOKEN2``..``GITHUB_TOKEN5``,
    skipping empty entries and duplicates. Read at call time so environment
    changes take effect without a restart.
    """
    tokens: List[str] = []
    for key in GITHUB_TOKEN_ENV_KEYS:
        value = (os.getenv(key) or "").strip()
        if value and value not in tokens:
            tokens.append(value)
    return tokens


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
        os.getenv("INTERNAL_LLM_API_KEY")
        or os.getenv("OSCANNER_LLM_API_KEY")
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
