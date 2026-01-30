"""Test cases for Gitee data extraction, DNS resolution, and network error handling."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import shutil
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
