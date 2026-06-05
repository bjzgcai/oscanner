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
    REPO_TOO_BIG_MESSAGE,
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
            mock_resolve.return_value = "zgc_ai_native_2026"
            mock_load.return_value = ({"id": "zgc_ai_native_2026"}, mock_scan_mod, "scan/path")
            mock_api_key.return_value = "fake_api_key"
            
            evaluator = get_or_create_evaluator(
                platform="github",
                owner="test_owner",
                repo="test_repo",
                commits=commits,
                plugin_id="zgc_ai_native_2026"
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
            mock_resolve.return_value = "zgc_ai_native_2026"
            mock_load.return_value = ({"id": "zgc_ai_native_2026"}, Mock(), "scan/path")
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
                "spec_quality": 5,
                "cloud_architecture": 4,
                "ai_engineering": 3,
                "mastery_professionalism": 2,
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
            api_key="fake_key",
            evaluator_factory=evaluator_factory
        )
        
        # The function returns evaluation dict which may not have username at top level
        # Check that it's a dict with expected keys
        assert isinstance(result, dict)
        assert result.get("total_commits_evaluated") == 2
        assert result.get("new_commits_count") == 2
        assert result.get("incremental") is False
        assert result.get("scores", {}).get("spec_quality") == 5
        mock_evaluator.evaluate_engineer.assert_called_once()

    def test_evaluate_author_incremental_adds_structured_evidence_links(self, temp_data_dir):
        """Evaluations should include review links for commits and changed files."""
        commit_sha = "abc1234567890abcdef"
        commits = [
            {
                "sha": commit_sha,
                "commit": {
                    "author": {"name": "test_user", "email": "test@example.com"},
                    "message": "Add parser",
                },
                "files": [
                    {"filename": "src/parser.py", "additions": 12, "deletions": 1},
                    {"filename": "docs/usage guide.md", "additions": 4, "deletions": 0},
                ],
            },
        ]

        mock_evaluator = Mock()
        mock_evaluator.evaluate_engineer = Mock(return_value={
            "scores": {"spec_quality": 5, "reasoning": "Test reasoning"},
            "commits_summary": {
                "total_additions": 16,
                "total_deletions": 1,
                "files_changed": 2,
                "languages": ["Python"],
            },
        })

        result = evaluate_author_incremental(
            commits=commits,
            author="test_user",
            previous_evaluation=None,
            data_dir=temp_data_dir,
            model="test-model",
            api_key="fake_key",
            platform="github",
            owner="test_owner",
            repo="test_repo",
            evaluator_factory=lambda: mock_evaluator,
        )

        assert result["evidence_links"] == [
            {
                "type": "commit",
                "label": "abc12345",
                "sha": commit_sha,
                "url": f"https://github.com/test_owner/test_repo/commit/{commit_sha}",
            },
            {
                "type": "file",
                "label": "src/parser.py",
                "path": "src/parser.py",
                "commit_sha": commit_sha,
                "url": f"https://github.com/test_owner/test_repo/blob/{commit_sha}/src/parser.py",
            },
            {
                "type": "dir",
                "label": "src/",
                "path": "src/",
                "commit_sha": commit_sha,
                "url": f"https://github.com/test_owner/test_repo/tree/{commit_sha}/src",
            },
            {
                "type": "file",
                "label": "docs/usage guide.md",
                "path": "docs/usage guide.md",
                "commit_sha": commit_sha,
                "url": f"https://github.com/test_owner/test_repo/blob/{commit_sha}/docs/usage%20guide.md",
            },
            {
                "type": "dir",
                "label": "docs/",
                "path": "docs/",
                "commit_sha": commit_sha,
                "url": f"https://github.com/test_owner/test_repo/tree/{commit_sha}/docs",
            },
        ]

    def test_evaluate_author_incremental_merges_previous_evidence_links(self, temp_data_dir):
        """Incremental evaluations should preserve old review links and append new ones."""
        previous_evaluation = {
            "last_commit_sha": "old123",
            "total_commits_evaluated": 1,
            "scores": {"spec_quality": 3, "reasoning": "Previous reasoning"},
            "commits_summary": {
                "total_additions": 1,
                "total_deletions": 0,
                "files_changed": 1,
                "languages": ["Python"],
            },
            "evidence_links": [
                {
                    "type": "commit",
                    "label": "old123",
                    "sha": "old123",
                    "url": "https://github.com/test_owner/test_repo/commit/old123",
                },
            ],
        }
        commits = [
            {
                "sha": "new456",
                "commit": {
                    "author": {"name": "test_user", "email": "test@example.com"},
                    "message": "New commit",
                },
                "files": [{"filename": "src/new.py"}],
            },
            {
                "sha": "old123",
                "commit": {
                    "author": {"name": "test_user", "email": "test@example.com"},
                    "message": "Old commit",
                },
            },
        ]

        mock_evaluator = Mock()
        mock_evaluator.evaluate_engineer = Mock(return_value={
            "scores": {"spec_quality": 7, "reasoning": "New reasoning"},
            "commits_summary": {
                "total_additions": 2,
                "total_deletions": 0,
                "files_changed": 1,
                "languages": ["Python"],
            },
        })

        result = evaluate_author_incremental(
            commits=commits,
            author="test_user",
            previous_evaluation=previous_evaluation,
            data_dir=temp_data_dir,
            model="test-model",
            api_key="fake_key",
            platform="github",
            owner="test_owner",
            repo="test_repo",
            evaluator_factory=lambda: mock_evaluator,
        )

        urls = [link["url"] for link in result["evidence_links"]]
        assert urls == [
            "https://github.com/test_owner/test_repo/commit/old123",
            "https://github.com/test_owner/test_repo/commit/new456",
            "https://github.com/test_owner/test_repo/blob/new456/src/new.py",
            "https://github.com/test_owner/test_repo/tree/new456/src",
        ]

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
                "spec_quality": 3,
                "cloud_architecture": 2,
                "ai_engineering": 1,
                "mastery_professionalism": 0,
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
                "spec_quality": 7,
                "cloud_architecture": 6,
                "ai_engineering": 5,
                "mastery_professionalism": 4,
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
            api_key="fake_key",
            evaluator_factory=evaluator_factory
        )
        
        assert result["username"] == "test_user"
        assert result["total_commits_evaluated"] == 2  # 1 old + 1 new
        assert result["new_commits_count"] == 1
        assert result["incremental"] is True
        # Verify weighted average: (3*1 + 7*1) / 2 = 5
        assert result["scores"]["spec_quality"] == 5
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
            "scores": {"spec_quality": 5},
        }
        
        result = evaluate_author_incremental(
            commits=commits,
            author="test_user",
            previous_evaluation=previous_evaluation,
            data_dir=temp_data_dir,
            model="test-model",
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
                api_key="fake_key",
                evaluator_factory=None
            )
        
        assert exc_info.value.status_code == 500
        assert "Evaluator factory" in str(exc_info.value.detail)

    def test_evaluate_author_incremental_stops_when_repo_context_exceeds_guardrail(self, temp_data_dir, monkeypatch):
        """Evaluation should stop before LLM work when repo files plus commit messages exceed the hard limit."""
        repo_files_dir = temp_data_dir / "repo_files"
        repo_files_dir.mkdir()
        (temp_data_dir / "repo_files_manifest.json").write_text("{}", encoding="utf-8")
        (repo_files_dir / "app.py").write_text("x" * 20, encoding="utf-8")
        monkeypatch.setattr(
            "evaluator.services.evaluation_service.MAX_REPO_EVALUATION_INPUT_TOKENS",
            25,
        )

        commits = [
            {
                "sha": "abc123",
                "commit": {
                    "author": {"name": "test_user", "email": "test@example.com"},
                    "message": "message over limit",
                },
            },
        ]

        def fail_factory():
            raise AssertionError("evaluator must not be constructed for oversized repo input")

        with pytest.raises(HTTPException) as exc_info:
            evaluate_author_incremental(
                commits=commits,
                author="test_user",
                previous_evaluation=None,
                data_dir=temp_data_dir,
                model="test-model",
                api_key="fake_key",
                evaluator_factory=fail_factory,
            )

        assert exc_info.value.status_code == 413
        assert exc_info.value.detail == REPO_TOO_BIG_MESSAGE

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
