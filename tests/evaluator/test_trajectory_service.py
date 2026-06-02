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
    get_commits_by_date,
)


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

    def test_ensure_repo_data_synced_uses_existing_data_when_not_forced(self, temp_data_dir):
        """Test that existing local data is reused when force_sync=False."""
        from evaluator.services.trajectory_service import ensure_repo_data_synced

        repo_dir = temp_data_dir / "github" / "test_owner" / "test_repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "commits_index.json").write_text("[]", encoding="utf-8")

        with patch('evaluator.services.trajectory_service.parse_repo_url') as mock_parse, \
             patch('evaluator.services.trajectory_service.get_platform_data_dir') as mock_data_dir, \
             patch('evaluator.services.trajectory_service.extract_github_data') as mock_extract:

            mock_parse.return_value = ("github", "test_owner", "test_repo")
            mock_data_dir.return_value = repo_dir

            platform, owner, repo, success = ensure_repo_data_synced(
                "https://github.com/test_owner/test_repo",
                force_sync=False
            )

            assert platform == "github"
            assert owner == "test_owner"
            assert repo == "test_repo"
            assert success is False
            mock_extract.assert_not_called()

    def test_ensure_repo_data_synced_refreshes_snapshot_for_requested_end_sha(self, temp_data_dir):
        """A requested end_sha should refresh complete repo files even when commit data exists."""
        from evaluator.services.trajectory_service import ensure_repo_data_synced

        repo_dir = temp_data_dir / "github" / "test_owner" / "test_repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "commits_index.json").write_text('[{"sha": "latest"}]', encoding="utf-8")

        with patch('evaluator.services.trajectory_service.parse_repo_url') as mock_parse, \
             patch('evaluator.services.trajectory_service.get_platform_data_dir') as mock_data_dir, \
             patch('evaluator.services.trajectory_service.extract_repo_files_at_commit_via_git') as mock_snapshot, \
             patch('evaluator.services.trajectory_service.extract_github_data') as mock_extract:

            mock_parse.return_value = ("github", "test_owner", "test_repo")
            mock_data_dir.return_value = repo_dir
            mock_snapshot.return_value = True

            platform, owner, repo, success = ensure_repo_data_synced(
                "https://github.com/test_owner/test_repo",
                force_sync=False,
                snapshot_sha="end123",
            )

            assert platform == "github"
            assert owner == "test_owner"
            assert repo == "test_repo"
            assert success is True
            mock_snapshot.assert_called_once_with("github", "test_owner", "test_repo", repo_dir, "end123")
            mock_extract.assert_not_called()

    def test_refresh_group_repo_snapshot_for_item_end_sha(self, temp_data_dir):
        """Group repo items should refresh repo_files at each item's end_sha."""
        from evaluator.services.trajectory_service import _refresh_group_repo_snapshot_for_end_sha

        repo_dir = temp_data_dir / "gitee" / "test_owner" / "test_repo"
        repo_dir.mkdir(parents=True)
        sync_result = {
            "success": True,
            "platform": "gitee",
            "owner": "test_owner",
            "repo": "test_repo",
        }

        with patch('evaluator.services.trajectory_service.extract_repo_files_at_commit_via_git') as mock_snapshot:
            mock_snapshot.return_value = True

            updated_sync, refreshed = _refresh_group_repo_snapshot_for_end_sha(
                "https://gitee.com/test_owner/test_repo",
                {"end_sha": "end123"},
                sync_result,
                repo_dir,
            )

            assert refreshed is True
            assert updated_sync["snapshot_sha"] == "end123"
            assert updated_sync["snapshot_refreshed"] is True
            mock_snapshot.assert_called_once_with("gitee", "test_owner", "test_repo", repo_dir, "end123")

    def test_ensure_repo_data_synced_force_sync_reextracts_when_data_exists(self, temp_data_dir):
        """Test that force_sync=True triggers re-extraction even with existing local data."""
        from evaluator.services.trajectory_service import ensure_repo_data_synced

        repo_dir = temp_data_dir / "gitee" / "test_owner" / "test_repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "commits_index.json").write_text("[]", encoding="utf-8")

        with patch('evaluator.services.trajectory_service.parse_repo_url') as mock_parse, \
             patch('evaluator.services.trajectory_service.get_platform_data_dir') as mock_data_dir, \
             patch('evaluator.services.trajectory_service.extract_gitee_data') as mock_extract:

            mock_parse.return_value = ("gitee", "test_owner", "test_repo")
            mock_data_dir.return_value = repo_dir
            mock_extract.return_value = True

            platform, owner, repo, success = ensure_repo_data_synced(
                "https://gitee.com/test_owner/test_repo",
                force_sync=True
            )

            assert platform == "gitee"
            assert owner == "test_owner"
            assert repo == "test_repo"
            assert success is True
            mock_extract.assert_called_once_with("test_owner", "test_repo", max_commits=500)

    def test_ensure_repo_data_synced_gitee_uses_incremental_sync_when_not_forced(self, temp_data_dir):
        """Existing Gitee data should use the fast incremental sync path instead of full extraction."""
        from evaluator.services.trajectory_service import ensure_repo_data_synced

        repo_dir = temp_data_dir / "gitee" / "test_owner" / "test_repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "commits_index.json").write_text("[]", encoding="utf-8")

        with patch('evaluator.services.trajectory_service.parse_repo_url') as mock_parse, \
             patch('evaluator.services.trajectory_service.get_platform_data_dir') as mock_data_dir, \
             patch('evaluator.services.trajectory_service.sync_gitee_data_incremental') as mock_incremental, \
             patch('evaluator.services.trajectory_service.extract_gitee_data') as mock_extract:

            mock_parse.return_value = ("gitee", "test_owner", "test_repo")
            mock_data_dir.return_value = repo_dir
            mock_incremental.return_value = True

            platform, owner, repo, success = ensure_repo_data_synced(
                "https://gitee.com/test_owner/test_repo",
                force_sync=False,
            )

            assert platform == "gitee"
            assert owner == "test_owner"
            assert repo == "test_repo"
            assert success is True
            mock_incremental.assert_called_once_with("test_owner", "test_repo", max_commits=500)
            mock_extract.assert_not_called()

    def test_analyze_growth_trajectory_uses_fresh_repo_data_and_all_commits(self, temp_data_dir):
        """Trajectory analysis should force sync and evaluate without previous trajectory state."""
        from evaluator.services.trajectory_service import analyze_growth_trajectory, ONE_OFF_MAX_COMMITS

        with patch('evaluator.services.trajectory_service.ensure_repo_data_synced') as mock_sync, \
             patch('evaluator.services.trajectory_service.get_new_commits_from_repos') as mock_new_commits, \
             patch('evaluator.services.trajectory_service.get_repo_start_date') as mock_start_date:

            mock_sync.return_value = ("gitee", "test_owner", "test_repo", False)
            mock_new_commits.return_value = (0, [], ["https://gitee.com/test_owner/test_repo"])
            mock_start_date.return_value = datetime(2026, 1, 1)

            response = analyze_growth_trajectory(
                username="Alice",
                repo_urls=["https://gitee.com/test_owner/test_repo"],
                aliases=["Alice"],
                plugin_id="zgc_ai_native_2026",
                model="deepseek/deepseek-v4-pro",
                language="zh-CN",
                checkpoint_strategy="none",
            )

            assert response.success is True
            assert mock_sync.call_args.kwargs["force_sync"] is True
            assert mock_sync.call_args.kwargs["max_commits"] == ONE_OFF_MAX_COMMITS
            assert mock_new_commits.call_args.kwargs["last_synced_sha"] is None

    def test_analyze_growth_trajectory_warns_when_one_off_cap_hides_author_commits(self, temp_data_dir):
        """When a capped one-off sync finds no author commits, explain the cap in the failure."""
        from evaluator.services import trajectory_service
        from evaluator.services.trajectory_service import analyze_growth_trajectory

        repo_dir = temp_data_dir / "github" / "test_owner" / "test_repo"
        repo_dir.mkdir(parents=True)
        with open(repo_dir / "commits_index.json", "w", encoding="utf-8") as f:
            json.dump([{"sha": f"commit-{idx}"} for idx in range(3)], f)

        with patch.object(trajectory_service, "ONE_OFF_MAX_COMMITS", 3), \
             patch('evaluator.services.trajectory_service.get_platform_data_dir') as mock_get_dir, \
             patch('evaluator.services.trajectory_service.ensure_repo_data_synced') as mock_sync, \
             patch('evaluator.services.trajectory_service.get_new_commits_from_repos') as mock_new_commits, \
             patch('evaluator.services.trajectory_service.get_repo_start_date') as mock_start_date:

            mock_get_dir.return_value = repo_dir
            mock_sync.return_value = ("github", "test_owner", "test_repo", True)
            mock_new_commits.return_value = (0, [], ["https://github.com/test_owner/test_repo"])
            mock_start_date.return_value = None

            response = analyze_growth_trajectory(
                username="vczh@163.com",
                repo_urls=["https://github.com/test_owner/test_repo"],
                aliases=["vczh@163.com"],
                plugin_id="zgc_ai_native_2026",
                model="deepseek/deepseek-v4-pro",
                language="zh-CN",
                checkpoint_strategy="none",
            )

            assert response.success is False
            assert "No commits found for the specified email" in response.message
            assert "we only fetch 3 commits at most" in response.message
            assert "this repo contains more than 3 commits" in response.message

    def test_create_checkpoint_evaluation_adds_structured_evidence_links(self, temp_data_dir):
        """One-off trajectory checkpoints should carry commit/file evidence links."""
        from evaluator.services.trajectory_service import create_checkpoint_evaluation

        commit_sha = "abc1234567890abcdef"
        commits = [
            {
                "sha": commit_sha,
                "commit": {
                    "author": {"name": "Alice", "email": "alice@example.com", "date": "2026-01-01T00:00:00Z"},
                    "message": "Add parser",
                },
                "files": [{"filename": "src/parser.py"}],
            },
        ]

        mock_evaluator = Mock()
        mock_evaluator.evaluate_engineer.return_value = {
            "username": "Alice",
            "total_commits_analyzed": 1,
            "files_loaded": 0,
            "mode": "moderate",
            "scores": {
                "spec_quality": 70,
                "cloud_architecture": 40,
                "ai_engineering": 50,
                "mastery_professionalism": 60,
                "reasoning": "Evidence based reasoning",
            },
            "commits_summary": {
                "total_additions": 1,
                "total_deletions": 0,
                "files_changed": 1,
                "languages": ["py"],
            },
        }
        mock_scan_mod = Mock()
        mock_scan_mod.create_commit_evaluator.return_value = mock_evaluator
        mock_meta = Mock(version="0.1.0")

        with patch("evaluator.services.trajectory_service.get_platform_data_dir") as mock_data_dir, \
             patch("evaluator.services.trajectory_service.load_scan_module") as mock_load_scan, \
             patch("evaluator.services.trajectory_service.get_llm_api_key") as mock_api_key, \
             patch("evaluator.services.trajectory_service._fetch_combined_collaboration_evidence") as mock_collab:
            mock_data_dir.return_value = temp_data_dir
            mock_load_scan.return_value = (mock_meta, mock_scan_mod, "scan/path")
            mock_api_key.return_value = "fake_key"
            mock_collab.return_value = {}

            checkpoint = create_checkpoint_evaluation(
                commits=commits,
                username="Alice",
                checkpoint_id=1,
                plugin_id="zgc_ai_native_2026",
                model="test-model",
                language="zh-CN",
                repos_analyzed=["https://gitee.com/test_owner/test_repo"],
                aliases_used=["Alice"],
                checkpoint_strategy="none",
            )

        assert checkpoint.evaluation.evidence_links == [
            {
                "type": "commit",
                "label": "abc12345",
                "sha": commit_sha,
                "url": f"https://gitee.com/test_owner/test_repo/commit/{commit_sha}",
            },
            {
                "type": "file",
                "label": "src/parser.py",
                "path": "src/parser.py",
                "commit_sha": commit_sha,
                "url": f"https://gitee.com/test_owner/test_repo/blob/{commit_sha}/src/parser.py",
            },
        ]

    def test_one_off_route_has_no_cache_parameter(self):
        """The public one-off trajectory route should not expose cache strategy."""
        import inspect
        from evaluator.routes.trajectory import analyze_trajectory_one_off

        assert "use_cache" not in inspect.signature(analyze_trajectory_one_off).parameters

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
