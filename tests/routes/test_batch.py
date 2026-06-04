"""Tests for batch repository routes."""

from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.mark.anyio
async def test_compare_contributor_passes_branch_to_evaluation(tmp_path, monkeypatch):
    from evaluator.routes import batch

    data_dir = tmp_path / "github" / "org" / "repo" / "branch-feature_demo"
    (data_dir / "commits").mkdir(parents=True)
    captured = {}

    async def fake_evaluate_author(owner, repo, contributor, **kwargs):
        captured.update(
            {
                "owner": owner,
                "repo": repo,
                "contributor": contributor,
                "branch": kwargs.get("branch"),
                "platform": kwargs.get("platform"),
            }
        )
        return {
            "success": True,
            "evaluation": {
                "scores": {},
                "total_commits_analyzed": 1,
                "commits_summary": {},
                "plugin": "zgc_ai_native_2026",
            },
        }

    monkeypatch.setattr(batch, "get_platform_data_dir", lambda platform, owner, repo, ref=None: data_dir)
    monkeypatch.setattr(batch, "extract_github_data", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("data exists")))
    monkeypatch.setattr(batch, "evaluate_author", fake_evaluate_author)

    result = await batch.compare_contributor_across_repos(
        {
            "contributor": "Ada",
            "repos": [
                {
                    "owner": "org",
                    "repo": "repo",
                    "platform": "github",
                    "branch": "feature/demo",
                }
            ],
        }
    )

    assert result["success"] is True
    assert captured == {
        "owner": "org",
        "repo": "repo",
        "contributor": "Ada",
        "branch": "feature/demo",
        "platform": "github",
    }


@pytest.mark.anyio
async def test_compare_contributor_preserves_plugin_score_keys(tmp_path, monkeypatch):
    from evaluator.routes import batch

    data_dir = tmp_path / "github" / "org" / "repo"
    (data_dir / "commits").mkdir(parents=True)
    captured = {}

    async def fake_evaluate_author(owner, repo, contributor, **kwargs):
        captured["request_body"] = kwargs.get("request_body")
        return {
            "success": True,
            "evaluation": {
                "scores": {
                    "spec_quality": 80,
                    "cloud_architecture": 70,
                    "ai_engineering": 60,
                    "mastery_professionalism": 90,
                    "reasoning": "ok",
                },
                "total_commits_analyzed": 3,
                "commits_summary": {},
                "plugin": "zgc_ai_native_2026",
            },
        }

    monkeypatch.setattr(batch, "get_platform_data_dir", lambda platform, owner, repo, ref=None: data_dir)
    monkeypatch.setattr(batch, "extract_github_data", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("data exists")))
    monkeypatch.setattr(batch, "resolve_plugin_id", lambda plugin: "zgc_ai_native_2026")
    monkeypatch.setattr(batch, "evaluate_author", fake_evaluate_author)

    result = await batch.compare_contributor_across_repos(
        {
            "contributor": "alice@example.com",
            "repos": [{"owner": "org", "repo": "repo", "platform": "github"}],
            "author_emails": ["alice@example.com", "alice@work.com"],
            "plugin": "zgc_ai_native_2026",
        }
    )

    assert result["success"] is True
    assert result["dimension_keys"] == [
        "spec_quality",
        "cloud_architecture",
        "ai_engineering",
        "mastery_professionalism",
    ]
    assert result["comparisons"][0]["scores"] == {
        "spec_quality": 80,
        "cloud_architecture": 70,
        "ai_engineering": 60,
        "mastery_professionalism": 90,
    }
    assert result["aggregate"]["average_scores"]["spec_quality"] == 80
    assert captured["request_body"] == {"emails": ["alice@example.com", "alice@work.com"]}
