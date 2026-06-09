"""
Repository exploration using opencode (with messages API fallback).
"""

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .llm import (
    _default_requested_model,
    _get_api_clients,
    _get_model_candidates,
    record_estimated_token_usage,
    record_llm_response_usage,
)

DEFAULT_OPENCODE_MODEL = "openrouter/deepseek/deepseek-v4-pro"


def _overview_filename(tag: Optional[str]) -> str:
    """Return the REPO_OVERVIEW filename for the given tag (or default)."""
    if tag:
        safe_tag = tag.replace("/", "_").replace("\\", "_")
        return f"REPO_OVERVIEW_{safe_tag}.md"
    return "REPO_OVERVIEW.md"


def _opencode_timeout_seconds() -> int:
    raw_value = os.getenv("REPOS_RUNNER_OPENCODE_TIMEOUT", "600").strip()
    try:
        timeout = int(raw_value)
    except ValueError:
        return 600
    return max(timeout, 1)


def _opencode_requested_model() -> str:
    for key in ("REPOS_RUNNER_OPENCODE_MODEL", "OPENCODE_MODEL"):
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()
    return DEFAULT_OPENCODE_MODEL


def _opencode_model_requires_openrouter_key(model: str) -> bool:
    return (model or "").strip().startswith("openrouter/")


def _project_env_fallback_paths() -> list[Path]:
    backend_dir = Path(__file__).resolve().parents[3]
    return [
        backend_dir / "repos_runner" / ".env",
        backend_dir / "repos_runner" / ".env.local",
        backend_dir / "evaluator" / ".env",
        backend_dir / "evaluator" / ".env.local",
    ]


def _read_env_file_value(path: Path, key: str) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return ""


