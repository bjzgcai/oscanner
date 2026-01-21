"""
Plugin discovery + loading for oscanner scan/evaluation strategies.

Design goals:
- No optional imports / no TYPE_CHECKING.
- No external dependencies (simple YAML parsing for our constrained index.yaml schema).
- Runtime discovery from the repo checkout's `plugins/` directory (or OSCANNER_PLUGINS_DIR override).
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class PluginMeta:
    """
    Metadata loaded from plugins/<id>/index.yaml.

    We intentionally keep the YAML schema minimal (flat key-value pairs) to avoid depending on PyYAML.
    """

    plugin_id: str
    name: str
    version: str
    description: str
    default: bool
    scan_entry: str  # relative path to a python file, e.g. "scan/__init__.py"
    # Frontend view entrypoints (optional). Kept flat for our simple YAML parser.
    # - view_single_entry: single repo analysis view
    # - view_compare_entry: multi repo compare view
    # - view_entry: legacy single-view entry (compat)
    view_single_entry: str
    view_compare_entry: str
    view_entry: str

    @classmethod
    def from_dict(cls, d: Dict[str, str], plugin_dir: Path) -> "PluginMeta":
        plugin_id = (d.get("id") or d.get("plugin_id") or plugin_dir.name).strip()
        name = (d.get("name") or plugin_id).strip()
        version = (d.get("version") or "0.0.0").strip()
        description = (d.get("description") or "").strip()
        default_raw = (d.get("default") or "").strip().lower()
        default = default_raw in ("1", "true", "yes", "y", "on")
        scan_entry = (d.get("scan_entry") or "scan/__init__.py").strip()
        view_single_entry = (d.get("view_single_entry") or "view/single_repo.tsx").strip()
        view_compare_entry = (d.get("view_compare_entry") or "view/multi_repo_compare.tsx").strip()
        view_entry = (d.get("view_entry") or "view/index.tsx").strip()
        return cls(
            plugin_id=plugin_id,
            name=name,
            version=version,
            description=description,
            default=default,
            scan_entry=scan_entry,
            view_single_entry=view_single_entry,
            view_compare_entry=view_compare_entry,
            view_entry=view_entry,
        )


class PluginLoadError(RuntimeError):
    pass


def _find_repo_root() -> Path:
    """
    Best-effort locate repository root (directory containing pyproject.toml).
    """
    try:
        here = Path(__file__).resolve()
        for p in [here.parent, *here.parents]:
            if (p / "pyproject.toml").exists():
                return p
    except Exception:
        pass
    return Path.cwd()


def get_plugins_dir() -> Optional[Path]:
    """
    Resolve plugins directory.

    Order:
    - OSCANNER_PLUGINS_DIR env var (absolute or relative to CWD)
    - <repo_root>/plugins
    - <cwd>/plugins
    """
    env = (os.getenv("OSCANNER_PLUGINS_DIR") or "").strip()
    if env:
        p = Path(env).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if p.is_dir():
            return p

    repo_root = _find_repo_root()
    candidate = repo_root / "plugins"
    if candidate.is_dir():
        return candidate

    candidate = Path.cwd() / "plugins"
    if candidate.is_dir():
        return candidate

    return None


def _parse_simple_yaml(path: Path) -> Dict[str, str]:
    """
    Parse a very small subset of YAML:
    - Flat key: value pairs
    - Ignores blank lines and comments (# ...)
    - Values may be quoted or unquoted
    """
    data: Dict[str, str] = {}
    raw = path.read_text(encoding="utf-8")
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            continue
        k, v = s.split(":", 1)
        key = k.strip()
        val = v.strip()
        if not key:
            continue
        # Strip simple quotes
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        data[key] = val
    return data


def discover_plugins() -> List[Tuple[PluginMeta, Path]]:
    """
    Discover plugins under plugins_dir.
    Returns: list of (meta, plugin_dir)
    """
    plugins_dir = get_plugins_dir()
    if not plugins_dir:
        return []

    found: List[Tuple[PluginMeta, Path]] = []
    for plugin_dir in sorted([p for p in plugins_dir.iterdir() if p.is_dir()]):
        idx = plugin_dir / "index.yaml"
        if not idx.exists():
            continue
        try:
            d = _parse_simple_yaml(idx)
            meta = PluginMeta.from_dict(d, plugin_dir)
            found.append((meta, plugin_dir))
        except Exception as e:
            # Skip broken plugins rather than failing the whole service.
            # The API layer can optionally surface warnings.
            _ = e
            continue
    return found


def get_default_plugin_id(plugins: List[Tuple[PluginMeta, Path]]) -> Optional[str]:
    if not plugins:
        return None
    for meta, _ in plugins:
        if meta.default:
            return meta.plugin_id
    # Prefer zgc_simple if present.
    for meta, _ in plugins:
        if meta.plugin_id == "zgc_simple":
            return meta.plugin_id
    return plugins[0][0].plugin_id


def load_scan_module(plugin_id: str) -> Tuple[PluginMeta, ModuleType, Path]:
    """
    Load a plugin's scan module from file path.

    Contract:
    - scan_entry points to a python file relative to the plugin dir (default: scan/__init__.py)
    - the module must export `create_commit_evaluator(...)` callable
    """
    plugins = discover_plugins()
    for meta, plugin_dir in plugins:
        if meta.plugin_id != plugin_id:
            continue

        scan_path = (plugin_dir / meta.scan_entry).resolve()
        if not scan_path.exists():
            raise PluginLoadError(f"Plugin '{plugin_id}' scan_entry not found: {scan_path}")

        module_name = f"oscanner_plugin_{plugin_id}_scan"
        spec = importlib.util.spec_from_file_location(module_name, str(scan_path))
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"Failed to create import spec for plugin '{plugin_id}' at {scan_path}")

        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception as e:
            raise PluginLoadError(f"Failed to import plugin '{plugin_id}' scan module: {e}") from e

        if not hasattr(mod, "create_commit_evaluator"):
            raise PluginLoadError(
                f"Plugin '{plugin_id}' scan module must define create_commit_evaluator(...): {scan_path}"
            )

        return meta, mod, scan_path

    available = [m.plugin_id for m, _ in plugins]
    raise PluginLoadError(f"Unknown plugin '{plugin_id}'. Available: {available}")


