"""
Checker discovery + loading for oscanner code quality checkers.

Design goals:
- No optional imports / no TYPE_CHECKING.
- No external dependencies (simple YAML parsing for our constrained checker_list.yaml schema).
- Runtime discovery from the repo checkout's `checkers/` directory.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CheckerMeta:
    """
    Metadata loaded from checkers/checker_list.yaml.
    
    We intentionally keep the YAML schema minimal (flat key-value pairs) to avoid depending on PyYAML.
    """

    checker_id: str
    name: str
    keyword: str  # Keyword to match in commit message (e.g., "ccn" for /checker:ccn)
    description: str
    entry: str  # relative path to checker.py, e.g. "checker.py"
    version: str
    enabled: bool

    @classmethod
    def from_dict(cls, d: Dict[str, Any], checker_dir: Path) -> "CheckerMeta":
        checker_id = (d.get("id") or checker_dir.name).strip() if isinstance(d.get("id"), str) else checker_dir.name
        name = (d.get("name") or checker_id).strip() if isinstance(d.get("name"), str) else checker_id
        keyword = (d.get("keyword") or checker_id).strip() if isinstance(d.get("keyword"), str) else checker_id
        description = (d.get("description") or "").strip() if isinstance(d.get("description"), str) else ""
        entry = (d.get("entry") or "checker.py").strip() if isinstance(d.get("entry"), str) else "checker.py"
        version = (d.get("version") or "0.0.0").strip() if isinstance(d.get("version"), str) else "0.0.0"
        
        # Handle enabled field (can be bool or string)
        enabled_raw = d.get("enabled")
        if isinstance(enabled_raw, bool):
            enabled = enabled_raw
        elif isinstance(enabled_raw, str):
            enabled = enabled_raw.strip().lower() in ("1", "true", "yes", "y", "on")
        else:
            enabled = True  # Default to enabled if not specified

        return cls(
            checker_id=checker_id,
            name=name,
            keyword=keyword,
            description=description,
            entry=entry,
            version=version,
            enabled=enabled,
        )


class CheckerLoadError(Exception):
    """Raised when a checker cannot be loaded."""

    pass


def get_checkers_dir() -> Path:
    """
    Get the checkers directory path.
    
    Checks OSCANNER_CHECKERS_DIR env var first, then defaults to repo root / checkers.
    """
    import time
    start_time = time.time()
    
    env_dir = os.getenv("OSCANNER_CHECKERS_DIR")
    if env_dir:
        print(f"[Checker] [Registry] Using OSCANNER_CHECKERS_DIR env var: {env_dir}")
        resolved = Path(env_dir).resolve()
        elapsed = time.time() - start_time
        if elapsed > 0.01:
            print(f"[Checker] [Registry] Path.resolve() took {elapsed:.3f}s for {env_dir}")
        print(f"[Checker] [Registry] Resolved checkers dir: {resolved}")
        return resolved

    # Default: assume we're in backend/evaluator/, go up to repo root, then checkers/
    resolve_start = time.time()
    current_file = Path(__file__).resolve()
    resolve_elapsed = time.time() - resolve_start
    if resolve_elapsed > 0.01:
        print(f"[Checker] [Registry] Path(__file__).resolve() took {resolve_elapsed:.3f}s")
    
    print(f"[Checker] [Registry] Current file: {current_file}")
    # backend/evaluator/checker_registry.py -> backend/evaluator -> backend -> repo root
    repo_root = current_file.parent.parent.parent
    checkers_dir = repo_root / "checkers"
    
    total_elapsed = time.time() - start_time
    print(f"[Checker] [Registry] get_checkers_dir() completed in {total_elapsed:.3f}s, returning: {checkers_dir}")
    return checkers_dir


def parse_checker_list_yaml(checkers_dir: Path) -> List[Dict[str, Any]]:
    """
    Parse checker_list.yaml using simple line-by-line parsing (no PyYAML dependency).
    
    Expected format:
    checkers:
      - id: ccn
        name: Cyclomatic Complexity Checker
        keyword: ccn
        ...
    """
    import time
    start_time = time.time()
    
    checker_list_path = checkers_dir / "checker_list.yaml"
    print(f"[Checker] [Registry] parse_checker_list_yaml() - Checking file: {checker_list_path}")
    
    exists_start = time.time()
    if not checker_list_path.exists():
        exists_elapsed = time.time() - exists_start
        print(f"[Checker] [Registry] Warning: checker_list.yaml not found at {checker_list_path} (exists check took {exists_elapsed:.3f}s)")
        return []
    exists_elapsed = time.time() - exists_start
    if exists_elapsed > 0.01:
        print(f"[Checker] [Registry] File exists check took {exists_elapsed:.3f}s")

    checkers = []
    current_checker: Optional[Dict[str, Any]] = None
    indent_level = 0

    open_start = time.time()
    print(f"[Checker] [Registry] Opening file: {checker_list_path}")
    with open(checker_list_path, "r", encoding="utf-8") as f:
        open_elapsed = time.time() - open_start
        if open_elapsed > 0.01:
            print(f"[Checker] [Registry] File open took {open_elapsed:.3f}s")
        
        line_count = 0
        parse_start = time.time()
        for line in f:
            line_count += 1
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Detect list item start
            if stripped.startswith("- "):
                if current_checker:
                    checkers.append(current_checker)
                current_checker = {}
                content = stripped[2:].strip()
            else:
                content = stripped

            # Parse key: value
            if ":" in content:
                key, value = content.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if current_checker is None:
                    # Top-level key (like "checkers:")
                    continue

                # Convert string booleans/numbers
                if value.lower() in ("true", "yes", "y", "on", "1"):
                    value = True
                elif value.lower() in ("false", "no", "n", "off", "0"):
                    value = False
                elif value.isdigit():
                    value = int(value)
                elif "." in value and value.replace(".", "").isdigit():
                    try:
                        value = float(value)
                    except ValueError:
                        pass

                current_checker[key] = value
        
        parse_elapsed = time.time() - parse_start
        print(f"[Checker] [Registry] Parsed {line_count} lines in {parse_elapsed:.3f}s")

    if current_checker:
        checkers.append(current_checker)

    total_elapsed = time.time() - start_time
    print(f"[Checker] [Registry] parse_checker_list_yaml() completed in {total_elapsed:.3f}s, found {len(checkers)} checker configs")
    return checkers


def discover_checkers() -> List[Tuple[CheckerMeta, Path]]:
    """
    Discover all checkers from checkers/checker_list.yaml.
    
    Returns:
        List of (CheckerMeta, checker_dir) tuples.
    """
    import time
    start_time = time.time()
    print(f"[Checker] [Registry] discover_checkers() started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
    
    try:
        # Step 1: Get checkers directory
        step_start = time.time()
        checkers_dir = get_checkers_dir()
        step_elapsed = time.time() - step_start
        print(f"[Checker] [Registry] Step 1 (get_checkers_dir) took {step_elapsed:.3f}s")
        
        exists_start = time.time()
        if not checkers_dir.exists():
            exists_elapsed = time.time() - exists_start
            print(f"[Checker] [Registry] Warning: checkers directory not found at {checkers_dir} (exists check took {exists_elapsed:.3f}s)")
            return []
        exists_elapsed = time.time() - exists_start
        if exists_elapsed > 0.01:
            print(f"[Checker] [Registry] Directory exists check took {exists_elapsed:.3f}s")

        # Step 2: Parse YAML
        step_start = time.time()
        checker_configs = parse_checker_list_yaml(checkers_dir)
        step_elapsed = time.time() - step_start
        print(f"[Checker] [Registry] Step 2 (parse_checker_list_yaml) took {step_elapsed:.3f}s, found {len(checker_configs)} configs")
        
        # Step 3: Process each checker config
        step_start = time.time()
        result = []
        for idx, config in enumerate(checker_configs):
            config_start = time.time()
            checker_id = config.get("id", "").strip()
            if not checker_id:
                print(f"[Checker] [Registry] Config {idx+1}: Skipping (no id)")
                continue

            checker_dir = checkers_dir / checker_id
            dir_exists_start = time.time()
            if not checker_dir.exists():
                dir_exists_elapsed = time.time() - dir_exists_start
                print(f"[Checker] [Registry] Config {idx+1} ({checker_id}): Warning - checker directory not found: {checker_dir} (exists check took {dir_exists_elapsed:.3f}s)")
                continue
            dir_exists_elapsed = time.time() - dir_exists_start
            if dir_exists_elapsed > 0.01:
                print(f"[Checker] [Registry] Config {idx+1} ({checker_id}): Directory exists check took {dir_exists_elapsed:.3f}s")

            try:
                meta_start = time.time()
                meta = CheckerMeta.from_dict(config, checker_dir)
                meta_elapsed = time.time() - meta_start
                if meta_elapsed > 0.01:
                    print(f"[Checker] [Registry] Config {idx+1} ({checker_id}): CheckerMeta.from_dict() took {meta_elapsed:.3f}s")
                
                if meta.enabled:
                    result.append((meta, checker_dir))
                    print(f"[Checker] [Registry] Config {idx+1} ({checker_id}): Added to result (enabled=True)")
                else:
                    print(f"[Checker] [Registry] Config {idx+1} ({checker_id}): Skipped (enabled=False)")
            except Exception as e:
                config_elapsed = time.time() - config_start
                print(f"[Checker] [Registry] Config {idx+1} ({checker_id}): Warning - Failed to parse checker config after {config_elapsed:.3f}s: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            config_elapsed = time.time() - config_start
            if config_elapsed > 0.05:
                print(f"[Checker] [Registry] Config {idx+1} ({checker_id}): Total processing took {config_elapsed:.3f}s")
        
        step_elapsed = time.time() - step_start
        print(f"[Checker] [Registry] Step 3 (process configs) took {step_elapsed:.3f}s, processed {len(checker_configs)} configs, {len(result)} enabled")

        total_elapsed = time.time() - start_time
        print(f"[Checker] [Registry] discover_checkers() completed in {total_elapsed:.3f}s, returning {len(result)} enabled checkers")
        return result
        
    except Exception as e:
        total_elapsed = time.time() - start_time
        print(f"[Checker] [Registry] ERROR in discover_checkers() after {total_elapsed:.3f}s: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise


def install_checker_requirements(checker_dir: Path) -> bool:
    """
    Install checker requirements from requirements.txt if it exists.
    
    Args:
        checker_dir: Path to checker directory
        
    Returns:
        True if installation succeeded or no requirements.txt found, False on failure
    """
    requirements_file = checker_dir / "requirements.txt"
    if not requirements_file.exists():
        return True  # No requirements file, nothing to install
    
    try:
        import subprocess
        import sys
        
        print(f"[Checker] Installing requirements from {requirements_file}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if result.returncode == 0:
            print(f"[Checker] Successfully installed requirements from {requirements_file}")
            return True
        else:
            print(f"[Checker] Warning: Failed to install requirements: {result.stderr}")
            return False
    except Exception as e:
        print(f"[Checker] Warning: Error installing checker requirements: {e}")
        return False


def load_checker_module(checker_id: str) -> Tuple[CheckerMeta, ModuleType, Path]:
    """
    Load a checker's Python module from file path.
    
    Contract:
    - entry points to a python file relative to the checker dir (default: checker.py)
    - the module must export `run_checker(commit_sha, files, data_dir, **kwargs) -> dict`
    
    Args:
        checker_id: Checker ID to load
        
    Returns:
        Tuple of (CheckerMeta, module, checker_path)
        
    Raises:
        CheckerLoadError: If checker cannot be loaded
    """
    checkers = discover_checkers()
    for meta, checker_dir in checkers:
        if meta.checker_id != checker_id:
            continue

        checker_path = (checker_dir / meta.entry).resolve()
        if not checker_path.exists():
            raise CheckerLoadError(f"Checker '{checker_id}' entry not found: {checker_path}")

        # Install checker requirements if they exist
        install_checker_requirements(checker_dir)

        module_name = f"oscanner_checker_{checker_id}"
        spec = importlib.util.spec_from_file_location(module_name, str(checker_path))
        if spec is None or spec.loader is None:
            raise CheckerLoadError(f"Failed to create import spec for checker '{checker_id}' at {checker_path}")

        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception as e:
            raise CheckerLoadError(f"Failed to import checker '{checker_id}' module: {e}") from e

        if not hasattr(mod, "run_checker"):
            raise CheckerLoadError(
                f"Checker '{checker_id}' module must define run_checker(commit_sha, files, data_dir, **kwargs): {checker_path}"
            )

        return meta, mod, checker_path

    available = [m.checker_id for m, _ in checkers]
    raise CheckerLoadError(f"Unknown checker '{checker_id}'. Available: {available}")


def find_checker_by_keyword(keyword: str) -> Optional[CheckerMeta]:
    """
    Find a checker by its keyword (used in commit messages like /checker:xxx).
    
    Args:
        keyword: Keyword to search for
        
    Returns:
        CheckerMeta if found, None otherwise
    """
    checkers = discover_checkers()
    for meta, _ in checkers:
        if meta.keyword == keyword:
            return meta
    return None
