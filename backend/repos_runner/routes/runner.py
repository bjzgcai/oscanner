"""
API routes for Repository Runner
"""

import asyncio
import inspect
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from repos_runner.schemas import (
    RepoCloneRequest,
    RepoMetadata,
    TestSummary,
    RunAllRequest,
    BatchRunRequest,
)
from repos_runner.grading import normalize_grading_rubric
from repos_runner.services import (
    clone_repository,
    explore_repository,
    run_tests,
    detect_test_commands,
    list_repos,
    delete_repo,
)
from repos_runner.services.repo_service import fetch_gitee_tag_message
from repos_runner.services.repo_service import (
    get_clone_source_dir,
    get_clone_source_dir_for_url,
    get_repos_dir,
    parse_repo_url,
    parse_repo_url_with_ref,
    source_dir_from_repo_key,
)
from repos_runner.services.repo_service.llm import (
    reset_token_usage_collection,
    start_token_usage_collection,
    summarize_token_usage,
)
from repos_runner.services.repo_service.runtime_env import build_runtime_env_context
from repos_runner.services.task_queue import RunnerQueueFull, runner_queue

router = APIRouter(prefix="/api/runner")

_ALLOWED_ARTIFACT_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_ACTIVE_RUN_ALL_REPORTS: set[tuple[str, str]] = set()
_README_REQUIREMENT_FILES = ("README.md", "README.en.md", "README.txt", "README")
_README_NON_REQUIREMENT_HEADING_RE = re.compile(
    r"^\s{0,3}#+\s*(?:todo|to do|roadmap|future|planned|plan|backlog|"
    r"not implemented|incomplete|known issues|limitations|"
    r"待办|计划|规划|路线图|未完成|未实现|暂未实现|后续)\b",
    re.IGNORECASE,
)
_README_NON_REQUIREMENT_LINE_RE = re.compile(
    r"\b(?:todo|planned|planning|future work|roadmap|not implemented|not yet implemented|"
    r"incomplete|coming soon|will support|will be supported)\b|"
    r"(?:待办|计划|规划|未完成|未实现|暂未实现|尚未实现|待实现|后续|未来)",
    re.IGNORECASE,
)


def _hide_grading_rubric(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _hide_grading_rubric(item)
            for key, item in value.items()
            if key != "grading_rubric"
        }
    if isinstance(value, list):
        return [_hide_grading_rubric(item) for item in value]
    return value


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def _run_tests_with_optional_runtime_env(*args, runtime_env=None, **kwargs):
    """Call run_tests while preserving compatibility with older monkeypatched fakes."""
    try:
        signature = inspect.signature(run_tests)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and "runtime_env" in signature.parameters:
        kwargs["runtime_env"] = runtime_env
    return await run_tests(*args, **kwargs)


def _extract_validation_features(feature_requirements: Optional[str]) -> list[str]:
    """Extract a lightweight display list from manually supplied requirements."""
    text = _clean_optional_text(feature_requirements)
    if not text:
        return []

    raw_items: list[str] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 1:
        raw_items = re.split(r"[,;]+", text)
    else:
        raw_items = lines

    features: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        cleaned = re.sub(r"^\s*(?:[-*•]+|\d+[.)])\s*", "", item).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        features.append(cleaned)
    return features[:50]


def _readme_requirements_from_clone(clone_path: str) -> Optional[str]:
    clone_dir = Path(clone_path)
    for filename in _README_REQUIREMENT_FILES:
        readme_path = clone_dir / filename
        if not readme_path.is_file():
            continue
        try:
            readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        kept_lines: list[str] = []
        in_non_requirement_section = False
        for raw_line in readme_text.splitlines():
            line = raw_line.rstrip()
            if re.match(r"^\s{0,3}#+\s+", line):
                in_non_requirement_section = bool(
                    _README_NON_REQUIREMENT_HEADING_RE.search(line)
                )
                if in_non_requirement_section:
                    continue
            if in_non_requirement_section:
                continue
            if _README_NON_REQUIREMENT_LINE_RE.search(line):
                continue
            kept_lines.append(line)

        cleaned = "\n".join(kept_lines).strip()
        if not cleaned:
            continue
        if len(cleaned) > 12000:
            cleaned = cleaned[:12000].rsplit("\n", 1)[0].strip() or cleaned[:12000]
        return (
            "## Repository README requirements\n\n"
            "Use the repository README as the functional acceptance standard. "
            "Only treat currently documented, implemented behavior as requirements; "
            "ignore TODO, planned, roadmap, future, incomplete, or explicitly unimplemented items.\n\n"
            f"Source: {filename}\n\n"
            f"{cleaned}"
        )
    return None


