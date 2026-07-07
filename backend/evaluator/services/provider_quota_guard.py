"""Daily local quota guard for upstream provider API calls."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import requests

from evaluator.paths import get_data_dir

_LOCK = threading.Lock()
_INSTALLED = False
_ORIGINAL_REQUESTS_REQUEST = None
_ORIGINAL_HTTPX_CLIENT_REQUEST = None
_ORIGINAL_HTTPX_ASYNC_CLIENT_REQUEST = None


class ProviderQuotaExceeded(RuntimeError):
    """Raised before an upstream provider request would exceed local budget."""


def _env_int(name: str, default: int = 0, *, minimum: int = 0) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, value)


def _quota_file_path() -> Path:
    configured = os.getenv("OSCANNER_PROVIDER_QUOTA_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()
    return get_data_dir() / "provider_quota_guard.json"


def _today_key() -> str:
    return date.today().isoformat()


def _read_state(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"date": _today_key(), "usage": {}}
    if not isinstance(payload, dict):
        return {"date": _today_key(), "usage": {}}
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    state = {"date": str(payload.get("date") or _today_key()), "usage": usage}
    if state["date"] != _today_key():
        return {"date": _today_key(), "usage": {}}
    return state


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(state, tmp, ensure_ascii=False, sort_keys=True)
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def _budget_for(bucket: str) -> int:
    if bucket == "github_rest":
        return _env_int("OSCANNER_GITHUB_REST_DAILY_BUDGET", 0)
    if bucket == "github_graphql":
        return _env_int("OSCANNER_GITHUB_GRAPHQL_DAILY_POINT_BUDGET", 0)
    if bucket == "gitee":
        return _env_int("OSCANNER_GITEE_DAILY_REQUEST_BUDGET", 0)
    return 0


def _github_graphql_cost(method: str) -> int:
    if method.upper() == "GET":
        return 1
    return _env_int("OSCANNER_GITHUB_GRAPHQL_DEFAULT_QUERY_COST", 1, minimum=1)


def _request_cost(bucket: str, method: str) -> int:
    if bucket == "github_graphql":
        return _github_graphql_cost(method)
    return 1


def _bucket_for_url(url: Any) -> str | None:
    parsed = urlparse(str(url))
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    if host == "api.github.com":
        if path.rstrip("/") == "/graphql":
            return "github_graphql"
        return "github_rest"
    if host == "gitee.com" and path.startswith("/api/v5"):
        return "gitee"
    return None


def _display_name(bucket: str) -> str:
    return {
        "github_rest": "GitHub REST",
        "github_graphql": "GitHub GraphQL",
        "gitee": "Gitee",
    }.get(bucket, bucket)


def reserve_provider_quota(bucket: str, cost: int = 1) -> None:
    budget = _budget_for(bucket)
    if budget <= 0:
        return
    cost = max(1, int(cost))
    today = _today_key()
    path = _quota_file_path()

    with _LOCK:
        state = _read_state(path)
        if state.get("date") != today:
            state = {"date": today, "usage": {}}
        usage = state.setdefault("usage", {})
        used = int(usage.get(bucket) or 0)
        if used + cost > budget:
            raise ProviderQuotaExceeded(
                f"{_display_name(bucket)} 今日平台额度已用完 "
                f"({used}/{budget}, requested {cost})."
            )
        usage[bucket] = used + cost
        _write_state(path, state)


def snapshot_provider_quota() -> dict[str, Any]:
    path = _quota_file_path()
    with _LOCK:
        state = _read_state(path)
    buckets = ("github_rest", "github_graphql", "gitee")
    return {
        "date": state.get("date") or _today_key(),
        "usage": {
            bucket: {
                "used": int((state.get("usage") or {}).get(bucket) or 0),
                "budget": _budget_for(bucket),
            }
            for bucket in buckets
        },
        "file": str(path),
    }


def _guard_request(method: str, url: Any) -> None:
    bucket = _bucket_for_url(url)
    if not bucket:
        return
    reserve_provider_quota(bucket, _request_cost(bucket, method))


def install_provider_quota_guard() -> None:
    global _INSTALLED
    global _ORIGINAL_REQUESTS_REQUEST
    global _ORIGINAL_HTTPX_CLIENT_REQUEST
    global _ORIGINAL_HTTPX_ASYNC_CLIENT_REQUEST

    if _INSTALLED:
        return

    _ORIGINAL_REQUESTS_REQUEST = requests.sessions.Session.request
    _ORIGINAL_HTTPX_CLIENT_REQUEST = httpx.Client.request
    _ORIGINAL_HTTPX_ASYNC_CLIENT_REQUEST = httpx.AsyncClient.request

    def guarded_requests_request(self, method, url, **kwargs):
        _guard_request(str(method), url)
        return _ORIGINAL_REQUESTS_REQUEST(self, method, url, **kwargs)

    def guarded_httpx_client_request(self, method, url, **kwargs):
        _guard_request(str(method), url)
        return _ORIGINAL_HTTPX_CLIENT_REQUEST(self, method, url, **kwargs)

    async def guarded_httpx_async_client_request(self, method, url, **kwargs):
        _guard_request(str(method), url)
        return await _ORIGINAL_HTTPX_ASYNC_CLIENT_REQUEST(self, method, url, **kwargs)

    requests.sessions.Session.request = guarded_requests_request
    httpx.Client.request = guarded_httpx_client_request
    httpx.AsyncClient.request = guarded_httpx_async_client_request
    _INSTALLED = True
