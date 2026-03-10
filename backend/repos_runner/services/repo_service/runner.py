"""
Main test execution entry point.
"""

import asyncio
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


async def run_tests(
    clone_path: str,
    overview_path: str,
    progress_callback=None,
    setup_timeout: int = 120,
    test_timeout: int = 300,
    tag_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Identify and run tests based on REPO_OVERVIEW.md.

    Args:
        clone_path: Path to the cloned repository
        overview_path: Path to REPO_OVERVIEW.md
        progress_callback: Optional async callback for progress updates
        setup_timeout: Seconds allowed per setup command (default 120)
        test_timeout: Seconds allowed per test command (default 300)
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

    test_report_path = clone_dir / "TEST_REPORT.md"
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
