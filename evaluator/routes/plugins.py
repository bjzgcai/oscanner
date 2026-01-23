"""Plugin management routes."""

from fastapi import APIRouter

from evaluator.services import get_plugins_snapshot

router = APIRouter()


@router.get("/api/plugins")
async def list_plugins():
    """
    List available scan plugins discovered from the local `plugins/` directory.
    """
    plugins, default_id = get_plugins_snapshot()
    print(f"[Info] Discovered {len(plugins)} plugins, default={default_id}")
    return {
        "success": True,
        "default": default_id,
        "plugins": [
            {
                "id": meta.plugin_id,
                "name": meta.name,
                "version": meta.version,
                "description": meta.description,
                "default": bool(meta.default),
                "scan_entry": meta.scan_entry,
                "view_single_entry": meta.view_single_entry,
                "has_view_single": bool((plugin_dir / meta.view_single_entry).exists()),
                "view_compare_entry": meta.view_compare_entry,
                "has_view_compare": bool((plugin_dir / meta.view_compare_entry).exists()),
                # Legacy (compat) single-view entry
                "view_entry": meta.view_entry,
                "has_view": bool((plugin_dir / meta.view_entry).exists()),
            }
            for meta, plugin_dir in plugins
        ],
    }


@router.get("/api/plugins/default")
async def get_default_plugin():
    """Get default plugin ID."""
    plugins, default_id = get_plugins_snapshot()
    _ = plugins

    return {"success": True, "default": default_id}
