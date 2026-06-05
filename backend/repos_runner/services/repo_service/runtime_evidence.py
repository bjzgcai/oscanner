"""Runtime feature evidence for repository test reports."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from repos_runner.grading import normalize_grading_rubric

from .llm import _message_text_content, _messages_create_with_fallback


DOC_CANDIDATES = (
    "README.md",
    "README.en.md",
    "AGENT.md",
    "AGENTS.md",
)

DEFAULT_SERVICE_TIMEOUT_SECONDS = 75.0
DEFAULT_RUNTIME_COMPAT_MODEL = "deepseek/deepseek-v4-pro"
SHELL_CONTROL_TOKENS = (" && ", " || ", ";")
MAX_RELATIVE_PATH_LENGTH = 1024
MAX_PATH_PART_LENGTH = 255


def _slug(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://", "", text)
    text = re.sub(r"[^a-z0-9._-]+", "_", text)
    return text.strip("._-") or fallback


def _safe_tag(tag: Any) -> str:
    text = str(tag or "").strip() or "untagged"
    return _slug(text, fallback="untagged")


def _normalize_feature(value: Any) -> str:
    text = str(value or "").lower().replace("/", " ")
    text = re.sub(r"[^a-z0-9.\u4e00-\u9fff]+", " ", text)
    return " ".join(text.split())


def _iter_doc_files(repo_dir: Path) -> list[Path]:
    files: list[Path] = []
    for name in DOC_CANDIDATES:
        path = repo_dir / name
        if path.is_file():
            files.append(path)
    docs_dir = repo_dir / "docs"
    if docs_dir.is_dir():
        files.extend(sorted(docs_dir.rglob("*.md"))[:20])
    return files


def _iter_command_lines(text: str) -> list[str]:
    commands: list[str] = []
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not line:
            continue
        if in_fence:
            commands.append(line)
            continue
        if line.startswith(("-", "*")):
            commands.append(line.lstrip("-* ").strip("` "))
        elif line.startswith("$ "):
            commands.append(line[2:].strip())
    return commands


def _safe_documented_cwd(line: str, repo_dir: Path, current_cwd: str) -> str | None:
    match = re.match(r"^\s*cd\s+([^\s;&|]+)\s*$", line)
    if not match:
        return None
    raw_path = match.group(1).strip().strip("'\"")
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        return None
    next_dir = (repo_dir / current_cwd / path).resolve()
    try:
        rel = next_dir.relative_to(repo_dir.resolve())
    except ValueError:
        return None
    if not next_dir.is_dir():
        return None
    return "." if str(rel) == "." else rel.as_posix()


def _canonical_python_script_command(line: str, repo_dir: Path) -> str | None:
    match = re.search(
        r"\b(?:python|python3)\s+(scripts/(?:dev-[a-z0-9_-]+|start|check|tasks)\.py(?:\s+[a-z0-9_-]+)?)",
        line,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    script_and_args = match.group(1).strip()
    script = script_and_args.split()[0]
    if not (repo_dir / script).is_file():
        return None
    if script == "scripts/start.py" and script_and_args != "scripts/start.py start":
        return None
    if "scripts/tasks.py" in script_and_args and not re.search(r"\bcheck\b", script_and_args):
        return None
    return f"python {script_and_args}"


def _canonical_uvicorn_command(line: str, repo_dir: Path, cwd: str) -> tuple[str, str] | None:
    match = re.search(
        r"(?:^|\s)(?:python(?:3)?\s+-m\s+)?uvicorn\s+"
        r"([a-zA-Z_][\w.]*:[a-zA-Z_][\w]*)\b(?P<args>.*)$",
        line,
    )
    if not match:
        return None
    app_target = match.group(1)
    args = match.group("args") or ""
    port_match = re.search(r"(?:^|\s)--port(?:=|\s+)(\d{2,5})(?:\s|$)", args)
    if not port_match:
        return None
    port = int(port_match.group(1))
    package_dir = (repo_dir / cwd).resolve()
    try:
        package_dir.relative_to(repo_dir.resolve())
    except ValueError:
        return None
    if not package_dir.is_dir():
        return None
    module_name = app_target.split(":", 1)[0]
    module_path = package_dir / Path(*module_name.split(".")).with_suffix(".py")
    package_init = package_dir / Path(*module_name.split(".")) / "__init__.py"
    if not module_path.is_file() and not package_init.is_file():
        return None
    return f"python -m uvicorn {app_target} --host 127.0.0.1 --port {port}", cwd


def _setup_state_for(setup_by_cwd: dict[str, dict[str, Any]], cwd: str) -> dict[str, Any]:
    return setup_by_cwd.setdefault(cwd, {"venv": "", "requirements": [], "npm_install": False})


def _remember_documented_setup(line: str, repo_dir: Path, cwd: str, setup_by_cwd: dict[str, dict[str, Any]]) -> bool:
    lowered = line.lower().strip()
    state = _setup_state_for(setup_by_cwd, cwd)

    venv_match = re.match(r"^(?:python|python3)\s+-m\s+venv\s+([^\s;&|]+)\s*$", line)
    if venv_match:
        venv_dir = venv_match.group(1).strip().strip("'\"")
        path = Path(venv_dir)
        if not path.is_absolute() and ".." not in path.parts:
            state["venv"] = path.as_posix()
        return True

    if re.search(r"(?:^|\s)(?:source\s+)?\.?/?\.venv[\\/](?:scripts|bin)[\\/]activate", lowered):
        if not state.get("venv"):
            state["venv"] = ".venv"
        return True

    pip_match = re.match(r"^(?:python\s+-m\s+)?pip(?:3)?\s+install\s+-r\s+([^\s;&|]+)\s*$", line)
    if pip_match:
        req = pip_match.group(1).strip().strip("'\"")
        req_path = Path(req)
        if not req_path.is_absolute() and ".." not in req_path.parts and (repo_dir / cwd / req_path).is_file():
            requirements = state.setdefault("requirements", [])
            req_value = req_path.as_posix()
            if req_value not in requirements:
                requirements.append(req_value)
        return True

    if lowered in {"npm install", "npm i", "pnpm install", "yarn install"}:
        state["npm_install"] = True
        return True

    return False


def _with_python_setup(command: str, repo_dir: Path, cwd: str, setup_by_cwd: dict[str, dict[str, Any]]) -> str:
    state = _setup_state_for(setup_by_cwd, cwd)
    requirements = list(state.get("requirements") or [])
    if not requirements and (repo_dir / cwd / "requirements.txt").is_file():
        requirements.append("requirements.txt")

    prefix: list[str] = []
    venv = str(state.get("venv") or "").strip()
    if venv:
        safe_venv = Path(venv).as_posix()
        prefix.append(f"python -m venv {shlex.quote(safe_venv)}")
        prefix.append(f". {shlex.quote(safe_venv + '/bin/activate')}")
    for requirement in requirements:
        prefix.append(f"python -m pip install -r {shlex.quote(requirement)}")

    if not prefix:
        return command
    return " && ".join([*prefix, command])


def _with_node_setup(command: str, cwd: str, setup_by_cwd: dict[str, dict[str, Any]]) -> str:
    state = _setup_state_for(setup_by_cwd, cwd)
    if state.get("npm_install"):
        return f"npm install && {command}"
    return command


def _canonical_npm_command(line: str, repo_dir: Path, cwd: str = ".") -> tuple[str, str] | None:
    lowered = line.lower()
    if "npm run dev" not in lowered:
        return None
    command_cwd = cwd
    if re.search(r"\bcd\s+frontend\b", lowered):
        command_cwd = "frontend"
    elif (repo_dir / "frontend" / "package.json").is_file() and not (repo_dir / "package.json").is_file():
        command_cwd = "frontend"
    package_dir = repo_dir / command_cwd
    if not (package_dir / "package.json").is_file():
        return None
    command = "npm run dev"
    if "--host" not in lowered:
        command += " -- --host 127.0.0.1"
    return command, command_cwd


def _normalize_compatible_command(
    command: str,
    cwd: str,
    repo_dir: Path,
    setup_by_cwd: dict[str, dict[str, Any]],
) -> tuple[str, str] | None:
    safe_cwd = _safe_documented_cwd(f"cd {cwd}", repo_dir, ".") if cwd != "." else "."
    if safe_cwd is None:
        return None

    script_command = _canonical_python_script_command(command, repo_dir)
    if script_command:
        return script_command, "."

    uvicorn_command = _canonical_uvicorn_command(command, repo_dir, safe_cwd)
    if uvicorn_command:
        normalized, command_cwd = uvicorn_command
        return _with_python_setup(normalized, repo_dir, command_cwd, setup_by_cwd), command_cwd

    npm_command = _canonical_npm_command(command, repo_dir, safe_cwd)
    if npm_command:
        normalized, command_cwd = npm_command
        return _with_node_setup(normalized, command_cwd, setup_by_cwd), command_cwd

    return None


def _runtime_compat_llm_enabled() -> bool:
    return _is_truthy(os.getenv("REPOS_RUNNER_RUNTIME_COMPAT_LLM", ""))


def _runtime_compat_model() -> str:
    return os.getenv("REPOS_RUNNER_RUNTIME_COMPAT_MODEL", "").strip() or DEFAULT_RUNTIME_COMPAT_MODEL


def _repo_path_sample(repo_dir: Path, limit: int = 250) -> list[str]:
    skip_dirs = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}
    paths: list[str] = []
    for path in sorted(repo_dir.rglob("*")):
        try:
            rel = path.relative_to(repo_dir)
        except ValueError:
            continue
        if any(part in skip_dirs or part.startswith(".venv") for part in rel.parts):
            continue
        paths.append(rel.as_posix() + ("/" if path.is_dir() else ""))
        if len(paths) >= limit:
            break
    return paths


def _docs_text_sample(repo_dir: Path, limit: int = 20000) -> str:
    doc_parts: list[str] = []
    for doc_path in _iter_doc_files(repo_dir):
        try:
            text = doc_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        doc_parts.append(f"--- {doc_path.relative_to(repo_dir)} ---\n{text[:5000]}")
    return "\n\n".join(doc_parts)[:limit]


def _safe_relative_path(repo_dir: Path, raw_path: Any) -> Path | None:
    text = str(raw_path or "").strip().strip("'\"`")
    if not text:
        return None
    if any(char in text for char in ("\x00", "\r", "\n")):
        return None
    if len(text) > MAX_RELATIVE_PATH_LENGTH:
        return None
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        return None
    if any(not part or len(part) > MAX_PATH_PART_LENGTH for part in path.parts):
        return None
    resolved = (repo_dir / path).resolve()
    try:
        resolved.relative_to(repo_dir.resolve())
    except ValueError:
        return None
    return resolved


def _ports_from_commands(commands: list[dict[str, str]]) -> list[int]:
    ports: list[int] = []
    for item in commands:
        for match in re.finditer(r"(?:^|\s)(?:--port(?:=|\s+)|-p\s+)(\d{2,5})(?:\s|$)", item.get("command", "")):
            port = int(match.group(1))
            if 1 <= port <= 65535 and port not in ports:
                ports.append(port)
    return ports


def _ports_from_runtime_plan(plan: dict[str, list[dict[str, Any]]]) -> list[int]:
    ports: list[int] = []
    for group_name in ["http_checks", "ui_checks"]:
        for item in plan.get(group_name) or []:
            for url in item.get("urls") or []:
                port = urlparse(str(url)).port
                if port and port not in ports:
                    ports.append(port)
    return ports


def _extract_json_array(text: str) -> list[Any]:
    match = re.search(r"\[.*\]", text or "", flags=re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _extract_json_object(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text or "", flags=re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _discover_llm_compatible_start_commands(
    repo_dir: Path,
    setup_by_cwd: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    if not _runtime_compat_llm_enabled():
        return []

    doc_parts: list[str] = []
    for doc_path in _iter_doc_files(repo_dir):
        try:
            text = doc_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        doc_parts.append(f"--- {doc_path.relative_to(repo_dir)} ---\n{text[:5000]}")

    if not doc_parts:
        return []

    repo_paths_json = json.dumps(_repo_path_sample(repo_dir), ensure_ascii=False)
    docs_text = "\n\n".join(doc_parts)[:20000]
    prompt = f"""You are helping normalize repository startup instructions for a Linux/Docker test runner.

