import os
import re
from pathlib import Path
from typing import Optional


def _xdg_dir(env_key: str, fallback: Path) -> Path:
    value = os.getenv(env_key)
    if value:
        return Path(value).expanduser()
    return fallback


def get_home_dir() -> Path:
    """
    Base dir for oscanner-related state.

    Priority:
    1) OSCANNER_HOME
    2) XDG_DATA_HOME/oscanner
    3) ~/.local/share/oscanner
    """
    if os.getenv("OSCANNER_HOME"):
        return Path(os.environ["OSCANNER_HOME"]).expanduser()
    data_home = _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")
    return data_home / "oscanner"


def get_data_dir() -> Path:
    """
    Get base data directory (without platform structure).
    For new code, use get_platform_data_dir() instead.
    """
    if os.getenv("OSCANNER_DATA_DIR"):
        return Path(os.environ["OSCANNER_DATA_DIR"]).expanduser()
    return get_home_dir() / "data"


def _safe_storage_segment(value: str, *, fallback: str = "default") -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return segment or fallback


def get_platform_data_dir(platform: str, owner: str, repo: str, ref: Optional[str] = None) -> Path:
    """
    Get platform-specific data directory for a repository.

    Args:
        platform: Platform name (github, gitee, gitlab)
        owner: Repository owner
        repo: Repository name
        ref: Optional branch/tag/SHA namespace for ref-specific data

    Returns:
        Path: data/{platform}/{owner}/{repo}
    """
    base_dir = get_data_dir()
    repo_dir = base_dir / platform / owner / repo
    if ref:
        return repo_dir / "refs" / _safe_storage_segment(ref)
    return repo_dir


def ensure_dirs() -> None:
    get_data_dir().mkdir(parents=True, exist_ok=True)


def ensure_platform_dirs(platform: str, owner: str, repo: str) -> None:
    """
    Ensure platform-specific directories exist.

    Args:
        platform: Platform name (github, gitee, gitlab)
        owner: Repository owner
        repo: Repository name
    """
    get_platform_data_dir(platform, owner, repo).mkdir(parents=True, exist_ok=True)
