"""
Repository services for cloning, exploring, and testing
"""

import os
import re
import subprocess
import shutil
import hashlib
import json
import asyncio
import venv as venv_mod
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime

import git

from repos_runner.services.sandbox import run_sandboxed


OPENROUTER_ANTHROPIC_BASE_URL = "https://openrouter.ai/api"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_repos_dir() -> Path:
    """Get the directory for storing cloned repositories"""
    base_dir = Path.home() / ".local" / "share" / "oscanner" / "repos"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def parse_repo_url(repo_url: str) -> Tuple[str, str, str]:
    """
    Parse repository URL to extract platform, owner, and repo name.

    Returns:
        Tuple of (platform, owner, repo_name)
    """
    repo_url = repo_url.rstrip("/").replace(".git", "")

    if "github.com" in repo_url:
        parts = repo_url.split("github.com/")[-1].split("/")
        return "github", parts[0], parts[1]
    elif "gitee.com" in repo_url:
        parts = repo_url.split("gitee.com/")[-1].split("/")
        return "gitee", parts[0], parts[1]
    else:
        raise ValueError(f"Unsupported repository URL: {repo_url}")


def _get_api_client(use_fallback: bool = False):
    """Return a configured Anthropic client.

    Primary: OPEN_ROUTER_KEY via OpenRouter
    Fallback: ANTHROPIC_API_KEY (+ optional ANTHROPIC_BASE_URL)
    """
    from anthropic import Anthropic

    if not use_fallback:
        openrouter_key = os.getenv("OPEN_ROUTER_KEY")
        if openrouter_key:
            openrouter_base_url = (
                os.getenv("OPEN_ROUTER_BASE_URL")
                or os.getenv("OPENROUTER_BASE_URL")
                or OPENROUTER_ANTHROPIC_BASE_URL
            )
            return Anthropic(api_key=openrouter_key, base_url=openrouter_base_url)

    # Fallback: ANTHROPIC_API_KEY + optional ANTHROPIC_BASE_URL
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "No API key available. Set OPEN_ROUTER_KEY (primary) or ANTHROPIC_API_KEY (fallback)"
        )

    kwargs: Dict[str, Any] = {"api_key": api_key}
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return Anthropic(**kwargs)


def _messages_create_with_fallback(**kwargs):
    """
    Create a messages response, trying OpenRouter first, then ANTHROPIC_API_KEY fallback.
    """
    client = _get_api_client()
    try:
        return client.messages.create(**kwargs)
    except Exception as primary_error:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise
        try:
            return _get_api_client(use_fallback=True).messages.create(**kwargs)
        except Exception as fallback_error:
            raise RuntimeError(
                f"Primary LLM request failed ({primary_error}); "
                f"ANTHROPIC_API_KEY fallback also failed ({fallback_error})"
            ) from fallback_error


# ---------------------------------------------------------------------------
# Clone
# ---------------------------------------------------------------------------

async def clone_repository(repo_url: str, sha: Optional[str] = None, tag: Optional[str] = None) -> Dict[str, Any]:
    """
    Clone a repository (shallow when no SHA/tag, full clone + checkout when SHA or tag given).

    Args:
        repo_url: Repository URL to clone
        sha: Optional commit SHA to checkout (takes priority over tag)
        tag: Optional tag to checkout (used only when sha is not provided)

    Returns:
        Dictionary containing repo metadata
    """
    platform, owner, repo_name = parse_repo_url(repo_url)

    repos_dir = get_repos_dir()
    clone_path = repos_dir / repo_name

    if clone_path.exists():
        await asyncio.to_thread(shutil.rmtree, clone_path)

    try:
        def _clone_sync():
            if sha:
                repo = git.Repo.clone_from(repo_url, clone_path)
                repo.git.checkout(sha)
                checked_out_sha = repo.head.commit.hexsha
            elif tag:
                repo = git.Repo.clone_from(repo_url, clone_path)
                repo.git.checkout(f"tags/{tag}")
                checked_out_sha = repo.head.commit.hexsha
            else:
                repo = git.Repo.clone_from(
                    repo_url, clone_path, depth=1, single_branch=True
                )
                checked_out_sha = repo.head.commit.hexsha

            default_branch = (
                repo.active_branch.name
                if not repo.head.is_detached
                else "detached"
            )

            return {
                "repo_name": repo_name,
                "default_branch": default_branch,
                "latest_commit_id": checked_out_sha,
                "clone_path": str(clone_path),
                "platform": platform,
                "owner": owner,
            }

        return await asyncio.to_thread(_clone_sync)

    except Exception as e:
        raise Exception(f"Failed to clone repository: {str(e)}")


# ---------------------------------------------------------------------------
# Virtual-environment with hash-based dependency caching
# ---------------------------------------------------------------------------

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



# ---------------------------------------------------------------------------
# Smarter test-framework detection (static, no LLM needed)
# ---------------------------------------------------------------------------

