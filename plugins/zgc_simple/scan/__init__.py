"""
Default scan plugin (self-contained).

This plugin uses the traditional six-dimensional evaluation standard
documented in `engineer_level_old.md`. It provides baseline scoring
without AI-Native 2026 rubric guidance.

IMPORTANT: this plugin must not import from `evaluator/`.

Scan contract (inputs/outputs) is documented at:
- plugins/_shared/scan/README.md

Standard reference:
- engineer_level_old.md (traditional six-dimensional framework)

TRAJECTORY EVALUATION:
- This plugin supports period-based trajectory tracking with 10-commit minimum nodes
- Scores should generally increase over time unless clear negative evidence exists
- Previous checkpoint scores are used as baseline reference when available
"""

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx


def _commit_identity_values(identity: Any) -> List[str]:
    if isinstance(identity, str):
        return [identity]
    if not isinstance(identity, dict):
        return []
    return [
        str(identity.get(key)).strip()
        for key in ("login", "name", "email")
        if str(identity.get(key) or "").strip()
    ]


def _commit_email_values(identity: Any) -> List[str]:
    if isinstance(identity, str):
        return [identity] if "@" in identity else []
    if not isinstance(identity, dict):
        return []
    email = str(identity.get("email") or "").strip()
    return [email] if email else []


def _commit_emails(commit: Dict[str, Any]) -> List[str]:
    emails: List[str] = []
    seen: Set[str] = set()
    for identity in (commit.get("author"), commit.get("committer")):
        for email in _commit_email_values(identity):
            key = email.lower()
            if key not in seen:
                seen.add(key)
                emails.append(email)
    nested = commit.get("commit", {})
    if isinstance(nested, dict):
        for identity in (nested.get("author"), nested.get("committer")):
            for email in _commit_email_values(identity):
                key = email.lower()
                if key not in seen:
                    seen.add(key)
                    emails.append(email)
    return emails


