from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER_COMPONENT = PROJECT_ROOT / "frontend" / "webapp" / "components" / "RepositoryRunner.tsx"
EN_MESSAGES = PROJECT_ROOT / "frontend" / "webapp" / "i18n" / "en-US.ts"
ZH_MESSAGES = PROJECT_ROOT / "frontend" / "webapp" / "i18n" / "zh-CN.ts"


def test_repository_runner_maps_optional_version_ref_to_sha_or_tag_payload():
    source = RUNNER_COMPONENT.read_text(encoding="utf-8")

    assert "const GIT_COMMIT_SHA_PATTERN = /^[0-9a-f]{7,40}$/i;" in source
    assert "function getVersionRefPayload(versionRef: string): { sha?: string; tag?: string }" in source
    assert "if (!trimmed) return {};" in source
    assert "return GIT_COMMIT_SHA_PATTERN.test(trimmed) ? { sha: trimmed } : { tag: trimmed };" in source
    assert "const [versionRef, setVersionRef] = useState('');" in source
    assert "body: JSON.stringify({ repo_url: repoUrl, ...getVersionRefPayload(versionRef) })" in source
    assert "setVersionRef('');" in source


def test_repository_runner_has_localized_optional_version_ref_placeholder():
    runner_source = RUNNER_COMPONENT.read_text(encoding="utf-8")
    en_source = EN_MESSAGES.read_text(encoding="utf-8")
    zh_source = ZH_MESSAGES.read_text(encoding="utf-8")

    assert "placeholder={t('runner.version_ref.placeholder')}" in runner_source
    assert "'runner.version_ref.placeholder': 'Optional: enter a tag or commit ID. Leave blank to use the latest commit.'" in en_source
    assert "'runner.version_ref.placeholder': '可选：输入 tag 或 commit id；留空则使用最新提交。'" in zh_source
