import argparse
import os
import shutil
import shlex
import subprocess
import sys
import time
import getpass
import socket
import signal
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List

from importlib import metadata as importlib_metadata

from . import __version__ as _PACKAGE_FALLBACK_VERSION


class _HelpOnErrorParser(argparse.ArgumentParser):
    """
    An argparse parser that prints help text on any parsing error.
    """

    def error(self, message: str) -> None:
        sys.stderr.write(f"error: {message}\n\n")
        self.print_help(sys.stderr)
        self.exit(2)


def _upgrade_self() -> int:
    """
    Upgrade the installed `oscanner-skill-evaluator` package in the current Python environment.

    Uses `python -m pip` when available; falls back to `uv pip` if pip is missing.
    """
    pkg = "oscanner-skill-evaluator"

    # Prefer pip in the current interpreter.
    pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", pkg]
    try:
        sys.stdout.write(f"[upgrade] $ {shlex.join(pip_cmd)}\n")
        return int(subprocess.call(pip_cmd))
    except Exception:
        # If pip isn't installed for this interpreter, try uv pip.
        uv = _require_uv()
        if not uv:
            sys.stderr.write(
                "ERROR: pip is not available in this Python environment, and `uv` is not installed.\n"
                "Install pip (`python -m ensurepip --upgrade` where applicable) or install uv, then retry.\n"
            )
            return 1

        uv_cmd = [uv, "pip", "install", "--python", sys.executable, "--upgrade", "--no-cache-dir", pkg]
        sys.stdout.write(f"[upgrade] $ {shlex.join(uv_cmd)}\n")
        return int(subprocess.call(uv_cmd))


def _is_repo_checkout() -> bool:
    """
    Best-effort detection of running from the repository checkout (dev/editable install).

    In a PyPI wheel install, the package lives under site-packages and won't have
    the repository root files like `pyproject.toml` or `webapp/`.
    """
    try:
        repo_root = Path(__file__).resolve().parents[1]
        return (repo_root / "pyproject.toml").exists() and (repo_root / "frontend" / "webapp").is_dir()
    except Exception:
        return False


def _add_common_env_help(parser: argparse.ArgumentParser) -> None:
    publish_env = ""
    if _is_repo_checkout():
        publish_env = "  UV_PUBLISH_TOKEN          PyPI token for `oscanner publish` (dev only)\n"

    parser.epilog = (
        "Environment variables:\n"
        "  OPEN_ROUTER_KEY           OpenRouter API key (required for LLM evaluation)\n"
        "  GITHUB_TOKEN              GitHub token (optional, higher rate limits)\n"
        f"{publish_env}"
        "  OSCANNER_HOME             Base directory for oscanner data/cache\n"
        "  OSCANNER_DATA_DIR         Override data directory\n"
        "  OSCANNER_CACHE_DIR        Override cache directory\n"
        "  OSCANNER_EVAL_CACHE_DIR   Override evaluation cache directory\n"
    )

def _print_dashboard_instructions() -> None:
    msg = (
        "Dashboard options:\n\n"
        "  A) Bundled dashboard (recommended for PyPI installs)\n"
        "     - Run backend:  oscanner serve\n"
        "     - Open:         http://localhost:8000/\n"
        "     - Runtime deps: NO npm required (static files served by backend)\n\n"
        "  B) Frontend dev server (repo only)\n"
        "     1) Start backend:\n"
        "        oscanner serve --reload\n"
        "     2) Start frontend (requires Node + npm):\n"
        "        oscanner dashboard --install\n"
        "     - Web:          http://localhost:3000\n"
    )
    sys.stdout.write(msg)


def _resolve_webapp_dir(webapp_dir_arg: Optional[str]) -> Optional[Path]:
    """
    Resolve the Next.js webapp directory.

    Order:
    - explicit --webapp-dir
    - ./webapp (current working directory)
    - <repo_root>/webapp (when running from the repo / editable install)
    """
    candidates: List[Path] = []
    if webapp_dir_arg:
        candidates.append(Path(webapp_dir_arg).expanduser())
    candidates.append(Path.cwd() / "webapp")
    candidates.append(Path.cwd() / "frontend" / "webapp")
    try:
        repo_root = Path(__file__).resolve().parents[1]
        candidates.append(repo_root / "webapp")
        candidates.append(repo_root / "frontend" / "webapp")
    except Exception:
        pass

    for p in candidates:
        if p.is_dir() and (p / "package.json").exists():
            return p.resolve()
    return None


def _require_npm() -> Optional[str]:
    return shutil.which("npm")


def _require_uv() -> Optional[str]:
    return shutil.which("uv")


