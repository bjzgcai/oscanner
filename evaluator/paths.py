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
    if os.getenv("OSCANNER_DATA_DIR"):
        return Path(os.environ["OSCANNER_DATA_DIR"]).expanduser()
    return get_home_dir() / "data"


def get_cache_dir() -> Path:
    if os.getenv("OSCANNER_CACHE_DIR"):
        return Path(os.environ["OSCANNER_CACHE_DIR"]).expanduser()
    cache_home = _xdg_dir("XDG_CACHE_HOME", Path.home() / ".cache")
    return cache_home / "oscanner" / "cache"


def get_eval_cache_dir() -> Path:
    if os.getenv("OSCANNER_EVAL_CACHE_DIR"):
        return Path(os.environ["OSCANNER_EVAL_CACHE_DIR"]).expanduser()
    return get_home_dir() / "evaluations" / "cache"


def ensure_dirs() -> None:
    get_data_dir().mkdir(parents=True, exist_ok=True)
    get_cache_dir().mkdir(parents=True, exist_ok=True)
    get_eval_cache_dir().mkdir(parents=True, exist_ok=True)


