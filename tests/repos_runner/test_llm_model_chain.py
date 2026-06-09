from repos_runner.services.repo_service import llm


def test_openrouter_model_chain_defaults_to_deepseek_then_glm_5_1(monkeypatch):
    for key in (
        "OPEN_ROUTER_PRIMARY_MODEL",
        "OPENROUTER_PRIMARY_MODEL",
        "OPEN_ROUTER_FALLBACK_MODEL",
        "OPENROUTER_FALLBACK_MODEL",
        "OPEN_ROUTER_FALLBACK_MODELS",
        "OPENROUTER_FALLBACK_MODELS",
        "OSCANNER_LLM_FALLBACK_MODELS",
    ):
        monkeypatch.delenv(key, raising=False)

    assert llm._get_model_candidates("OPEN_ROUTER_KEY", "") == [
        "deepseek/deepseek-v4-pro",
        "z-ai/glm-5.1",
    ]


def test_openrouter_model_chain_normalizes_opencode_model_prefix(monkeypatch):
    monkeypatch.delenv("OPEN_ROUTER_PRIMARY_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_PRIMARY_MODEL", raising=False)
    monkeypatch.delenv("OPEN_ROUTER_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("OPEN_ROUTER_FALLBACK_MODELS", raising=False)
    monkeypatch.delenv("OPENROUTER_FALLBACK_MODELS", raising=False)
    monkeypatch.delenv("OSCANNER_LLM_FALLBACK_MODELS", raising=False)

    assert llm._get_model_candidates(
        "OPEN_ROUTER_KEY",
        "openrouter/deepseek/deepseek-v4-pro",
    ) == [
        "deepseek/deepseek-v4-pro",
        "z-ai/glm-5.1",
    ]
