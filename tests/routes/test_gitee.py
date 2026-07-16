from types import SimpleNamespace

import pytest

from evaluator.routes import gitee


def test_gitee_profile_route_is_registered():
    route_paths = {getattr(route, "path", "") for route in gitee.router.routes}

    assert "/api/gitee/profile/evaluate" in route_paths


def test_gitee_commit_limit_supports_1000_and_clamps_larger_values():
    assert gitee._parse_commit_limit(1000) == 1000
    assert gitee._parse_commit_limit(2500) == 1000


def test_gitee_profile_sync_attributes_all_commits_regardless_of_identity(tmp_path, monkeypatch):
    commit = {
        "sha": "9" * 40,
        "commit": {
            "author": {"name": "Different User", "email": "different@example.com"},
            "committer": {"name": "Another User", "email": "another@example.com"},
            "message": "feat: profile-wide gitee evidence",
        },
    }
    data_dir = tmp_path / "gitee" / "owner" / "repo"

    monkeypatch.setattr(gitee, "get_platform_data_dir", lambda *args: data_dir)
    monkeypatch.setattr(gitee, "extract_gitee_data", lambda *args, **kwargs: True)
    monkeypatch.setattr(gitee, "load_commits_from_local", lambda *args, **kwargs: [commit])
    monkeypatch.setattr(
        gitee,
        "fetch_collaboration_evidence",
        lambda **kwargs: {"items": [], "warnings": []},
    )

    result = gitee._sync_one_repo(
        {
            "owner": "owner",
            "repo": "repo",
            "repo_url": "https://gitee.com/owner/repo",
            "username": "profile-owner",
        },
        sync_commits_per_repo=0,
    )

    assert len(result["commits"]) == 1
    assert result["commits"][0]["matched_identity"] == "profile-owner"
    assert result["commits"][0]["commit"]["author"]["email"] == "different@example.com"


def test_gitee_repository_sync_with_email_keeps_only_exact_matches(tmp_path, monkeypatch):
    commits = [
        {
            "sha": "7" * 40,
            "commit": {
                "author": {"name": "Matched", "email": "requested@example.com"},
                "message": "feat: matched",
            },
        },
        {
            "sha": "8" * 40,
            "commit": {
                "author": {"name": "Other", "email": "other@example.com"},
                "message": "feat: unmatched",
            },
        },
    ]
    data_dir = tmp_path / "gitee" / "owner" / "repo"

    monkeypatch.setattr(gitee, "get_platform_data_dir", lambda *args: data_dir)
    monkeypatch.setattr(gitee, "extract_gitee_data", lambda *args, **kwargs: True)
    monkeypatch.setattr(gitee, "load_commits_from_local", lambda *args, **kwargs: commits)
    monkeypatch.setattr(
        gitee,
        "fetch_collaboration_evidence",
        lambda **kwargs: {"items": [], "warnings": []},
    )

    result = gitee._sync_one_repo(
        {
            "owner": "owner",
            "repo": "repo",
            "repo_url": "https://gitee.com/owner/repo",
            "username": "gitee:owner/repo",
        },
        sync_commits_per_repo=0,
        emails=["requested@example.com"],
    )

    assert [commit["sha"] for commit in result["commits"]] == ["7" * 40]
    assert result["commits"][0]["matched_email"] == "requested@example.com"


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
    assert "commit_count" not in result["summary"]
    assert result["commits"][0]["sha"] == "b" * 40
    assert result["evaluation"]["total_commits_analyzed"] == 1


@pytest.mark.asyncio
async def test_gitee_repo_evaluate_matches_supplied_commit_email(tmp_path, monkeypatch):
    matched = gitee._serialize_commit(
        {
            "sha": "c" * 40,
            "html_url": "https://gitee.com/owner/repo/commit/" + "c" * 40,
            "commit": {
                "author": {
                    "name": "Alice",
                    "email": "Alice@Example.com",
                    "date": "2026-03-01T00:00:00Z",
                },
                "committer": {
                    "name": "Integrator",
                    "email": "integrator@example.com",
                    "date": "2026-03-01T00:01:00Z",
                },
                "message": "feat: repo scoped",
            },
            "stats": {"additions": 2, "deletions": 1, "total": 3},
            "files": [{"filename": "repo.py"}],
        },
        owner="owner",
        repo="repo",
        username="alice@example.com",
        matched_email="alice@example.com",
    )

    class FakeEvaluator:
        def evaluate_engineer(self, *, commits, username, max_commits, load_files):
            assert username == "alice@example.com"
            assert [commit["sha"] for commit in commits] == ["c" * 40]
            return {
                "username": username,
                "total_commits_analyzed": len(commits),
                "scores": {"spec_quality": 90},
            }

    class FakeScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            return FakeEvaluator()

    seen = {}

    def fake_sync(repo, *, sync_commits_per_repo, emails=None):
        seen["repo"] = repo
        seen["emails"] = emails
        return {
            "repo": repo,
            "data_dir": str(tmp_path / "gitee" / "owner" / "repo"),
            "changed": True,
            "mode": "incremental",
            "commits": [matched],
            "collaboration_evidence": [],
            "warnings": [],
        }

    monkeypatch.setattr(gitee, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(gitee, "get_llm_api_key", lambda: "llm-key")
    monkeypatch.setattr(gitee, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(gitee, "resolve_plugin_id", lambda plugin: plugin or "zgc_ai_native_2026")
    monkeypatch.setattr(
        gitee,
        "load_scan_module",
        lambda plugin_id: (SimpleNamespace(version="1.0.0"), FakeScanModule, tmp_path / "scan.py"),
    )
    monkeypatch.setattr(gitee, "_sync_one_repo", fake_sync)

    result = await gitee.evaluate_gitee_profile(
        {
            "repo_url": "https://gitee.com/owner/repo",
            "emails": "Alice@Example.com",
            "commit_limit": 10,
            "model": "test-model",
            "plugin": "zgc_ai_native_2026",
            "language": "zh-CN",
        }
    )

    assert seen["repo"]["repo_full_name"] == "owner/repo"
    assert seen["emails"] == ["alice@example.com"]
    assert result["scope"] == "gitee_repository"
    assert result["commits"][0]["matched_email"] == "alice@example.com"
    assert result["evaluation"]["scope"] == "gitee_repository"
