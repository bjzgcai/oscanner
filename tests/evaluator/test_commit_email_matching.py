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


def test_simple_plugin_filters_by_email_identity():
    from plugins.zgc_simple.scan import CommitEvaluatorModerate

    evaluator = CommitEvaluatorModerate(api_key="test", data_dir=".")
    commit = {"commit": {"author": {"name": "Laptop", "email": "student@example.com"}}}

    assert evaluator._is_commit_by_author(commit, "student@example.com") is True
    assert evaluator._is_commit_by_author(commit, "github-login") is False
