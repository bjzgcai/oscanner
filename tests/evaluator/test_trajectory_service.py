"""Test cases for trajectory service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import sys
import json
from datetime import datetime, timedelta

# Add project root to path if not already there
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add backend directory to Python path so evaluator can be imported as top-level package
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from evaluator.services.trajectory_service import (
    load_trajectory_cache,
    save_trajectory_cache,
    get_commits_by_date,
)


class TestTrajectoryCache:
    """Test trajectory cache functionality."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_load_trajectory_cache_not_exists(self, temp_cache_dir):
        """Test loading non-existent cache."""
        with patch('evaluator.services.trajectory_service.get_trajectory_cache_path') as mock_path:
            mock_path.return_value = temp_cache_dir / "nonexistent.json"
            
            result = load_trajectory_cache("test_user")
            
            assert result is None

    def test_load_trajectory_cache_exists(self, temp_cache_dir):
        """Test loading existing cache."""
        cache_file = temp_cache_dir / "test_user.json"
        cache_data = {
            "username": "test_user",
            "repo_urls": ["https://github.com/test/repo"],
            "checkpoints": [],
            "last_synced_sha": None,
            "last_synced_at": None,
            "total_checkpoints": 0
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)
        
        with patch('evaluator.services.trajectory_service.get_trajectory_cache_path') as mock_path:
            mock_path.return_value = cache_file
            
            result = load_trajectory_cache("test_user")
            
            assert result is not None
            assert result.username == "test_user"
            assert len(result.repo_urls) == 1

    def test_load_trajectory_cache_invalid_json(self, temp_cache_dir):
        """Test loading invalid cache file."""
        cache_file = temp_cache_dir / "test_user.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write("invalid json content")
        
        with patch('evaluator.services.trajectory_service.get_trajectory_cache_path') as mock_path:
            mock_path.return_value = cache_file
            
            result = load_trajectory_cache("test_user")
            
            # Should return None on error
            assert result is None

    def test_save_trajectory_cache(self, temp_cache_dir):
        """Test saving trajectory cache."""
        from evaluator.schemas.trajectory import TrajectoryCache
        
        cache_file = temp_cache_dir / "test_user.json"
        trajectory = TrajectoryCache(
            username="test_user",
            repo_urls=["https://github.com/test/repo"],
            checkpoints=[],
            last_synced_sha=None,
            last_synced_at=None,
            total_checkpoints=0
        )
        
        with patch('evaluator.services.trajectory_service.get_trajectory_cache_path') as mock_path:
            mock_path.return_value = cache_file
            
            save_trajectory_cache(trajectory)
            
            assert cache_file.exists()
            with open(cache_file, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            assert saved_data["username"] == "test_user"


class TestGetCommitsByDate:
    """Test get commits by date functionality."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for test data."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_get_commits_by_date(self, temp_data_dir):
        """Test getting commits grouped by date."""
        from evaluator.services.trajectory_service import get_commits_by_date
        
        # Create test data directory with commits
        repo_dir = temp_data_dir / "github" / "test_owner" / "test_repo"
        repo_dir.mkdir(parents=True)
        
        commits_data = [
            {
                "sha": "commit1",
                "commit": {
                    "author": {
                        "name": "test_user",
                        "date": (datetime.now() - timedelta(days=5)).isoformat()
                    }
                }
            },
            {
                "sha": "commit2",
                "commit": {
                    "author": {
                        "name": "test_user",
                        "date": (datetime.now() - timedelta(days=3)).isoformat()
                    }
                }
            },
        ]
        
        with open(repo_dir / "commits_list.json", 'w', encoding='utf-8') as f:
            json.dump(commits_data, f)
        
        with patch('evaluator.services.trajectory_service.get_platform_data_dir') as mock_get_dir:
            mock_get_dir.return_value = repo_dir
            
            result = get_commits_by_date(
                username="test_user",
                repo_urls=["https://github.com/test_owner/test_repo"],
                aliases=["test_user"]
            )
            
            # Should return list of {date, count} dicts
            assert isinstance(result, list)
            assert len(result) > 0
            assert "date" in result[0]
            assert "count" in result[0]

    def test_get_commits_by_date_no_matches(self, temp_data_dir):
        """Test get commits by date with no matching commits."""
        from evaluator.services.trajectory_service import get_commits_by_date
        
        repo_dir = temp_data_dir / "github" / "test_owner" / "test_repo"
        repo_dir.mkdir(parents=True)
        
        commits_data = [
            {
                "sha": "commit1",
                "commit": {
                    "author": {
                        "name": "other_user",
                        "date": (datetime.now() - timedelta(days=5)).isoformat()
                    }
                }
            },
        ]
        
        with open(repo_dir / "commits_list.json", 'w', encoding='utf-8') as f:
            json.dump(commits_data, f)
        
        with patch('evaluator.services.trajectory_service.get_platform_data_dir') as mock_get_dir:
            mock_get_dir.return_value = repo_dir
            
            result = get_commits_by_date(
                username="test_user",
                repo_urls=["https://github.com/test_owner/test_repo"],
                aliases=["test_user"]
            )
            
            # Should return empty list or list with zero counts
            assert isinstance(result, list)

    def test_get_commits_by_date_no_repo_data(self, temp_data_dir):
        """Test get commits by date with no repo data."""
        from evaluator.services.trajectory_service import get_commits_by_date
        
        with patch('evaluator.services.trajectory_service.get_platform_data_dir') as mock_get_dir:
            mock_get_dir.return_value = temp_data_dir / "nonexistent"
            
            result = get_commits_by_date(
                username="test_user",
                repo_urls=["https://github.com/test_owner/test_repo"],
                aliases=["test_user"]
            )
            
            # Should return empty list when no data
            assert isinstance(result, list)


class TestEnsureRepoDataSynced:
    """Test repository data synchronization."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for test data."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_ensure_repo_data_synced_github_success(self, temp_data_dir):
        """Test successful GitHub repo data sync."""
        from evaluator.services.trajectory_service import ensure_repo_data_synced
        
        with patch('evaluator.services.trajectory_service.parse_repo_url') as mock_parse, \
             patch('evaluator.services.trajectory_service.extract_github_data') as mock_extract:
            
            mock_parse.return_value = ("github", "test_owner", "test_repo")
            mock_extract.return_value = True
            
            platform, owner, repo, success = ensure_repo_data_synced(
                "https://github.com/test_owner/test_repo"
            )
            
            assert platform == "github"
            assert owner == "test_owner"
            assert repo == "test_repo"
            assert success is True

    def test_ensure_repo_data_synced_gitee_success(self, temp_data_dir):
        """Test successful Gitee repo data sync."""
        from evaluator.services.trajectory_service import ensure_repo_data_synced
        
        with patch('evaluator.services.trajectory_service.parse_repo_url') as mock_parse, \
             patch('evaluator.services.trajectory_service.extract_gitee_data') as mock_extract:
            
            mock_parse.return_value = ("gitee", "test_owner", "test_repo")
            mock_extract.return_value = True
            
            platform, owner, repo, success = ensure_repo_data_synced(
                "https://gitee.com/test_owner/test_repo"
            )
            
            assert platform == "gitee"
            assert owner == "test_owner"
            assert repo == "test_repo"
            assert success is True

    def test_ensure_repo_data_synced_extraction_failure(self, temp_data_dir):
        """Test repo data sync when extraction fails."""
        from evaluator.services.trajectory_service import ensure_repo_data_synced
        
        with patch('evaluator.services.trajectory_service.parse_repo_url') as mock_parse, \
             patch('evaluator.services.trajectory_service.extract_github_data') as mock_extract:
            
            mock_parse.return_value = ("github", "test_owner", "test_repo")
            mock_extract.return_value = False
            
            with pytest.raises(Exception) as exc_info:
                ensure_repo_data_synced("https://github.com/test_owner/test_repo")
            
            assert "Failed to extract" in str(exc_info.value)

    def test_ensure_repo_data_synced_network_error(self, temp_data_dir):
        """Test repo data sync with network error."""
        from evaluator.services.trajectory_service import ensure_repo_data_synced
        
        with patch('evaluator.services.trajectory_service.parse_repo_url') as mock_parse, \
             patch('evaluator.services.trajectory_service.extract_github_data') as mock_extract:
            
            mock_parse.return_value = ("github", "test_owner", "test_repo")
            mock_extract.side_effect = Exception("Failed to resolve DNS")
            
            with pytest.raises(Exception) as exc_info:
                ensure_repo_data_synced("https://github.com/test_owner/test_repo")
            
            assert "Network error" in str(exc_info.value) or "DNS" in str(exc_info.value)

    def test_ensure_repo_data_synced_unsupported_platform(self, temp_data_dir):
        """Test repo data sync with unsupported platform."""
        from evaluator.services.trajectory_service import ensure_repo_data_synced
        
        with patch('evaluator.services.trajectory_service.parse_repo_url') as mock_parse:
            mock_parse.return_value = ("unknown", "test_owner", "test_repo")
            
            with pytest.raises(Exception) as exc_info:
                ensure_repo_data_synced("https://unknown.com/test_owner/test_repo")
            
            assert "Unsupported platform" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
