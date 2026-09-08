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
        "github_inputs": "Alice@Example.com, octocat, github.com/openai/codex.git",
    })

    assert parsed["emails"] == ["alice@example.com"]
    assert parsed["github_profiles"] == ["https://github.com/octocat"]
    assert parsed["github_repos"] == ["https://github.com/openai/codex"]


def test_github_repo_commit_collection_paginates_to_requested_limit(monkeypatch):
    calls = []

    def fake_get_json(client, url, *, warnings, params=None):
        calls.append(params)
        page = params["page"]
        return [{"sha": f"{page}-{index}"} for index in range(params["per_page"])]

    monkeypatch.setattr(github, "_github_get_json", fake_get_json)

    commits = github._github_paginated_repo_commits(
        object(),
        owner="owner",
        repo="repo",
        warnings=[],
        max_commits=250,
    )

    assert len(commits) == 250
    assert calls == [
        {"per_page": 100, "page": 1},
        {"per_page": 100, "page": 2},
        {"per_page": 50, "page": 3},
    ]


def test_github_request_retries_after_rate_limit_reset(monkeypatch):
    request = github.httpx.Request("GET", "https://api.github.com/rate_limit")
    responses = [
        github.httpx.Response(
            403,
            request=request,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "101"},
            json={"message": "API rate limit exceeded"},
        ),
        github.httpx.Response(200, request=request, json={"ok": True}),
    ]

    class FakeClient:
        def get(self, url, params=None):
            return responses.pop(0)

    sleeps = []
    monkeypatch.setattr(github.time, "time", lambda: 100)
    monkeypatch.setattr(github.time, "sleep", sleeps.append)

    response = github._github_request_with_rate_limit_retry(FakeClient(), str(request.url))

    assert response.status_code == 200
    assert sleeps == [2.0]


def test_github_commit_collection_marks_failed_page_incomplete(monkeypatch):
    warnings = []
    monkeypatch.setattr(github, "_github_get_json", lambda *args, **kwargs: None)

    commits = github._github_paginated_repo_commits(
        object(),
        owner="owner",
        repo="repo",
        warnings=warnings,
        max_commits=100,
    )

    assert commits == []
    assert warnings[0].startswith(github.GITHUB_COLLECTION_INCOMPLETE_PREFIX)


def test_github_incomplete_payload_omits_authoritative_available_count():
    payload = github._github_global_analysis_payload(
        emails=["alice@example.com"],
        commits_by_email={"alice@example.com": [{"platform": "github", "repo_full_name": "owner/repo", "sha": "1"}]},
        matched_repos={"github:owner/repo": github._github_repo_item("github", "owner", "repo")},
        collaboration_items=[],
        warnings=[f"{github.GITHUB_COLLECTION_INCOMPLETE_PREFIX} github rate limit exhausted"],
    )

    assert payload["success"] is False
    assert payload["incomplete"] is True
    assert payload["summary"]["commit_count_is_authoritative"] is False
    assert payload["summary"]["partial_commit_count"] == 1
    assert "available_commit_count" not in payload["summary"]


def test_github_commit_index_accepts_empty_message():
    entry = github._github_commit_index_entry({"sha": "a" * 40, "commit": {"message": ""}})

    assert entry["sha"] == "a" * 40
    assert entry["message"] == ""


