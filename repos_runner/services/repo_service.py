"""
Repository services for cloning, exploring, and testing
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import git
import json
import asyncio
from datetime import datetime


def get_repos_dir() -> Path:
    """Get the directory for storing cloned repositories"""
    base_dir = Path.home() / ".local" / "share" / "oscanner" / "repos"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_repo_venv_dir(clone_path: str) -> Path:
    """Get the virtual environment directory for a specific repository"""
    clone_dir = Path(clone_path)
    venv_dir = clone_dir / ".venv"
    return venv_dir


def ensure_repo_venv(clone_path: str) -> Path:
    """
    Ensure per-repository virtual environment exists for running tests.
    Each repository gets its own isolated environment for dependency isolation.

    Args:
        clone_path: Path to the cloned repository

    Returns:
        Path to the virtual environment's python executable
    """
    venv_dir = get_repo_venv_dir(clone_path)

    if not venv_dir.exists():
        # Create virtual environment
        import venv
        venv.create(venv_dir, with_pip=True)

    # Return path to python executable
    if os.name == 'nt':  # Windows
        python_path = venv_dir / "Scripts" / "python.exe"
    else:  # Unix/Linux/Mac
        python_path = venv_dir / "bin" / "python"

    return python_path


def parse_repo_url(repo_url: str) -> Tuple[str, str, str]:
    """
    Parse repository URL to extract platform, owner, and repo name.

    Returns:
        Tuple of (platform, owner, repo_name)
    """
    # Remove trailing .git if present
    repo_url = repo_url.rstrip("/").replace(".git", "")

    # Handle GitHub URLs
    if "github.com" in repo_url:
        parts = repo_url.split("github.com/")[-1].split("/")
        return "github", parts[0], parts[1]

    # Handle Gitee URLs
    elif "gitee.com" in repo_url:
        parts = repo_url.split("gitee.com/")[-1].split("/")
        return "gitee", parts[0], parts[1]

    else:
        raise ValueError(f"Unsupported repository URL: {repo_url}")


async def clone_repository(repo_url: str) -> Dict[str, Any]:
    """
    Clone a repository with depth 1 (shallow clone).

    Args:
        repo_url: URL of the repository to clone

    Returns:
        Dictionary containing repo metadata
    """
    platform, owner, repo_name = parse_repo_url(repo_url)

    # Determine clone path
    repos_dir = get_repos_dir()
    clone_path = repos_dir / repo_name

    # Remove existing directory if it exists
    if clone_path.exists():
        shutil.rmtree(clone_path)

    # Clone the repository (shallow clone)
    try:
        repo = git.Repo.clone_from(
            repo_url,
            clone_path,
            depth=1,
            single_branch=True
        )

        # Get repository metadata
        default_branch = repo.active_branch.name
        latest_commit = repo.head.commit
        latest_commit_id = latest_commit.hexsha

        return {
            "repo_name": repo_name,
            "default_branch": default_branch,
            "latest_commit_id": latest_commit_id,
            "clone_path": str(clone_path),
            "platform": platform,
            "owner": owner
        }

    except Exception as e:
        raise Exception(f"Failed to clone repository: {str(e)}")


async def explore_repository(clone_path: str, progress_callback=None) -> str:
    """
    Explore repository and generate REPO_OVERVIEW.md using Claude Code SDK.

    Args:
        clone_path: Path to the cloned repository
        progress_callback: Optional callback for progress updates

    Returns:
        Path to generated REPO_OVERVIEW.md
    """
    clone_dir = Path(clone_path)
    overview_path = clone_dir / "REPO_OVERVIEW.md"

    if progress_callback:
        await progress_callback("Starting repository exploration...")

    try:
        # Import Claude Agent SDK
        from anthropic import Anthropic

        # Get API key from environment (check multiple possible variable names)
        api_key = (
            os.getenv("ANTHROPIC_API_KEY") or
            os.getenv("OSCANNER_LLM_API_KEY") or
            os.getenv("OPENAI_API_KEY") or
            os.getenv("ANTHROPIC_AUTH_TOKEN")
        )
        if not api_key:
            raise ValueError("API key not found. Set one of: ANTHROPIC_API_KEY, OSCANNER_LLM_API_KEY, OPENAI_API_KEY, or ANTHROPIC_AUTH_TOKEN")

        # Get base URL if provided (for custom API endpoints)
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = Anthropic(**client_kwargs)

        if progress_callback:
            await progress_callback("Analyzing repository structure...")

        # Build context from repository
        context = await _build_repo_context(clone_dir, progress_callback)

        if progress_callback:
            await progress_callback("Generating overview with Claude...")

        # Generate overview using Claude with streaming
        prompt = f"""Analyze this repository and generate a comprehensive REPO_OVERVIEW.md that includes:

