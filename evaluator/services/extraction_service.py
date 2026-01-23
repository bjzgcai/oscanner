"""Data extraction service for GitHub and Gitee repositories."""

import sys
import subprocess
import json
import requests
from pathlib import Path
from typing import List, Dict, Any
from fastapi import HTTPException

from evaluator.paths import get_platform_data_dir
from evaluator.config import get_github_token, get_gitee_token
from evaluator.utils import get_author_from_commit


def extract_github_data(owner: str, repo: str) -> bool:
    """Extract GitHub repository data using extraction tool"""
    try:
        repo_url = f"https://github.com/{owner}/{repo}"
        output_dir = get_platform_data_dir("github", owner, repo)

        print(f"\n{'='*60}")
        print(f"Extracting GitHub data for {owner}/{repo}...")
        print(f"{'='*60}")

        # Construct command (module execution; does not rely on CWD)
        cmd = [
            sys.executable,
            "-m",
            "evaluator.tools.extract_repo_data_moderate",
            "--repo-url",
            repo_url,
            "--out",
            str(output_dir),
            "--max-commits",
            "500",  # Fetch enough to cover all contributors
        ]

        gh_token = get_github_token()
        if gh_token:
            cmd.extend(["--token", gh_token])

        # Run extraction tool
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 minute timeout

        if result.returncode != 0:
            print(f"✗ Extraction failed: {result.stderr}")
            return False

        print(f"✓ Extraction successful")
        print(result.stdout)
        return True

    except subprocess.TimeoutExpired:
        print(f"✗ Extraction timeout after 5 minutes")
        return False
    except Exception as e:
        print(f"✗ Extraction error: {e}")
        import traceback
        traceback.print_exc()
        return False


def fetch_github_commits(owner: str, repo: str, limit: int = 100) -> list:
    """Fetch commits from GitHub API"""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    headers = {}
    gh_token = get_github_token()
    if gh_token:
        headers["Authorization"] = f"token {gh_token}"

    params = {"per_page": min(limit, 100)}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch GitHub commits: {str(e)}")


def fetch_gitee_commits(owner: str, repo: str, limit: int = 100, is_enterprise: bool = False) -> list:
    """Fetch commits from Gitee API"""
    if is_enterprise:
        url = f"https://api.gitee.com/enterprises/{owner}/repos/{repo}/commits"
    else:
        url = f"https://api.gitee.com/repos/{owner}/{repo}/commits"

    # Gitee uses `access_token` query param (Authorization header is not reliable for v5 APIs).
    headers = {}
    params = {"per_page": min(limit, 100)}
    gitee_token = get_gitee_token()
    if gitee_token:
        params["access_token"] = gitee_token

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Gitee commits: {str(e)}")


def extract_gitee_data(owner: str, repo: str, max_commits: int = 200) -> bool:
    """
    Extract Gitee repository data into platform-specific directory similar to GitHub extractor.

    This is a minimal extractor used by the multi-repo compare workflow.
    It fetches commit list then fetches per-commit details (which may include files/diffs depending on API support).
    """
    try:
        data_dir = get_platform_data_dir("gitee", owner, repo)
        data_dir.mkdir(parents=True, exist_ok=True)
        commits_dir = data_dir / "commits"
        commits_dir.mkdir(parents=True, exist_ok=True)

        # 1) Fetch commits list (paginated)
        commits: List[Dict[str, Any]] = []
        page = 1
        per_page = 100
        while len(commits) < max_commits:
            api_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/commits"
            params: Dict[str, Any] = {"per_page": per_page, "page": page}
            gitee_token = get_gitee_token()
            if gitee_token:
                params["access_token"] = gitee_token
            resp = requests.get(api_url, params=params, timeout=30)
            if resp.status_code != 200:
                print(f"✗ Gitee commits list failed: {resp.status_code} {resp.text[:200]}")
                return False
            batch = resp.json()
            if not isinstance(batch, list) or not batch:
                break
            commits.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        commits = commits[:max_commits]

        with open(data_dir / "commits_list.json", "w", encoding="utf-8") as f:
            json.dump(commits, f, indent=2, ensure_ascii=False)

        # 2) Fetch per-commit details
        commits_index = []
        for c in commits:
            sha = c.get("sha")
            if not sha:
                continue
            detail_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/commits/{sha}"
            params = {}
            gitee_token = get_gitee_token()
            if gitee_token:
                params["access_token"] = gitee_token
            dresp = requests.get(detail_url, params=params, timeout=30)
            if dresp.status_code != 200:
                # Fallback to list item
                detail = c
            else:
                detail = dresp.json()

            with open(commits_dir / f"{sha}.json", "w", encoding="utf-8") as f:
                json.dump(detail, f, indent=2, ensure_ascii=False)

            commit_msg = detail.get("commit", {}).get("message", "") if isinstance(detail, dict) else ""
            author_name = get_author_from_commit(detail) if isinstance(detail, dict) else ""
            commit_date = ""
            if isinstance(detail, dict):
                commit_date = detail.get("commit", {}).get("author", {}).get("date", "") or detail.get("commit", {}).get("committer", {}).get("date", "")
            file_list = []
            if isinstance(detail, dict):
                file_list = [fi.get("filename") for fi in (detail.get("files") or []) if isinstance(fi, dict) and fi.get("filename")]

            commits_index.append(
                {
                    "sha": sha,
                    "message": (commit_msg.split("\n")[0] if commit_msg else "")[:100],
                    "author": author_name or "",
                    "date": commit_date or "",
                    "files_changed": len(file_list),
                    "files": file_list,
                }
            )

        with open(data_dir / "commits_index.json", "w", encoding="utf-8") as f:
            json.dump(commits_index, f, indent=2, ensure_ascii=False)

        # 3) repo_info.json
        repo_info = {"name": f"{owner}/{repo}", "full_name": f"{owner}/{repo}", "owner": owner, "platform": "gitee"}
        with open(data_dir / "repo_info.json", "w", encoding="utf-8") as f:
            json.dump(repo_info, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"✗ Gitee extraction failed: {e}")
        return False


def get_repo_data_dir(platform: str, owner: str, repo: str) -> Path:
    """Get or create platform-specific data directory for repository"""
    data_dir = get_platform_data_dir(platform, owner, repo)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