def test_github_profile_collection_reuses_complete_cache_and_stops_at_known_sha(tmp_path, monkeypatch):
    repo_dir = tmp_path / "github" / "owner" / "repo"
    repo_dir.mkdir(parents=True)
    cached_sha = "a" * 40
    new_sha = "b" * 40
    cached_commit = github._serialize_commit(
        commit={
            "sha": cached_sha,
            "commit": {"author": {"email": "old@example.com"}, "committer": {}, "message": "cached"},
        },
        platform="github",
        owner="owner",
        repo="repo",
    )
    (repo_dir / "commits_list.json").write_text(json.dumps([cached_commit]), encoding="utf-8")
    (repo_dir / "sync_state.json").write_text(json.dumps({"collection_complete": True}), encoding="utf-8")
    new_commit = {
        "sha": new_sha,
        "commit": {"author": {"email": "new@example.com"}, "committer": {}, "message": "new"},
    }
    cached_list_item = {
        "sha": cached_sha,
        "commit": {"author": {"email": "old@example.com"}, "committer": {}, "message": "cached"},
    }
    commit_page_calls = []

    def fake_get_json(client, url, *, warnings, params=None):
        if url.endswith("/users/owner/repos"):
            return [{"full_name": "owner/repo"}]
        if url.endswith("/repos/owner/repo/commits"):
            commit_page_calls.append(params["page"])
            return [new_commit, cached_list_item]
        return []

    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(github, "_github_get_json", fake_get_json)
    monkeypatch.setattr(
        github,
        "_github_commit_detail",
        lambda *args, **kwargs: pytest.fail("profile collection should not fetch per-commit details"),
    )

    commits, matched_repos = github._github_profile_repo_commits(
        object(), login="owner", warnings=[]
    )

    assert commit_page_calls == [1]
    assert {_commit["sha"] for _commit in commits} == {new_sha, cached_sha}
    assert matched_repos["github:owner/repo"]["repo_full_name"] == "owner/repo"


def test_github_profile_fork_without_submitted_email_contributes_no_commits(tmp_path, monkeypatch):
    fetched_urls = []

    def fake_get_json(client, url, *, warnings, params=None):
        fetched_urls.append(url)
        if url.endswith("/users/owner/repos"):
            return [{"full_name": "owner/forked", "fork": True}]
        return []

    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(github, "_github_get_json", fake_get_json)

    commits, matched_repos = github._github_profile_repo_commits(
        object(), login="owner", emails=[], warnings=[]
    )

    assert commits == []
    assert matched_repos["github:owner/forked"]["fork"] is True
    assert not any(url.endswith("/repos/owner/forked/commits") for url in fetched_urls)


def test_github_profile_fork_keeps_only_submitted_email_matches(tmp_path, monkeypatch):
    matched_sha = "c" * 40
    unmatched_sha = "d" * 40
    commits_page = [
        {
            "sha": matched_sha,
            "commit": {
                "author": {"email": "requested@example.com"},
                "committer": {"email": "other@example.com"},
                "message": "matched fork work",
            },
        },
        {
            "sha": unmatched_sha,
            "commit": {
                "author": {"email": "upstream@example.com"},
                "committer": {"email": "upstream@example.com"},
                "message": "inherited upstream history",
            },
        },
    ]

    def fake_get_json(client, url, *, warnings, params=None):
        if url.endswith("/users/owner/repos"):
            return [{"full_name": "owner/forked", "fork": True}]
        if url.endswith("/repos/owner/forked/commits"):
            return commits_page
        return []

    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(github, "_github_get_json", fake_get_json)
    monkeypatch.setattr(
        github,
        "_github_commit_detail",
        lambda *args, **kwargs: pytest.fail("fork email filtering should use commit-list identities"),
    )

    commits, matched_repos = github._github_profile_repo_commits(
        object(),
        login="owner",
        emails=["Requested@Example.com"],
        warnings=[],
    )

    assert [commit["sha"] for commit in commits] == [matched_sha]
    assert commits[0]["matched_email"] == "requested@example.com"
    assert commits[0]["matched_identity"] == "github:owner"
    assert commits[0]["source"] == "github_profile_fork_email_commits"
    assert matched_repos["github:owner/forked"]["fork"] is True


