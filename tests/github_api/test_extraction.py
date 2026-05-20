"""Test cases for GitHub data extraction and error handling."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys

# Add project root to path if not already there
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add backend directory to Python path so evaluator can be imported as top-level package
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from evaluator.services.extraction_service import (
    extract_github_data,
    extract_repo_files_at_commit_via_git,
    fetch_github_commits,
    _extract_github_data_via_git,
    _write_filtered_repo_snapshot,
)
from evaluator.utils.repo_parser import parse_repo_url_with_ref


class TestGitHubExtraction:
    """Test GitHub data extraction functionality."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for test data."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_extract_github_data_success(self, temp_data_dir):
        """Test successful GitHub data extraction."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('subprocess.run') as mock_subprocess:
            
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = "fake_github_token"
            
            # Mock successful subprocess execution
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Extraction completed successfully"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result

            commits_dir = temp_data_dir / "commits"
            commits_dir.mkdir(parents=True, exist_ok=True)
            (commits_dir / "abc123.json").write_text("{}", encoding="utf-8")
            
            result = extract_github_data("test_owner", "test_repo")
            
            assert result is True
            mock_subprocess.assert_called_once()
            # Verify token is passed via env instead of argv so it is not exposed in process listings.
            call_args = mock_subprocess.call_args
            assert "backend.evaluator.tools.extract_repo_data_moderate" in call_args[0][0]
            assert "--token" not in call_args[0][0]
            assert "fake_github_token" not in call_args[0][0]
            assert call_args.kwargs["env"]["GITHUB_TOKEN"] == "fake_github_token"

    def test_write_filtered_repo_snapshot_excludes_dependencies_binary_and_large_files(self, temp_data_dir):
        """Complete repo snapshots should keep only evaluation-relevant text files."""
        checkout_dir = temp_data_dir / "checkout"
        output_dir = temp_data_dir / "out"
        (checkout_dir / "src").mkdir(parents=True)
        (checkout_dir / "node_modules" / "pkg").mkdir(parents=True)
        (checkout_dir / "assets").mkdir(parents=True)
        (checkout_dir / "src" / "app.py").write_text("print('useful')\n", encoding="utf-8")
        (checkout_dir / "README.md").write_text("# Useful\n", encoding="utf-8")
        (checkout_dir / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
        (checkout_dir / "node_modules" / "pkg" / "index.js").write_text("module.exports = 1\n", encoding="utf-8")
        (checkout_dir / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (checkout_dir / "src" / "large.py").write_text("x" * 20, encoding="utf-8")

        manifest = _write_filtered_repo_snapshot(
            checkout_dir,
            output_dir,
            end_sha="end123",
            max_file_bytes=18,
        )

        assert sorted(item["path"] for item in manifest["included_files"]) == ["README.md", "src/app.py"]
        assert (output_dir / "repo_files" / "src" / "app.py").read_text(encoding="utf-8") == "print('useful')\n"
        assert not (output_dir / "repo_files" / "node_modules").exists()
        skipped = {item["path"]: item["reason"] for item in manifest["skipped_files"]}
        assert skipped[".env"] == "excluded_path"
        assert skipped["node_modules/pkg/index.js"] == "excluded_path"
        assert skipped["assets/logo.png"] == "excluded_path"
        assert skipped["src/large.py"] == "too_large"

    def test_extract_repo_files_at_commit_uses_shallow_commit_fetch(self, temp_data_dir):
        """Snapshot extraction should first try fetching exactly the requested commit."""
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with patch('evaluator.services.extraction_service.get_gitee_token') as mock_token, \
             patch('evaluator.services.extraction_service._run_git') as mock_run_git, \
             patch('evaluator.services.extraction_service._write_filtered_repo_snapshot') as mock_write_snapshot:

            mock_token.return_value = None
            mock_run_git.return_value = completed
            mock_write_snapshot.return_value = {"included_count": 2, "skipped_count": 1}

            result = extract_repo_files_at_commit_via_git(
                "gitee",
                "test_owner",
                "test_repo",
                temp_data_dir,
                "abcdef1234567890",
            )

            assert result is True
            git_commands = [call.args[0] for call in mock_run_git.call_args_list]
            assert git_commands[0] == ["git", "init"]
            assert git_commands[1] == ["git", "remote", "add", "origin", "https://gitee.com/test_owner/test_repo.git"]
            assert git_commands[2] == ["git", "fetch", "--depth", "1", "--no-tags", "origin", "abcdef1234567890"]
            assert git_commands[3] == ["git", "checkout", "--detach", "abcdef1234567890"]
            mock_write_snapshot.assert_called_once()

    def test_parse_repo_url_with_ref_accepts_tree_branch_urls(self):
        github = parse_repo_url_with_ref("https://github.com/carterwu/carterwu.github.io/tree/main")
        assert (github.platform, github.owner, github.repo, github.branch) == (
            "github",
            "carterwu",
            "carterwu.github.io",
            "main",
        )

        gitee = parse_repo_url_with_ref(
            "https://gitee.com/zgcai/oscanner/tree/feat/update-gitee-ci-pipelines"
        )
        assert (gitee.platform, gitee.owner, gitee.repo, gitee.branch) == (
            "gitee",
            "zgcai",
            "oscanner",
            "feat/update-gitee-ci-pipelines",
        )

    def test_git_fallback_extraction_clones_requested_branch(self, temp_data_dir):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        clone_commands = []

        def fake_run_git(command, cwd=None, timeout=120):
            if command[:2] == ["git", "clone"]:
                clone_commands.append(command)
                Path(command[-1]).mkdir(parents=True, exist_ok=True)
                return completed
            if command[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="feature/demo\n", stderr="")
            if command[:2] == ["git", "rev-list"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="abc123\n", stderr="")
            if command[:3] == ["git", "show", "-s"]:
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=(
                        "abc123\n"
                        "Test Author\n"
                        "author@example.com\n"
                        "2026-01-01T00:00:00+00:00\n"
                        "Test Author\n"
                        "author@example.com\n"
                        "2026-01-01T00:00:00+00:00\n"
                        "Initial commit\n"
                    ),
                    stderr="",
                )
            if command[:3] == ["git", "show", "--name-status"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="M\tREADME.md\n", stderr="")
            if command[:3] == ["git", "show", "--numstat"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="1\t0\tREADME.md\n", stderr="")
            if command[:3] == ["git", "show", "--format="]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")
            return completed

        with patch('evaluator.services.extraction_service._run_git', side_effect=fake_run_git), \
             patch('evaluator.services.extraction_service._inject_git_token', side_effect=lambda url, platform: url), \
             patch('evaluator.services.extraction_service._write_filtered_repo_snapshot') as mock_snapshot:

            mock_snapshot.return_value = {"included_count": 1, "skipped_count": 0}

            result = _extract_github_data_via_git(
                "test_owner",
                "test_repo",
                temp_data_dir,
                max_commits=500,
                branch="feature/demo",
            )

            assert result is True
            assert clone_commands[0] == [
                "git",
                "clone",
                "--no-tags",
                "--single-branch",
                "--branch",
                "feature/demo",
                "--depth",
                "500",
                "https://github.com/test_owner/test_repo.git",
                str(Path(clone_commands[0][-1])),
            ]

    def test_git_fallback_retries_transient_clone_failure(self, temp_data_dir):
        """Git fallback extraction should retry transient GitHub clone failures."""
        attempts = 0
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        def fake_run_git(command, cwd=None, timeout=120):
            nonlocal attempts
            if command[:2] == ["git", "clone"]:
                attempts += 1
                if attempts == 1:
                    return subprocess.CompletedProcess(
                        args=command,
                        returncode=128,
                        stdout="",
                        stderr=(
                            "fatal: unable to access "
                            "'https://github.com/test_owner/test_repo.git/': "
                            "GnuTLS recv error (-110): The TLS connection was non-properly terminated."
                        ),
                    )
                Path(command[-1]).mkdir(parents=True, exist_ok=True)
                return completed
            if command[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="main\n", stderr="")
            if command[:2] == ["git", "rev-list"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="abc123\n", stderr="")
            if command[:3] == ["git", "show", "-s"]:
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=(
                        "abc123\n"
                        "Test Author\n"
                        "author@example.com\n"
                        "2026-01-01T00:00:00+00:00\n"
                        "Test Author\n"
                        "author@example.com\n"
                        "2026-01-01T00:00:00+00:00\n"
                        "Initial commit\n"
                    ),
                    stderr="",
                )
            if command[:3] == ["git", "show", "--name-status"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="M\tREADME.md\n", stderr="")
            if command[:3] == ["git", "show", "--numstat"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="1\t0\tREADME.md\n", stderr="")
            if command[:3] == ["git", "show", "--format="]:
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout="diff --git a/README.md b/README.md\n+hello\n",
                    stderr="",
                )
            return completed

        with patch('evaluator.services.extraction_service._run_git', side_effect=fake_run_git), \
             patch('evaluator.services.extraction_service._inject_git_token', side_effect=lambda url, platform: url), \
             patch('evaluator.services.extraction_service._write_filtered_repo_snapshot') as mock_snapshot:

            mock_snapshot.return_value = {"included_count": 1, "skipped_count": 0}

            result = _extract_github_data_via_git(
                "test_owner",
                "test_repo",
                temp_data_dir,
                max_commits=500,
            )

            assert result is True
            assert attempts == 2
            assert (temp_data_dir / "commits_index.json").exists()

    def test_extract_github_data_no_token(self, temp_data_dir):
        """Test GitHub extraction without token."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('subprocess.run') as mock_subprocess:
            
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = None
            
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Extraction completed"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result

            commits_dir = temp_data_dir / "commits"
            commits_dir.mkdir(parents=True, exist_ok=True)
            (commits_dir / "abc123.json").write_text("{}", encoding="utf-8")
            
            result = extract_github_data("test_owner", "test_repo")
            
            assert result is True
            # Verify command does not include token
            call_args = mock_subprocess.call_args
            assert "--token" not in call_args[0][0]

    def test_extract_github_data_can_skip_file_context(self, temp_data_dir):
        """Author discovery can extract commits without downloading file context."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('evaluator.services.extraction_service._try_write_latest_repo_snapshot') as mock_snapshot, \
             patch('subprocess.run') as mock_subprocess:

            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = None

            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Extraction completed"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result

            commits_dir = temp_data_dir / "commits"
            commits_dir.mkdir(parents=True, exist_ok=True)
            (commits_dir / "abc123.json").write_text("{}", encoding="utf-8")

            result = extract_github_data("test_owner", "test_repo", include_file_context=False)

            assert result is True
            call_args = mock_subprocess.call_args
            assert "--skip-file-context" in call_args[0][0]
            mock_snapshot.assert_not_called()

    def test_extract_github_data_writes_latest_repo_snapshot(self, temp_data_dir):
        """Successful GitHub extraction should store complete filtered repo files for latest SHA."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('evaluator.services.extraction_service._try_write_latest_repo_snapshot') as mock_snapshot, \
             patch('subprocess.run') as mock_subprocess:

            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = None
            mock_snapshot.return_value = True

            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Extraction completed"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result

            commits_dir = temp_data_dir / "commits"
            commits_dir.mkdir(parents=True, exist_ok=True)
            (commits_dir / "abc123.json").write_text("{}", encoding="utf-8")
            (temp_data_dir / "commits_index.json").write_text('[{"sha": "abc123"}]', encoding="utf-8")

            result = extract_github_data("test_owner", "test_repo")

            assert result is True
            mock_snapshot.assert_called_once_with("github", "test_owner", "test_repo", temp_data_dir)

    def test_extract_github_data_subprocess_failure(self, temp_data_dir):
        """Test GitHub extraction when subprocess fails."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('subprocess.run') as mock_subprocess:
            
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = "fake_token"
            
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Extraction failed: API rate limit exceeded"
            mock_subprocess.return_value = mock_result
            
            result = extract_github_data("test_owner", "test_repo")
            
            assert result is False

    def test_extract_github_data_subprocess_failure_with_git_fallback_success(self, temp_data_dir):
        """Test GitHub extraction fallback to git when API extractor fails."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('subprocess.run') as mock_subprocess, \
             patch('evaluator.services.extraction_service._extract_github_data_via_git') as mock_git_fallback:
            
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = None
            mock_git_fallback.return_value = True

            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "HTTPError 403 rate limit exceeded"
            mock_subprocess.return_value = mock_result

            result = extract_github_data("test_owner", "test_repo")

            assert result is True
            mock_git_fallback.assert_called_once_with("test_owner", "test_repo", temp_data_dir, max_commits=500)

    def test_extract_github_data_success_but_empty_commits_uses_git_fallback(self, temp_data_dir):
        """Test fallback when API extractor exits 0 but produces no commit files."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('subprocess.run') as mock_subprocess, \
             patch('evaluator.services.extraction_service._extract_github_data_via_git') as mock_git_fallback:

            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = None
            mock_git_fallback.return_value = True

            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Extraction completed"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result

            result = extract_github_data("test_owner", "test_repo")

            assert result is True
            mock_git_fallback.assert_called_once_with("test_owner", "test_repo", temp_data_dir, max_commits=500)

    def test_extract_github_data_timeout(self, temp_data_dir):
        """Test GitHub extraction timeout handling."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('subprocess.run') as mock_subprocess:
            
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = "fake_token"
            
            # Mock timeout exception
            mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 1800)
            
            result = extract_github_data("test_owner", "test_repo")
            
            assert result is False

    def test_extract_github_data_exception(self, temp_data_dir):
        """Test GitHub extraction exception handling."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('subprocess.run') as mock_subprocess:
            
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = "fake_token"
            
            # Mock exception
            mock_subprocess.side_effect = Exception("Unexpected error")
            
            result = extract_github_data("test_owner", "test_repo")
            
            assert result is False


class TestGitHubCommitsFetch:
    """Test GitHub commits fetching functionality."""

    def test_fetch_github_commits_success(self):
        """Test successful GitHub commits fetch."""
        import requests
        
        with patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('requests.get') as mock_get:
            
            mock_token.return_value = "fake_token"
            
            # Mock successful API response
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = [
                {"sha": "abc123", "commit": {"message": "Test commit"}},
                {"sha": "def456", "commit": {"message": "Another commit"}},
            ]
            mock_get.return_value = mock_resp
            
            commits = fetch_github_commits("test_owner", "test_repo", limit=100)
            
            assert len(commits) == 2
            assert commits[0]["sha"] == "abc123"
            mock_get.assert_called_once()
            # Verify Authorization header is set
            call_kwargs = mock_get.call_args[1]
            assert "Authorization" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Authorization"] == "token fake_token"

    def test_fetch_github_commits_no_token(self):
        """Test GitHub commits fetch without token."""
        import requests
        
        with patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('requests.get') as mock_get:
            
            mock_token.return_value = None
            
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = [{"sha": "abc123"}]
            mock_get.return_value = mock_resp
            
            commits = fetch_github_commits("test_owner", "test_repo", limit=100)
            
            assert len(commits) == 1
            # Verify no Authorization header when no token
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["headers"] == {}

    def test_fetch_github_commits_api_error(self):
        """Test GitHub commits fetch with API error."""
        import requests
        
        with patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('requests.get') as mock_get:
            
            mock_token.return_value = "fake_token"
            
            # Mock API error response
            mock_resp = Mock()
            mock_resp.status_code = 401
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
            mock_get.return_value = mock_resp
            
            with pytest.raises(Exception) as exc_info:
                fetch_github_commits("test_owner", "test_repo", limit=100)
            
            assert "401" in str(exc_info.value) or "Failed to fetch" in str(exc_info.value)

    def test_fetch_github_commits_network_error(self):
        """Test GitHub commits fetch with network error."""
        import requests
        
        with patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('requests.get') as mock_get:
            
            mock_token.return_value = "fake_token"
            
            # Mock network error
            mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
            
            with pytest.raises(Exception) as exc_info:
                fetch_github_commits("test_owner", "test_repo", limit=100)
            
            assert "Failed to fetch" in str(exc_info.value) or "Connection" in str(exc_info.value)

    def test_fetch_github_commits_timeout(self):
        """Test GitHub commits fetch timeout."""
        import requests
        
        with patch('evaluator.services.extraction_service.get_github_token') as mock_token, \
             patch('requests.get') as mock_get:
            
            mock_token.return_value = "fake_token"
            
            # Mock timeout error
            mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
            
            with pytest.raises(Exception) as exc_info:
                fetch_github_commits("test_owner", "test_repo", limit=100)
            
            assert "Failed to fetch" in str(exc_info.value) or "timeout" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
