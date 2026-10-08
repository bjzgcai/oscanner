"""
GitHub request helpers with fallback-token rotation.

GitHub API access is authenticated with ``GITHUB_TOKEN``. When that token runs
out of quota the API responds with ``403``/``429`` and ``x-ratelimit-remaining:
0`` (primary limit) or a secondary-rate-limit message. These helpers retry such
requests with the next configured token (``GITHUB_TOKEN2``, ``GITHUB_TOKEN3``,
...) before falling back to waiting for the rate-limit window to reset.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx

from evaluator.config.tokens import get_github_tokens

GITHUB_RATE_LIMIT_STATUSES = frozenset({403, 429})
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_WAIT_SECONDS = 120.0


def github_auth_header(token: Optional[str]) -> Dict[str, str]:
    """Build the Authorization header for a GitHub token (empty when unset)."""
    value = (token or "").strip()
    return {"Authorization": f"Bearer {value}"} if value else {}


def github_token_candidates(primary: Optional[str] = None) -> List[str]:
    """
    Ordered GitHub tokens: an explicit ``primary`` first, then configured
    fallbacks (``GITHUB_TOKEN``, ``GITHUB_TOKEN2``, ...), de-duplicated.
    """
    tokens: List[str] = []
    primary_value = (primary or "").strip()
    if primary_value:
        tokens.append(primary_value)
    for token in get_github_tokens():
        if token not in tokens:
            tokens.append(token)
    return tokens


def _response_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return ""
    if isinstance(payload, dict):
        return str(payload.get("message") or "")
    return ""


def is_github_rate_limited(response: Optional[httpx.Response]) -> bool:
    """Return True when a response indicates an exhausted or throttled token."""
    if response is None or response.status_code not in GITHUB_RATE_LIMIT_STATUSES:
        return False

    if str(response.headers.get("retry-after") or "").strip():
        return True

    remaining = str(response.headers.get("x-ratelimit-remaining") or "").strip()
    if remaining == "0":
        return True

    message = _response_message(response).lower()
    return "rate limit" in message or "secondary rate" in message or "abuse" in message


def github_rate_limit_wait_seconds(response: Optional[httpx.Response]) -> Optional[float]:
    """
    Seconds to wait before the token that produced ``response`` recovers.

    Returns ``None`` when the response is not a rate-limit response.
    """
    if not is_github_rate_limited(response):
        return None

    assert response is not None  # narrowed by is_github_rate_limited
    retry_after = str(response.headers.get("retry-after") or "").strip()
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass

    reset_at = str(response.headers.get("x-ratelimit-reset") or "").strip()
    try:
        return max(0.0, float(reset_at) - time.time() + 1.0)
    except ValueError:
        return None


def github_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Any = None,
    content: Any = None,
    tokens: Optional[List[str]] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
) -> httpx.Response:
    """
    Perform an authenticated GitHub request, rotating tokens when rate limited.

    ``headers`` should hold caller-supplied headers (Accept, API version, ...);
    the Authorization header is added per attempt. Every configured token is
    tried once before waiting for a rate-limit reset window.
    """
    token_list: List[Optional[str]] = list(tokens) if tokens is not None else list(get_github_tokens())
    if not token_list:
        token_list = [None]

    base_headers = dict(headers or {})

    def _send(token: Optional[str]) -> httpx.Response:
        request_headers = dict(base_headers)
        request_headers.update(github_auth_header(token))
        return client.request(
            method,
            url,
            headers=request_headers,
            params=params,
            json=json_body,
            content=content,
        )

    last_response: Optional[httpx.Response] = None

    # First pass: try each token once, rotating on rate-limit responses so a
    # fresh token is used before waiting for a reset window.
    for token in token_list:
        response = _send(token)
        last_response = response
        if response.status_code < 400 or not is_github_rate_limited(response):
            return response

    # All tokens are throttled: wait for the first token's window to reset.
    for _ in range(max(0, max_retries)):
        wait_seconds = github_rate_limit_wait_seconds(last_response)
        if wait_seconds is None or wait_seconds > max_wait_seconds:
            break
        time.sleep(wait_seconds)
        response = _send(token_list[0])
        last_response = response
        if response.status_code < 400 or not is_github_rate_limited(response):
            return response

    assert last_response is not None
    return last_response
