import asyncio
import importlib.util
from pathlib import Path

from repos_runner.services.repo_service import coverage, runtime_evidence
from repos_runner.grading import DEFAULT_GRADING_RUBRIC


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_NATIVE_RUBRIC_PATH = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "rubric.md"


class _Message:
    def __init__(self, text: str):
        self.content = [{"text": text}]


def test_feature_extraction_prompt_includes_grading_rubric(monkeypatch):
    captured = {}

    def _fake_messages_create_with_fallback(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return _Message('["Health endpoint returns JSON"]')

    monkeypatch.setattr(coverage, "_messages_create_with_fallback", _fake_messages_create_with_fallback)

    features = asyncio.run(
        coverage._extract_features_from_tag_message(
            "- `/health` returns JSON",
            grading_rubric="Require input validation evidence.",
        )
    )

    assert features == ["Health endpoint returns JSON"]
    assert "Require input validation evidence." in captured["prompt"]
    assert "do not invent features" in captured["prompt"]


def test_feature_extraction_prompt_uses_default_grading_rubric(monkeypatch):
    captured = {}

    def _fake_messages_create_with_fallback(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return _Message('["Health endpoint returns JSON"]')

    monkeypatch.setattr(coverage, "_messages_create_with_fallback", _fake_messages_create_with_fallback)

    asyncio.run(coverage._extract_features_from_tag_message("- `/health` returns JSON"))

    assert DEFAULT_GRADING_RUBRIC in captured["prompt"]


def test_default_grading_rubric_aligns_with_ai_native_evaluator_rubric():
    expected_terms = [
        "评分规则",
        "Vibe Coding",
        "AI搬运工",
        "系统构建者",
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
        "证据",
        "规格/质量",
        "可复现性",
        "云原生",
        "AI 工程",
        "专业性",
        "保守评分",
        "轨迹评估上下文",
    ]

    rubric_lower = DEFAULT_GRADING_RUBRIC.lower()
    for term in expected_terms:
        assert term.lower() in rubric_lower


def test_runner_and_ai_native_plugin_load_same_shared_rubric_file():
    scan_path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_shared_ai_native_rubric", scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)

    shared_rubric = AI_NATIVE_RUBRIC_PATH.read_text(encoding="utf-8").strip()

    assert shared_rubric
    assert plugin._RUBRIC_SUMMARY == shared_rubric
    assert DEFAULT_GRADING_RUBRIC == shared_rubric


def test_runtime_evidence_plan_prompt_includes_grading_rubric(monkeypatch, tmp_path):
    captured = {}
    repo = tmp_path / "repo"
    repo.mkdir()

    def _fake_messages_create_with_fallback(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return _Message('{"static_checks": [], "http_checks": [], "ui_checks": []}')

    monkeypatch.setattr(
        runtime_evidence,
        "_messages_create_with_fallback",
        _fake_messages_create_with_fallback,
    )

    runtime_evidence._llm_runtime_evidence_plan(
        repo,
        "- `/health` returns JSON",
        ["Health endpoint returns JSON"],
        [],
        grading_rubric="API behavior counts before UI polish.",
    )

    assert "API behavior counts before UI polish." in captured["prompt"]
    assert "only for the exact required features" in captured["prompt"]
