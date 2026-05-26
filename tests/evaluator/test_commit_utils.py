from evaluator.utils.commit_utils import is_commit_by_author


def test_is_commit_by_author_matches_github_author_login():
    commit = {
        "commit": {
            "author": {
                "name": "Evan You",
                "email": "yyou@example.com",
            },
        },
        "author": {
            "login": "yyx990803",
            "name": "Evan You",
        },
    }

    assert is_commit_by_author(commit, "yyx990803") is True


def test_is_commit_by_author_matches_github_committer_login():
    commit = {
        "commit": {
            "author": {
                "name": "Evan You",
                "email": "yyou@example.com",
            },
        },
        "author": None,
        "committer": {
            "login": "yyx990803",
            "name": "Evan You",
        },
    }

    assert is_commit_by_author(commit, "yyx990803") is True