def test_github_repository_commits_matches_supplied_email_without_owner_fallback(monkeypatch):
    sha = "e" * 40
    list_commit = {"sha": sha}
    detail_commit = {
        "sha": sha,
        "html_url": f"https://github.com/wyj4real/auto-researcher/commit/{sha}",
        "commit": {
            "author": {
                "name": "Qinzhong Tian",
                "email": "56856603+LoadStar822@users.noreply.github.com",
                "date": "2026-06-01T00:00:00Z",
            },
            "committer": {
                "name": "Qinzhong Tian",
                "email": "56856603+LoadStar822@users.noreply.github.com",
                "date": "2026-06-01T00:00:00Z",
            },
            "message": "feat: initial research agent",
        },
        "author": {"login": "LoadStar822"},
        "committer": {"login": "LoadStar822"},
        "stats": {"additions": 5, "deletions": 1, "total": 6},
        "files": [{"filename": "README.md"}],
    }
    calls = []

    def fake_get_json(client, url, *, warnings, params=None):
        calls.append(params)
        return [list_commit]

    monkeypatch.setattr(github, "_github_get_json", fake_get_json)
    monkeypatch.setattr(github, "_github_commit_detail", lambda *args, **kwargs: detail_commit)

    commits_by_identity, matched_repos = github._github_repository_commits(
        object(),
        repo_urls=["https://github.com/wyj4real/auto-researcher"],
        emails=["56856603+loadstar822@users.noreply.github.com"],
        warnings=[],
        max_commits_per_repo=100,
    )

    assert calls == [
        {"per_page": 100, "page": 1},
    ]
    email_key = "56856603+loadstar822@users.noreply.github.com"
    assert list(commits_by_identity) == [email_key]
    assert commits_by_identity[email_key][0]["matched_email"] == email_key
    assert commits_by_identity[email_key][0]["matched_login"] == ""
    assert commits_by_identity[email_key][0]["source"] == "github_repo_email_commits"
    assert commits_by_identity[email_key][0]["repo_full_name"] == "wyj4real/auto-researcher"
    assert matched_repos["github:wyj4real/auto-researcher"]["repo_url"] == "https://github.com/wyj4real/auto-researcher"


def test_github_repository_all_commits_fetches_repo_without_email_filter(monkeypatch):
    sha = "1" * 40
    detail_commit = {
        "sha": sha,
        "html_url": f"https://github.com/owner/repo/commit/{sha}",
        "commit": {
            "author": {
                "name": "Any Author",
                "email": "any@example.com",
                "date": "2026-06-01T00:00:00Z",
            },
            "committer": {
                "name": "Any Committer",
                "email": "committer@example.com",
                "date": "2026-06-01T00:01:00Z",
            },
            "message": "feat: visible commit",
        },
        "stats": {"additions": 2, "deletions": 0, "total": 2},
        "files": [{"filename": "README.md"}],
    }
    calls = []

    def fake_get_json(client, url, *, warnings, params=None):
        calls.append((url, params))
        return [{"sha": sha}]

    monkeypatch.setattr(github, "_github_get_json", fake_get_json)
    monkeypatch.setattr(github, "_github_commit_detail", lambda *args, **kwargs: detail_commit)

    commits_by_identity, matched_repos = github._github_repository_all_commits(
        object(),
        repo_urls=["https://github.com/owner/repo"],
        warnings=[],
        max_commits_per_repo=1,
    )

    assert calls == [
        (
            "https://api.github.com/repos/owner/repo/commits",
            {"per_page": 1, "page": 1},
        )
    ]
    identity_key = "github:owner/repo"
    assert list(commits_by_identity) == [identity_key]
    assert commits_by_identity[identity_key][0]["matched_email"] == ""
    assert commits_by_identity[identity_key][0]["matched_identity"] == identity_key
    assert commits_by_identity[identity_key][0]["source"] == "github_repo_all_commits"
    assert matched_repos[identity_key]["repo_url"] == "https://github.com/owner/repo"


