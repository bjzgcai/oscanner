from evaluator.services.profile_sampling import (
    annotate_evaluation, candidate_window, file_category, sample_profile_commits,
)


def commit(repo, sha, path="src/train.py", year=2020):
    return {"platform": "github", "repo_full_name": repo, "repo_url": f"https://github.com/{repo}",
            "sha": sha, "date": f"{year}-01-01T00:00:00Z", "matched_email": "a@example.com",
            "files": [{"filename": path, "patch": f"+assert output_{sha}", "additions": 1}]}


def test_older_engineering_survives_documentation_flood():
    items = [commit("a/repo", f"doc{i}", "README.md", 2026) for i in range(100)]
    items += [commit("a/repo", f"code{i}", year=2020 + i) for i in range(5)]
    selected, summary = sample_profile_commits(items, 5)
    assert summary["engineering_commit_count"] >= 4
    assert summary["documentation_only_commit_count"] <= 1
    assert all(c["files"][0]["patch"] for c in selected)


def test_repository_cap_and_year_diversity():
    items = [commit(f"a/r{r}", f"{r}-{i}", year=2000 + i) for r in range(4) for i in range(20)]
    selected, summary = sample_profile_commits(items, 20)
    assert len(selected) == 20
    assert summary["repository_coverage"] == 4
    assert max(sum(c["repo_full_name"] == f"a/r{r}" for c in selected) for r in range(4)) <= 6
    assert len({c["committed_at"][:4] for c in selected}) > 1


def test_missing_details_and_broad_attribution_are_low_confidence():
    items = [commit("a/r", str(i)) for i in range(10)]
    for c in items:
        c.pop("matched_email")
    _, summary = sample_profile_commits(items, 10)
    assert summary["evidence_confidence"] == "low"
    items[0]["files"] = []
    selected, summary = sample_profile_commits(items, 10)
    assert summary["detail_complete_count"] == 9
    result = annotate_evaluation({"scores": {"quality": 15}}, summary, selected)
    assert result["assessment_status"] == "insufficient_evidence"
    assert result["scores"]["quality"] == 15


def test_paths_not_messages_control_classification():
    assert file_category(".github/workflows/test.yml") == "engineering_config"
    assert file_category("tests/test_train.py") == "test_quality"
    assert file_category("docs/adr/001.md") == "architecture_documentation"
    assert file_category("dist/bundle.js") == "generated_or_low_signal"
    assert file_category("config/unknown.blob") == "unknown"


def test_identical_shas_across_forks_deduplicate_but_reverts_remain():
    original = commit("a/r", "abc")
    mirrored = commit("b/r", "abc")
    revert = {**commit("a/r", "def"), "message": "Revert abc"}
    selected, _ = sample_profile_commits([original, mirrored, revert], 10)
    assert {c["sha"] for c in selected} == {"abc", "def"}


def test_candidate_budget_covers_old_and_new_across_repos():
    items = [commit(f"a/{r}", f"{r}-{i}", year=2000 + i) for r in range(3) for i in range(20)]
    selected = candidate_window(items, 12)
    assert len(selected) == 12
    assert len({c["repo_full_name"] for c in selected}) == 3
    assert any(c["date"].startswith("2000") for c in selected)
    assert any(c["date"].startswith("2019") for c in selected)


def test_exact_reapplied_patch_counts_once_without_merging_distinct_changes():
    first = commit("a/r", "abc")
    reapplied = {**first, "sha": "def"}
    distinct = commit("a/r", "ghi")
    selected, _ = sample_profile_commits([first, reapplied, distinct], 10)
    assert len(selected) == 2


def test_docs_only_and_unknown_files_cannot_be_high_confidence():
    docs = [commit("a/r", str(i), "README.md") for i in range(20)]
    selected, summary = sample_profile_commits(docs, 10)
    assert len(selected) == 10
    assert summary["engineering_commit_count"] == 0
    assert annotate_evaluation({}, summary)["assessment_status"] == "insufficient_evidence"
