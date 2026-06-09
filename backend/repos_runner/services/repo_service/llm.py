"""
OpenRouter API client helpers.
"""

import os
import contextvars
import json
import urllib.error
import urllib.request
from types import SimpleNamespace
from typing import Dict, Any, List, Tuple, Optional


DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api"
DEFAULT_OPENROUTER_PRIMARY_MODEL = "deepseek/deepseek-v4-pro"
DEFAULT_OPENROUTER_FALLBACK_MODEL = "z-ai/glm-5.1"
_TOKEN_USAGE_RECORDS: contextvars.ContextVar[Optional[List[Dict[str, Any]]]] = contextvars.ContextVar(
    "repos_runner_token_usage_records",
    default=None,
)


def _env_first_nonempty(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()
    return ""


def _split_model_list(raw: str) -> List[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _openrouter_api_model_name(model: str) -> str:
    value = (model or "").strip()
    if value.startswith("openrouter/"):
        return value.split("/", 1)[1]
    return value


def _token_count(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value >= 0:
        return int(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if text.isdigit():
            return int(text)
    return None


def _first_token_count(*values: Any) -> Optional[int]:
    for value in values:
        count = _token_count(value)
        if count is not None:
            return count
    return None


def _usage_get(usage: Any, key: str) -> Any:
    if isinstance(usage, dict):
        return usage.get(key)
    return getattr(usage, key, None)


def _estimate_token_count(text: Any) -> Optional[int]:
    value = str(text or "").strip()
    if not value:
        return None
    return max(1, (len(value) + 3) // 4)


def _message_parts_to_text(messages: Any) -> str:
    parts: List[str] = []

    def _push(value: Any) -> None:
        if isinstance(value, str):
            if value.strip():
                parts.append(value.strip())
            return
        if isinstance(value, list):
            for item in value:
                _push(item)
            return
        if isinstance(value, dict):
            _push(value.get("content"))
            _push(value.get("text"))

    _push(messages)
    return "\n\n".join(parts)


def normalize_token_usage(usage: Any, source: str = "provider") -> Optional[Dict[str, Any]]:
    nested = _usage_get(usage, "usage")
    if nested is not None:
        normalized = normalize_token_usage(nested, source=source)
        if normalized:
            return normalized

    input_tokens = _first_token_count(
        _usage_get(usage, "input_tokens"),
        _usage_get(usage, "inputTokens"),
        _usage_get(usage, "prompt_tokens"),
        _usage_get(usage, "promptTokens"),
    )
    output_tokens = _first_token_count(
        _usage_get(usage, "output_tokens"),
        _usage_get(usage, "outputTokens"),
        _usage_get(usage, "completion_tokens"),
        _usage_get(usage, "completionTokens"),
    )
    total_tokens = _first_token_count(
        _usage_get(usage, "total_tokens"),
        _usage_get(usage, "totalTokens"),
    )

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    if input_tokens is None and total_tokens is not None and output_tokens is not None:
        input_tokens = max(total_tokens - output_tokens, 0)
    if output_tokens is None and total_tokens is not None and input_tokens is not None:
        output_tokens = max(total_tokens - input_tokens, 0)

    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "source": "provider" if source == "provider" else "estimated",
    }


def start_token_usage_collection() -> contextvars.Token:
    return _TOKEN_USAGE_RECORDS.set([])


def reset_token_usage_collection(token: contextvars.Token) -> None:
    _TOKEN_USAGE_RECORDS.reset(token)


def record_token_usage(usage: Any, source: str = "provider") -> bool:
    normalized = normalize_token_usage(usage, source=source)
    records = _TOKEN_USAGE_RECORDS.get()
    if not normalized or records is None:
        return False
    records.append(normalized)
    return True


def record_estimated_token_usage(prompt: Any, content: Any) -> bool:
    input_tokens = _estimate_token_count(_message_parts_to_text(prompt))
    output_tokens = _estimate_token_count(content)
    if input_tokens is None and output_tokens is None:
        return False
    return record_token_usage(
        {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": (input_tokens or 0) + (output_tokens or 0),
        },
        source="estimated",
    )


def record_llm_response_usage(response: Any, messages: Any = None, content: Any = None) -> bool:
    if record_token_usage(response, source="provider"):
        return True
    if messages is not None or content is not None:
        return record_estimated_token_usage(messages, content)
    return False


def summarize_token_usage() -> Optional[Dict[str, Any]]:
    records = _TOKEN_USAGE_RECORDS.get()
    if not records:
        return None

    summary: Dict[str, Any] = {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "source": "provider" if all(record.get("source") == "provider" for record in records) else "estimated",
    }

    for field in ("input_tokens", "output_tokens", "total_tokens"):
        values = [
            record.get(field)
            for record in records
            if isinstance(record.get(field), int)
        ]
        if values:
            summary[field] = sum(values)

    if summary["total_tokens"] is None and (
        summary["input_tokens"] is not None or summary["output_tokens"] is not None
    ):
        summary["total_tokens"] = (summary["input_tokens"] or 0) + (summary["output_tokens"] or 0)

    return summary


def _default_requested_model() -> str:
    """
    Optional requested model override for repos_runner tasks.

    Priority:
    1) REPOS_RUNNER_LLM_MODEL
    2) OSCANNER_LLM_MODEL
    """
    return _env_first_nonempty("REPOS_RUNNER_LLM_MODEL", "OSCANNER_LLM_MODEL")


def _message_text_content(message: Any) -> str:
    """
    Extract concatenated text from a Messages API response.

    Some providers return mixed content blocks such as ThinkingBlock alongside
    text blocks. Only text-bearing blocks should be consumed by downstream JSON
    parsers.
    """
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: List[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text:
            parts.append(text)
            continue
        if isinstance(block, dict):
            block_text = block.get("text")
            if isinstance(block_text, str) and block_text:
                parts.append(block_text)

    return "\n".join(parts).strip()


def _message_has_text_content(message: Any) -> bool:
    """Return True when the response contains at least one usable text block."""
    return bool(_message_text_content(message))


def _to_namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(
            **{key: _to_namespace(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return [_to_namespace(item) for item in value]
    return value


def _openrouter_chat_url(base_url: str) -> str:
    base = (base_url or DEFAULT_OPENROUTER_BASE_URL).strip().rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _openrouter_error_message(error: urllib.error.HTTPError) -> str:
    try:
        body = error.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    if not body:
        return f"HTTP {error.code}"
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return f"HTTP {error.code}: {body[:500]}"
    detail = data.get("error") if isinstance(data, dict) else None
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("code") or detail
    else:
        message = detail or data
    return f"HTTP {error.code}: {message}"


class _OpenRouterStream:
    def __init__(self, response: Any):
        self._response = response
        self.text_stream = [_message_text_content(response)]

    def __enter__(self) -> "_OpenRouterStream":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def get_final_message(self) -> Any:
        return self._response


class _OpenRouterMessages:
    def __init__(self, api_key: str, base_url: str):
        self._api_key = api_key
        self._url = _openrouter_chat_url(base_url)

    def create(self, **kwargs: Any) -> Any:
        body = json.dumps(kwargs).encode("utf-8")
        request = urllib.request.Request(
            self._url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise RuntimeError(_openrouter_error_message(error)) from error
        except urllib.error.URLError as error:
            raise RuntimeError(str(error.reason)) from error

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as error:
            raise RuntimeError("OpenRouter returned invalid JSON") from error
        choice = (data.get("choices") or [{}])[0] if isinstance(data, dict) else {}
        message = choice.get("message") if isinstance(choice, dict) else {}
        content = message.get("content") if isinstance(message, dict) else ""
        usage = _to_namespace(data.get("usage", {})) if isinstance(data, dict) else None
        return SimpleNamespace(
            content=[SimpleNamespace(text=content or "")],
            usage=usage,
            raw=_to_namespace(data),
        )

    def stream(self, **kwargs: Any) -> _OpenRouterStream:
        response = self.create(**kwargs)
        return _OpenRouterStream(response)


class _OpenRouterClient:
    def __init__(self, api_key: str, base_url: str):
        self.messages = _OpenRouterMessages(api_key=api_key, base_url=base_url)


def _build_openrouter_client(api_key: str):
    openrouter_base_url = (
        _env_first_nonempty("OPEN_ROUTER_BASE_URL", "OPENROUTER_BASE_URL")
        or DEFAULT_OPENROUTER_BASE_URL
    )
    return _OpenRouterClient(api_key=api_key.strip(), base_url=openrouter_base_url)


def _openrouter_model_chain(requested_model: str) -> List[str]:
    explicit_primary = _env_first_nonempty(
        "OPEN_ROUTER_PRIMARY_MODEL",
        "OPENROUTER_PRIMARY_MODEL",
    )
    primary = _openrouter_api_model_name(
        explicit_primary or DEFAULT_OPENROUTER_PRIMARY_MODEL
    )
    fallback_raw = _env_first_nonempty(
        "OPEN_ROUTER_FALLBACK_MODEL",
        "OPENROUTER_FALLBACK_MODEL",
    ) or DEFAULT_OPENROUTER_FALLBACK_MODEL
    extra_fallbacks_raw = _env_first_nonempty(
        "OPEN_ROUTER_FALLBACK_MODELS",
        "OPENROUTER_FALLBACK_MODELS",
        "OSCANNER_LLM_FALLBACK_MODELS",
    )

    fallback_models = [
        _openrouter_api_model_name(model)
        for model in _split_model_list(fallback_raw)
    ]
    if not fallback_models:
        fallback_models = [DEFAULT_OPENROUTER_FALLBACK_MODEL]
    extra_fallbacks = [
        _openrouter_api_model_name(model)
        for model in _split_model_list(extra_fallbacks_raw)
    ]

    requested = _openrouter_api_model_name(requested_model)

    models: List[str] = []
    if explicit_primary:
        if primary:
            models.append(primary)
        if requested and requested not in models:
            models.append(requested)
    else:
        if requested:
            models.append(requested)
        if primary and primary not in models:
            models.append(primary)

    for model in [*fallback_models, *extra_fallbacks]:
        if model and model not in models:
            models.append(model)
    return models


def _get_model_candidates(provider_name: str, requested_model: str = "") -> List[str]:
    """
    Return model attempts for a provider.

    OPEN_ROUTER_KEY:
      1) requested model / OPEN_ROUTER_PRIMARY_MODEL (default deepseek/deepseek-v4-pro)
      2) OPEN_ROUTER_FALLBACK_MODEL / OPEN_ROUTER_FALLBACK_MODELS
      (env-overridable via OPEN_ROUTER_PRIMARY_MODEL / OPEN_ROUTER_FALLBACK_MODEL)
    """
    if provider_name == "OPEN_ROUTER_KEY":
        return _openrouter_model_chain(requested_model)
    return []


def _get_api_clients() -> List[Tuple[str, Any]]:
    """
    Return provider clients in priority order.

    Priority:
    1) OPEN_ROUTER_KEY
    """
    openrouter_key = _env_first_nonempty(
        "OPEN_ROUTER_KEY",
        "OPENROUTER_API_KEY",
        "OPENROUTER_KEY",
    )

    clients: List[Tuple[str, Any]] = []

    if openrouter_key:
        clients.append(("OPEN_ROUTER_KEY", _build_openrouter_client(openrouter_key)))

    return clients


def _get_api_client(use_fallback: bool = False):
    """Return a configured OpenRouter client."""

    clients = _get_api_clients()
    if not clients:
        raise ValueError("No API credential available. Set OPEN_ROUTER_KEY.")
    return clients[0][1]


def _messages_create_with_fallback(**kwargs):
    """
    Create a messages response using provider priority.

    OPEN_ROUTER_KEY is tried first when available.
    """
    clients = _get_api_clients()
    if not clients:
        raise ValueError("No API credential available. Set OPEN_ROUTER_KEY.")

    request_kwargs = dict(kwargs)
    requested_model = str(request_kwargs.pop("model", "") or "")
    require_text = bool(request_kwargs.pop("require_text", False))

    attempts: List[Tuple[str, Any, str]] = []
    for provider_name, client in clients:
        for model in _get_model_candidates(provider_name, requested_model):
            attempts.append((provider_name, client, model))

    errors: List[Tuple[str, str, Exception]] = []
    for provider_name, client, model in attempts:
        try:
            response = client.messages.create(model=model, **request_kwargs)
            if require_text and not _message_has_text_content(response):
                raise RuntimeError("Response contained no final text blocks")
            record_llm_response_usage(
                response,
                messages=request_kwargs.get("messages"),
                content=_message_text_content(response),
            )
            return response
        except Exception as error:
            errors.append((provider_name, model, error))

    if len(errors) == 1:
        provider_name, model, error = errors[0]
        raise RuntimeError(f"{provider_name} ({model}) request failed ({error})") from error

    error_summary = "; ".join(
        f"{provider_name} ({model}) failed ({error})"
        for provider_name, model, error in errors
    )
    raise RuntimeError(f"All model attempts failed: {error_summary}") from errors[-1][2]
