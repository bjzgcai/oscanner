from types import SimpleNamespace

import pytest

from evaluator.routes import gitee


def test_gitee_profile_route_is_registered():
    route_paths = {getattr(route, "path", "") for route in gitee.router.routes}

    assert "/api/gitee/profile/evaluate" in route_paths


@pytest.mark.asyncio
async def test_gitee_profile_evaluate_uses_latest_matching_commits(tmp_path, monkeypatch):
    older = gitee._serialize_commit(
        {
            "sha": "a" * 40,
            "html_url": "https://gitee.com/owner/repo/commit/" + "a" * 40,
            "author": {"login": "alice"},
            "commit": {
                "author": {"name": "alice", "date": "2026-01-01T00:00:00Z"},
                "message": "feat: older",
            },
            "stats": {"additions": 1, "deletions": 0, "total": 1},
            "files": [{"filename": "old.py"}],
        },
        owner="owner",
        repo="repo",
        username="alice",
    )
    newer = gitee._serialize_commit(
        {
            "sha": "b" * 40,
            "html_url": "https://gitee.com/owner/repo/commit/" + "b" * 40,
            "author": {"login": "alice"},
            "commit": {
                "author": {"name": "alice", "date": "2026-02-01T00:00:00Z"},
                "message": "feat: newer",
            },
            "stats": {"additions": 3, "deletions": 1, "total": 4},
            "files": [{"filename": "new.py"}],
        },
        owner="owner",
        repo="repo",
        username="alice",
    )

    class FakeEvaluator:
        def evaluate_engineer(self, *, commits, username, max_commits, load_files):
            assert username == "alice"
            assert max_commits == 1
            assert load_files is False
            assert [commit["sha"] for commit in commits] == ["b" * 40]
            return {
                "username": username,
                "total_commits_analyzed": len(commits),
                "scores": {"spec_quality": 88},
            }

    class FakeScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            assert kwargs["language"] == "zh-CN"
            return FakeEvaluator()

    monkeypatch.setattr(gitee, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(gitee, "get_llm_api_key", lambda: "llm-key")
    monkeypatch.setattr(gitee, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(gitee, "resolve_plugin_id", lambda plugin: plugin or "zgc_ai_native_2026")
    monkeypatch.setattr(
        gitee,
        "load_scan_module",
        lambda plugin_id: (SimpleNamespace(version="1.0.0"), FakeScanModule, tmp_path / "scan.py"),
    )
    monkeypatch.setattr(
        gitee,
        "_fetch_profile_repositories",
        lambda username, token: [
            {
                "platform": "gitee",
                "owner": "owner",
                "repo": "repo",
                "repo_full_name": "owner/repo",
                "repo_url": "https://gitee.com/owner/repo",
            }
        ],
    )
    monkeypatch.setattr(
        gitee,
        "_sync_one_repo",
        lambda repo, *, sync_commits_per_repo: {
            "repo": repo,
            "data_dir": str(tmp_path / "gitee" / "owner" / "repo"),
            "changed": True,
            "mode": "incremental",
            "commits": [older, newer],
            "collaboration_evidence": [],
            "warnings": [],
        },
    )

    result = await gitee.evaluate_gitee_profile(
        {
            "username": "alice",
            "commit_limit": 1,
            "model": "test-model",
            "plugin": "zgc_ai_native_2026",
            "language": "zh-CN",
        }
    )

    assert result["success"] is True
    assert result["summary"]["commit_limit"] == 1
    assert result["summary"]["available_commit_count"] == 2
    assert result["commits"][0]["sha"] == "b" * 40
    assert result["evaluation"]["total_commits_analyzed"] == 1
