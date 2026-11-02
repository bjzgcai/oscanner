import importlib


def test_default_llm_model_is_glm(monkeypatch):
    monkeypatch.delenv("INTERNAL_LLM_QUESTION_MODEL", raising=False)
    monkeypatch.delenv("OSCANNER_LLM_MODEL", raising=False)
    import evaluator.config.tokens as tokens

    tokens = importlib.reload(tokens)

    assert tokens.DEFAULT_LLM_MODEL == "glm"
