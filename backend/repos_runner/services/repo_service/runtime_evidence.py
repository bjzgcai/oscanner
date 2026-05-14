"""Runtime feature evidence for repository test reports."""

from __future__ import annotations

import asyncio
import copy
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


DOC_CANDIDATES = (
    "README.md",
    "README.en.md",
    "AGENT.md",
    "AGENTS.md",
)

DEFAULT_SERVICE_TIMEOUT_SECONDS = 75.0
PROBED_PORTS = {8000, 8100, 8200, 5173, 3000, 3003}


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


def _canonical_npm_command(line: str, repo_dir: Path) -> tuple[str, str] | None:
    lowered = line.lower()
    if "npm run dev" not in lowered:
        return None
    cwd = "."
    if re.search(r"\bcd\s+frontend\b", lowered):
        cwd = "frontend"
    elif (repo_dir / "frontend" / "package.json").is_file() and not (repo_dir / "package.json").is_file():
        cwd = "frontend"
    package_dir = repo_dir / cwd
    if not (package_dir / "package.json").is_file():
        return None
    command = "npm run dev"
    if "--host" not in lowered:
        command += " -- --host 127.0.0.1"
    return command, cwd


def discover_documented_start_commands(repo_dir: Path) -> list[dict[str, str]]:
    """Extract safe startup/check commands from README-like documents."""
    repo_dir = Path(repo_dir)
    discovered: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for doc_path in _iter_doc_files(repo_dir):
        try:
            text = doc_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in _iter_command_lines(text):
            command = _canonical_python_script_command(line, repo_dir)
            cwd = "."
            npm_command = _canonical_npm_command(line, repo_dir)
            if npm_command:
                command, cwd = npm_command
            if not command:
                continue
            key = (cwd, command)
            if key in seen:
                continue
            seen.add(key)
            discovered.append({
                "command": command,
                "cwd": cwd,
                "source": str(doc_path.relative_to(repo_dir)),
            })
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
) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "passed": bool(passed),
        "evidence": evidence,
        "features": features,
        "screenshots": screenshots or [],
    }


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


def _env_scene_configured(repo_dir: Path) -> bool:
    for name in [".env", ".env.example"]:
        env_path = repo_dir / name
        if not env_path.is_file():
            continue
        try:
            content = env_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == "ARCHIVE_SCENE" and value.strip().strip("'\""):
                return True
    return False


