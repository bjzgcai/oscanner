"""Evaluation routes - author evaluation endpoints."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from evaluator.paths import get_platform_data_dir, get_platform_eval_dir
from evaluator.plugin_registry import load_scan_module, PluginLoadError
from evaluator.config import get_llm_api_key, DEFAULT_LLM_MODEL, get_gitee_token
from evaluator.utils import load_commits_from_local
from evaluator.schemas import EvaluationResponseSchema
from evaluator.services import (
    resolve_plugin_id,
    get_evaluation_cache_path,
    get_plugins_snapshot,
    evaluate_author_incremental,
    get_repo_data_dir,
    fetch_gitee_commits,
    merge_evaluations_logic,
)

router = APIRouter()


@router.post("/api/evaluate/{owner}/{repo}/{author}", response_model=EvaluationResponseSchema)
async def evaluate_author(
    owner: str,
    repo: str,
    author: str,
    use_chunking: bool = Query(True),
    use_cache: bool = Query(True),
    model: str = Query(DEFAULT_LLM_MODEL),
    platform: str = Query("github"),
    plugin: str = Query(""),
    language: str = Query("en-US"),
    parallel_chunking: bool = Query(True),
    max_parallel_workers: int = Query(3),
    request_body: Optional[Dict[str, Any]] = None
):
    """Evaluate an author with auto-sync and incremental evaluation."""
    try:
        # Check LLM configuration before analysis
        api_key = get_llm_api_key()
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init)."
            )

        plugin_id = resolve_plugin_id(plugin)

        # Load plugin
        try:
            meta, scan_mod, scan_path = load_scan_module(plugin_id)
        except PluginLoadError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Parse aliases
        aliases = None
        if request_body and isinstance(request_body, dict):
            aliases_list = request_body.get("aliases")
            if aliases_list and isinstance(aliases_list, list):
                aliases = [str(a).lower().strip() for a in aliases_list if a]

        # Normalize parameters (handle Query objects and type conversion)
        # When this function is called programmatically, Query objects aren't resolved by FastAPI
        from fastapi.params import Query as QueryType

        if not isinstance(model, str):
            model = DEFAULT_LLM_MODEL

        # Ensure parallel_chunking and max_parallel_workers are proper types, not Query objects
        if isinstance(parallel_chunking, QueryType):
            parallel_chunking = parallel_chunking.default
        parallel_chunking = bool(parallel_chunking)

        if isinstance(max_parallel_workers, QueryType):
            max_parallel_workers = max_parallel_workers.default
        max_parallel_workers = int(max_parallel_workers)

        # Check data directory
        data_dir = get_platform_data_dir(platform, owner, repo)
        if not data_dir.exists():
            raise HTTPException(status_code=404, detail=f"No local data found for {platform}/{owner}/{repo}. Please extract data first.")

        # Handle multi-alias evaluation
        if aliases and len(aliases) > 1:
            print(f"[Aliases] Evaluating {len(aliases)} identities separately then merging...")
            evaluations_to_merge = []
            default_plugin_id = get_plugins_snapshot()[1]

            for alias in aliases:
                print(f"[Aliases] Evaluating identity: {alias}")
                commits = load_commits_from_local(data_dir, limit=None)
                if not commits:
                    continue

                # Load previous evaluation
                eval_dir = get_platform_eval_dir(platform, owner, repo)
                eval_path = get_evaluation_cache_path(eval_dir, alias, plugin_id, default_plugin_id)
                previous_evaluation = None

                if use_cache and eval_path.exists():
                    try:
                        with open(eval_path, 'r', encoding='utf-8') as f:
                            previous_evaluation = json.load(f)
                    except Exception as e:
                        print(f"[Aliases] ⚠ Failed to load cached evaluation: {e}")

                # Evaluate (api_key already checked at the start)

                def _factory():
                    return scan_mod.create_commit_evaluator(
                        data_dir=str(data_dir),
                        api_key=api_key,
                        model=model,
                        mode="moderate",
                        language=language,
                        parallel_chunking=parallel_chunking,
                        max_parallel_workers=max_parallel_workers,
                    )

                evaluation = evaluate_author_incremental(
                    commits=commits,
                    author=alias,
                    previous_evaluation=previous_evaluation,
                    data_dir=data_dir,
                    model=model,
                    use_chunking=use_chunking,
                    api_key=api_key,
                    aliases=[alias],
                    evaluator_factory=_factory,
                    parallel_chunking=parallel_chunking,
                    max_parallel_workers=max_parallel_workers,
                )
                evaluation["plugin"] = plugin_id
                if meta:
                    evaluation["plugin_version"] = meta.version

                # Save
                if use_cache:
                    eval_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(eval_path, 'w', encoding='utf-8') as f:
                        json.dump(evaluation, f, indent=2, ensure_ascii=False)

                alias_commits = [c for c in commits if any(a.lower() in str(c.get("author", "")).lower() for a in [alias])]
                evaluations_to_merge.append({
                    "author": alias,
                    "weight": len(alias_commits),
                    "evaluation": evaluation
                })

            # Merge
            if len(evaluations_to_merge) >= 2:
                merged_eval = merge_evaluations_logic(evaluations_to_merge, model)
                return {
                    "success": True,
                    "evaluation": merged_eval,
                    "metadata": {"cached": False, "timestamp": datetime.now().isoformat(), "source": "merged_aliases"}
                }
            elif len(evaluations_to_merge) == 1:
                return {
                    "success": True,
                    "evaluation": evaluations_to_merge[0]["evaluation"],
                    "metadata": {"cached": False, "timestamp": datetime.now().isoformat(), "source": "single_alias"}
                }
            else:
                raise HTTPException(status_code=404, detail="No commits found for any aliases")

        # Single author evaluation
        print(f"[Evaluation] Loading commits for {author}...")
        commits = load_commits_from_local(data_dir, limit=None)
        if not commits:
            raise HTTPException(status_code=404, detail=f"No commits found in local data for {owner}/{repo}")

        # Load previous evaluation
        eval_dir = get_platform_eval_dir(platform, owner, repo)
        default_plugin_id = get_plugins_snapshot()[1]
        eval_path = get_evaluation_cache_path(eval_dir, author, plugin_id, default_plugin_id)
        previous_evaluation = None

        if use_cache and eval_path.exists():
            try:
                with open(eval_path, 'r', encoding='utf-8') as f:
                    previous_evaluation = json.load(f)
            except Exception as e:
                print(f"[Evaluation] ⚠ Failed to load previous evaluation: {e}")

        # Evaluate (api_key already checked at the start)

        def _factory():
            return scan_mod.create_commit_evaluator(
                data_dir=str(data_dir),
                api_key=api_key,
                model=model,
                mode="moderate",
                language=language,
                parallel_chunking=parallel_chunking,
                max_parallel_workers=max_parallel_workers,
            )

        evaluation = evaluate_author_incremental(
            commits=commits,
            author=author,
            previous_evaluation=previous_evaluation,
            data_dir=data_dir,
            model=model,
            use_chunking=use_chunking,
            api_key=api_key,
            aliases=aliases,
            evaluator_factory=_factory,
            parallel_chunking=parallel_chunking,
            max_parallel_workers=max_parallel_workers,
        )
        evaluation["plugin"] = plugin_id
        if meta:
            evaluation["plugin_version"] = meta.version

        # Save
        if use_cache:
            eval_path.parent.mkdir(parents=True, exist_ok=True)
            with open(eval_path, 'w', encoding='utf-8') as f:
                json.dump(evaluation, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "evaluation": evaluation,
            "metadata": {"cached": False, "timestamp": datetime.now().isoformat()}
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/api/merge-evaluations")
async def merge_evaluations(request: dict):
    """Merge multiple evaluations using LLM-based weighted combination."""
    evaluations_data = request.get("evaluations", [])
    model = request.get("model", DEFAULT_LLM_MODEL)

    merged_evaluation = merge_evaluations_logic(evaluations_data, model)

    return {
        "success": True,
        "merged_evaluation": merged_evaluation
    }


@router.post("/api/gitee/evaluate/{owner}/{repo}/{contributor}", response_model=EvaluationResponseSchema)
async def evaluate_gitee_contributor(
    owner: str,
    repo: str,
    contributor: str,
    limit: int = Query(150, ge=1, le=200),
    use_cache: bool = Query(True),
    is_enterprise: bool = Query(False),
    plugin: str = Query(""),
):
    """Evaluate a Gitee contributor."""
    platform = "gitee"

    try:
        # Check LLM configuration before analysis
        api_key = get_llm_api_key()
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="LLM not configured. Please set OPEN_ROUTER_KEY / OPENAI_API_KEY / OSCANNER_LLM_API_KEY (or run oscanner init)."
            )

        # Get commits
        commits = fetch_gitee_commits(owner, repo, 500, is_enterprise)

        # Load plugin
        plugin_id = resolve_plugin_id(plugin)
        meta, scan_mod, scan_path = load_scan_module(plugin_id)

        evaluator = scan_mod.create_commit_evaluator(
            data_dir=str(get_repo_data_dir(platform, owner, repo)),
            api_key=api_key,
            model=DEFAULT_LLM_MODEL,
            mode="moderate",
        )

        # Evaluate
        try:
            evaluation = evaluator.evaluate_engineer(
                commits=commits,
                username=contributor,
                max_commits=limit,
                load_files=True
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"LLM evaluation failed: {str(e)}")

        if not evaluation or "scores" not in evaluation:
            raise HTTPException(status_code=404, detail=f"Contributor '{contributor}' not found")

        return {
            "success": True,
            "evaluation": {
                "username": evaluation.get("username", contributor),
                "mode": evaluation.get("mode", "moderate"),
                "total_commits_analyzed": evaluation.get("total_commits_analyzed", 0),
                "files_loaded": evaluation.get("files_loaded", 0),
                "scores": evaluation.get("scores", {}),
                "commits_summary": evaluation.get("commits_summary", {}),
                "plugin": plugin_id,
                "plugin_version": meta.version,
            },
            "metadata": {"cached": False, "timestamp": datetime.now().isoformat()}
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")
