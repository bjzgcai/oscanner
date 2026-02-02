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

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx


class CommitEvaluatorModerate:
    """
    Self-contained moderate evaluator:
    - Uses commit diffs + optional local file contents under data_dir
    - Calls OpenAI-compatible chat completions endpoint via requests
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        max_input_tokens: int = 190000,
        data_dir: Optional[str] = None,
        mode: str = "moderate",
        model: Optional[str] = None,
        api_base_url: Optional[str] = None,
        chat_completions_url: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        dimensions: Optional[Dict[str, str]] = None,
        dimension_instructions: Optional[Dict[str, str]] = None,
        rubric_text: Optional[str] = None,
        language: str = "en-US",
        parallel_chunking: bool = False,
        max_parallel_workers: int = 3,
        previous_checkpoint_scores: Optional[Dict[str, Any]] = None,
        forced_checker_id: Optional[str] = None,
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
        self.mode = mode
        self.model = model or os.getenv("OSCANNER_LLM_MODEL") or "anthropic/claude-sonnet-4.5"
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
        self.parallel_chunking = parallel_chunking
        self.max_parallel_workers = max_parallel_workers
        self.previous_checkpoint_scores = previous_checkpoint_scores
        self.forced_checker_id = forced_checker_id

        # Checker API base URL (default to localhost, can be overridden via env)
        self.checker_api_base = os.getenv("OSCANNER_CHECKER_API_BASE", "http://localhost:8000")
        self._checker_cache: Dict[str, Any] = {}  # Cache checker results
        
        # Create HTTP client with connection pooling for better performance
        # httpx.Client is more efficient than requests for concurrent operations
        self._http_client = httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0))

        self._file_cache: Dict[str, str] = {}
        self._repo_structure: Optional[Dict[str, Any]] = None

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
        use_chunking: bool = True,
    ) -> Dict[str, Any]:
        if not commits:
            return self._get_empty_evaluation(username)

        analyzed_commits = commits if max_commits is None else commits[: int(max_commits)]
        author_commits = [c for c in analyzed_commits if self._is_commit_by_author(c, username)]
        if not author_commits:
            return self._get_empty_evaluation(username)

        if use_chunking and len(author_commits) > 20:
            return self._evaluate_engineer_chunked(author_commits, username, load_files=load_files)
        return self._evaluate_engineer_standard(author_commits, username, load_files=load_files)

    def _is_commit_by_author(self, commit: Dict[str, Any], username: str) -> bool:
        # Handle comma-separated usernames as multiple aliases
        aliases = [alias.strip().lower() for alias in username.split(',')]

        if "author" in commit and isinstance(commit["author"], str):
            return commit["author"].lower() in aliases
        if "commit" in commit:
            author = commit.get("commit", {}).get("author", {}).get("name", "")
            return bool(author) and author.lower() in aliases
        return False

    def _evaluate_engineer_standard(self, commits: List[Dict[str, Any]], username: str, *, load_files: bool) -> Dict[str, Any]:
        file_contents: Dict[str, str] = {}
        repo_structure: Optional[Dict[str, Any]] = None
        if self.mode == "moderate" and load_files and self.data_dir:
            file_contents = self._load_relevant_files(commits)
            repo_structure = self._load_repo_structure()

        context = self._build_commit_context(commits, username, file_contents=file_contents, repo_structure=repo_structure)
        scores = self._evaluate_with_llm(context, username)
        return {
            "username": username,
            "total_commits_analyzed": len(commits),
            "files_loaded": len(file_contents),
            "mode": self.mode,
            "scores": scores,
            "commits_summary": self._summarize_commits(commits),
        }

    def _evaluate_engineer_chunked(self, commits: List[Dict[str, Any]], username: str, *, load_files: bool) -> Dict[str, Any]:
        commits_per_chunk = 15 if self.mode == "moderate" else 20
        chunks = [commits[i : i + commits_per_chunk] for i in range(0, len(commits), commits_per_chunk)]

        repo_structure = None
        if self.mode == "moderate" and load_files and self.data_dir:
            repo_structure = self._load_repo_structure()

        accumulated = None
        all_files: Dict[str, str] = {}
        for idx, chunk in enumerate(chunks, 1):
            chunk_files: Dict[str, str] = {}
            if self.mode == "moderate" and load_files and self.data_dir:
                chunk_files = self._load_relevant_files(chunk)
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

        return {
            "username": username,
            "total_commits_analyzed": len(commits),
            "files_loaded": len(all_files),
            "mode": self.mode,
            "scores": accumulated or self._fallback_evaluation(""),
            "commits_summary": self._summarize_commits(commits),
            "chunked": True,
            "chunks_processed": len(chunks),
        }

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
                # Pass all Python files from checkpoint, or None to let checker scan entire repo
                last_commit = commits[-1]
                last_sha = last_commit.get("sha") or last_commit.get("hash") or ""
                if last_sha:
                    # Pass all Python files from checkpoint to checker
                    # If no Python files found in commits, pass None to let checker scan entire repository
                    python_files_list = list(all_python_files) if all_python_files else None
                    result = self._run_checker(
                        self.forced_checker_id, 
                        platform, 
                        owner, 
                        repo, 
                        last_sha,
                        files=python_files_list  # Pass all Python files from checkpoint, or None for full repo scan
                    )
                    if result and result.get("success"):
                        # Update message to indicate checkpoint scope
                        message = result.get("message", "")
                        if all_python_files:
                            message = f"Checked {len(all_python_files)} Python files across {len(commits)} commits in checkpoint. {message}"
                        else:
                            message = f"Checked entire repository (no Python files in {len(commits)} commits). {message}"
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
            parts.append("REPO STRUCTURE (truncated):")
            parts.append(json.dumps(repo_structure, ensure_ascii=False)[:8000])
            parts.append("")
        if file_contents:
            parts.append("RELEVANT FILE CONTENTS:")
            for p, content in list(file_contents.items())[:25]:
                parts.append(f"\n--- FILE: {p} ---\n{content[:12000]}")
            parts.append("")
        
        parts.append("COMMITS:")
        for c in commits[:50]:
            sha = c.get("sha") or c.get("hash") or ""
            msg = (c.get("message") or c.get("commit", {}).get("message") or "").split("\n")[0][:160]
            parts.append(f"\n- {sha} {msg}")
            for f in (c.get("files") or [])[:30]:
                if isinstance(f, dict):
                    fn = f.get("filename") or ""
                    patch = f.get("patch") or ""
                    parts.append(f"  * {fn}\n{patch[:4000]}")
        
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
            parts.append(json.dumps(previous_evaluation, ensure_ascii=False)[:12000])
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
        for rel in uniq[:25]:
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
        allow_fallback = str(os.getenv("OSCANNER_ALLOW_FALLBACK") or "").strip().lower() in ("1", "true", "yes", "y")
        if not self.api_key:
            print("[ERROR] LLM API key not configured")
            if allow_fallback:
                return self._fallback_evaluation(context)
            raise RuntimeError("LLM not configured (missing API key)")

        prompt = self._build_evaluation_prompt(context, username, chunk_idx=chunk_idx)
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
        if allow_fallback:
            print("[WARNING] Using fallback evaluation (keyword-based)")
            return self._fallback_evaluation(context)
        raise RuntimeError(f"LLM request failed for all models. last_error={last_err}")

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _truncate_context(self, context: str, max_tokens: int) -> str:
        cur = self._estimate_tokens(context)
        if cur <= max_tokens:
            return context
        target_chars = max_tokens * 4
        return context[:target_chars] + "\n\n[... Context truncated ...]"

    def _build_evaluation_prompt(self, context: str, username: str, chunk_idx: Optional[int] = None) -> str:
        prompt_template_tokens = 900
        max_context_tokens = self.max_input_tokens - prompt_template_tokens
        context = self._truncate_context(context, max_context_tokens)

        is_chinese = self.language == "zh-CN"

        # Build previous checkpoint context if available
        previous_scores_block = ""
        if self.previous_checkpoint_scores:
            prev_scores = {k: v for k, v in self.previous_checkpoint_scores.items() if k != 'reasoning'}
            if is_chinese:
                previous_scores_block = f"\n\n上一个评估节点的分数（基线参考）:\n{json.dumps(prev_scores, ensure_ascii=False, indent=2)}\n注意：当前评估应该基于上一个节点的分数，除非有明确的负面证据，否则分数应该保持稳定或略有增长。这是成长轨迹追踪系统的一部分，评估节点基于2周周期累积的至少10个提交。"
            else:
                previous_scores_block = f"\n\nPREVIOUS CHECKPOINT SCORES (baseline reference):\n{json.dumps(prev_scores, ensure_ascii=False, indent=2)}\nNOTE: Current evaluation should build on previous scores. Maintain or gradually increase scores unless clear negative evidence exists. This is part of a growth trajectory tracking system with evaluation nodes based on 10+ commits from 2-week periods."

        # Language-specific instructions
        if is_chinese:
            base_instruction = f'你是一位专业的工程能力评估员。分析用户 "{username}" 的数据，并对每个维度评分（0-100分）。'
            mode_note = ""
            if self.mode == "moderate":
                mode_note = "\n注意：你可能会看到提交差异（commit diffs）和文件内容。在有帮助的情况下请使用文件内容。"
            chunked_instruction = ""
            if chunk_idx:
                chunked_instruction = "\n分块评估：基于之前的评分和新证据更新分数；提供完整的推理过程。"
            data_label = "数据"
            dimensions_label = "评估维度"
            return_json_instruction = "仅返回有效的JSON格式"
        else:
            base_instruction = f'You are an expert engineering evaluator. Analyze data from user "{username}" and score each dimension 0-100.'
            mode_note = ""
            if self.mode == "moderate":
                mode_note = "\nNOTE: You may see both commit diffs AND file contents. Use file contents when helpful."
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
            reasoning_example = "提供包含 **主要优势**、**改进空间**、**整体评估** 的推理过程。"
            format_note = "每个维度评分范围：0-100"
            json_instruction = "重要：必须只返回JSON对象，不要添加任何解释性文字、markdown格式或代码块标记。直接返回JSON，格式如下："
        else:
            reasoning_example = "Provide sections with **Key Strengths**, **Areas for Growth**, **Overall Assessment**."
            format_note = "Each dimension: score 0-100"
            json_instruction = "IMPORTANT: Return ONLY a JSON object. Do NOT add explanatory text, markdown formatting, or code block markers. Return raw JSON directly in this format:"

        # Create proper valid JSON example
        fmt_example = {k: 0 for k in self.dimensions.keys()}
        fmt_example["reasoning"] = reasoning_example
        fmt_text = json.dumps(fmt_example, ensure_ascii=False, indent=2)
        fmt_text_with_note = f"{format_note}\n\n{fmt_text}"

        return (
            f'{base_instruction}'
            f"{mode_note}{chunked_instruction}{rubric_block}{previous_scores_block}\n\n{data_label}:\n{context}\n\n{dimensions_label}:\n{dims_text}\n\n"
            f"{json_instruction}\n{fmt_text_with_note}"
        )

    def _parse_llm_response_with_retry(self, content: str, original_prompt: str, model: str, retry_count: int = 0) -> Dict[str, Any]:
        """Parse LLM response with retry mechanism if parsing fails."""
        max_retries = 1  # Only retry once to avoid infinite loops
        
        try:
            return self._parse_llm_response(content)
        except Exception as parse_error:
            error_msg = str(parse_error)
            print(f"[ERROR] Failed to parse LLM response: {error_msg}")
            
            if retry_count >= max_retries:
                print(f"[ERROR] Max retries ({max_retries}) reached, using fallback")
                return self._get_fallback_evaluation()
            
            # Build retry prompt with original prompt and error information
            is_chinese = self.language == "zh-CN"
            # Show more content for better debugging (up to 1000 chars)
            content_preview = content[:1000] + ("..." if len(content) > 1000 else "")
            
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
                    return self._get_fallback_evaluation()
                
                retry_data = resp.json()
                if "choices" not in retry_data or not retry_data["choices"]:
                    print(f"[ERROR] No choices in retry API response")
                    return self._get_fallback_evaluation()
                
                retry_content = retry_data["choices"][0]["message"]["content"]
                print(f"[LLM] Retry response received ({len(retry_content)} chars), parsing...")
                return self._parse_llm_response_with_retry(retry_content, original_prompt, model, retry_count + 1)
                
            except Exception as retry_error:
                print(f"[ERROR] Retry LLM call failed: {retry_error}")
                return self._get_fallback_evaluation()

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

    def _get_fallback_evaluation(self) -> Dict[str, Any]:
        """Get fallback evaluation with default scores."""
        print("[FALLBACK] Using default scores due to parsing failure")
        fallback = {k: 50 for k in self.dimensions.keys()}
        fallback["reasoning"] = "**Error:** LLM response parsing failed. Using default scores."
        return fallback

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

    def _fallback_evaluation(self, context: str) -> Dict[str, Any]:
        text = (context or "").lower()

        def score_by_keywords(keywords: List[str]) -> int:
            hits = sum(1 for kw in keywords if kw in text)
            if not keywords:
                return 0
            return min(100, int((hits / len(keywords)) * 100))

        # Heuristic keywords (broad/default)
        kw = {
            "ai_fullstack": ["model", "training", "tensorflow", "pytorch", "neural", "ml", "ai", "inference"],
            "ai_architecture": ["api", "architecture", "design", "service", "endpoint", "microservice", "schema"],
            "cloud_native": ["docker", "kubernetes", "k8s", "ci/cd", "deploy", "container", "cloud", "terraform"],
            "open_source": ["fix", "issue", "pr", "review", "merge", "refactor", "improve", "doc"],
            "intelligent_dev": ["test", "unit", "integration", "auto", "script", "tool", "lint", "format", "cli"],
            "leadership": ["optimize", "performance", "security", "best practice", "pattern", "migration"],
        }

        scores: Dict[str, Any] = {}
        for k in self.dimensions.keys():
            scores[k] = score_by_keywords(kw.get(k, []))

        scores["reasoning"] = (
            "**Note:** LLM not available or failed; using keyword-based heuristic scoring.\n\n"
            "**Key Strengths:** Scores reflect presence of relevant keywords in commits/diffs/files.\n\n"
            "**Areas for Growth:** Configure a working LLM provider for deeper contextual analysis.\n\n"
            "**Overall Assessment:** Treat these scores as rough indicators only."
        )
        return scores

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
            "mode": self.mode,
            "scores": scores,
            "commits_summary": {"total_additions": 0, "total_deletions": 0, "files_changed": 0, "languages": []},
        }


def create_commit_evaluator(
    *,
    data_dir: str,
    api_key: str,
    model: Optional[str] = None,
    mode: str = "moderate",
    language: str = "en-US",
    parallel_chunking: bool = False,
    max_parallel_workers: int = 3,
    previous_checkpoint_scores: Optional[Dict[str, Any]] = None,
    forced_checker_id: Optional[str] = None,
):
    return CommitEvaluatorModerate(
        data_dir=data_dir,
        api_key=api_key,
        model=model,
        mode=mode,
        language=language,
        parallel_chunking=parallel_chunking,
        max_parallel_workers=max_parallel_workers,
        previous_checkpoint_scores=previous_checkpoint_scores,
        forced_checker_id=forced_checker_id,
    )

