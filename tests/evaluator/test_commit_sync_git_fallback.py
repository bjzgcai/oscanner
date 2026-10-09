"""Tests for the git-clone fallback used by commit boundary/incremental sync."""

import json
import subprocess

import pytest

from evaluator.services import extraction_service


def _run_git(cmd, cwd):
    return subprocess.run(
        ["git", *cmd],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def sample_repo(tmp_path):
    repo = tmp_path / "sample-repo"
    repo.mkdir()
    _run_git(["init", "-q"], repo)
    _run_git(["config", "user.name", "Alice Student"], repo)
    _run_git(["config", "user.email", "alice@example.com"], repo)

    (repo / "README.md").write_text("# Sample\n\nHello world.\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('v1')\n", encoding="utf-8")
    _run_git(["add", "."], repo)
    _run_git(["commit", "-q", "-m", "Initial commit"], repo)
    root_sha = _run_git(["rev-parse", "HEAD"], repo).stdout.strip()

    (repo / "src" / "app.py").write_text("print('v2')\n# updated\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (repo / "assets.bin").write_bytes(b"\x00\x01\x02binary-bytes")
    (repo / "dir with space").mkdir()
    (repo / "dir with space" / "file name.txt").write_text("spaced content\n", encoding="utf-8")
    (repo / "empty.txt").write_text("", encoding="utf-8")
    _run_git(["add", "."], repo)
    _run_git(["commit", "-q", "-m", "Update app and add docs"], repo)
    second_sha = _run_git(["rev-parse", "HEAD"], repo).stdout.strip()

    _run_git(["rm", "-q", "README.md"], repo)
    _run_git(["mv", "docs/guide.md", "docs/manual.md"], repo)
    _run_git(["add", "."], repo)
    _run_git(["commit", "-q", "-m", "Remove readme, rename guide"], repo)
    third_sha = _run_git(["rev-parse", "HEAD"], repo).stdout.strip()

    return {"path": repo, "shas": [root_sha, second_sha, third_sha]}


def _point_clone_at(sample_repo, monkeypatch):
    monkeypatch.setattr(
        extraction_service,
        "_repo_git_url",
        lambda platform, owner, repo: str(sample_repo["path"]),
    )


class _FakeResponse:
    def __init__(self, status_code, headers=None, payload=None, text=""):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no payload")
        return self._payload


def test_response_is_quota_limited():
    limited = _FakeResponse(403, headers={"x-ratelimit-remaining": "0"})
    secondary = _FakeResponse(429, payload={"message": "You have exceeded a secondary rate limit"})
    normal = _FakeResponse(200)
    not_found = _FakeResponse(404)

    assert extraction_service._response_is_quota_limited(limited) is True
    assert extraction_service._response_is_quota_limited(secondary) is True
    assert extraction_service._response_is_quota_limited(normal) is False
    assert extraction_service._response_is_quota_limited(not_found) is False


def test_numstat_parser_keeps_rename_entries_aligned():
    name_status = "R100\x00docs/guide.md\x00docs/manual.md\x00D\x00README.md\x00"
    numstat = "0\t0\t\x00docs/guide.md\x00docs/manual.md\x002\t0\tREADME.md\x00"

    entries = extraction_service._parse_name_status_z(name_status)
    stats = extraction_service._parse_numstat_z(numstat, entries)

    assert entries == [
        ("R", "docs/guide.md", "docs/manual.md"),
        ("D", "README.md", "README.md"),
    ]
    assert stats == [(0, 0), (2, 0)]


def test_git_clone_fallback_builds_api_shaped_details(sample_repo, monkeypatch):
    _point_clone_at(sample_repo, monkeypatch)
    shas = sample_repo["shas"]

    details, _file_contents = extraction_service._fetch_commit_details_via_git_clone(
        "github", "owner", "sample-repo", shas
    )

    assert set(details) == set(shas)

    root = details[shas[0]]
    assert root["sha"] == shas[0]
    assert root["commit"]["author"]["name"] == "Alice Student"
    assert root["commit"]["author"]["email"] == "alice@example.com"
    assert root["commit"]["message"] == "Initial commit"
    assert root["parents"] == []
    by_name = {entry["filename"]: entry for entry in root["files"]}
    assert by_name["README.md"]["status"] == "added"
    assert by_name["README.md"]["additions"] > 0
    assert "Hello world" in by_name["README.md"]["patch"]
    assert root["stats"]["additions"] == sum(entry["additions"] for entry in root["files"])

    second = details[shas[1]]
    by_name = {entry["filename"]: entry for entry in second["files"]}
    assert by_name["src/app.py"]["status"] == "modified"
    assert "print('v2')" in by_name["src/app.py"]["patch"]
    assert by_name["docs/guide.md"]["status"] == "added"
    assert by_name["assets.bin"]["patch"] == ""
    assert by_name["dir with space/file name.txt"]["additions"] == 1
    assert "spaced content" in by_name["dir with space/file name.txt"]["patch"]
    assert by_name["empty.txt"]["additions"] == 0
    assert by_name["empty.txt"]["deletions"] == 0
    assert second["parents"] == [{"sha": shas[0]}]

    third = details[shas[2]]
    by_name = {entry["filename"]: entry for entry in third["files"]}
    assert by_name["README.md"]["status"] == "removed"
    assert by_name["README.md"]["deletions"] > 0
    assert by_name["docs/manual.md"]["status"] == "renamed"
    assert by_name["docs/manual.md"]["previous_filename"] == "docs/guide.md"
    assert by_name["docs/manual.md"]["additions"] == 0
    assert by_name["docs/manual.md"]["deletions"] == 0
    assert third["parents"] == [{"sha": shas[1]}]


def test_git_clone_fallback_collects_file_contents(sample_repo, monkeypatch):
    _point_clone_at(sample_repo, monkeypatch)
    shas = sample_repo["shas"]

    _details, file_contents = extraction_service._fetch_commit_details_via_git_clone(
        "gitee", "owner", "sample-repo", shas, collect_file_contents=True
    )

    assert file_contents["src/app.py"] == "print('v2')\n# updated\n"
    # README.md was deleted in the newest commit; the newest still-existing version is used.
    assert file_contents["README.md"] == "# Sample\n\nHello world.\n"
    assert file_contents["docs/manual.md"] == "# Guide\n"
    assert file_contents["empty.txt"] == ""
    assert file_contents["dir with space/file name.txt"] == "spaced content\n"


def test_collect_details_mixes_api_and_fallback(sample_repo, monkeypatch):
    _point_clone_at(sample_repo, monkeypatch)
    shas = sample_repo["shas"]

    def fetch_one(sha):
        if sha == shas[0]:
            return {
                "sha": sha,
                "commit": {
                    "author": {"name": "Api Author", "email": "api@example.com", "date": "2026-01-01T00:00:00Z"},
                    "message": "api commit",
                },
                "files": [],
            }
        raise extraction_service.ProviderQuotaExceeded("daily budget exhausted")

    details, file_contents, quota_exhausted = extraction_service._collect_commit_details_with_git_fallback(
        "github",
        "owner",
        "sample-repo",
        shas,
        fetch_one,
        validate=lambda sha, detail: detail.get("sha") == sha,
        log_prefix="Test Sync",
    )

    assert quota_exhausted is True
    assert details[shas[0]]["commit"]["author"]["name"] == "Api Author"
    assert details[shas[1]]["commit"]["message"] == "Update app and add docs"
    assert details[shas[2]]["commit"]["message"] == "Remove readme, rename guide"
    assert file_contents == {}


def test_sync_github_boundary_falls_back_on_quota(sample_repo, tmp_path, monkeypatch):
    _point_clone_at(sample_repo, monkeypatch)
    data_dir = tmp_path / "data"
    monkeypatch.setattr(extraction_service, "get_platform_data_dir", lambda *parts: data_dir)
    monkeypatch.setattr(extraction_service, "_try_write_latest_repo_snapshot", lambda *a, **k: False)

    def _raise(*args, **kwargs):
        raise extraction_service.ProviderQuotaExceeded("daily budget exhausted")

    monkeypatch.setattr(extraction_service, "_fetch_github_commit_detail", _raise)
    shas = sample_repo["shas"]

    changed = extraction_service.sync_github_commits_by_sha("owner", "sample-repo", shas)

    assert changed is True
    commits_dir = data_dir / "commits"
    for sha in shas:
        assert (commits_dir / f"{sha}.json").exists()
        assert (commits_dir / f"{sha}.diff").exists()
    index = json.loads((data_dir / "commits_index.json").read_text(encoding="utf-8"))
    assert {entry["sha"] for entry in index} == set(shas)


def test_sync_github_boundary_raises_when_fallback_fails(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(extraction_service, "get_platform_data_dir", lambda *parts: data_dir)
    monkeypatch.setattr(
        extraction_service,
        "_repo_git_url",
        lambda platform, owner, repo: str(tmp_path / "missing-repo"),
    )

    def _raise(*args, **kwargs):
        raise extraction_service.ProviderQuotaExceeded("daily budget exhausted")

    monkeypatch.setattr(extraction_service, "_fetch_github_commit_detail", _raise)

    with pytest.raises(extraction_service.CommitSyncQuotaExceeded):
        extraction_service.sync_github_commits_by_sha("owner", "repo", ["0" * 40])


def test_sync_gitee_boundary_falls_back_on_quota(sample_repo, tmp_path, monkeypatch):
    _point_clone_at(sample_repo, monkeypatch)
    data_dir = tmp_path / "data"
    monkeypatch.setattr(extraction_service, "get_platform_data_dir", lambda *parts: data_dir)
    monkeypatch.setattr(extraction_service, "get_gitee_token", lambda: "test-token")
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("provider API must not be called after quota exhaustion")

    monkeypatch.setattr(extraction_service, "_try_write_gitee_repo_snapshot", _fail_if_called)
    monkeypatch.setattr(extraction_service, "_write_gitee_file_context", _fail_if_called)

    def _raise(*args, **kwargs):
        raise extraction_service.ProviderQuotaExceeded("daily budget exhausted")

    monkeypatch.setattr(extraction_service, "_fetch_gitee_commit_detail", _raise)
    shas = sample_repo["shas"]

    changed = extraction_service.sync_gitee_commits_by_sha("owner", "sample-repo", shas)

    assert changed is True
    commits_dir = data_dir / "commits"
    for sha in shas:
        assert (commits_dir / f"{sha}.json").exists()
    files_dir = data_dir / "files"
    assert (files_dir / "src" / "app.py").read_text(encoding="utf-8") == "print('v2')\n# updated\n"
    assert (files_dir / "README.md").read_text(encoding="utf-8") == "# Sample\n\nHello world.\n"


def test_incremental_validation_rejects_404_stub_commit():
    shas = ["a" * 40, "b" * 40]

    details, file_contents, quota_exhausted = extraction_service._collect_commit_details_with_git_fallback(
        "github",
        "owner",
        "repo",
        shas,
        fetch_one=lambda sha: {"sha": sha},
        validate=lambda sha, detail: _get_commit_sha_safe(detail) == sha
        and isinstance(detail.get("commit"), dict),
        log_prefix="GitHub Incremental",
    )

    assert details == {}
    assert file_contents == {}
    assert quota_exhausted is False


def _get_commit_sha_safe(detail):
    return str(detail.get("sha") or detail.get("hash") or "").strip()


def test_clone_fallback_clears_partial_clone_before_second_strategy(monkeypatch, tmp_path):
    marker = tmp_path / "marker"
    calls = []

    def fake_clone(clone_cmd, *, clone_dir, timeout):
        calls.append(list(clone_cmd))
        if len(calls) == 1:
            clone_dir.mkdir(parents=True, exist_ok=True)
            (clone_dir / "partial").write_text("leftover", encoding="utf-8")
            return subprocess.CompletedProcess(clone_cmd, 1, "", "filter unsupported")
        assert not (clone_dir / "partial").exists()
        clone_dir.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(clone_cmd, 0, "", "")

    monkeypatch.setattr(extraction_service, "_repo_git_url", lambda *args: str(tmp_path / "repo"))
    monkeypatch.setattr(extraction_service, "_run_git_clone_with_retries", fake_clone)
    monkeypatch.setattr(
        extraction_service,
        "_git_commit_details_from_clone_dir",
        lambda clone_dir, shas, **kwargs: {shas[0]: {"sha": shas[0]}},
    )

    details, _contents = extraction_service._fetch_commit_details_via_git_clone(
        "gitee", "owner", "repo", ["c" * 40]
    )

    assert len(calls) == 2
    assert "--filter=blob:none" in calls[0]
    assert "--filter=blob:none" not in calls[1]
    assert details == {"c" * 40: {"sha": "c" * 40}}
