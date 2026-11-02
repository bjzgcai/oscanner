from repos_runner.services.repo_service import llm


def test_model_chains_default_to_internal_glm_then_openrouter_deepseek(monkeypatch):
    for key in (
        "OSCANNER_LLM_MODEL",
        "REPOS_RUNNER_LLM_MODEL",
        "OSCANNER_LLM_FALLBACK_MODEL",
        "OPEN_ROUTER_FALLBACK_MODELS",
        "OPENROUTER_FALLBACK_MODELS",
    ):
        monkeypatch.delenv(key, raising=False)

    assert llm._get_model_candidates("INTERNAL_LLM_KEY", "") == ["glm"]
    assert llm._get_model_candidates("OPEN_ROUTER_KEY", "") == ["deepseek/deepseek-v4.1-flash-1017"]


def test_openrouter_model_chain_normalizes_opencode_model_prefix(monkeypatch):
    monkeypatch.delenv("OSCANNER_LLM_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("OPEN_ROUTER_FALLBACK_MODELS", raising=False)
    monkeypatch.delenv("OPENROUTER_FALLBACK_MODELS", raising=False)

    assert llm._get_model_candidates(
        "OPEN_ROUTER_KEY",
        "openrouter/deepseek/deepseek-v4.1-flash-1017",
    ) == ["deepseek/deepseek-v4.1-flash-1017"]
