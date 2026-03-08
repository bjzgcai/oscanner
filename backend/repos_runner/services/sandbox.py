"""
Sandbox and resource-cap utilities for running untrusted test commands.

Design goals
------------
* **No network access** – tests must not exfiltrate data or download extra deps
  at test-time (deps should be installed during setup, before the cap is applied).
* **CPU time cap** – a runaway test suite cannot peg a core forever.
* **File-write containment** – writes are restricted to the repo directory and
  standard temp paths; system directories are read-only.
* **Process/thread count cap** – prevents fork-bombs or thread-exhaustion attacks.
* **File-size cap** – prevents filling the disk with gigantic output files.
* **Open-file-descriptor cap** – prevents fd exhaustion that would affect the
  parent FastAPI process.
* **Address-space cap** – coarse guard against memory bombs.

Platform notes
--------------
* macOS – uses ``sandbox-exec`` (Seatbelt) for the filesystem + network policy
  and Python ``resource`` module for rlimits.  ``sandbox-exec`` is available on
  every macOS version we target; it wraps the child process transparently.
* Linux – ``sandbox-exec`` is absent; we skip the Seatbelt layer and rely solely
  on rlimits (which are more complete on Linux than macOS anyway).
* Windows – rlimits are not supported; sandbox is a no-op except for timeouts.
"""

from __future__ import annotations

import os
import platform
import resource
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Resource limit defaults
# ---------------------------------------------------------------------------

# Sensible defaults that let normal test suites finish while capping abuse.
_DEFAULT_CPU_SECONDS   = 300   # matches default test_timeout
_DEFAULT_FSIZE_MB      = 512   # max file the child can create (bytes written)
_DEFAULT_AS_MB         = 2048  # virtual address space (2 GB)
_DEFAULT_NOFILE        = 256   # open file descriptors
_DEFAULT_NPROC         = 512   # processes + threads spawnable by this user


@dataclass
class ResourceLimits:
    """
    Tuneable resource caps applied to each sandboxed subprocess.

    All values use natural units (seconds, MB, count) so callers never
    have to think about bytes vs megabytes.
    """
    cpu_seconds: int   = _DEFAULT_CPU_SECONDS
    fsize_mb:    int   = _DEFAULT_FSIZE_MB
    as_mb:       int   = _DEFAULT_AS_MB
    max_files:   int   = _DEFAULT_NOFILE
    max_procs:   int   = _DEFAULT_NPROC

    @classmethod
    def from_timeout(cls, timeout_seconds: int) -> "ResourceLimits":
        """Convenience constructor that ties CPU cap to the wall-clock timeout."""
        return cls(cpu_seconds=timeout_seconds)


# ---------------------------------------------------------------------------
# macOS Seatbelt profile builder
# ---------------------------------------------------------------------------

_SEATBELT_TEMPLATE = textwrap.dedent("""\
    (version 1)

    ;; Default-deny posture
    (deny default)

    ;; Allow process execution of files already on disk
    (allow process-exec)
    (allow process-fork)

    ;; Allow signal delivery within the process group
    (allow signal (target same-sandbox))

    ;; Read access: everything except a few sensitive spots
    (allow file-read*)
    (deny  file-read* (subpath "/private/etc/master.passwd"))
    (deny  file-read* (subpath "/private/etc/sudo_lecture"))

    ;; Write access: only the repo dir and system temp locations
    (allow file-write* (subpath "{repo_dir}"))
    (allow file-write* (subpath "/tmp"))
    (allow file-write* (subpath "/private/tmp"))
    (allow file-write* (subpath "/var/folders"))

    ;; Sysctl reads needed by Python / runtime
    (allow sysctl-read)

    ;; POSIX IPC (shared memory, semaphores) – needed by pytest-xdist etc.
    (allow ipc-posix*)
    (allow ipc-sysv*)

    ;; Mach IPC needed by the macOS runtime
    (allow mach-lookup)
    (allow mach-priv-host-port)

    ;; System calls needed by the runtime
    (allow system-socket)
    (allow network-outbound (local))   ;; loopback only (no external network)
    (deny  network-outbound (remote))  ;; block all remote connections
    (deny  network-inbound)

    ;; Allow file-descriptor operations
    (allow file-ioctl)

    ;; Allow iokit device access (needed by Python on Apple Silicon)
    (allow iokit-open)
""")