# Maps a config-file key to (setup_commands, test_commands)
_FRAMEWORK_MAP: List[Dict[str, Any]] = [
    # Python
    {
        "files": ["pytest.ini", "setup.cfg", "pyproject.toml", "conftest.py"],
        "content_hints": {"pyproject.toml": ["pytest"], "setup.cfg": ["pytest"]},
        "setup": ["pip install -e .[test] || pip install -r requirements.txt || true",
                  "pip install pytest pytest-json-report"],
        "test": ["pytest --json-report --json-report-file=.test_report.json -v || true"],
        "language": "python",
    },
    {
        "files": ["requirements-test.txt", "requirements_test.txt"],
        "content_hints": {},
        "setup": ["pip install -r requirements-test.txt"],
        "test": ["pytest --json-report --json-report-file=.test_report.json -v || true"],
        "language": "python",
    },
    # Node / Jest
    {
        "files": ["jest.config.js", "jest.config.ts", "jest.config.mjs"],
        "content_hints": {},
        "setup": ["npm install"],
        "test": ["npx jest --json --outputFile=.test_report.json || true"],
        "language": "node",
    },
    {
        "files": ["package.json"],
        "content_hints": {"package.json": ["jest"]},
        "setup": ["npm install"],
        "test": ["npx jest --json --outputFile=.test_report.json || true"],
        "language": "node",
    },
    # Node / Vitest
    {
        "files": ["vitest.config.ts", "vitest.config.js"],
        "content_hints": {},
        "setup": ["npm install"],
        "test": ["npx vitest run --reporter=json > .test_report.json || true"],
        "language": "node",
    },
    {
        "files": ["package.json"],
        "content_hints": {"package.json": ["vitest"]},
        "setup": ["npm install"],
        "test": ["npx vitest run --reporter=json > .test_report.json || true"],
        "language": "node",
    },
    # Node / Mocha
    {
        "files": [".mocharc.js", ".mocharc.yml", ".mocharc.json"],
        "content_hints": {},
        "setup": ["npm install"],
        "test": ["npx mocha --reporter json > .test_report.json || true"],
        "language": "node",
    },
    # Go
    {
        "files": ["go.mod"],
        "content_hints": {},
        "setup": ["go mod download"],
        "test": ["go test ./... -v -json > .test_report.json || true"],
        "language": "go",
    },
    # Rust
    {
        "files": ["Cargo.toml"],
        "content_hints": {},
        "setup": [],
        "test": ["cargo test -- --format json 2>&1 > .test_report.json || cargo test 2>&1 | tee .test_report.txt || true"],
        "language": "rust",
    },
    # Maven (Java)
    {
        "files": ["pom.xml"],
        "content_hints": {},
        "setup": [],
        "test": ["mvn test -q 2>&1 | tee .test_report.txt || true"],
        "language": "java",
    },
    # Gradle (Java/Kotlin)
    {
        "files": ["build.gradle", "build.gradle.kts"],
        "content_hints": {},
        "setup": [],
        "test": ["./gradlew test 2>&1 | tee .test_report.txt || true"],
        "language": "java",
    },
    # Ruby
    {
        "files": ["Gemfile"],
        "content_hints": {},
        "setup": ["bundle install"],
        "test": ["bundle exec rspec --format json --out .test_report.json || bundle exec rake test 2>&1 | tee .test_report.txt || true"],
        "language": "ruby",
    },
    # Dotnet
    {
        "files": [],
        "glob": "**/*.csproj",
        "content_hints": {},
        "setup": ["dotnet restore"],
        "test": ["dotnet test --logger trx 2>&1 | tee .test_report.txt || true"],
        "language": "dotnet",
    },
    # Elixir
    {
        "files": ["mix.exs"],
        "content_hints": {},
        "setup": ["mix deps.get"],
        "test": ["mix test --formatter ExUnit.CLIFormatter 2>&1 | tee .test_report.txt || true"],
        "language": "elixir",
    },
]


