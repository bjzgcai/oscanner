"""
Main test execution entry point.
"""

import asyncio
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from repos_runner.services.sandbox import run_sandboxed

from .venv import ensure_repo_venv
from .detection import (
    _detect_frameworks_statically,
    _load_test_config,
    _save_test_config,
    _detect_commands_via_llm,
)
from .parsing import _parse_json_report, _parse_test_output
from .coverage import _extract_features_from_tag_message, _check_feature_coverage
from .report import _generate_test_report


# ─────────────────────────────────────────────────────────────────────────────
# Generic test-file discovery
# ─────────────────────────────────────────────────────────────────────────────

# Per-language: which file suffixes to scan, which names are tests, which dirs skip
_LANG_DISCOVERY: Dict[str, Dict] = {
    "python": {
        "suffixes": (".py",),
        "is_test": lambda name: name.startswith("test_") or name.endswith("_test.py"),
        "skip_dirs": {".venv", "venv", "__pycache__", ".git", ".tox", ".eggs", "dist"},
    },
    "node": {
        # JS / TS / JSX / TSX
        "suffixes": (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"),
        "is_test": lambda name: any(
            name.endswith(s)
            for s in (
                ".test.js", ".spec.js",
                ".test.ts", ".spec.ts",
                ".test.jsx", ".spec.jsx",
                ".test.tsx", ".spec.tsx",
                ".test.mjs", ".spec.mjs",
            )
        ),
        # also collect any file inside an __tests__ dir
        "extra_dir": "__tests__",
        "skip_dirs": {"node_modules", ".git", "dist", "build", "coverage", ".next", ".nuxt", ".turbo"},
    },
    "java": {
        "suffixes": (".java",),
        "is_test": lambda name: (
            name.endswith("Test.java") or name.endswith("Tests.java")
            or name.endswith("IT.java") or name.startswith("Test")
        ),
        "skip_dirs": {".git", "build", "target", ".gradle", "out"},
    },
    "ruby": {
        "suffixes": (".rb",),
        "is_test": lambda name: name.endswith("_spec.rb") or name.endswith("_test.rb"),
        "skip_dirs": {".git", "vendor", ".bundle", "tmp"},
    },
    "php": {
        "suffixes": (".php",),
        "is_test": lambda name: name.endswith("Test.php") or name.startswith("Test"),
        "skip_dirs": {".git", "vendor", "node_modules"},
    },
    "go": {
        "suffixes": (".go",),
        "is_test": lambda name: name.endswith("_test.go"),
        "skip_dirs": {".git", "vendor"},
    },
    "rust": {
        # Rust tests live inline; cargo test handles everything — no path override needed
        "suffixes": (".rs",),
        "is_test": lambda name: False,
        "skip_dirs": {".git", "target"},
    },
    "dotnet": {
        "suffixes": (".cs",),
        "is_test": lambda name: name.endswith("Tests.cs") or name.endswith("Test.cs"),
        "skip_dirs": {".git", "bin", "obj"},
    },
    "swift": {
        "suffixes": (".swift",),
        "is_test": lambda name: name.endswith("Tests.swift") or name.endswith("Test.swift"),
        "skip_dirs": {".git", ".build", "DerivedData"},
    },
    "elixir": {
        "suffixes": (".exs", ".ex"),
        "is_test": lambda name: name.endswith("_test.exs"),
        "skip_dirs": {".git", "_build", "deps"},
    },
    "kotlin": {
        "suffixes": (".kt",),
        "is_test": lambda name: name.endswith("Test.kt") or name.endswith("Tests.kt"),
        "skip_dirs": {".git", "build", "target", ".gradle", "out"},
    },
}


def _common_test_dir(test_files: List[str]) -> str:
    """Return the common ancestor directory for a list of file paths, or '.' if rooted."""
    if not test_files:
        return "."
    parents = [str(Path(f).parent) for f in test_files]
    if len(parents) == 1:
        return parents[0] if parents[0] != "." else "."
    try:
        common = os.path.commonpath(parents)
        return common if common else "."
    except Exception:
        return "."


def _find_test_files(clone_dir: Path, language: str) -> List[str]:
    """
    Recursively find test files for *language* inside *clone_dir*.
    Returns paths relative to clone_dir.
    """
    spec = _LANG_DISCOVERY.get(language)
    if spec is None:
        return []

    skip_dirs: set = spec["skip_dirs"]
    is_test = spec["is_test"]
    suffixes: tuple = spec["suffixes"]
    extra_dir: str = spec.get("extra_dir", "")

    found: List[str] = []
    for p in clone_dir.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.parts[len(clone_dir.parts):]
        # Skip excluded directories anywhere in the relative path
        if any(
            part in skip_dirs
            or part.startswith(".venv")  # .venv_<hash> per-repo venvs
            or (part.startswith(".") and part != ".")
            for part in rel_parts
        ):
            continue
        if p.suffix not in suffixes:
            continue
        if is_test(p.name) or (extra_dir and extra_dir in rel_parts):
            found.append(str(p.relative_to(clone_dir)))

    return found


def _detect_node_framework(clone_dir: Path) -> str:
    """Return 'jest', 'vitest', or 'mocha' by inspecting package.json."""
    pkg = clone_dir / "package.json"
    if pkg.exists():
        try:
            import json as _json
            data = _json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
            all_deps: Dict[str, str] = {}
            all_deps.update(data.get("dependencies", {}))
            all_deps.update(data.get("devDependencies", {}))
            scripts_text = str(data.get("scripts", {}))
            deps_text = str(all_deps)
            combined = deps_text + scripts_text
            if "vitest" in combined:
                return "vitest"
            if "mocha" in combined:
                return "mocha"
            if "jest" in combined:
                return "jest"
        except Exception:
            pass
    return "jest"


def _build_discovered_command(clone_dir: Path, language: str, test_files: List[str]) -> Optional[str]:
    """
    Build the best single test command for *language* given *test_files*.
    Returns None for languages whose runners auto-discover (Go, Rust, Java Maven/Gradle, etc.)
    so that the existing static-detected command is kept unchanged.
    """
    if not test_files:
        return None

    test_dir = _common_test_dir(test_files)

    if language == "python":
        paths_arg = test_dir if test_dir not in (".", "") else " ".join(test_files[:10])
        return f"pytest {paths_arg} --json-report --json-report-file=.test_report.json -v || true"

    if language == "node":
        framework = _detect_node_framework(clone_dir)
        dir_arg = "" if test_dir in (".", "") else f" {test_dir}"
        if framework == "vitest":
            return f"npx vitest run{dir_arg} --reporter=json > .test_report.json || true"
        if framework == "mocha":
            # Mocha takes glob / file list
            files_arg = " ".join(f'"{f}"' for f in test_files[:20])
            return f"npx mocha {files_arg} --reporter json > .test_report.json || true"
        # Jest (default)
        return f"npx jest{dir_arg} --json --outputFile=.test_report.json || true"

    if language == "ruby":
        dir_arg = f" {test_dir}" if test_dir not in (".", "") else ""
        return (
            f"bundle exec rspec{dir_arg} --format json --out .test_report.json || "
            "bundle exec rake test 2>&1 | tee .test_report.txt || true"
        )

    if language == "php":
        dir_arg = f" {test_dir}" if test_dir not in (".", "") else ""
        return f"vendor/bin/phpunit{dir_arg} --log-junit .test_report.xml 2>&1 | tee .test_report.txt || true"

    if language == "dotnet":
        # dotnet test discovers automatically; no path needed
        return None

    if language in ("go", "rust", "java", "swift", "elixir", "kotlin"):
        # These runners handle full recursive discovery on their own
        return None

    return None


async def run_tests(
    clone_path: str,
    overview_path: str,
    progress_callback=None,
    setup_timeout: int = 120,
    test_timeout: int = 600,
    tag_message: Optional[str] = None,
    tag: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Identify and run tests based on REPO_OVERVIEW.md.

    Args:
        clone_path: Path to the cloned repository
        overview_path: Path to REPO_OVERVIEW.md
        progress_callback: Optional async callback for progress updates
        setup_timeout: Seconds allowed per setup command (default 120)
        test_timeout: Seconds allowed per test command (default 600)
        tag_message: Optional tag annotation message; when provided the score is
                     weighted by feature coverage (features described in the message
                     that are not exercised by the test suite reduce the max score).

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

    # Override test commands with recursively-discovered paths.
    # Fixes LLM-generated commands that hard-code wrong relative paths
    # (e.g. `tests/unit` when tests are actually at `zhugecai/tests/unit/`).
    # Applies to Python, Node/JS/TS, Ruby, PHP; skips languages whose runners
    # auto-discover (Go, Rust, Java, Swift, etc.).
    # When language is unknown (e.g. REPO_OVERVIEW.md was empty), scan all languages.
    language = test_info.get("language", "")
    found_test_files = _find_test_files(clone_dir, language)
    if not found_test_files and language in ("unknown", ""):
        for candidate in ("python", "node", "ruby", "php", "go", "rust", "java", "dotnet", "elixir", "kotlin", "swift"):
            files = _find_test_files(clone_dir, candidate)
            if files:
                language = candidate
                found_test_files = files
                if progress_callback:
                    await progress_callback(
                        f"Language was unknown; auto-detected '{language}' from test files"
                    )
                break
    if found_test_files:
        discovered_cmd = _build_discovered_command(clone_dir, language, found_test_files)
        if discovered_cmd:
            if progress_callback:
                await progress_callback(
                    f"Found {len(found_test_files)} {language} test file(s) recursively; "
                    f"using: {discovered_cmd}"
                )
            test_info = dict(test_info)
            test_info["language"] = language
            test_info["test_commands"] = [discovered_cmd]
            # Add default Python setup if none exist
            if language == "python" and not test_info.get("setup_commands"):
                test_info["setup_commands"] = [
                    "pip install -r requirements.txt || true",
                    "pip install pytest pytest-json-report",
                ]
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

        _safe_tag = tag.replace("/", "_").replace("\\", "_") if tag else None
        test_report_path = clone_dir / (f"TEST_REPORT_{_safe_tag}.md" if _safe_tag else "TEST_REPORT.md")
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

    raw_pass_rate = (total_passed / total_tests) if total_tests > 0 else 0

    # -- Feature coverage adjustment (when tag_message is provided) --
    feature_coverage: Optional[Dict[str, Any]] = None
    coverage_ratio = 1.0

    if tag_message and tag_message.strip():
        if progress_callback:
            await progress_callback("Analyzing tag message for required features...")
        features = await _extract_features_from_tag_message(tag_message)
        if features:
            if progress_callback:
                await progress_callback(
                    f"Required features ({len(features)}): {', '.join(features)}"
                )
            if progress_callback:
                await progress_callback("Checking feature coverage in test files...")
            feature_coverage = await _check_feature_coverage(clone_dir, features)
            coverage_ratio = feature_coverage["coverage_ratio"]
            covered = feature_coverage["covered"]
            not_covered = feature_coverage["not_covered"]
            if progress_callback:
                await progress_callback(
                    f"Feature coverage: {len(covered)}/{len(features)} features covered "
                    f"({coverage_ratio * 100:.0f}%)"
                )
            if not_covered and progress_callback:
                await progress_callback(f"Missing feature tests: {', '.join(not_covered)}")
        else:
            # Tag message present but no testable features could be extracted → score is 0
            coverage_ratio = 0.0
            if progress_callback:
                await progress_callback(
                    "No testable features could be extracted from the tag message — score set to 0"
                )

    score = int(raw_pass_rate * coverage_ratio * 100)

    if progress_callback:
        if feature_coverage:
            await progress_callback(
                f"Tests completed. Score: {score}/100 "
                f"(pass_rate={raw_pass_rate * 100:.1f}% × "
                f"feature_coverage={coverage_ratio * 100:.0f}%)"
            )
        else:
            await progress_callback(
                f"Tests completed. Score: {score}/100 ({total_passed}/{total_tests} passed)"
            )

    # Merge command-level and individual test-case results for the report
    report_items = all_test_cases if all_test_cases else command_results

    _safe_tag = tag.replace("/", "_").replace("\\", "_") if tag else None
    test_report_path = clone_dir / (f"TEST_REPORT_{_safe_tag}.md" if _safe_tag else "TEST_REPORT.md")
    await _generate_test_report(
        report_path=test_report_path,
        repo_name=clone_dir.name,
        total=total_tests,
        passed=total_passed,
        failed=total_failed,
        score=score,
        test_results=report_items,
        feature_coverage=feature_coverage,
        tag_message=tag_message,
    )

    if progress_callback:
        await progress_callback(f"Test report saved to {test_report_path}")

    result: Dict[str, Any] = {
        "total": total_tests,
        "passed": total_passed,
        "failed": total_failed,
        "skipped": 0,
        "score": score,
        "details": command_results,
        "test_cases": all_test_cases,
        "report_path": str(test_report_path),
    }
    if feature_coverage:
        result["feature_coverage"] = feature_coverage
        result["tag_message"] = tag_message
    return result