def test_fetch_global_github_evidence_expands_owner_url_without_emails(tmp_path, monkeypatch):
    sha = "2" * 40
    detail_commit = {
        "files": [{"filename": "src/main.py", "patch": "+print(1)"}],
        "sha": sha,
        "html_url": f"https://github.com/owner/repo/commit/{sha}",
        "commit": {
            "author": {"name": "Any Author", "email": "any@example.com"},
            "committer": {"name": "Any Committer", "email": "committer@example.com"},
            "message": "feat: owner scoped commit",
        },
    }
    fetched_urls = []
    detail_calls = []

    def fetch_detail(*args, **kwargs):
        detail_calls.append(kwargs["sha"])
        return detail_commit

    def fake_get_json(client, url, *, warnings, params=None):
        fetched_urls.append(url)
        if url.endswith("/users/owner"):
            return {"login": "owner", "html_url": "https://github.com/owner"}
        if url.endswith("/users/owner/repos"):
            return [{"full_name": "owner/repo"}]
        if url.endswith("/repos/owner/repo/commits") and params and params.get("page") == 1:
            return [{key: value for key, value in detail_commit.items() if key != "files"}]
        if url.endswith("/repos/owner/repo/commits"):
            return []
        return []

    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(github, "_github_rate_limit_preflight", lambda *args, **kwargs: True)
    monkeypatch.setattr(github, "_github_get_json", fake_get_json)
    monkeypatch.setattr(github, "_github_commit_detail", fetch_detail)
    monkeypatch.setattr(github, "_collaboration_items_for_repo", lambda **kwargs: ([{
        "source": "pr_discussions",
        "label": "PR #1",
        "detail": "1 discussion comments",
        "url": "https://github.com/owner/repo/pull/1",
        "platform": "github",
        "owner": "owner",
        "repo": "repo",
        "repo_full_name": "owner/repo",
        "repo_url": "https://github.com/owner/repo",
    }], []))
    monkeypatch.setattr(github, "_github_commit_linked_evidence", lambda *args, **kwargs: [])
    monkeypatch.setattr(github, "_github_evidence_for_logins", lambda *args, **kwargs: [])

    commits_by_identity, matched_repos, collaboration_items, warnings = github._fetch_global_github_evidence(
        [],
        github_profiles=["https://github.com/owner"],
        github_repos=[],
        max_commits_per_role=1,
    )

    assert warnings == []
    assert "https://api.github.com/users/owner/repos" in fetched_urls
    assert detail_calls == [sha]
    assert commits_by_identity["github:owner"][0]["files"][0]["patch"] == "+print(1)"
    assert list(commits_by_identity) == ["github:owner"]
    assert commits_by_identity["github:owner"][0]["sha"] == sha
    assert commits_by_identity["github:owner"][0]["matched_identity"] == "github:owner"
    assert commits_by_identity["github:owner"][0]["source"] == "github_profile_all_commits"
    assert matched_repos["github:owner/repo"]["repo_full_name"] == "owner/repo"
    assert collaboration_items[0]["url"] == "https://github.com/owner/repo/pull/1"


def test_fetch_global_github_profile_keeps_all_commits_when_email_is_supplied(tmp_path, monkeypatch):
    sha = "3" * 40
    detail_commit = {
        "files": [{"filename": "src/main.py", "patch": "+print(1)"}],
        "sha": sha,
        "html_url": f"https://github.com/owner/repo/commit/{sha}",
        "commit": {
            "author": {"name": "Different Identity", "email": "different@example.com"},
            "committer": {"name": "Another Identity", "email": "another@example.com"},
            "message": "feat: profile-wide evidence",
        },
    }

    def fake_get_json(client, url, *, warnings, params=None):
        if url.endswith("/users/owner"):
            return {"login": "owner", "html_url": "https://github.com/owner"}
        if url.endswith("/users/owner/repos"):
            return [{"full_name": "owner/repo"}]
        if url.endswith("/repos/owner/repo/commits") and params and params.get("page") == 1:
            return [detail_commit]
        return []

    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(github, "_github_rate_limit_preflight", lambda *args, **kwargs: True)
    monkeypatch.setattr(github, "_github_get_json", fake_get_json)
    monkeypatch.setattr(github, "_github_commit_detail", lambda *args, **kwargs: detail_commit)
    monkeypatch.setattr(github, "_github_search_items", lambda *args, **kwargs: [])
    monkeypatch.setattr(github, "_collaboration_items_for_repo", lambda **kwargs: ([], []))
    monkeypatch.setattr(github, "_github_commit_linked_evidence", lambda *args, **kwargs: [])
    monkeypatch.setattr(github, "_github_evidence_for_logins", lambda *args, **kwargs: [])

    commits_by_identity, matched_repos, _, warnings = github._fetch_global_github_evidence(
        ["requested@example.com"],
        github_profiles=["https://github.com/owner"],
        max_commits_per_role=10,
    )

    assert warnings == []
    profile_commit = commits_by_identity["github:owner"][0]
    assert profile_commit["sha"] == sha
    assert profile_commit["commit"]["author"]["email"] == "different@example.com"
    assert profile_commit["matched_identity"] == "github:owner"
    assert matched_repos["github:owner/repo"]["repo_full_name"] == "owner/repo"


