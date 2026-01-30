"""Test cases for evaluation service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import sys
from datetime import datetime

# Add project root to path if not already there
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add backend directory to Python path so evaluator can be imported as top-level package
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from evaluator.services.evaluation_service import (
    get_or_create_evaluator,
    evaluate_author_incremental,
    get_empty_evaluation,
)
from fastapi import HTTPException


class TestGetOrCreateEvaluator:
    """Test evaluator creation functionality."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for test data."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_get_or_create_evaluator_success(self, temp_data_dir):
        """Test successful evaluator creation."""
        commits = [
            {"sha": "abc123", "commit": {"message": "Test commit"}},
            {"sha": "def456", "commit": {"message": "Another commit"}},
        ]
        
        mock_evaluator = Mock()
        mock_evaluator.evaluate_engineer = Mock()
        
        mock_scan_mod = Mock()
        mock_scan_mod.create_commit_evaluator = Mock(return_value=mock_evaluator)
        
        with patch('evaluator.services.evaluation_service.get_repo_data_dir') as mock_get_dir, \
             patch('evaluator.services.evaluation_service.resolve_plugin_id') as mock_resolve, \
             patch('evaluator.services.evaluation_service.load_scan_module') as mock_load, \
             patch('evaluator.services.evaluation_service.get_llm_api_key') as mock_api_key:
            
            mock_get_dir.return_value = temp_data_dir
            mock_resolve.return_value = "zgc_simple"
            mock_load.return_value = ({"id": "zgc_simple"}, mock_scan_mod, "scan/path")
            mock_api_key.return_value = "fake_api_key"
            
            evaluator = get_or_create_evaluator(
                platform="github",
                owner="test_owner",
                repo="test_repo",
                commits=commits,
                plugin_id="zgc_simple"
            )
            
            assert evaluator == mock_evaluator
            # Verify commits were saved
            assert (temp_data_dir / "commits_index.json").exists()
            assert (temp_data_dir / "commits" / "abc123.json").exists()
            assert (temp_data_dir / "commits" / "def456.json").exists()
            assert (temp_data_dir / "repo_info.json").exists()

    def test_get_or_create_evaluator_no_llm_key(self, temp_data_dir):
        """Test evaluator creation fails when LLM key is missing."""
        commits = [{"sha": "abc123"}]
        
        with patch('evaluator.services.evaluation_service.get_repo_data_dir') as mock_get_dir, \
             patch('evaluator.services.evaluation_service.resolve_plugin_id') as mock_resolve, \
             patch('evaluator.services.evaluation_service.load_scan_module') as mock_load, \
             patch('evaluator.services.evaluation_service.get_llm_api_key') as mock_api_key:
            
            mock_get_dir.return_value = temp_data_dir
            mock_resolve.return_value = "zgc_simple"
            mock_load.return_value = ({"id": "zgc_simple"}, Mock(), "scan/path")
            mock_api_key.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                get_or_create_evaluator(
                    platform="github",
                    owner="test_owner",
                    repo="test_repo",
                    commits=commits
                )
            
            assert exc_info.value.status_code == 500
            assert "LLM not configured" in str(exc_info.value.detail)