Return ONLY a JSON array of objects with this shape:
[{{"command": "uvicorn package.main:app --port 12345", "cwd": "relative/service", "source": "README.md"}}]

Allowed command families:
- uvicorn <module>:<app> --port <port>
- python -m uvicorn <module>:<app> --port <port>
- npm run dev
- python scripts/dev-*.py
- python scripts/start.py start
- python scripts/check.py
- python scripts/tasks.py check

Rules:
- Use only relative cwd values that exist in the repository.
- Do not include install, activate, rm, curl, shell redirection, secrets, or arbitrary commands.
Repository paths:
{repo_paths_json}

Documents:
{docs_text}
"""
    try:
        message = _messages_create_with_fallback(
            model=_runtime_compat_model(),
            require_text=True,
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return []

    candidates = _extract_json_array(_message_text_content(message))
    commands: list[dict[str, str]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_compatible_command(
            str(item.get("command") or ""),
            str(item.get("cwd") or "."),
            repo_dir,
            setup_by_cwd,
        )
        if not normalized:
            continue
        command, cwd = normalized
        source = str(item.get("source") or "LLM compatibility scan").strip() or "LLM compatibility scan"
        commands.append({"command": command, "cwd": cwd, "source": source})
    return commands


def discover_documented_start_commands(repo_dir: Path) -> list[dict[str, str]]:
    """Extract safe startup/check commands from README-like documents."""
    repo_dir = Path(repo_dir)
    discovered: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    setup_by_cwd: dict[str, dict[str, Any]] = {}

    for doc_path in _iter_doc_files(repo_dir):
        try:
            text = doc_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        cwd = "."
        for line in _iter_command_lines(text):
            next_cwd = _safe_documented_cwd(line, repo_dir, cwd)
            if next_cwd is not None:
                cwd = next_cwd
                continue
            if _remember_documented_setup(line, repo_dir, cwd, setup_by_cwd):
                continue
            command = _canonical_python_script_command(line, repo_dir)
            command_cwd = "."
            uvicorn_command = _canonical_uvicorn_command(line, repo_dir, cwd)
            if uvicorn_command:
                command, command_cwd = uvicorn_command
                command = _with_python_setup(command, repo_dir, command_cwd, setup_by_cwd)
            npm_command = _canonical_npm_command(line, repo_dir, cwd)
            if npm_command:
                command, command_cwd = npm_command
                command = _with_node_setup(command, command_cwd, setup_by_cwd)
            if not command:
                continue
            key = (command_cwd, command)
            if key in seen:
                continue
            seen.add(key)
            discovered.append({
                "command": command,
                "cwd": command_cwd,
                "source": str(doc_path.relative_to(repo_dir)),
            })
            if len(discovered) >= 8:
                break

    for item in _discover_llm_compatible_start_commands(repo_dir, setup_by_cwd):
        key = (item["cwd"], item["command"])
        if key in seen:
            continue
        seen.add(key)
        discovered.append(item)
        if len(discovered) >= 8:
            break

    if any("scripts/dev-" in item["command"] for item in discovered):
        discovered = [item for item in discovered if "scripts/start.py" not in item["command"]]
    if any("scripts/check.py" in item["command"] for item in discovered):
        discovered = [item for item in discovered if "scripts/tasks.py check" not in item["command"]]
    return discovered[:8]


def _feature_check(
    check_id: str,
    label: str,
    passed: bool,
    evidence: str,
    features: list[str],
    screenshots: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "passed": bool(passed),
        "evidence": evidence,
        "features": features,
        "screenshots": screenshots or [],
        "details": details or {},
    }


def _existence_evidence(path_label: str, exists: bool) -> str:
    return path_label if exists else f"{path_label} 不存在"


def runtime_subprocess_env() -> dict[str, str]:
    """Return a minimal env for untrusted repo runtime commands."""
    env = {}
    for key in ["PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"]:
        value = os.environ.get(key)
        if value:
            env[key] = value
    env["PYTHONUNBUFFERED"] = "1"
    env["CI"] = "1"
    return env


def _is_truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _static_feature_checks(repo_dir: Path) -> list[dict[str, Any]]:
    """Collect generic static facts; course semantics are handled later."""
    repo_paths = _repo_path_sample(repo_dir)
    return [
        _feature_check(
            "repository_static_inventory",
            "Repository static file inventory",
            True,
            f"{len(repo_paths)} repository paths captured",
            [],
            details={"paths": repo_paths},
        )
    ]


def _artifact_dir(clone_dir: Path, tag: str = "") -> Path:
    return clone_dir / f"TEST_ARTIFACTS_{_safe_tag(tag)}" / "runtime-evidence"


def _relative_artifact(path: Path, clone_dir: Path) -> str:
    return path.relative_to(clone_dir).as_posix()


def _command_log_path(command_item: dict[str, str], artifact_dir: Path) -> Path:
    log_name = _slug(command_item["command"].replace(" ", "_"))[:80] + ".log"
    return artifact_dir / "logs" / log_name


def _start_process(
    command_item: dict[str, str],
    repo_dir: Path,
    artifact_dir: Path,
    execution_session=None,
) -> subprocess.Popen | None:
    command = command_item["command"]
    use_shell = any(token in command for token in SHELL_CONTROL_TOKENS)
    args = ["/bin/sh", "-c", command] if use_shell else shlex.split(command)
    if not args:
        raise ValueError("Empty command")
    if not use_shell and args[0] == "python":
        args[0] = sys.executable

    log_path = _command_log_path(command_item, artifact_dir)
    if getattr(execution_session, "is_docker", False):
        execution_session.start_background(
            command_item["command"],
            cwd=repo_dir / command_item.get("cwd", "."),
            log_path=log_path,
            env=runtime_subprocess_env(),
        )
        return None

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("ab")
    try:
        return subprocess.Popen(
            args,
            cwd=repo_dir / command_item.get("cwd", "."),
            env=runtime_subprocess_env(),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log_file.close()


async def _run_check_command(
    command_item: dict[str, str],
    repo_dir: Path,
    artifact_dir: Path,
    timeout: int = 90,
    execution_session=None,
) -> dict[str, Any]:
    args = shlex.split(command_item["command"])
    if args and args[0] == "python":
        args[0] = sys.executable
    log_path = _command_log_path(command_item, artifact_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def _run() -> tuple[bool, str]:
        try:
            if getattr(execution_session, "is_docker", False):
                result = execution_session.run(
                    command_item["command"],
                    cwd=repo_dir / command_item.get("cwd", "."),
                    env=runtime_subprocess_env(),
                    timeout=timeout,
                )
                output = (result.stdout or "") + (result.stderr or "")
            else:
                result = subprocess.run(
                    args,
                    cwd=repo_dir / command_item.get("cwd", "."),
                    env=runtime_subprocess_env(),
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                )
                output = result.stdout or ""
            log_path.write_text(output, encoding="utf-8", errors="ignore")
            detail = f"exit {result.returncode}"
            if output.strip():
                detail += f": {output.strip().splitlines()[-1][:160]}"
            return result.returncode == 0, detail
        except Exception as error:
            log_path.write_text(str(error), encoding="utf-8", errors="ignore")
            return False, str(error)

    passed, detail = await asyncio.to_thread(_run)
    return _feature_check(
        "environment_check",
        "Environment check passes",
        passed,
        detail,
        ["Environment check passes"],
    )


def _stop_processes(processes: list[subprocess.Popen]) -> None:
    for proc in processes:
        if proc.poll() is not None:
            continue
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            try:
                proc.terminate()
            except OSError:
                pass
    deadline = time.monotonic() + 5
    for proc in processes:
        try:
            proc.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                try:
                    proc.kill()
                except OSError:
                    pass


def _listening_pids(port: int) -> set[int]:
    lsof = shutil.which("lsof")
    if lsof:
        result = subprocess.run(
            [lsof, f"-tiTCP:{port}", "-sTCP:LISTEN"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return {int(line) for line in result.stdout.splitlines() if line.strip().isdigit()}
    ss = shutil.which("ss")
    if ss:
        result = subprocess.run(
            [ss, "-ltnp", f"sport = :{port}"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return {int(pid) for pid in re.findall(r"pid=(\d+)", result.stdout)}
    return set()


def _url_has_runtime_listener(url: str, baseline_ports: dict[int, set[int]] | None) -> tuple[bool, str]:
    if not baseline_ports:
        return True, ""
    port = urlparse(url).port
    if not port or port not in baseline_ports:
        return True, ""
    before = baseline_ports.get(port, set())
    if not before:
        return True, ""
    current = _listening_pids(port)
    if current - before:
        return True, ""
    return False, f"{url}: port {port} was already occupied before starting documented services"


async def _wait_http(
    urls: list[str],
    expect_json: bool = False,
    timeout: float = 20.0,
    baseline_ports: dict[int, set[int]] | None = None,
    execution_session=None,
) -> tuple[bool, str, str]:
    deadline = time.monotonic() + timeout
    last_error = ""
    if getattr(execution_session, "is_docker", False):
        while time.monotonic() < deadline:
            for url in urls:
                ok, resolved_url, detail = await asyncio.to_thread(
                    execution_session.http_get,
                    url,
                    expect_json=expect_json,
                    timeout=5,
                )
                if ok:
                    return True, resolved_url, detail
                last_error = f"{url}: {detail}"
            await asyncio.sleep(1)
        return False, "", last_error or "No response"

    async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
        while time.monotonic() < deadline:
            for url in urls:
                try:
                    response = await client.get(url)
                    if response.status_code < 400:
                        ok_listener, listener_error = _url_has_runtime_listener(url, baseline_ports)
                        if not ok_listener:
                            last_error = listener_error
                            continue
                        if expect_json:
                            try:
                                response.json()
                            except ValueError as error:
                                last_error = f"{url}: non-JSON response ({error})"
                                continue
                        return True, url, f"HTTP {response.status_code}"
                    last_error = f"{url}: HTTP {response.status_code}"
                except Exception as error:
                    last_error = f"{url}: {error}"
            await asyncio.sleep(1)
    return False, "", last_error or "No response"


def _chrome_binary() -> str:
    for name in ["google-chrome", "chromium", "chromium-browser"]:
        path = shutil.which(name)
        if path:
            return path
    return ""


def _run_chrome(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    chrome = _chrome_binary()
    if not chrome:
        raise FileNotFoundError("No Chrome/Chromium binary found")
    return subprocess.run(
        [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


async def _capture_screenshot(url: str, screenshot_path: Path, execution_session=None) -> bool:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    if getattr(execution_session, "is_docker", False) and hasattr(execution_session, "capture_screenshot"):
        try:
            return await asyncio.to_thread(
                execution_session.capture_screenshot,
                url,
                screenshot_path,
                timeout=20,
            )
        except Exception:
            return False

    def _capture() -> bool:
        result = _run_chrome([
            "--window-size=1365,768",
            f"--screenshot={screenshot_path}",
            url,
        ])
        return result.returncode == 0 and screenshot_path.is_file() and screenshot_path.stat().st_size > 0

    try:
        return await asyncio.to_thread(_capture)
    except Exception:
        return False


async def _dump_dom(url: str, execution_session=None) -> str:
    if getattr(execution_session, "is_docker", False):
        if hasattr(execution_session, "dump_dom"):
            try:
                return await asyncio.to_thread(execution_session.dump_dom, url, timeout=10)
            except Exception:
                return ""
        return await asyncio.to_thread(execution_session.http_text, url, timeout=5)

    def _dump() -> str:
        result = _run_chrome(["--virtual-time-budget=3000", "--dump-dom", url])
        if result.returncode == 0:
            return result.stdout
        return ""

    try:
        return await asyncio.to_thread(_dump)
    except Exception:
        return ""


def _safe_local_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        return ""
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        return ""
    return text


def _feature_allowed(feature: Any, required_features: list[str]) -> str:
    norm = _normalize_feature(feature)
    by_norm = {_normalize_feature(item): item for item in required_features}
    return by_norm.get(norm, "")


def _normalize_runtime_plan(
    raw_plan: dict[str, Any],
    repo_dir: Path,
    required_features: list[str],
    command_ports: list[int],
) -> dict[str, list[dict[str, Any]]]:
    plan: dict[str, list[dict[str, Any]]] = {
        "static_checks": [],
        "http_checks": [],
        "ui_checks": [],
    }
    if not isinstance(raw_plan, dict) or not required_features:
        return plan

    for item in raw_plan.get("static_checks") or []:
        if not isinstance(item, dict):
            continue
        feature = _feature_allowed(item.get("feature"), required_features)
        if not feature:
            continue
        paths: list[str] = []
        for raw_path in item.get("paths") or []:
            path = _safe_relative_path(repo_dir, raw_path)
            if path is None:
                continue
            paths.append(path.relative_to(repo_dir.resolve()).as_posix())
        if paths:
            plan["static_checks"].append({
                "feature": feature,
                "paths": paths,
                "mode": "any" if str(item.get("mode") or "").lower() == "any" else "all",
            })

    for item in raw_plan.get("http_checks") or []:
        if not isinstance(item, dict):
            continue
        feature = _feature_allowed(item.get("feature"), required_features)
        if not feature:
            continue
        urls: list[str] = []
        for raw_url in item.get("urls") or []:
            url = _safe_local_url(raw_url)
            if url and url not in urls:
                urls.append(url)
        path = str(item.get("path") or "").strip()
        if path.startswith("/") and not path.startswith("//"):
            ports = []
            for raw_port in item.get("ports") or command_ports:
                try:
                    port = int(raw_port)
                except (TypeError, ValueError):
                    continue
                if 1 <= port <= 65535:
                    ports.append(port)
            for port in ports:
                url = f"http://127.0.0.1:{port}{path}"
                if url not in urls:
                    urls.append(url)
        if urls:
            plan["http_checks"].append({
                "feature": feature,
                "urls": urls[:8],
                "expect_json": bool(item.get("expect_json")),
            })

    for item in raw_plan.get("ui_checks") or []:
        if not isinstance(item, dict):
            continue
        feature = _feature_allowed(item.get("feature"), required_features)
        if not feature:
            continue
        urls = [
            url
            for url in (_safe_local_url(raw_url) for raw_url in item.get("urls") or [])
            if url
        ]
        keywords = [
            str(keyword).strip()
            for keyword in item.get("keywords") or []
            if str(keyword).strip()
        ]
        if urls:
            plan["ui_checks"].append({
                "feature": feature,
                "urls": urls[:5],
                "keywords": keywords[:12],
            })

    return plan


def _fallback_runtime_evidence_plan(
    tag_message: str,
    required_features: list[str],
    command_ports: list[int],
) -> dict[str, Any]:
    static_checks: list[dict[str, Any]] = []
    http_checks: list[dict[str, Any]] = []
    ui_checks: list[dict[str, Any]] = []
    text = str(tag_message or "")

    code_spans = re.findall(r"`([^`]+)`", text)
    path_spans = [
        span.strip()
        for span in code_spans
        if span.strip() and not span.strip().startswith("/") and ("/" in span or "." in span)
    ]
    for feature in required_features:
        feature_text = _normalize_feature(feature)
        paths = [
            path
            for path in path_spans
            if any(part and part in feature_text for part in _normalize_feature(path).split())
        ]
        if paths:
            static_checks.append({"feature": feature, "paths": paths, "mode": "all"})

    endpoint_paths = sorted(set(re.findall(r"`(/[A-Za-z0-9_./-]+)`|(?<!\w)(/[A-Za-z0-9_./-]+)", text)))
    flattened_paths = [first or second for first, second in endpoint_paths if (first or second)]
    for feature in required_features:
        for path in flattened_paths:
            if path.lower() in str(feature).lower() or path.lower().strip("/") in str(feature).lower():
                http_checks.append({
                    "feature": feature,
                    "path": path,
                    "ports": command_ports,
                    "expect_json": "json" in str(feature).lower() or "JSON" in text,
                })

    return {
        "static_checks": static_checks,
        "http_checks": http_checks,
        "ui_checks": ui_checks,
    }


def _llm_runtime_evidence_plan(
    repo_dir: Path,
    tag_message: str,
    required_features: list[str],
    commands: list[dict[str, str]],
    grading_rubric: str | None = None,
) -> dict[str, Any]:
    if not required_features or not str(tag_message or "").strip():
        return {}

    rubric = normalize_grading_rubric(grading_rubric)
    rubric_section = (
        "\nGrading rubric:\n"
        f"{rubric}\n"
        "Use the rubric to choose checks that prove the expected quality, but only for the exact required features.\n"
    )

    prompt = f"""Create a safe runtime-evidence plan for an automated repository evaluator.

