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
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Resource limit defaults
# ---------------------------------------------------------------------------

# Sensible defaults that let normal test suites finish while capping abuse.
_DEFAULT_CPU_SECONDS   = 600   # matches default test_timeout
_DEFAULT_FSIZE_MB      = 512   # max file the child can create (bytes written)
_DEFAULT_AS_MB         = 2048  # virtual address space (2 GB)
_DEFAULT_NOFILE        = 256   # open file descriptors
_DEFAULT_NPROC         = 4096  # processes + threads spawnable by this user
_DOCKER_WORKDIR       = "/workspace"
_DEFAULT_DOCKER_IMAGE = "python:3.12-bookworm"


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


def requested_executor() -> str:
    """Return requested repo execution backend: host, docker, or auto."""
    value = os.getenv("REPOS_RUNNER_EXECUTOR", "auto").strip().lower()
    return value if value in {"host", "docker", "auto"} else "auto"


def docker_available() -> bool:
    """Return True when the Docker CLI and daemon are usable."""
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
        )
        return result.returncode == 0
    except Exception:
        return False


def should_use_docker_executor() -> bool:
    """Decide whether repo commands should run in Docker."""
    executor = requested_executor()
    if executor == "host":
        return False
    if executor == "docker":
        if not shutil.which("docker"):
            raise RuntimeError("REPOS_RUNNER_EXECUTOR=docker but Docker CLI was not found")
        return True
    return docker_available()


class HostSandboxSession:
    """Execution session backed by the existing host sandbox."""

    is_docker = False

    def __init__(self, repo_dir: Path):
        self.repo_dir = Path(repo_dir)

    def __enter__(self) -> "HostSandboxSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def run(
        self,
        cmd: str,
        *,
        cwd: Path,
        timeout: int,
        env: Optional[dict] = None,
    ) -> subprocess.CompletedProcess:
        return run_sandboxed(cmd, cwd=Path(cwd), timeout=timeout, env=env)


