"""Data extraction service for GitHub and Gitee repositories."""

import sys
import subprocess
import json
import os
import socket
import base64
import shutil
import tempfile
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from fastapi import HTTPException

from evaluator.paths import get_platform_data_dir
from evaluator.config import get_github_token, get_gitee_token
from evaluator.utils import get_author_from_commit


def get_requests_session() -> requests.Session:
    """
    Create a requests session with proxy support and better error handling.
    Respects HTTP_PROXY, HTTPS_PROXY, and NO_PROXY environment variables.
    """
    session = requests.Session()
    
    # Configure proxies from environment variables
    proxies = {}
    http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
    https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
    
    if http_proxy:
        proxies['http'] = http_proxy
    if https_proxy:
        proxies['https'] = https_proxy
    
    if proxies:
        session.proxies.update(proxies)
        print(f"[Network] Using proxies: {proxies}")
    
    return session


def check_dns_resolution(hostname: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check DNS resolution for a hostname and detect DNS hijacking.
    Returns (success, error_message, resolved_ip)
    """
    try:
        ip = socket.gethostbyname(hostname)
        # Check if the resolved IP looks suspicious (DNS hijacking)
        # Common hijacked IPs for gitee.com include baiduads.com domains
        try:
            reverse_dns = socket.gethostbyaddr(ip)[0]
            if 'baiduads' in reverse_dns.lower() or 'ads' in reverse_dns.lower():
                return False, f"DNS hijacking detected: {hostname} resolves to {ip} (reverse DNS: {reverse_dns})", ip
        except:
            pass  # Reverse DNS lookup failed, continue
        
        return True, None, ip
    except socket.gaierror as e:
        return False, str(e), None
    except Exception as e:
        return False, f"Unexpected error: {str(e)}", None


def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _run_git(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _map_git_status(status_code: str) -> str:
    if not status_code:
        return "modified"
    code = status_code[0].upper()
    return {
        "A": "added",
        "M": "modified",
        "D": "removed",
        "R": "renamed",
        "C": "copied",
        "T": "changed",
        "U": "unmerged",
    }.get(code, "modified")


def _parse_git_diff_by_file(diff_text: str) -> Dict[str, str]:
    patches: Dict[str, str] = {}
    current_file = None
    current_lines: List[str] = []

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current_file and current_lines:
                patches[current_file] = "\n".join(current_lines)
            current_lines = [line]
            parts = line.split(" ")
            if len(parts) >= 4 and parts[3].startswith("b/"):
                current_file = parts[3][2:]
            else:
                current_file = None
            continue
        if current_file is not None:
            current_lines.append(line)

    if current_file and current_lines:
        patches[current_file] = "\n".join(current_lines)

    return patches


def _extract_github_data_via_git(owner: str, repo: str, output_dir: Path, max_commits: int = 500) -> bool:
    """
    Fallback extractor that uses git CLI instead of GitHub API.
    Useful when GitHub REST API is unavailable (e.g., rate limit).
    """
    repo_url = f"https://github.com/{owner}/{repo}.git"
    output_dir.mkdir(parents=True, exist_ok=True)

    commits_dir = output_dir / "commits"
    files_dir = output_dir / "files"
    shutil.rmtree(commits_dir, ignore_errors=True)
    shutil.rmtree(files_dir, ignore_errors=True)
    commits_dir.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix=f"{owner}_{repo}_") as tmpdir:
            clone_dir = Path(tmpdir) / "repo"

            clone_cmd = [
                "git",
                "clone",
                "--no-tags",
                "--single-branch",
                "--depth",
                str(max_commits),
                repo_url,
                str(clone_dir),
            ]
            clone_result = _run_git(clone_cmd, timeout=300)
            if clone_result.returncode != 0:
                print(f"✗ Git fallback clone failed: {clone_result.stderr}")
                return False

            branch_result = _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=clone_dir, timeout=30)
            default_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"

            rev_list_cmd = ["git", "rev-list", "--max-count", str(max_commits), "HEAD"]
            rev_list_result = _run_git(rev_list_cmd, cwd=clone_dir, timeout=60)
            if rev_list_result.returncode != 0:
                print(f"✗ Git fallback rev-list failed: {rev_list_result.stderr}")
                return False

            shas = [line.strip() for line in rev_list_result.stdout.splitlines() if line.strip()]
            commits_index: List[Dict[str, Any]] = []
            commits_list: List[Dict[str, Any]] = []
            files_context: Dict[str, int] = {}

            for sha in shas:
                meta_result = _run_git(
                    [
                        "git",
                        "show",
                        "-s",
                        "--format=%H%n%an%n%ae%n%aI%n%cn%n%ce%n%cI%n%B",
                        sha,
                    ],
                    cwd=clone_dir,
                    timeout=30,
                )
                if meta_result.returncode != 0:
                    continue

                meta_lines = meta_result.stdout.splitlines()
                if len(meta_lines) < 7:
                    continue

                subject = meta_lines[7] if len(meta_lines) > 7 else ""
                full_message = "\n".join(meta_lines[7:]).strip() if len(meta_lines) > 7 else subject

                name_status_result = _run_git(
                    ["git", "show", "--name-status", "--format=", sha],
                    cwd=clone_dir,
                    timeout=30,
                )
                numstat_result = _run_git(
                    ["git", "show", "--numstat", "--format=", sha],
                    cwd=clone_dir,
                    timeout=30,
                )
                diff_result = _run_git(
                    ["git", "show", "--format=", "--no-color", sha],
                    cwd=clone_dir,
                    timeout=60,
                )

                if diff_result.returncode == 0:
                    with open(commits_dir / f"{sha}.diff", "w", encoding="utf-8", errors="ignore") as f:
                        f.write(diff_result.stdout)

                patch_by_file = _parse_git_diff_by_file(diff_result.stdout if diff_result.returncode == 0 else "")

                files: List[Dict[str, Any]] = []
                if name_status_result.returncode == 0:
                    for line in name_status_result.stdout.splitlines():
                        if not line.strip():
                            continue
                        parts = line.split("\t")
                        if len(parts) < 2:
                            continue

                        status_raw = parts[0]
                        status = _map_git_status(status_raw)
                        file_obj: Dict[str, Any] = {"status": status}

                        if status_raw[:1].upper() in {"R", "C"} and len(parts) >= 3:
                            old_name = parts[1]
                            new_name = parts[2]
                            file_obj["filename"] = new_name
                            file_obj["previous_filename"] = old_name
                        else:
                            file_obj["filename"] = parts[1]

                        filename = file_obj.get("filename", "")
                        if filename:
                            files_context[filename] = files_context.get(filename, 0) + 1
                            patch = patch_by_file.get(filename)
                            if patch:
                                file_obj["patch"] = patch
                        files.append(file_obj)

                additions = 0
                deletions = 0
                if numstat_result.returncode == 0:
                    for line in numstat_result.stdout.splitlines():
                        if not line.strip():
                            continue
                        parts = line.split("\t")
                        if len(parts) < 3:
                            continue
                        try:
                            if parts[0] != "-":
                                additions += int(parts[0])
                            if parts[1] != "-":
                                deletions += int(parts[1])
                        except ValueError:
                            continue

                commit_obj = {
                    "sha": meta_lines[0],
                    "commit": {
                        "author": {"name": meta_lines[1], "email": meta_lines[2], "date": meta_lines[3]},
                        "committer": {"name": meta_lines[4], "email": meta_lines[5], "date": meta_lines[6]},
                        "message": full_message,
                    },
                    "author": {"name": meta_lines[1], "email": meta_lines[2]},
                    "committer": {"name": meta_lines[4], "email": meta_lines[5]},
                    "files": files,
                    "stats": {
                        "additions": additions,
                        "deletions": deletions,
                        "total": additions + deletions,
                    },
                }

                _save_json(commits_dir / f"{sha}.json", commit_obj)
                commits_list.append(
                    {
                        "sha": meta_lines[0],
                        "commit": {
                            "author": {"name": meta_lines[1], "email": meta_lines[2], "date": meta_lines[3]},
                            "committer": {"name": meta_lines[4], "email": meta_lines[5], "date": meta_lines[6]},
                            "message": full_message,
                        },
                    }
                )
                commits_index.append(
                    {
                        "sha": meta_lines[0],
                        "message": subject[:100],
                        "author": meta_lines[1],
                        "date": meta_lines[3],
                        "files_changed": len(files),
                        "additions": additions,
                        "deletions": deletions,
                        "files": [f.get("filename", "") for f in files if f.get("filename")],
                    }
                )

            if not commits_index:
                print("✗ Git fallback extracted no commits")
                return False

            _save_json(output_dir / "commits_list.json", commits_list)
            _save_json(output_dir / "commits_index.json", commits_index)
            _save_json(
                output_dir / "repo_info.json",
                {
                    "name": repo,
                    "full_name": f"{owner}/{repo}",
                    "owner": {"login": owner},
                    "default_branch": default_branch,
                    "platform": "github",
                    "extraction_method": "git_fallback",
                },
            )

            repo_structure = []
            for root, dirs, file_names in os.walk(clone_dir):
                if ".git" in dirs:
                    dirs.remove(".git")
                rel = os.path.relpath(root, clone_dir)
                repo_structure.append(
                    {
                        "path": "" if rel == "." else rel,
                        "dirs": sorted(dirs),
                        "files": sorted(file_names),
                    }
                )
            _save_json(output_dir / "repo_structure.json", repo_structure)

            files_fetched = 0
            max_files = 100
            for path, _count in sorted(files_context.items(), key=lambda kv: -kv[1])[:max_files]:
                src_path = (clone_dir / path).resolve()
                dst_path = (files_dir / path).resolve()
                try:
                    if not src_path.exists() or not src_path.is_file():
                        continue
                    if files_dir.resolve() not in dst_path.parents and dst_path != files_dir.resolve():
                        continue
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src_path, dst_path)
                    files_fetched += 1
                except Exception:
                    continue

            first_commit = commits_index[0]
            sync_state = {
                "last_synced_at": datetime.now().isoformat(),
                "last_commit_sha": first_commit.get("sha") or first_commit.get("hash"),
                "last_commit_date": first_commit.get("date", ""),
                "total_commits_fetched": len(commits_index),
                "sync_history": [
                    {
                        "synced_at": datetime.now().isoformat(),
                        "commits_added": len(commits_index),
                        "last_sha": first_commit.get("sha") or first_commit.get("hash"),
                        "mode": "initial_extraction",
                    }
                ],
            }
            _save_json(output_dir / "sync_state.json", sync_state)

            _save_json(
                output_dir / "EXTRACTION_INFO.json",
                {
                    "repository": f"{owner}/{repo}",
                    "url": f"https://github.com/{owner}/{repo}",
                    "extraction_type": "git_fallback",
                    "description": "Git-based extraction fallback",
                    "stats": {
                        "total_commits": len(commits_index),
                        "unique_files_mentioned": len(files_context),
                        "file_contents_fetched": files_fetched,
                    },
                },
            )

            print(f"✓ Git fallback extraction successful: {len(commits_index)} commits")
            return True
    except subprocess.TimeoutExpired as e:
        print(f"✗ Git fallback timeout: {e}")
        return False
    except Exception as e:
        print(f"✗ Git fallback extraction error: {e}")
        return False


def extract_github_data(owner: str, repo: str) -> bool:
    """Extract GitHub repository data using extraction tool"""
    output_dir = get_platform_data_dir("github", owner, repo)
    try:
        repo_url = f"https://github.com/{owner}/{repo}"

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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minute timeout

        if result.returncode != 0:
            print(f"✗ Extraction failed: {result.stderr}")
            print("↻ Trying git-based fallback extraction...")
            return _extract_github_data_via_git(owner, repo, output_dir, max_commits=500)

        print(f"✓ Extraction successful")
        print(result.stdout)

        commits_dir = output_dir / "commits"
        has_commit_json = commits_dir.exists() and any(commits_dir.glob("*.json"))
        if not has_commit_json:
            print("⚠ API extraction produced no commits, trying git-based fallback...")
            return _extract_github_data_via_git(owner, repo, output_dir, max_commits=500)

        return True

    except subprocess.TimeoutExpired:
        print(f"✗ Extraction timeout after 30 minutes")
        print("↻ Trying git-based fallback extraction...")
        return _extract_github_data_via_git(owner, repo, output_dir, max_commits=500)
    except Exception as e:
        print(f"✗ Extraction error: {e}")
        import traceback
        traceback.print_exc()
        print("↻ Trying git-based fallback extraction...")
        return _extract_github_data_via_git(owner, repo, output_dir, max_commits=500)


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

    This function uses Python requests library to call Gitee API directly (not a command-line tool).
    It fetches commit list then fetches per-commit details (which may include files/diffs depending on API support).
    
    Note: Unlike GitHub extraction which uses a subprocess command, Gitee extraction uses direct API calls.
    """
    try:
        print(f"[Gitee Extraction] Starting data extraction for {owner}/{repo}")
        
        # Check token configuration first
        gitee_token = get_gitee_token()
        if not gitee_token:
            raise Exception("Gitee token not configured. Please set GITEE_TOKEN environment variable or configure it via oscanner init.")
        
        # Log token usage (masked for security)
        token_preview = f"{gitee_token[:8]}..." if len(gitee_token) > 8 else "***"
        print(f"[Gitee Extraction] Using Gitee token: {token_preview}")
        
        data_dir = get_platform_data_dir("gitee", owner, repo)
        data_dir.mkdir(parents=True, exist_ok=True)
        commits_dir = data_dir / "commits"
        commits_dir.mkdir(parents=True, exist_ok=True)

        # 1) Fetch commits list (paginated)
        commits: List[Dict[str, Any]] = []
        page = 1
        per_page = 100
        session = get_requests_session()
        
        while len(commits) < max_commits:
            api_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/commits"
            params: Dict[str, Any] = {
                "per_page": per_page,
                "page": page,
                "access_token": gitee_token
            }
            
            try:
                print(f"[Gitee] Fetching commits from: {api_url} (page {page})")
                resp = session.get(api_url, params=params, timeout=30, allow_redirects=True)
                
                if resp.status_code != 200:
                    error_detail = resp.text[:200] if resp.text else "Unknown error"
                    if resp.status_code == 401:
                        raise Exception(f"Gitee API authentication failed (401). Please check if your Gitee token is valid. Error: {error_detail}")
                    raise Exception(f"Gitee API error ({resp.status_code}): {error_detail}")
                
            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                if "Failed to resolve" in error_msg or "NameResolutionError" in error_msg or "nodename nor servname" in error_msg:
                    raise Exception(f"DNS resolution failed for gitee.com. Please check your network connection and DNS settings. Error: {error_msg}")
                elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    raise Exception(f"Request to gitee.com timed out. Please check your network connection or try again later. Error: {error_msg}")
                else:
                    raise Exception(f"Network request failed: {error_msg}")
            
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
        files_context: Dict[str, int] = {}  # Track unique files mentioned in commits

        for c in commits:
            sha = c.get("sha")
            if not sha:
                continue
            detail_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/commits/{sha}"
            params = {"access_token": gitee_token}
            try:
                dresp = session.get(detail_url, params=params, timeout=30)
                if dresp.status_code == 200:
                    detail = dresp.json()
                else:
                    # Fallback to list item if API error
                    detail = c
            except requests.exceptions.RequestException:
                # Fallback to list item if network error
                detail = c

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

                # Track files for context extraction
                for filename in file_list:
                    if filename:
                        files_context[filename] = files_context.get(filename, 0) + 1

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

        # 3) Fetch current file contents for files mentioned in diffs
        print(f"\n[Gitee] Fetching file context for {len(files_context)} unique files...")
        files_dir = data_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        files_fetched = 0
        # Sort by mention count (most changed files first) and take top 100
        sorted_files = sorted(files_context.items(), key=lambda x: -x[1])[:100]

        for i, (filepath, mention_count) in enumerate(sorted_files):
            print(f"  [{i+1}/{len(sorted_files)}] {filepath}... ", end='', flush=True)

            # Fetch current file content from Gitee API
            file_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{filepath}"
            params = {"access_token": gitee_token}

            try:
                file_resp = session.get(file_url, params=params, timeout=30)

                if file_resp.status_code != 200:
                    print("✗ API error")
                    continue

                file_obj = file_resp.json()

                # Create directory structure for the file
                file_path = files_dir / filepath
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Gitee API returns base64-encoded content
                content_b64 = file_obj.get('content', '')
                if content_b64:
                    try:
                        # Decode base64 content
                        content_bytes = base64.b64decode(content_b64)
                        # Try to decode as UTF-8, ignore errors for binary files
                        content_str = content_bytes.decode('utf-8', errors='ignore')

                        # Save file content
                        with open(file_path, 'w', encoding='utf-8', errors='ignore') as f:
                            f.write(content_str)

                        files_fetched += 1
                        print(f"✓ ({file_obj.get('size', 0)} bytes)")
                    except Exception as e:
                        print(f"✗ decode error: {e}")
                else:
                    print("✗ no content")

            except requests.exceptions.RequestException as e:
                print(f"✗ network error")
                continue
            except Exception as e:
                print(f"✗ error: {e}")
                continue

        print(f"\n  ✓ Fetched {files_fetched} file contents")

        # 4) repo_info.json
        repo_info = {"name": f"{owner}/{repo}", "full_name": f"{owner}/{repo}", "owner": owner, "platform": "gitee"}
        with open(data_dir / "repo_info.json", "w", encoding="utf-8") as f:
            json.dump(repo_info, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Gitee extraction complete:")
        print(f"  - {len(commits_index)} commits")
        print(f"  - {len(files_context)} unique files mentioned")
        print(f"  - {files_fetched} file contents fetched")

        return True
    except Exception as e:
        error_msg = str(e)
        print(f"✗ Gitee extraction failed: {error_msg}")
        # Always re-raise exceptions so callers can handle them properly
        # This ensures consistent error handling behavior
        raise


def get_repo_data_dir(platform: str, owner: str, repo: str) -> Path:
    """Get or create platform-specific data directory for repository"""
    data_dir = get_platform_data_dir(platform, owner, repo)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
