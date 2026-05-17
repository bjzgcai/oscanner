"""Test cases for Gitee data extraction, DNS resolution, and network error handling."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import shutil
import json
import sys

# Add project root to path if not already there
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add backend directory to Python path so evaluator can be imported as top-level package
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Import directly from extraction_service module
from evaluator.services.extraction_service import (
    extract_gitee_data,
    sync_gitee_data_incremental,
    check_dns_resolution,
)


class TestDNSResolution:
    """Test DNS resolution functionality."""

    def test_dns_resolution_success(self):
        """Test successful DNS resolution."""
        # Test with a well-known domain
        success, error, ip = check_dns_resolution("www.baidu.com")
        assert success is True
        assert error is None
        assert ip is not None

    def test_dns_resolution_failure(self):
        """Test DNS resolution failure for non-existent domain."""
        success, error, ip = check_dns_resolution("nonexistent-domain-12345.test")
        assert success is False
        assert error is not None
        assert ip is None

    def test_dns_hijacking_detection(self):
        """Test detection of DNS hijacking (baiduads.com in reverse DNS)."""
        # Mock socket.gethostbyname to return an IP
        # Mock socket.gethostbyaddr to return baiduads.com (indicating hijacking)
        with patch('socket.gethostbyname') as mock_gethostbyname, \
             patch('socket.gethostbyaddr') as mock_gethostbyaddr:
            
            mock_gethostbyname.return_value = "180.76.199.13"
            mock_gethostbyaddr.return_value = ("gitee.com-31ba39d0fd3.baiduads.com", [], [])
            
            success, error, ip = check_dns_resolution("gitee.com")
            
            assert success is False
            assert "hijacking" in error.lower()
            assert ip == "180.76.199.13"

    def test_dns_resolution_no_hijacking(self):
        """Test DNS resolution without hijacking."""
        with patch('socket.gethostbyname') as mock_gethostbyname, \
             patch('socket.gethostbyaddr') as mock_gethostbyaddr:
            
            mock_gethostbyname.return_value = "1.2.3.4"
            mock_gethostbyaddr.return_value = ("gitee.com", [], [])
            
            success, error, ip = check_dns_resolution("gitee.com")
            
            assert success is True
            assert error is None
            assert ip == "1.2.3.4"


class TestGiteeExtraction:
    """Test Gitee data extraction functionality."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for test data."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_extract_gitee_data_token_required(self, temp_data_dir):
        """Test that extraction fails when Gitee token is not configured."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_gitee_token') as mock_token:
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = None
            with pytest.raises(Exception) as exc_info:
                extract_gitee_data("test_owner", "test_repo", max_commits=10)
            assert "token" in str(exc_info.value).lower() or "GITEE" in str(exc_info.value)

    def test_extract_gitee_data_dns_failure(self, temp_data_dir):
        """Test extraction failure when request raises DNS/resolution error."""
        import requests
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_requests_session') as mock_session, \
             patch('evaluator.services.extraction_service.get_gitee_token') as mock_token:
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = "fake_token"
            mock_sess = Mock()
            mock_sess.get.side_effect = requests.exceptions.ConnectionError(
                "Failed to resolve 'gitee.com' (NameResolutionError)"
            )
            mock_session.return_value = mock_sess
            with pytest.raises(Exception) as exc_info:
                extract_gitee_data("test_owner", "test_repo", max_commits=10)
            assert "DNS" in str(exc_info.value) or "resolution" in str(exc_info.value).lower()

    def test_extract_gitee_data_network_error(self, temp_data_dir):
        """Test handling of network errors."""
        import requests
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_requests_session') as mock_session, \
             patch('evaluator.services.extraction_service.get_gitee_token') as mock_token:
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = "fake_token"
            mock_sess = Mock()
            mock_sess.get.side_effect = requests.exceptions.ConnectionError("Connection failed")
            mock_session.return_value = mock_sess
            with pytest.raises(Exception) as exc_info:
                extract_gitee_data("test_owner", "test_repo", max_commits=10)
            assert "connection" in str(exc_info.value).lower() or "network" in str(exc_info.value).lower()

    def test_extract_gitee_data_timeout_error(self, temp_data_dir):
        """Test handling of timeout errors."""
        import requests
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_requests_session') as mock_session, \
             patch('evaluator.services.extraction_service.get_gitee_token') as mock_token:
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = "fake_token"
            mock_sess = Mock()
            mock_sess.get.side_effect = requests.exceptions.Timeout("Request timed out")
            mock_session.return_value = mock_sess
            with pytest.raises(Exception) as exc_info:
                extract_gitee_data("test_owner", "test_repo", max_commits=10)
            assert "timeout" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()

    def test_extract_gitee_data_api_error(self, temp_data_dir):
        """Test handling of API errors (non-200 status codes)."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_requests_session') as mock_session, \
             patch('evaluator.services.extraction_service.get_gitee_token') as mock_token:
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = "fake_token"
            mock_resp = Mock()
            mock_resp.status_code = 404
            mock_resp.text = "Repository not found"
            mock_resp.headers = {'Server': 'nginx'}
            mock_sess = Mock()
            mock_sess.get.return_value = mock_resp
            mock_session.return_value = mock_sess
            with pytest.raises(Exception) as exc_info:
                extract_gitee_data("test_owner", "test_repo", max_commits=10)
            assert "404" in str(exc_info.value) or "API error" in str(exc_info.value)

    def test_extract_gitee_data_uses_gitee_api_domain(self, temp_data_dir):
        """Test that extraction uses gitee.com API host (API rejects www.gitee.com with 403 Invalid Hostname)."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_requests_session') as mock_session, \
             patch('evaluator.services.extraction_service.get_gitee_token') as mock_token:
            
            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = "fake_token_for_test"
            
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = []
            mock_resp.headers = {'Server': 'nginx'}
            
            mock_sess = Mock()
            mock_sess.get.return_value = mock_resp
            mock_session.return_value = mock_sess
            
            result = extract_gitee_data("test_owner", "test_repo", max_commits=10)
            
            calls = mock_sess.get.call_args_list
            assert len(calls) > 0
            first_call_url = calls[0][0][0] if calls else None
            assert first_call_url is not None
            assert "gitee.com" in first_call_url

    def test_extract_gitee_data_writes_latest_repo_snapshot(self, temp_data_dir):
        """Successful Gitee extraction should store complete filtered repo files for latest SHA."""
        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_requests_session') as mock_session, \
             patch('evaluator.services.extraction_service.get_gitee_token') as mock_token, \
             patch('evaluator.services.extraction_service._try_write_latest_repo_snapshot') as mock_snapshot:

            mock_get_dir.return_value = temp_data_dir
            mock_token.return_value = "fake_token_for_test"
            mock_snapshot.return_value = True

            commits_resp = Mock()
            commits_resp.status_code = 200
            commits_resp.json.return_value = [{"sha": "abc123"}]

            detail_resp = Mock()
            detail_resp.status_code = 200
            detail_resp.json.return_value = {
                "sha": "abc123",
                "commit": {"author": {"name": "Ada", "date": "2026-01-01T00:00:00+00:00"}, "message": "feat"},
                "files": [{"filename": "src/app.py"}],
            }

            file_resp = Mock()
            file_resp.status_code = 200
            file_resp.json.return_value = {"content": "cHJpbnQoJ29rJykK", "size": 12}

            mock_sess = Mock()
            mock_sess.get.side_effect = [commits_resp, detail_resp, file_resp]
            mock_session.return_value = mock_sess

            result = extract_gitee_data("test_owner", "test_repo", max_commits=1)

            assert result is True
            mock_snapshot.assert_called_once_with("gitee", "test_owner", "test_repo", temp_data_dir)

    def test_sync_gitee_data_incremental_fetches_only_missing_latest_commits(self, temp_data_dir):
        """Existing Gitee data should be extended by fetching only the latest missing commits."""
        repo_dir = temp_data_dir / "gitee" / "test_owner" / "test_repo"
        commits_dir = repo_dir / "commits"
        commits_dir.mkdir(parents=True)
        (repo_dir / "files").mkdir(parents=True)

        existing_commit = {
            "sha": "oldsha",
            "commit": {"author": {"name": "Alice", "date": "2026-01-01T00:00:00+00:00"}, "message": "old"},
        }
        (repo_dir / "commits_list.json").write_text(json.dumps([existing_commit]), encoding="utf-8")
        (repo_dir / "commits_index.json").write_text(
            json.dumps([
                {
                    "sha": "oldsha",
                    "message": "old",
                    "author": "Alice",
                    "date": "2026-01-01T00:00:00+00:00",
                    "files_changed": 0,
                    "files": [],
                }
            ]),
            encoding="utf-8",
        )

        contributors_resp = Mock()
        contributors_resp.status_code = 200
        contributors_resp.json.return_value = [{"name": "Alice", "contributions": 2}]

        commits_page_resp = Mock()
        commits_page_resp.status_code = 200
        commits_page_resp.json.return_value = [
            {
                "sha": "newsha",
                "commit": {"author": {"name": "Alice", "date": "2026-01-02T00:00:00+00:00"}, "message": "new"},
            },
        ]

        detail_resp = Mock()
        detail_resp.status_code = 200
        detail_resp.json.return_value = {
            "sha": "newsha",
            "commit": {"author": {"name": "Alice", "date": "2026-01-02T00:00:00+00:00"}, "message": "new"},
            "files": [{"filename": "src/app.py", "patch": "@@"}],
        }

        content_resp = Mock()
        content_resp.status_code = 200
        content_resp.json.return_value = {"content": "cHJpbnQoJ2hpJykK", "size": 12}

        responses = [contributors_resp, commits_page_resp, detail_resp, content_resp]
        mock_sess = Mock()
        mock_sess.get.side_effect = responses

        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_requests_session') as mock_session, \
             patch('evaluator.services.extraction_service.get_gitee_token') as mock_token:
            mock_get_dir.return_value = repo_dir
            mock_session.return_value = mock_sess
            mock_token.return_value = "fake_token_for_test"

            result = sync_gitee_data_incremental("test_owner", "test_repo", max_commits=500)

        assert result is True

        saved_commits = json.loads((repo_dir / "commits_list.json").read_text(encoding="utf-8"))
        assert [commit["sha"] for commit in saved_commits] == ["newsha", "oldsha"]
        assert (commits_dir / "newsha.json").exists()
        assert (repo_dir / "files" / "src" / "app.py").read_text(encoding="utf-8") == "print('hi')\n"

        requested_urls = [call.args[0] for call in mock_sess.get.call_args_list]
        assert any("/contributors" in url for url in requested_urls)
        assert sum("/commits" in url and not url.endswith("/newsha") for url in requested_urls) == 1

    def test_sync_gitee_data_incremental_verifies_latest_page_when_counts_match(self, temp_data_dir):
        """When contributor count matches local data, verify latest SHAs before skipping details."""
        repo_dir = temp_data_dir / "gitee" / "test_owner" / "test_repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "commits_list.json").write_text(
            json.dumps([
                {"sha": "sha1", "commit": {"author": {"name": "Alice"}, "message": "one"}},
                {"sha": "sha2", "commit": {"author": {"name": "Alice"}, "message": "two"}},
            ]),
            encoding="utf-8",
        )
        (repo_dir / "commits_index.json").write_text("[]", encoding="utf-8")

        contributors_resp = Mock()
        contributors_resp.status_code = 200
        contributors_resp.json.return_value = [{"name": "Alice", "contributions": 2}]

        commits_page_resp = Mock()
        commits_page_resp.status_code = 200
        commits_page_resp.json.return_value = [
            {"sha": "sha1", "commit": {"author": {"name": "Alice"}, "message": "one"}},
            {"sha": "sha2", "commit": {"author": {"name": "Alice"}, "message": "two"}},
        ]

        mock_sess = Mock()
        mock_sess.get.side_effect = [contributors_resp, commits_page_resp]

        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_requests_session') as mock_session, \
             patch('evaluator.services.extraction_service.get_gitee_token') as mock_token:
            mock_get_dir.return_value = repo_dir
            mock_session.return_value = mock_sess
            mock_token.return_value = "fake_token_for_test"

            result = sync_gitee_data_incremental("test_owner", "test_repo", max_commits=500)

        assert result is False
        requested_urls = [call.args[0] for call in mock_sess.get.call_args_list]
        assert requested_urls == [
            "https://gitee.com/api/v5/repos/test_owner/test_repo/contributors",
            "https://gitee.com/api/v5/repos/test_owner/test_repo/commits",
        ]

    def test_sync_gitee_data_incremental_fetches_missing_latest_sha_even_when_counts_match(self, temp_data_dir):
        """Matching contributor counts should not hide a missing latest remote SHA."""
        repo_dir = temp_data_dir / "gitee" / "test_owner" / "test_repo"
        commits_dir = repo_dir / "commits"
        commits_dir.mkdir(parents=True)
        (repo_dir / "files").mkdir(parents=True)
        (repo_dir / "commits_list.json").write_text(
            json.dumps([
                {"sha": "local-new", "commit": {"author": {"name": "Alice"}, "message": "local new"}},
                {"sha": "local-old", "commit": {"author": {"name": "Alice"}, "message": "local old"}},
            ]),
            encoding="utf-8",
        )
        (repo_dir / "commits_index.json").write_text("[]", encoding="utf-8")

        contributors_resp = Mock()
        contributors_resp.status_code = 200
        contributors_resp.json.return_value = [{"name": "Alice", "contributions": 2}]

        commits_page_resp = Mock()
        commits_page_resp.status_code = 200
        commits_page_resp.json.return_value = [
            {
                "sha": "remote-new",
                "commit": {"author": {"name": "Alice", "date": "2026-01-03T00:00:00+00:00"}, "message": "remote new"},
            },
            {
                "sha": "local-new",
                "commit": {"author": {"name": "Alice", "date": "2026-01-02T00:00:00+00:00"}, "message": "local new"},
            },
        ]

        detail_resp = Mock()
        detail_resp.status_code = 200
        detail_resp.json.return_value = {
            "sha": "remote-new",
            "commit": {"author": {"name": "Alice", "date": "2026-01-03T00:00:00+00:00"}, "message": "remote new"},
            "files": [],
        }

        mock_sess = Mock()
        mock_sess.get.side_effect = [contributors_resp, commits_page_resp, detail_resp]

        with patch('evaluator.services.extraction_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.extraction_service.get_requests_session') as mock_session, \
             patch('evaluator.services.extraction_service.get_gitee_token') as mock_token:
            mock_get_dir.return_value = repo_dir
            mock_session.return_value = mock_sess
            mock_token.return_value = "fake_token_for_test"

            result = sync_gitee_data_incremental("test_owner", "test_repo", max_commits=500)

        assert result is True
        saved_commits = json.loads((repo_dir / "commits_list.json").read_text(encoding="utf-8"))
        assert [commit["sha"] for commit in saved_commits] == ["remote-new", "local-new", "local-old"]
        assert (commits_dir / "remote-new.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
