"""
Test framework detection (static-first, LLM fallback) and config caching.
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

from .llm import _default_requested_model, _message_text_content, _messages_create_with_fallback


# Maps a config-file key to (setup_commands, test_commands)
_FRAMEWORK_MAP: List[Dict[str, Any]] = [
    # Python
    {
        "files": ["pytest.ini", "setup.cfg", "pyproject.toml", "conftest.py"],
        "content_hints": {"pyproject.toml": ["pytest"], "setup.cfg": ["pytest"]},
        "setup": ["pip install -e .[test] || pip install -r requirements.txt || true",
                  "pip install pytest pytest-json-report"],
        "test": ["pytest --json-report --json-report-file=.test_report.json -v"],
        "language": "python",
    },
    {
        "files": ["requirements-test.txt", "requirements_test.txt"],
        "content_hints": {},
        "setup": ["pip install -r requirements-test.txt"],
        "test": ["pytest --json-report --json-report-file=.test_report.json -v"],
        "language": "python",
    },
    # Node / Jest
    {
        "files": ["jest.config.js", "jest.config.ts", "jest.config.mjs"],
        "content_hints": {},
        "setup": ["npm install"],
        "test": ["npx jest --json --outputFile=.test_report.json"],
        "language": "node",
    },
    {
        "files": ["package.json"],
        "content_hints": {"package.json": ["jest"]},
        "setup": ["npm install"],
        "test": ["npx jest --json --outputFile=.test_report.json"],
        "language": "node",
    },
    # Node / Vitest
    {
        "files": ["vitest.config.ts", "vitest.config.js"],
        "content_hints": {},
        "setup": ["npm install"],
        "test": ["npx vitest run --reporter=json > .test_report.json"],
        "language": "node",
    },
    {
        "files": ["package.json"],
        "content_hints": {"package.json": ["vitest"]},
        "setup": ["npm install"],
        "test": ["npx vitest run --reporter=json > .test_report.json"],
        "language": "node",
    },
    # Node / Mocha
    {
        "files": [".mocharc.js", ".mocharc.yml", ".mocharc.json"],
        "content_hints": {},
        "setup": ["npm install"],
        "test": ["npx mocha --reporter json > .test_report.json"],
        "language": "node",
    },
    # Go
    {
        "files": ["go.mod"],
        "content_hints": {},
        "setup": ["go mod download"],
        "test": ["go test ./... -v -json > .test_report.json"],
        "language": "go",
    },
    # Rust
    {
        "files": ["Cargo.toml"],
        "content_hints": {},
        "setup": [],
        "test": ["cargo test -- --format json 2>&1 > .test_report.json || cargo test 2>&1 | tee .test_report.txt"],
        "language": "rust",
    },
    # Maven (Java)
    {
        "files": ["pom.xml"],
        "content_hints": {},
        "setup": [],
        "test": ["mvn test -q 2>&1 | tee .test_report.txt"],
        "language": "java",
    },
    # Gradle (Java/Kotlin)
    {
        "files": ["build.gradle", "build.gradle.kts"],
        "content_hints": {},
        "setup": [],
        "test": ["./gradlew test 2>&1 | tee .test_report.txt"],
        "language": "java",
    },
    # Ruby
    {
        "files": ["Gemfile"],
        "content_hints": {},
        "setup": ["bundle install"],
        "test": ["bundle exec rspec --format json --out .test_report.json || bundle exec rake test 2>&1 | tee .test_report.txt"],
        "language": "ruby",
    },
    # Dotnet
    {
        "files": [],
        "glob": "**/*.csproj",
        "content_hints": {},
        "setup": ["dotnet restore"],
        "test": ["dotnet test --logger trx 2>&1 | tee .test_report.txt"],
        "language": "dotnet",
    },
    # Elixir
    {
        "files": ["mix.exs"],
        "content_hints": {},
        "setup": ["mix deps.get"],
        "test": ["mix test --formatter ExUnit.CLIFormatter 2>&1 | tee .test_report.txt"],
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
        model=_default_requested_model(),
        require_text=True,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = _message_text_content(message)
    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {"test_commands": [], "setup_commands": [], "language": "unknown"}
