from evaluator.utils import get_emails_from_commit, is_commit_by_author


def test_email_identity_matches_commit_email_not_display_name():
    commit = {
        "commit": {
            "author": {"name": "LAPTOP-3GRH3D06\\dxc", "email": "tcmdxc430@gmail.com"},
            "committer": {"name": "GitHub", "email": "noreply@github.com"},
        }
    }

    assert get_emails_from_commit(commit) == ["tcmdxc430@gmail.com", "noreply@github.com"]
    assert is_commit_by_author(commit, "tcmdxc430@gmail.com") is True
    assert is_commit_by_author(commit, "tcmdxc430-rgb") is False
    assert is_commit_by_author(commit, "LAPTOP-3GRH3D06\\dxc") is True


def test_ai_native_plugin_filters_by_email_identity():
    from plugins.zgc_ai_native_2026.scan import CommitEvaluatorModerate

    evaluator = CommitEvaluatorModerate(api_key="test", data_dir=".")
    commit = {"commit": {"author": {"name": "Laptop", "email": "student@example.com"}}}

    assert evaluator._is_commit_by_author(commit, "student@example.com") is True
    assert evaluator._is_commit_by_author(commit, "github-login") is False


def test_ai_native_plugin_matches_explicit_profile_attribution():
    from plugins.zgc_ai_native_2026.scan import CommitEvaluatorModerate

    evaluator = CommitEvaluatorModerate(api_key="test", data_dir=".")
    commit = {
        "commit": {
            "author": {"name": "Student", "email": "private@users.noreply.github.com"},
        },
        "matched_login": "github-login",
        "matched_identity": "@github-login",
        "matched_roles": [{"role": "author", "github_login": "github-login"}],
    }

    assert evaluator._is_commit_by_author(
        commit,
        "student@example.com,github:github-login,github-login",
    ) is True


def test_ai_native_plugin_filters_identity_before_commit_cap(monkeypatch):
    from plugins.zgc_ai_native_2026.scan import CommitEvaluatorModerate

    evaluator = CommitEvaluatorModerate(api_key="test", data_dir=".")
    unrelated = {
        "sha": "1" * 40,
        "commit": {"author": {"name": "Other", "email": "other@example.com"}},
    }
    attributed = {
        "sha": "2" * 40,
        "commit": {"author": {"name": "Student", "email": "private@example.com"}},
        "matched_login": "student-login",
    }
    monkeypatch.setattr(
        evaluator,
        "_evaluate_engineer_standard",
        lambda commits, username, load_files: {
            "username": username,
            "total_commits_analyzed": len(commits),
            "commits": commits,
        },
    )
    monkeypatch.setattr(evaluator, "_commits_exceed_prompt_budget", lambda *args, **kwargs: False)

    result = evaluator.evaluate_engineer(
        commits=[unrelated, attributed],
        username="student-login",
        max_commits=1,
        load_files=False,
    )

    assert result["total_commits_analyzed"] == 1
    assert result["commits"] == [attributed]
