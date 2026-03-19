"""
Anthropic/OpenRouter API client helpers.
"""

import os
from typing import Dict, Any, List, Tuple


OPENROUTER_ANTHROPIC_BASE_URL = "https://openrouter.ai/api"
DEFAULT_OPENROUTER_PRIMARY_MODEL = "anthropic/claude-sonnet-4.5"
DEFAULT_OPENROUTER_FALLBACK_MODEL = "anthropic/claude-sonnet-4.5"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


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


def _default_requested_model() -> str:
    """
    Optional requested model override for repos_runner tasks.

    Priority:
    1) REPOS_RUNNER_LLM_MODEL
    2) OSCANNER_LLM_MODEL
    """
    return _env_first_nonempty("REPOS_RUNNER_LLM_MODEL", "OSCANNER_LLM_MODEL")


def _build_anthropic_client(api_key: str):
    from anthropic import Anthropic

    kwargs: Dict[str, Any] = {"api_key": api_key}
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    if base_url and base_url.strip():
        kwargs["base_url"] = base_url.strip()
    return Anthropic(**kwargs)


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
      1) OPEN_ROUTER_PRIMARY_MODEL (default anthropic/claude-sonnet-4.5)
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
    2) ANTHROPIC_API_KEY

    To allow Anthropic fallback when OpenRouter is configured, set:
    OPEN_ROUTER_FALLBACK_TO_ANTHROPIC=true
    """
    openrouter_key = _env_first_nonempty(
        "OPEN_ROUTER_KEY",
        "OPENROUTER_API_KEY",
        "OPENROUTER_KEY",
    )
    anthropic_key = _env_first_nonempty("ANTHROPIC_API_KEY")

    clients: List[Tuple[str, Any]] = []

    if openrouter_key:
        clients.append(("OPEN_ROUTER_KEY", _build_openrouter_client(openrouter_key)))
        allow_anthropic_fallback = _is_truthy(
            _env_first_nonempty("OPEN_ROUTER_FALLBACK_TO_ANTHROPIC")
        )
        if anthropic_key and allow_anthropic_fallback:
            clients.append(("ANTHROPIC_API_KEY", _build_anthropic_client(anthropic_key)))
        return clients

    if anthropic_key:
        clients.append(("ANTHROPIC_API_KEY", _build_anthropic_client(anthropic_key)))

    return clients


def _get_api_client(use_fallback: bool = False):
    """Return a configured Anthropic client.

    Default priority is OPEN_ROUTER_KEY first.
    If OPEN_ROUTER_KEY is set, ANTHROPIC_API_KEY is only used when
    OPEN_ROUTER_FALLBACK_TO_ANTHROPIC=true.
    """
    if use_fallback:
        anthropic_key = _env_first_nonempty("ANTHROPIC_API_KEY")
        if not anthropic_key:
            raise ValueError("No fallback API key available. Set ANTHROPIC_API_KEY.")
        return _build_anthropic_client(anthropic_key)

    clients = _get_api_clients()
    if not clients:
        raise ValueError(
            "No API key available. Set OPEN_ROUTER_KEY (primary) or ANTHROPIC_API_KEY."
        )
    return clients[0][1]


def _messages_create_with_fallback(**kwargs):
    """
    Create a messages response using provider priority.

    OPEN_ROUTER_KEY is tried first when available.
    ANTHROPIC_API_KEY is only attempted as fallback if enabled via
    OPEN_ROUTER_FALLBACK_TO_ANTHROPIC=true.
    """
    clients = _get_api_clients()
    if not clients:
        raise ValueError(
            "No API key available. Set OPEN_ROUTER_KEY (primary) or ANTHROPIC_API_KEY."
        )

    request_kwargs = dict(kwargs)
    requested_model = str(request_kwargs.pop("model", "") or "")

    attempts: List[Tuple[str, Any, str]] = []
    for provider_name, client in clients:
        for model in _get_model_candidates(provider_name, requested_model):
            attempts.append((provider_name, client, model))

    errors: List[Tuple[str, str, Exception]] = []
    for provider_name, client, model in attempts:
        try:
            return client.messages.create(model=model, **request_kwargs)
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
