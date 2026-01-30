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

from evaluator.services.extraction_service import (
    extract_github_data,
    fetch_github_commits,
)


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
            
            result = extract_github_data("test_owner", "test_repo")
            
            assert result is True
            mock_subprocess.assert_called_once()
            # Verify command includes token
            call_args = mock_subprocess.call_args
            assert "--token" in call_args[0][0]
            assert "fake_github_token" in call_args[0][0]

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
            
            result = extract_github_data("test_owner", "test_repo")
            
            assert result is True
            # Verify command does not include token
            call_args = mock_subprocess.call_args
            assert "--token" not in call_args[0][0]

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
