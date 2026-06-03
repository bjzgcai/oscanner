"""Tests for PR/review/issue collaboration evidence plumbing."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_ai_native_plugin():
    scan_path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_zgc_ai_native_2026_external_evidence", scan_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalize_evidence_sources_always_includes_commit_diffs():
    from evaluator.services.collaboration_evidence import normalize_evidence_sources

    assert normalize_evidence_sources(["pr_discussions", "approvals"]) == [
        "commit_diffs",
        "pr_discussions",
        "approvals",
    ]


def test_ai_native_collaboration_block_uses_external_pr_issue_evidence():
    plugin = _load_ai_native_plugin()
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="test-model",
        language="en-US",
        collaboration_evidence={
            "requested_sources": ["commit_diffs", "pr_discussions", "review_comments", "approvals", "issue_triage", "maintainer_decisions"],
            "items": [
                {
                    "source": "pr_discussions",
                    "label": "PR #12: Add export flow",
                    "detail": "3 discussion comments",
                    "url": "https://github.com/org/repo/pull/12",
                },
                {
                    "source": "review_comments",
                    "label": "PR #12 review by maintainer",
                    "detail": "requested change on API contract",
                },
                {
                    "source": "approvals",
                    "label": "PR #12 approved",
                    "detail": "APPROVED by maintainer",
                },
                {
                    "source": "issue_triage",
                    "label": "Issue #8 labeled bug",
                    "detail": "triaged and assigned before implementation",
                },
                {
                    "source": "maintainer_decisions",
                    "label": "PR #12 merged",
                    "detail": "merged by maintainer",
                },
            ],
        },
    )

    evidence = evaluator._build_collaboration_evidence(
        commits=[
            {
                "sha": "abc123",
                "commit": {
                    "author": {"name": "Ada"},
                    "message": "feat: add export flow (#12)",
                },
                "files": [{"filename": "backend/export.py", "patch": "+def export()"}],
            }
        ],
        repo_structure={},
    )
    block = evaluator._format_collaboration_evidence_block(evidence, is_chinese=False)

    assert "PR discussions" in block
    assert "review comments" in block
    assert "approvals" in block
    assert "issue triage" in block
    assert "maintainer decisions" in block
    assert "PR #12: Add export flow" in block
    assert evidence["summary"]["external_items"] == 5


def test_collaboration_evidence_fetcher_reuses_fresh_cache(tmp_path, monkeypatch):
    from evaluator.services.collaboration_evidence import fetch_collaboration_evidence

    cache_file = tmp_path / "collaboration_evidence.json"
    cache_file.write_text(
        """
{
  "platform": "github",
  "owner": "org",
  "repo": "repo",
  "requested_sources": ["pr_discussions"],
  "fetched_at": "2999-01-01T00:00:00+00:00",
  "items": [{"source": "pr_discussions", "label": "cached PR", "detail": "cached"}]
}
""".strip(),
        encoding="utf-8",
    )

    def fail_fetch(*_args, **_kwargs):
        raise AssertionError("fresh cache should avoid platform API fetch")

    monkeypatch.setattr("evaluator.services.collaboration_evidence._fetch_platform_evidence", fail_fetch)

    evidence = fetch_collaboration_evidence(
        platform="github",
        owner="org",
        repo="repo",
        data_dir=tmp_path,
        evidence_sources=["pr_discussions"],
    )

    assert evidence["items"][0]["label"] == "cached PR"
    assert evidence["cache"]["hit"] is True


def test_analyze_group_repositories_passes_collaboration_evidence_to_plugin(tmp_path, monkeypatch):
    from evaluator.services import trajectory_service

    captured_kwargs = {}

    class FakeEvaluator:
        def evaluate_repository(self, **_kwargs):
            return {
                "username": "repo",
                "total_commits_analyzed": 1,
                "files_loaded": 0,
                "mode": "moderate",
                "scores": {
                    "spec_quality": 70,
                    "cloud_architecture": 70,
                    "ai_engineering": 70,
                    "mastery_professionalism": 80,
                    "reasoning": "external collaboration evidence",
                },
                "commits_summary": {"total_additions": 1, "total_deletions": 0, "files_changed": 1, "languages": []},
            }

    def fake_create_commit_evaluator(**kwargs):
        captured_kwargs.update(kwargs)
        return FakeEvaluator()

    fake_scan = SimpleNamespace(create_commit_evaluator=fake_create_commit_evaluator)
    fake_meta = SimpleNamespace(version="0.1.0")
    commits = [
        {
            "sha": "abc123",
            "commit": {"author": {"name": "Ada", "date": "2026-01-01T00:00:00Z"}, "message": "feat: work"},
            "files": [{"filename": "app.py", "patch": "+print(1)"}],
        }
    ]

    monkeypatch.setattr(trajectory_service, "_sync_repo_for_group_eval", lambda _repo_url: ("github", "org", "repo", False))
    monkeypatch.setattr(trajectory_service, "_load_all_repo_commits", lambda _repo_url: (commits, tmp_path))
    monkeypatch.setattr(trajectory_service, "_refresh_group_repo_snapshot_for_end_sha", lambda repo_url, item, sync, data_dir: (sync, False))
    monkeypatch.setattr(trajectory_service, "ensure_repo_evaluation_input_within_limit", lambda **_kwargs: None)
    monkeypatch.setattr(trajectory_service, "load_scan_module", lambda _plugin_id: (fake_meta, fake_scan, Path("scan.py")))
    monkeypatch.setattr(trajectory_service, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(
        trajectory_service,
        "fetch_collaboration_evidence",
        lambda **kwargs: {
            "requested_sources": kwargs["evidence_sources"],
            "items": [{"source": "pr_discussions", "label": "PR #1", "detail": "discussion"}],
        },
    )

    result = trajectory_service.analyze_group_repositories(
        repositories=[{"repo_url": "https://github.com/org/repo"}],
        plugin_id="zgc_ai_native_2026",
        model="test-model",
        language="en-US",
        evidence_sources=["pr_discussions"],
    )

    assert result["success"] is True
    assert captured_kwargs["collaboration_evidence"]["items"][0]["label"] == "PR #1"


@pytest.mark.anyio
async def test_analyze_one_off_route_passes_evidence_sources_to_service(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    captured_args = {}

    def fake_analyze_growth_trajectory(*args):
        captured_args["evidence_sources"] = args[-2]
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
            "evidence_sources": ["commit_diffs", "pr_discussions", "approvals"],
            "expected_feature": "实现导出功能",
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
    assert captured_args["evidence_sources"] == ["commit_diffs", "pr_discussions", "approvals"]
    assert captured_args["expected_feature"] == "实现导出功能"
