"""Growth trajectory API endpoints."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
import asyncio
import json
import time
import uuid

from evaluator.config import DEFAULT_LLM_MODEL, get_llm_api_key, get_github_token, get_gitee_token
from evaluator.schemas import TrajectoryResponse
from evaluator.services import (
    analyze_growth_trajectory,
    analyze_group_repositories,
    resolve_plugin_id,
)
from evaluator.paths import get_platform_data_dir
from evaluator.services.trajectory_service import ensure_repo_data_synced
from evaluator.services.trajectory_poll_store import SQLiteTrajectoryPollStore
from evaluator.utils import parse_repo_url, load_commits_from_local, get_author_from_commit

router = APIRouter()
EXCLUDED_GITEE_AUTHORS_FOR_NULL_USERNAME = {"吴衍标"}
ONE_OFF_PRIMARY_MODEL = "deepseek/deepseek-v4-pro"
ONE_OFF_PRIMARY_MODELS = (ONE_OFF_PRIMARY_MODEL,)
_POLL_INTERRUPTED_MESSAGE = "Analysis job interrupted by server restart. Please start a new analysis."
_trajectory_poll_store = SQLiteTrajectoryPollStore()
_trajectory_poll_store.mark_interrupted_jobs(time.time(), _POLL_INTERRUPTED_MESSAGE)


def _repository_scoped_group_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in item.items()
        if key not in {"username", "aliases", "author_aliases"}
    }


def _extract_group_repository_items(request_body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Accept batch payloads from Courses and direct callers.

    Supported shapes:
    - {"students": [{"repo_url": "...", ...}]}
    - {"repositories": [{"repo_url": "...", ...}]}
    - {"repos": [{"repo_url": "...", ...}]}
    - {"repo_url": "..."} for single-repo compatibility
    """
    for key in ("students", "repositories", "repos"):
        items = request_body.get(key)
        if isinstance(items, list):
            return [
                _repository_scoped_group_item(item)
                for item in items
                if isinstance(item, dict)
            ]

    repo_url = str(request_body.get("repo_url") or "").strip()
    if repo_url:
        return [{
            "id": request_body.get("id"),
            "repo_url": repo_url,
            "organization": request_body.get("organization"),
            "pq_id": request_body.get("pq_id"),
        }]

    return []


def _check_platform_tokens_for_repos(repo_urls: List[str]) -> None:
    github_token = get_github_token()
    gitee_token = get_gitee_token()
    missing_platforms = []

    for repo_url in repo_urls:
        parsed = parse_repo_url(repo_url)
        if not parsed:
            continue

        platform, _, _ = parsed
        if platform == "github" and not github_token and "github" not in missing_platforms:
            missing_platforms.append("github")
        elif platform == "gitee" and not gitee_token and "gitee" not in missing_platforms:
            missing_platforms.append("gitee")

    if missing_platforms:
        missing_tokens = []
        if "github" in missing_platforms:
            missing_tokens.append("GitHub Token (GITHUB_TOKEN)")
        if "gitee" in missing_platforms:
            missing_tokens.append("Gitee Token (GITEE_TOKEN)")
        raise HTTPException(
            status_code=400,
            detail=f"Missing required platform tokens: {', '.join(missing_tokens)}. "
                   "Please configure them before analyzing.",
        )


