"""
Repository exploration using Claude Code SDK (with messages API fallback).
"""

import asyncio
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


def _overview_filename(tag: Optional[str]) -> str:
    """Return the REPO_OVERVIEW filename for the given tag (or default)."""
    if tag:
        safe_tag = tag.replace("/", "_").replace("\\", "_")
        return f"REPO_OVERVIEW_{safe_tag}.md"
    return "REPO_OVERVIEW.md"


async def explore_repository(
    clone_path: str,
    progress_callback=None,
    tag_message: Optional[str] = None,
    tag: Optional[str] = None,
) -> str:
    """
    Explore repository and generate REPO_OVERVIEW_{tag}.md using the Claude Code SDK.

    The SDK runs Claude as an agentic loop with shell-tool access so it can
    actually read files, list directories, and understand the project structure
    rather than just receiving a pre-built context string.

    Args:
        tag_message: Optional annotation describing target features to focus on.
        tag: Optional tag name used to version the output filename.

    Returns:
        Path to generated REPO_OVERVIEW_{tag}.md (or REPO_OVERVIEW.md if no tag)
    """
    clone_dir = Path(clone_path)
    overview_path = clone_dir / _overview_filename(tag)

    if progress_callback:
        await progress_callback("Starting repository exploration with Claude Code SDK...")

    try:
        from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock

        if progress_callback:
            await progress_callback("Claude is exploring the repository structure...")

        tag_section = (
            f"\n\nThe repository is tagged with the following target features/requirements:\n"
            f"{tag_message}\n"
            f"Pay attention to these when identifying test coverage and setup."
            if tag_message else ""
        )

        overview_filename = _overview_filename(tag)
        prompt = (
            "You are analyzing a software repository to understand how to run its tests. "
            "Explore the repository files, read the README, config files (package.json, "
            "pyproject.toml, Cargo.toml, go.mod, etc.), and any existing test files. "
            f"{tag_section}"
            f"\n\nThen produce a file called {overview_filename} in the current directory with "
            "this exact structure:\n\n"
            "# {repo_name}\n\n"
            + (
                "## Tag Message\n"
                f"{tag_message}\n\n"
                if tag_message else ""
            )
            + "## Project Type\n"
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
        assistant_text_parts = []
        recorded_provider_usage = False
        async for message in query(
            prompt=prompt,
            options=ClaudeCodeOptions(
                cwd=str(clone_dir),
                # Allow file reads and writes but no network calls
                allowed_tools=["Read", "Write", "Glob", "Bash"],
            ),
        ):
            if record_llm_response_usage(message):
                recorded_provider_usage = True
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        char_count += len(block.text)
                        assistant_text_parts.append(block.text)
                        if progress_callback and char_count % 200 < 20:
                            await progress_callback(
                                f"Claude exploring... ({char_count} chars processed)"
                            )

        if not recorded_provider_usage:
            record_estimated_token_usage(prompt, "\n".join(assistant_text_parts))

        # If Claude wrote the file, great. Otherwise fall back to context-based approach.
        if not overview_path.exists():
            if progress_callback:
                await progress_callback(
                    "SDK did not write the file directly; using context fallback..."
                )
            overview_path = Path(
                await _explore_via_messages_api(clone_path, progress_callback, tag_message, tag)
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
        return await _explore_via_messages_api(clone_path, progress_callback, tag_message, tag)

    except Exception as e:
        if progress_callback:
            await progress_callback(f"SDK error ({e}); falling back to messages API...")
        return await _explore_via_messages_api(clone_path, progress_callback, tag_message, tag)


async def _explore_via_messages_api(
    clone_path: str,
    progress_callback=None,
    tag_message: Optional[str] = None,
    tag: Optional[str] = None,
) -> str:
    """Fallback: build context manually and call the Anthropic messages API."""
    clone_dir = Path(clone_path)
    overview_path = clone_dir / _overview_filename(tag)

    if progress_callback:
        await progress_callback("Analyzing repository structure...")

    context = await _build_repo_context(clone_dir)

    if progress_callback:
        await progress_callback("Generating overview with Claude...")

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
        raise ValueError(
            "No API credential available. Set OPEN_ROUTER_KEY (primary), "
            "ANTHROPIC_AUTH_TOKEN, or ANTHROPIC_API_KEY."
        )

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
