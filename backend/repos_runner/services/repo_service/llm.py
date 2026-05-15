"""
Anthropic/OpenRouter API client helpers.
"""

import os
import contextvars
from typing import Dict, Any, List, Tuple, Optional


OPENROUTER_ANTHROPIC_BASE_URL = "https://openrouter.ai/api"
DEFAULT_OPENROUTER_PRIMARY_MODEL = "anthropic/claude-sonnet-4.6"
DEFAULT_OPENROUTER_FALLBACK_MODEL = "anthropic/claude-sonnet-4.6"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
_TOKEN_USAGE_RECORDS: contextvars.ContextVar[Optional[List[Dict[str, Any]]]] = contextvars.ContextVar(
    "repos_runner_token_usage_records",
    default=None,
)


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_first_nonempty(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()
    return ""


def _split_model_list(raw: str) -> List[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


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


def _build_anthropic_client(api_key: str = "", auth_token: str = ""):
    from anthropic import Anthropic

    api_key = api_key.strip()
    auth_token = auth_token.strip()

    kwargs: Dict[str, Any] = {}
    if auth_token:
        # Anthropic-compatible gateways such as OpenRouter expect auth_token.
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ["ANTHROPIC_AUTH_TOKEN"] = auth_token
        kwargs["auth_token"] = auth_token
    elif api_key:
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
        os.environ["ANTHROPIC_API_KEY"] = api_key
        kwargs["api_key"] = api_key
    else:
        raise ValueError(
            "No Anthropic credential available. Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY."
        )

    base_url = os.getenv("ANTHROPIC_BASE_URL")
    if base_url and base_url.strip():
        kwargs["base_url"] = base_url.strip()
    try:
        return Anthropic(**kwargs)
    except TypeError:
        if "auth_token" not in kwargs:
            raise
        legacy_kwargs = dict(kwargs)
        legacy_kwargs["api_key"] = legacy_kwargs.pop("auth_token")
        return Anthropic(**legacy_kwargs)


def _build_openrouter_client(api_key: str):
    from anthropic import Anthropic

    openrouter_base_url = (
        _env_first_nonempty("OPEN_ROUTER_BASE_URL", "OPENROUTER_BASE_URL")
        or OPENROUTER_ANTHROPIC_BASE_URL
    )
    # The Anthropic SDK still consults process env while preparing auth headers.
    # When this service is pointed at OpenRouter, a stale ANTHROPIC_API_KEY from
    # the parent shell can silently constrain requests to Anthropic providers.
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["ANTHROPIC_AUTH_TOKEN"] = api_key
    # Important: use auth_token for OpenRouter's Anthropic-compatible endpoint.
    # Using api_key here can implicitly constrain routing to Anthropic providers only.
    try:
        return Anthropic(auth_token=api_key, base_url=openrouter_base_url)
    except TypeError:
        # Backward compatibility for older SDKs.
        return Anthropic(api_key=api_key, base_url=openrouter_base_url)


def _append_anthropic_clients(
    clients: List[Tuple[str, Any]],
    auth_token: str,
    api_key: str,
) -> None:
    if auth_token:
        clients.append(
            ("ANTHROPIC_AUTH_TOKEN", _build_anthropic_client(auth_token=auth_token))
        )
    if api_key and api_key != auth_token:
        clients.append(("ANTHROPIC_API_KEY", _build_anthropic_client(api_key=api_key)))


def _normalize_anthropic_model_name(model: str) -> str:
    value = (model or "").strip()
    if not value:
        return DEFAULT_ANTHROPIC_MODEL
    if value == "anthropic/claude-sonnet-4.6":
        return DEFAULT_ANTHROPIC_MODEL
    if value == "claude-sonnet-4.6":
        return DEFAULT_ANTHROPIC_MODEL
    if value.startswith("anthropic/"):
        return value.split("/", 1)[1]
    # Direct Anthropic provider fallback cannot serve non-Anthropic names
    # like "openai/..." or "qwen/...". Fall back to a Claude default.
    if "/" in value:
        return DEFAULT_ANTHROPIC_MODEL
    return value


def _openrouter_model_chain(requested_model: str) -> List[str]:
    explicit_primary = _env_first_nonempty(
        "OPEN_ROUTER_PRIMARY_MODEL",
        "OPENROUTER_PRIMARY_MODEL",
    )
    primary = explicit_primary or DEFAULT_OPENROUTER_PRIMARY_MODEL
    fallback_raw = _env_first_nonempty(
        "OPEN_ROUTER_FALLBACK_MODEL",
        "OPENROUTER_FALLBACK_MODEL",
    ) or DEFAULT_OPENROUTER_FALLBACK_MODEL
    extra_fallbacks_raw = _env_first_nonempty(
        "OPEN_ROUTER_FALLBACK_MODELS",
        "OPENROUTER_FALLBACK_MODELS",
        "OSCANNER_LLM_FALLBACK_MODELS",
    )

    fallback_models = _split_model_list(fallback_raw)
    if not fallback_models:
        fallback_models = [DEFAULT_OPENROUTER_FALLBACK_MODEL]
    extra_fallbacks = _split_model_list(extra_fallbacks_raw)

    requested = (requested_model or "").strip()
    defaults = {
        "",
        "claude-sonnet-4-6",
        "claude-sonnet-4.6",
        "anthropic/claude-sonnet-4.6",
    }

    models: List[str] = []
    if explicit_primary:
        if primary:
            models.append(primary)
        if requested and requested not in defaults and requested not in models:
            models.append(requested)
    else:
        if requested and requested not in defaults:
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
      1) OPEN_ROUTER_PRIMARY_MODEL (default anthropic/claude-sonnet-4.6)
      2) OPEN_ROUTER_FALLBACK_MODEL / OPEN_ROUTER_FALLBACK_MODELS
      (env-overridable via OPEN_ROUTER_PRIMARY_MODEL / OPEN_ROUTER_FALLBACK_MODEL)
    """
    if provider_name == "OPEN_ROUTER_KEY":
        return _openrouter_model_chain(requested_model)
    return [_normalize_anthropic_model_name(requested_model)]


def _get_api_clients() -> List[Tuple[str, Any]]:
    """
    Return provider clients in priority order.

    Priority:
    1) OPEN_ROUTER_KEY
    2) ANTHROPIC_AUTH_TOKEN
    3) ANTHROPIC_API_KEY

    To allow direct Anthropic-compatible fallback when OpenRouter is configured, set:
    OPEN_ROUTER_FALLBACK_TO_ANTHROPIC=true
    """
    openrouter_key = _env_first_nonempty(
        "OPEN_ROUTER_KEY",
        "OPENROUTER_API_KEY",
        "OPENROUTER_KEY",
    )
    anthropic_auth_token = _env_first_nonempty("ANTHROPIC_AUTH_TOKEN")
    anthropic_key = _env_first_nonempty("ANTHROPIC_API_KEY")

    clients: List[Tuple[str, Any]] = []

    if openrouter_key:
        clients.append(("OPEN_ROUTER_KEY", _build_openrouter_client(openrouter_key)))
        allow_anthropic_fallback = _is_truthy(
            _env_first_nonempty("OPEN_ROUTER_FALLBACK_TO_ANTHROPIC")
        )
        if allow_anthropic_fallback:
            _append_anthropic_clients(clients, anthropic_auth_token, anthropic_key)
        return clients

    _append_anthropic_clients(clients, anthropic_auth_token, anthropic_key)

    return clients


def _get_api_client(use_fallback: bool = False):
    """Return a configured Anthropic client.

    Default priority is OPEN_ROUTER_KEY first.
    If OPEN_ROUTER_KEY is set, direct Anthropic-compatible credentials are only used when
    OPEN_ROUTER_FALLBACK_TO_ANTHROPIC=true.
    """
    if use_fallback:
        anthropic_auth_token = _env_first_nonempty("ANTHROPIC_AUTH_TOKEN")
        anthropic_key = _env_first_nonempty("ANTHROPIC_API_KEY")
        if anthropic_auth_token:
            return _build_anthropic_client(auth_token=anthropic_auth_token)
        if anthropic_key:
            return _build_anthropic_client(api_key=anthropic_key)
        raise ValueError(
            "No fallback API credential available. Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY."
        )

    clients = _get_api_clients()
    if not clients:
        raise ValueError(
            "No API credential available. Set OPEN_ROUTER_KEY (primary), "
            "ANTHROPIC_AUTH_TOKEN, or ANTHROPIC_API_KEY."
        )
    return clients[0][1]


def _messages_create_with_fallback(**kwargs):
    """
    Create a messages response using provider priority.

    OPEN_ROUTER_KEY is tried first when available.
    ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY are only attempted as fallback if enabled via
    OPEN_ROUTER_FALLBACK_TO_ANTHROPIC=true.
    """
    clients = _get_api_clients()
    if not clients:
        raise ValueError(
            "No API credential available. Set OPEN_ROUTER_KEY (primary), "
            "ANTHROPIC_AUTH_TOKEN, or ANTHROPIC_API_KEY."
        )

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
