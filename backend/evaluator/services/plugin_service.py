"""Plugin discovery and management service."""

from pathlib import Path
from typing import Optional
from fastapi import HTTPException

from evaluator.plugin_registry import discover_plugins, get_default_plugin_id


def get_plugins_snapshot():
    """Get current snapshot of available plugins and default plugin ID."""
    plugins = discover_plugins()
    default_id = get_default_plugin_id(plugins)
    return plugins, default_id


def resolve_plugin_id(requested: Optional[str]) -> str:
    """
    Resolve and validate plugin ID.

    Args:
        requested: Requested plugin ID (or None for default)

    Returns:
        Validated plugin ID

    Raises:
        HTTPException: If plugin not found or no plugins available
    """
    plugins, default_id = get_plugins_snapshot()
    requested_id = (requested or "").strip()
    if requested_id:
        # Validate existence early for clearer errors.
        if requested_id in {m.plugin_id for m, _ in plugins}:
            return requested_id
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unknown plugin '{requested_id}'",
                "available": [m.plugin_id for m, _ in plugins],
                "default": default_id,
            },
        )
    if default_id:
        return default_id
    raise HTTPException(status_code=500, detail="No plugins discovered (plugins/ directory missing?)")


def get_evaluation_cache_path(eval_dir: Path, author: str, plugin_id: str, default_id: Optional[str]) -> Path:
    """
    Construct cache file path for evaluation results.

    Args:
        eval_dir: Evaluation directory
        author: Author name
        plugin_id: Plugin ID
        default_id: Default plugin ID (for legacy compatibility)

    Returns:
        Path to cache file
    """
    safe_author = (author or "").strip().lower()
    if not safe_author:
        safe_author = "unknown"
    # Keep legacy path for default plugin to preserve existing caches.
    if default_id and plugin_id == default_id:
        return eval_dir / f"{safe_author}.json"
    if plugin_id in ("", "builtin"):
        return eval_dir / f"{safe_author}.json"
    return eval_dir / f"{safe_author}__{plugin_id}.json"
