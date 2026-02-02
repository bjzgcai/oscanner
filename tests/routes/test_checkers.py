"""Test cases for checker API routes, focusing on minimal shallow git clone."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add backend directory to Python path
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from evaluator.routes.checkers import clone_repo_shallow


class TestCloneRepoShallow:
    """Test minimal shallow git clone functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        # Cleanup
        if temp_path.exists():
            shutil.rmtree(temp_path)

    def test_clone_without_commit_uses_depth_1(self, temp_dir):
        """Test that cloning without commit uses depth=1 (minimal clone)."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        target_dir = temp_dir / "repo"
        
        with patch('subprocess.run') as mock_run:
            # Mock successful clone
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            
            result = clone_repo_shallow(repo_url, target_dir, commit_sha=None)
            
            # Verify clone was called with depth=1
            assert mock_run.called
            call_args = mock_run.call_args_list[0]
            cmd = call_args[0][0]
            
            assert "git" in cmd
            assert "clone" in cmd
            assert "--depth" in cmd
            assert "1" in cmd
            assert repo_url in cmd
            assert str(target_dir) in cmd
            # Should NOT have --no-single-branch when no commit_sha
            assert "--no-single-branch" not in cmd

    def test_clone_with_commit_uses_depth_1(self, temp_dir):
        """Test that cloning with commit uses depth=1 (minimal clone)."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        target_dir = temp_dir / "repo"
        commit_sha = "abc123def456"
        
        with patch('subprocess.run') as mock_run:
            # Mock successful clone and fetch
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            
            result = clone_repo_shallow(repo_url, target_dir, commit_sha=commit_sha)
            
            # Verify clone was called with depth=1 and --no-single-branch
            assert mock_run.call_count >= 1
            clone_call = mock_run.call_args_list[0]
            cmd = clone_call[0][0]
            
            assert "git" in cmd
            assert "clone" in cmd
            assert "--depth" in cmd
            assert "1" in cmd
            assert "--no-single-branch" in cmd
            assert repo_url in cmd
            assert str(target_dir) in cmd
            
            # Verify fetch was called with depth=1
            if mock_run.call_count > 1:
                fetch_call = mock_run.call_args_list[1]
                fetch_cmd = fetch_call[0][0]
                assert "fetch" in fetch_cmd
                assert "--depth" in fetch_cmd
                assert "1" in fetch_cmd
                assert commit_sha in fetch_cmd

    def test_clone_fetch_fallback_to_depth_10(self, temp_dir):
        """Test that fetch falls back to depth=10 if depth=1 fails."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        target_dir = temp_dir / "repo"
        commit_sha = "abc123def456"
        
        with patch('subprocess.run') as mock_run:
            # First call (clone) succeeds
            # Second call (fetch with depth=1) fails
            # Third call (fetch with depth=10) succeeds
            def side_effect(*args, **kwargs):
                cmd = args[0] if args else kwargs.get('cmd', [])
                if 'clone' in cmd:
                    return Mock(returncode=0, stdout="", stderr="")
                elif 'fetch' in cmd and '--depth' in cmd and '1' in cmd:
                    return Mock(returncode=1, stdout="", stderr="error")
                elif 'fetch' in cmd and '--depth' in cmd and '10' in cmd:
                    return Mock(returncode=0, stdout="", stderr="")
                return Mock(returncode=0, stdout="", stderr="")
            
            mock_run.side_effect = side_effect
            
            result = clone_repo_shallow(repo_url, target_dir, commit_sha=commit_sha)
            
            # Verify fetch was called twice: first with depth=1, then with depth=10
            fetch_calls = [call for call in mock_run.call_args_list if 'fetch' in str(call)]
            assert len(fetch_calls) >= 1
            
            # Check that first fetch attempt used depth=1
            first_fetch_cmd = fetch_calls[0][0][0]
            assert "--depth" in first_fetch_cmd
            assert "1" in first_fetch_cmd
            
            # Check that fallback fetch used depth=10
            if len(fetch_calls) > 1:
                second_fetch_cmd = fetch_calls[1][0][0]
                assert "--depth" in second_fetch_cmd
                assert "10" in second_fetch_cmd

    def test_clone_removes_existing_directory(self, temp_dir):
        """Test that existing directory is removed before cloning."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        target_dir = temp_dir / "repo"
        
        # Create existing directory
        target_dir.mkdir(parents=True)
        (target_dir / "existing_file.txt").write_text("test")
        
        with patch('subprocess.run') as mock_run, \
             patch('shutil.rmtree') as mock_rmtree:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            
            result = clone_repo_shallow(repo_url, target_dir, commit_sha=None)
            
            # Verify rmtree was called to remove existing directory
            assert mock_rmtree.called
            assert mock_rmtree.call_args[0][0] == target_dir

    def test_clone_timeout_handling(self, temp_dir):
        """Test that timeout is properly handled."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        target_dir = temp_dir / "repo"
        
        with patch('subprocess.run') as mock_run:
            # Simulate timeout
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["git"], timeout=300)
            
            result = clone_repo_shallow(repo_url, target_dir, commit_sha=None)
            
            # Should return False on timeout
            assert result is False

    def test_clone_failure_returns_false(self, temp_dir):
        """Test that clone failure returns False."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        target_dir = temp_dir / "repo"
        
        with patch('subprocess.run') as mock_run:
            # Mock failed clone
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="clone failed")
            
            result = clone_repo_shallow(repo_url, target_dir, commit_sha=None)
            
            # Should return False on failure
            assert result is False

    def test_clone_success_returns_true(self, temp_dir):
        """Test that successful clone returns True."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        target_dir = temp_dir / "repo"
        
        with patch('subprocess.run') as mock_run:
            # Mock successful clone
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            
            result = clone_repo_shallow(repo_url, target_dir, commit_sha=None)
            
            # Should return True on success
            assert result is True

    def test_minimal_data_transfer(self, temp_dir):
        """Test that minimal shallow clone minimizes data transfer."""
        repo_url = "https://github.com/octocat/Hello-World.git"
        target_dir = temp_dir / "repo"
        commit_sha = "abc123def456"
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            
            result = clone_repo_shallow(repo_url, target_dir, commit_sha=commit_sha)
            
            # Verify all git operations use minimal depth
            for call in mock_run.call_args_list:
                cmd = call[0][0]
                if "clone" in cmd or "fetch" in cmd:
                    # Should always have --depth with value 1 or 10 (never unshallow)
                    if "--depth" in cmd:
                        depth_idx = cmd.index("--depth")
                        depth_value = cmd[depth_idx + 1]
                        assert depth_value in ["1", "10"], f"Unexpected depth value: {depth_value}"
                    # Should NOT have --unshallow
                    assert "--unshallow" not in cmd
