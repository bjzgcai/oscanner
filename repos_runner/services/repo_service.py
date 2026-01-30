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

        # Use streaming API
        overview_content = ""
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
                # Send progress every ~100 characters
                if len(overview_content) % 100 < len(text):
                    if progress_callback:
                        await progress_callback(f"Generated {len(overview_content)} characters...")

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


async def run_tests(clone_path: str, overview_path: str, progress_callback=None) -> Dict[str, Any]:
    """
    Identify and run tests based on REPO_OVERVIEW.md.

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
        for cmd in test_info["setup_commands"]:
            if progress_callback:
                await progress_callback(f"Running setup: {cmd}")
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=clone_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            except Exception as e:
                if progress_callback:
                    await progress_callback(f"Setup failed: {str(e)}")

    # Run test commands
    test_results = []
    total_tests = len(test_info.get("test_commands", []))

    if total_tests == 0:
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

    passed = 0
    failed = 0

    for idx, cmd in enumerate(test_info.get("test_commands", [])):
        if progress_callback:
            await progress_callback(f"Running test {idx + 1}/{total_tests}: {cmd}")

        start_time = datetime.now()
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=clone_dir,
                capture_output=True,
                text=True,
                timeout=300
            )

            duration = (datetime.now() - start_time).total_seconds()

            status = "passed" if result.returncode == 0 else "failed"
            if status == "passed":
                passed += 1
            else:
                failed += 1

            test_results.append({
                "name": cmd,
                "status": status,
                "duration": duration,
                "output": result.stdout + result.stderr
            })

            if progress_callback:
                await progress_callback(f"Test {idx + 1} {status}")

        except subprocess.TimeoutExpired:
            test_results.append({
                "name": cmd,
                "status": "failed",
                "duration": 300.0,
                "output": "Test timed out after 5 minutes"
            })
            failed += 1

            if progress_callback:
                await progress_callback(f"Test {idx + 1} timed out")

        except Exception as e:
            test_results.append({
                "name": cmd,
                "status": "failed",
                "duration": 0.0,
                "output": str(e)
            })
            failed += 1

            if progress_callback:
                await progress_callback(f"Test {idx + 1} error: {str(e)}")

    # Calculate score
    score = int((passed / total_tests) * 100) if total_tests > 0 else 0

    if progress_callback:
        await progress_callback(f"Tests completed. Score: {score}/100")

    return {
        "total": total_tests,
        "passed": passed,
        "failed": failed,
        "skipped": 0,
        "score": score,
        "details": test_results
    }
