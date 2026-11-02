from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_frontend_model_selectors_use_internal_glm():
    files = [
        PROJECT_ROOT / "frontend" / "webapp" / "components" / "Navigation.tsx",
        PROJECT_ROOT / "frontend" / "webapp" / "components" / "TrajectoryAnalysis.tsx",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    model_defaults = (
        PROJECT_ROOT / "frontend" / "webapp" / "utils" / "llmModels.ts"
    ).read_text(encoding="utf-8")

    assert "INTERNAL_LLM_MODEL" in combined
    assert "export const INTERNAL_LLM_MODEL = 'glm'" in model_defaults
    assert "export const OPENROUTER_LLM_MODEL = 'deepseek/deepseek-v4.1-flash-1017'" in model_defaults
    assert "qwen/qwen3-coder-flash" not in combined
    assert "/" + "claude" + "-sonnet-" not in combined
    assert "z-ai/glm-4.7" not in combined


def test_frontend_migrates_legacy_models_to_internal_default():
    settings = (
        PROJECT_ROOT
        / "frontend"
        / "webapp"
        / "components"
        / "AppSettingsContext.tsx"
    ).read_text(encoding="utf-8")

    assert "DEFAULT_MODEL = INTERNAL_LLM_MODEL" in settings
    assert "'qwen/qwen3-coder-flash'" in settings
    assert "'deepseek/deepseek-v4-pro'" in settings
    assert "normalizeModel" in settings
    assert "LEGACY_MODEL_ALIASES.has(trimmed)" in settings
    assert "localStorage.setItem(STORAGE_KEY_MODEL, next)" in settings


def test_frontend_llm_settings_describe_glm_primary_and_openrouter_fallback():
    modal = (
        PROJECT_ROOT
        / "frontend"
        / "webapp"
        / "components"
        / "LlmConfigModal.tsx"
    ).read_text(encoding="utf-8")

    assert "OSCANNER_LLM_FALLBACK_MODELS（可选）" in modal
    assert "OpenRouter 回退模型" in modal
    assert "fallback_model: llmFallbackModel" in modal
    assert "openrouter_key: openRouterKey || null" in modal
    assert "{INTERNAL_LLM_MODEL} → {llmFallbackModel" in modal
