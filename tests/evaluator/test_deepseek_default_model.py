import importlib


def test_default_llm_model_is_deepseek_v4_pro(monkeypatch):
    monkeypatch.delenv("OSCANNER_LLM_MODEL", raising=False)
    import evaluator.config.tokens as tokens

    tokens = importlib.reload(tokens)

    assert tokens.DEFAULT_LLM_MODEL == "deepseek/deepseek-v4-pro"