def _build_seatbelt_profile(repo_dir: Path) -> str:
    """Return a Seatbelt policy string scoped to *repo_dir*."""
    return _SEATBELT_TEMPLATE.format(repo_dir=str(repo_dir).replace('"', '\\"'))


# ---------------------------------------------------------------------------
# rlimit preexec helper
# ---------------------------------------------------------------------------

def _make_rlimit_preexec(limits: ResourceLimits):
    """
    Return a callable suitable for ``subprocess.Popen(preexec_fn=...)``.

    The returned function runs *inside the child process* (after fork, before
    exec) and tightens resource limits.  It is defined as a closure so that
    ``limits`` is captured by value at construction time.
    """
    cpu    = limits.cpu_seconds
    fsize  = limits.fsize_mb   * 1024 * 1024
    as_    = limits.as_mb      * 1024 * 1024
    nofile = limits.max_files
    nproc  = limits.max_procs

    def _preexec():
        try:
            resource.setrlimit(resource.RLIMIT_CPU,    (cpu,    cpu))
        except (ValueError, resource.error):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE,  (fsize,  fsize))
        except (ValueError, resource.error):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_AS,     (as_,    as_))
        except (ValueError, resource.error):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (nofile, nofile))
        except (ValueError, resource.error):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_NPROC,  (nproc,  nproc))
        except (ValueError, resource.error):
            pass

    return _preexec


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_sandboxed(
    cmd: str,
    *,
    cwd: Path,
    timeout: int,
    limits: Optional[ResourceLimits] = None,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    """
    Run *cmd* (shell string) inside a sandbox with resource caps.

    Parameters
    ----------
    cmd:
        Shell command string, passed to ``/bin/sh -c``.
    cwd:
        Working directory — also used as the write-allowed root for the
        macOS Seatbelt profile.
    timeout:
        Wall-clock timeout in seconds (``subprocess.TimeoutExpired`` is
        raised on breach, same as bare ``subprocess.run``).
    limits:
        Resource caps to apply.  Defaults to ``ResourceLimits.from_timeout(timeout)``.
    env:
        Optional environment dict.  Defaults to the current process environment.

    Returns
    -------
    subprocess.CompletedProcess
        Same contract as ``subprocess.run(..., capture_output=True, text=True)``.

    Raises
    ------
    subprocess.TimeoutExpired
        When *timeout* is exceeded (caller is expected to handle this).
    """
    if limits is None:
        limits = ResourceLimits.from_timeout(timeout)

    _platform = platform.system()
    child_env = {**os.environ, **(env or {})}

    # Propagate PATH so test runners (pytest, go, cargo …) are found
    if "PATH" not in child_env:
        child_env["PATH"] = os.defpath

    # ------------------------------------------------------------------
    # macOS: wrap with sandbox-exec for filesystem + network policy
    # ------------------------------------------------------------------
    if _platform == "Darwin":
        profile = _build_seatbelt_profile(cwd)

        # Write the profile to a temp file; sandbox-exec reads it with -f
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sb", delete=False, prefix="oscanner_sb_"
        ) as fh:
            fh.write(profile)
            profile_path = fh.name

        try:
            wrapped_cmd = ["sandbox-exec", "-f", profile_path, "/bin/sh", "-c", cmd]
            return subprocess.run(
                wrapped_cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=child_env,
                preexec_fn=_make_rlimit_preexec(limits),
            )
        finally:
            try:
                os.unlink(profile_path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Linux: rlimits only (no sandbox-exec)
    # ------------------------------------------------------------------
    elif _platform == "Linux":
        return subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=child_env,
            preexec_fn=_make_rlimit_preexec(limits),
        )

    # ------------------------------------------------------------------
    # Other (Windows, etc.): best-effort, no sandboxing
    # ------------------------------------------------------------------
    else:
        return subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=child_env,
        )