def _active_report_key(repo_url: str, tag: Optional[str] = None) -> tuple[str, str]:
    normalized_repo_url = str(repo_url or "").strip().removesuffix(".git").rstrip("/").lower()
    normalized_tag = str(tag or "").strip()
    return normalized_repo_url, normalized_tag


class _PipelineTimeout(RuntimeError):
    """Raised when a run-all pipeline exceeds its configured deadline."""


def _timeout_label(timeout: float) -> str:
    return f"{timeout:g}"


def _pipeline_timeout_message(timeout: float) -> str:
    return f"Pipeline timed out after {_timeout_label(timeout)}s"


def _remaining_pipeline_seconds(deadline: float) -> float:
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise _PipelineTimeout()
    return remaining


async def _await_pipeline_step(awaitable, *, deadline: float):
    try:
        timeout = _remaining_pipeline_seconds(deadline)
    except _PipelineTimeout:
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise
    task = asyncio.create_task(awaitable)
    try:
        return await asyncio.wait_for(task, timeout=timeout)
    except asyncio.TimeoutError as exc:
        if task.done() and not task.cancelled():
            return task.result()
        raise _PipelineTimeout() from exc


def _resolve_runner_artifact_path(
    repo_url: Optional[str],
    artifact_path: str,
    repo_name: Optional[str] = None,
) -> Path:
    if repo_url:
        try:
            repos_dir = get_repos_dir()
            clone_dir = get_clone_source_dir_for_url(repo_url, repos_dir=repos_dir)
            if not clone_dir.exists():
                _, _, legacy_repo_name = parse_repo_url(repo_url)
                legacy_clone_dir = repos_dir / legacy_repo_name
                if legacy_clone_dir.exists():
                    clone_dir = legacy_clone_dir
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif repo_name:
        try:
            clone_dir = source_dir_from_repo_key(repo_name, repos_dir=get_repos_dir())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=400, detail="repo_url or repo_name is required")

    raw_path = str(artifact_path or "").strip().replace("\\", "/")
    if not raw_path:
        raise HTTPException(status_code=404, detail="Artifact not found")

    relative_path = Path(raw_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise HTTPException(status_code=404, detail="Artifact not found")

    parts = relative_path.parts
    if not parts or not parts[0].startswith("TEST_ARTIFACTS_"):
        raise HTTPException(status_code=404, detail="Artifact not found")

    clone_dir = clone_dir.resolve()
    candidate = (clone_dir / relative_path).resolve()
    if not (candidate == clone_dir or clone_dir in candidate.parents):
        raise HTTPException(status_code=404, detail="Artifact not found")
    if not candidate.is_file() or candidate.suffix.lower() not in _ALLOWED_ARTIFACT_IMAGE_SUFFIXES:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return candidate


# ---------------------------------------------------------------------------
# Clone
# ---------------------------------------------------------------------------

@router.post("/clone")
async def clone_repo(request: RepoCloneRequest):
    """Clone a repository and return metadata."""
    try:
        clone_kwargs = {"timeout": request.clone_timeout}
        if request.branch:
            clone_kwargs["branch"] = request.branch
        metadata = await clone_repository(request.repo_url, request.sha, request.tag, **clone_kwargs)
        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Explore (SSE)
# ---------------------------------------------------------------------------

@router.post("/explore")
async def explore_repo_stream(
    clone_path: str,
    feature_requirements: Optional[str] = None,
    tag: Optional[str] = None,
):
    """
    Explore repository and generate REPO_OVERVIEW.md with streaming progress.
    Uses opencode for agentic exploration (falls back to messages API).
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(message: str):
            await progress_queue.put(message)

        async def explore_task():
            try:
                result = await explore_repository(
                    clone_path,
                    progress_callback,
                    _clean_optional_text(feature_requirements),
                    tag=_clean_optional_text(tag),
                )
                await progress_queue.put({"status": "completed", "overview_path": result})
            except Exception as e:
                await progress_queue.put({"status": "failed", "error": str(e)})
            finally:
                await progress_queue.put(None)

        task = asyncio.create_task(explore_task())

        while True:
            message = await progress_queue.get()
            if message is None:
                break
            if isinstance(message, str):
                event_data = json.dumps({"event": "progress", "data": {"message": message}})
            else:
                event_data = json.dumps({"event": "status", "data": message})
            yield f"data: {event_data}\n\n"

        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Detect test commands
# ---------------------------------------------------------------------------

@router.get("/detect-tests")
async def detect_tests(overview_path: str, feature_requirements: Optional[str] = None):
    """
    Detect test commands from REPO_OVERVIEW.md without running them.
    Uses static analysis first, falls back to LLM, caches result.
    """
    try:
        test_info = await detect_test_commands(overview_path)
        validation_features = _extract_validation_features(feature_requirements)
        if validation_features:
            test_info = dict(test_info)
            test_info["validation_features"] = validation_features
        return test_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Run tests (SSE)
# ---------------------------------------------------------------------------

@router.post("/run-tests")
async def run_tests_stream(
    clone_path: str,
    overview_path: str,
    setup_timeout: int = Query(default=300, description="Seconds allowed per setup command"),
    test_timeout: int = Query(default=600, description="Seconds allowed per test command"),
    feature_requirements: Optional[str] = None,
    tag_message: Optional[str] = None,
    tag: Optional[str] = None,
    grading_rubric: Optional[str] = None,
    runtime_env_profile: Optional[str] = None,
    runtime_env_required_policy: str = "warn",
    runtime_env_safe_defaults: bool = True,
):
    """
    Run tests based on REPO_OVERVIEW.md with streaming progress.

    - setup_timeout: per-command timeout for dependency installation (default 300s)
    - test_timeout:  per-command timeout for test execution (default 600s)
    - feature_requirements/tag_message: optional feature requirements to validate
      alongside code tests
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        requirements = _clean_optional_text(feature_requirements) or _clean_optional_text(tag_message)
        clean_tag = _clean_optional_text(tag)
        clean_grading_rubric = normalize_grading_rubric(grading_rubric)

        async def progress_callback(message: str):
            await progress_queue.put(message)

        async def worker_progress_callback(message: str):
            loop.call_soon_threadsafe(progress_queue.put_nowait, message)
            await asyncio.sleep(0)

        async def test_task():
            try:
                from pathlib import Path
                async with runner_queue.acquire(progress_callback):
                    runtime_env = build_runtime_env_context(
                        clone_path,
                        profile=_clean_optional_text(runtime_env_profile),
                        required_policy=runtime_env_required_policy,
                        include_safe_defaults=runtime_env_safe_defaults,
                    )
                    result = await asyncio.to_thread(
                        lambda: asyncio.run(_run_tests_with_optional_runtime_env(
                            clone_path,
                            overview_path,
                            worker_progress_callback,
                            setup_timeout=setup_timeout,
                            test_timeout=test_timeout,
                            tag_message=requirements,
                            tag=clean_tag,
                            grading_rubric=clean_grading_rubric,
                            runtime_env=runtime_env,
                        ))
                    )
                report_path = result.get("report_path", "")
                try:
                    report_content = Path(report_path).read_text() if report_path else ""
                except Exception:
                    report_content = ""
                await progress_queue.put({
                    "status": "completed",
                    "results": _hide_grading_rubric(result),
                    "report_content": report_content,
                })
            except RunnerQueueFull as e:
                await progress_queue.put({"status": "failed", "error": str(e)})
            except Exception as e:
                await progress_queue.put({"status": "failed", "error": str(e)})
            finally:
                await progress_queue.put(None)

        task = asyncio.create_task(test_task())

        while True:
            message = await progress_queue.get()
            if message is None:
                break
            if isinstance(message, str):
                event_data = json.dumps({"event": "progress", "data": {"message": message}})
            else:
                event_data = json.dumps({"event": "status", "data": message})
            yield f"data: {event_data}\n\n"

        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Run-all pipeline (SSE) with idempotency flags
# ---------------------------------------------------------------------------

@router.post("/run-all")
async def run_all_stream(request: RunAllRequest):
    """
    Combined clone → explore → run-tests pipeline with SSE streaming progress.

    Pipeline stages:
    1. Clone   — shallow clone (depth=1) into
                 ~/.local/share/oscanner/repos/{platform}/{owner}/{repo}/{ref}/source/
                 Optionally checks out a specific SHA or tag.
    2. Explore — generates REPO_OVERVIEW.md via the configured LLM to understand
                 project structure, languages, and suggested test commands.
    3. Tests   — auto-detects test framework, sets up an isolated .venv, runs tests
                 inside a sandboxed subprocess. Produces TEST_REPORT.md with a
                 0–100 score based on pass/fail metrics.

    Idempotency flags:
    - skip_clone:   reuse existing clone (skip re-cloning)
    - skip_explore: reuse existing REPO_OVERVIEW.md (skip LLM exploration)

    Tag annotation scoring (Gitee only):
    - When `tag` is provided, fetches the annotated tag message from Gitee.
    - Extracts feature descriptions from the message and checks which features
      are exercised by the test suite (via LLM). Uncovered features reduce the
      maximum achievable score proportionally.

    SSE events emitted:
    - {"event": "progress", "data": {"message": "<msg>"}}   — pipeline log lines
    - {"event": "status",   "data": {"status": "completed", "results": {...}}}
    - {"event": "status",   "data": {"status": "failed",    "error": "<msg>"}}

    What is NOT covered:
    - Private repositories (no authentication support)
    - Tag annotation fetch for GitHub (Gitee-only)
    - Parallel test execution within a single repo
    - Non-Git version control systems
    """
    logger.info("run-all request: repo_url=%s tag=%s sha=%s", request.repo_url, request.tag, request.sha)
    print(f"[run-all] repo_url={request.repo_url} tag={request.tag} sha={request.sha}", flush=True)

    async def event_generator() -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        async def progress_callback(message: str):
            await progress_queue.put(message)

        async def worker_progress_callback(message: str):
            loop.call_soon_threadsafe(progress_queue.put_nowait, message)

        async def run_pipeline_in_worker_loop():
            usage_token = start_token_usage_collection()
            try:
                from pathlib import Path
                from repos_runner.services.repo_service import (
                    get_clone_source_dir,
                    get_repos_dir,
                    parse_repo_url,
                    parse_repo_url_with_ref,
                    repo_storage_key,
                )

                deadline = asyncio.get_running_loop().time() + request.pipeline_timeout

                # -- Clone step --
                if request.skip_clone:
                    parsed = parse_repo_url_with_ref(request.repo_url)
                    platform, owner, repo_name = parsed.platform, parsed.owner, parsed.repo
                    checkout_branch = None if request.sha or request.tag else (request.branch or parsed.branch)
                    clone_path = str(
                        get_clone_source_dir(
                            get_repos_dir(),
                            platform=platform,
                            owner=owner,
                            repo=repo_name,
                            sha=request.sha,
                            tag=request.tag,
                            branch=checkout_branch,
                        )
                    )
                    await worker_progress_callback(f"Skipping clone, reusing {clone_path}")
                    clone_metadata = {
                        "clone_path": clone_path,
                        "repo_name": repo_storage_key(
                            platform,
                            owner,
                            repo_name,
                            sha=request.sha,
                            tag=request.tag,
                            branch=checkout_branch,
                        ),
                        "display_name": repo_name,
                    }
                else:
                    await worker_progress_callback("Cloning repository...")
                    clone_kwargs = {"timeout": request.clone_timeout}
                    if request.branch:
                        clone_kwargs["branch"] = request.branch
                    clone_metadata = await _await_pipeline_step(
                        clone_repository(
                            request.repo_url,
                            request.sha,
                            request.tag,
                            **clone_kwargs,
                        ),
                        deadline=deadline,
                    )

                clone_path = clone_metadata["clone_path"]
                runtime_env = build_runtime_env_context(
                    clone_path,
                    profile=_clean_optional_text(request.runtime_env_profile),
                    required_policy=request.runtime_env_required_policy,
                    include_safe_defaults=request.runtime_env_safe_defaults,
                )
                if request.runtime_env_profile:
                    await worker_progress_callback(
                        f"Using runtime env profile '{request.runtime_env_profile}'"
                    )
                if runtime_env.missing_required_keys:
                    await worker_progress_callback(
                        "Missing detected runtime env keys: "
                        + ", ".join(runtime_env.missing_required_keys)
                    )
                if runtime_env.blocked_secret_keys:
                    await worker_progress_callback(
                        "Paid/real secret keys were not injected: "
                        + ", ".join(runtime_env.blocked_secret_keys)
                    )
                _safe_tag = request.tag.replace("/", "_").replace("\\", "_") if request.tag else None
                overview_filename = f"REPO_OVERVIEW_{_safe_tag}.md" if _safe_tag else "REPO_OVERVIEW.md"
                overview_path = str(Path(clone_path) / overview_filename)

                # -- Feature requirements / tag message --
                tag_message = str(request.tag_message or "").strip() or None
                grading_rubric = normalize_grading_rubric(request.grading_rubric)
                if tag_message:
                    await worker_progress_callback("Using forwarded feature requirements.")
                elif request.tag:
                    await worker_progress_callback(
                        f"Fetching tag annotation for '{request.tag}' from Gitee..."
                    )
                    tag_message = await _await_pipeline_step(
                        fetch_gitee_tag_message(request.repo_url, request.tag),
                        deadline=deadline,
                    )
                    if tag_message:
                        await worker_progress_callback(f"Tag message: {tag_message}")
                    else:
                        await worker_progress_callback(
                            "No tag annotation message found; checking README requirements."
                        )
                if not tag_message:
                    tag_message = _readme_requirements_from_clone(clone_path)
                    if tag_message:
                        await worker_progress_callback(
                            "Using README as functional acceptance requirements."
                        )

                # -- Explore step --
                if request.skip_explore and Path(overview_path).exists():
                    await worker_progress_callback(
                        f"Skipping exploration, reusing existing {overview_filename}"
                    )
                else:
                    await worker_progress_callback("Exploring repository...")
                    overview_path = await _await_pipeline_step(
                        explore_repository(
                            clone_path, worker_progress_callback, tag_message, tag=request.tag
                        ),
                        deadline=deadline,
                    )

                # -- Test step --
                await worker_progress_callback("Running tests...")
                result = await _await_pipeline_step(
                    _run_tests_with_optional_runtime_env(
                        clone_path,
                        overview_path,
                        worker_progress_callback,
                        setup_timeout=request.setup_timeout,
                        test_timeout=request.test_timeout,
                        tag_message=tag_message,
                        tag=request.tag,
                        grading_rubric=grading_rubric,
                        runtime_env=runtime_env,
                    ),
                    deadline=deadline,
                )

                report_path = result.get("report_path", "")
                try:
                    from pathlib import Path as _Path
                    report_content = _Path(report_path).read_text() if report_path else ""
                except Exception:
                    report_content = ""
                token_usage = summarize_token_usage()
                if token_usage:
                    result["token_usage"] = token_usage
                return {
                    "status": "completed",
                    "clone_metadata": clone_metadata,
                    "overview_path": overview_path,
                    "results": _hide_grading_rubric(result),
                    "report_content": report_content,
                    "token_usage": token_usage,
                }
            finally:
                reset_token_usage_collection(usage_token)

        async def pipeline_task():
            active_key = _active_report_key(request.repo_url, request.tag)
            _ACTIVE_RUN_ALL_REPORTS.add(active_key)
            try:
                async with runner_queue.acquire(progress_callback):
                    completed = await asyncio.to_thread(
                        lambda: asyncio.run(run_pipeline_in_worker_loop())
                    )
                    await progress_queue.put(completed)

            except asyncio.CancelledError:
                progress_queue.put_nowait({"status": "failed", "error": "Pipeline was cancelled"})
                raise
            except _PipelineTimeout:
                await progress_queue.put({
                    "status": "failed",
                    "error": _pipeline_timeout_message(request.pipeline_timeout),
                })
            except RunnerQueueFull as e:
                await progress_queue.put({"status": "failed", "error": str(e)})
            except Exception as e:
                await progress_queue.put({"status": "failed", "error": str(e)})
            finally:
                _ACTIVE_RUN_ALL_REPORTS.discard(active_key)
                progress_queue.put_nowait(None)

        task = asyncio.create_task(pipeline_task())

        while True:
            message = await progress_queue.get()
            if message is None:
                break
            if isinstance(message, str):
                event_data = json.dumps({"event": "progress", "data": {"message": message}})
            else:
                event_data = json.dumps({"event": "status", "data": message})
            yield f"data: {event_data}\n\n"

        try:
            await task
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Batch run (SSE) — up to 3 concurrent pipelines
# ---------------------------------------------------------------------------

@router.post("/batch-run")
async def batch_run_stream(request: BatchRunRequest):
    """
    Run up to N repos through the clone → explore → test pipeline concurrently.
    Concurrency is capped at 3 (max_concurrency field, ignored if > 3).

    SSE events:
    - {"event": "progress", "data": {"repo": "<url>", "message": "<msg>"}}
    - {"event": "repo_done",  "data": {"repo": "<url>", "status": "completed"|"failed", ...}}
    - {"event": "batch_done", "data": {"total": N, "succeeded": N, "failed": N}}
    """
    concurrency = min(request.max_concurrency, 3)

    async def event_generator() -> AsyncGenerator[str, None]:
        from pathlib import Path
        from repos_runner.services.repo_service import (
            get_clone_source_dir,
            get_repos_dir,
            parse_repo_url,
            parse_repo_url_with_ref,
            repo_storage_key,
        )

        event_queue: asyncio.Queue = asyncio.Queue()
        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(repo_req: RunAllRequest):
            repo_url = repo_req.repo_url
            async with semaphore:
                async def cb(msg: str):
                    await event_queue.put({"_type": "progress", "repo": repo_url, "message": msg})

                try:
                    async with runner_queue.acquire(cb):
                        deadline = asyncio.get_running_loop().time() + repo_req.pipeline_timeout
                        if repo_req.skip_clone:
                            parsed = parse_repo_url_with_ref(repo_url)
                            platform, owner, repo_name = parsed.platform, parsed.owner, parsed.repo
                            checkout_branch = None if repo_req.sha or repo_req.tag else (repo_req.branch or parsed.branch)
                            clone_path = str(
                                get_clone_source_dir(
                                    get_repos_dir(),
                                    platform=platform,
                                    owner=owner,
                                    repo=repo_name,
                                    sha=repo_req.sha,
                                    tag=repo_req.tag,
                                    branch=checkout_branch,
                                )
                            )
                            await cb(f"Skipping clone, reusing {clone_path}")
                            clone_metadata = {
                                "clone_path": clone_path,
                                "repo_name": repo_storage_key(
                                    platform,
                                    owner,
                                    repo_name,
                                    sha=repo_req.sha,
                                    tag=repo_req.tag,
                                    branch=checkout_branch,
                                ),
                                "display_name": repo_name,
                            }
                        else:
                            await cb("Cloning repository...")
                            clone_kwargs = {"timeout": repo_req.clone_timeout}
                            if repo_req.branch:
                                clone_kwargs["branch"] = repo_req.branch
                            clone_metadata = await _await_pipeline_step(
                                clone_repository(repo_url, repo_req.sha, repo_req.tag, **clone_kwargs),
                                deadline=deadline,
                            )

                        clone_path = clone_metadata["clone_path"]
                        runtime_env = build_runtime_env_context(
                            clone_path,
                            profile=_clean_optional_text(repo_req.runtime_env_profile),
                            required_policy=repo_req.runtime_env_required_policy,
                            include_safe_defaults=repo_req.runtime_env_safe_defaults,
                        )
                        if repo_req.runtime_env_profile:
                            await cb(f"Using runtime env profile '{repo_req.runtime_env_profile}'")
                        if runtime_env.missing_required_keys:
                            await cb(
                                "Missing detected runtime env keys: "
                                + ", ".join(runtime_env.missing_required_keys)
                            )
                        _safe_tag = repo_req.tag.replace("/", "_").replace("\\", "_") if repo_req.tag else None
                        overview_filename = f"REPO_OVERVIEW_{_safe_tag}.md" if _safe_tag else "REPO_OVERVIEW.md"
                        overview_path = str(Path(clone_path) / overview_filename)

                        # -- Feature requirements / tag message --
                        tag_message = str(repo_req.tag_message or "").strip() or None
                        grading_rubric = normalize_grading_rubric(repo_req.grading_rubric)
                        if tag_message:
                            await cb("Using forwarded feature requirements.")
                        elif repo_req.tag:
                            await cb(f"Fetching tag annotation for '{repo_req.tag}' from Gitee...")
                            tag_message = await _await_pipeline_step(
                                fetch_gitee_tag_message(repo_url, repo_req.tag),
                                deadline=deadline,
                            )
                            if tag_message:
                                await cb(f"Tag message: {tag_message}")
                            else:
                                await cb(
                                    "No tag annotation message found; checking README requirements."
                                )
                        if not tag_message:
                            tag_message = _readme_requirements_from_clone(clone_path)
                            if tag_message:
                                await cb("Using README as functional acceptance requirements.")

                        if repo_req.skip_explore and Path(overview_path).exists():
                            await cb(f"Skipping exploration, reusing existing {overview_filename}")
                        else:
                            await cb("Exploring repository...")
                            overview_path = await _await_pipeline_step(
                                explore_repository(
                                    clone_path, cb, tag_message, tag=repo_req.tag
                                ),
                                deadline=deadline,
                            )

                        await cb("Running tests...")
                        result = await _await_pipeline_step(
                            _run_tests_with_optional_runtime_env(
                                clone_path,
                                overview_path,
                                cb,
                                setup_timeout=repo_req.setup_timeout,
                                test_timeout=repo_req.test_timeout,
                                tag_message=tag_message,
                                tag=repo_req.tag,
                                grading_rubric=grading_rubric,
                                runtime_env=runtime_env,
                            ),
                            deadline=deadline,
                        )

                    await event_queue.put({
                        "_type": "repo_done",
                        "repo": repo_url,
                        "status": "completed",
                        "clone_metadata": clone_metadata,
                        "overview_path": overview_path,
                        "results": _hide_grading_rubric(result),
                    })
                except RunnerQueueFull as e:
                    await event_queue.put({
                        "_type": "repo_done",
                        "repo": repo_url,
                        "status": "failed",
                        "error": str(e),
                    })
                except _PipelineTimeout:
                    await event_queue.put({
                        "_type": "repo_done",
                        "repo": repo_url,
                        "status": "failed",
                        "error": _pipeline_timeout_message(repo_req.pipeline_timeout),
                    })
                except Exception as e:
                    await event_queue.put({
                        "_type": "repo_done",
                        "repo": repo_url,
                        "status": "failed",
                        "error": str(e),
                    })

        tasks = [asyncio.create_task(run_one(r)) for r in request.repos]

        async def wait_all():
            await asyncio.gather(*tasks, return_exceptions=True)
            await event_queue.put(None)  # sentinel

        asyncio.create_task(wait_all())

        succeeded = 0
        failed = 0

        while True:
            item = await event_queue.get()
            if item is None:
                break

            event_type = item.pop("_type")

            if event_type == "progress":
                yield f"data: {json.dumps({'event': 'progress', 'data': item})}\n\n"
            elif event_type == "repo_done":
                if item.get("status") == "completed":
                    succeeded += 1
                else:
                    failed += 1
                yield f"data: {json.dumps({'event': 'repo_done', 'data': item})}\n\n"

        yield f"data: {json.dumps({'event': 'batch_done', 'data': {'total': len(request.repos), 'succeeded': succeeded, 'failed': failed}})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Queue status
# ---------------------------------------------------------------------------

@router.get("/queue")
async def get_queue_status():
    """Return current in-process runner queue state."""
    return runner_queue.snapshot()


# ---------------------------------------------------------------------------
# Resource lifecycle
# ---------------------------------------------------------------------------

@router.get("/repos")
async def list_cloned_repos():
    """
    List all cloned repositories with disk usage and status.

    Returns repo_name, clone_path, size_mb, last_accessed,
    has_overview, has_report, has_test_config.
    """
    try:
        return {"repos": list_repos()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/repo")
async def remove_repo(repo_name: str):
    """
    Delete a cloned repository and all associated files (venv, reports, etc.).

    Returns freed_mb.
    """
    try:
        result = delete_repo(repo_name)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifact")
async def get_artifact(path: str, repo_url: Optional[str] = None, repo_name: Optional[str] = None):
    """
    Serve runtime evidence images from TEST_ARTIFACTS_* for a cloned repository.
    """
    artifact_path = _resolve_runner_artifact_path(repo_url, path, repo_name)
    media_type = mimetypes.guess_type(artifact_path.name)[0] or "application/octet-stream"
    return FileResponse(artifact_path, media_type=media_type)


@router.get("/report")
async def get_report(repo_url: str, tag: Optional[str] = None):
    """
    Return the content of TEST_REPORT_{tag}.md (or TEST_REPORT.md) for a cloned repo.
    """
    try:
        parsed = parse_repo_url_with_ref(repo_url)
        platform, owner, repo_name = parsed.platform, parsed.owner, parsed.repo
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    repos_dir = get_repos_dir()
    clone_dir = get_clone_source_dir(
        repos_dir,
        platform=platform,
        owner=owner,
        repo=repo_name,
        tag=tag,
        branch=None if tag else parsed.branch,
    )
    legacy_clone_dir = repos_dir / repo_name
    if not clone_dir.exists() and legacy_clone_dir.exists():
        clone_dir = legacy_clone_dir
    active_key = _active_report_key(repo_url, tag)
    if not clone_dir.exists() and active_key in _ACTIVE_RUN_ALL_REPORTS:
        safe_tag = tag.replace("/", "_").replace(" ", "_") if tag else ""
        report_name = f"TEST_REPORT_{safe_tag}.md" if safe_tag else "TEST_REPORT.md"
        return JSONResponse(
            status_code=202,
            content={
                "status": "testing",
                "message": "正在测试评估中",
                "filename": report_name,
            },
        )

    if not clone_dir.exists():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    if tag:
        safe_tag = tag.replace("/", "_").replace(" ", "_")
        report_path = clone_dir / f"TEST_REPORT_{safe_tag}.md"
    else:
        report_path = clone_dir / "TEST_REPORT.md"

    if not report_path.exists():
        if active_key in _ACTIVE_RUN_ALL_REPORTS:
            return JSONResponse(
                status_code=202,
                content={
                    "status": "testing",
                    "message": "正在测试评估中",
                    "filename": report_path.name,
                },
            )
        raise HTTPException(status_code=404, detail=f"Report not found: {report_path.name}")

    return {"content": report_path.read_text(), "filename": report_path.name}
