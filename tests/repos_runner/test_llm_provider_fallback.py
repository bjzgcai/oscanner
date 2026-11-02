import json
from types import SimpleNamespace

import pytest

from repos_runner.services.repo_service import llm


class _Client:
    def __init__(self, name, responses):
        self.name = name
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(content=[{"text": response}], usage=None)


def _json_validator(text):
    data = json.loads(text)
    if not isinstance(data, dict) or "ok" not in data:
        raise ValueError("missing ok")
    return data


def _install_clients(monkeypatch, internal, openrouter):
    monkeypatch.setattr(
        llm,
        "_get_api_clients",
        lambda: [("INTERNAL_LLM_KEY", internal), ("OPEN_ROUTER_KEY", openrouter)],
    )
    monkeypatch.delenv("OSCANNER_LLM_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("OPEN_ROUTER_FALLBACK_MODELS", raising=False)
    monkeypatch.delenv("OPENROUTER_FALLBACK_MODELS", raising=False)


def test_runner_transport_uses_internal_glm_then_openrouter(monkeypatch):
    internal = _Client("internal", [
        llm.LLMRequestFailure("rate limited", reason="rate_limit", retryable=True, status_code=429)
    ])
    openrouter = _Client("openrouter", ['{"ok": true}'])
    _install_clients(monkeypatch, internal, openrouter)

    result = llm._messages_create_with_fallback(
        model="glm",
        messages=[{"role": "user", "content": "test"}],
        require_text=True,
        validate_text=_json_validator,
    )

    assert getattr(result, "_oscanner_validated") == {"ok": True}
    assert internal.calls[0]["model"] == "glm"
    assert openrouter.calls[0]["model"] == "deepseek/deepseek-v4.1-flash-1017"
    assert getattr(result, "_oscanner_provider") == "OPEN_ROUTER_KEY"
    assert getattr(result, "_oscanner_attempts")[0]["reason"] == "rate_limit"


def test_runner_transport_does_not_fallback_on_auth_error(monkeypatch):
    internal = _Client("internal", [
        llm.LLMRequestFailure(
            "HTTP 401 unauthorized",
            reason="auth_or_configuration",
            retryable=False,
            status_code=401,
        )
    ])
    openrouter = _Client("openrouter", ['{"ok": true}'])
    _install_clients(monkeypatch, internal, openrouter)

    with pytest.raises(RuntimeError, match="HTTP 401"):
        llm._messages_create_with_fallback(
            model="glm",
            messages=[{"role": "user", "content": "test"}],
            require_text=True,
        )

    assert openrouter.calls == []


def test_runner_transport_corrects_invalid_json_once_on_same_provider(monkeypatch):
    internal = _Client("internal", ["not json", '{"ok": true}'])
    openrouter = _Client("openrouter", ['{"ok": true}'])
    _install_clients(monkeypatch, internal, openrouter)

    result = llm._messages_create_with_fallback(
        model="glm",
        messages=[{"role": "user", "content": "test"}],
        require_text=True,
        validate_text=_json_validator,
    )

    assert getattr(result, "_oscanner_validated") == {"ok": True}
    assert len(internal.calls) == 2
    assert openrouter.calls == []
    correction_messages = internal.calls[1]["messages"]
    assert "corrected JSON" in correction_messages[-1]["content"]


def test_runner_transport_empty_response_falls_back(monkeypatch):
    internal = _Client("internal", [""])
    openrouter = _Client("openrouter", ['{"ok": true}'])
    _install_clients(monkeypatch, internal, openrouter)

    result = llm._messages_create_with_fallback(
        model="glm",
        messages=[{"role": "user", "content": "test"}],
        require_text=True,
        validate_text=_json_validator,
    )

    assert getattr(result, "_oscanner_validated") == {"ok": True}
    assert getattr(result, "_oscanner_attempts")[0]["reason"] == "empty_response"