def _detect_frameworks_statically(clone_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Detect test framework from project files without calling an LLM.

    Returns a dict with 'setup_commands', 'test_commands', 'language',
    or None if nothing is detected.
    """
    for entry in _FRAMEWORK_MAP:
        # Check explicit files
        matched = any((clone_dir / f).exists() for f in entry.get("files", []))

        # Check glob patterns (e.g. *.csproj)
        if not matched and entry.get("glob"):
            matched = any(True for _ in clone_dir.glob(entry["glob"]))

        if not matched:
            continue

        # Check content hints if any
        hints = entry.get("content_hints", {})
        if hints:
            hint_ok = False
            for fname, keywords in hints.items():
                fpath = clone_dir / fname
                if fpath.exists():
                    try:
                        content = fpath.read_text(encoding="utf-8", errors="ignore").lower()
                        if any(kw.lower() in content for kw in keywords):
                            hint_ok = True
                            break
                    except Exception:
                        pass
            if not hint_ok:
                continue

        return {
            "setup_commands": entry["setup"],
            "test_commands": entry["test"],
            "language": entry["language"],
        }

    return None


def _load_test_config(clone_dir: Path) -> Optional[Dict[str, Any]]:
    """Load cached test_config.json if it exists."""
    config_path = clone_dir / "test_config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except Exception:
            pass
    return None


def _save_test_config(clone_dir: Path, config: Dict[str, Any]) -> None:
    """Atomically write test_config.json."""
    config_path = clone_dir / "test_config.json"
    tmp_path = config_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(config, indent=2))
    tmp_path.rename(config_path)


# ---------------------------------------------------------------------------
# Explore (Claude Code SDK agentic approach)
# ---------------------------------------------------------------------------

async def explore_repository(clone_path: str, progress_callback=None) -> str:
    """
    Explore repository and generate REPO_OVERVIEW.md using the Claude Code SDK.

    The SDK runs Claude as an agentic loop with shell-tool access so it can
    actually read files, list directories, and understand the project structure
    rather than just receiving a pre-built context string.

    Returns:
        Path to generated REPO_OVERVIEW.md
    """
    clone_dir = Path(clone_path)
    overview_path = clone_dir / "REPO_OVERVIEW.md"

    if progress_callback:
        await progress_callback("Starting repository exploration with Claude Code SDK...")

    try:
        from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock

        if progress_callback:
            await progress_callback("Claude is exploring the repository structure...")

        prompt = (
            "You are analyzing a software repository to understand how to run its tests. "
            "Explore the repository files, read the README, config files (package.json, "
            "pyproject.toml, Cargo.toml, go.mod, etc.), and any existing test files. "
            "Then produce a file called REPO_OVERVIEW.md in the current directory with "
            "this exact structure:\n\n"
            "# {repo_name}\n\n"
            "## Project Type\n"
            "<1-2 sentences: language, framework, purpose>\n\n"
            "## Test Framework\n"
            "<name of test framework(s) found, or 'None detected'>\n\n"
            "## Setup Commands\n"
            "```\n"
            "<commands to install dependencies, one per line>\n"
            "```\n\n"
            "## Test Commands\n"
            "```\n"
            "<commands to run tests, one per line>\n"
            "```\n\n"
            "Be concise. Only include what is needed to run tests. "
            "Write the file when done."
        )

        char_count = 0
        async for message in query(
            prompt=prompt,
            options=ClaudeCodeOptions(
                cwd=str(clone_dir),
                # Allow file reads and writes but no network calls
                allowed_tools=["Read", "Write", "Glob", "Bash"],
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        char_count += len(block.text)
                        if progress_callback and char_count % 200 < 20:
                            await progress_callback(
                                f"Claude exploring... ({char_count} chars processed)"
                            )

        # If Claude wrote the file, great. Otherwise fall back to context-based approach.
        if not overview_path.exists():
            if progress_callback:
                await progress_callback(
                    "SDK did not write the file directly; using context fallback..."
                )
            overview_path = Path(
                await _explore_via_messages_api(clone_path, progress_callback)
            )

        if progress_callback:
            await progress_callback("Repository exploration completed!")

        return str(overview_path)

    except ImportError:
        # claude-code-sdk not installed, fall back to messages API
        if progress_callback:
            await progress_callback(
                "claude-code-sdk not available; falling back to messages API..."
            )
        return await _explore_via_messages_api(clone_path, progress_callback)

    except Exception as e:
        if progress_callback:
            await progress_callback(f"SDK error ({e}); falling back to messages API...")
        return await _explore_via_messages_api(clone_path, progress_callback)


async def _explore_via_messages_api(clone_path: str, progress_callback=None) -> str:
    """Fallback: build context manually and call the Anthropic messages API."""
    clone_dir = Path(clone_path)
    overview_path = clone_dir / "REPO_OVERVIEW.md"

    if progress_callback:
        await progress_callback("Analyzing repository structure...")

    context = await _build_repo_context(clone_dir)

    if progress_callback:
        await progress_callback("Generating overview with Claude...")

    prompt = f"""Analyze this repository and generate a concise REPO_OVERVIEW.md focused on testing:

1. Project name and type (1-2 sentences)
2. Test framework(s) used (if any)
3. Setup/installation commands needed to run tests
4. Test commands to execute

Be extremely concise. Skip examples, features, and detailed documentation.

Repository context:
{context}

Generate the markdown content for REPO_OVERVIEW.md:"""

    async def _stream_once(client) -> str:
        content = ""
        last_progress_length = 0
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                content += text
                current_length = len(content)
                if (
                    progress_callback
                    and current_length - last_progress_length >= 200
                ):
                    await progress_callback(f"Generated {current_length} characters...")
                    last_progress_length = current_length
        return content

    try:
        overview_content = await _stream_once(_get_api_client())
    except Exception as primary_error:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise
        if progress_callback:
            await progress_callback(
                "Primary LLM request failed, retrying with ANTHROPIC_API_KEY fallback..."
            )
        try:
            overview_content = await _stream_once(_get_api_client(use_fallback=True))
        except Exception as fallback_error:
            raise RuntimeError(
                f"Primary LLM request failed ({primary_error}); "
                f"ANTHROPIC_API_KEY fallback also failed ({fallback_error})"
            ) from fallback_error

    if progress_callback:
        await progress_callback("Writing REPO_OVERVIEW.md...")

    overview_path.write_text(overview_content)
    return str(overview_path)


async def _build_repo_context(repo_path: Path) -> str:
    """Build a text summary of the repository for the messages-API fallback."""
    context_parts = []

    for readme in ["README.md", "README.txt", "README"]:
        readme_path = repo_path / readme
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8", errors="ignore")
                context_parts.append(f"## README:\n{content[:5000]}")
                break
            except Exception:
                pass

    try:
        tree_output = subprocess.run(
            ["tree", "-L", "3", "-I",
             "node_modules|venv|.git|__pycache__|*.pyc|.venv_*",
             str(repo_path)],
            capture_output=True, text=True, timeout=10,
        )
        if tree_output.returncode == 0:
            context_parts.append(f"## Directory Structure:\n{tree_output.stdout[:3000]}")
    except Exception:
        try:
            files = []
            for item in repo_path.rglob("*"):
                if any(
                    skip in str(item)
                    for skip in [".git", "node_modules", "venv", "__pycache__", ".venv_"]
                ):
                    continue
                rel_path = item.relative_to(repo_path)
                if len(files) < 100:
                    files.append(str(rel_path))
            context_parts.append("## Files:\n" + "\n".join(files))
        except Exception:
            pass

    config_files = [
        "package.json", "requirements.txt", "setup.py",
        "pyproject.toml", "Cargo.toml", "go.mod",
    ]
    for config_file in config_files:
        config_path = repo_path / config_file
        if config_path.exists():
            try:
                content = config_path.read_text(encoding="utf-8", errors="ignore")
                context_parts.append(f"## {config_file}:\n{content[:2000]}")
            except Exception:
                pass

    return "\n\n".join(context_parts)


# ---------------------------------------------------------------------------
# Test command detection (static-first, LLM fallback, cached)
# ---------------------------------------------------------------------------

async def detect_test_commands(overview_path: str) -> Dict[str, Any]:
    """
    Detect test commands from REPO_OVERVIEW.md.

    Strategy:
      1. Static detection from project files (no LLM cost)
      2. If nothing found, fall back to LLM parsing of REPO_OVERVIEW.md
      3. Cache result in test_config.json

    Returns:
        Dictionary containing test_commands, setup_commands, and language
    """
    overview_file = Path(overview_path)
    if not overview_file.exists():
        raise FileNotFoundError(f"REPO_OVERVIEW.md not found at {overview_path}")

    clone_dir = overview_file.parent

    # Check cache
    cached = _load_test_config(clone_dir)
    if cached:
        return cached

    # Static detection
    static = _detect_frameworks_statically(clone_dir)
    if static:
        _save_test_config(clone_dir, static)
        return static

    # LLM fallback
    result = await _detect_commands_via_llm(overview_file.read_text())
    _save_test_config(clone_dir, result)
    return result


async def _detect_commands_via_llm(overview_content: str) -> Dict[str, Any]:
    """Parse REPO_OVERVIEW.md with Claude to extract commands."""
    prompt = f"""Based on this REPO_OVERVIEW.md, identify the commands to run tests.

{overview_content}

Return a JSON object with this exact structure:
{{
  "test_commands": ["command1", "command2"],
  "setup_commands": ["optional setup command"],
  "language": "python|node|go|rust|java|ruby|dotnet|other"
}}

If no tests are found, return {{"test_commands": [], "setup_commands": [], "language": "unknown"}}
"""

    message = _messages_create_with_fallback(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {"test_commands": [], "setup_commands": [], "language": "unknown"}


# ---------------------------------------------------------------------------
# Structured test-output parsing
# ---------------------------------------------------------------------------

def _parse_json_report(clone_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Parse .test_report.json written by pytest-json-report or jest --json.
    Returns a dict with 'passed', 'failed', 'total', 'test_cases' or None.
    """
    report_path = clone_dir / ".test_report.json"
    if not report_path.exists():
        return None

    try:
        data = json.loads(report_path.read_text())
    except Exception:
        return None

    # pytest-json-report format
    if "summary" in data and "tests" in data:
        summary = data["summary"]
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0) + summary.get("error", 0)
        total = summary.get("total", passed + failed)

        test_cases = []
        for t in data.get("tests", []):
            outcome = t.get("outcome", "unknown")
            test_cases.append({
                "name": t.get("nodeid", t.get("name", "unknown")),
                "status": "passed" if outcome == "passed" else "failed",
                "duration": t.get("duration", 0),
                "output": t.get("call", {}).get("longrepr", "") if outcome != "passed" else "",
            })
        return {"passed": passed, "failed": failed, "total": total, "test_cases": test_cases}

    # jest --json format
    if "numPassedTests" in data:
        passed = data.get("numPassedTests", 0)
        failed = data.get("numFailedTests", 0)
        total = data.get("numTotalTests", passed + failed)

        test_cases = []
        for suite in data.get("testResults", []):
            for t in suite.get("testResults", []):
                status_raw = t.get("status", "unknown")
                test_cases.append({
                    "name": " > ".join(t.get("ancestorTitles", [])) + " > " + t.get("title", ""),
                    "status": "passed" if status_raw == "passed" else "failed",
                    "duration": t.get("duration", 0) / 1000.0,  # ms → s
                    "output": "\n".join(t.get("failureMessages", [])),
                })
        return {"passed": passed, "failed": failed, "total": total, "test_cases": test_cases}

    # Go test JSON format (one JSON object per line)
    if "Action" in data:
        # Single line parsed as object; re-read the file line by line
        report_path = clone_dir / ".test_report.json"
        return _parse_go_json_report(report_path)

    return None