class TestEvaluateAuthorIncremental:
    """Test incremental evaluation functionality."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for test data."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_evaluate_author_incremental_no_previous(self, temp_data_dir):
        """Test incremental evaluation with no previous evaluation."""
        commits = [
            {
                "sha": "abc123",
                "commit": {
                    "author": {"name": "test_user", "email": "test@example.com"},
                    "message": "Test commit"
                }
            },
            {
                "sha": "def456",
                "commit": {
                    "author": {"name": "test_user", "email": "test@example.com"},
                    "message": "Another commit"
                }
            },
        ]
        
        mock_evaluator = Mock()
        mock_evaluator.evaluate_engineer = Mock(return_value={
            "scores": {
                "ai_fullstack": 5,
                "ai_architecture": 4,
                "cloud_native": 3,
                "open_source": 2,
                "intelligent_dev": 1,
                "leadership": 0,
                "reasoning": "Test reasoning"
            },
            "commits_summary": {
                "total_additions": 100,
                "total_deletions": 50,
                "files_changed": 10,
                "languages": ["Python"]
            }
        })
        
        def evaluator_factory():
            return mock_evaluator
        
        result = evaluate_author_incremental(
            commits=commits,
            author="test_user",
            previous_evaluation=None,
            data_dir=temp_data_dir,
            model="test-model",
            use_chunking=False,
            api_key="fake_key",
            evaluator_factory=evaluator_factory
        )
        
        # The function returns evaluation dict which may not have username at top level
        # Check that it's a dict with expected keys
        assert isinstance(result, dict)
        assert result.get("total_commits_evaluated") == 2
        assert result.get("new_commits_count") == 2
        assert result.get("incremental") is False
        assert result.get("scores", {}).get("ai_fullstack") == 5
        mock_evaluator.evaluate_engineer.assert_called_once()

    def test_evaluate_author_incremental_with_previous(self, temp_data_dir):
        """Test incremental evaluation with previous evaluation."""
        old_commits = [
            {
                "sha": "old123",
                "commit": {
                    "author": {"name": "test_user", "email": "test@example.com"},
                    "message": "Old commit"
                }
            },
        ]
        new_commits = [
            {
                "sha": "new456",
                "commit": {
                    "author": {"name": "test_user", "email": "test@example.com"},
                    "message": "New commit"
                }
            },
        ]
        all_commits = new_commits + old_commits  # Newest first
        
        previous_evaluation = {
            "last_commit_sha": "old123",
            "total_commits_evaluated": 1,
            "scores": {
                "ai_fullstack": 3,
                "ai_architecture": 2,
                "cloud_native": 1,
                "open_source": 0,
                "intelligent_dev": 0,
                "leadership": 0,
                "reasoning": "Previous reasoning"
            },
            "commits_summary": {
                "total_additions": 50,
                "total_deletions": 25,
                "files_changed": 5,
                "languages": ["Python"]
            }
        }
        
        mock_evaluator = Mock()
        mock_evaluator.evaluate_engineer = Mock(return_value={
            "scores": {
                "ai_fullstack": 7,
                "ai_architecture": 6,
                "cloud_native": 5,
                "open_source": 4,
                "intelligent_dev": 3,
                "leadership": 2,
                "reasoning": "New reasoning"
            },
            "commits_summary": {
                "total_additions": 100,
                "total_deletions": 50,
                "files_changed": 10,
                "languages": ["JavaScript"]
            }
        })
        
        def evaluator_factory():
            return mock_evaluator
        
        result = evaluate_author_incremental(
            commits=all_commits,
            author="test_user",
            previous_evaluation=previous_evaluation,
            data_dir=temp_data_dir,
            model="test-model",
            use_chunking=False,
            api_key="fake_key",
            evaluator_factory=evaluator_factory
        )
        
        assert result["username"] == "test_user"
        assert result["total_commits_evaluated"] == 2  # 1 old + 1 new
        assert result["new_commits_count"] == 1
        assert result["incremental"] is True
        # Verify weighted average: (3*1 + 7*1) / 2 = 5
        assert result["scores"]["ai_fullstack"] == 5
        # Verify reasoning is combined
        assert "Recent Activity" in result["scores"]["reasoning"]
        assert "Previous Assessment" in result["scores"]["reasoning"]

    def test_evaluate_author_incremental_no_commits(self, temp_data_dir):
        """Test incremental evaluation with no commits for author."""
        commits = [
            {
                "sha": "abc123",
                "commit": {
                    "author": {"name": "other_user", "email": "other@example.com"},
                    "message": "Other user commit"
                }
            },
        ]
        
        result = evaluate_author_incremental(
            commits=commits,
            author="test_user",
            previous_evaluation=None,
            data_dir=temp_data_dir,
            model="test-model",
            use_chunking=False,
            api_key="fake_key",
            evaluator_factory=lambda: Mock()
        )
        
        assert result["username"] == "test_user"
        assert result["total_commits_evaluated"] == 0
        assert result["scores"]["reasoning"] == "No commits found for this author."

    def test_evaluate_author_incremental_no_new_commits(self, temp_data_dir):
        """Test incremental evaluation when no new commits exist."""
        commits = [
            {
                "sha": "abc123",
                "commit": {
                    "author": {"name": "test_user", "email": "test@example.com"},
                    "message": "Test commit"
                }
            },
        ]
        
        previous_evaluation = {
            "last_commit_sha": "abc123",
            "total_commits_evaluated": 1,
            "scores": {"ai_fullstack": 5},
        }
        
        result = evaluate_author_incremental(
            commits=commits,
            author="test_user",
            previous_evaluation=previous_evaluation,
            data_dir=temp_data_dir,
            model="test-model",
            use_chunking=False,
            api_key="fake_key",
            evaluator_factory=lambda: Mock()
        )
        
        # Should return previous evaluation unchanged
        assert result == previous_evaluation

    def test_evaluate_author_incremental_no_evaluator_factory(self, temp_data_dir):
        """Test incremental evaluation fails when evaluator factory is missing."""
        commits = [{"sha": "abc123", "commit": {"author": {"name": "test_user"}}}]
        
        with pytest.raises(HTTPException) as exc_info:
            evaluate_author_incremental(
                commits=commits,
                author="test_user",
                previous_evaluation=None,
                data_dir=temp_data_dir,
                model="test-model",
                use_chunking=False,
                api_key="fake_key",
                evaluator_factory=None
            )
        
        assert exc_info.value.status_code == 500
        assert "Evaluator factory" in str(exc_info.value.detail)

    def test_evaluate_author_incremental_llm_error(self, temp_data_dir):
        """Test incremental evaluation handles LLM errors."""
        commits = [
            {
                "sha": "abc123",
                "commit": {
                    "author": {"name": "test_user", "email": "test@example.com"},
                    "message": "Test commit"
                }
            },
        ]
        
        mock_evaluator = Mock()
        mock_evaluator.evaluate_engineer = Mock(side_effect=Exception("LLM API error"))
        
        def evaluator_factory():
            return mock_evaluator
        
        with pytest.raises(HTTPException) as exc_info:
            evaluate_author_incremental(
                commits=commits,
                author="test_user",
                previous_evaluation=None,
                data_dir=temp_data_dir,
                model="test-model",
                use_chunking=False,
                api_key="fake_key",
                evaluator_factory=evaluator_factory
            )
        
        assert exc_info.value.status_code == 502
        assert "LLM evaluation failed" in str(exc_info.value.detail)


class TestGetEmptyEvaluation:
    """Test empty evaluation functionality."""

    def test_get_empty_evaluation(self):
        """Test getting empty evaluation for user with no commits."""
        result = get_empty_evaluation("test_user")
        
        assert result["username"] == "test_user"
        assert result["total_commits_evaluated"] == 0
        assert result["new_commits_count"] == 0
        assert result["incremental"] is False
        assert all(score == 0 for key, score in result["scores"].items() if key != "reasoning")
        assert result["scores"]["reasoning"] == "No commits found for this author."
        assert result["commits_summary"]["total_additions"] == 0
        assert result["commits_summary"]["total_deletions"] == 0
        assert result["commits_summary"]["files_changed"] == 0
        assert result["commits_summary"]["languages"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
