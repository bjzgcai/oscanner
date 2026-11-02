from pathlib import Path

import pytest

from evaluator.routes import config as config_route


@pytest.mark.anyio
async def test_llm_config_reports_internal_gateway_mode_when_both_keys_exist(monkeypatch):
    monkeypatch.setenv("OSCANNER_LLM_API_KEY", "internal-test-key")
    monkeypatch.setenv("OPEN_ROUTER_KEY", "openrouter-test-key")
    monkeypatch.setattr(config_route, "get_user_env_path", lambda: Path("/nonexistent"))

    config = await config_route.get_llm_config()

    assert config["configured"] is True
    assert config["mode"] == "openai"
    assert config["fallback_configured"] is True
    assert config["oscanner_llm_fallback_model"] == "deepseek/deepseek-v4.1-flash-1017"


@pytest.mark.anyio
async def test_internal_config_save_keeps_openrouter_credentials(monkeypatch, tmp_path):
    written = {}
    env_path = tmp_path / ".env.local"
    env_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(config_route, "get_user_env_path", lambda: env_path)
    monkeypatch.setattr(
        config_route,
        "parse_env_file",
        lambda _path: {"OPEN_ROUTER_KEY": "openrouter-test-key"},
    )
    monkeypatch.setattr(
        config_route,
        "write_env_file",
        lambda _path, env: written.update(env),
    )
    monkeypatch.setattr(config_route, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(config_route, "apply_env_to_process", lambda env: written.update(env))

    result = await config_route.set_llm_config({
        "mode": "openai",
        "api_key": "internal-test-key",
        "base_url": "https://llm.example/v1",
        "model": "glm",
        "fallback_model": "deepseek/deepseek-v4.1-flash-1017",
        "openrouter_key": "new-openrouter-test-key",
    })

    assert result["success"] is True
    assert written["OPEN_ROUTER_KEY"] == "new-openrouter-test-key"
    assert written["OSCANNER_LLM_MODEL"] == "glm"
    assert written["OSCANNER_LLM_FALLBACK_MODEL"] == "deepseek/deepseek-v4.1-flash-1017"


@pytest.mark.anyio
async def test_openrouter_config_save_uses_requested_default_model(monkeypatch, tmp_path):
    written = {}
    env_path = tmp_path / ".env.local"
    env_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(config_route, "get_user_env_path", lambda: env_path)
    monkeypatch.setattr(config_route, "parse_env_file", lambda _path: {})
    monkeypatch.setattr(
        config_route,
        "write_env_file",
        lambda _path, env: written.update(env),
    )
    monkeypatch.setattr(config_route, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(config_route, "apply_env_to_process", lambda env: written.update(env))

    await config_route.set_llm_config({
        "mode": "openrouter",
        "openrouter_key": "openrouter-test-key",
    })

    assert written["OSCANNER_LLM_MODEL"] == "deepseek/deepseek-v4.1-flash-1017"
    assert "OSCANNER_LLM_API_KEY" not in written


@pytest.mark.anyio
async def test_internal_config_save_keeps_existing_fallback_key_when_blank(monkeypatch, tmp_path):
    written = {}
    env_path = tmp_path / ".env.local"
    env_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(config_route, "get_user_env_path", lambda: env_path)
    monkeypatch.setattr(
        config_route,
        "parse_env_file",
        lambda _path: {"OPEN_ROUTER_KEY": "openrouter-test-key"},
    )
    monkeypatch.setattr(
        config_route,
        "write_env_file",
        lambda _path, env: written.update(env),
    )
    monkeypatch.setattr(config_route, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(config_route, "apply_env_to_process", lambda env: written.update(env))

    await config_route.set_llm_config({
        "mode": "openai",
        "api_key": "internal-test-key",
        "base_url": "https://llm.example/v1",
        "model": "glm",
        "openrouter_key": "",
    })

    assert written["OPEN_ROUTER_KEY"] == "openrouter-test-key"
    assert written["OSCANNER_LLM_FALLBACK_MODEL"] == "deepseek/deepseek-v4.1-flash-1017"