class DockerSandboxSession:
    """Disposable Docker container used for one cloned repository run."""

    is_docker = True

    def __init__(self, repo_dir: Path):
        self.repo_dir = Path(repo_dir).resolve()
        self.image = os.getenv("REPOS_RUNNER_DOCKER_IMAGE", _DEFAULT_DOCKER_IMAGE)
        self.name = f"oscanner-runner-{uuid.uuid4().hex[:12]}"
        self.container_id = ""

    def __enter__(self) -> "DockerSandboxSession":
        mount = f"{self.repo_dir}:{_DOCKER_WORKDIR}"
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                self.name,
                "--network",
                os.getenv("REPOS_RUNNER_DOCKER_NETWORK", "bridge"),
                "--memory",
                os.getenv("REPOS_RUNNER_DOCKER_MEMORY", "2g"),
                "--cpus",
                os.getenv("REPOS_RUNNER_DOCKER_CPUS", "2"),
                "--pids-limit",
                os.getenv("REPOS_RUNNER_DOCKER_PIDS", "512"),
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "-v",
                mount,
                "-w",
                _DOCKER_WORKDIR,
                "-e",
                "CI=1",
                "-e",
                "PYTHONUNBUFFERED=1",
                self.image,
                "sleep",
                "86400",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        self.container_id = (result.stdout or "").strip()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            subprocess.run(
                ["docker", "rm", "-f", self.name],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )
        except subprocess.TimeoutExpired:
            pass
        return False

    def _container_cwd(self, cwd: Path) -> str:
        cwd = Path(cwd).resolve()
        try:
            rel = cwd.relative_to(self.repo_dir)
        except ValueError:
            return _DOCKER_WORKDIR
        if str(rel) == ".":
            return _DOCKER_WORKDIR
        return f"{_DOCKER_WORKDIR}/{rel.as_posix()}"

    def _container_path(self, path: Path) -> str:
        path = Path(path).resolve()
        rel = path.relative_to(self.repo_dir)
        return f"{_DOCKER_WORKDIR}/{rel.as_posix()}"

    def run(
        self,
        cmd: str,
        *,
        cwd: Path,
        timeout: int,
        env: Optional[dict] = None,
    ) -> subprocess.CompletedProcess:
        args = ["docker", "exec", "-i", "-w", self._container_cwd(Path(cwd))]
        for key, value in (env or {}).items():
            args.extend(["-e", f"{key}={value}"])
        args.extend([self.name, "/bin/sh", "-lc", cmd])
        return subprocess.run(
            args,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )

    def start_background(
        self,
        command: str,
        *,
        cwd: Path,
        log_path: Path,
        env: Optional[dict] = None,
    ) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        container_log = self._container_path(log_path)
        env_prefix = " ".join(
            f"{shlex.quote(str(key))}={shlex.quote(str(value))}"
            for key, value in (env or {}).items()
        )
        if env_prefix:
            env_prefix += " "
        shell_cmd = (
            f"mkdir -p {shlex.quote(str(Path(container_log).parent))} && "
            f"({env_prefix}{command}) >> {shlex.quote(container_log)} 2>&1 &"
        )
        subprocess.run(
            [
                "docker",
                "exec",
                "-d",
                "-w",
                self._container_cwd(Path(cwd)),
                self.name,
                "/bin/sh",
                "-lc",
                shell_cmd,
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )

    def http_get(self, url: str, *, expect_json: bool = False, timeout: int = 5) -> tuple[bool, str, str]:
        code = (
            "import json, sys, urllib.request\n"
            "url = sys.argv[1]\n"
            "expect_json = sys.argv[2] == '1'\n"
            "try:\n"
            "    with urllib.request.urlopen(url, timeout=3) as response:\n"
            "        body = response.read(1048576)\n"
            "        if response.status >= 400:\n"
            "            print(f'HTTP {response.status}')\n"
            "            sys.exit(1)\n"
            "        if expect_json:\n"
            "            json.loads(body.decode('utf-8', errors='ignore'))\n"
            "        print(f'HTTP {response.status}')\n"
            "except Exception as error:\n"
            "    print(str(error))\n"
            "    sys.exit(1)\n"
        )
        cmd = (
            "python -c "
            f"{shlex.quote(code)} {shlex.quote(url)} {'1' if expect_json else '0'} "
            "|| python3 -c "
            f"{shlex.quote(code)} {shlex.quote(url)} {'1' if expect_json else '0'}"
        )
        result = self.run(cmd, cwd=self.repo_dir, timeout=timeout)
        detail = (result.stdout or result.stderr or "").strip().splitlines()
        message = detail[-1] if detail else f"exit {result.returncode}"
        return result.returncode == 0, url if result.returncode == 0 else "", message

    def http_text(self, url: str, *, timeout: int = 5) -> str:
        code = (
            "import sys, urllib.request\n"
            "try:\n"
            "    with urllib.request.urlopen(sys.argv[1], timeout=3) as response:\n"
            "        print(response.read(1048576).decode('utf-8', errors='ignore'))\n"
            "except Exception:\n"
            "    sys.exit(1)\n"
        )
        result = self.run(
            "python -c "
            f"{shlex.quote(code)} {shlex.quote(url)} "
            "|| python3 -c "
            f"{shlex.quote(code)} {shlex.quote(url)}",
            cwd=self.repo_dir,
            timeout=timeout,
        )
        return result.stdout if result.returncode == 0 else ""


def create_execution_session(repo_dir: Path):
    """Create the configured execution session for a cloned repository."""
    if should_use_docker_executor():
        return DockerSandboxSession(Path(repo_dir))
    return HostSandboxSession(Path(repo_dir))


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
            # RLIMIT_NPROC is per-user on Linux — if the user already has
            # many processes running (e.g. WSL2), setting a hard cap of 512
            # can immediately prevent any further forks ("Cannot fork").
            # Only apply the cap if the current soft limit is higher, and
            # ensure we leave at least 64 slots above the current count.
            cur_soft, cur_hard = resource.getrlimit(resource.RLIMIT_NPROC)
            if cur_soft > nproc:
                resource.setrlimit(resource.RLIMIT_NPROC, (nproc, min(nproc, cur_hard)))
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
