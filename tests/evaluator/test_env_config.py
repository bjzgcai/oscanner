"""Tests for evaluator environment loading."""

import os
import sys
from pathlib import Path

# Add project root to path if not already there
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add backend directory to Python path so evaluator can be imported as top-level package
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import evaluator.config.env as env_config
from evaluator.config.env import get_project_env_paths, load_runtime_env


def test_get_project_env_paths_prefers_server_dir_env_and_deduplicates(tmp_path):
    """Server-local .env should be found even when launched from repo root."""
    repo_root = tmp_path / "repo"
    server_dir = repo_root / "backend" / "evaluator"
    server_dir.mkdir(parents=True)

    server_env = server_dir / ".env"
    server_env.write_text("OPEN_ROUTER_KEY=test\n", encoding="utf-8")

    paths = get_project_env_paths(
        server_file=server_dir / "server.py",
        cwd=repo_root,
    )

    assert paths == [server_env.resolve()]


def test_get_project_env_paths_includes_distinct_cwd_env_after_server_env(tmp_path):
    """A root-level .env should still be loaded after the evaluator-local one."""
    repo_root = tmp_path / "repo"
    server_dir = repo_root / "backend" / "evaluator"
    server_dir.mkdir(parents=True)

    server_env = server_dir / ".env"
    root_env = repo_root / ".env"
    server_env.write_text("OPEN_ROUTER_KEY=server\n", encoding="utf-8")
    root_env.write_text("OPEN_ROUTER_KEY=root\n", encoding="utf-8")

    paths = get_project_env_paths(
        server_file=server_dir / "server.py",
        cwd=repo_root,
    )

    assert paths == [server_env.resolve(), root_env.resolve()]


def test_load_runtime_env_restores_non_empty_file_value_over_empty_process_var(tmp_path, monkeypatch):
    """Empty inherited vars should not block non-empty values from .env."""
    repo_root = tmp_path / "repo"
    server_dir = repo_root / "backend" / "evaluator"
    server_dir.mkdir(parents=True)

    server_env = server_dir / ".env"
    server_env.write_text("OPEN_ROUTER_KEY=server-key\n", encoding="utf-8")

    monkeypatch.setenv("OPEN_ROUTER_KEY", "")
    monkeypatch.setattr(env_config, "get_user_env_path", lambda: tmp_path / "missing-user.env.local")

    loaded = load_runtime_env(
        server_file=server_dir / "server.py",
        cwd=repo_root,
    )

    assert loaded == [server_env.resolve()]
    assert os.getenv("OPEN_ROUTER_KEY") == "server-key"
