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
async def test_analyze_gitee_github_collects_cached_commits_by_email(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    repo_dir = data_dir / "github" / "owner" / "repo"
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
          "html_url": "https://github.com/owner/repo/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "commit": {
            "author": {
              "name": "Alice",
              "email": "alice@example.com",
              "date": "2026-01-02T03:04:05Z"
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