def format_sse_event(event: str, data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _parse_sse_frame(frame: str) -> tuple[str, Any] | None:
    event = "message"
    data_lines: List[str] = []

    for line in frame.splitlines():
        if not line or line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[6:].strip() or "message"
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    if not data_lines:
        return None

    raw_data = "\n".join(data_lines)
    try:
        data: Any = json.loads(raw_data)
    except json.JSONDecodeError:
        data = raw_data
    return event, data


def _parse_sse_buffer(buffer: str) -> tuple[List[tuple[str, Any]], str]:
    normalized = buffer.replace("\r\n", "\n")
    frames = normalized.split("\n\n")
    remaining = frames.pop() or ""
    events = [
        parsed
        for frame in frames
        if frame.strip()
        for parsed in [_parse_sse_frame(frame)]
        if parsed is not None
    ]
    return events, remaining


def _wants_sse(request: Request | None) -> bool:
    accept = str((getattr(request, "headers", {}) or {}).get("accept") or "").lower()
    return "text/event-stream" in accept


def _with_single_repo_compat(result: Dict[str, Any]) -> Dict[str, Any]:
    # Single-repo compatibility for callers that expect the one-off shape.
    results = result.get("results") if isinstance(result, dict) else None
    if isinstance(results, list) and len(results) == 1:
        single = results[0]
        return {
            **result,
            "checkpoint": single.get("checkpoint"),
            "score": single.get("score"),
            "commits_analyzed": single.get("commits_analyzed", 0),
            "repo_url": single.get("repo_url"),
            "username": single.get("username"),
        }
    return result


def _get_commit_datetime(commit: Dict[str, Any]) -> Optional[datetime]:
    """Extract commit datetime from known commit payload formats."""
    date_str = (
        commit.get("commit", {}).get("author", {}).get("date")
        or commit.get("date")
        or ""
    )
    if not date_str:
        return None

    try:
        parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _get_oldest_commit(commits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pick oldest commit by date when possible; otherwise fallback to list tail."""
    oldest_commit = commits[-1]
    oldest_date = _get_commit_datetime(oldest_commit)

    for commit in commits:
        commit_date = _get_commit_datetime(commit)
        if commit_date is None:
            continue
        if oldest_date is None or commit_date < oldest_date:
            oldest_date = commit_date
            oldest_commit = commit

    return oldest_commit


def _infer_username_from_first_commit(repo_urls: List[str]) -> Optional[str]:
    """
    Infer default username from the earliest ("first") commit author
    across all provided repositories.
    """
    inferred_username: Optional[str] = None
    inferred_commit_date: Optional[datetime] = None

    for repo_url in repo_urls:
        parsed = parse_repo_url(repo_url)
        if not parsed:
            continue

        platform, owner, repo = parsed

        try:
            # Ensure local data exists before reading commit history.
            ensure_repo_data_synced(repo_url, max_commits=500)
        except Exception as e:
            print(f"[Trajectory API One-Off] Warning: failed to sync {repo_url} for username inference: {e}")
            continue

        data_dir = get_platform_data_dir(platform, owner, repo)
        if not data_dir.exists():
            continue

        commits = load_commits_from_local(data_dir, limit=None)
        if not commits:
            continue

        oldest_commit = _get_oldest_commit(commits)
        author = (get_author_from_commit(oldest_commit) or "").strip()
        if not author:
            continue

        commit_date = _get_commit_datetime(oldest_commit)
        if inferred_username is None:
            inferred_username = author
            inferred_commit_date = commit_date
            continue

        if commit_date is not None and (inferred_commit_date is None or commit_date < inferred_commit_date):
            inferred_username = author
            inferred_commit_date = commit_date

    return inferred_username


def _infer_gitee_authors_from_commits(repo_urls: List[str]) -> List[str]:
    """
    Infer all author names from Gitee repositories in repo_urls.
    Authors are returned in descending commit-count order.
    """
    author_counts: Dict[str, int] = {}
    author_display_names: Dict[str, str] = {}

    for repo_url in repo_urls:
        parsed = parse_repo_url(repo_url)
        if not parsed:
            continue

        platform, owner, repo = parsed
        if platform != "gitee":
            continue

        try:
            ensure_repo_data_synced(repo_url, max_commits=500)
        except Exception as e:
            print(f"[Trajectory API One-Off] Warning: failed to sync {repo_url} for gitee author inference: {e}")
            continue

        data_dir = get_platform_data_dir(platform, owner, repo)
        if not data_dir.exists():
            continue

        commits = load_commits_from_local(data_dir, limit=None)
        if not commits:
            continue

        for commit in commits:
            author = (get_author_from_commit(commit) or "").strip()
            if not author:
                continue

            key = author.lower()
            if key not in author_counts:
                author_counts[key] = 0
                author_display_names[key] = author
            author_counts[key] += 1

    sorted_keys = sorted(
        author_counts.keys(),
        key=lambda k: (-author_counts[k], author_display_names[k].lower())
    )
    authors = [author_display_names[k] for k in sorted_keys]
    excluded = {name.strip().lower() for name in EXCLUDED_GITEE_AUTHORS_FOR_NULL_USERNAME}
    return [name for name in authors if name.strip().lower() not in excluded]


@router.post("/api/trajectory/analyze")
async def analyze_trajectory(
    request_body: Dict[str, Any],
    plugin: str = Query(""),
    model: str = Query(DEFAULT_LLM_MODEL),
    language: str = Query("zh-CN"),
    forced_checker: str = Query(""),
    worktree_base: str = Query("build"),  # 'build' or 'temp', default 'build'
    checkpoint_strategy: str = Query("period")  # 'period' or 'none', default 'period'
) -> Dict[str, Any]:
    """
    Analyze user growth trajectory.

    Request body format:
    {
        "username": "CarterWu",
        "repo_urls": ["https://gitee.com/zgcai/oscanner"],
        "aliases": ["CarterWu", "wu-yanbiao"]
    }

    Returns TrajectoryResponse with:
    - success: bool
    - trajectory: TrajectoryData (if successful)
    - new_checkpoint_created: bool
    - message: str
    - commits_pending: int (commits not yet forming a checkpoint)
    """
    try:
        # Validate request body
        if not isinstance(request_body, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")

        username = request_body.get("username")

        # Handle both repo_url (singular) and repo_urls (plural) for backwards compatibility
        repo_urls = request_body.get("repo_urls", [])
        if not repo_urls and request_body.get("repo_url"):
            # If repo_urls is empty but repo_url exists, use it
            repo_urls = [request_body.get("repo_url")]

        aliases = request_body.get("aliases", [])

        if not username:
            raise HTTPException(status_code=400, detail="Missing required field: username")

        if not isinstance(repo_urls, list):
            raise HTTPException(status_code=400, detail="repo_urls must be a list (can be empty)")

        # If repo_urls is empty, return empty trajectory
        if not repo_urls:
            return {
                "success": True,
                "trajectory": {
                    "username": username,
                    "repo_urls": [],
                    "checkpoints": [],
                    "total_checkpoints": 0,
                    "created_at": None,
                    "updated_at": None
                },
                "new_checkpoint_created": False,
                "message": "No repositories to analyze",
                "commits_pending": 0
            }

        # Ensure aliases includes username
        if username not in aliases:
            aliases = [username] + aliases

        # Check LLM configuration before analysis
        api_key = get_llm_api_key()
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init)."
            )

        # Check platform token configuration before analysis
        github_token = get_github_token()
        gitee_token = get_gitee_token()
        missing_platforms = []
        
        for repo_url in repo_urls:
            parsed = parse_repo_url(repo_url)
            if not parsed:
                continue  # Skip invalid URLs, they'll be handled later
            
            platform, owner, repo = parsed
            if platform == "github" and not github_token:
                if "github" not in missing_platforms:
                    missing_platforms.append("github")
            elif platform == "gitee" and not gitee_token:
                if "gitee" not in missing_platforms:
                    missing_platforms.append("gitee")
        
        if missing_platforms:
            missing_tokens = []
            if "github" in missing_platforms:
                missing_tokens.append("GitHub Token (GITHUB_TOKEN)")
            if "gitee" in missing_platforms:
                missing_tokens.append("Gitee Token (GITEE_TOKEN)")
            
            raise HTTPException(
                status_code=400,
                detail=f"Missing required platform tokens: {', '.join(missing_tokens)}. "
                       f"Please configure them in Settings (LLM Settings) before analyzing. "
                       f"Without tokens, API rate limits are very low (~60 requests/hour for GitHub, lower for Gitee)."
            )

        # Resolve plugin ID
        plugin_id = resolve_plugin_id(plugin)

        print(f"[Trajectory API] Analyzing trajectory for {username}")
        print(f"[Trajectory API] Repos: {repo_urls}")
        print(f"[Trajectory API] Aliases: {aliases}")

        # Call trajectory analysis service
        # Run synchronous blocking operations in thread pool to avoid blocking event loop
        forced_checker_id = forced_checker.strip() if forced_checker else None
        worktree_base_value = worktree_base.strip() if worktree_base else "build"
        if worktree_base_value not in ("build", "temp"):
            worktree_base_value = "build"  # Default to build

        checkpoint_strategy_value = checkpoint_strategy.strip() if checkpoint_strategy else "period"
        if checkpoint_strategy_value not in ("period", "none"):
            checkpoint_strategy_value = "period"  # Default to period

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            analyze_growth_trajectory,
            username,
            repo_urls,
            aliases,
            plugin_id,
            model,
            language,
            forced_checker_id,
            worktree_base_value,
            checkpoint_strategy_value,
            None,  # start_sha (not used in regular endpoint)
            None,  # end_sha (not used in regular endpoint)
        )

        return response.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Trajectory API] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Trajectory analysis failed: {str(e)}")


@router.post("/api/trajectory/analyze_stream")
async def analyze_trajectory_stream(
    request_body: Dict[str, Any],
    plugin: str = Query(""),
    model: str = Query(DEFAULT_LLM_MODEL),
    language: str = Query("zh-CN"),
    forced_checker: str = Query(""),
    worktree_base: str = Query("build"),
    checkpoint_strategy: str = Query("period")
) -> StreamingResponse:
    """
    Stream trajectory analysis as SSE.

    Final `result` event matches /api/trajectory/analyze response shape.
    """

    async def event_stream():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Dict[str, Any]]] = asyncio.Queue()

        def emit(event: str, data: Dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, (event, data))

        def run_analysis() -> Dict[str, Any]:
            if not isinstance(request_body, dict):
                raise ValueError("Request body must be a JSON object")

            username = request_body.get("username")
            repo_urls = request_body.get("repo_urls", [])
            if not repo_urls and request_body.get("repo_url"):
                repo_urls = [request_body.get("repo_url")]

            aliases = request_body.get("aliases", [])
            if not isinstance(aliases, list):
                aliases = []

            if not username:
                raise ValueError("Missing required field: username")

            if not isinstance(repo_urls, list):
                raise ValueError("repo_urls must be a list (can be empty)")

            if not repo_urls:
                return {
                    "success": True,
                    "trajectory": {
                        "username": username,
                        "repo_urls": [],
                        "checkpoints": [],
                        "total_checkpoints": 0,
                        "created_at": None,
                        "updated_at": None,
                    },
                    "new_checkpoint_created": False,
                    "message": "No repositories to analyze",
                    "commits_pending": 0,
                }

            if username not in aliases:
                aliases = [username] + aliases

            api_key = get_llm_api_key()
            if not api_key:
                raise RuntimeError(
                    "LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init)."
                )

            github_token = get_github_token()
            gitee_token = get_gitee_token()
            missing_platforms: List[str] = []

            for repo_url in repo_urls:
                parsed = parse_repo_url(repo_url)
                if not parsed:
                    continue

                platform, _, _ = parsed
                if platform == "github" and not github_token and "github" not in missing_platforms:
                    missing_platforms.append("github")
                elif platform == "gitee" and not gitee_token and "gitee" not in missing_platforms:
                    missing_platforms.append("gitee")

            if missing_platforms:
                missing_tokens = []
                if "github" in missing_platforms:
                    missing_tokens.append("GitHub Token (GITHUB_TOKEN)")
                if "gitee" in missing_platforms:
                    missing_tokens.append("Gitee Token (GITEE_TOKEN)")
                raise RuntimeError(
                    f"Missing required platform tokens: {', '.join(missing_tokens)}. "
                    "Please configure them in Settings (LLM Settings) before analyzing. "
                    "Without tokens, API rate limits are very low (~60 requests/hour for GitHub, lower for Gitee)."
                )

            plugin_id = resolve_plugin_id(plugin)
            forced_checker_id = forced_checker.strip() if forced_checker else None
            worktree_base_value = worktree_base.strip() if worktree_base else "build"
            if worktree_base_value not in ("build", "temp"):
                worktree_base_value = "build"

            checkpoint_strategy_value = checkpoint_strategy.strip() if checkpoint_strategy else "period"
            if checkpoint_strategy_value not in ("period", "none"):
                checkpoint_strategy_value = "period"

            emit("section", {
                "title": "开始成长轨迹分析",
                "status": "running",
                "username": username,
                "repo_count": len(repo_urls),
            })

            response = analyze_growth_trajectory(
                username,
                repo_urls,
                aliases,
                plugin_id,
                model,
                language,
                forced_checker_id,
                worktree_base_value,
                checkpoint_strategy_value,
                None,
                None,
                None,
                emit,
            )
            return response.model_dump()

        yield format_sse_event("section", {"title": "连接已建立", "status": "done"})
        task = loop.run_in_executor(None, run_analysis)

        while True:
            if task.done():
                while not queue.empty():
                    event, data = queue.get_nowait()
                    yield format_sse_event(event, data)
                try:
                    result = task.result()
                    yield format_sse_event("result", result)
                    yield format_sse_event("done", {"finish_reason": "stop"})
                except Exception as e:
                    yield format_sse_event("error", {"message": str(e)})
                break

            try:
                event, data = await asyncio.wait_for(queue.get(), timeout=15)
                yield format_sse_event(event, data)
            except asyncio.TimeoutError:
                yield format_sse_event("heartbeat", {"status": "running"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/courses/group_analyse_code")
async def group_analyse_code(
    request_body: Dict[str, Any],
    request: Request = None,
    plugin: str = Query("zgc_ai_native_2026"),
    language: str = Query("zh-CN"),
    max_fetch_workers: int = Query(4),
    forced_checker: str = Query(""),
    worktree_base: str = Query("build"),
) -> Dict[str, Any]:
    """
    Courses-compatible full repository group evaluation.

    This endpoint is intentionally repository-scoped, not author-scoped:
    - it evaluates every commit stored for each repo
    - it uses DeepSeek V4 Pro's long context window
    - it disables commit chunking for the LLM evaluation path
    - it accepts multiple repos in a single request so scores are produced with
      the same model, rubric, and runtime settings
    """
    if _wants_sse(request):
        return StreamingResponse(
            _group_analyse_code_event_stream(
                request_body=request_body,
                plugin=plugin,
                language=language,
                max_fetch_workers=max_fetch_workers,
                forced_checker=forced_checker,
                worktree_base=worktree_base,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        if not isinstance(request_body, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")

        repositories = _extract_group_repository_items(request_body)
        if not repositories:
            return {
                "success": False,
                "message": "No repositories to analyze",
                "results": [],
                "summary": {"total": 0, "success": 0, "failed": 0},
            }

        api_key = get_llm_api_key()
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init).",
            )

        repo_urls = [str(item.get("repo_url") or "").strip() for item in repositories if item.get("repo_url")]
        _check_platform_tokens_for_repos(repo_urls)

        plugin_id = resolve_plugin_id(plugin)
        forced_checker_id = forced_checker.strip() if forced_checker else None
        worktree_base_value = worktree_base.strip() if worktree_base else "build"
        if worktree_base_value not in ("build", "temp"):
            worktree_base_value = "build"

        expected_feature = request_body.get("expected_feature")
        if isinstance(expected_feature, str):
            expected_feature = expected_feature.strip() or None
        elif expected_feature is not None:
            raise HTTPException(status_code=400, detail="expected_feature must be a string")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: analyze_group_repositories(
                repositories=repositories,
                plugin_id=plugin_id,
                model=ONE_OFF_PRIMARY_MODEL,
                language=language,
                max_fetch_workers=max_fetch_workers,
                forced_checker_id=forced_checker_id,
                worktree_base=worktree_base_value,
                full_repo=True,
                expected_feature=expected_feature,
            ),
        )

        return _with_single_repo_compat(result)

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Courses Group Analyse] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Group analysis failed: {str(e)}")


async def _group_analyse_code_event_stream(
    *,
    request_body: Dict[str, Any],
    plugin: str,
    language: str,
    max_fetch_workers: int,
    forced_checker: str,
    worktree_base: str,
):
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, Dict[str, Any]]] = asyncio.Queue()

    def emit(event: str, data: Dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (event, data))

    def run_analysis() -> Dict[str, Any]:
        if not isinstance(request_body, dict):
            raise ValueError("Request body must be a JSON object")

        repositories = _extract_group_repository_items(request_body)
        if not repositories:
            return {
                "success": False,
                "message": "No repositories to analyze",
                "results": [],
                "summary": {"total": 0, "success": 0, "failed": 0},
            }

        api_key = get_llm_api_key()
        if not api_key:
            raise RuntimeError(
                "LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init)."
            )

        repo_urls = [str(item.get("repo_url") or "").strip() for item in repositories if item.get("repo_url")]
        _check_platform_tokens_for_repos(repo_urls)

        plugin_id = resolve_plugin_id(plugin)
        forced_checker_id = forced_checker.strip() if forced_checker else None
        worktree_base_value = worktree_base.strip() if worktree_base else "build"
        if worktree_base_value not in ("build", "temp"):
            worktree_base_value = "build"

        expected_feature = request_body.get("expected_feature")
        if isinstance(expected_feature, str):
            expected_feature = expected_feature.strip() or None
        elif expected_feature is not None:
            raise ValueError("expected_feature must be a string")

        emit("section", {
            "title": "开始团体仓库评估",
            "status": "running",
            "repo_count": len(repositories),
        })

        result = analyze_group_repositories(
            repositories=repositories,
            plugin_id=plugin_id,
            model=ONE_OFF_PRIMARY_MODEL,
            language=language,
            max_fetch_workers=max_fetch_workers,
            forced_checker_id=forced_checker_id,
            worktree_base=worktree_base_value,
            full_repo=True,
            expected_feature=expected_feature,
            progress_callback=emit,
        )
        return _with_single_repo_compat(result)

    yield format_sse_event("section", {"title": "连接已建立", "status": "done"})
    task = loop.run_in_executor(None, run_analysis)

    while True:
        if task.done():
            while not queue.empty():
                event, data = queue.get_nowait()
                yield format_sse_event(event, data)
            try:
                result = task.result()
                yield format_sse_event("result", result)
                yield format_sse_event("done", {"finish_reason": "stop"})
            except Exception as e:
                yield format_sse_event("error", {"message": str(e)})
            break

        try:
            event, data = await asyncio.wait_for(queue.get(), timeout=15)
            yield format_sse_event(event, data)
        except asyncio.TimeoutError:
            yield format_sse_event("heartbeat", {"status": "running"})


@router.post("/api/trajectory/analyze_one-off")
async def analyze_trajectory_one_off(
    request_body: Dict[str, Any],
    plugin: str = Query("zgc_ai_native_2026"),
    model: str = Query(DEFAULT_LLM_MODEL),
    language: str = Query("zh-CN"),
    forced_checker: str = Query(""),
    worktree_base: str = Query("build"),  # 'build' or 'temp', default 'build'
    checkpoint_strategy: str = Query("none"),  # 'period' or 'none', default 'none' for one-off
    start_sha: str = Query(""),  # Optional: commit hash to start from (INCLUDED)
    end_sha: str = Query("")  # Optional: commit hash to end at (INCLUDED)
) -> Dict[str, Any]:
    """
    Analyze user growth trajectory as a one-off request.

    This endpoint is for external parties to call. It performs analysis for a specific
    commit range and returns a SINGLE checkpoint.

    Request body format:
    {
        "username": "CarterWu",
        "repo_urls": ["https://gitee.com/zgcai/oscanner"],
        "aliases": ["CarterWu", "wu-yanbiao"],
        "expected_feature": "Optional feature description used as an evaluation baseline"
    }
    Note: `username` is optional.
    - If `username` is null and repo is from Gitee, all detected authors are used (no single-author filtering).
    - Otherwise, missing/empty username defaults to the first commit author.
    - `expected_feature` is optional. When omitted or blank, evaluation uses the normal rubric only.

    Query parameters:
    - checkpoint_strategy: 'none' (default) or 'period'. Use 'none' for analyzing any commit range.
    - start_sha: Optional commit hash to start from (INCLUDED in range)
    - end_sha: Optional commit hash to end at (INCLUDED in range)

    When checkpoint_strategy=none:
    - If start_sha not provided: start from first commit (included)
    - If end_sha not provided: use latest commit (included)
    - No minimum commit requirement

    Corner cases:
    - Both None: evaluate all commits
    - Only start_sha: evaluate from start_sha to latest
    - Only end_sha: evaluate from first to end_sha
    - start_sha == end_sha: single commit evaluation
    - start_sha newer than end_sha: error (invalid range)
    - SHA not found: error with clear message

    Returns:
    - success: bool
    - checkpoint: TrajectoryCheckpoint (single checkpoint object, if successful)
    - message: str
    - commits_analyzed: int (number of commits included in the checkpoint)
    """
    try:
        # Validate request body
        if not isinstance(request_body, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")

        username = request_body.get("username")
        username_is_explicit_null = "username" in request_body and request_body.get("username") is None

        # Handle both repo_url (singular) and repo_urls (plural) for backwards compatibility
        repo_urls = request_body.get("repo_urls", [])
        if not repo_urls and request_body.get("repo_url"):
            # If repo_urls is empty but repo_url exists, use it
            repo_urls = [request_body.get("repo_url")]

        aliases = request_body.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []

        expected_feature = request_body.get("expected_feature")
        if isinstance(expected_feature, str):
            expected_feature = expected_feature.strip() or None
        elif expected_feature is not None:
            raise HTTPException(status_code=400, detail="expected_feature must be a string")

        if isinstance(username, str):
            username = username.strip()
        elif username is not None:
            raise HTTPException(status_code=400, detail="username must be a string")

        if not isinstance(repo_urls, list):
            raise HTTPException(status_code=400, detail="repo_urls must be a list (can be empty)")

        # If repo_urls is empty, return error
        if not repo_urls:
            return {
                "success": False,
                "checkpoint": None,
                "message": "No repositories to analyze",
                "commits_analyzed": 0
            }

        # Check LLM configuration before analysis
        api_key = get_llm_api_key()
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init)."
            )

        # Check platform token configuration before analysis
        github_token = get_github_token()
        gitee_token = get_gitee_token()
        missing_platforms = []

        for repo_url in repo_urls:
            parsed = parse_repo_url(repo_url)
            if not parsed:
                continue  # Skip invalid URLs, they'll be handled later

            platform, owner, repo = parsed
            if platform == "github" and not github_token:
                if "github" not in missing_platforms:
                    missing_platforms.append("github")
            elif platform == "gitee" and not gitee_token:
                if "gitee" not in missing_platforms:
                    missing_platforms.append("gitee")

        if missing_platforms:
            missing_tokens = []
            if "github" in missing_platforms:
                missing_tokens.append("GitHub Token (GITHUB_TOKEN)")
            if "gitee" in missing_platforms:
                missing_tokens.append("Gitee Token (GITEE_TOKEN)")

            raise HTTPException(
                status_code=400,
                detail=f"Missing required platform tokens: {', '.join(missing_tokens)}. "
                       f"Please configure them in Settings (LLM Settings) before analyzing. "
                       f"Without tokens, API rate limits are very low (~60 requests/hour for GitHub, lower for Gitee)."
            )

        inferred_all_authors: List[str] = []

        # Username is optional for one-off mode.
        if not username:
            # Special mode: username=null + gitee repo means evaluate without single-author filtering.
            if username_is_explicit_null:
                inferred_all_authors = _infer_gitee_authors_from_commits(repo_urls)
                if inferred_all_authors:
                    username = inferred_all_authors[0]
                    print(
                        f"[Trajectory API One-Off] username=null for gitee repo, "
                        f"using {len(inferred_all_authors)} inferred authors"
                    )
                else:
                    print(
                        "[Trajectory API One-Off] username=null but no gitee authors inferred, "
                        "falling back to first-commit author inference"
                    )

            if not username:
                username = _infer_username_from_first_commit(repo_urls)
                if not username:
                    raise HTTPException(
                        status_code=400,
                        detail="Missing required field: username. Unable to infer default username from first commit author."
                    )
                print(f"[Trajectory API One-Off] Inferred username from first commit author: {username}")
            elif username_is_explicit_null and inferred_all_authors:
                print(f"[Trajectory API One-Off] Primary username set to first inferred gitee author: {username}")

        # Ensure aliases include username and (when enabled) all inferred Gitee authors.
        merged_aliases: List[str] = []
        seen_aliases = set()
        for candidate in [username, *inferred_all_authors, *aliases]:
            if not isinstance(candidate, str):
                continue
            cleaned = candidate.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen_aliases:
                continue
            seen_aliases.add(key)
            merged_aliases.append(cleaned)
        aliases = merged_aliases

        # Resolve plugin ID
        plugin_id = resolve_plugin_id(plugin)

        print(f"[Trajectory API One-Off] Analyzing trajectory for {username}")
        print(f"[Trajectory API One-Off] Repos: {repo_urls}")
        print(f"[Trajectory API One-Off] Aliases: {aliases}")

        # Call trajectory analysis service
        # Run synchronous blocking operations in thread pool to avoid blocking event loop
        forced_checker_id = forced_checker.strip() if forced_checker else None
        worktree_base_value = worktree_base.strip() if worktree_base else "build"
        if worktree_base_value not in ("build", "temp"):
            worktree_base_value = "build"  # Default to build

        checkpoint_strategy_value = checkpoint_strategy.strip() if checkpoint_strategy else "none"
        if checkpoint_strategy_value not in ("period", "none"):
            checkpoint_strategy_value = "none"  # Default to none for one-off

        start_sha_value = start_sha.strip() if start_sha else None
        end_sha_value = end_sha.strip() if end_sha else None

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            analyze_growth_trajectory,
            username,
            repo_urls,
            aliases,
            plugin_id,
            ONE_OFF_PRIMARY_MODEL,
            language,
            forced_checker_id,
            worktree_base_value,
            checkpoint_strategy_value,
            start_sha_value,
            end_sha_value,
            expected_feature,
        )

        if not response.success or not response.trajectory or not response.trajectory.checkpoints:
            return {
                "success": False,
                "checkpoint": None,
                "message": f"{ONE_OFF_PRIMARY_MODEL} analysis failed: {response.message}",
                "commits_analyzed": 0,
                "model_judging": {
                    "primary_models": list(ONE_OFF_PRIMARY_MODELS),
                    "synthesis_model": None,
                    "failed_model": ONE_OFF_PRIMARY_MODEL,
                },
            }

        checkpoint = response.trajectory.checkpoints[-1]
        checkpoint_data = checkpoint.model_dump()
        commit_count = (
            (checkpoint_data.get("commits_range") or {}).get("commit_count")
            or 0
        )

        return {
            "success": True,
            "checkpoint": checkpoint_data,
            "message": f"Created final one-off judgment using {ONE_OFF_PRIMARY_MODEL}.",
            "commits_analyzed": commit_count,
            "model_judging": {
                "primary_models": list(ONE_OFF_PRIMARY_MODELS),
                "synthesis_model": None,
                "conflicts_detected": False,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Trajectory API One-Off] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Trajectory analysis failed: {str(e)}")


@router.post("/api/trajectory/analyze_one_off_stream")
async def analyze_trajectory_one_off_stream(
    request_body: Dict[str, Any],
    plugin: str = Query("zgc_ai_native_2026"),
    model: str = Query(DEFAULT_LLM_MODEL),
    language: str = Query("zh-CN"),
    forced_checker: str = Query(""),
    worktree_base: str = Query("build"),
    checkpoint_strategy: str = Query("none"),
    start_sha: str = Query(""),
    end_sha: str = Query("")
) -> StreamingResponse:
    """
    Stream one-off trajectory analysis as SSE.

    Events:
    - section: high-level analysis phase status
    - token: raw LLM token text from OpenAI-compatible streaming chunks
    - result: final JSON payload matching /api/trajectory/analyze_one-off
    - error: user-readable failure
    - done: stream completed
    """

    async def event_stream():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Dict[str, Any]]] = asyncio.Queue()

        def emit(event: str, data: Dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, (event, data))

        def run_analysis() -> Dict[str, Any]:
            if not isinstance(request_body, dict):
                raise ValueError("Request body must be a JSON object")

            username = request_body.get("username")
            username_is_explicit_null = "username" in request_body and request_body.get("username") is None

            repo_urls = request_body.get("repo_urls", [])
            if not repo_urls and request_body.get("repo_url"):
                repo_urls = [request_body.get("repo_url")]

            aliases = request_body.get("aliases", [])
            if not isinstance(aliases, list):
                aliases = []

            expected_feature = request_body.get("expected_feature")
            if isinstance(expected_feature, str):
                expected_feature = expected_feature.strip() or None
            elif expected_feature is not None:
                raise ValueError("expected_feature must be a string")

            if isinstance(username, str):
                username = username.strip()
            elif username is not None:
                raise ValueError("username must be a string")

            if not isinstance(repo_urls, list):
                raise ValueError("repo_urls must be a list (can be empty)")

            if not repo_urls:
                return {
                    "success": False,
                    "checkpoint": None,
                    "message": "No repositories to analyze",
                    "commits_analyzed": 0,
                }

            api_key = get_llm_api_key()
            if not api_key:
                raise RuntimeError(
                    "LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init)."
                )

            github_token = get_github_token()
            gitee_token = get_gitee_token()
            missing_platforms: List[str] = []

            for repo_url in repo_urls:
                parsed = parse_repo_url(repo_url)
                if not parsed:
                    continue

                platform, _, _ = parsed
                if platform == "github" and not github_token and "github" not in missing_platforms:
                    missing_platforms.append("github")
                elif platform == "gitee" and not gitee_token and "gitee" not in missing_platforms:
                    missing_platforms.append("gitee")

            if missing_platforms:
                missing_tokens = []
                if "github" in missing_platforms:
                    missing_tokens.append("GitHub Token (GITHUB_TOKEN)")
                if "gitee" in missing_platforms:
                    missing_tokens.append("Gitee Token (GITEE_TOKEN)")
                raise RuntimeError(
                    f"Missing required platform tokens: {', '.join(missing_tokens)}. "
                    "Please configure them in Settings (LLM Settings) before analyzing. "
                    "Without tokens, API rate limits are very low (~60 requests/hour for GitHub, lower for Gitee)."
                )

            inferred_all_authors: List[str] = []
            if not username:
                if username_is_explicit_null:
                    inferred_all_authors = _infer_gitee_authors_from_commits(repo_urls)
                    if inferred_all_authors:
                        username = inferred_all_authors[0]
                        emit("section", {
                            "title": "识别仓库作者",
                            "status": "done",
                            "author_count": len(inferred_all_authors),
                        })

                if not username:
                    username = _infer_username_from_first_commit(repo_urls)
                    if not username:
                        raise RuntimeError(
                            "Missing required field: username. Unable to infer default username from first commit author."
                        )

            merged_aliases: List[str] = []
            seen_aliases = set()
            for candidate in [username, *inferred_all_authors, *aliases]:
                if not isinstance(candidate, str):
                    continue
                cleaned = candidate.strip()
                if not cleaned:
                    continue
                key = cleaned.lower()
                if key in seen_aliases:
                    continue
                seen_aliases.add(key)
                merged_aliases.append(cleaned)
            aliases = merged_aliases

            plugin_id = resolve_plugin_id(plugin)
            forced_checker_id = forced_checker.strip() if forced_checker else None
            worktree_base_value = worktree_base.strip() if worktree_base else "build"
            if worktree_base_value not in ("build", "temp"):
                worktree_base_value = "build"

            checkpoint_strategy_value = checkpoint_strategy.strip() if checkpoint_strategy else "none"
            if checkpoint_strategy_value not in ("period", "none"):
                checkpoint_strategy_value = "none"

            start_sha_value = start_sha.strip() if start_sha else None
            end_sha_value = end_sha.strip() if end_sha else None

            emit("section", {
                "title": "开始整体评估",
                "status": "running",
                "username": username,
                "repo_count": len(repo_urls),
            })

            response = analyze_growth_trajectory(
                username,
                repo_urls,
                aliases,
                plugin_id,
                ONE_OFF_PRIMARY_MODEL,
                language,
                forced_checker_id,
                worktree_base_value,
                checkpoint_strategy_value,
                start_sha_value,
                end_sha_value,
                expected_feature,
                emit,
            )

            if not response.success or not response.trajectory or not response.trajectory.checkpoints:
                return {
                    "success": False,
                    "checkpoint": None,
                    "message": f"{ONE_OFF_PRIMARY_MODEL} analysis failed: {response.message}",
                    "commits_analyzed": 0,
                    "model_judging": {
                        "primary_models": list(ONE_OFF_PRIMARY_MODELS),
                        "synthesis_model": None,
                        "failed_model": ONE_OFF_PRIMARY_MODEL,
                    },
                }

            checkpoint = response.trajectory.checkpoints[-1]
            checkpoint_data = checkpoint.model_dump()
            commit_count = (
                (checkpoint_data.get("commits_range") or {}).get("commit_count")
                or 0
            )

            return {
                "success": True,
                "checkpoint": checkpoint_data,
                "message": f"Created final one-off judgment using {ONE_OFF_PRIMARY_MODEL}.",
                "commits_analyzed": commit_count,
                "model_judging": {
                    "primary_models": list(ONE_OFF_PRIMARY_MODELS),
                    "synthesis_model": None,
                    "conflicts_detected": False,
                },
            }

        yield format_sse_event("section", {"title": "连接已建立", "status": "done"})
        task = loop.run_in_executor(None, run_analysis)

        while True:
            if task.done():
                while not queue.empty():
                    event, data = queue.get_nowait()
                    yield format_sse_event(event, data)
                try:
                    result = task.result()
                    yield format_sse_event("result", result)
                    yield format_sse_event("done", {"finish_reason": "stop"})
                except Exception as e:
                    yield format_sse_event("error", {"message": str(e)})
                break

            try:
                event, data = await asyncio.wait_for(queue.get(), timeout=15)
                yield format_sse_event(event, data)
            except asyncio.TimeoutError:
                yield format_sse_event("heartbeat", {"status": "running"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _run_one_off_poll_job(
    job_id: str,
    request_body: Dict[str, Any],
    plugin: str,
    model: str,
    language: str,
    forced_checker: str,
    worktree_base: str,
    checkpoint_strategy: str,
    start_sha: str,
    end_sha: str,
) -> None:
    buffer = ""
    try:
        response = await analyze_trajectory_one_off_stream(
            request_body=request_body,
            plugin=plugin,
            model=model,
            language=language,
            forced_checker=forced_checker,
            worktree_base=worktree_base,
            checkpoint_strategy=checkpoint_strategy,
            start_sha=start_sha,
            end_sha=end_sha,
        )

        async for chunk in response.body_iterator:
            text = (
                chunk.decode("utf-8", errors="replace")
                if isinstance(chunk, bytes)
                else str(chunk)
            )
            buffer += text
            events, buffer = _parse_sse_buffer(buffer)
            for event, data in events:
                _trajectory_poll_store.append_event(job_id, event, data)

        if buffer.strip():
            events, _ = _parse_sse_buffer(f"{buffer}\n\n")
            for event, data in events:
                _trajectory_poll_store.append_event(job_id, event, data)
    except Exception as exc:
        message = f"Trajectory analysis poll job failed: {exc}"
        _trajectory_poll_store.append_event(job_id, "error", {"message": message})
        _trajectory_poll_store.finish_job(job_id, error=message)
        return

    _trajectory_poll_store.finish_job(job_id)


@router.post("/api/trajectory/analyze_one_off_poll")
async def start_trajectory_analyze_one_off_poll(
    request_body: Dict[str, Any],
    plugin: str = Query("zgc_ai_native_2026"),
    model: str = Query(DEFAULT_LLM_MODEL),
    language: str = Query("zh-CN"),
    forced_checker: str = Query(""),
    worktree_base: str = Query("build"),
    checkpoint_strategy: str = Query("none"),
    start_sha: str = Query(""),
    end_sha: str = Query(""),
) -> JSONResponse:
    """Start a durable one-off trajectory analysis job and return its poll URL."""
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    _trajectory_poll_store.cleanup()
    job_id = uuid.uuid4().hex
    _trajectory_poll_store.create_job(job_id)
    asyncio.create_task(
        _run_one_off_poll_job(
            job_id=job_id,
            request_body=request_body,
            plugin=plugin,
            model=model,
            language=language,
            forced_checker=forced_checker,
            worktree_base=worktree_base,
            checkpoint_strategy=checkpoint_strategy,
            start_sha=start_sha,
            end_sha=end_sha,
        )
    )

    return JSONResponse(
        {
            "job_id": job_id,
            "poll_url": f"/api/trajectory/analyze_one_off_poll/{job_id}",
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/trajectory/analyze_one_off_poll/{job_id}")
async def get_trajectory_analyze_one_off_poll(
    job_id: str,
    cursor: int = Query(0, ge=0),
) -> JSONResponse:
    """Return stored events for a durable one-off trajectory analysis job."""
    _trajectory_poll_store.cleanup()
    status = _trajectory_poll_store.get_job(job_id, cursor=cursor)
    if status is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    return JSONResponse(status, headers={"Cache-Control": "no-store"})
