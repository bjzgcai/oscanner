"""Tests for expected_feature baseline evaluation."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_ai_native_plugin():
    scan_path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_zgc_ai_native_2026_scan", scan_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_ai_native_prompt_uses_expected_feature_as_baseline():
    plugin = _load_ai_native_plugin()

    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="test-model",
        language="zh-CN",
        expected_feature="实现用户登录功能，包括密码校验和失败提示",
    )

    prompt = evaluator._build_evaluation_prompt("提交和文件内容", "alice")

    assert "期望实现功能" in prompt
    assert "实现用户登录功能，包括密码校验和失败提示" in prompt
    assert "降低评分" in prompt
    assert "缺失" in prompt


def test_create_checkpoint_evaluation_passes_expected_feature_to_plugin():
    from evaluator.services.trajectory_service import create_checkpoint_evaluation

    captured_kwargs = {}

    class FakeEvaluator:
        def evaluate_engineer(self, **_kwargs):
            return {
                "username": "alice",
                "total_commits_analyzed": 1,
                "files_loaded": 0,
                "mode": "moderate",
                "scores": {
                    "spec_quality": 40,
                    "cloud_architecture": 30,
                    "ai_engineering": 20,
                    "mastery_professionalism": 50,
                    "reasoning": "Lacks the expected login feature.",
                },
                "commits_summary": {
                    "total_additions": 1,
                    "total_deletions": 0,
                    "files_changed": 1,
                    "languages": ["py"],
                },
            }

    def fake_create_commit_evaluator(**kwargs):
        captured_kwargs.update(kwargs)
        return FakeEvaluator()

    fake_scan = SimpleNamespace(create_commit_evaluator=fake_create_commit_evaluator)
    fake_meta = SimpleNamespace(version="0.1.0")
    commits = [
        {
            "sha": "abc123",
            "commit": {
                "author": {"name": "alice", "date": "2026-01-01T00:00:00Z"},
                "message": "initial work",
            },
            "files": [{"filename": "app.py", "patch": "+print('hello')"}],
        }
    ]

    with patch("evaluator.services.trajectory_service.load_scan_module", return_value=(fake_meta, fake_scan, Path("scan.py"))), \
         patch("evaluator.services.trajectory_service.get_platform_data_dir", return_value=Path("/tmp/data")), \
         patch("evaluator.services.trajectory_service.get_llm_api_key", return_value="test-key"):
        checkpoint = create_checkpoint_evaluation(
            commits=commits,
            username="alice",
            checkpoint_id=1,
            plugin_id="zgc_ai_native_2026",
            model="test-model",
            language="zh-CN",
            repos_analyzed=["https://github.com/example/repo"],
            aliases_used=["alice"],
            expected_feature="实现用户登录功能",
            checkpoint_strategy="none",
        )

    assert captured_kwargs["expected_feature"] == "实现用户登录功能"
    assert checkpoint.evaluation.expected_feature == "实现用户登录功能"


@pytest.mark.anyio
async def test_analyze_one_off_route_passes_expected_feature_to_service(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    captured_args = {}

    def fake_analyze_growth_trajectory(*args):
        captured_args["expected_feature"] = args[-1]
        return SimpleNamespace(success=False, trajectory=None, message="done")

    monkeypatch.setattr(trajectory_route, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(trajectory_route, "get_github_token", lambda: "github-token")
    monkeypatch.setattr(trajectory_route, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(trajectory_route, "resolve_plugin_id", lambda plugin: plugin)
    monkeypatch.setattr(trajectory_route, "analyze_growth_trajectory", fake_analyze_growth_trajectory)

    result = await trajectory_route.analyze_trajectory_one_off(
        request_body={
            "repo_url": "https://github.com/example/repo",
            "username": "alice",
            "aliases": ["alice"],
            "expected_feature": "实现用户登录功能",
        },
        plugin="zgc_ai_native_2026",
        model="test-model",
        language="zh-CN",
        forced_checker="",
        worktree_base="build",
        checkpoint_strategy="none",
        start_sha="",
        end_sha="",
    )

    assert result["success"] is False
    assert captured_args["expected_feature"] == "实现用户登录功能"


@pytest.mark.anyio
async def test_analyze_one_off_route_allows_missing_expected_feature(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    captured_args = {}

    def fake_analyze_growth_trajectory(*args):
        captured_args["expected_feature"] = args[-1]
        return SimpleNamespace(success=False, trajectory=None, message="done")

    monkeypatch.setattr(trajectory_route, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(trajectory_route, "get_github_token", lambda: "github-token")
    monkeypatch.setattr(trajectory_route, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(trajectory_route, "resolve_plugin_id", lambda plugin: plugin)
    monkeypatch.setattr(trajectory_route, "analyze_growth_trajectory", fake_analyze_growth_trajectory)

    result = await trajectory_route.analyze_trajectory_one_off(
        request_body={
            "repo_url": "https://github.com/example/repo",
            "username": "alice",
            "aliases": ["alice"],
        },
        plugin="zgc_ai_native_2026",
        model="test-model",
        language="zh-CN",
        forced_checker="",
        worktree_base="build",
        checkpoint_strategy="none",
        start_sha="",
        end_sha="",
    )

    assert result["success"] is False
    assert captured_args["expected_feature"] is None


@pytest.mark.anyio
async def test_analyze_one_off_route_uses_deepseek_only_without_synthesis(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    models_used = []

    class FakeCommitRange:
        commit_count = 2

    class FakeCheckpoint:
        commits_range = FakeCommitRange()

        def __init__(self, model_name):
            self.model_name = model_name

        def model_dump(self):
            return {
                "checkpoint_id": 1,
                "commits_range": {"commit_count": 2},
                "evaluation": {
                    "username": "alice",
                    "scores": {
                        "spec_quality": 60 if self.model_name.startswith("deepseek/") else 80,
                        "cloud_architecture": 50,
                        "ai_engineering": 70,
                        "mastery_professionalism": 55,
                        "reasoning": f"**整体评估**\n{self.model_name} judgement",
                    },
                },
            }

    def fake_analyze_growth_trajectory(*args):
        model_name = args[4]
        models_used.append(model_name)
        return SimpleNamespace(
            success=True,
            trajectory=SimpleNamespace(checkpoints=[FakeCheckpoint(model_name)]),
            message=f"{model_name} done",
        )

    monkeypatch.setattr(trajectory_route, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(trajectory_route, "get_github_token", lambda: "github-token")
    monkeypatch.setattr(trajectory_route, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(trajectory_route, "resolve_plugin_id", lambda plugin: plugin)
    monkeypatch.setattr(trajectory_route, "analyze_growth_trajectory", fake_analyze_growth_trajectory)

    result = await trajectory_route.analyze_trajectory_one_off(
        request_body={
            "repo_url": "https://github.com/example/repo",
            "username": "alice",
            "aliases": ["alice"],
            "expected_feature": "实现用户登录功能",
        },
        plugin="zgc_ai_native_2026",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
        forced_checker="",
        worktree_base="build",
        checkpoint_strategy="none",
        start_sha="",
        end_sha="",
    )

    assert result["success"] is True
    assert models_used == ["deepseek/deepseek-v4-pro"]
    assert result["checkpoint"]["evaluation"]["scores"]["reasoning"] == "**整体评估**\ndeepseek/deepseek-v4-pro judgement"
    assert result["model_judging"] == {
        "primary_models": ["deepseek/deepseek-v4-pro"],
        "synthesis_model": None,
        "conflicts_detected": False,
    }