def _parse_go_json_report(report_path: Path) -> Optional[Dict[str, Any]]:
    """Parse Go test JSON output (one JSON object per line)."""
    try:
        lines = report_path.read_text().splitlines()
        passed = 0
        failed = 0
        test_cases = []
        test_durations: Dict[str, float] = {}

        for line in lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            action = obj.get("Action", "")
            test = obj.get("Test", "")
            if not test:
                continue
            if action == "pass":
                passed += 1
                test_cases.append({
                    "name": test,
                    "status": "passed",
                    "duration": obj.get("Elapsed", 0),
                    "output": "",
                })
            elif action == "fail":
                failed += 1
                test_cases.append({
                    "name": test,
                    "status": "failed",
                    "duration": obj.get("Elapsed", 0),
                    "output": "",
                })

        total = passed + failed
        if total == 0:
            return None
        return {"passed": passed, "failed": failed, "total": total, "test_cases": test_cases}
    except Exception:
        return None


def _parse_test_output_with_regex(output: str) -> Optional[Dict[str, int]]:
    """Fast-path regex parsing for common test framework stdout."""

    # pytest: "9 failed, 9 passed"
    m = re.search(r"=+\s*(\d+)\s+failed,\s+(\d+)\s+passed", output)
    if m:
        failed, passed = int(m.group(1)), int(m.group(2))
        return {"passed": passed, "failed": failed, "total": passed + failed}

    # pytest: "9 passed"
    m = re.search(r"=+\s*(\d+)\s+passed", output)
    if m:
        passed = int(m.group(1))
        return {"passed": passed, "failed": 0, "total": passed}

    # Jest: "Tests:  9 failed, 9 passed, 18 total"
    m = re.search(r"Tests:\s+(\d+)\s+failed,\s+(\d+)\s+passed,\s+(\d+)\s+total", output)
    if m:
        return {"failed": int(m.group(1)), "passed": int(m.group(2)), "total": int(m.group(3))}

    # Jest all-passed: "Tests:  9 passed, 9 total"
    m = re.search(r"Tests:\s+(\d+)\s+passed,\s+(\d+)\s+total", output)
    if m:
        passed, total = int(m.group(1)), int(m.group(2))
        return {"passed": passed, "failed": total - passed, "total": total}

    # Go: "ok" / "FAIL" summary lines → "FAIL: N PASS: N" is non-standard; use basic ok/fail
    ok_count = len(re.findall(r"^ok\s+", output, re.MULTILINE))
    fail_count = len(re.findall(r"^FAIL\s+", output, re.MULTILINE))
    if ok_count + fail_count > 0:
        return {"passed": ok_count, "failed": fail_count, "total": ok_count + fail_count}

    # cargo test: "test result: ok. N passed; N failed"
    m = re.search(r"test result:.*?(\d+)\s+passed;\s+(\d+)\s+failed", output)
    if m:
        passed, failed = int(m.group(1)), int(m.group(2))
        return {"passed": passed, "failed": failed, "total": passed + failed}

    # Maven surefire: "Tests run: N, Failures: N, Errors: N"
    m = re.search(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)", output)
    if m:
        total, failures, errors = int(m.group(1)), int(m.group(2)), int(m.group(3))
        failed = failures + errors
        return {"passed": total - failed, "failed": failed, "total": total}

    # RSpec: "N examples, N failures"
    m = re.search(r"(\d+)\s+examples?,\s*(\d+)\s+failures?", output)
    if m:
        total, failed = int(m.group(1)), int(m.group(2))
        return {"passed": total - failed, "failed": failed, "total": total}

    return None