1. A brief summary of the repository's purpose and functionality
2. An overview of the main components and structure of the codebase
3. Key features and functionalities provided by the repository
4. Any important setup or installation instructions
5. Examples of how to use the features of the repository

Repository context:
{context}

Generate the markdown content for REPO_OVERVIEW.md:"""

        # Use streaming API with real-time progress updates
        overview_content = ""
        last_progress_length = 0
        progress_interval = 200  # Send update every 200 characters

        with client.messages.stream(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        ) as stream:
            for text in stream.text_stream:
                overview_content += text
                # Send progress updates at regular intervals
                current_length = len(overview_content)
                if current_length - last_progress_length >= progress_interval:
                    if progress_callback:
                        await progress_callback(f"Generated {current_length} characters...")
                    last_progress_length = current_length

        if progress_callback:
            await progress_callback("Writing REPO_OVERVIEW.md...")

        # Write to file
        overview_path.write_text(overview_content)

        if progress_callback:
            await progress_callback("Repository exploration completed!")

        return str(overview_path)

    except Exception as e:
        if progress_callback:
            await progress_callback(f"Error: {str(e)}")
        raise Exception(f"Failed to explore repository: {str(e)}")


async def _build_repo_context(repo_path: Path, progress_callback=None) -> str:
    """Build context about the repository for Claude to analyze"""
    context_parts = []

    # Get README if exists
    readme_files = ["README.md", "README.txt", "README"]
    for readme in readme_files:
        readme_path = repo_path / readme
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8", errors="ignore")
                context_parts.append(f"## README:\n{content[:5000]}")
                break
            except Exception:
                pass

    # Get directory structure
    try:
        tree_output = subprocess.run(
            ["tree", "-L", "3", "-I", "node_modules|venv|.git|__pycache__|*.pyc", str(repo_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if tree_output.returncode == 0:
            context_parts.append(f"## Directory Structure:\n{tree_output.stdout[:3000]}")
    except Exception:
        # Fallback to simple listing
        try:
            files = []
            for item in repo_path.rglob("*"):
                if any(skip in str(item) for skip in [".git", "node_modules", "venv", "__pycache__"]):
                    continue
                rel_path = item.relative_to(repo_path)
                if len(files) < 100:
                    files.append(str(rel_path))
            context_parts.append(f"## Files:\n" + "\n".join(files))
        except Exception:
            pass

    # Get package.json or requirements.txt or similar
    config_files = ["package.json", "requirements.txt", "setup.py", "pyproject.toml", "Cargo.toml", "go.mod"]
    for config_file in config_files:
        config_path = repo_path / config_file
        if config_path.exists():
            try:
                content = config_path.read_text(encoding="utf-8", errors="ignore")
                context_parts.append(f"## {config_file}:\n{content[:2000]}")
            except Exception:
                pass

    return "\n\n".join(context_parts)


async def detect_test_commands(overview_path: str) -> Dict[str, Any]:
    """
    Detect test commands from REPO_OVERVIEW.md without running them.

    Args:
        overview_path: Path to REPO_OVERVIEW.md

    Returns:
        Dictionary containing test_commands and setup_commands
    """
    overview_file = Path(overview_path)

    if not overview_file.exists():
        raise FileNotFoundError(f"REPO_OVERVIEW.md not found at {overview_path}")

    overview_content = overview_file.read_text()

    try:
        from anthropic import Anthropic

        api_key = (
            os.getenv("ANTHROPIC_API_KEY") or
            os.getenv("OSCANNER_LLM_API_KEY") or
            os.getenv("OPENAI_API_KEY") or
            os.getenv("ANTHROPIC_AUTH_TOKEN")
        )
        if not api_key:
            raise ValueError("API key not found. Set one of: ANTHROPIC_API_KEY, OSCANNER_LLM_API_KEY, OPENAI_API_KEY, or ANTHROPIC_AUTH_TOKEN")

        # Get base URL if provided (for custom API endpoints)
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = Anthropic(**client_kwargs)

        prompt = f"""Based on this REPO_OVERVIEW.md, identify the command(s) to run tests for this repository.