def _open_url(url: str) -> None:
    """
    Best-effort open a URL in the default browser.
    Never raises; failures are logged as a short warning.
    """
    try:
        u = (url or "").strip()
        if not u:
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        if os.name == "nt":
            # `start` is a built-in of cmd.exe
            subprocess.Popen(["cmd", "/c", "start", "", u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        opener = shutil.which("xdg-open") or shutil.which("gio")
        if opener:
            if os.path.basename(opener) == "gio":
                subprocess.Popen([opener, "open", u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen([opener, u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        sys.stdout.write(f"[dev] Dashboard URL: {u}\n")
    except Exception:
        try:
            sys.stdout.write(f"[dev] Dashboard URL: {url}\n")
        except Exception:
            pass


def _parse_node_version(raw: str) -> Optional[tuple]:
    """
    Parse Node.js version strings like "v20.19.6" into a tuple (major, minor, patch).
    Returns None if parsing fails.
    """
    s = (raw or "").strip()
    if s.startswith("v"):
        s = s[1:]
    parts = s.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except Exception:
        return None


def _node_at_least(v: Optional[tuple], major: int, minor: int) -> bool:
    if not v:
        return False
    if v[0] != major:
        return v[0] > major
    return v[1] >= minor


def _resolve_project_dir(project_dir_arg: Optional[str]) -> Optional[Path]:
    """
    Resolve a directory that contains `pyproject.toml`.

    Order:
    - explicit --project-dir
    - current working directory
    - <repo_root> (when running from the repository / editable install)
    """
    candidates: List[Path] = []
    if project_dir_arg:
        candidates.append(Path(project_dir_arg).expanduser())
    candidates.append(Path.cwd())
    candidates.append(Path(__file__).resolve().parents[1])

    for p in candidates:
        try:
            if p.is_dir() and (p / "pyproject.toml").exists():
                return p.resolve()
        except Exception:
            continue
    return None


def _parse_env_file(path: Path) -> dict:
    """
    Parse a .env-like file into a dict.
    Keeps only simple KEY=VALUE pairs, ignores comments/blank lines.
    """
    env = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    except FileNotFoundError:
        return {}
    return env


def _write_env_file(path: Path, env: dict) -> None:
    """
    Write a .env.local file with a stable key order.
    """
    header = [
        "# Generated by `oscanner init`",
        "#",
        "# Notes:",
        "# - This file is loaded by the backend if present in the working directory.",
        "# - Do NOT commit real keys to git.",
        "",
    ]

    order = [
        # Provider selection
        "OSCANNER_LLM_BASE_URL",
        "OSCANNER_LLM_CHAT_COMPLETIONS_URL",
        "OSCANNER_LLM_API_KEY",
        "OSCANNER_LLM_MODEL",
        "OSCANNER_LLM_FALLBACK_MODELS",
        # Legacy / compatibility
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "OPEN_ROUTER_KEY",
        # Repo tokens
        "GITHUB_TOKEN",
        "GITEE_TOKEN",
    ]

    lines = list(header)
    for k in order:
        if k in env and env[k] is not None and str(env[k]).strip() != "":
            lines.append(f"{k}={env[k]}")
    # Write remaining keys not in the predefined order (rare)
    for k in sorted(env.keys()):
        if k in order:
            continue
        v = env[k]
        if v is None or str(v).strip() == "":
            continue
        lines.append(f"{k}={v}")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _prompt(text: str, default: Optional[str] = None) -> str:
    hint = f" [{default}]" if default is not None and default != "" else ""
    while True:
        val = input(f"{text}{hint}: ").strip()
        if val:
            return val
        if default is not None:
            return default


def _prompt_secret(text: str, default: Optional[str] = None) -> str:
    hint = " [hidden]" if default else ""
    while True:
        val = getpass.getpass(f"{text}{hint}: ").strip()
        if val:
            return val
        if default is not None:
            return default


def _mask(value: str) -> str:
    v = value or ""
    if len(v) <= 6:
        return "***"
    return f"{v[:3]}***{v[-3:]}"


def _is_tcp_port_open(host: str, port: int, timeout_s: float = 0.25) -> bool:
    """
    Best-effort check whether something is already listening on host:port.
    """
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_s):
            return True
    except OSError:
        return False


def _is_http_healthy(url: str, timeout_s: float = 0.6) -> bool:
    """
    Best-effort check if an HTTP endpoint responds quickly (used to detect a hung backend).
    """
    try:
        req = urllib.request.Request(url, headers={"accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return 200 <= int(getattr(resp, "status", 0) or 0) < 300
    except Exception:
        return False


def _wait_http_ok(url: str, timeout_s: float = 12.0, poll_s: float = 0.2) -> bool:
    """
    Wait until an HTTP endpoint responds with a 2xx code, or until timeout.
    """
    deadline = time.time() + float(timeout_s)
    while time.time() < deadline:
        if _is_http_healthy(url, timeout_s=0.6):
            return True
        time.sleep(float(poll_s))
    return False


def _http_get_best_effort(url: str, timeout_s: float = 30.0) -> None:
    """
    Fire a GET request to warm up servers (e.g. trigger Next dev compilation).
    Never raises.
    """
    try:
        req = urllib.request.Request(url, headers={"accept": "text/html"})
        with urllib.request.urlopen(req, timeout=float(timeout_s)):
            return
    except Exception:
        return


def _run_uvicorn_statreload(app: str, host: str, port: int, reload_dirs: List[str]) -> int:
    """
    Run uvicorn using StatReload (mtime polling).

    Rationale: on macOS, uvicorn's watchfiles reloader (FSEvents) can hang and never bind the socket.
    StatReload is slower but extremely reliable for dev.
    """
    from uvicorn.config import Config
    from uvicorn.server import Server
    from uvicorn.supervisors.statreload import StatReload

    config = Config(
        app,
        host=host,
        port=int(port),
        reload=True,
        reload_dirs=reload_dirs or None,
    )
    server = Server(config=config)
    sock = config.bind_socket()
    StatReload(config, target=server.run, sockets=[sock]).run()
    return 0


def _pids_listening_on_tcp_port(port: int) -> List[int]:
    """
    Best-effort: return PIDs that are LISTENing on a local TCP port.
    Uses `lsof` when available. Returns [] if unavailable/unsupported.
    """
    port = int(port)
    lsof = shutil.which("lsof")
    if not lsof:
        return []
    try:
        out = subprocess.check_output(
            [lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not out:
            return []
        pids: List[int] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                pids.append(int(line))
            except Exception:
                continue
        # de-dup preserving order
        seen = set()
        uniq: List[int] = []
        for pid in pids:
            if pid not in seen:
                uniq.append(pid)
                seen.add(pid)
        return uniq
    except Exception:
        return []


def _pid_command(pid: int) -> str:
    try:
        return subprocess.check_output(["ps", "-o", "command=", "-p", str(int(pid))], text=True).strip()
    except Exception:
        return ""


def _try_terminate_pid(pid: int, graceful_sig: int = signal.SIGINT, grace_s: float = 1.5) -> bool:
    """
    Try to stop a PID gracefully then force-kill.
    Returns True if the PID is gone at the end.
    """
    pid = int(pid)
    try:
        os.kill(pid, graceful_sig)
    except Exception:
        pass
    # wait a bit
    end = time.time() + float(grace_s)
    while time.time() < end:
        try:
            os.kill(pid, 0)
            time.sleep(0.05)
        except Exception:
            return True
    # force kill
    try:
        os.kill(pid, signal.SIGKILL)
    except Exception:
        pass
    # final check
    try:
        os.kill(pid, 0)
        return False
    except Exception:
        return True


def _cleanup_dev_ports_if_safe(
    backend_port: int,
    frontend_port: int,
    *,
    allow_kill: bool,
    webapp_dir: Optional[Path],
) -> None:
    """
    Best-effort cleanup for dev convenience.

    Only kills processes we can confidently identify as:
    - uvicorn evaluator.server:app (backend)
    - next dev (frontend)
    """
    if not allow_kill:
        return

    # Backend: only kill if it looks like our evaluator server AND it's unhealthy.
    health_url = f"http://127.0.0.1:{int(backend_port)}/health"
    if _is_tcp_port_open("127.0.0.1", int(backend_port)) and not _is_http_healthy(health_url, timeout_s=0.6):
        for pid in _pids_listening_on_tcp_port(int(backend_port)):
            cmdline = _pid_command(pid)
            if "uvicorn" in cmdline and ("evaluator.server:app" in cmdline or "backend.evaluator.server:app" in cmdline):
                sys.stdout.write(f"[dev] Found hung backend on :{backend_port} (pid {pid}). Stopping it...\n")
                _try_terminate_pid(pid, graceful_sig=signal.SIGINT)

    # Frontend: kill only if it looks like Next dev. (No health endpoint.)
    if _is_tcp_port_open("127.0.0.1", int(frontend_port)):
        for pid in _pids_listening_on_tcp_port(int(frontend_port)):
            cmdline = _pid_command(pid)
            looks_like_next = ("next" in cmdline and "dev" in cmdline) or ("next-server" in cmdline)
            if not looks_like_next:
                continue
            # If we know the webapp dir, be stricter: only kill if command mentions it.
            if webapp_dir and str(webapp_dir) not in cmdline:
                # Still allow if it's clearly `next dev` and owned by current user; ps output doesn't include user here.
                pass
            sys.stdout.write(f"[dev] Found existing frontend on :{frontend_port} (pid {pid}). Stopping it...\n")
            _try_terminate_pid(pid, graceful_sig=signal.SIGINT)


def _prompt_reuse_or_overwrite(key: str, existing_value: str, is_secret: bool = False) -> str:
    """
    If key exists, ask whether to reuse it (default) or overwrite it.
    Returns:
      - "__REUSE__" to indicate reuse
      - "__CLEAR__" to indicate clear
      - otherwise returns the new value
    """
    preview = _mask(existing_value) if is_secret else existing_value
    sys.stdout.write(f"{key} already set: {preview}\n")
    ans = _prompt("Reuse existing value? (Y/n)", "Y").lower().strip()
    if ans in ("", "y", "yes"):
        return "__REUSE__"
    ans2 = _prompt("Overwrite or clear? (o/c)", "o").lower().strip()
    if ans2.startswith("c"):
        return "__CLEAR__"
    # overwrite
    if is_secret:
        return _prompt_secret(f"New value for {key}")
    return _prompt(f"New value for {key}")


def cmd_init(args: argparse.Namespace) -> int:
    """
    Interactive initializer that generates/updates `.env.local`.
    """
    target = Path(args.path).expanduser().resolve() if args.path else (Path.cwd() / ".env.local")
    exists = target.exists()
    existing = _parse_env_file(target) if exists else {}

    interactive = bool(sys.stdin.isatty()) and not args.non_interactive

    action = args.action or ("overwrite" if not exists else "merge")
    if interactive:
        # Make it per-key friendly by default; no global k/m/o/q menu.
        # If user explicitly asks for "keep", we respect it.
        if action == "keep" and exists:
            sys.stdout.write("Keeping existing config. No changes made.\n")
            return 0
    else:
        # Non-interactive needs explicit decision if file exists.
        if exists and not args.action:
            sys.stderr.write(
                f"ERROR: {target} already exists. Re-run with --action merge|overwrite|keep (or run without --non-interactive).\n"
            )
            return 2

    base_env = {} if action == "overwrite" else dict(existing)

    provider = args.provider
    if not provider:
        if any(k in base_env for k in ("OSCANNER_LLM_BASE_URL", "OSCANNER_LLM_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL")):
            provider = "openai"
        elif "OPEN_ROUTER_KEY" in base_env:
            provider = "openrouter"
        elif not interactive:
            provider = "openai"  # sensible default for non-interactive explicit flags
        else:
            sys.stdout.write("Select LLM provider:\n")
            sys.stdout.write("  [1] OpenRouter (uses OPEN_ROUTER_KEY)\n")
            sys.stdout.write("  [2] OpenAI-compatible Chat Completions (base_url + api_key + model)\n")
            p = _prompt("Provider", "2").strip()
            provider = "openrouter" if p == "1" else "openai"

    new_env = dict(base_env)

    # Optional repo tokens
    github_default = base_env.get("GITHUB_TOKEN") if base_env.get("GITHUB_TOKEN") else ""
    gitee_default = base_env.get("GITEE_TOKEN") if base_env.get("GITEE_TOKEN") else ""

    if provider == "openrouter":
        # OPEN_ROUTER_KEY
        if args.api_key is not None:
            new_env["OPEN_ROUTER_KEY"] = args.api_key
        elif interactive:
            if new_env.get("OPEN_ROUTER_KEY"):
                decision = _prompt_reuse_or_overwrite("OPEN_ROUTER_KEY", new_env["OPEN_ROUTER_KEY"], is_secret=True)
                if decision == "__CLEAR__":
                    new_env.pop("OPEN_ROUTER_KEY", None)
                elif decision != "__REUSE__":
                    new_env["OPEN_ROUTER_KEY"] = decision
            else:
                new_env["OPEN_ROUTER_KEY"] = _prompt_secret("OPEN_ROUTER_KEY (OpenRouter)")

        # Default model (optional)
        if args.model is not None:
            new_env["OSCANNER_LLM_MODEL"] = args.model
        elif interactive:
            if new_env.get("OSCANNER_LLM_MODEL"):
                decision = _prompt_reuse_or_overwrite("OSCANNER_LLM_MODEL", new_env["OSCANNER_LLM_MODEL"], is_secret=False)
                if decision == "__CLEAR__":
                    new_env.pop("OSCANNER_LLM_MODEL", None)
                elif decision != "__REUSE__":
                    new_env["OSCANNER_LLM_MODEL"] = decision
            else:
                set_model = _prompt("Set OSCANNER_LLM_MODEL? (y/N)", "N").lower().startswith("y")
                if set_model:
                    new_env["OSCANNER_LLM_MODEL"] = _prompt("OSCANNER_LLM_MODEL", "qwen/qwen3-coder-flash")

    else:
        # base url
        if args.base_url is not None:
            new_env["OSCANNER_LLM_BASE_URL"] = args.base_url
        elif interactive:
            if new_env.get("OSCANNER_LLM_BASE_URL"):
                decision = _prompt_reuse_or_overwrite("OSCANNER_LLM_BASE_URL", new_env["OSCANNER_LLM_BASE_URL"])
                if decision == "__CLEAR__":
                    new_env.pop("OSCANNER_LLM_BASE_URL", None)
                elif decision != "__REUSE__":
                    new_env["OSCANNER_LLM_BASE_URL"] = decision
            else:
                new_env["OSCANNER_LLM_BASE_URL"] = _prompt(
                    "OSCANNER_LLM_BASE_URL (e.g. https://api.siliconflow.cn/v1)",
                    "https://api.siliconflow.cn/v1",
                )

        # explicit chat completions url (optional)
        if args.chat_completions_url is not None:
            if args.chat_completions_url == "":
                new_env.pop("OSCANNER_LLM_CHAT_COMPLETIONS_URL", None)
            else:
                new_env["OSCANNER_LLM_CHAT_COMPLETIONS_URL"] = args.chat_completions_url
        elif interactive:
            if new_env.get("OSCANNER_LLM_CHAT_COMPLETIONS_URL"):
                decision = _prompt_reuse_or_overwrite(
                    "OSCANNER_LLM_CHAT_COMPLETIONS_URL",
                    new_env["OSCANNER_LLM_CHAT_COMPLETIONS_URL"],
                )
                if decision == "__CLEAR__":
                    new_env.pop("OSCANNER_LLM_CHAT_COMPLETIONS_URL", None)
                elif decision != "__REUSE__":
                    new_env["OSCANNER_LLM_CHAT_COMPLETIONS_URL"] = decision
            else:
                # usually not needed; keep it optional
                use_url = _prompt("Set OSCANNER_LLM_CHAT_COMPLETIONS_URL? (y/N)", "N").lower().startswith("y")
                if use_url:
                    new_env["OSCANNER_LLM_CHAT_COMPLETIONS_URL"] = _prompt(
                        "OSCANNER_LLM_CHAT_COMPLETIONS_URL",
                        "https://api.siliconflow.cn/v1/chat/completions",
                    )

        # api key
        if args.api_key is not None:
            new_env["OSCANNER_LLM_API_KEY"] = args.api_key
        elif interactive:
            if new_env.get("OSCANNER_LLM_API_KEY"):
                decision = _prompt_reuse_or_overwrite("OSCANNER_LLM_API_KEY", new_env["OSCANNER_LLM_API_KEY"], is_secret=True)
                if decision == "__CLEAR__":
                    new_env.pop("OSCANNER_LLM_API_KEY", None)
                elif decision != "__REUSE__":
                    new_env["OSCANNER_LLM_API_KEY"] = decision
            else:
                new_env["OSCANNER_LLM_API_KEY"] = _prompt_secret("OSCANNER_LLM_API_KEY (Bearer token)")

        # model
        if args.model is not None:
            new_env["OSCANNER_LLM_MODEL"] = args.model
        elif interactive:
            if new_env.get("OSCANNER_LLM_MODEL"):
                decision = _prompt_reuse_or_overwrite("OSCANNER_LLM_MODEL", new_env["OSCANNER_LLM_MODEL"])
                if decision == "__CLEAR__":
                    new_env.pop("OSCANNER_LLM_MODEL", None)
                elif decision != "__REUSE__":
                    new_env["OSCANNER_LLM_MODEL"] = decision
            else:
                new_env["OSCANNER_LLM_MODEL"] = _prompt("OSCANNER_LLM_MODEL", "qwen/qwen3-coder-flash")

        # fallbacks (optional)
        if args.fallback_models is not None:
            if args.fallback_models == "":
                new_env.pop("OSCANNER_LLM_FALLBACK_MODELS", None)
            else:
                new_env["OSCANNER_LLM_FALLBACK_MODELS"] = args.fallback_models
        elif interactive:
            if new_env.get("OSCANNER_LLM_FALLBACK_MODELS"):
                decision = _prompt_reuse_or_overwrite("OSCANNER_LLM_FALLBACK_MODELS", new_env["OSCANNER_LLM_FALLBACK_MODELS"])
                if decision == "__CLEAR__":
                    new_env.pop("OSCANNER_LLM_FALLBACK_MODELS", None)
                elif decision != "__REUSE__":
                    new_env["OSCANNER_LLM_FALLBACK_MODELS"] = decision
            else:
                set_fb = _prompt("Set OSCANNER_LLM_FALLBACK_MODELS? (y/N)", "N").lower().startswith("y")
                if set_fb:
                    new_env["OSCANNER_LLM_FALLBACK_MODELS"] = _prompt("OSCANNER_LLM_FALLBACK_MODELS (comma-separated)")

    # Tokens (optional)
    if args.github_token is not None:
        if args.github_token == "":
            new_env.pop("GITHUB_TOKEN", None)
        else:
            new_env["GITHUB_TOKEN"] = args.github_token
    elif interactive:
        if new_env.get("GITHUB_TOKEN"):
            decision = _prompt_reuse_or_overwrite("GITHUB_TOKEN", new_env["GITHUB_TOKEN"], is_secret=True)
            if decision == "__CLEAR__":
                new_env.pop("GITHUB_TOKEN", None)
            elif decision != "__REUSE__":
                new_env["GITHUB_TOKEN"] = decision
        else:
            set_gh = _prompt("Set GITHUB_TOKEN? (y/N)", "N").lower().startswith("y")
            if set_gh:
                new_env["GITHUB_TOKEN"] = _prompt_secret("GITHUB_TOKEN", github_default or None)

    if args.gitee_token is not None:
        if args.gitee_token == "":
            new_env.pop("GITEE_TOKEN", None)
        else:
            new_env["GITEE_TOKEN"] = args.gitee_token
    elif interactive:
        if new_env.get("GITEE_TOKEN"):
            decision = _prompt_reuse_or_overwrite("GITEE_TOKEN", new_env["GITEE_TOKEN"], is_secret=True)
            if decision == "__CLEAR__":
                new_env.pop("GITEE_TOKEN", None)
            elif decision != "__REUSE__":
                new_env["GITEE_TOKEN"] = decision
        else:
            set_gt = _prompt("Set GITEE_TOKEN? (y/N)", "N").lower().startswith("y")
            if set_gt:
                new_env["GITEE_TOKEN"] = _prompt_secret("GITEE_TOKEN", gitee_default or None)

    # If overwriting, optionally keep unknown keys from the existing file.
    if action == "overwrite" and exists and args.keep_unknown:
        for k, v in existing.items():
            if k not in new_env:
                new_env[k] = v

    _write_env_file(target, new_env)

    # Print short summary without leaking secrets
    sys.stdout.write(f"Wrote config: {target}\n")
    if "OPEN_ROUTER_KEY" in new_env:
        sys.stdout.write(f"  OPEN_ROUTER_KEY={_mask(new_env.get('OPEN_ROUTER_KEY',''))}\n")
    if "OSCANNER_LLM_API_KEY" in new_env:
        sys.stdout.write(f"  OSCANNER_LLM_API_KEY={_mask(new_env.get('OSCANNER_LLM_API_KEY',''))}\n")
    if "OSCANNER_LLM_BASE_URL" in new_env:
        sys.stdout.write(f"  OSCANNER_LLM_BASE_URL={new_env.get('OSCANNER_LLM_BASE_URL')}\n")
    if "OSCANNER_LLM_MODEL" in new_env:
        sys.stdout.write(f"  OSCANNER_LLM_MODEL={new_env.get('OSCANNER_LLM_MODEL')}\n")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    # Import lazily to keep `oscanner --help` fast and avoid import errors
    import uvicorn
    # If the port is already bound, decide whether to reuse, clean up, or fail.
    # This avoids the confusing "page keeps loading" symptom when a previous reload watcher hung.
    if _is_tcp_port_open("127.0.0.1", int(args.port)):
        health_url = f"http://127.0.0.1:{int(args.port)}/health"
        if _is_http_healthy(health_url, timeout_s=0.6):
            sys.stdout.write(f"[serve] Backend already running on http://localhost:{args.port}\n")
            return 0
        if bool(getattr(args, "kill_old", True)):
            for pid in _pids_listening_on_tcp_port(int(args.port)):
                cmdline = _pid_command(pid)
                if "uvicorn" in cmdline and ("evaluator.server:app" in cmdline or "backend.evaluator.server:app" in cmdline):
                    sys.stdout.write(f"[serve] Found hung backend on :{args.port} (pid {pid}). Stopping it...\n")
                    _try_terminate_pid(pid, graceful_sig=signal.SIGINT)
        # If it's still occupied after cleanup attempt, bail with a clear error.
        if _is_tcp_port_open("127.0.0.1", int(args.port)):
            sys.stderr.write(
                f"ERROR: Port {args.port} is in use, and backend did not respond to {health_url}\n"
                "Stop the process on that port, or re-run with `oscanner serve --port <free_port>`.\n"
            )
            return 1

    # `evaluator.server` loads dotenv; this keeps backward-compat with existing setup.
    # We call it via module path so it works both in repo and after installation.
    #
    # IMPORTANT: When running with --reload in this monorepo, watching the entire CWD can
    # include `webapp/node_modules` and other large trees, which can destabilize the reload
    # watcher on macOS. Restrict reload watching to Python source dirs.
    reload_kwargs = {}
    if args.reload:
        try:
            repo_root = Path(__file__).resolve().parents[1]
            reload_kwargs = {
                "reload_dirs": [str(repo_root / "backend" / "evaluator"), str(repo_root / "cli")],
            }
        except Exception:
            reload_kwargs = {}

    # On macOS, prefer StatReload to avoid watchfiles/FSEvents hangs.
    if bool(args.reload) and sys.platform == "darwin":
        reload_dirs = reload_kwargs.get("reload_dirs", []) if isinstance(reload_kwargs, dict) else []
        if not reload_dirs:
            reload_dirs = [str(Path.cwd())]
        return _run_uvicorn_statreload("backend.evaluator.server:app", args.host, int(args.port), list(reload_dirs))

    uvicorn.run(
        "backend.evaluator.server:app",
        host=args.host,
        port=int(args.port),
        reload=bool(args.reload),
        **reload_kwargs,
    )
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    # We run the extractor as a module so it works post-install and doesn't rely on CWD.
    cmd = [
        sys.executable,
        "-m",
        "backend.evaluator.tools.extract_repo_data_moderate",
        "--repo-url",
        args.repo_url,
        "--out",
        str(Path(args.out).expanduser().resolve()),
        "--max-commits",
        str(args.max_commits),
    ]
    if args.token:
        cmd.extend(["--token", args.token])
    return os.spawnv(os.P_WAIT, sys.executable, cmd)


def cmd_dashboard(args: argparse.Namespace) -> int:
    """
    Start the Next.js dashboard frontend.

    If the repository's webapp/ directory is not available (e.g., PyPI install),
    print instructions instead of failing with a confusing error.
    """
    if args.print_only:
        _print_dashboard_instructions()
        return 0

    webapp_dir = _resolve_webapp_dir(args.webapp_dir)
    if not webapp_dir:
        # In PyPI installs, prefer bundled dashboard served by backend.
        _print_dashboard_instructions()
        return 0

    npm = _require_npm()
    if not npm:
        sys.stderr.write("ERROR: npm is not installed. Please install Node.js + npm first.\n")
        return 1

    env = os.environ.copy()
    env["PORT"] = str(args.port)

    # If the dev port is already occupied (often a previous Next dev), try to stop it first.
    if bool(getattr(args, "kill_old", True)):
        _cleanup_dev_ports_if_safe(
            backend_port=int(os.getenv("PORT", "8000")),
            frontend_port=int(args.port),
            allow_kill=True,
            webapp_dir=webapp_dir,
        )

    node_modules = webapp_dir / "node_modules"
    if args.install or not node_modules.exists():
        sys.stdout.write(f"[dashboard] Installing dependencies in {webapp_dir} ...\n")
        rc = subprocess.call([npm, "install"], cwd=str(webapp_dir), env=env)
        if rc != 0:
            return int(rc)

    sys.stdout.write(f"[dashboard] Starting Next.js dev server on http://localhost:{args.port} ...\n")
    return int(subprocess.call([npm, "run", "dev"], cwd=str(webapp_dir), env=env))


def cmd_publish(args: argparse.Namespace) -> int:
    """
    Build distributions with `uv build` and upload them with `uv publish`.

    This command is intended to be run from the repository root (where `pyproject.toml` exists).
    """
    uv = _require_uv()
    if not uv:
        sys.stderr.write("ERROR: `uv` is not installed or not on PATH.\n")
        return 1

    project_dir = _resolve_project_dir(args.project_dir)
    if not project_dir:
        sys.stderr.write(
            "ERROR: Could not find `pyproject.toml`.\n"
            "Run this command from the repository root, or pass --project-dir /path/to/repo.\n"
        )
        return 2

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else (project_dir / "dist")
    out_dir = out_dir.resolve()

    env = os.environ.copy()

    # Optional: build and bundle dashboard static files into the Python package.
    # This is a build-time concern (requires Node/npm). Runtime does not require npm.
    if not getattr(args, "skip_dashboard", False):
        webapp_dir = project_dir / "webapp"
        if webapp_dir.is_dir() and (webapp_dir / "package.json").exists():
            npm = _require_npm()
            if not npm:
                sys.stderr.write(
                    "ERROR: npm is not installed; cannot build bundled dashboard.\n"
                    "Install Node.js + npm, or re-run with --skip-dashboard.\n"
                )
                return 5

            # Next.js 16 requires Node >= 20.9.0. We don't hard-fail on parsing, but do a best-effort check.
            try:
                node_ver_raw = subprocess.check_output(["node", "-v"], cwd=str(webapp_dir), env=env, text=True).strip()
                sys.stdout.write(f"[publish] Detected node: {node_ver_raw}\n")
                node_v = _parse_node_version(node_ver_raw)
                if node_v and not _node_at_least(node_v, 20, 9):
                    # Common on macOS: user has a newer Homebrew node, but current shell is pinned to an older nvm node.
                    hb_node = "/opt/homebrew/bin/node"
                    hb_npm = "/opt/homebrew/bin/npm"
                    if os.path.exists(hb_node) and os.path.exists(hb_npm):
                        hb_ver_raw = subprocess.check_output([hb_node, "-v"], cwd=str(webapp_dir), env=env, text=True).strip()
                        hb_v = _parse_node_version(hb_ver_raw)
                        if hb_v and _node_at_least(hb_v, 20, 9):
                            sys.stdout.write(f"[publish] Switching to Homebrew node: {hb_ver_raw}\n")
                            env["PATH"] = "/opt/homebrew/bin:" + env.get("PATH", "")
                            npm = hb_npm
            except Exception:
                sys.stdout.write("[publish] WARNING: could not detect Node version (node -v failed).\n")

            sys.stdout.write("[publish] Building dashboard (webapp/) for bundling...\n")
            # Use npm install to support both local and CI; package-lock.json exists in repo.
            rc = subprocess.call([npm, "install"], cwd=str(webapp_dir), env=env)
            if rc != 0:
                return int(rc)
            rc = subprocess.call([npm, "run", "build"], cwd=str(webapp_dir), env=env)
            if rc != 0:
                return int(rc)

            exported = webapp_dir / "out"
            if not exported.is_dir() or not (exported / "index.html").exists():
                sys.stderr.write(
                    "ERROR: webapp build did not produce static export at webapp/out.\n"
                    "Ensure Next is configured with output='export'.\n"
                )
                return 6

            dest = project_dir / "cli" / "dashboard_dist"
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copytree(exported, dest, dirs_exist_ok=True)
            sys.stdout.write(f"[publish] Bundled dashboard into {dest}\n")
        else:
            sys.stdout.write("[publish] Skipping dashboard bundling (no webapp/ directory).\n")

    # Build
    if not args.no_build:
        build_cmd: List[str] = [uv, "build", str(project_dir), "--out-dir", str(out_dir), "--clear"]
        if args.sdist:
            build_cmd.append("--sdist")
        if args.wheel:
            build_cmd.append("--wheel")
        if args.no_build_logs:
            build_cmd.append("--no-build-logs")

        sys.stdout.write(f"[publish] Building distributions into {out_dir} ...\n")
        sys.stdout.write(f"[publish] $ {shlex.join(build_cmd)}\n")
        rc = subprocess.call(build_cmd, cwd=str(project_dir), env=env)
        if rc != 0:
            return int(rc)

    # Publish
    if args.dry_run:
        sys.stdout.write("[publish] Dry-run mode: will not upload files.\n")

    # Token handling: prefer explicit --token, then env UV_PUBLISH_TOKEN, else prompt (TTY only).
    token = args.token or env.get("UV_PUBLISH_TOKEN", "")
    if not token and not args.dry_run:
        if sys.stdin.isatty() and not args.non_interactive:
            token = getpass.getpass("PyPI token (will be set as UV_PUBLISH_TOKEN for this run): ").strip()
        else:
            sys.stderr.write(
                "ERROR: No PyPI token provided.\n"
                "Set UV_PUBLISH_TOKEN or pass --token, or run interactively without --non-interactive.\n"
            )
            return 3
    if token:
        env["UV_PUBLISH_TOKEN"] = token

    # Confirmation guard (only for real uploads).
    if not args.dry_run and not args.yes:
        if not sys.stdin.isatty() or args.non_interactive:
            sys.stderr.write("ERROR: Refusing to publish without confirmation. Re-run with --yes.\n")
            return 4
        target = args.index or "pypi(default)"
        sys.stdout.write(
            f"About to upload distributions from {out_dir} to {target}.\n"
            "This will publish artifacts to an index and is hard to undo.\n"
        )
        ans = input("Continue? (y/N): ").strip().lower()
        if ans not in ("y", "yes"):
            sys.stdout.write("Cancelled.\n")
            return 0

    publish_cmd: List[str] = [uv, "publish"]
    if args.index:
        publish_cmd.extend(["--index", args.index])
    if args.publish_url:
        publish_cmd.extend(["--publish-url", args.publish_url])
    if args.check_url:
        publish_cmd.extend(["--check-url", args.check_url])
    if args.trusted_publishing:
        publish_cmd.extend(["--trusted-publishing", args.trusted_publishing])
    if args.no_attestations:
        publish_cmd.append("--no-attestations")
    if args.dry_run:
        publish_cmd.append("--dry-run")
    if args.files and len(args.files) > 0:
        publish_cmd.extend(list(args.files))

    sys.stdout.write("[publish] Uploading distributions...\n")
    sys.stdout.write(f"[publish] $ {shlex.join(publish_cmd)}\n")
    return int(subprocess.call(publish_cmd, cwd=str(project_dir), env=env))


def cmd_dev(args: argparse.Namespace) -> int:
    """
    One-command dev mode: start backend + frontend together.
    """
    # In PyPI installs, the `webapp/` source is not bundled. The dashboard can be bundled as
    # pre-built static files and served by the backend at /.
    webapp_dir = _resolve_webapp_dir(args.webapp_dir)
    if args.backend_only or not webapp_dir:
        if not webapp_dir and not args.backend_only:
            sys.stdout.write("[dev] Frontend source (webapp/) not found; starting backend only.\n")
            sys.stdout.write("[dev] If dashboard is bundled, open: http://localhost:8000/\n")
        if not args.no_open:
            _open_url(f"http://localhost:{int(args.backend_port)}/")
        serve_args = argparse.Namespace(host=args.host, port=int(args.backend_port), reload=bool(args.reload))
        return cmd_serve(serve_args)

    npm = _require_npm()
    if not npm:
        sys.stderr.write(
            "ERROR: npm is not installed. Please install Node.js + npm first.\n"
            "Tip: re-run with `oscanner dev --backend-only` to start backend only.\n"
        )
        return 1

    # Dev convenience: if old processes are occupying ports, try to clean them up safely.
    _cleanup_dev_ports_if_safe(
        int(args.backend_port),
        int(args.frontend_port),
        allow_kill=bool(getattr(args, "kill_old", True)),
        webapp_dir=webapp_dir,
    )

    # Backend process (uvicorn)
    backend_cmd: List[str] = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.evaluator.server:app",
        "--host",
        args.host,
        "--port",
        str(args.backend_port),
    ]
    if args.reload:
        # On macOS, avoid uvicorn watchfiles reloader; use StatReload via a small python runner.
        if sys.platform == "darwin":
            try:
                repo_root = Path(__file__).resolve().parents[1]
                reload_dirs = [str(repo_root / "backend" / "evaluator"), str(repo_root / "cli")]
            except Exception:
                reload_dirs = [str(Path.cwd())]
            backend_cmd = [
                sys.executable,
                "-c",
                (
                    "from cli.cli import _run_uvicorn_statreload; "
                    "_run_uvicorn_statreload('backend.evaluator.server:app', %r, %r, %r)"
                    % (args.host, int(args.backend_port), reload_dirs)
                ),
            ]
        else:
            backend_cmd.append("--reload")
            # Restrict reload watching in this monorepo (avoid webapp/node_modules causing watcher instability).
            try:
                repo_root = Path(__file__).resolve().parents[1]
                backend_cmd.extend(["--reload-dir", str(repo_root / "backend" / "evaluator")])
                backend_cmd.extend(["--reload-dir", str(repo_root / "cli")])
                backend_cmd.extend(["--reload-exclude", "**/webapp/**"])
                backend_cmd.extend(["--reload-exclude", "**/node_modules/**"])
                backend_cmd.extend(["--reload-exclude", "**/.next/**"])
                backend_cmd.extend(["--reload-exclude", "**/dist/**"])
            except Exception:
                pass

    env_backend = os.environ.copy()
    env_backend["PORT"] = str(args.backend_port)
    # Ensure backend directory is in PYTHONPATH for uvicorn subprocess
    try:
        repo_root = Path(__file__).resolve().parents[1]
        backend_dir = repo_root / "backend"
        pythonpath = str(backend_dir)
        if "PYTHONPATH" in env_backend:
            env_backend["PYTHONPATH"] = f"{pythonpath}:{env_backend['PYTHONPATH']}"
        else:
            env_backend["PYTHONPATH"] = pythonpath
    except Exception:
        pass
    if args.reload:
        # Same rationale as in cmd_serve(): avoid macOS FSEvents watcher hangs in watchfiles.
        if sys.platform == "darwin" and not env_backend.get("WATCHFILES_FORCE_POLLING"):
            env_backend["WATCHFILES_FORCE_POLLING"] = "1"

    backend: Optional[subprocess.Popen] = None
    backend_started = False
    frontend: Optional[subprocess.Popen] = None

    # If something is already listening on the port, assume backend is already running and reuse it,
    # but guard against a "hung" process that accepts TCP but doesn't respond to HTTP.
    health_url = f"http://127.0.0.1:{int(args.backend_port)}/health"
    if _is_tcp_port_open("127.0.0.1", int(args.backend_port)):
        if _is_http_healthy(health_url, timeout_s=0.6):
            sys.stdout.write(
                f"[dev] Backend already running on http://localhost:{args.backend_port} (port in use). Reusing it.\n"
            )
        else:
            # Offer an interactive cleanup path. This is particularly useful on macOS where the
            # backend may run under a `python -c ...` wrapper (StatReload), which our safe
            # heuristics might not recognize as `uvicorn evaluator.server:app`.
            allow_kill = bool(getattr(args, "kill_old", True))
            interactive = bool(sys.stdin.isatty())
            pids = _pids_listening_on_tcp_port(int(args.backend_port)) if (allow_kill and interactive) else []

            sys.stderr.write(
                f"ERROR: Port {args.backend_port} is in use, but backend health check did not respond: {health_url}\n"
                "This usually means a previous uvicorn process is hung (common when heavy sync work runs inside async handlers).\n"
            )

            if pids:
                sys.stderr.write("Detected processes listening on this port:\n")
                for pid in pids:
                    cmdline = _pid_command(pid)
                    sys.stderr.write(f"  - pid {pid}: {cmdline or '(unknown command)'}\n")
                ans = input(f"Kill these process(es) and continue? (y/N): ").strip().lower()
                if ans in ("y", "yes"):
                    for pid in pids:
                        sys.stdout.write(f"[dev] Stopping pid {pid}...\n")
                        _try_terminate_pid(pid, graceful_sig=signal.SIGINT)
                    # Re-check after termination attempt.
                    time.sleep(0.15)
                    if _is_tcp_port_open("127.0.0.1", int(args.backend_port)) and not _is_http_healthy(
                        health_url, timeout_s=0.6
                    ):
                        sys.stderr.write(
                            f"ERROR: Port {args.backend_port} is still in use and backend is not healthy: {health_url}\n"
                            "Please stop the process manually, or re-run with `--backend-port <free_port>`.\n"
                        )
                        return 1
                    # If port is now free, fall through to start backend below.
                else:
                    sys.stderr.write(
                        "Stop the process on that port, or re-run with `--backend-port <free_port>`.\n"
                    )
                    return 1
            else:
                sys.stderr.write(
                    "Stop the process on that port, or re-run with `--backend-port <free_port>`.\n"
                )
                return 1

    if not _is_tcp_port_open("127.0.0.1", int(args.backend_port)):
        sys.stdout.write(f"[dev] Starting backend on http://localhost:{args.backend_port} ...\n")
        backend = subprocess.Popen(backend_cmd, env=env_backend)
        backend_started = True

        # Fail-fast if the backend never binds (common symptom: reload process stuck).
        if not _wait_http_ok(health_url, timeout_s=3.0, poll_s=0.2):
            sys.stderr.write(f"ERROR: Backend did not become ready: {health_url}\n")
            try:
                backend.terminate()
            except Exception:
                pass
            return 1

    try:
        env_frontend = os.environ.copy()
        env_frontend["PORT"] = str(args.frontend_port)
        # When running the frontend dev server (port 3000), default API calls should go to the backend.
        # The webapp defaults to same-origin when NEXT_PUBLIC_API_SERVER_URL is unset, which would hit 3000 and 404.
        if not env_frontend.get("NEXT_PUBLIC_API_SERVER_URL"):
            env_frontend["NEXT_PUBLIC_API_SERVER_URL"] = f"http://localhost:{int(args.backend_port)}"

        node_modules = webapp_dir / "node_modules"
        if args.install or not node_modules.exists():
            sys.stdout.write(f"[dev] Installing frontend dependencies in {webapp_dir} ...\n")
            rc = subprocess.call([npm, "install"], cwd=str(webapp_dir), env=env_frontend)
            if rc != 0:
                backend.terminate()
                backend.wait(timeout=10)
                return int(rc)

        sys.stdout.write(f"[dev] Starting frontend on http://localhost:{args.frontend_port} ...\n")
        frontend = subprocess.Popen([npm, "run", "dev"], cwd=str(webapp_dir), env=env_frontend)
        if not args.no_open:
            # Next serves from root in this repo.
            # Next dev compiles lazily on first request; warm it up before opening the browser
            # so users don't just see a "spinning" page while compilation happens.
            dash_url = f"http://localhost:{int(args.frontend_port)}/"
            if _wait_http_ok(dash_url, timeout_s=12.0):
                _http_get_best_effort(dash_url, timeout_s=60.0)
            _open_url(dash_url)

        # Wait until one exits; Ctrl+C stops both.
        while True:
            b = backend.poll() if backend is not None else None
            f = frontend.poll()
            if b is not None:
                if backend_started:
                    sys.stderr.write("[dev] Backend exited; stopping frontend...\n")
                    frontend.terminate()
                    return int(b)
                backend = None
            if f is not None:
                sys.stderr.write("[dev] Frontend exited; stopping backend...\n")
                if backend_started and backend is not None:
                    backend.terminate()
                return int(f)
            time.sleep(0.5)
    except KeyboardInterrupt:
        sys.stdout.write("\n[dev] Shutting down...\n")
        return 0
    finally:
        # Best-effort cleanup
        if backend_started and backend is not None:
            try:
                # Prefer SIGINT for uvicorn to shutdown cleanly.
                backend.send_signal(signal.SIGINT)
                backend.wait(timeout=3)
            except Exception:
                try:
                    backend.terminate()
                except Exception:
                    pass
        try:
            if frontend is not None:
                frontend.terminate()
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = _HelpOnErrorParser(prog="oscanner", description="oscanner toolchain CLI")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_get_distribution_version()}")
    parser.add_argument(
        "-U",
        "--upgrade",
        dest="upgrade_self",
        action="store_true",
        help="Upgrade oscanner-skill-evaluator in the current Python environment and exit.",
    )
    sub = parser.add_subparsers(dest="command", parser_class=_HelpOnErrorParser)

    p_init = sub.add_parser("init", help="Interactive setup: generate/update .env.local")
    p_init.add_argument("--path", help="Target env file path (default: ./.env.local)")
    p_init.add_argument("--provider", choices=["openrouter", "openai"], help="LLM provider")
    p_init.add_argument("--base-url", help="OpenAI-compatible base URL (e.g. https://api.siliconflow.cn/v1)")
    p_init.add_argument("--chat-completions-url", help="Override full chat completions URL")
    p_init.add_argument("--api-key", help="LLM API key (will be stored in env file)")
    p_init.add_argument("--model", help="Default model id")
    p_init.add_argument("--fallback-models", help="Comma-separated fallback model ids")
    p_init.add_argument("--github-token", nargs="?", const="", help="Set GITHUB_TOKEN (optional). If flag present without value, clears it.")
    p_init.add_argument("--gitee-token", nargs="?", const="", help="Set GITEE_TOKEN (optional). If flag present without value, clears it.")
    p_init.add_argument("--action", choices=["merge", "overwrite", "keep"], help="How to handle existing env file")
    p_init.add_argument("--non-interactive", action="store_true", help="Do not prompt; require explicit flags")
    p_init.add_argument("--keep-unknown", action="store_true", help="When overwriting, keep existing unknown keys")
    p_init.set_defaults(func=cmd_init)

    p_serve = sub.add_parser("serve", help="Start the FastAPI backend service")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    p_serve.add_argument("--reload", action="store_true", help="Enable auto-reload (dev)")
    p_serve.add_argument(
        "--kill-old",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-stop a stale/hung previous oscanner uvicorn process occupying the port (safe heuristics).",
    )
    p_serve.set_defaults(func=cmd_serve)

    p_extract = sub.add_parser("extract", help="Extract repo data (moderate mode)")
    p_extract.add_argument("repo_url", help="GitHub repository URL, e.g. https://github.com/owner/repo")
    p_extract.add_argument("--out", required=True, help="Output directory for extracted data")
    p_extract.add_argument("--token", help="GitHub token (or set GITHUB_TOKEN env var)")
    p_extract.add_argument("--max-commits", type=int, default=500)
    p_extract.set_defaults(func=cmd_extract)

    p_dash = sub.add_parser("dashboard", help="Start the optional dashboard frontend (Next.js)")
    p_dash.add_argument("--port", type=int, default=int(os.getenv("WEBAPP_PORT", "3000")))
    p_dash.add_argument(
        "--kill-old",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-stop a stale Next dev process occupying the port (safe heuristics).",
    )
    p_dash.add_argument(
        "--webapp-dir",
        help="Path to the webapp/ directory (if not running from the repo root).",
    )
    p_dash.add_argument(
        "--install",
        action="store_true",
        help="Run `npm install` before starting (auto-runs if node_modules is missing).",
    )
    p_dash.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="Print dashboard instructions instead of starting it.",
    )
    p_dash.set_defaults(func=cmd_dashboard)

    p_dev = sub.add_parser("dev", help="Start backend + dashboard together (dev mode)")
    p_dev.add_argument("--host", default="0.0.0.0")
    p_dev.add_argument("--backend-port", type=int, default=int(os.getenv("PORT", "8000")))
    p_dev.add_argument("--frontend-port", type=int, default=int(os.getenv("WEBAPP_PORT", "3000")))
    p_dev.add_argument("--reload", action="store_true", help="Enable backend auto-reload (dev)")
    p_dev.add_argument(
        "--kill-old",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-stop stale dev processes occupying backend/frontend ports (safe heuristics).",
    )
    p_dev.add_argument(
        "--backend-only",
        action="store_true",
        help="Start backend only (useful for PyPI installs without the webapp/ source).",
    )
    p_dev.add_argument(
        "--no-open",
        action="store_true",
        help="Do not auto-open the dashboard URL in a browser.",
    )
    p_dev.add_argument(
        "--webapp-dir",
        help="Path to the webapp/ directory (if not running from the repo root).",
    )
    p_dev.add_argument(
        "--install",
        action="store_true",
        help="Run `npm install` before starting (auto-runs if node_modules is missing).",
    )
    p_dev.set_defaults(func=cmd_dev)

    # Dev-only command: publishing is an authoring workflow and should not be exposed to end users.
    if _is_repo_checkout():
        p_publish = sub.add_parser("publish", help="(dev) Build and publish distributions to PyPI via uv")
        p_publish.add_argument(
            "--project-dir",
            help="Path to the repo root (directory containing pyproject.toml). Defaults to CWD.",
        )
        p_publish.add_argument(
            "--out-dir",
            help="Output directory for built artifacts (default: <project>/dist).",
        )
        p_publish.add_argument("--sdist", action="store_true", help="Build sdist only (can combine with --wheel).")
        p_publish.add_argument("--wheel", action="store_true", help="Build wheel only (can combine with --sdist).")
        p_publish.add_argument("--no-build", dest="no_build", action="store_true", help="Skip the build step.")
        p_publish.add_argument("--no-build-logs", action="store_true", help="Hide build backend logs.")
        p_publish.add_argument(
            "--index",
            help="Named index to publish to (uv config). If omitted, uses uv default (PyPI).",
        )
        p_publish.add_argument(
            "--publish-url",
            help="Override the upload endpoint URL (advanced).",
        )
        p_publish.add_argument(
            "--check-url",
            help="Check an index URL for existing files to skip duplicate uploads (advanced).",
        )
        p_publish.add_argument(
            "--token",
            help="PyPI token (alternative to setting UV_PUBLISH_TOKEN).",
        )
        p_publish.add_argument(
            "--trusted-publishing",
            choices=["automatic", "always", "never"],
            help="Trusted publishing mode for uv publish.",
        )
        p_publish.add_argument("--no-attestations", action="store_true", help="Do not upload attestations.")
        p_publish.add_argument("--dry-run", action="store_true", help="Dry-run publish without uploading.")
        p_publish.add_argument("--yes", action="store_true", help="Do not prompt for confirmation.")
        p_publish.add_argument(
            "--non-interactive",
            action="store_true",
            help="Do not prompt; requires --token/UV_PUBLISH_TOKEN and --yes.",
        )
        p_publish.add_argument(
            "--skip-dashboard",
            action="store_true",
            help="Do not build/bundle the dashboard into the Python package (advanced).",
        )
        p_publish.add_argument(
            "files",
            nargs="*",
            help="Optional file globs to upload (default: dist/*).",
        )
        p_publish.set_defaults(func=cmd_publish)

    _add_common_env_help(parser)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "upgrade_self", False):
        rc = _upgrade_self()
        if rc == 0:
            sys.stdout.write("Upgrade finished. Re-run `oscanner --version` to confirm.\n")
        return int(rc)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    return int(args.func(args))


def _get_distribution_version() -> str:
    """
    Return the installed distribution version of `oscanner-skill-evaluator`.

    Falls back to package __version__ for editable/dev scenarios where distribution
    metadata isn't available.
    """
    try:
        return str(importlib_metadata.version("oscanner-skill-evaluator"))
    except importlib_metadata.PackageNotFoundError:
        return str(_PACKAGE_FALLBACK_VERSION)
    except Exception:
        return str(_PACKAGE_FALLBACK_VERSION)



