"""Runner storage path contract tests."""

import asyncio
from pathlib import Path

from repos_runner.services.repo_service import clone as clone_module
from repos_runner.services.repo_service.clone import clone_repository
from repos_runner.services.repo_service.lifecycle import delete_repo, list_repos
from repos_runner.services.repo_service.paths import (
    get_clone_source_dir,
    get_repos_dir,
    repo_storage_key,
)


class _FakeCompletedProcess:
    stdout = ""
    stderr = ""
    returncode = 0


def _fake_run_git(command, *, timeout, cwd=None):
    clone_path = Path(command[-1])
    clone_path.mkdir(parents=True, exist_ok=True)
    (clone_path / "README.md").write_text("cloned", encoding="utf-8")
    return _FakeCompletedProcess()


def _fake_git_output(command, *, timeout, cwd):
    if command == ["git", "rev-parse", "HEAD"]:
        return "abc123"
    if command == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
        return "main"
    raise AssertionError(f"unexpected git output command: {command}")


def test_repos_dir_respects_oscanner_home(monkeypatch, tmp_path):
    monkeypatch.setenv("OSCANNER_HOME", str(tmp_path / "oscanner-home"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert get_repos_dir() == tmp_path / "oscanner-home" / "repos"


def test_clone_source_dir_is_namespaced_by_platform_owner_repo_and_ref(tmp_path):
    repos_dir = tmp_path / "repos"

    assert get_clone_source_dir(
        repos_dir,
        platform="github",
        owner="owner-one",
        repo="demo",
    ) == repos_dir / "github" / "owner-one" / "demo" / "default" / "source"
    assert get_clone_source_dir(
        repos_dir,
        platform="gitee",
        owner="owner-two",
        repo="demo",
        tag="course/lesson 1",
    ) == repos_dir / "gitee" / "owner-two" / "demo" / "tag-course_lesson_1" / "source"
    assert get_clone_source_dir(
        repos_dir,
        platform="gitee",
        owner="owner-two",
        repo="demo",
        branch="feat/update pipelines",
    ) == repos_dir / "gitee" / "owner-two" / "demo" / "branch-feat_update_pipelines" / "source"


def test_clone_repository_avoids_same_repo_name_collisions(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda repo_url: repo_url,
    )
    monkeypatch.setattr(clone_module, "_run_git", _fake_run_git)
    monkeypatch.setattr(clone_module, "_git_output", _fake_git_output)

    github_result = asyncio.run(clone_repository("https://github.com/org/demo"))
    gitee_result = asyncio.run(clone_repository("https://gitee.com/team/demo"))

    assert github_result["repo_name"] == "github/org/demo/default"
    assert gitee_result["repo_name"] == "gitee/team/demo/default"
    assert Path(github_result["clone_path"]) == (
        repos_dir / "github" / "org" / "demo" / "default" / "source"
    )
    assert Path(gitee_result["clone_path"]) == (
        repos_dir / "gitee" / "team" / "demo" / "default" / "source"
    )
    assert Path(github_result["clone_path"]).exists()
    assert Path(gitee_result["clone_path"]).exists()


def test_clone_repository_uses_tree_branch_url_as_checkout_branch(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    git_commands = []

    def _record_run_git(command, *, timeout, cwd=None):
        git_commands.append(command)
        if command[:2] == ["git", "clone"]:
            clone_path = Path(command[-1])
            clone_path.mkdir(parents=True, exist_ok=True)
            (clone_path / "README.md").write_text("cloned", encoding="utf-8")
        return _FakeCompletedProcess()

    def _branch_git_output(command, *, timeout, cwd):
        if command == ["git", "rev-parse", "HEAD"]:
            return "abc123"
        if command == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return "feat/update-gitee-ci-pipelines"
        raise AssertionError(f"unexpected git output command: {command}")

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda repo_url: repo_url,
    )
    monkeypatch.setattr(clone_module, "_run_git", _record_run_git)
    monkeypatch.setattr(clone_module, "_git_output", _branch_git_output)

    result = asyncio.run(
        clone_repository("https://gitee.com/zgcai/oscanner/tree/feat/update-gitee-ci-pipelines")
    )

    clone_command = git_commands[0]
    assert clone_command == [
        "git",
        "clone",
        "--depth",
        "1",
        "--single-branch",
        "--branch",
        "feat/update-gitee-ci-pipelines",
        "https://gitee.com/zgcai/oscanner.git",
        str(repos_dir / "gitee" / "zgcai" / "oscanner" / "branch-feat_update-gitee-ci-pipelines" / "source"),
    ]
    assert result["repo_name"] == "gitee/zgcai/oscanner/branch-feat_update-gitee-ci-pipelines"
    assert result["default_branch"] == "feat/update-gitee-ci-pipelines"


def test_clone_repository_fetches_tag_shallowly(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    git_commands = []
    tag = "v1.2.3"

    def _record_run_git(command, *, timeout, cwd=None):
        git_commands.append((command, cwd))
        if command == ["git", "init", str(repos_dir / "github" / "org" / "demo" / "tag-v1.2.3" / "source")]:
            clone_path = Path(command[-1])
            clone_path.mkdir(parents=True, exist_ok=True)
        return _FakeCompletedProcess()

    def _detached_git_output(command, *, timeout, cwd):
        if command == ["git", "rev-parse", "HEAD"]:
            return "tagged123"
        if command == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return "HEAD"
        raise AssertionError(f"unexpected git output command: {command}")

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda repo_url: repo_url,
    )
    monkeypatch.setattr(clone_module, "_run_git", _record_run_git)
    monkeypatch.setattr(clone_module, "_git_output", _detached_git_output)

    result = asyncio.run(clone_repository("https://github.com/org/demo", tag=tag))

    clone_path = repos_dir / "github" / "org" / "demo" / "tag-v1.2.3" / "source"
    assert git_commands == [
        (["git", "init", str(clone_path)], None),
        (["git", "remote", "add", "origin", "https://github.com/org/demo.git"], clone_path),
        (["git", "fetch", "--depth", "1", "origin", f"refs/tags/{tag}:refs/tags/{tag}"], clone_path),
        (["git", "checkout", f"tags/{tag}"], clone_path),
    ]
    assert result["repo_name"] == "github/org/demo/tag-v1.2.3"
    assert result["default_branch"] == "detached"


def test_clone_repository_fetches_sha_shallowly_before_full_clone(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    git_commands = []
    sha = "abcdef1234567890"

    def _record_run_git(command, *, timeout, cwd=None):
        git_commands.append((command, cwd))
        if command == ["git", "init", str(repos_dir / "github" / "org" / "demo" / f"sha-{sha}" / "source")]:
            clone_path = Path(command[-1])
            clone_path.mkdir(parents=True, exist_ok=True)
        return _FakeCompletedProcess()

    def _detached_git_output(command, *, timeout, cwd):
        if command == ["git", "rev-parse", "HEAD"]:
            return sha
        if command == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return "HEAD"
        raise AssertionError(f"unexpected git output command: {command}")

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda repo_url: repo_url,
    )
    monkeypatch.setattr(clone_module, "_run_git", _record_run_git)
    monkeypatch.setattr(clone_module, "_git_output", _detached_git_output)

    result = asyncio.run(clone_repository("https://github.com/org/demo", sha=sha))

    clone_path = repos_dir / "github" / "org" / "demo" / f"sha-{sha}" / "source"
    assert git_commands == [
        (["git", "init", str(clone_path)], None),
        (["git", "remote", "add", "origin", "https://github.com/org/demo.git"], clone_path),
        (["git", "fetch", "--depth", "1", "--no-tags", "origin", sha], clone_path),
        (["git", "checkout", sha], clone_path),
    ]
    assert result["repo_name"] == f"github/org/demo/sha-{sha}"
    assert result["default_branch"] == "detached"


def test_clone_repository_uses_tree_sha_url_as_checkout_sha(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    git_commands = []
    sha = "9ba36e6a104ab1ffe296e0f71cf596bca12b2d6a"

    def _record_run_git(command, *, timeout, cwd=None):
        git_commands.append((command, cwd))
        expected_init_path = (
            repos_dir / "github" / "bjzgcai" / "oscanner" / f"sha-{sha}" / "source"
        )
        if command == ["git", "init", str(expected_init_path)]:
            clone_path = Path(command[-1])
            clone_path.mkdir(parents=True, exist_ok=True)
        return _FakeCompletedProcess()

    def _detached_git_output(command, *, timeout, cwd):
        if command == ["git", "rev-parse", "HEAD"]:
            return sha
        if command == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return "HEAD"
        raise AssertionError(f"unexpected git output command: {command}")

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda repo_url: repo_url,
    )
    monkeypatch.setattr(clone_module, "_run_git", _record_run_git)
    monkeypatch.setattr(clone_module, "_git_output", _detached_git_output)

    result = asyncio.run(
        clone_repository(f"https://github.com/bjzgcai/oscanner/tree/{sha}")
    )

    clone_path = repos_dir / "github" / "bjzgcai" / "oscanner" / f"sha-{sha}" / "source"
    assert git_commands == [
        (["git", "init", str(clone_path)], None),
        (
            ["git", "remote", "add", "origin", "https://github.com/bjzgcai/oscanner.git"],
            clone_path,
        ),
        (["git", "fetch", "--depth", "1", "--no-tags", "origin", sha], clone_path),
        (["git", "checkout", sha], clone_path),
    ]
    assert result["repo_name"] == f"github/bjzgcai/oscanner/sha-{sha}"
    assert result["default_branch"] == "detached"


def test_clone_repository_falls_back_to_full_clone_when_shallow_sha_fetch_fails(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    git_commands = []
    sha = "abcdef1234567890"

    def _record_run_git(command, *, timeout, cwd=None):
        git_commands.append((command, cwd))
        clone_path = repos_dir / "github" / "org" / "demo" / f"sha-{sha}" / "source"
        if command == ["git", "init", str(clone_path)]:
            clone_path.mkdir(parents=True, exist_ok=True)
        if command == ["git", "fetch", "--depth", "1", "--no-tags", "origin", sha]:
            raise RuntimeError("git fetch failed: server does not allow request for unadvertised object")
        if command[:2] == ["git", "clone"]:
            Path(command[-1]).mkdir(parents=True, exist_ok=True)
        return _FakeCompletedProcess()

    def _detached_git_output(command, *, timeout, cwd):
        if command == ["git", "rev-parse", "HEAD"]:
            return sha
        if command == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return "HEAD"
        raise AssertionError(f"unexpected git output command: {command}")

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda repo_url: repo_url,
    )
    monkeypatch.setattr(clone_module, "_run_git", _record_run_git)
    monkeypatch.setattr(clone_module, "_git_output", _detached_git_output)

    result = asyncio.run(clone_repository("https://github.com/org/demo", sha=sha))

    clone_path = repos_dir / "github" / "org" / "demo" / f"sha-{sha}" / "source"
    assert git_commands == [
        (["git", "init", str(clone_path)], None),
        (["git", "remote", "add", "origin", "https://github.com/org/demo.git"], clone_path),
        (["git", "fetch", "--depth", "1", "--no-tags", "origin", sha], clone_path),
        (["git", "clone", "https://github.com/org/demo.git", str(clone_path)], None),
        (["git", "checkout", sha], clone_path),
    ]
    assert result["repo_name"] == f"github/org/demo/sha-{sha}"
    assert result["default_branch"] == "detached"


def test_clone_repository_retries_transient_git_tls_clone_failure(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    attempts = 0

    def _flaky_run_git(command, *, timeout, cwd=None):
        nonlocal attempts
        if command[:2] == ["git", "clone"]:
            attempts += 1
            if attempts == 1:
                raise RuntimeError(
                    "git clone failed: fatal: unable to access "
                    "'https://github.com/org/demo/': GnuTLS recv error (-110): "
                    "The TLS connection was non-properly terminated."
                )
            clone_path = Path(command[-1])
            clone_path.mkdir(parents=True, exist_ok=True)
            (clone_path / "README.md").write_text("cloned", encoding="utf-8")
        return _FakeCompletedProcess()

    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone.get_repos_dir",
        lambda: repos_dir,
    )
    monkeypatch.setattr(
        "repos_runner.services.repo_service.clone._inject_auth_token",
        lambda repo_url: repo_url,
    )
    monkeypatch.setattr(clone_module, "_run_git", _flaky_run_git)
    monkeypatch.setattr(clone_module, "_git_output", _fake_git_output)

    result = asyncio.run(clone_repository("https://github.com/org/demo"))

    assert attempts == 2
    assert result["repo_name"] == "github/org/demo/default"
    assert Path(result["clone_path"]).exists()


def test_lifecycle_lists_and_deletes_namespaced_repo_keys(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    source_dir = repos_dir / "github" / "org" / "demo" / "default" / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "TEST_REPORT.md").write_text("report", encoding="utf-8")

    monkeypatch.setattr(
        "repos_runner.services.repo_service.lifecycle.get_repos_dir",
        lambda: repos_dir,
    )

    repos = list_repos()

    assert [repo["repo_name"] for repo in repos] == ["github/org/demo/default"]
    assert repos[0]["clone_path"] == str(source_dir)
    assert repos[0]["has_report"] is True

    result = delete_repo(repo_storage_key("github", "org", "demo"))

    assert result["repo_name"] == "github/org/demo/default"
    assert not (repos_dir / "github" / "org" / "demo" / "default").exists()


def test_lifecycle_still_lists_legacy_flat_repositories(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    legacy_dir = repos_dir / "demo"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "README.md").write_text("legacy", encoding="utf-8")

    monkeypatch.setattr(
        "repos_runner.services.repo_service.lifecycle.get_repos_dir",
        lambda: repos_dir,
    )

    repos = list_repos()

    assert [repo["repo_name"] for repo in repos] == ["demo"]
    assert repos[0]["clone_path"] == str(legacy_dir)