class CommitEvaluatorModerate:
    """
    Self-contained moderate evaluator:
    - Uses commit diffs as evidence + optional local file contents as background
    - Calls OpenAI-compatible chat completions endpoint via requests
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        max_input_tokens: int = 190000,
        data_dir: Optional[str] = None,
        model: Optional[str] = None,
        api_base_url: Optional[str] = None,
        chat_completions_url: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        dimensions: Optional[Dict[str, str]] = None,
        dimension_instructions: Optional[Dict[str, str]] = None,
        rubric_text: Optional[str] = None,
        language: str = "en-US",
        previous_checkpoint_scores: Optional[Dict[str, Any]] = None,
        forced_checker_id: Optional[str] = None,
        expected_feature: Optional[str] = None,
    ):
        self.api_key = (
            api_key
            or os.getenv("OSCANNER_LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("OPEN_ROUTER_KEY")
        )
        self.api_base_url = (
            api_base_url
            or os.getenv("OSCANNER_LLM_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://openrouter.ai/api/v1"
        )
        self.api_url = (
            chat_completions_url
            or os.getenv("OSCANNER_LLM_CHAT_COMPLETIONS_URL")
            or f"{self.api_base_url.rstrip('/')}/chat/completions"
        )
        self.max_input_tokens = int(max_input_tokens)
        self.data_dir = Path(data_dir) if data_dir else None
        self.model = model or os.getenv("OSCANNER_LLM_MODEL") or "deepseek/deepseek-v4-pro"
        self.fallback_models = fallback_models

        self.dimensions = dimensions or {
            "ai_fullstack": "AI Model Full-Stack Development",
            "ai_architecture": "AI Native Architecture Design",
            "cloud_native": "Cloud Native Engineering",
            "open_source": "Open Source Collaboration",
            "intelligent_dev": "Intelligent Development",
            "leadership": "Engineering Leadership",
        }
        self.dimension_instructions = dimension_instructions or {
            "ai_fullstack": "Assess AI/ML model development, training, optimization, deployment.",
            "ai_architecture": "Evaluate AI-first system design, API design, microservices.",
            "cloud_native": "Assess containerization, IaC, CI/CD, deployment automation.",
            "open_source": "Evaluate collaboration quality, communication, refactoring, bug fixes.",
            "intelligent_dev": "Assess automation, tooling, testing, linting/formatting.",
            "leadership": "Evaluate technical decision-making, performance/security, best practices.",
        }
        self.rubric_text = (rubric_text or "").strip()
        self.language = language
        self.previous_checkpoint_scores = previous_checkpoint_scores
        self.forced_checker_id = forced_checker_id
        self.expected_feature = (expected_feature or "").strip()

        # Checker API base URL (default to localhost, can be overridden via env)
        self.checker_api_base = os.getenv("OSCANNER_CHECKER_API_BASE", "http://localhost:8000")
        self._checker_cache: Dict[str, Any] = {}  # Cache checker results
        
        # Create HTTP client with connection pooling for better performance
        # httpx.Client is more efficient than requests for concurrent operations
        self._http_client = httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0))

        self._file_cache: Dict[str, str] = {}
        self._repo_structure: Optional[Dict[str, Any]] = None

    def _build_expected_feature_block(self, is_chinese: bool) -> str:
        if not self.expected_feature:
            return ""

        if is_chinese:
            return (
                "\n\n期望实现功能（评价基线）:\n"
                f"{self.expected_feature}\n"
                "请只根据提交信息和提交差异判断该功能是否真正实现；文件内容只能作为理解提交的背景。"
                "如缺失或不完整，请降低相关维度评分，"
                "并在 reasoning 中说明 **期望实现功能** 和 **缺失功能**。"
            )

        return (
            "\n\nEXPECTED FEATURE BASELINE:\n"
            f"{self.expected_feature}\n"
            "Check whether the commit messages and commit diffs actually implement this feature. "
            "Use repository files only as background for understanding those commits. "
            "If it is missing or incomplete, score lower on relevant dimensions and report the expected feature and lacking feature in reasoning."
        )

    def __del__(self):
        """Clean up HTTP client on object destruction."""
        if hasattr(self, '_http_client'):
            try:
                self._http_client.close()
            except Exception:
                pass  # Ignore errors during cleanup

    def evaluate_engineer(
        self,
        *,
        commits: List[Dict[str, Any]],
        username: str,
        max_commits: Optional[int] = None,
        load_files: bool = True,
    ) -> Dict[str, Any]:
        if not commits:
            return self._get_empty_evaluation(username)

        analyzed_commits = commits if max_commits is None else commits[: int(max_commits)]
        author_commits = [c for c in analyzed_commits if self._is_commit_by_author(c, username)]
        if not author_commits:
            return self._get_empty_evaluation(username)

        if self._commits_exceed_prompt_budget(author_commits, username, load_files=load_files):
            return self._evaluate_engineer_chunked(author_commits, username, load_files=load_files)
        return self._evaluate_engineer_standard(author_commits, username, load_files=load_files)

    def _commits_exceed_prompt_budget(self, commits: List[Dict[str, Any]], username: str, *, load_files: bool) -> bool:
        file_contents: Dict[str, str] = {}
        repo_structure: Optional[Dict[str, Any]] = None
        if load_files and self.data_dir:
            file_contents = self._load_context_files(commits)
            repo_structure = self._load_repo_structure()
        context = self._build_commit_context(commits, username, file_contents=file_contents, repo_structure=repo_structure)
        prompt = self._build_evaluation_prompt(context, username)
        return self._estimate_tokens(prompt) > self.max_input_tokens

    def _prompt_token_count(self, context: str, username: str, *, chunk_idx: Optional[int] = None) -> int:
        prompt = self._build_evaluation_prompt(context, username, chunk_idx=chunk_idx)
        return self._estimate_tokens(prompt)

    def _commit_has_input_truncation(self, commits: List[Dict[str, Any]]) -> bool:
        return any(bool(c.get("_oscanner_input_truncated")) for c in commits)

    def _truncate_text_for_budget(self, text: str, max_chars: int) -> str:
        marker = "\n...[truncated to fit LLM input budget]..."
        if len(text) <= max_chars:
            return text
        if max_chars <= len(marker):
            compact_marker = "[truncated to fit LLM input budget]"
            return compact_marker[: max(1, max_chars)]
        return text[: max_chars - len(marker)] + marker

    def _copy_commit_with_text_limit(self, commit: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
        truncated = copy.deepcopy(commit)
        truncated["_oscanner_input_truncated"] = True

        if isinstance(truncated.get("message"), str):
            truncated["message"] = self._truncate_text_for_budget(truncated["message"], max_chars)
        nested_commit = truncated.get("commit")
        if isinstance(nested_commit, dict) and isinstance(nested_commit.get("message"), str):
            nested_commit["message"] = self._truncate_text_for_budget(nested_commit["message"], max_chars)

        for file_info in truncated.get("files") or []:
            if isinstance(file_info, dict) and isinstance(file_info.get("patch"), str):
                file_info["patch"] = self._truncate_text_for_budget(file_info["patch"], max_chars)
        return truncated

    def _truncate_single_commit_for_prompt_budget(
        self,
        commit: Dict[str, Any],
        username: str,
        *,
        chunk_idx: int,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        original_context = self._build_chunked_context(
            [commit],
            username,
            chunk_idx=chunk_idx,
            total_chunks=1,
            file_contents={},
            repo_structure=None,
            previous_evaluation=None,
        )
        original_tokens = self._prompt_token_count(original_context, username, chunk_idx=chunk_idx)

        text_lengths: List[int] = []
        if isinstance(commit.get("message"), str):
            text_lengths.append(len(commit["message"]))
        nested_commit = commit.get("commit")
        if isinstance(nested_commit, dict) and isinstance(nested_commit.get("message"), str):
            text_lengths.append(len(nested_commit["message"]))
        for file_info in commit.get("files") or []:
            if isinstance(file_info, dict) and isinstance(file_info.get("patch"), str):
                text_lengths.append(len(file_info["patch"]))

        high = max(text_lengths or [0])
        low = 0
        best: Optional[Dict[str, Any]] = None
        best_tokens: Optional[int] = None

        while low <= high:
            mid = (low + high) // 2
            candidate = self._copy_commit_with_text_limit(commit, mid)
            context = self._build_chunked_context(
                [candidate],
                username,
                chunk_idx=chunk_idx,
                total_chunks=1,
                file_contents={},
                repo_structure=None,
                previous_evaluation=None,
            )
            prompt_tokens = self._prompt_token_count(context, username, chunk_idx=chunk_idx)
            if prompt_tokens <= self.max_input_tokens:
                best = candidate
                best_tokens = prompt_tokens
                low = mid + 1
            else:
                high = mid - 1

        if best is None:
            raise RuntimeError(
                "A single commit exceeds the LLM input budget even after truncating commit and file input."
            )

        sha = commit.get("sha") or commit.get("hash") or ""
        message = (
            "A single commit exceeds the LLM input budget; repo input was truncated so evaluation could continue."
        )
        return best, {
            "type": "single_commit_exceeds_budget",
            "message": message,
            "commit": str(sha),
            "max_input_tokens": self.max_input_tokens,
            "estimated_tokens_before_truncation": original_tokens,
            "estimated_tokens_after_truncation": best_tokens,
            "strategy": "truncate_commit_and_file_input",
        }

    def _is_commit_by_author(self, commit: Dict[str, Any], username: str) -> bool:
        aliases = [alias.strip().lower() for alias in username.split(',') if alias.strip()]
        if not aliases:
            return False

        email_aliases = {alias for alias in aliases if "@" in alias}
        if email_aliases and any(email.lower() in email_aliases for email in _commit_emails(commit)):
            return True

        name_aliases = set(aliases) - email_aliases
        if not name_aliases:
            return False

        candidates: List[str] = []
        candidates.extend(_commit_identity_values(commit.get("author")))
        candidates.extend(_commit_identity_values(commit.get("committer")))
        nested = commit.get("commit", {})
        if isinstance(nested, dict):
            candidates.extend(_commit_identity_values(nested.get("author")))
            candidates.extend(_commit_identity_values(nested.get("committer")))

        if any(candidate.lower().strip() in name_aliases for candidate in candidates):
            return True
        return False

    def _evaluate_engineer_standard(self, commits: List[Dict[str, Any]], username: str, *, load_files: bool) -> Dict[str, Any]:
        file_contents: Dict[str, str] = {}
        repo_structure: Optional[Dict[str, Any]] = None
        if load_files and self.data_dir:
            file_contents = self._load_context_files(commits)
            repo_structure = self._load_repo_structure()

        context = self._build_commit_context(commits, username, file_contents=file_contents, repo_structure=repo_structure)
        scores = self._evaluate_with_llm(context, username)
        return {
            "username": username,
            "total_commits_analyzed": len(commits),
            "files_loaded": len(file_contents),
            "mode": "moderate",
            "scores": scores,
            "commits_summary": self._summarize_commits(commits),
        }

    def _evaluate_engineer_chunked(self, commits: List[Dict[str, Any]], username: str, *, load_files: bool) -> Dict[str, Any]:
        chunks: List[List[Dict[str, Any]]] = []
        input_budget_errors: List[Dict[str, Any]] = []
        current: List[Dict[str, Any]] = []
        for commit in commits:
            candidate = [*current, commit]
            file_contents: Dict[str, str] = {}
            repo_structure: Optional[Dict[str, Any]] = None
            if load_files and self.data_dir:
                file_contents = self._load_context_files(candidate)
                repo_structure = self._load_repo_structure()
            context = self._build_commit_context(candidate, username, file_contents=file_contents, repo_structure=repo_structure)
            prompt = self._build_evaluation_prompt(context, username, chunk_idx=len(chunks) + 1)
            if self._estimate_tokens(prompt) <= self.max_input_tokens:
                current = candidate
                continue
            if current:
                chunks.append(current)
                current = [commit]
                single_files: Dict[str, str] = {}
                single_structure: Optional[Dict[str, Any]] = None
                if load_files and self.data_dir:
                    single_files = self._load_context_files(current)
                    single_structure = self._load_repo_structure()
                single_context = self._build_commit_context(
                    current,
                    username,
                    file_contents=single_files,
                    repo_structure=single_structure,
                )
                single_prompt = self._build_evaluation_prompt(single_context, username, chunk_idx=len(chunks) + 1)
                if self._estimate_tokens(single_prompt) > self.max_input_tokens:
                    truncated_commit, budget_error = self._truncate_single_commit_for_prompt_budget(
                        commit,
                        username,
                        chunk_idx=len(chunks) + 1,
                    )
                    input_budget_errors.append(budget_error)
                    current = [truncated_commit]
                continue
            truncated_commit, budget_error = self._truncate_single_commit_for_prompt_budget(
                commit,
                username,
                chunk_idx=len(chunks) + 1,
            )
            input_budget_errors.append(budget_error)
            current = [truncated_commit]
        if current:
            chunks.append(current)

        repo_structure = None
        if load_files and self.data_dir:
            repo_structure = self._load_repo_structure()

        accumulated = None
        all_files: Dict[str, str] = {}
        for idx, chunk in enumerate(chunks, 1):
            chunk_files: Dict[str, str] = {}
            if load_files and self.data_dir and not self._commit_has_input_truncation(chunk):
                chunk_files = self._load_context_files(chunk)
                all_files.update(chunk_files)
            context = self._build_chunked_context(
                chunk,
                username,
                chunk_idx=idx,
                total_chunks=len(chunks),
                file_contents=chunk_files,
                repo_structure=repo_structure if idx == 1 else None,
                previous_evaluation=accumulated,
            )
            chunk_scores = self._evaluate_with_llm(context, username, chunk_idx=idx)
            if accumulated is None:
                accumulated = chunk_scores
            else:
                accumulated = self._merge_evaluations(accumulated, chunk_scores, idx)

        if accumulated is None:
            raise RuntimeError("LLM evaluation failed: no chunks were evaluated")

        result = {
            "username": username,
            "total_commits_analyzed": len(commits),
            "files_loaded": len(all_files),
            "mode": "moderate",
            "scores": accumulated,
            "commits_summary": self._summarize_commits(commits),
            "chunked": True,
            "chunks_processed": len(chunks),
        }
        if input_budget_errors:
            result["input_truncated"] = True
            result["warnings"] = [error["message"] for error in input_budget_errors]
            result["input_budget_errors"] = input_budget_errors
        return result

    def _extract_checker_keywords(self, commit_message: str) -> List[str]:
        """
        Extract checker keywords from commit message.
        Supports formats: /checker:xxx, /check:xxx
        """
        keywords = []
        import re
        # Match /checker:xxx or /check:xxx
        patterns = [
            r'/checker:(\w+)',
            r'/check:(\w+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, commit_message, re.IGNORECASE)
            keywords.extend(matches)
        return list(set(keywords))  # Remove duplicates

    def _get_checker_list(self) -> List[Dict[str, Any]]:
        """Query checker list from backend API."""
        import time
        start_time = time.time()
        print(f"[Checker] [Plugin] _get_checker_list() called at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
        print(f"[Checker] [Plugin] API base: {self.checker_api_base}")
        
        try:
            url = f"{self.checker_api_base}/api/checkers/list"
            print(f"[Checker] [Plugin] Requesting: {url}")
            print(f"[Checker] [Plugin] Timeout: 2s")
            
            # Short timeout for localhost - should respond quickly if service is running
            request_start = time.time()
            resp = self._http_client.get(url, timeout=2.0)
            request_elapsed = time.time() - request_start
            print(f"[Checker] [Plugin] HTTP request completed in {request_elapsed:.3f}s, status: {resp.status_code}")
            
            if resp.status_code == 200:
                parse_start = time.time()
                data = resp.json()
                parse_elapsed = time.time() - parse_start
                checkers = data.get("checkers", [])
                total_elapsed = time.time() - start_time
                print(f"[Checker] [Plugin] JSON parsing took {parse_elapsed:.3f}s")
                print(f"[Checker] [Plugin] Successfully fetched {len(checkers)} checkers in {total_elapsed:.3f}s")
                return checkers
            else:
                total_elapsed = time.time() - start_time
                print(f"[Checker] [Plugin] Warning: Failed to fetch checker list: HTTP {resp.status_code} - {resp.text[:200]} (took {total_elapsed:.3f}s)")
        except httpx.TimeoutException as e:
            total_elapsed = time.time() - start_time
            print(f"[Checker] [Plugin] ERROR: Checker API timeout after {total_elapsed:.3f}s (timeout=2s)")
            print(f"[Checker] [Plugin] Timeout exception: {type(e).__name__}: {e}")
            print(f"[Checker] [Plugin] NOTE: This timeout occurs because:")
            print(f"[Checker] [Plugin]   1. Plugin code calls checker API synchronously during evaluation")
            print(f"[Checker] [Plugin]   2. Backend service functions (evaluate_author_incremental, etc.) are synchronous")
            print(f"[Checker] [Plugin]   3. Even with httpx.Client, sync calls in async context can block if not in thread pool")
            print(f"[Checker] [Plugin]   4. Backend should run sync blocking operations in thread pool executor")
        except httpx.ConnectError as e:
            total_elapsed = time.time() - start_time
            print(f"[Checker] [Plugin] ERROR: Connection error after {total_elapsed:.3f}s")
            print(f"[Checker] [Plugin] Connection error: {type(e).__name__}: {e}")
            print(f"[Checker] [Plugin] Checker service not available at {self.checker_api_base}")
        except Exception as e:
            total_elapsed = time.time() - start_time
            print(f"[Checker] [Plugin] ERROR: Unexpected error after {total_elapsed:.3f}s")
            print(f"[Checker] [Plugin] Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        return []

    def _run_checker(
        self,
        checker_id: str,
        platform: str,
        owner: str,
        repo: str,
        commit_sha: str,
        files: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Run a checker via backend API."""
        cache_key = f"{checker_id}:{commit_sha}"
        if cache_key in self._checker_cache:
            return self._checker_cache[cache_key]

        try:
            url = f"{self.checker_api_base}/api/checkers/run"
            payload = {
                "checker_id": checker_id,
                "platform": platform,
                "owner": owner,
                "repo": repo,
                "commit_sha": commit_sha,
                "files": files,
            }
            resp = self._http_client.post(url, json=payload, timeout=60.0)
            if resp.status_code == 200:
                result = resp.json()
                self._checker_cache[cache_key] = result
                return result
            else:
                print(f"[Checker] Warning: Checker {checker_id} failed: {resp.status_code} - {resp.text}")
        except httpx.TimeoutException:
            print(f"[Checker] Info: Checker {checker_id} timeout - service may not be responding")
        except httpx.ConnectError:
            print(f"[Checker] Info: Checker service not available for {checker_id}")
        except Exception as e:
            print(f"[Checker] Warning: Failed to run checker {checker_id}: {type(e).__name__}: {e}")
        return None

    def _get_platform_owner_repo_from_data_dir(self) -> Optional[tuple]:
        """Extract platform, owner, repo from data_dir path."""
        if not self.data_dir:
            return None
        # data_dir format: .../data/<platform>/<owner>/<repo>
        parts = Path(self.data_dir).parts
        try:
            data_idx = parts.index("data")
            if len(parts) > data_idx + 3:
                return (parts[data_idx + 1], parts[data_idx + 2], parts[data_idx + 3])
        except ValueError:
            pass
        return None

    def _build_commit_context(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        *,
        file_contents: Dict[str, str],
        repo_structure: Optional[Dict[str, Any]],
    ) -> str:
        parts: List[str] = [f"User: {username}", f"Commits: {len(commits)}", ""]
        
        # Extract checker keywords and run checkers FIRST (before other content)
        # This ensures checker results are not truncated when context is too long
        checker_results_summary = []
        platform_owner_repo = self._get_platform_owner_repo_from_data_dir()
        
        if platform_owner_repo:
            platform, owner, repo = platform_owner_repo
            checker_list = self._get_checker_list()
            checker_keyword_map = {c.get("keyword"): c.get("id") for c in checker_list if c.get("enabled")}
            
            # Process commits: check for /checker:xxx keywords
            for c in commits[:50]:
                sha = c.get("sha") or c.get("hash") or ""
                msg = c.get("message") or c.get("commit", {}).get("message") or ""
                keywords = self._extract_checker_keywords(msg)
                
                for keyword in keywords:
                    checker_id = checker_keyword_map.get(keyword)
                    if checker_id:
                        result = self._run_checker(checker_id, platform, owner, repo, sha)
                        if result and result.get("success"):
                            checker_results_summary.append({
                                "checker": checker_id,
                                "commit": sha[:8],
                                "score": result.get("score", 0),
                                "message": result.get("message", ""),
                                "analysis": result.get("analysis", ""),  # Detailed analysis report
                                "details": result.get("details", []),  # Function-level details
                            })
            
            # Force checker on checkpoint (check all commits' Python files, not just last commit)
            if self.forced_checker_id and commits:
                # Collect all Python files from all commits in this checkpoint
                all_python_files = set()
                for commit in commits:
                    commit_files = commit.get("files", [])
                    if isinstance(commit_files, list):
                        for f in commit_files:
                            if isinstance(f, dict):
                                filename = f.get("filename", "")
                            else:
                                filename = str(f)
                            if filename.endswith('.py'):
                                all_python_files.add(filename)
                
                # Use the last commit SHA as the commit_sha (for API compatibility)
                last_commit = commits[-1]
                last_sha = last_commit.get("sha") or last_commit.get("hash") or ""
                if last_sha and all_python_files:
                    python_files_list = sorted(all_python_files)
                    result = self._run_checker(
                        self.forced_checker_id, 
                        platform, 
                        owner, 
                        repo, 
                        last_sha,
                        files=python_files_list
                    )
                    if result and result.get("success"):
                        # Update message to indicate checkpoint scope
                        message = result.get("message", "")
                        message = f"Checked {len(all_python_files)} Python files across {len(commits)} commits in checkpoint. {message}"
                        checker_results_summary.append({
                            "checker": self.forced_checker_id,
                            "commit": last_sha[:8],
                            "score": result.get("score", 0),
                            "message": message,
                            "analysis": result.get("analysis", ""),
                            "details": result.get("details", []),
                            "forced": True,
                        })
        
        # Append checker results FIRST (before other content) to prevent truncation
        if checker_results_summary:
            parts.append("")
            parts.append("## Code Quality Checker Results")
            for cr in checker_results_summary:
                forced_label = " [FORCED]" if cr.get("forced") else ""
                parts.append(f"### {cr['checker']}{forced_label} (commit {cr['commit']})")
                parts.append(f"Score: {cr['score']}/100")
                parts.append(f"Summary: {cr['message']}")
                
                # Include detailed analysis if available
                if cr.get("analysis"):
                    parts.append("")
                    parts.append("Detailed Analysis:")
                    parts.append(cr["analysis"])
                
                parts.append("")  # Empty line between checkers
        
        if repo_structure:
            parts.append("BACKGROUND REPO STRUCTURE (not scoring evidence; use only to understand commit diffs/messages):")
            parts.append(json.dumps(repo_structure, ensure_ascii=False)[:8000])
            parts.append("")
        if file_contents:
            parts.append("BACKGROUND REPOSITORY FILES (not scoring evidence; use only to understand files referenced by commit diffs/messages):")
            for p, content in file_contents.items():
                parts.append(f"\n--- FILE: {p} ---\n{content}")
            parts.append("")
        
        parts.append("COMMITS:")
        for c in commits[:50]:
            sha = c.get("sha") or c.get("hash") or ""
            msg = (c.get("message") or c.get("commit", {}).get("message") or "").split("\n")[0][:160]
            parts.append(f"\n- {sha} {msg}")
            for f in (c.get("files") or []) :
                if isinstance(f, dict):
                    fn = f.get("filename") or ""
                    patch = f.get("patch") or ""
                    parts.append(f"  * {fn}\n{patch}")
        
        return "\n".join(parts)

    def _build_chunked_context(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        *,
        chunk_idx: int,
        total_chunks: int,
        file_contents: Dict[str, str],
        repo_structure: Optional[Dict[str, Any]],
        previous_evaluation: Optional[Dict[str, Any]],
    ) -> str:
        parts = [f"CHUNK {chunk_idx}/{total_chunks}", ""]
        if previous_evaluation:
            parts.append("PREVIOUS EVALUATION (scores+reasoning):")
            parts.append(json.dumps(previous_evaluation, ensure_ascii=False))
            parts.append("")
        parts.append(self._build_commit_context(commits, username, file_contents=file_contents, repo_structure=repo_structure))
        return "\n".join(parts)

    def _load_relevant_files(self, commits: List[Dict[str, Any]]) -> Dict[str, str]:
        if not self.data_dir:
            return {}
        files: List[str] = []
        for c in commits:
            for f in c.get("files") or []:
                if isinstance(f, dict) and f.get("filename"):
                    files.append(str(f["filename"]))
        # de-dup preserve order
        seen = set()
        uniq: List[str] = []
        for p in files:
            if p in seen:
                continue
            seen.add(p)
            uniq.append(p)

        out: Dict[str, str] = {}
        for rel in uniq:
            if rel in self._file_cache:
                out[rel] = self._file_cache[rel]
                continue
            abs_path = (self.data_dir / "files" / rel).resolve()
            try:
                if abs_path.exists() and abs_path.is_file():
                    content = abs_path.read_text(encoding="utf-8", errors="ignore")
                    self._file_cache[rel] = content
                    out[rel] = content
            except Exception:
                continue
        return out

    def _repo_snapshot_root(self) -> Optional[Path]:
        if not self.data_dir:
            return None
        repo_files_dir = self.data_dir / "repo_files"
        manifest_path = self.data_dir / "repo_files_manifest.json"
        if not repo_files_dir.exists() or not repo_files_dir.is_dir() or not manifest_path.exists():
            return None
        return repo_files_dir

    def _list_repo_snapshot_paths(self) -> List[str]:
        repo_files_dir = self._repo_snapshot_root()
        if not repo_files_dir:
            return []
        out: List[str] = []
        for abs_path in sorted(repo_files_dir.rglob("*")):
            if not abs_path.is_file():
                continue
            try:
                out.append(abs_path.relative_to(repo_files_dir).as_posix())
            except ValueError:
                continue
        return out

    def _load_repo_snapshot_files(self, selected_paths: Optional[Set[str]] = None) -> Dict[str, str]:
        repo_files_dir = self._repo_snapshot_root()
        if not repo_files_dir:
            return {}

        out: Dict[str, str] = {}
        paths = self._list_repo_snapshot_paths() if selected_paths is None else sorted(selected_paths)
        for rel in paths:
            abs_path = repo_files_dir / rel
            if not abs_path.is_file():
                continue
            cache_key = f"repo_files/{rel}"
            if cache_key in self._file_cache:
                out[rel] = self._file_cache[cache_key]
                continue
            try:
                content = abs_path.read_text(encoding="utf-8", errors="ignore")
                self._file_cache[cache_key] = content
                out[rel] = content
            except Exception:
                continue
        return out

    def _changed_file_paths(self, commits: List[Dict[str, Any]]) -> List[str]:
        paths: List[str] = []
        for commit in commits:
            for file_item in commit.get("files") or []:
                if not isinstance(file_item, dict):
                    continue
                filename = str(file_item.get("filename") or "").strip()
                if filename:
                    paths.append(filename)
        seen: Set[str] = set()
        return [p for p in paths if not (p in seen or seen.add(p))]

    def _root_context_paths_for_changes(self, changed_paths: Set[str], available_paths: Set[str]) -> Set[str]:
        selected: Set[str] = set()
        root_candidates: Dict[str, Tuple[str, ...]] = {
            "python": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "tox.ini", "pytest.ini"),
            "node": ("package.json", "tsconfig.json", "jsconfig.json", "vite.config.ts", "vite.config.js", "next.config.js", "next.config.mjs"),
            "java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts", "gradlew"),
            "cpp": ("CMakeLists.txt", "Makefile", "meson.build", "conanfile.txt", "conanfile.py", "vcpkg.json"),
            "container": ("Dockerfile", "docker-compose.yml", "compose.yml", ".github/workflows/ci.yml"),
        }

        has_python = any(path.endswith((".py", ".pyi")) for path in changed_paths)
        has_node = any(path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")) for path in changed_paths)
        has_java = any(path.endswith(".java") for path in changed_paths)
        has_cpp = any(path.endswith((".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx")) for path in changed_paths)
        has_container = any(
            path == "Dockerfile"
            or path.endswith(("Dockerfile", "docker-compose.yml", "compose.yml"))
            or path.startswith(".github/workflows/")
            for path in changed_paths
        )

        groups: List[str] = []
        if has_python:
            groups.append("python")
        if has_node:
            groups.append("node")
        if has_java:
            groups.append("java")
        if has_cpp:
            groups.append("cpp")
        if has_container:
            groups.append("container")

        for group in groups:
            selected.update(path for path in root_candidates[group] if path in available_paths)
        return selected

    def _python_import_candidates(self, source_path: str, content: str, available_paths: Set[str]) -> Set[str]:
        selected: Set[str] = set()
        source_dir = Path(source_path).parent
        modules: List[str] = []
        for match in re.finditer(r"^\s*from\s+([.\w]+)\s+import\s+[\w*({]", content, flags=re.MULTILINE):
            modules.append(match.group(1))
        for match in re.finditer(r"^\s*import\s+([.\w]+)", content, flags=re.MULTILINE):
            modules.extend(part.strip().split(" as ")[0] for part in match.group(1).split(","))

        for module in modules:
            if not module:
                continue
            if module.startswith("."):
                rel_parts = [part for part in module.lstrip(".").split(".") if part]
                module_path = source_dir.joinpath(*rel_parts).as_posix() if rel_parts else source_dir.as_posix()
            else:
                module_path = "/".join(part for part in module.split(".") if part)
            for candidate in (f"{module_path}.py", f"{module_path}/__init__.py"):
                if candidate in available_paths:
                    selected.add(candidate)
        return selected

    def _js_import_candidates(self, source_path: str, content: str, available_paths: Set[str]) -> Set[str]:
        selected: Set[str] = set()
        source_dir = Path(source_path).parent
        imports = re.findall(r"(?:from\s+|import\s*\(|require\()\s*['\"]([^'\"]+)['\"]", content)
        extensions = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".css")
        for specifier in imports:
            if not specifier.startswith("."):
                continue
            base = source_dir.joinpath(specifier).as_posix()
            candidates: List[str] = []
            for ext in extensions:
                candidates.append(f"{base}{ext}")
            for ext in extensions[1:]:
                candidates.append(f"{base}/index{ext}")
            selected.update(candidate for candidate in candidates if candidate in available_paths)
        return selected

    def _cpp_include_candidates(self, source_path: str, content: str, available_paths: Set[str]) -> Set[str]:
        selected: Set[str] = set()
        source_dir = Path(source_path).parent
        includes = re.findall(r"^\s*#\s*include\s+\"([^\"]+)\"", content, flags=re.MULTILINE)
        for include_path in includes:
            base = source_dir.joinpath(include_path).as_posix()
            if base in available_paths:
                selected.add(base)
            selected.update(path for path in available_paths if path.endswith(f"/{include_path}"))
        return selected

    def _java_import_candidates(self, source_path: str, content: str, available_paths: Set[str]) -> Set[str]:
        selected: Set[str] = set()
        imports = re.findall(r"^\s*import\s+(?:static\s+)?([\w.]+)(?:\.\*)?\s*;", content, flags=re.MULTILINE)
        for imported in imports:
            if imported.startswith(("java.", "javax.", "jakarta.", "org.junit.")):
                continue
            rel_path = "/".join(imported.split(".")) + ".java"
            selected.update(path for path in available_paths if path.endswith(rel_path))
        return selected

    def _related_context_paths(self, changed_paths: Set[str], changed_contents: Dict[str, str], available_paths: Set[str]) -> Set[str]:
        selected: Set[str] = set()
        for path, content in changed_contents.items():
            if path.endswith((".py", ".pyi")):
                selected.update(self._python_import_candidates(path, content, available_paths))
            elif path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
                selected.update(self._js_import_candidates(path, content, available_paths))
            elif path.endswith((".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx")):
                selected.update(self._cpp_include_candidates(path, content, available_paths))
            elif path.endswith(".java"):
                selected.update(self._java_import_candidates(path, content, available_paths))
        selected.difference_update(changed_paths)
        return selected

    def _select_repo_context_paths(self, commits: List[Dict[str, Any]]) -> Set[str]:
        available_paths = set(self._list_repo_snapshot_paths())
        if not available_paths:
            return set()

        changed_paths = {path for path in self._changed_file_paths(commits) if path in available_paths}
        changed_contents = self._load_repo_snapshot_files(changed_paths)

        selected = set(changed_paths)
        selected.update(self._related_context_paths(changed_paths, changed_contents, available_paths))
        selected.update(self._root_context_paths_for_changes(changed_paths, available_paths))
        return selected

    def _load_context_files(self, commits: List[Dict[str, Any]], *, include_all_repo_snapshot: bool = False) -> Dict[str, str]:
        if self._repo_snapshot_root():
            if include_all_repo_snapshot:
                return self._load_repo_snapshot_files()
            selected_paths = self._select_repo_context_paths(commits)
            return self._load_repo_snapshot_files(selected_paths)
        return self._load_relevant_files(commits)

    def _load_repo_structure(self) -> Optional[Dict[str, Any]]:
        if self._repo_structure is not None:
            return self._repo_structure
        if not self.data_dir:
            return None
        p = self.data_dir / "repo_structure.json"
        try:
            if p.exists():
                self._repo_structure = json.loads(p.read_text(encoding="utf-8"))
                return self._repo_structure
        except Exception:
            return None
        return None

    def _evaluate_with_llm(self, context: str, username: str, chunk_idx: Optional[int] = None) -> Dict[str, Any]:
        if not self.api_key:
            print("[ERROR] LLM API key not configured")
            raise RuntimeError("LLM not configured (missing API key)")

        prompt = self._build_evaluation_prompt(context, username, chunk_idx=chunk_idx)
        prompt_tokens = self._estimate_tokens(prompt)
        if prompt_tokens > self.max_input_tokens:
            raise RuntimeError(
                f"LLM input exceeds model budget ({prompt_tokens} > {self.max_input_tokens} estimated tokens)."
            )
        models_to_try = [self.model] + (self.fallback_models or [])

        last_err = None
        for m in models_to_try:
            try:
                print(f"[LLM] Calling {m} at {self.api_url}")
                resp = self._http_client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": m,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 4000,
                    },
                )
                # httpx uses is_success instead of ok
                if not resp.is_success:
                    last_err = f"{resp.status_code} {resp.text[:200]}"
                    print(f"[ERROR] LLM API returned error: {last_err}")
                    continue
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                print(f"[LLM] Response received, parsing...")
                return self._parse_llm_response_with_retry(content, prompt, m)
            except Exception as e:
                last_err = str(e)
                print(f"[ERROR] LLM request failed for model {m}: {last_err}")
                continue
        print(f"[ERROR] All LLM models failed. Last error: {last_err}")
        raise RuntimeError(f"LLM request failed for all models. last_error={last_err}")

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text))

    def _build_evaluation_prompt(self, context: str, username: str, chunk_idx: Optional[int] = None) -> str:
        is_chinese = self.language == "zh-CN"

        # Build previous checkpoint context if available
        previous_scores_block = ""
        if self.previous_checkpoint_scores:
            prev_scores = {k: v for k, v in self.previous_checkpoint_scores.items() if k != 'reasoning'}
            if is_chinese:
                previous_scores_block = f"\n\n上一个评估节点的分数（基线参考）:\n{json.dumps(prev_scores, ensure_ascii=False, indent=2)}\n注意：当前评估应该基于上一个节点的分数，除非有明确的负面证据，否则分数应该保持稳定或略有增长。这是成长轨迹追踪系统的一部分，评估节点基于2周周期累积的至少10个提交。"
            else:
                previous_scores_block = f"\n\nPREVIOUS CHECKPOINT SCORES (baseline reference):\n{json.dumps(prev_scores, ensure_ascii=False, indent=2)}\nNOTE: Current evaluation should build on previous scores. Maintain or gradually increase scores unless clear negative evidence exists. This is part of a growth trajectory tracking system with evaluation nodes based on 10+ commits from 2-week periods."
        expected_feature_block = self._build_expected_feature_block(is_chinese)

        # Language-specific instructions
        if is_chinese:
            base_instruction = f'你是一位专业的工程能力评估员。分析用户 "{username}" 的数据，并对每个维度评分（0-100分）。'
            mode_note = (
                "\n注意：只有提交信息、提交差异（commit diffs）和代码检查器结果可以作为评分证据。"
                "仓库快照文件和仓库结构只能作为背景帮助理解提交，不得单独用于评分或作为证据引用。"
            )
            chunked_instruction = ""
            if chunk_idx:
                chunked_instruction = "\n分块评估：基于之前的评分和新证据更新分数；提供完整的推理过程。"
            data_label = "数据"
            dimensions_label = "评估维度"
            return_json_instruction = "仅返回有效的JSON格式"
        else:
            base_instruction = f'You are an expert engineering evaluator. Analyze data from user "{username}" and score each dimension 0-100.'
            mode_note = (
                "\nNOTE: Only commit messages, commit diffs, and checker results are scoring evidence. "
                "Repository snapshot files and repo structure are background only. "
                "Do not cite repository snapshot files or repo structure as evidence unless the same path appears in a commit message or diff."
            )
            chunked_instruction = ""
            if chunk_idx:
                chunked_instruction = "\nCHUNKED: Update scores based on previous + new evidence; provide full reasoning."
            data_label = "DATA"
            dimensions_label = "DIMENSIONS"
            return_json_instruction = "Return ONLY valid JSON"

        rubric_block = ""
        if self.rubric_text:
            snippet = self.rubric_text
            if len(snippet) > 6000:
                snippet = snippet[:6000] + "\n...[rubric truncated]..."
            rubric_label = "评分标准" if is_chinese else "RUBRIC / STANDARD"
            rubric_block = f"\n\n{rubric_label}:\n{snippet}\n"

        dim_lines: List[str] = []
        i = 1
        for k, title in self.dimensions.items():
            guide = (self.dimension_instructions.get(k) or "").strip()
            dim_lines.append(f"{i}. **{title} ({k})**: {guide}" if guide else f"{i}. **{title} ({k})**")
            i += 1
        dims_text = "\n".join(dim_lines)

        if is_chinese:
            reasoning_example = "提供包含 **主要优势**、**改进空间**、**整体评估** 的推理过程。证据必须来自 commit sha、commit message 和 commit diff 中的文件路径/改动；如期望实现功能缺失，请说明缺失功能。"
            format_note = "每个维度评分范围：0-100"
            json_instruction = "重要：必须只返回JSON对象，不要添加任何解释性文字、markdown格式或代码块标记。直接返回JSON，格式如下："
        else:
            reasoning_example = (
                "Provide sections with **Key Strengths**, **Areas for Growth**, **Overall Assessment**. "
                "Evidence must come from commit sha, commit message, and file paths/changes visible in commit diffs. "
                "If the expected feature is lacking, describe the lacking feature."
            )
            format_note = "Each dimension: score 0-100"
            json_instruction = "IMPORTANT: Return ONLY a JSON object. Do NOT add explanatory text, markdown formatting, or code block markers. Return raw JSON directly in this format:"

        # Create proper valid JSON example
        fmt_example = {k: 0 for k in self.dimensions.keys()}
        fmt_example["reasoning"] = reasoning_example
        fmt_text = json.dumps(fmt_example, ensure_ascii=False, indent=2)
        fmt_text_with_note = f"{format_note}\n\n{fmt_text}"

        return (
            f'{base_instruction}'
            f"{mode_note}{chunked_instruction}{rubric_block}{previous_scores_block}{expected_feature_block}\n\n{data_label}:\n{context}\n\n{dimensions_label}:\n{dims_text}\n\n"
            f"{json_instruction}\n{fmt_text_with_note}"
        )

    def _parse_llm_response_with_retry(self, content: str, original_prompt: str, model: str, retry_count: int = 0) -> Dict[str, Any]:
        """Parse LLM response with retry mechanism if parsing fails."""
        max_retries = 1  # Only retry once to avoid infinite loops
        content_text = content if isinstance(content, str) else ""
        
        try:
            if not content_text.strip():
                raise ValueError("LLM response content was empty")
            return self._parse_llm_response(content_text)
        except Exception as parse_error:
            error_msg = str(parse_error)
            print(f"[ERROR] Failed to parse LLM response: {error_msg}")
            
            if retry_count >= max_retries:
                print(f"[ERROR] Max retries ({max_retries}) reached")
                return self._handle_parse_retry_failure(error_msg)
            
            # Build retry prompt with original prompt and error information
            is_chinese = self.language == "zh-CN"
            # Show more content for better debugging (up to 1000 chars)
            content_preview = content_text[:1000] + ("..." if len(content_text) > 1000 else "")
            
            if is_chinese:
                retry_instruction = f"""\n\n[重要] 你之前的回复格式不正确，无法解析为JSON。

错误信息：{error_msg}

你之前的回复（前1000字符）：
{content_preview}

请重新返回正确的JSON格式。必须只返回JSON对象，不要添加任何解释性文字、markdown格式或代码块标记。直接返回JSON。"""
            else:
                retry_instruction = f"""\n\n[IMPORTANT] Your previous response format was incorrect and could not be parsed as JSON.

Error: {error_msg}

Your previous response (first 1000 chars):
{content_preview}

Please return the correct JSON format again. Return ONLY a JSON object. Do NOT add explanatory text, markdown formatting, or code block markers. Return raw JSON directly."""
            
            retry_prompt = original_prompt + retry_instruction
            
            print(f"[RETRY] Attempting to retry LLM call (attempt {retry_count + 1}/{max_retries + 1})")
            print(f"[DEBUG] Retry prompt length: {len(retry_prompt)} chars")
            
            try:
                resp = self._http_client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": retry_prompt}],
                        "temperature": 0.3,
                        "max_tokens": 4000,
                    },
                )
                
                # httpx uses is_success instead of ok
                if not resp.is_success:
                    print(f"[ERROR] Retry LLM API returned error: {resp.status_code} {resp.text[:200]}")
                    return self._handle_parse_retry_failure(f"Retry LLM API returned error: {resp.status_code}")
                
                retry_data = resp.json()
                if "choices" not in retry_data or not retry_data["choices"]:
                    print(f"[ERROR] No choices in retry API response")
                    return self._handle_parse_retry_failure("No choices in retry API response")
                
                retry_content = retry_data["choices"][0]["message"]["content"]
                if not isinstance(retry_content, str) or not retry_content.strip():
                    return self._handle_parse_retry_failure("Retry LLM response content was empty")
                print(f"[LLM] Retry response received ({len(retry_content)} chars), parsing...")
                return self._parse_llm_response_with_retry(retry_content, original_prompt, model, retry_count + 1)
                
            except Exception as retry_error:
                print(f"[ERROR] Retry LLM call failed: {retry_error}")
                return self._handle_parse_retry_failure(str(retry_error))

    def _handle_parse_retry_failure(self, reason: str) -> Dict[str, Any]:
        raise RuntimeError(f"LLM response parsing failed after retry: {reason}")

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        try:
            # Enhanced debugging: log response length and first/last parts
            print(f"[DEBUG] LLM response length: {len(content)} chars")
            print(f"[DEBUG] Response start: {content[:200]}")
            print(f"[DEBUG] Response end: {content[-200:]}")

            # Try to extract JSON from markdown code blocks first
            import re
            json_str = None
            
            # Check for markdown code blocks (```json ... ``` or ``` ... ```)
            code_block_pattern = r'```(?:json)?\s*\n?(.*?)```'
            code_block_matches = re.findall(code_block_pattern, content, re.DOTALL)
            if code_block_matches:
                # Try each code block match
                for match in code_block_matches:
                    stripped = match.strip()
                    if stripped.startswith('{') and stripped.endswith('}'):
                        try:
                            json.loads(stripped)  # Validate it's valid JSON
                            json_str = stripped
                            print(f"[DEBUG] Found JSON in markdown code block")
                            break
                        except json.JSONDecodeError:
                            continue
            
            # If no code block found, try to extract JSON directly
            if not json_str:
                start = content.find("{")
                if start < 0:
                    print("[ERROR] No opening brace '{' found in LLM response")
                    raise ValueError("No JSON object found in response")
                
                # Find the matching closing brace by counting braces
                brace_count = 0
                end = start
                for i in range(start, len(content)):
                    if content[i] == '{':
                        brace_count += 1
                    elif content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
                
                if brace_count != 0:
                    print(f"[ERROR] Unmatched braces: found opening at {start} but no matching closing brace")
                    raise ValueError("Invalid JSON object boundaries - unmatched braces")
                
                json_str = content[start:end]
                print(f"[DEBUG] Extracted JSON from position {start} to {end}")

            print(f"[DEBUG] Extracted JSON length: {len(json_str)} chars")
            print(f"[DEBUG] Extracted JSON: {json_str[:300]}...")

            data = json.loads(json_str)
            print(f"[DEBUG] JSON parsed successfully, keys: {list(data.keys())}")

            out: Dict[str, Any] = {}
            for k in self.dimensions.keys():
                score_val = data.get(k, 0)
                out[k] = min(100, max(0, int(score_val)))
                print(f"[DEBUG] Dimension {k}: {score_val} -> {out[k]}")

            if "reasoning" in data:
                out["reasoning"] = self._format_reasoning(str(data["reasoning"]))
                print(f"[DEBUG] Reasoning found, length: {len(out['reasoning'])} chars")
            else:
                # LLM didn't provide reasoning - add placeholder
                print("[WARNING] LLM response missing 'reasoning' field")
                out["reasoning"] = "LLM evaluation completed but reasoning was not provided."

            print("[SUCCESS] LLM response parsed successfully")
            return out
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parsing failed: {e}")
            if 'json_str' in locals():
                print(f"[ERROR] JSON string attempted: {json_str[:1000]}")
            # Re-raise to trigger retry mechanism
            raise ValueError(f"JSON parsing failed: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to parse LLM response: {e}")
            print(f"[ERROR] LLM response content: {content[:1000]}")
            # Re-raise to trigger retry mechanism
            raise

    def _format_reasoning(self, reasoning: str) -> str:
        r = (reasoning or "").replace("\\n\\n", "\n\n").replace("\\n", "\n")
        return r.strip()

    def _merge_evaluations(self, prev: Dict[str, Any], new: Dict[str, Any], chunk_idx: int) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k in self.dimensions.keys():
            out[k] = int(round((int(prev.get(k, 0)) + int(new.get(k, 0))) / 2))
        pr = str(prev.get("reasoning", "")).strip()
        nr = str(new.get("reasoning", "")).strip()
        out["reasoning"] = (nr + "\n\n---\n\n" + pr).strip() if (nr and pr) else (nr or pr)
        out["chunks_merged"] = chunk_idx
        return out

    def _summarize_commits(self, commits: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_additions = 0
        total_deletions = 0
        files_changed = set()
        languages = set()
        for commit in commits:
            stats = commit.get("stats", {}) if isinstance(commit.get("stats"), dict) else {}
            total_additions += int(stats.get("additions", 0) or 0)
            total_deletions += int(stats.get("deletions", 0) or 0)
            for fi in commit.get("files") or []:
                if isinstance(fi, dict):
                    fn = fi.get("filename") or ""
                    if fn:
                        files_changed.add(fn)
                        if "." in fn:
                            languages.add(fn.rsplit(".", 1)[-1])
        return {
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "files_changed": len(files_changed),
            "languages": list(languages)[:10],
        }

    def _get_empty_evaluation(self, username: str) -> Dict[str, Any]:
        scores = {k: 0 for k in self.dimensions.keys()}
        scores["reasoning"] = "No commits found for this user in the analyzed data."
        return {
            "username": username,
            "total_commits_analyzed": 0,
            "files_loaded": 0,
            "mode": "moderate",
            "scores": scores,
            "commits_summary": {"total_additions": 0, "total_deletions": 0, "files_changed": 0, "languages": []},
        }


def create_commit_evaluator(
    *,
    data_dir: str,
    api_key: str,
    model: Optional[str] = None,
    language: str = "en-US",
    previous_checkpoint_scores: Optional[Dict[str, Any]] = None,
    forced_checker_id: Optional[str] = None,
    worktree_base: str = "build",
    expected_feature: Optional[str] = None,
):
    return CommitEvaluatorModerate(
        data_dir=data_dir,
        api_key=api_key,
        model=model,
        language=language,
        previous_checkpoint_scores=previous_checkpoint_scores,
        forced_checker_id=forced_checker_id,
        expected_feature=expected_feature,
    )
