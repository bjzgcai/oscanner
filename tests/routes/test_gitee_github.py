import pytest

from evaluator.routes import gitee_github


def test_parse_email_list_requires_comma_separated_valid_emails():
    assert gitee_github._parse_email_list("Alice@Example.com,bob@example.org") == [
        "alice@example.com",
        "bob@example.org",
    ]

    with pytest.raises(Exception) as exc_info:
        gitee_github._parse_email_list("alice@example.com，bob@example.org")

    assert "Invalid email format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_analyze_gitee_github_collects_cached_gitee_commits_by_author_and_committer_email(tmp_path, monkeypatch):
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

    monkeypatch.setattr(gitee_github, "get_data_dir", lambda: data_dir)
    monkeypatch.setattr(
        gitee_github,
        "_fetch_global_github_evidence",
        lambda emails, **_: ({email: [] for email in emails}, {}, [], []),
    )

    result = await gitee_github.analyze_gitee_github({
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

    author_match = gitee_github._serialize_commit(
        commit=commit,
        platform="github",
        owner="owner",
        repo="repo",
        matched_email="dev@example.com",
    )
    committer_match = gitee_github._serialize_commit(
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