def _configured_openrouter_key() -> str:
    for key in ("OPEN_ROUTER_KEY", "OPENROUTER_API_KEY"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    for path in _project_env_fallback_paths():
        value = _read_env_file_value(path, "OPEN_ROUTER_KEY")
        if value:
            return value
    return ""


def _build_opencode_env() -> dict[str, str]:
    env = {**os.environ, "NO_COLOR": "1"}
    openrouter_key = _configured_openrouter_key()
    if openrouter_key and not env.get("OPENROUTER_API_KEY", "").strip():
        env["OPEN_ROUTER_KEY"] = openrouter_key
        env["OPENROUTER_API_KEY"] = openrouter_key
    return env


def _build_overview_prompt(
    repo_name: str,
    overview_filename: str,
    tag_message: Optional[str] = None,
) -> str:
    tag_section = (
        "\n\nThe repository is tagged with the following target features/requirements:\n"
        f"{tag_message}\n"
        "Pay attention to these when identifying test coverage and setup."
        if tag_message else ""
    )
    tag_output_section = (
        "## Tag Message\n"
        f"{tag_message}\n\n"
        if tag_message else ""
    )
    return (
        "You are analyzing a software repository to understand how to run its tests. "
        "Explore the repository files, README, package/config files, and existing test files. "
        "Do not modify files. Return only the final markdown content, with no commentary "
        "before or after it."
        f"{tag_section}\n\n"
        f"The markdown will be saved as {overview_filename}. Use this exact structure:\n\n"
        f"# {repo_name}\n\n"
        f"{tag_output_section}"
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
        "Be concise. Only include what is needed to run tests."
    )


def _extract_markdown_from_opencode_output(output: str) -> str:
    content = (output or "").strip()
    if not content:
        return ""

    heading_index = content.find("# ")
    if heading_index >= 0:
        return content[heading_index:].strip()
    return content


async def _explore_via_opencode(
    clone_path: str,
    progress_callback=None,
    tag_message: Optional[str] = None,
    tag: Optional[str] = None,
) -> str:
    clone_dir = Path(clone_path)
    overview_filename = _overview_filename(tag)
    overview_path = clone_dir / overview_filename

    if not shutil.which("opencode"):
        raise FileNotFoundError("opencode CLI not available")

    if progress_callback:
        await progress_callback("Starting repository exploration with opencode...")

    prompt = _build_overview_prompt(clone_dir.name, overview_filename, tag_message)
    command = ["opencode", "run", "--agent", "plan", "--dir", str(clone_dir)]
    requested_model = _opencode_requested_model()
    if _opencode_model_requires_openrouter_key(requested_model) and not _configured_openrouter_key():
        raise RuntimeError("OPEN_ROUTER_KEY is empty; cannot use OpenRouter opencode model")
    if requested_model:
        command.extend(["--model", requested_model])
    command.append(prompt)

    if progress_callback:
        await progress_callback("opencode is exploring the repository structure...")

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(clone_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_build_opencode_env(),
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=_opencode_timeout_seconds(),
        )
    except asyncio.TimeoutError as exc:
        kill = getattr(process, "kill", None)
        if callable(kill):
            kill()
        raise TimeoutError("opencode repository exploration timed out") from exc

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

    if process.returncode != 0:
        detail = stderr or stdout.strip() or f"exit code {process.returncode}"
        raise RuntimeError(f"opencode repository exploration failed: {detail}")

    overview_content = _extract_markdown_from_opencode_output(stdout)
    if not overview_content:
        raise RuntimeError("opencode did not return overview content")

    if progress_callback:
        await progress_callback(f"Writing {overview_filename}...")

    overview_path.write_text(overview_content, encoding="utf-8")
    record_estimated_token_usage(prompt, overview_content)

    if progress_callback:
        await progress_callback("Repository exploration completed!")

    return str(overview_path)


async def explore_repository(
    clone_path: str,
    progress_callback=None,
    tag_message: Optional[str] = None,
    tag: Optional[str] = None,
) -> str:
    """
    Explore repository and generate REPO_OVERVIEW_{tag}.md using opencode.

    Args:
        tag_message: Optional annotation describing target features to focus on.
        tag: Optional tag name used to version the output filename.

    Returns:
        Path to generated REPO_OVERVIEW_{tag}.md (or REPO_OVERVIEW.md if no tag)
    """
    try:
        return await _explore_via_opencode(clone_path, progress_callback, tag_message, tag)
    except FileNotFoundError:
        if progress_callback:
            await progress_callback("opencode CLI not available; falling back to messages API...")
        return await _explore_via_messages_api(clone_path, progress_callback, tag_message, tag)
    except Exception as e:
        if progress_callback:
            await progress_callback(f"opencode error ({e}); falling back to messages API...")
        return await _explore_via_messages_api(clone_path, progress_callback, tag_message, tag)


async def _explore_via_messages_api(
    clone_path: str,
    progress_callback=None,
    tag_message: Optional[str] = None,
    tag: Optional[str] = None,
) -> str:
    """Fallback: build context manually and call the configured messages API."""
    clone_dir = Path(clone_path)
    overview_path = clone_dir / _overview_filename(tag)

    if progress_callback:
        await progress_callback("Analyzing repository structure...")

    context = await _build_repo_context(clone_dir)

    if progress_callback:
        await progress_callback("Generating overview with AI...")

    tag_section = (
        f"\nThe repository is tagged with the following target features/requirements:\n{tag_message}\n"
        if tag_message else ""
    )

    prompt = f"""Analyze this repository and generate a concise REPO_OVERVIEW.md focused on testing:

1. Project name and type (1-2 sentences)
2. Test framework(s) used (if any)
3. Setup/installation commands needed to run tests
4. Test commands to execute
{tag_section}
Be extremely concise. Skip examples, features, and detailed documentation.

The generated REPO_OVERVIEW.md must start with:
# <repo_name>
{f'''
## Tag Message
{tag_message}
''' if tag_message else ''}
## Project Type
...

Repository context:
{context}

Generate the markdown content for REPO_OVERVIEW.md:"""

    async def _stream_once(client, model: str) -> str:
        content = ""
        last_progress_length = 0
        messages = [{"role": "user", "content": prompt}]
        final_message = None
        with client.messages.stream(
            model=model,
            max_tokens=1500,
            messages=messages,
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
            get_final_message = getattr(stream, "get_final_message", None)
            if callable(get_final_message):
                final_message = get_final_message()
        if not content.strip():
            raise RuntimeError("Response contained no final text blocks")
        record_llm_response_usage(final_message, messages=messages, content=content)
        return content

    clients = _get_api_clients()
    if not clients:
        raise ValueError("No API credential available. Set OPEN_ROUTER_KEY.")

    attempts = []
    requested_model = _default_requested_model()
    for provider_name, client in clients:
        for model in _get_model_candidates(provider_name, requested_model):
            attempts.append((provider_name, client, model))

    errors = []
    overview_content = None
    for idx, (provider_name, client, model) in enumerate(attempts):
        try:
            overview_content = await _stream_once(client, model)
            break
        except Exception as error:
            errors.append((provider_name, model, error))
            if progress_callback and idx < len(attempts) - 1:
                await progress_callback(
                    f"{provider_name} ({model}) failed, trying fallback..."
                )

    if overview_content is None:
        if len(errors) == 1:
            provider_name, model, error = errors[0]
            raise RuntimeError(f"{provider_name} ({model}) request failed ({error})") from error

        error_summary = "; ".join(
            f"{provider_name} ({model}) failed ({error})"
            for provider_name, model, error in errors
        )
        raise RuntimeError(f"All model attempts failed: {error_summary}") from errors[-1][2]

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
