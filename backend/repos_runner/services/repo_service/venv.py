"""
Virtual-environment management with hash-based dependency caching.
"""

import os
import hashlib
import shutil
import venv as venv_mod
from pathlib import Path
from typing import List


def _dep_hash(clone_dir: Path) -> str:
    """
    Compute a hash over all known dependency manifests found in clone_dir.
    Changing any manifest invalidates the venv cache.
    """
    manifests = [
        "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
        "setup.py", "setup.cfg", "pyproject.toml",
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "Cargo.toml", "Cargo.lock",
        "go.mod", "go.sum",
        "Gemfile", "Gemfile.lock",
        "pom.xml", "build.gradle",
    ]
    h = hashlib.sha256()
    for name in manifests:
        p = clone_dir / name
        if p.exists():
            try:
                h.update(p.read_bytes())
            except Exception:
                pass
    return h.hexdigest()[:16]


def ensure_repo_venv(clone_path: str) -> Path:
    """
    Return path to the venv Python executable for this repo.

    Uses hash-based caching: the venv is named `.venv_{hash}` so it is
    reused if dependency manifests have not changed.  Stale venvs from
    previous hashes are removed automatically.
    """
    clone_dir = Path(clone_path)
    dep_hash = _dep_hash(clone_dir)
    venv_dir = clone_dir / f".venv_{dep_hash}"

    # Remove any stale venvs (different hash)
    for old_venv in clone_dir.glob(".venv_*"):
        if old_venv != venv_dir and old_venv.is_dir():
            shutil.rmtree(old_venv, ignore_errors=True)

    if not venv_dir.exists():
        venv_mod.create(venv_dir, with_pip=True)

    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def get_repo_venv_dir(clone_path: str) -> Path:
    """Return the venv directory path (for listing/cleanup purposes)."""
    clone_dir = Path(clone_path)
    dep_hash = _dep_hash(clone_dir)
    return clone_dir / f".venv_{dep_hash}"