def _static_feature_checks(repo_dir: Path) -> list[dict[str, Any]]:
    harness = repo_dir / ".harness"
    harness_dirs = ["rules", "specs", "datasets", "eval", "logs"]
    project_skeleton_ok = all(
        path.exists()
        for path in [
            repo_dir / "README.md",
            repo_dir / "frontend",
            repo_dir / "services" / "app_backend",
            repo_dir / "services" / "domain_layer",
            repo_dir / "scripts",
            harness,
        ]
    )
    harness_setup_ok = (
        (harness / "README.md").is_file()
        and (harness / "ROADMAP.md").is_file()
        and all((harness / name).is_dir() for name in harness_dirs)
    )
    frontend_api_candidates = [
        repo_dir / "frontend" / "src" / "api.js",
        repo_dir / "frontend" / "src" / "api.ts",
        repo_dir / "frontend" / "src" / "lib" / "api.js",
        repo_dir / "frontend" / "src" / "lib" / "api.ts",
        repo_dir / "frontend" / "src" / "services" / "api.js",
        repo_dir / "frontend" / "src" / "services" / "api.ts",
    ]
    return [
        _feature_check(
            "project_skeleton",
            "Project skeleton initialized",
            project_skeleton_ok,
            "README.md, frontend/, services/, scripts/, .harness/",
            [
                "Project skeleton initialization",
                "Project unified skeleton initialization",
                "Project scaffold initialized",
            ],
        ),
        _feature_check(
            "harness_setup",
            ".harness key files and directories exist",
            harness_setup_ok,
            ".harness README.md, ROADMAP.md, rules/, specs/, datasets/, eval/, logs/",
            [
                "Harness directory setup",
                "Harness file setup",
                ".harness key files and directories established",
            ],
        ),
        _feature_check(
            "environment_configuration",
            "Environment configuration exists",
            _env_scene_configured(repo_dir),
            ".env or .env.example ARCHIVE_SCENE",
            [
                "Environment configuration",
                "ENV scene configuration",
                ".env main scene configuration",
            ],
        ),
        _feature_check(
            "domain_layer_directory",
            "domain_layer directory exists",
            (repo_dir / "services" / "domain_layer").is_dir(),
            "services/domain_layer",
            ["domain_layer directory created", "domain_layer directory exists"],
        ),
        _feature_check(
            "domain_layer_requirements",
            "domain_layer requirements.txt exists",
            (repo_dir / "services" / "domain_layer" / "requirements.txt").is_file(),
            "services/domain_layer/requirements.txt",
            ["domain_layer requirements.txt created", "domain_layer requirements.txt exists"],
        ),
        _feature_check(
            "api_wrapper_reserved",
            "API call wrapper reserved",
            any(path.is_file() for path in frontend_api_candidates),
            "frontend/src api wrapper candidate",
            ["API call encapsulation reserved", "API call wrapper reserved"],
        ),
        _feature_check(
            "harness_readme",
            ".harness README.md exists",
            (harness / "README.md").is_file(),
            ".harness/README.md",
            [".harness README.md created", ".harness/README.md exists"],
        ),
        _feature_check(
            "harness_roadmap",
            ".harness ROADMAP.md exists",
            (harness / "ROADMAP.md").is_file(),
            ".harness/ROADMAP.md",
            [".harness ROADMAP.md created", ".harness/ROADMAP.md exists"],
        ),
        *[
            _feature_check(
                f"harness_{name}",
                f".harness {name}/ exists",
                (harness / name).is_dir(),
                f".harness/{name}/",
                [
                    f".harness {name} directory created",
                    f".harness {name}/ exists",
                    f".harness/{name}/ exists",
                ],
            )
            for name in ["rules", "specs", "datasets", "eval", "logs"]
        ],
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
    args = shlex.split(command_item["command"])
    if not args:
        raise ValueError("Empty command")
    if args[0] == "python":
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


async def _capture_screenshot(url: str, screenshot_path: Path) -> bool:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

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


async def collect_runtime_evidence(
    clone_dir: Path | str,
    tag: str = "",
    progress_callback=None,
    service_timeout: float = DEFAULT_SERVICE_TIMEOUT_SECONDS,
    execution_session=None,
) -> dict[str, Any]:
    """Start documented services and collect runtime/static feature evidence."""
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
    if not clone_dir.is_dir():
        evidence["enabled"] = False
        evidence["warnings"].append(f"Clone directory not found: {clone_dir}")
        return evidence

    commands = discover_documented_start_commands(clone_dir)
    evidence["commands"] = commands
    evidence["checks"].extend(_static_feature_checks(clone_dir))
    baseline_ports = None if getattr(execution_session, "is_docker", False) else {
        port: _listening_pids(port) for port in PROBED_PORTS
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

        health_ok, health_url, health_detail = await _wait_http(
            [
                "http://127.0.0.1:8000/health",
                "http://127.0.0.1:8200/health",
                "http://127.0.0.1:8100/health",
            ],
            expect_json=True,
            timeout=service_timeout,
            baseline_ports=baseline_ports,
            execution_session=execution_session,
        )
        evidence["checks"].append(
            _feature_check(
                "health_json",
                "/health returns JSON",
                health_ok,
                health_url or health_detail,
                ["Health endpoint returns JSON", "/health returns valid JSON"],
            )
        )

        app_ok, app_url, app_detail = await _wait_http(
            ["http://127.0.0.1:8000/health"],
            expect_json=True,
            timeout=2.0,
            baseline_ports=baseline_ports,
            execution_session=execution_session,
        )
        evidence["checks"].append(
            _feature_check(
                "app_backend_starts",
                "app_backend starts",
                app_ok,
                app_url or app_detail,
                ["app_backend starts", "app_backend service starts"],
            )
        )

        domain_ok, domain_url, domain_detail = await _wait_http(
            ["http://127.0.0.1:8200/health"],
            expect_json=True,
            timeout=2.0,
            baseline_ports=baseline_ports,
            execution_session=execution_session,
        )
        evidence["checks"].append(
            _feature_check(
                "domain_unified_port",
                "domain_layer uses one service port",
                domain_ok,
                domain_url or domain_detail,
                ["Domain service unified port", "Domain layer single port"],
            )
        )

        docs_ok, docs_url, docs_detail = await _wait_http(
            ["http://127.0.0.1:8000/docs", "http://127.0.0.1:8200/docs"],
            timeout=8.0,
            baseline_ports=baseline_ports,
            execution_session=execution_session,
        )
        docs_screenshots: list[str] = []
        if docs_ok and docs_url and not getattr(execution_session, "is_docker", False):
            docs_path = artifact_dir / "screenshots" / "docs.png"
            if await _capture_screenshot(docs_url, docs_path):
                docs_screenshots.append(_relative_artifact(docs_path, clone_dir))
        evidence["checks"].append(
            _feature_check(
                "docs_accessible",
                "/docs accessible",
                docs_ok,
                docs_url or docs_detail,
                ["Docs endpoint accessible", "/docs accessible"],
                docs_screenshots,
            )
        )

        frontend_ok, frontend_url, frontend_detail = await _wait_http(
            [
                "http://127.0.0.1:5173",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3003",
            ],
            timeout=12.0,
            baseline_ports=baseline_ports,
            execution_session=execution_session,
        )
        frontend_screenshots: list[str] = []
        dom_text = ""
        if frontend_ok and frontend_url:
            if not getattr(execution_session, "is_docker", False):
                homepage_path = artifact_dir / "screenshots" / "homepage.png"
                if await _capture_screenshot(frontend_url, homepage_path):
                    frontend_screenshots.append(_relative_artifact(homepage_path, clone_dir))
            dom_text = await _dump_dom(frontend_url, execution_session=execution_session)
        evidence["checks"].append(
            _feature_check(
                "frontend_dev_server",
                "Frontend dev server starts",
                frontend_ok,
                frontend_url or frontend_detail,
                ["Frontend npm run dev starts"],
                frontend_screenshots,
            )
        )
        evidence["checks"].append(
            _feature_check(
                "homepage_opens",
                "Homepage opens",
                frontend_ok,
                frontend_url or frontend_detail,
                ["Homepage opens", "Homepage loads"],
                frontend_screenshots,
            )
        )
        scene_placeholder = bool(re.search(r"(场景|选择|scene)", dom_text, flags=re.IGNORECASE))
        evidence["checks"].append(
            _feature_check(
                "homepage_scene_placeholder",
                "Homepage scene selection placeholder",
                frontend_ok and scene_placeholder,
                "DOM contains scene placeholder text" if scene_placeholder else "Scene placeholder text not found",
                ["Homepage scene selection placeholder", "Homepage shows scene selection"],
                frontend_screenshots,
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
    for feature in moved:
        if feature not in covered:
            covered.append(feature)

    total = len(covered) + len(remaining)
    merged["covered"] = covered
    merged["not_covered"] = remaining
    merged["coverage_ratio"] = (len(covered) / total) if total else 1.0
    merged["runtime_covered"] = moved
    return merged
