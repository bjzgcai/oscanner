import importlib.util
import json
from pathlib import Path

import httpx
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_plugin():
    path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_llm_provider_fallback", path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)
    return plugin


def _evaluator(plugin, events=None, **kwargs):
    return plugin.create_commit_evaluator(
        data_dir="",
        api_key="internal-key",
        model="glm",
        api_base_url="https://internal.example/v1",
        chat_completions_url="https://internal.example/v1/chat/completions",
        provider_fallbacks=[{
            "provider": "openrouter",
            "model": "deepseek/deepseek-v4.1-flash-1017",
            "api_key": "openrouter-key",
            "base_url": "https://openrouter.example/api/v1",
            "chat_completions_url": "https://openrouter.example/api/v1/chat/completions",
        }],
        progress_callback=(lambda event, data: events.append((event, data))) if events is not None else None,
        max_input_tokens=100_000,
        **kwargs,
    )


class _JsonResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _StreamResponse:
    def __init__(self, status_code=200, content="", text="", fail_after=None):
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300
        self.content = content
        self.text = text
        self.fail_after = fail_after

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.text.encode()

    def iter_lines(self):
        if self.fail_after is not None:
            yield "data: " + json.dumps({"choices": [{"delta": {"content": self.fail_after}}]})
            raise httpx.ReadError(
                "connection reset",
                request=httpx.Request("POST", "https://internal.example"),
            )
        if self.content:
            yield "data: " + json.dumps({"choices": [{"delta": {"content": self.content}}]})
        yield "data: [DONE]"


def _success(content):
    return _JsonResponse(200, {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
    })


def _parse_json(text):
    return json.loads(text)


def test_provider_chain_defaults_to_internal_glm_then_openrouter(monkeypatch):
    plugin = _load_plugin()
    for key in (
        "OSCANNER_LLM_API_KEY",
        "INTERNAL_LLM_API_KEY",
        "OPENAI_API_KEY",
        "OPEN_ROUTER_KEY",
        "OPENROUTER_API_KEY",
        "OSCANNER_LLM_FALLBACK_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OSCANNER_LLM_API_KEY", "internal-key")
    monkeypatch.setenv("OPEN_ROUTER_KEY", "openrouter-key")

    evaluator = plugin.create_commit_evaluator(data_dir="", api_key="internal-key", model="glm")
    attempts = evaluator._provider_attempts()

    assert [(row.provider, row.model) for row in attempts] == [
        ("internal", "glm"),
        ("openrouter", "deepseek/deepseek-v4.1-flash-1017"),
    ]


@pytest.mark.parametrize(
    "failure",
    [
        _JsonResponse(429, text="rate limited"),
        _JsonResponse(500, text="upstream error"),
    ],
)
def test_runtime_http_failures_fall_back_to_openrouter(monkeypatch, failure):
    plugin = _load_plugin()
    evaluator = _evaluator(plugin)
    calls = []

    def fake_stream(_method, url, **_kwargs):
        calls.append(url)
        if "internal.example" in url:
            return _StreamResponse(
                status_code=failure.status_code,
                text=failure.text,
            )
        return _StreamResponse(content='{"ok": true}')

    monkeypatch.setattr(evaluator._http_client, "stream", fake_stream)

    result = evaluator._chat_json_with_fallback(
        prompt="test",
        parse=_parse_json,
        label="test",
        emit_tokens=False,
    )

    assert result == {"ok": True}
    assert calls == [
        "https://internal.example/v1/chat/completions",
        "https://openrouter.example/api/v1/chat/completions",
    ]
    provenance = evaluator._summarize_llm_provenance()
    assert provenance["fallback_used"] is True
    assert provenance["attempts"][0]["reason"] in {"rate_limit", "server_error"}


def test_timeout_falls_back_to_openrouter(monkeypatch):
    plugin = _load_plugin()
    evaluator = _evaluator(plugin)
    calls = []

    def fake_stream(_method, url, **_kwargs):
        calls.append(url)
        if "internal.example" in url:
            raise httpx.ReadTimeout("timed out", request=httpx.Request("POST", url))
        return _StreamResponse(content='{"ok": true}')

    monkeypatch.setattr(evaluator._http_client, "stream", fake_stream)

    assert evaluator._chat_json_with_fallback(
        prompt="test",
        parse=_parse_json,
        label="test",
        emit_tokens=False,
    ) == {"ok": True}
    assert len(calls) == 2
    assert evaluator._summarize_llm_provenance()["attempts"][0]["reason"] == "timeout"