def test_github_repository_with_email_does_not_fallback_to_unmatched_commits(monkeypatch):
    sha = "4" * 40
    detail_commit = {
        "sha": sha,
        "commit": {
            "author": {"name": "Other", "email": "other@example.com"},
            "committer": {"name": "Other", "email": "other@example.com"},
            "message": "feat: unrelated commit",
        },
    }

    monkeypatch.setattr(
        github,
        "_github_get_json",
        lambda client, url, *, warnings, params=None: [{"sha": sha}],
    )
    monkeypatch.setattr(github, "_github_commit_detail", lambda *args, **kwargs: detail_commit)

    commits_by_identity, matched_repos = github._github_repository_commits(
        object(),
        repo_urls=["https://github.com/owner/repo"],
        emails=["requested@example.com"],
        warnings=[],
        max_commits_per_repo=1,
    )

    assert commits_by_identity == {"requested@example.com": []}
    assert matched_repos["github:owner/repo"]["repo_full_name"] == "owner/repo"


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
    assert result["summary"]["available_commit_count"] == 1
    assert "commit_count" not in result["summary"]
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
            assert max_commits == 1000
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
        "max_github_commits_per_role": 1000,
    })

    assert result["success"] is True
    assert result["scope"] == "github_global"
    assert result["summary"]["matched_repo_count"] == 1
    assert result["evaluation"]["plugin"] == "zgc_ai_native_2026"
    assert result["evaluation"]["total_commits_analyzed"] == 1
    assert result["evaluation"]["evidence_links"][0]["url"].endswith("/commit/" + "c" * 40)
    assert fetch_kwargs["max_commits_per_role"] == 1000


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
async def test_evaluate_global_github_caps_requested_commit_limit_at_1000(tmp_path, monkeypatch):
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
        "max_github_commits_per_role": 2500,
    })

    assert result["success"] is True
    assert fetch_kwargs["max_commits_per_role"] == 1000


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
            assert username == "github:alice,alice"
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


def test_global_github_evaluation_keeps_email_and_profile_identities(tmp_path, monkeypatch):
    captured = {}

    class FakeEvaluator:
        def evaluate_engineer(self, *, commits, username, max_commits, load_files):
            captured.update({
                "commits": commits,
                "username": username,
                "max_commits": max_commits,
                "load_files": load_files,
            })
            return {"total_commits_analyzed": len(commits), "scores": {}}

    class FakeScanModule:
        @staticmethod
        def create_commit_evaluator(**kwargs):
            return FakeEvaluator()

    commits = [
        {"sha": "1" * 40, "matched_email": "alice@example.com"},
        {"sha": "2" * 40, "matched_login": "alice", "matched_identity": "@alice"},
    ]

    monkeypatch.setattr(github, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(github, "_global_github_evidence_links", lambda commits: [])

    result = github._evaluate_global_github_commits(
        api_key="test-key",
        emails=["alice@example.com"],
        identity_keys=["alice@example.com", "github:alice"],
        model="test-model",
        plugin_id="zgc_ai_native_2026",
        language="en-US",
        meta=None,
        scan_mod=FakeScanModule,
        all_commits=commits,
        collaboration_items=[],
        commit_limit=1000,
    )

    assert captured["username"] == "alice@example.com,github:alice,alice"
    assert captured["commits"] == commits
    assert captured["max_commits"] == 1000
    assert captured["load_files"] is False
    assert result["emails"] == ["alice@example.com"]
    assert result["identity_keys"] == ["alice@example.com", "github:alice"]


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