{overview_content}

Return a JSON object with the following structure:
{{
  "test_commands": ["command1", "command2"],
  "setup_commands": ["optional setup command"]
}}

If no tests are found, return {{"test_commands": [], "setup_commands": []}}
"""

        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse response
        response_text = message.content[0].text
        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            test_info = json.loads(json_match.group())
        else:
            test_info = {"test_commands": [], "setup_commands": []}

        return test_info

    except Exception as e:
        raise Exception(f"Failed to detect test commands: {str(e)}")


async def _generate_test_report(
    report_path: Path,
    repo_name: str,
    total: int,
    passed: int,
    failed: int,
    score: int,
    test_results: list
) -> None:
    """Generate TEST_REPORT.md for analyzed repository"""
    from datetime import datetime

    # Calculate percentages
    pass_rate = (passed / total * 100) if total > 0 else 0
    fail_rate = (failed / total * 100) if total > 0 else 0

    # Determine grade
    if score >= 90:
        grade = "Excellent ⭐⭐⭐⭐⭐"
    elif score >= 70:
        grade = "Good ⭐⭐⭐⭐"
    elif score >= 50:
        grade = "Fair ⭐⭐⭐"
    else:
        grade = "Poor ⭐"

    # Build report content
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

    # Group results by status
    passed_tests = [t for t in test_results if t["status"] == "passed"]
    failed_tests = [t for t in test_results if t["status"] == "failed"]

    # Passed tests
    if passed_tests:
        report += f"### ✅ Passed Tests ({len(passed_tests)})\n\n"
        for test in passed_tests:
            duration = test.get("duration", 0)
            report += f"- `{test['name']}` ({duration:.2f}s)\n"
        report += "\n"

    # Failed tests
    if failed_tests:
        report += f"### ❌ Failed Tests ({len(failed_tests)})\n\n"
        for test in failed_tests:
            duration = test.get("duration", 0)
            report += f"- `{test['name']}` ({duration:.2f}s)\n"
            # Include error output (truncated)
            output = test.get("output", "")
            if output:
                truncated_output = output[-500:] if len(output) > 500 else output
                report += f"  ```\n  {truncated_output}\n  ```\n"
        report += "\n"

    # Score breakdown
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

    if score < 70:
        report += """### Priority Actions
1. Fix all failing tests
2. Investigate root causes of failures
3. Add missing test coverage for critical paths
4. Re-run tests until score >= 70

"""

    if failed_tests:
        report += "### Failed Tests to Fix\n"
        for idx, test in enumerate(failed_tests[:5], 1):
            report += f"{idx}. `{test['name']}`\n"
        if len(failed_tests) > 5:
            report += f"\n...and {len(failed_tests) - 5} more\n"
        report += "\n"

    report += """## Next Steps

1. Review failed tests and fix underlying issues
2. Run tests again: `/api/runner/run-tests`
3. Aim for 70%+ pass rate (Good rating)
4. Target 90%+ pass rate (Excellent rating)