def test_authentication_error_does_not_fall_back(monkeypatch):
    plugin = _load_plugin()
    evaluator = _evaluator(plugin)
    calls = []

    def fake_stream(_method, url, **_kwargs):
        calls.append(url)
        return _StreamResponse(status_code=401, text="unauthorized")

    monkeypatch.setattr(evaluator._http_client, "stream", fake_stream)

    with pytest.raises(plugin.LLMRequestError, match="HTTP 401"):
        evaluator._chat_json_with_fallback(
            prompt="test",
            parse=_parse_json,
            label="test",
            emit_tokens=False,
        )
    assert calls == ["https://internal.example/v1/chat/completions"]


def test_invalid_json_is_corrected_once_on_same_provider(monkeypatch):
    plugin = _load_plugin()
    evaluator = _evaluator(plugin)
    calls = []

    def fake_stream(_method, url, **kwargs):
        calls.append((url, kwargs["json"]["messages"]))
        if len(calls) == 1:
            return _StreamResponse(content="not json")
        return _StreamResponse(content='{"ok": true}')

    monkeypatch.setattr(evaluator._http_client, "stream", fake_stream)

    assert evaluator._chat_json_with_fallback(
        prompt="test",
        parse=_parse_json,
        label="test",
        emit_tokens=False,
    ) == {"ok": True}
    assert len(calls) == 2
    assert all("internal.example" in url for url, _messages in calls)
    assert "correct JSON" in calls[1][1][0]["content"] or "JSON" in calls[1][1][0]["content"]


def test_invalid_json_twice_switches_to_openrouter(monkeypatch):
    plugin = _load_plugin()
    evaluator = _evaluator(plugin)
    calls = []

    def fake_stream(_method, url, **_kwargs):
        calls.append(url)
        if "internal.example" in url:
            return _StreamResponse(content="not json")
        return _StreamResponse(content='{"ok": true}')

    monkeypatch.setattr(evaluator._http_client, "stream", fake_stream)

    assert evaluator._chat_json_with_fallback(
        prompt="test",
        parse=_parse_json,
        label="test",
        emit_tokens=False,
    ) == {"ok": True}
    assert calls == [
        "https://internal.example/v1/chat/completions",
        "https://internal.example/v1/chat/completions",
        "https://openrouter.example/api/v1/chat/completions",
    ]
    reasons = [row.get("reason") for row in evaluator._summarize_llm_provenance()["attempts"]]
    assert "invalid_output" in reasons


def test_partial_stream_failure_emits_reset_before_openrouter_retry(monkeypatch):
    plugin = _load_plugin()
    events = []
    evaluator = _evaluator(plugin, events=events)
    calls = []

    class _Stream:
        def __init__(self, url):
            self.url = url
            self.is_success = True

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def iter_lines(self):
            if "internal.example" in self.url:
                yield "data: " + json.dumps({"choices": [{"delta": {"content": "partial"}}]})
                raise httpx.ReadError(
                    "connection reset",
                    request=httpx.Request("POST", self.url),
                )
            yield "data: " + json.dumps({"choices": [{"delta": {"content": '{"ok": true}'}}]})
            yield "data: [DONE]"

    def fake_stream(_method, url, **_kwargs):
        calls.append(url)
        return _Stream(url)

    monkeypatch.setattr(evaluator._http_client, "stream", fake_stream)

    result = evaluator._chat_json_with_fallback(
        prompt="test",
        parse=_parse_json,
        label="test",
        emit_tokens=True,
    )

    assert result == {"ok": True}
    token_text = "".join(data["content"] for event, data in events if event == "token")
    assert token_text == "partial" + '{"ok": true}'
    reset_events = [data for event, data in events if event == "reset_stream"]
    assert reset_events == [{
        "reset_stream": True,
        "from_provider": "internal",
        "from_model": "glm",
        "to_provider": "openrouter",
        "to_model": "deepseek/deepseek-v4.1-flash-1017",
        "reason": "transport",
    }]
    assert len(calls) == 2
