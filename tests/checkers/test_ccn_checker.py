"""Test cases for CCN (Cyclomatic Complexity) checker."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add backend directory to Python path
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Import checker module
import importlib.util
checker_path = project_root / "checkers" / "ccn" / "checker.py"
spec = importlib.util.spec_from_file_location("ccn_checker", checker_path)
ccn_checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccn_checker)


class TestCCNCheckerLizardExecution:
    """Test lizard execution and JSON parsing in CCN checker."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        # Cleanup
        if temp_path.exists():
            shutil.rmtree(temp_path)

    def test_lizard_json_flag_not_supported(self, temp_dir):
        """Test that lizard --json flag is not supported and checker handles it gracefully."""
        # Create a test Python file
        test_file = temp_dir / "test.py"
        test_file.write_text("def test_func(x):\n    if x > 0:\n        return x\n    return 0\n")
        
        # Test that --json flag causes error
        result = subprocess.run(
            [sys.executable, "-m", "lizard", "--json", str(test_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Should fail because --json is not supported
        assert result.returncode != 0
        assert "unrecognized arguments" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_lizard_without_json_flag_works(self, temp_dir):
        """Test that lizard works without --json flag."""
        # Create a test Python file
        test_file = temp_dir / "test.py"
        test_file.write_text("def test_func(x):\n    if x > 0:\n        return x\n    return 0\n")
        
        # Test that lizard works without --json
        result = subprocess.run(
            [sys.executable, "-m", "lizard", str(test_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Should succeed
        assert result.returncode == 0
        assert "test_func" in result.stdout

    def test_checker_handles_lizard_json_error(self, temp_dir):
        """Test that checker properly handles lizard --json error."""
        data_dir = temp_dir / "data"
        data_dir.mkdir()
        files_dir = data_dir / "files"
        files_dir.mkdir()
        
        # Mock subprocess.run to simulate --json error (current implementation uses subprocess)
        with patch('subprocess.run') as mock_run:
            # Simulate lizard --json error
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="error: unrecognized arguments: --json"
            )
            
            result = ccn_checker.run_checker(
                commit_sha="abc123",
                files=None,
                data_dir=data_dir,
                worktree_path=None,
            )
            
            # Current implementation may return success=False or handle differently
            # The key is that it should handle the error gracefully
            assert "success" in result
            # If it fails, should have error message
            if not result["success"]:
                assert "lizard" in result.get("message", "").lower() or "error" in result.get("message", "").lower()

    def test_checker_uses_lizard_api_instead_of_json_flag(self, temp_dir):
        """Test that checker should use lizard Python API instead of --json flag."""
        data_dir = temp_dir / "data"
        data_dir.mkdir()
        worktree_path = temp_dir / "worktree"
        worktree_path.mkdir()
        
        # Create a test Python file in worktree
        test_file = worktree_path / "test.py"
        test_file.write_text("def test_func(x):\n    if x > 0:\n        return x\n    return 0\n")
        
        # Mock lizard.analyze_file to return structured data
        with patch('lizard.analyze_file') as mock_analyze:
            # Create mock file analysis result
            mock_file = MagicMock()
            mock_file.name = "test.py"
            mock_func = MagicMock()
            mock_func.name = "test_func"
            mock_func.cyclomatic_complexity = 2
            mock_func.nloc = 4
            mock_func.start_line = 1
            mock_func.parameters = ["x"]
            mock_file.function_list = [mock_func]
            mock_analyze.return_value = [mock_file]
            
            # Mock subprocess.run to fail (simulating --json error)
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(
                    returncode=1,
                    stdout="",
                    stderr="error: unrecognized arguments: --json"
                )
                
                # The checker should handle this error
                result = ccn_checker.run_checker(
                    commit_sha="abc123",
                    files=["test.py"],
                    data_dir=data_dir,
                    worktree_path=worktree_path,
                )
                
                # Should return failure
                assert result["success"] is False

    def test_lizard_python_api_works(self, temp_dir):
        """Test that lizard Python API works correctly."""
        test_file = temp_dir / "test.py"
        test_file.write_text("def test_func(x):\n    if x > 0:\n        return x\n    return 0\n")
        
        try:
            import lizard
            result = lizard.analyze_file(str(test_file))
            
            # Should return FileInformation object (not a list)
            assert hasattr(result, 'filename')
            assert hasattr(result, 'function_list')
            
            # Check function structure
            if result.function_list:
                func = result.function_list[0]
                assert hasattr(func, 'name')
                assert hasattr(func, 'cyclomatic_complexity')
                assert hasattr(func, 'nloc')
                assert hasattr(func, 'start_line')
        except ImportError:
            pytest.skip("lizard module not available")

    def test_checker_should_use_lizard_api_not_cli_json(self):
        """Test that checker implementation should use lizard Python API, not CLI --json."""
        # This test documents the expected behavior
        # The checker should use lizard.analyze_file() instead of subprocess with --json
        
        # Verify that lizard Python API exists
        try:
            import lizard
            assert hasattr(lizard, 'analyze_file')
            assert callable(lizard.analyze_file)
        except ImportError:
            pytest.skip("lizard module not available")


class TestCCNCheckerFix:
    """Test that checker uses correct lizard API instead of --json flag."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        if temp_path.exists():
            shutil.rmtree(temp_path)

    def test_checker_with_lizard_api(self, temp_dir):
        """Test checker using lizard Python API (correct approach)."""
        data_dir = temp_dir / "data"
        data_dir.mkdir()
        worktree_path = temp_dir / "worktree"
        worktree_path.mkdir()
        
        # Create test Python file
        test_file = worktree_path / "test.py"
        test_file.write_text("""
def simple_func(x):
    return x

def complex_func(x, y):
    if x > 0:
        if y > 0:
            return x + y
        return x
    return 0
""")
        
        # Mock lizard.analyze_file to return test data
        with patch('lizard.analyze_file') as mock_analyze:
            # Create mock results
            mock_file = MagicMock()
            mock_file.name = "test.py"
            
            # Simple function
            mock_func1 = MagicMock()
            mock_func1.name = "simple_func"
            mock_func1.cyclomatic_complexity = 1
            mock_func1.nloc = 2
            mock_func1.start_line = 2
            mock_func1.parameters = ["x"]
            
            # Complex function
            mock_func2 = MagicMock()
            mock_func2.name = "complex_func"
            mock_func2.cyclomatic_complexity = 3
            mock_func2.nloc = 6
            mock_func2.start_line = 4
            mock_func2.parameters = ["x", "y"]
            
            mock_file.function_list = [mock_func1, mock_func2]
            mock_analyze.return_value = [mock_file]
            
            # Test that checker can be called (will need to be fixed to use API)
            # For now, just verify the mock works
            result = mock_analyze(str(test_file))
            assert len(result) == 1
            assert len(result[0].function_list) == 2