async def _parse_test_output_with_llm(output: str) -> Optional[Dict[str, int]]:
    """LLM fallback for unknown test frameworks."""
    try:
        truncated = output[-2000:] if len(output) > 2000 else output

        prompt = f"""Parse this test output and extract the test results.

Test output:
```
{truncated}
```

Return ONLY a JSON object (no other text):
{{
  "passed": <number>,
  "failed": <number>,
  "total": <number>
}}

If you cannot determine the counts, return: {{"passed": 0, "failed": 0, "total": 0}}
"""
        message = _messages_create_with_fallback(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()
        json_match = re.search(r"\{[^}]+\}", response_text)
        if json_match:
            result = json.loads(json_match.group())
            if all(k in result for k in ["passed", "failed", "total"]):
                if result["total"] > 0 and result["passed"] + result["failed"] == result["total"]:
                    return result
    except Exception:
        pass
    return None


async def _parse_test_output(output: str) -> Optional[Dict[str, int]]:
    result = _parse_test_output_with_regex(output)
    if result:
        return result
    return await _parse_test_output_with_llm(output)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

async def _generate_test_report(
    report_path: Path,
    repo_name: str,
    total: int,
    passed: int,
    failed: int,
    score: int,
    test_results: list,
) -> None:
    """Generate TEST_REPORT.md for analyzed repository."""
    pass_rate = (passed / total * 100) if total > 0 else 0
    fail_rate = (failed / total * 100) if total > 0 else 0

    if score >= 90:
        grade = "Excellent ⭐⭐⭐⭐⭐"
    elif score >= 70:
        grade = "Good ⭐⭐⭐⭐"
    elif score >= 50:
        grade = "Fair ⭐⭐⭐"
    else:
        grade = "Poor ⭐"

    report = f"""# Test Report: {repo_name}

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Overall Score**: {score}/100 ({grade})

## Summary
- **Total Tests**: {total}
- **Passed**: {passed} ({pass_rate:.1f}%)
- **Failed**: {failed} ({fail_rate:.1f}%)
- **Skipped**: 0 (0%)
- **Score**: {score}/100

## Test Results

"""

    if total == 0:
        report += """⚠️ **No tests detected in this repository**

This repository does not appear to have any automated tests configured.

"""

    passed_tests = [t for t in test_results if t["status"] == "passed"]
    failed_tests = [t for t in test_results if t["status"] == "failed"]

    if passed_tests:
        report += f"### ✅ Passed Tests ({len(passed_tests)})\n\n"
        for t in passed_tests:
            duration = t.get("duration", 0)
            report += f"- `{t['name']}` ({duration:.2f}s)\n"
        report += "\n"

    if failed_tests:
        report += f"### ❌ Failed Tests ({len(failed_tests)})\n\n"
        for t in failed_tests:
            duration = t.get("duration", 0)
            report += f"- `{t['name']}` ({duration:.2f}s)\n"
            output = t.get("output", "")
            if output:
                truncated_output = output[-500:] if len(output) > 500 else output
                report += f"  ```\n  {truncated_output}\n  ```\n"
        report += "\n"

    report += f"""## Score Breakdown

- **Pass Rate**: {pass_rate:.1f}% ({passed}/{total})
- **Base Score**: {score}/100

### Grade Scale
- 90-100: Excellent ⭐⭐⭐⭐⭐ (Production ready)
- 70-89: Good ⭐⭐⭐⭐ (Minor gaps acceptable)
- 50-69: Fair ⭐⭐⭐ (Needs improvement)
- 0-49: Poor ⭐ (Significant gaps)

## Recommendations

"""

    if total == 0:
        report += """### Get Started with Testing
1. Choose a testing framework appropriate for your language/stack
2. Write tests for critical functionality first
3. Aim for at least 70% code coverage
4. Set up continuous integration to run tests automatically

"""
    elif score < 70:
        report += """### Priority Actions
1. Fix all failing tests
2. Investigate root causes of failures
3. Add missing test coverage for critical paths
4. Re-run tests until score >= 70

"""

    if failed_tests:
        report += "### Failed Tests to Fix\n"
        for idx, t in enumerate(failed_tests[:5], 1):
            report += f"{idx}. `{t['name']}`\n"
        if len(failed_tests) > 5:
            report += f"\n...and {len(failed_tests) - 5} more\n"
        report += "\n"

    report += """## Next Steps

"""
    if total == 0:
        report += """1. Set up a testing framework for your project
2. Write initial tests for core functionality
3. Run analysis again: `/api/runner/run-tests`

"""
    else:
        report += """1. Review failed tests and fix underlying issues
2. Run tests again: `/api/runner/run-tests`
3. Aim for 70%+ pass rate (Good rating)
4. Target 90%+ pass rate (Excellent rating)

"""

    report += "---\n\n*Generated by repos_runner - Automated repository testing service*\n"

    report_path.write_text(report)


# ---------------------------------------------------------------------------
# Run tests (main entry point)
# ---------------------------------------------------------------------------

async def run_tests(
    clone_path: str,
    overview_path: str,
    progress_callback=None,
    setup_timeout: int = 120,
    test_timeout: int = 300,
) -> Dict[str, Any]:
    """
    Identify and run tests based on REPO_OVERVIEW.md.

    Args:
        clone_path: Path to the cloned repository
        overview_path: Path to REPO_OVERVIEW.md
        progress_callback: Optional async callback for progress updates
        setup_timeout: Seconds allowed per setup command (default 120)
        test_timeout: Seconds allowed per test command (default 300)

    Returns:
        Dictionary containing test results and score
    """
    clone_dir = Path(clone_path)
    overview_file = Path(overview_path)

    if not overview_file.exists():
        raise FileNotFoundError(f"REPO_OVERVIEW.md not found at {overview_path}")

    if progress_callback:
        await progress_callback("Reading REPO_OVERVIEW.md...")

    overview_content = overview_file.read_text()

    if progress_callback:
        await progress_callback("Identifying test commands...")

    # Try static detection first (cheap), then LLM
    test_info = _detect_frameworks_statically(clone_dir)
    if test_info:
        if progress_callback:
            await progress_callback(
                f"Detected {test_info.get('language', 'unknown')} project via static analysis"
            )
        # Cache it
        _save_test_config(clone_dir, test_info)
    else:
        # Check cache before calling LLM
        test_info = _load_test_config(clone_dir)
        if test_info:
            if progress_callback:
                await progress_callback("Using cached test configuration")
        else:
            if progress_callback:
                await progress_callback("Using LLM to identify test commands...")
            test_info = await _detect_commands_via_llm(overview_content)
            _save_test_config(clone_dir, test_info)

    # Run setup commands with hash-based venv caching for Python
    if test_info.get("setup_commands"):
        venv_python = ensure_repo_venv(clone_path)
        language = test_info.get("language", "")

        for cmd in test_info["setup_commands"]:
            if progress_callback:
                await progress_callback(f"Running setup: {cmd}")

            # Route pip installs through the per-repo venv
            if language == "python" and (
                cmd.startswith("pip install") or cmd.startswith("pip3 install")
            ):
                cmd = cmd.replace("pip install", f"{venv_python} -m pip install")
                cmd = cmd.replace("pip3 install", f"{venv_python} -m pip install")

            try:
                result = run_sandboxed(
                    cmd,
                    cwd=clone_dir,
                    timeout=setup_timeout,
                )
                if progress_callback and result.returncode != 0:
                    await progress_callback(f"Setup warning: {result.stderr[:200]}")
            except subprocess.TimeoutExpired:
                if progress_callback:
                    await progress_callback(
                        f"Setup command timed out after {setup_timeout}s: {cmd}"
                    )
            except Exception as e:
                if progress_callback:
                    await progress_callback(f"Setup failed: {str(e)}")

    # Run test commands
    test_commands = test_info.get("test_commands", [])
    num_commands = len(test_commands)

    if num_commands == 0:
        if progress_callback:
            await progress_callback("No tests found in repository")

        test_report_path = clone_dir / "TEST_REPORT.md"
        await _generate_test_report(
            report_path=test_report_path,
            repo_name=clone_dir.name,
            total=0, passed=0, failed=0, score=0,
            test_results=[],
        )
        return {
            "total": 0, "passed": 0, "failed": 0, "skipped": 0,
            "score": 0, "details": [],
            "message": "No tests found in repository",
            "report_path": str(test_report_path),
        }

    total_passed = 0
    total_failed = 0
    total_tests = 0
    all_test_cases: List[Dict[str, Any]] = []
    command_results = []

    venv_python = ensure_repo_venv(clone_path)
    language = test_info.get("language", "")

    for idx, cmd in enumerate(test_commands):
        if progress_callback:
            await progress_callback(f"Running test {idx + 1}/{num_commands}: {cmd}")

        # Route Python commands through per-repo venv
        modified_cmd = cmd
        if language == "python":
            if cmd.startswith("python ") or cmd.startswith("python3 "):
                modified_cmd = f"{venv_python} " + cmd.split(" ", 1)[1]
            elif cmd.startswith("pytest"):
                modified_cmd = f"{venv_python} -m pytest" + cmd[6:]

        start_time = datetime.now()
        try:
            result = run_sandboxed(
                modified_cmd,
                cwd=clone_dir,
                timeout=test_timeout,
            )

            duration = (datetime.now() - start_time).total_seconds()
            output = result.stdout + result.stderr

            # Try structured JSON report first
            structured = _parse_json_report(clone_dir)
            if structured:
                cmd_passed = structured["passed"]
                cmd_failed = structured["failed"]
                cmd_total = structured["total"]
                status = "passed" if cmd_failed == 0 else "failed"
                all_test_cases.extend(structured.get("test_cases", []))
            else:
                # Fall back to regex / LLM parsing of stdout
                parsed_counts = await _parse_test_output(output)
                if parsed_counts:
                    cmd_passed = parsed_counts["passed"]
                    cmd_failed = parsed_counts["failed"]
                    cmd_total = parsed_counts["total"]
                    status = "passed" if cmd_failed == 0 else "failed"
                else:
                    status = "passed" if result.returncode == 0 else "failed"
                    cmd_passed = 1 if status == "passed" else 0
                    cmd_failed = 1 if status == "failed" else 0
                    cmd_total = 1

            total_passed += cmd_passed
            total_failed += cmd_failed
            total_tests += cmd_total

            command_results.append({
                "name": cmd,
                "status": status,
                "duration": duration,
                "output": output,
            })

            if progress_callback:
                await progress_callback(
                    f"Test {idx + 1}: {cmd_passed} passed, {cmd_failed} failed"
                )

        except subprocess.TimeoutExpired:
            command_results.append({
                "name": cmd,
                "status": "failed",
                "duration": float(test_timeout),
                "output": f"Test timed out after {test_timeout}s",
            })
            total_failed += 1
            total_tests += 1
            if progress_callback:
                await progress_callback(f"Test {idx + 1} timed out after {test_timeout}s")

        except Exception as e:
            command_results.append({
                "name": cmd,
                "status": "failed",
                "duration": 0.0,
                "output": str(e),
            })
            total_failed += 1
            total_tests += 1
            if progress_callback:
                await progress_callback(f"Test {idx + 1} error: {str(e)}")

    score = int((total_passed / total_tests) * 100) if total_tests > 0 else 0

    if progress_callback:
        await progress_callback(
            f"Tests completed. Score: {score}/100 ({total_passed}/{total_tests} passed)"
        )

    # Merge command-level and individual test-case results for the report
    report_items = all_test_cases if all_test_cases else command_results

    test_report_path = clone_dir / "TEST_REPORT.md"
    await _generate_test_report(
        report_path=test_report_path,
        repo_name=clone_dir.name,
        total=total_tests,
        passed=total_passed,
        failed=total_failed,
        score=score,
        test_results=report_items,
    )

    if progress_callback:
        await progress_callback(f"Test report saved to {test_report_path}")

    return {
        "total": total_tests,
        "passed": total_passed,
        "failed": total_failed,
        "skipped": 0,
        "score": score,
        "details": command_results,
        "test_cases": all_test_cases,
        "report_path": str(test_report_path),
    }


# ---------------------------------------------------------------------------
# Resource lifecycle
# ---------------------------------------------------------------------------

def list_repos() -> List[Dict[str, Any]]:
    """
    List all cloned repositories with disk usage and last-modified time.

    Returns:
        List of dicts with repo_name, clone_path, size_mb, last_accessed, has_report
    """
    repos_dir = get_repos_dir()
    repos = []

    for repo_dir in sorted(repos_dir.iterdir()):
        if not repo_dir.is_dir():
            continue

        # Calculate total directory size
        total_bytes = sum(
            f.stat().st_size
            for f in repo_dir.rglob("*")
            if f.is_file()
        )

        # Get last modification time
        try:
            mtime = repo_dir.stat().st_mtime
            last_accessed = datetime.fromtimestamp(mtime).isoformat()
        except Exception:
            last_accessed = None

        repos.append({
            "repo_name": repo_dir.name,
            "clone_path": str(repo_dir),
            "size_mb": round(total_bytes / (1024 * 1024), 2),
            "last_accessed": last_accessed,
            "has_overview": (repo_dir / "REPO_OVERVIEW.md").exists(),
            "has_report": (repo_dir / "TEST_REPORT.md").exists(),
            "has_test_config": (repo_dir / "test_config.json").exists(),
        })

    return repos


def delete_repo(repo_name: str) -> Dict[str, Any]:
    """
    Delete a cloned repository and all associated files.

    Returns:
        Dict with status and freed_mb
    """
    repos_dir = get_repos_dir()
    repo_dir = repos_dir / repo_name

    if not repo_dir.exists():
        raise FileNotFoundError(f"Repository '{repo_name}' not found")

    # Measure size before deleting
    total_bytes = sum(
        f.stat().st_size for f in repo_dir.rglob("*") if f.is_file()
    )
    freed_mb = round(total_bytes / (1024 * 1024), 2)

    shutil.rmtree(repo_dir)

    return {
        "status": "deleted",
        "repo_name": repo_name,
        "freed_mb": freed_mb,
    }
