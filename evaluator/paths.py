import os
from pathlib import Path


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


def get_platform_data_dir(platform: str, owner: str, repo: str) -> Path:
    """
    Get platform-specific data directory for a repository.

    Args:
        platform: Platform name (github, gitee, gitlab)
        owner: Repository owner
        repo: Repository name

    Returns:
        Path: data/{platform}/{owner}/{repo}
    """
    base_dir = get_data_dir()
    return base_dir / platform / owner / repo


def get_platform_eval_dir(platform: str, owner: str, repo: str) -> Path:
    """
    Get platform-specific evaluation directory for a repository.

    Args:
        platform: Platform name (github, gitee, gitlab)
        owner: Repository owner
        repo: Repository name

    Returns:
        Path: home/evaluations/{platform}/{owner}/{repo}
    """
    home_dir = get_home_dir()
    return home_dir / "evaluations" / platform / owner / repo


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
    get_platform_eval_dir(platform, owner, repo).mkdir(parents=True, exist_ok=True)


def get_trajectory_cache_dir() -> Path:
    """
    Get trajectory cache directory for growth tracking.

    Returns:
        Path: home/track
    """
    home_dir = get_home_dir()
    return home_dir / "track"


def get_trajectory_cache_path(username: str) -> Path:
    """
    Get trajectory cache file path for a specific user or group of users.

    Args:
        username: Username or comma-separated list of usernames (e.g., "author1,author2")
                 Authors will be sorted alphabetically for consistent cache keys.

    Returns:
        Path: home/track/{author1,author2,...}.json (sorted alphabetically)

    Examples:
        "alice" -> home/track/alice.json
        "bob,alice" -> home/track/alice,bob.json (sorted)
        "alice,bob" -> home/track/alice,bob.json (sorted)
    """
    cache_dir = get_trajectory_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    # If username contains commas, split and sort authors for consistent cache key
    if ',' in username:
        authors = [a.strip() for a in username.split(',')]
        # Sort authors alphabetically for order-insensitive caching
        sorted_authors = sorted(authors)
        normalized_username = ','.join(sorted_authors)
    else:
        normalized_username = username.strip()

    return cache_dir / f"{normalized_username}.json"


