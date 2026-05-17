"""Plugin discovery and management service."""

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
