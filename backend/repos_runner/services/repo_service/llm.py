"""
Anthropic/OpenRouter API client helpers.
"""

import os
from typing import Dict, Any


OPENROUTER_ANTHROPIC_BASE_URL = "https://openrouter.ai/api"


def _get_api_client(use_fallback: bool = False):
    """Return a configured Anthropic client.

    Primary: OPEN_ROUTER_KEY via OpenRouter
    Fallback: ANTHROPIC_API_KEY (+ optional ANTHROPIC_BASE_URL)
    """
    from anthropic import Anthropic

    if not use_fallback:
        openrouter_key = os.getenv("OPEN_ROUTER_KEY")
        if openrouter_key:
            openrouter_base_url = (
                os.getenv("OPEN_ROUTER_BASE_URL")
                or os.getenv("OPENROUTER_BASE_URL")
                or OPENROUTER_ANTHROPIC_BASE_URL
            )
            return Anthropic(api_key=openrouter_key, base_url=openrouter_base_url)

    # Fallback: ANTHROPIC_API_KEY + optional ANTHROPIC_BASE_URL
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "No API key available. Set OPEN_ROUTER_KEY (primary) or ANTHROPIC_API_KEY (fallback)"
        )

    kwargs: Dict[str, Any] = {"api_key": api_key}
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return Anthropic(**kwargs)


def _messages_create_with_fallback(**kwargs):
    """
    Create a messages response, trying OpenRouter first, then ANTHROPIC_API_KEY fallback.
    """
    client = _get_api_client()
    try:
        return client.messages.create(**kwargs)
    except Exception as primary_error:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise
        try:
            return _get_api_client(use_fallback=True).messages.create(**kwargs)
        except Exception as fallback_error:
            raise RuntimeError(
                f"Primary LLM request failed ({primary_error}); "
                f"ANTHROPIC_API_KEY fallback also failed ({fallback_error})"
            ) from fallback_error
