"""Internal synthesis and historical evidence recovery. No identity recollection."""

import hashlib
import hmac
import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from evaluator.collectors.github import GitHubCollector
from evaluator.collectors.gitee import GiteeCollector
from evaluator.config import DEFAULT_LLM_MODEL, get_github_token, get_gitee_token, get_llm_api_key
from evaluator.paths import get_data_dir
from evaluator.plugin_registry import load_scan_module
from evaluator.utils import parse_repo_url


async def verify_synthesis_token(x_synthesis_token: str = Header(default="")):
    expected = os.getenv("OSCANNER_SYNTHESIS_TOKEN", "")
    if not expected:
        raise HTTPException(503, "Internal synthesis token is not configured")
    if not x_synthesis_token or not hmac.compare_digest(expected, x_synthesis_token):
        raise HTTPException(401, "Invalid synthesis token")


router = APIRouter(prefix="/api/internal", dependencies=[Depends(verify_synthesis_token)])


class EvidenceSynthesisRequest(BaseModel):
    username: str = "saved evaluation"
    language: str = "zh-CN"
    model: str | None = None
    bundles: list[dict[str, Any]] = Field(default_factory=list)
    commits: list[dict[str, Any]] = Field(default_factory=list)
    collaboration_evidence: list[dict[str, Any]] = Field(default_factory=list)
    recover_original_evidence: bool = False


def recover_commits(commits):
    cache = get_data_dir() / "historical_commit_details"
    cache.mkdir(parents=True, exist_ok=True)
    github = GitHubCollector(token=get_github_token())
    gitee = GiteeCollector(token=os.getenv("GITEE_ENTERPRISE_TOKEN"), public_token=get_gitee_token())
    unique = {}
    for commit in commits:
        url = commit.get("repo_url") or ""
        if not url and commit.get("owner") and commit.get("repo"):
            url = f"https://{commit.get('platform', 'github')}.com/{commit['owner']}/{commit['repo']}"
        parsed = parse_repo_url(url)
        sha = str(commit.get("sha") or commit.get("hash") or "")
        if not parsed or not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
            raise ValueError("Archived commit requires a valid repository and full immutable SHA")
        key = (*parsed, sha.lower())
        candidate = {**commit, "platform": parsed[0], "owner": parsed[1], "repo": parsed[2],
                     "repo_full_name": f"{parsed[1]}/{parsed[2]}", "repo_url": url, "sha": sha.lower()}
        if key not in unique or len(candidate.get("files") or []) > len(unique[key].get("files") or []):
            unique[key] = candidate

    def recover(commit):
        if (isinstance(commit.get("files"), list) and commit["files"] and not commit.get("detail_incomplete")
                and all(isinstance(file, dict) and "patch" in file for file in commit["files"])):
            return commit
        identity = f"{commit['repo_url']}@{commit['sha']}"
        path = cache / (hashlib.sha256(identity.encode()).hexdigest() + ".json")
        detail = None
        if path.exists():
            try:
                detail = json.loads(path.read_text())
            except (ValueError, OSError):
                pass
        if detail is None:
            try:
                if commit["platform"] == "github":
                    detail = github.fetch_commit_data(commit["owner"], commit["repo"], commit["sha"])
                else:
                    detail = gitee.fetch_commit_data(commit["owner"], commit["repo"], commit["sha"], is_enterprise="z.gitee.cn" in commit["repo_url"])
            except Exception:
                raise ValueError(f"Original commit unavailable: {identity}") from None
            if not isinstance(detail, dict) or not isinstance(detail.get("files"), list):
                raise ValueError(f"Original commit details unavailable: {identity}")
            if str(detail.get("sha") or "").lower() != commit["sha"]:
                raise ValueError(f"Recovered commit SHA mismatch: {identity}")
            # GitHub's single response can truncate large commits at the page boundary.
            if commit["platform"] == "github" and len(detail["files"]) >= 3000 and not detail.get('file_listing_complete'):
                raise ValueError(f"Original commit file listing incomplete: {identity}")
            with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as handle:
                json.dump(detail, handle, ensure_ascii=False)
            os.replace(handle.name, path)
        return {**commit, "files": detail["files"], "stats": detail.get("stats", {}), "detail_incomplete": False}

    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(recover, unique.values()))


def synthesize(request: EvidenceSynthesisRequest):
    _, module, _ = load_scan_module("zgc_ai_native_2026")
    evaluator = module.create_commit_evaluator(
        data_dir=str(get_data_dir() / "evidence_synthesis"), api_key=get_llm_api_key(),
        model=request.model or DEFAULT_LLM_MODEL, language=request.language,
        collaboration_evidence={"items": request.collaboration_evidence},
    )
    if request.bundles and (request.commits or request.recover_original_evidence):
        raise ValueError("Supply evidence bundles or archived commits, not both")
    if request.bundles:
        sources, facts = {}, []
        for bundle in request.bundles:
            for source in bundle.get("sources", []):
                if source["id"] in sources and sources[source["id"]] != source:
                    raise ValueError("Conflicting source identity")
                sources[source["id"]] = source
            facts.extend(bundle.get("facts", []))
        evaluation = evaluator.synthesize_evidence(list(sources.values()), facts)
    elif request.commits:
        commits = recover_commits(request.commits) if request.recover_original_evidence else request.commits
        evaluation = evaluator._evaluate_evidence(commits, request.username, load_files=False)
        return {"success": True, "evaluation": evaluation, "commits": commits}
    else:
        raise ValueError("No archived commits or evidence bundles supplied")
    return {"success": True, "evaluation": evaluation}


@router.post("/synthesize")
async def synthesize_endpoint(request: EvidenceSynthesisRequest):
    try:
        return await run_in_threadpool(synthesize, request)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from None