Merged course/repository tag message:
{tag_message}
{rubric_section}

Required features extracted from that tag:
{json.dumps(required_features, ensure_ascii=False)}

Repository path sample:
{json.dumps(_repo_path_sample(repo_dir), ensure_ascii=False)}

README/docs sample:
{_docs_text_sample(repo_dir)}

Documented commands that the runner can start:
{json.dumps(commands, ensure_ascii=False)}

Return ONLY a JSON object with this shape:
{{
  "static_checks": [
    {{"feature": "exact required feature", "paths": ["relative/path"], "mode": "all"}}
  ],
  "http_checks": [
    {{"feature": "exact required feature", "path": "/health", "ports": [8000], "expect_json": true}}
  ],
  "ui_checks": [
    {{"feature": "exact required feature", "urls": ["http://127.0.0.1:5173"], "keywords": ["visible text"]}}
  ]
}}

Rules:
- Use only exact feature strings from the required features list.
- Use static_checks for file/directory requirements.
- Use http_checks for API/endpoint requirements.
- Use ui_checks for browser-visible page requirements.
- Use only relative repository paths.
- Use only localhost/127.0.0.1 URLs or endpoint paths plus ports found in the docs/commands.
- Omit a check when the tag does not provide enough information to verify it safely.
"""
    try:
        message = _messages_create_with_fallback(
            model=os.getenv("REPOS_RUNNER_EVIDENCE_PLAN_MODEL", "").strip() or _runtime_compat_model(),
            require_text=True,
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return {}
    return _extract_json_object(_message_text_content(message))


def _build_runtime_evidence_plan(
    repo_dir: Path,
    tag_message: str = "",
    required_features: list[str] | None = None,
    commands: list[dict[str, str]] | None = None,
    grading_rubric: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    features = [str(feature) for feature in (required_features or []) if str(feature).strip()]
    command_list = commands or []
    command_ports = _ports_from_commands(command_list)
    raw_plan = _llm_runtime_evidence_plan(
        repo_dir,
        tag_message,
        features,
        command_list,
        grading_rubric=grading_rubric,
    )
    if not raw_plan:
        raw_plan = _fallback_runtime_evidence_plan(tag_message, features, command_ports)
    return _normalize_runtime_plan(raw_plan, repo_dir, features, command_ports)


def _run_dynamic_static_check(repo_dir: Path, item: dict[str, Any]) -> dict[str, Any]:
    paths = [str(path) for path in item.get("paths") or []]
    mode = item.get("mode") or "all"
    existing = []
    for path in paths:
        try:
            if (repo_dir / path).exists():
                existing.append(path)
        except OSError:
            continue
    passed = bool(paths) and (bool(existing) if mode == "any" else len(existing) == len(paths))
    missing = [path for path in paths if path not in existing]
    evidence = ", ".join(existing) if passed else f"missing: {', '.join(missing)}"
    feature = str(item.get("feature") or "Static requirement")
    return _feature_check(
        f"dynamic_static_{_slug(feature)}",
        feature,
        passed,
        evidence,
        [feature],
        details={"paths": paths, "mode": mode},
    )


async def _run_dynamic_http_check(
    item: dict[str, Any],
    baseline_ports: dict[int, set[int]] | None,
    execution_session=None,
) -> dict[str, Any]:
    feature = str(item.get("feature") or "HTTP requirement")
    ok, url, detail = await _wait_http(
        list(item.get("urls") or []),
        expect_json=bool(item.get("expect_json")),
        timeout=8.0,
        baseline_ports=baseline_ports,
        execution_session=execution_session,
    )
    return _feature_check(
        f"dynamic_http_{_slug(feature)}",
        feature,
        ok,
        url or detail,
        [feature],
        details={"urls": item.get("urls") or [], "expect_json": bool(item.get("expect_json"))},
    )


async def _run_dynamic_ui_check(
    item: dict[str, Any],
    artifact_dir: Path,
    clone_dir: Path,
    baseline_ports: dict[int, set[int]] | None,
    execution_session=None,
) -> dict[str, Any]:
    feature = str(item.get("feature") or "UI requirement")
    urls = list(item.get("urls") or [])
    ok, url, detail = await _wait_http(
        urls,
        timeout=8.0,
        baseline_ports=baseline_ports,
        execution_session=execution_session,
    )
    screenshots: list[str] = []
    passed = False
    evidence = url or detail
    if ok and url:
        screenshot_path = artifact_dir / "screenshots" / f"{_slug(feature)}.png"
        if await _capture_screenshot(url, screenshot_path, execution_session=execution_session):
            screenshots.append(_relative_artifact(screenshot_path, clone_dir))
        dom_text = await _dump_dom(url, execution_session=execution_session)
        keywords = [str(keyword) for keyword in item.get("keywords") or [] if str(keyword).strip()]
        if keywords:
            passed = any(keyword.lower() in dom_text.lower() for keyword in keywords)
            evidence = "DOM contains requested text" if passed else "requested UI text not found"
        else:
            passed = True
    return _feature_check(
        f"dynamic_ui_{_slug(feature)}",
        feature,
        passed,
        evidence,
        [feature],
        screenshots,
        details={"urls": urls, "keywords": item.get("keywords") or []},
    )


async def collect_runtime_evidence(
    clone_dir: Path | str,
    tag: str = "",
    tag_message: str = "",
    required_features: list[str] | None = None,
    progress_callback=None,
    service_timeout: float = DEFAULT_SERVICE_TIMEOUT_SECONDS,
    execution_session=None,
    grading_rubric: str | None = None,
) -> dict[str, Any]:
    """Start documented services and collect tag-driven runtime/static evidence."""
    clone_dir = Path(clone_dir)
    artifact_dir = _artifact_dir(clone_dir, tag)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    evidence: dict[str, Any] = {
        "enabled": True,
        "executor": "docker" if getattr(execution_session, "is_docker", False) else "host",
        "clone_dir": str(clone_dir),
        "artifact_dir": str(artifact_dir),
        "commands": [],
        "checks": [],
        "covered_features": [],
        "warnings": [],
    }
    clean_rubric = normalize_grading_rubric(grading_rubric)
    evidence["grading_rubric"] = clean_rubric
    if not clone_dir.is_dir():
        evidence["enabled"] = False
        evidence["warnings"].append(f"Clone directory not found: {clone_dir}")
        return evidence

    commands = discover_documented_start_commands(clone_dir)
    evidence["commands"] = commands
    evidence["checks"].extend(_static_feature_checks(clone_dir))
    evidence["plan"] = _build_runtime_evidence_plan(
        clone_dir,
        tag_message=tag_message,
        required_features=required_features or [],
        commands=commands,
        grading_rubric=clean_rubric,
    )
    ports_to_track = sorted({
        *_ports_from_commands(commands),
        *_ports_from_runtime_plan(evidence["plan"]),
    })
    baseline_ports = None if getattr(execution_session, "is_docker", False) else {
        port: _listening_pids(port) for port in ports_to_track
    }

    processes: list[subprocess.Popen] = []
    try:
        for item in commands:
            command = item["command"]
            if "scripts/check.py" in command or "scripts/tasks.py" in command:
                evidence["checks"].append(
                    await _run_check_command(
                        item,
                        clone_dir,
                        artifact_dir,
                        execution_session=execution_session,
                    )
                )
                continue
            try:
                if progress_callback:
                    await progress_callback(f"Starting documented service: {command}")
                proc = _start_process(item, clone_dir, artifact_dir, execution_session)
                if proc is not None:
                    processes.append(proc)
            except Exception as error:
                evidence["warnings"].append(f"Failed to start '{command}': {error}")

        plan = evidence.get("plan") or {}
        for item in plan.get("static_checks") or []:
            evidence["checks"].append(_run_dynamic_static_check(clone_dir, item))
        for item in plan.get("http_checks") or []:
            evidence["checks"].append(
                await _run_dynamic_http_check(
                    item,
                    baseline_ports=baseline_ports,
                    execution_session=execution_session,
                )
            )
        for item in plan.get("ui_checks") or []:
            evidence["checks"].append(
                await _run_dynamic_ui_check(
                    item,
                    artifact_dir=artifact_dir,
                    clone_dir=clone_dir,
                    baseline_ports=baseline_ports,
                    execution_session=execution_session,
                )
            )
    finally:
        _stop_processes(processes)

    covered_features: list[str] = []
    for check in evidence["checks"]:
        if not check.get("passed"):
            continue
        for feature in check.get("features") or []:
            if feature not in covered_features:
                covered_features.append(feature)
    evidence["covered_features"] = covered_features
    evidence["summary"] = {
        "passed": len([check for check in evidence["checks"] if check.get("passed")]),
        "total": len(evidence["checks"]),
    }
    return evidence


def merge_runtime_feature_coverage(
    feature_coverage: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Move runtime-proven required features from not_covered to covered."""
    merged = copy.deepcopy(feature_coverage)
    covered = list(merged.get("covered") or [])
    not_covered = list(merged.get("not_covered") or [])

    runtime_features = list(evidence.get("covered_features") or [])
    for check in evidence.get("checks") or []:
        if check.get("passed"):
            runtime_features.extend(check.get("features") or [])
    runtime_norms = {_normalize_feature(feature) for feature in runtime_features}

    moved: list[str] = []
    remaining: list[str] = []
    for feature in not_covered:
        if _normalize_feature(feature) in runtime_norms:
            moved.append(feature)
        else:
            remaining.append(feature)

    llm_moved = _llm_match_runtime_feature_coverage(remaining, evidence)
    if llm_moved:
        llm_norms = {_normalize_feature(feature) for feature in llm_moved}
        next_remaining: list[str] = []
        for feature in remaining:
            if _normalize_feature(feature) in llm_norms:
                moved.append(feature)
            else:
                next_remaining.append(feature)
        remaining = next_remaining

    for feature in moved:
        if feature not in covered:
            covered.append(feature)

    total = len(covered) + len(remaining)
    merged["covered"] = covered
    merged["not_covered"] = remaining
    merged["coverage_ratio"] = (len(covered) / total) if total else 1.0
    merged["runtime_covered"] = moved
    return merged


