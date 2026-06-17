import json

import pytest
from types import SimpleNamespace

from evaluator.routes import github


def test_github_evaluate_route_is_registered_with_legacy_alias():
    route_paths = {getattr(route, "path", "") for route in github.router.routes}

    assert "/api/github/evaluate" in route_paths
    assert "/api/github/analyze" in route_paths
    assert "/api/gitee-github/evaluate" in route_paths
    assert "/api/gitee-github/analyze" in route_paths


def test_parse_email_list_requires_comma_separated_valid_emails():
    assert github._parse_email_list("Alice@Example.com,bob@example.org") == [
        "alice@example.com",
        "bob@example.org",
    ]

    with pytest.raises(Exception) as exc_info:
        github._parse_email_list("alice@example.com，bob@example.org")

    assert "Invalid email format" in str(exc_info.value)


def test_parse_github_identity_request_accepts_mixed_emails_profiles_and_repos():
    parsed = github._parse_github_identity_request({
        "github_inputs": "Alice@Example.com, https://github.com/octocat, github.com/openai/codex.git",
    })

    assert parsed["emails"] == ["alice@example.com"]
    assert parsed["github_profiles"] == ["https://github.com/octocat"]
    assert parsed["github_repos"] == ["https://github.com/openai/codex"]


@pytest.mark.asyncio
async def test_analyze_github_collects_cached_gitee_commits_by_author_and_committer_email(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    repo_dir = data_dir / "gitee" / "owner" / "repo"
    commits_dir = repo_dir / "commits"
    commits_dir.mkdir(parents=True)
    sha = "a" * 40
    (repo_dir / "commits_index.json").write_text(
        f'[{{"sha": "{sha}"}}]',
        encoding="utf-8",
    )
    (commits_dir / f"{sha}.json").write_text(
        """
        {
          "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "html_url": "https://gitee.com/owner/repo/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "commit": {
            "author": {
              "name": "Alice",
              "email": "alice@example.com",
              "date": "2026-01-02T03:04:05Z"
            },
            "committer": {
              "name": "Alice Integrator",
              "email": "alice@example.com",
              "date": "2026-01-02T03:05:05Z"
            },
            "message": "feat: add thing"
          },
          "stats": {"additions": 3, "deletions": 1, "total": 4},
          "files": [{"filename": "app.py"}]
        }
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr(github, "get_data_dir", lambda: data_dir)
    monkeypatch.setattr(
        github,
        "_fetch_global_github_evidence",
        lambda emails, **_: ({email: [] for email in emails}, {}, [], []),
    )

    result = await github.analyze_github({
        "emails": "alice@example.com",
        "fetch_collaboration": False,
    })

    assert result["success"] is True
    assert result["repos_scanned"] == 1
    assert result["summary"]["matched_repo_count"] == 1
    assert result["summary"]["commit_count"] == 1
    assert result["commits"][0]["matched_email"] == "alice@example.com"
    assert result["commits"][0]["repo_full_name"] == "owner/repo"
    assert {role["role"] for role in result["commits"][0]["matched_roles"]} == {"author", "committer"}


def test_serialize_commit_records_author_and_committer_roles():
    commit = {
        "sha": "b" * 40,
        "commit": {
            "author": {
                "name": "Author Name",
                "email": "dev@example.com",
                "date": "2026-01-02T03:04:05Z",
            },
            "committer": {
                "name": "Committer Name",
                "email": "integrator@example.com",
                "date": "2026-01-02T04:04:05Z",
            },
            "message": "feat: separate identities",
        },
        "author": {"login": "dev-login"},
        "committer": {"login": "integrator-login"},
    }

    author_match = github._serialize_commit(
        commit=commit,
        platform="github",
        owner="owner",
        repo="repo",
        matched_email="dev@example.com",
    )
    committer_match = github._serialize_commit(
        commit=commit,
        platform="github",
        owner="owner",
        repo="repo",
        matched_email="integrator@example.com",
    )

    assert author_match["matched_roles"] == [
        {
            "role": "author",
            "email": "dev@example.com",
            "name": "Author Name",
            "date": "2026-01-02T03:04:05Z",
            "github_login": "dev-login",
        }
    ]
    assert committer_match["matched_roles"][0]["role"] == "committer"
    assert committer_match["git_committer"]["github_login"] == "integrator-login"
    assert committer_match["commit"]["committer"]["email"] == "integrator@example.com"


@pytest.mark.asyncio
async def test_evaluate_global_github_scores_email_matched_commits(tmp_path, monkeypatch):
    commit = github._serialize_commit(
        commit={
            "sha": "c" * 40,
            "html_url": "https://github.com/owner/repo/commit/" + "c" * 40,
            "commit": {
                "author": {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "date": "2026-01-02T03:04:05Z",
                },
                "committer": {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "date": "2026-01-02T03:05:05Z",
                },
                "message": "feat: add global evaluator",
            },
            "stats": {"additions": 12, "deletions": 2, "total": 14},
            "files": [{"filename": "backend/evaluator/routes/github.py"}],
        },
        platform="github",
        owner="owner",
        repo="repo",
        matched_email="alice@example.com",
    )
    matched_repos = {"github:owner/repo": github._github_repo_item("github", "owner", "repo")}

    class FakeEvaluator:
        def evaluate_engineer(self, *, commits, username, max_commits, load_files):
            assert username == "alice@example.com"
            assert max_commits == 150
            assert load_files is False
            assert commits[0]["commit"]["author"]["email"] == "alice@example.com"
            return {
                "username": username,
                "total_commits_analyzed": len(commits),
                "files_loaded": 0,
                "scores": {"spec_quality": 80, "reasoning": "Matched GitHub global commits."},
                "commits_summary": {
                    "total_additions": 12,
                    "total_deletions": 2,
                    "files_changed": 1,
                    "languages": ["py"],
                },
            }

    class FakeScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            assert kwargs["collaboration_evidence"]["items"] == []
            return FakeEvaluator()

    monkeypatch.setattr(github, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(github, "resolve_plugin_id", lambda plugin: plugin or "zgc_ai_native_2026")
    monkeypatch.setattr(
        github,
        "load_scan_module",
        lambda plugin_id: (SimpleNamespace(version="1.0.0"), FakeScanModule, tmp_path / "scan.py"),
    )
    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    fetch_kwargs = {}

    def fake_fetch_global_github_evidence(emails, **kwargs):
        fetch_kwargs.update(kwargs)
        return {"alice@example.com": [commit]}, matched_repos, [], []

    monkeypatch.setattr(github, "_fetch_global_github_evidence", fake_fetch_global_github_evidence)

    result = await github.evaluate_global_github({
        "emails": "alice@example.com",
        "model": "test-model",
        "plugin": "zgc_ai_native_2026",
        "language": "en-US",
    })

    assert result["success"] is True
    assert result["scope"] == "github_global"
    assert result["summary"]["matched_repo_count"] == 1
    assert result["evaluation"]["plugin"] == "zgc_ai_native_2026"
    assert result["evaluation"]["total_commits_analyzed"] == 1
    assert result["evaluation"]["evidence_links"][0]["url"].endswith("/commit/" + "c" * 40)
    assert fetch_kwargs["max_commits_per_role"] == 10


@pytest.mark.asyncio
async def test_evaluate_global_github_caches_matched_repo_evidence_to_xdg(tmp_path, monkeypatch):
    commit = github._serialize_commit(
        commit={
            "sha": "9" * 40,
            "html_url": "https://github.com/owner/repo/commit/" + "9" * 40,
            "commit": {
                "author": {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "date": "2026-03-01T00:00:00Z",
                },
                "committer": {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "date": "2026-03-01T00:01:00Z",
                },
                "message": "feat: cache github evidence",
            },
            "stats": {"additions": 4, "deletions": 1, "total": 5},
            "files": [{"filename": "app.py"}],
        },
        platform="github",
        owner="owner",
        repo="repo",
        matched_email="alice@example.com",
    )
    matched_repos = {"github:owner/repo": github._github_repo_item("github", "owner", "repo")}
    collaboration_items = [
        {
            "source": "pr_discussions",
            "label": "PR #3: cache evidence",
            "detail": "pull request discussed by GitHub login",
            "url": "https://github.com/owner/repo/pull/3",
            "updated_at": "2026-03-01T00:02:00Z",
            "platform": "github",
            "owner": "owner",
            "repo": "repo",
            "repo_full_name": "owner/repo",
            "repo_url": "https://github.com/owner/repo",
            "github_login": "alice",
        }
    ]

    class FakeEvaluator:
        def evaluate_engineer(self, *, commits, username, max_commits, load_files):
            return {
                "username": username,
                "total_commits_analyzed": len(commits),
                "files_loaded": 0,
                "scores": {},
            }

    class FakeScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            return FakeEvaluator()

    monkeypatch.setattr(github, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(github, "resolve_plugin_id", lambda plugin: plugin or "zgc_ai_native_2026")
    monkeypatch.setattr(
        github,
        "load_scan_module",
        lambda plugin_id: (SimpleNamespace(version="1.0.0"), FakeScanModule, tmp_path / "scan.py"),
    )
    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        github,
        "_fetch_global_github_evidence",
        lambda emails, **kwargs: ({"alice@example.com": [commit]}, matched_repos, collaboration_items, []),
    )

    result = await github.evaluate_global_github({"emails": "alice@example.com"})

    repo_dir = tmp_path / "github" / "owner" / "repo"
    assert result["cache"]["github_xdg_cache"]["repo_count"] == 1
    assert (repo_dir / "commits" / f"{'9' * 40}.json").exists()
    commits_index = json.loads((repo_dir / "commits_index.json").read_text(encoding="utf-8"))
    assert commits_index[0]["sha"] == "9" * 40
    collaboration_cache = json.loads((repo_dir / "collaboration_evidence.json").read_text(encoding="utf-8"))
    assert collaboration_cache["items"][0]["url"] == "https://github.com/owner/repo/pull/3"
    assert json.loads((repo_dir / "repo_info.json").read_text(encoding="utf-8"))["platform"] == "github"


@pytest.mark.asyncio
async def test_evaluate_global_github_passes_requested_commit_limit(tmp_path, monkeypatch):
    commit = github._serialize_commit(
        commit={
            "sha": "d" * 40,
            "html_url": "https://github.com/owner/repo/commit/" + "d" * 40,
            "commit": {
                "author": {"name": "Alice", "email": "alice@example.com"},
                "committer": {"name": "Alice", "email": "alice@example.com"},
                "message": "feat: tune github limit",
            },
            "stats": {"additions": 1, "deletions": 0, "total": 1},
            "files": [],
        },
        platform="github",
        owner="owner",
        repo="repo",
        matched_email="alice@example.com",
    )
    matched_repos = {"github:owner/repo": github._github_repo_item("github", "owner", "repo")}

    class FakeEvaluator:
        def evaluate_engineer(self, *, commits, username, max_commits, load_files):
            return {
                "username": username,
                "total_commits_analyzed": len(commits),
                "files_loaded": 0,
                "scores": {},
            }

    class FakeScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            return FakeEvaluator()

    fetch_kwargs = {}

    def fake_fetch_global_github_evidence(emails, **kwargs):
        fetch_kwargs.update(kwargs)
        return {"alice@example.com": [commit]}, matched_repos, [], []

    monkeypatch.setattr(github, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(github, "resolve_plugin_id", lambda plugin: plugin or "zgc_ai_native_2026")
    monkeypatch.setattr(
        github,
        "load_scan_module",
        lambda plugin_id: (SimpleNamespace(version="1.0.0"), FakeScanModule, tmp_path / "scan.py"),
    )
    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(github, "_fetch_global_github_evidence", fake_fetch_global_github_evidence)

    result = await github.evaluate_global_github({
        "emails": "alice@example.com",
        "max_github_commits_per_role": 25,
    })

    assert result["success"] is True
    assert fetch_kwargs["max_commits_per_role"] == 25


@pytest.mark.asyncio
async def test_evaluate_global_github_caps_requested_commit_limit_at_100(tmp_path, monkeypatch):
    commit = github._serialize_commit(
        commit={
            "sha": "e" * 40,
            "html_url": "https://github.com/owner/repo/commit/" + "e" * 40,
            "commit": {
                "author": {"name": "Alice", "email": "alice@example.com"},
                "committer": {"name": "Alice", "email": "alice@example.com"},
                "message": "feat: cap github limit",
            },
            "stats": {"additions": 1, "deletions": 0, "total": 1},
            "files": [],
        },
        platform="github",
        owner="owner",
        repo="repo",
        matched_email="alice@example.com",
    )
    matched_repos = {"github:owner/repo": github._github_repo_item("github", "owner", "repo")}

    class FakeEvaluator:
        def evaluate_engineer(self, *, commits, username, max_commits, load_files):
            return {
                "username": username,
                "total_commits_analyzed": len(commits),
                "files_loaded": 0,
                "scores": {},
            }

    class FakeScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            return FakeEvaluator()

    fetch_kwargs = {}

    def fake_fetch_global_github_evidence(emails, **kwargs):
        fetch_kwargs.update(kwargs)
        return {"alice@example.com": [commit]}, matched_repos, [], []

    monkeypatch.setattr(github, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(github, "resolve_plugin_id", lambda plugin: plugin or "zgc_ai_native_2026")
    monkeypatch.setattr(
        github,
        "load_scan_module",
        lambda plugin_id: (SimpleNamespace(version="1.0.0"), FakeScanModule, tmp_path / "scan.py"),
    )
    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(github, "_fetch_global_github_evidence", fake_fetch_global_github_evidence)

    result = await github.evaluate_global_github({
        "emails": "alice@example.com",
        "max_github_commits_per_role": 250,
    })

    assert result["success"] is True
    assert fetch_kwargs["max_commits_per_role"] == 100


@pytest.mark.asyncio
async def test_evaluate_global_github_scores_profile_identity_without_email(tmp_path, monkeypatch):
    commit = github._serialize_commit(
        commit={
            "sha": "7" * 40,
            "html_url": "https://github.com/alice/project/commit/" + "7" * 40,
            "commit": {
                "author": {"name": "Alice", "email": "alice@users.noreply.github.com"},
                "committer": {"name": "Alice", "email": "alice@users.noreply.github.com"},
                "message": "feat: profile evidence",
            },
            "author": {"login": "alice"},
            "committer": {"login": "alice"},
            "stats": {"additions": 3, "deletions": 0, "total": 3},
            "files": [],
        },
        platform="github",
        owner="alice",
        repo="project",
        matched_login="alice",
    )
    matched_repos = {"github:alice/project": github._github_repo_item("github", "alice", "project")}

    class FakeEvaluator:
        def evaluate_engineer(self, *, commits, username, max_commits, load_files):
            assert username == "github:alice"
            assert commits[0]["matched_identity"] == "@alice"
            return {
                "username": username,
                "total_commits_analyzed": len(commits),
                "files_loaded": 0,
                "scores": {},
            }

    class FakeScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            return FakeEvaluator()

    fetch_kwargs = {}

    def fake_fetch_global_github_evidence(emails, **kwargs):
        fetch_kwargs.update(kwargs)
        return {"github:alice": [commit]}, matched_repos, [], []

    monkeypatch.setattr(github, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(github, "resolve_plugin_id", lambda plugin: plugin or "zgc_ai_native_2026")
    monkeypatch.setattr(
        github,
        "load_scan_module",
        lambda plugin_id: (SimpleNamespace(version="1.0.0"), FakeScanModule, tmp_path / "scan.py"),
    )
    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(github, "_fetch_global_github_evidence", fake_fetch_global_github_evidence)

    result = await github.evaluate_global_github({"github_profiles": ["https://github.com/alice"]})

    assert result["success"] is True
    assert result["emails"] == []
    assert result["identity_keys"] == ["github:alice"]
    assert result["evaluation"]["email"] == ""
    assert result["evaluation"]["identity_keys"] == ["github:alice"]
    assert fetch_kwargs["github_profiles"] == ["https://github.com/alice"]


@pytest.mark.asyncio
async def test_stream_global_github_evaluation_emits_sections_and_result(tmp_path, monkeypatch):
    commit = github._serialize_commit(
        commit={
            "sha": "f" * 40,
            "html_url": "https://github.com/owner/repo/commit/" + "f" * 40,
            "commit": {
                "author": {"name": "Alice", "email": "alice@example.com"},
                "committer": {"name": "Alice", "email": "alice@example.com"},
                "message": "feat: stream github evaluation",
            },
            "stats": {"additions": 1, "deletions": 0, "total": 1},
            "files": [],
        },
        platform="github",
        owner="owner",
        repo="repo",
        matched_email="alice@example.com",
    )
    matched_repos = {"github:owner/repo": github._github_repo_item("github", "owner", "repo")}

    class FakeEvaluator:
        def evaluate_engineer(self, *, commits, username, max_commits, load_files):
            return {
                "username": username,
                "total_commits_analyzed": len(commits),
                "files_loaded": 0,
                "scores": {},
            }

    class FakeScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            return FakeEvaluator()

    monkeypatch.setattr(github, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(github, "resolve_plugin_id", lambda plugin: plugin or "zgc_ai_native_2026")
    monkeypatch.setattr(
        github,
        "load_scan_module",
        lambda plugin_id: (SimpleNamespace(version="1.0.0"), FakeScanModule, tmp_path / "scan.py"),
    )
    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        github,
        "_fetch_global_github_evidence",
        lambda emails, **kwargs: ({"alice@example.com": [commit]}, matched_repos, [], []),
    )

    chunks = [
        chunk
        async for chunk in github._stream_global_github_evaluation({"emails": "alice@example.com"})
    ]
    output = "".join(chunks)

    assert "event: section" in output
    assert "event: result" in output
    assert "GitHub 证据采集完成" in output
    assert '"success":true' in output
