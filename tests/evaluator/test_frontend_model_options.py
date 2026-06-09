from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_frontend_model_selectors_only_offer_deepseek():
    files = [
        PROJECT_ROOT / "frontend" / "webapp" / "components" / "Navigation.tsx",
        PROJECT_ROOT / "frontend" / "webapp" / "components" / "TrajectoryAnalysis.tsx",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "deepseek/deepseek-v4-pro" in combined
    assert "qwen/qwen3-coder-flash" not in combined
    assert "/" + "claude" + "-sonnet-" not in combined
    assert "z-ai/glm-4.7" not in combined


def test_frontend_migrates_legacy_qwen_model_to_deepseek_default():
    settings = (
        PROJECT_ROOT
        / "frontend"
        / "webapp"
        / "components"
        / "AppSettingsContext.tsx"
    ).read_text(encoding="utf-8")

    assert "DEFAULT_MODEL = 'deepseek/deepseek-v4-pro'" in settings
    assert "'qwen/qwen3-coder-flash'" in settings
    assert "normalizeModel" in settings
    assert "LEGACY_MODEL_ALIASES.has(trimmed)" in settings
    assert "localStorage.setItem(STORAGE_KEY_MODEL, next)" in settings