---

*Generated by [repos_runner](https://github.com/your-org/oscanner) - Automated repository testing service*
"""

    # Write report to file
    report_path.write_text(report)


def _parse_test_output_with_regex(output: str) -> Optional[Dict[str, int]]:
    """
    Try to parse test output using regex patterns for common formats.
    This is the fast path for well-known test frameworks.

    Returns:
        Dictionary with 'passed', 'failed', 'total' keys, or None if no match
    """
    import re

    # Jest format: "Tests:       9 failed, 9 passed, 18 total"
    jest_match = re.search(r'Tests:\s+(\d+)\s+failed,\s+(\d+)\s+passed,\s+(\d+)\s+total', output)
    if jest_match:
        return {
            'failed': int(jest_match.group(1)),
            'passed': int(jest_match.group(2)),
            'total': int(jest_match.group(3))
        }

    # Jest format (all passed): "Tests:       9 passed, 18 total"
    jest_passed_match = re.search(r'Tests:\s+(\d+)\s+passed,\s+(\d+)\s+total', output)
    if jest_passed_match:
        passed = int(jest_passed_match.group(1))
        total = int(jest_passed_match.group(2))
        return {
            'passed': passed,
            'failed': total - passed,
            'total': total
        }

    # Jest format (all failed): "Tests:       9 failed, 18 total"
    jest_failed_match = re.search(r'Tests:\s+(\d+)\s+failed,\s+(\d+)\s+total', output)
    if jest_failed_match:
        failed = int(jest_failed_match.group(1))
        total = int(jest_failed_match.group(2))
        return {
            'passed': total - failed,
            'failed': failed,
            'total': total
        }

    # pytest format: "====== 9 failed, 9 passed in 8.51s ======"
    pytest_match = re.search(r'=+\s*(\d+)\s+failed,\s+(\d+)\s+passed', output)
    if pytest_match:
        failed = int(pytest_match.group(1))
        passed = int(pytest_match.group(2))
        return {
            'failed': failed,
            'passed': passed,
            'total': failed + passed
        }

    # pytest format (all passed): "====== 9 passed in 8.51s ======"
    pytest_passed_match = re.search(r'=+\s*(\d+)\s+passed', output)
    if pytest_passed_match:
        passed = int(pytest_passed_match.group(1))
        return {
            'passed': passed,
            'failed': 0,
            'total': passed
        }

    # Go test format: "FAIL: 9 PASS: 9"
    go_match = re.search(r'FAIL:\s*(\d+).*PASS:\s*(\d+)', output)
    if go_match:
        failed = int(go_match.group(1))
        passed = int(go_match.group(2))
        return {
            'failed': failed,
            'passed': passed,
            'total': failed + passed
        }

    # No match found
    return None


async def _parse_test_output_with_llm(output: str) -> Optional[Dict[str, int]]:
    """
    Parse test output using LLM when regex patterns fail.
    This is the flexible fallback for unknown test frameworks.

    Returns:
        Dictionary with 'passed', 'failed', 'total' keys, or None if parsing fails
    """
    try:
        from anthropic import Anthropic

        api_key = (
            os.getenv("ANTHROPIC_API_KEY") or
            os.getenv("OSCANNER_LLM_API_KEY") or
            os.getenv("OPENAI_API_KEY") or
            os.getenv("ANTHROPIC_AUTH_TOKEN")
        )
        if not api_key:
            return None

        base_url = os.getenv("ANTHROPIC_BASE_URL")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = Anthropic(**client_kwargs)

        # Truncate output to avoid excessive token usage (keep last 2000 chars with summary)
        truncated_output = output[-2000:] if len(output) > 2000 else output

        prompt = f"""Parse this test output and extract the test results.

Test output (last 2000 characters):
```
{truncated_output}
```

Return ONLY a JSON object with this exact structure (no other text):
{{
  "passed": <number of passed tests>,
  "failed": <number of failed tests>,
  "total": <total number of tests>
}}

If you cannot determine the counts, return: {{"passed": 0, "failed": 0, "total": 0}}
"""

        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse response
        response_text = message.content[0].text.strip()
        # Extract JSON from response
        import re
        json_match = re.search(r'\{[^}]+\}', response_text)
        if json_match:
            result = json.loads(json_match.group())
            # Validate the result has required keys and reasonable values
            if all(k in result for k in ['passed', 'failed', 'total']):
                if result['total'] > 0 and result['passed'] + result['failed'] == result['total']:
                    return result

        return None

    except Exception as e:
        # Silently fail and return None - this is a best-effort fallback
        return None


async def _parse_test_output(output: str) -> Optional[Dict[str, int]]:
    """
    Parse test output to extract test counts.
    Uses regex for common formats, falls back to LLM for unknown formats.

    Returns:
        Dictionary with 'passed', 'failed', 'total' keys, or None if parsing fails
    """
    # Fast path: Try regex patterns first
    result = _parse_test_output_with_regex(output)
    if result:
        return result

    # Fallback: Use LLM for unknown formats
    result = await _parse_test_output_with_llm(output)
    return result


async def run_tests(clone_path: str, overview_path: str, progress_callback=None) -> Dict[str, Any]:
    """
    Identify and run tests based on REPO_OVERVIEW.md.
    Generates TEST_REPORT.md in the repository directory.

    Args:
        clone_path: Path to the cloned repository
        overview_path: Path to REPO_OVERVIEW.md
        progress_callback: Optional callback for progress updates

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

    # Use Claude to identify test commands
    try:
        from anthropic import Anthropic

        api_key = (
            os.getenv("ANTHROPIC_API_KEY") or
            os.getenv("OSCANNER_LLM_API_KEY") or
            os.getenv("OPENAI_API_KEY") or
            os.getenv("ANTHROPIC_AUTH_TOKEN")
        )
        if not api_key:
            raise ValueError("API key not found. Set one of: ANTHROPIC_API_KEY, OSCANNER_LLM_API_KEY, OPENAI_API_KEY, or ANTHROPIC_AUTH_TOKEN")

        # Get base URL if provided (for custom API endpoints)
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = Anthropic(**client_kwargs)

        prompt = f"""Based on this REPO_OVERVIEW.md, identify the command(s) to run tests for this repository.

{overview_content}

Return a JSON object with the following structure:
{{
  "test_commands": ["command1", "command2"],
  "setup_commands": ["optional setup command"]
}}

If no tests are found, return {{"test_commands": [], "setup_commands": []}}
"""

        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse response
        response_text = message.content[0].text
        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            test_info = json.loads(json_match.group())
        else:
            test_info = {"test_commands": [], "setup_commands": []}

    except Exception as e:
        if progress_callback:
            await progress_callback(f"Warning: Could not identify tests: {str(e)}")
        test_info = {"test_commands": [], "setup_commands": []}

    # Run setup commands if any
    if test_info.get("setup_commands"):
        # Ensure per-repository virtual environment exists
        venv_python = ensure_repo_venv(clone_path)

        for cmd in test_info["setup_commands"]:
            if progress_callback:
                await progress_callback(f"Running setup: {cmd}")

            # Modify command to use venv python for pip installs
            if cmd.startswith("pip install") or cmd.startswith("pip3 install"):
                # Replace pip with venv pip
                cmd = cmd.replace("pip install", f"{venv_python} -m pip install")
                cmd = cmd.replace("pip3 install", f"{venv_python} -m pip install")

            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=clone_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if progress_callback and result.returncode != 0:
                    await progress_callback(f"Setup warning: {result.stderr[:200]}")
            except Exception as e:
                if progress_callback:
                    await progress_callback(f"Setup failed: {str(e)}")

    # Run test commands
    test_results = []
    num_commands = len(test_info.get("test_commands", []))

    if num_commands == 0:
        if progress_callback:
            await progress_callback("No tests found in repository")
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "score": 0,
            "details": [],
            "message": "No tests found in repository"
        }

    # Accumulate actual test counts from parsed output
    total_passed = 0
    total_failed = 0
    total_tests = 0

    # Get per-repository venv python path for running tests
    venv_python = ensure_repo_venv(clone_path)

    for idx, cmd in enumerate(test_info.get("test_commands", [])):
        if progress_callback:
            await progress_callback(f"Running test {idx + 1}/{num_commands}: {cmd}")

        # Modify command to use venv python if it's a python/pytest command
        modified_cmd = cmd
        if cmd.startswith("python ") or cmd.startswith("python3 "):
            modified_cmd = cmd.replace("python ", f"{venv_python} ", 1)
            modified_cmd = modified_cmd.replace("python3 ", f"{venv_python} ", 1)
        elif cmd.startswith("pytest"):
            modified_cmd = f"{venv_python} -m pytest" + cmd[6:]

        start_time = datetime.now()
        try:
            result = subprocess.run(
                modified_cmd,
                shell=True,
                cwd=clone_dir,
                capture_output=True,
                text=True,
                timeout=300
            )

            duration = (datetime.now() - start_time).total_seconds()
            output = result.stdout + result.stderr

            # Try to parse test output to get actual test counts
            parsed_counts = await _parse_test_output(output)

            if parsed_counts:
                # Use parsed counts from test framework output
                cmd_passed = parsed_counts['passed']
                cmd_failed = parsed_counts['failed']
                cmd_total = parsed_counts['total']
                status = "passed" if cmd_failed == 0 else "failed"
            else:
                # Fallback: treat command as single test
                status = "passed" if result.returncode == 0 else "failed"
                cmd_passed = 1 if status == "passed" else 0
                cmd_failed = 1 if status == "failed" else 0
                cmd_total = 1

            total_passed += cmd_passed
            total_failed += cmd_failed
            total_tests += cmd_total

            test_results.append({
                "name": cmd,
                "status": status,
                "duration": duration,
                "output": output,
                "parsed_counts": parsed_counts
            })

            if progress_callback:
                if parsed_counts:
                    await progress_callback(f"Test {idx + 1}: {cmd_passed} passed, {cmd_failed} failed")
                else:
                    await progress_callback(f"Test {idx + 1} {status}")

        except subprocess.TimeoutExpired:
            test_results.append({
                "name": cmd,
                "status": "failed",
                "duration": 300.0,
                "output": "Test timed out after 5 minutes",
                "parsed_counts": None
            })
            total_failed += 1
            total_tests += 1

            if progress_callback:
                await progress_callback(f"Test {idx + 1} timed out")

        except Exception as e:
            test_results.append({
                "name": cmd,
                "status": "failed",
                "duration": 0.0,
                "output": str(e),
                "parsed_counts": None
            })
            total_failed += 1
            total_tests += 1

            if progress_callback:
                await progress_callback(f"Test {idx + 1} error: {str(e)}")

    # Calculate score based on actual test counts
    score = int((total_passed / total_tests) * 100) if total_tests > 0 else 0

    if progress_callback:
        await progress_callback(f"Tests completed. Score: {score}/100 ({total_passed}/{total_tests} passed)")

    # Generate TEST_REPORT.md in the repository directory
    test_report_path = clone_dir / "TEST_REPORT.md"
    await _generate_test_report(
        report_path=test_report_path,
        repo_name=clone_dir.name,
        total=total_tests,
        passed=total_passed,
        failed=total_failed,
        score=score,
        test_results=test_results
    )

    if progress_callback:
        await progress_callback(f"Test report saved to {test_report_path}")

    return {
        "total": total_tests,
        "passed": total_passed,
        "failed": total_failed,
        "skipped": 0,
        "score": score,
        "details": test_results,
        "report_path": str(test_report_path)
    }