def _llm_match_runtime_feature_coverage(
    remaining_features: list[str],
    evidence: dict[str, Any],
) -> list[str]:
    """Use passed runtime evidence to match required-feature paraphrases."""
    if not remaining_features:
        return []

    passed_checks: list[dict[str, Any]] = []
    failed_norms: set[str] = set()
    failed_checks: list[dict[str, Any]] = []
    for check in evidence.get("checks") or []:
        check_features = check.get("features") or []
        if check.get("passed"):
            passed_checks.append(
                {
                    "id": check.get("id"),
                    "label": check.get("label"),
                    "features": check_features,
                    "evidence": check.get("evidence"),
                    "details": check.get("details") or {},
                }
            )
            continue

        failed_norms.update(_normalize_feature(feature) for feature in check_features)
        failed_norms.add(_normalize_feature(check.get("label")))
        failed_checks.append(
            {
                "id": check.get("id"),
                "label": check.get("label"),
                "features": check_features,
                "evidence": check.get("evidence"),
            }
        )
    if not passed_checks and not evidence.get("covered_features"):
        return []

    prompt = f"""Match required features to runtime evidence from an automated repository test report.

Required features still marked uncovered:
{json.dumps(remaining_features, ensure_ascii=False)}

Passed runtime/static evidence:
{json.dumps({"covered_features": evidence.get("covered_features") or [], "checks": passed_checks}, ensure_ascii=False)}

Failed runtime checks that must not be used as positive evidence:
{json.dumps(failed_checks, ensure_ascii=False)}

Return ONLY a JSON object:
{{"covered": ["feature from required list"]}}

Rules:
- Only include exact strings copied from the required features list.
- Mark a feature covered when the passed evidence clearly proves the same requirement, even if wording differs.
- Do not include features that are absent, ambiguous, or only supported by failed checks.
"""
    try:
        message = _messages_create_with_fallback(
            model=os.getenv("REPOS_RUNNER_FEATURE_MATCH_MODEL", "").strip() or _runtime_compat_model(),
            require_text=True,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return []

    data = _extract_json_object(_message_text_content(message))
    covered = data.get("covered")
    if not isinstance(covered, list):
        return []

    by_norm = {_normalize_feature(feature): feature for feature in remaining_features}
    matched: list[str] = []
    seen: set[str] = set()
    for item in covered:
        norm = _normalize_feature(item)
        feature = by_norm.get(norm)
        if feature and norm not in seen and norm not in failed_norms:
            matched.append(feature)
            seen.add(norm)
    return matched
