"""Tests for courses-style group repository evaluation."""

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.mark.anyio
async def test_group_analyse_code_route_batches_repos_without_parallel_chunking(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    captured = {}

    def fake_analyze_group_repositories(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "results": [
                {
                    "success": True,
                    "id": "s1",
                    "username": "Alice",
                    "repo_url": "https://gitee.com/org/repo-a",
                    "score": 88,
                    "checkpoint": {"evaluation": {"scores": {"total": 88}}},
                },
                {
                    "success": True,
                    "id": "s2",
                    "username": "Bob",
                    "repo_url": "https://github.com/org/repo-b",
                    "score": 83,
                    "checkpoint": {"evaluation": {"scores": {"total": 83}}},
                },
            ],
            "model_judging": {"primary_models": ["deepseek/deepseek-v4-pro"]},
        }

    monkeypatch.setattr(trajectory_route, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(trajectory_route, "get_github_token", lambda: "github-token")
    monkeypatch.setattr(trajectory_route, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(trajectory_route, "resolve_plugin_id", lambda plugin: plugin)
    monkeypatch.setattr(trajectory_route, "analyze_group_repositories", fake_analyze_group_repositories)

    result = await trajectory_route.group_analyse_code(
        request_body={
            "tag": "整体",
            "students": [
                {"id": "s1", "username": "Alice", "repo_url": "https://gitee.com/org/repo-a"},
                {"id": "s2", "username": "Bob", "repo_url": "https://github.com/org/repo-b"},
            ],
        },
        plugin="zgc_ai_native_2026",
        language="zh-CN",
        use_cache=True,
        max_fetch_workers=4,
        forced_checker="",
        worktree_base="build",
    )

    assert result["success"] is True
    assert [item["repo_url"] for item in captured["repositories"]] == [
        "https://gitee.com/org/repo-a",
        "https://github.com/org/repo-b",
    ]
    assert captured["model"] == "deepseek/deepseek-v4-pro"
    assert captured["full_repo"] is True
    assert captured["use_chunking"] is False
    assert captured["max_fetch_workers"] == 4


def test_ai_native_plugin_evaluate_repository_uses_all_commits_without_chunking(monkeypatch):
    import importlib.util

    scan_path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_zgc_ai_native_2026_group_scan", scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)

    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )

    commits = [
        {
            "sha": f"sha-{idx}",
            "author": "Alice" if idx % 2 else "Bob",
            "commit": {
                "author": {"name": "Alice" if idx % 2 else "Bob", "date": f"2026-01-{idx:02d}T00:00:00Z"},
                "message": f"commit {idx}",
            },
            "files": [{"filename": f"file_{idx}.py", "patch": f"+print({idx})"}],
        }
        for idx in range(1, 31)
    ]

    contexts = []

    def fail_chunking(*_args, **_kwargs):
        raise AssertionError("full repository evaluation must not chunk")

    def fake_part_eval(part_name, part_context, username, chunk_idx=None):
        contexts.append((part_name, part_context, username, chunk_idx))
        return {
            "spec_quality": 80,
            "cloud_architecture": 70,
            "ai_engineering": 75,
            "mastery_professionalism": 85,
            "reasoning": "repo-level judgment",
        }

    def fake_merge(partial_results, username, checker_raw_analysis=None):
        return partial_results[0]

    monkeypatch.setattr(evaluator, "_evaluate_engineer_chunked", fail_chunking)
    monkeypatch.setattr(evaluator, "_evaluate_part_with_llm", fake_part_eval)
    monkeypatch.setattr(evaluator, "_merge_partial_evaluations", fake_merge)

    result = evaluator.evaluate_repository(
        commits=commits,
        repo_label="https://gitee.com/org/repo",
        load_files=False,
        use_chunking=False,
    )

    assert result["username"] == "https://gitee.com/org/repo"
    assert result["total_commits_analyzed"] == 30
    commits_context = next(context for part_name, context, *_ in contexts if part_name == "commits")
    assert "sha-1" in commits_context
    assert "sha-30" in commits_context
    assert "Commits: 30" in commits_context
