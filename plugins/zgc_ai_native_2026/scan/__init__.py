"""
AI-Native 2026 scan plugin.

This plugin uses the AI-Native 2026 evaluation standard documented in `engineer_level.md`.
It injects a rubric summary (L1-L5 behavioral profiles) into the LLM prompt to bias
reasoning toward "built-in quality", "reproducibility", "cloud-native", "agent/tooling",
and "professionalism" evidence, helping distinguish "AI搬运工" from "系统构建者".

Output remains compatible with the existing dashboard (six score keys + reasoning),
but the evaluation criteria are stricter and more focused on evidence-based assessment.

Scan contract (inputs/outputs) is documented at:
- plugins/_shared/scan/README.md

Standard reference:
- engineer_level.md (2026 AI-Native Engineer Practical Competency Standard)
"""

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx


_RUBRIC_SUMMARY = """
You are evaluating an engineer in the Vibe Coding era. Distinguish "AI搬运工" vs "系统构建者".
Use L1-L5 behavioral profiles as guidance:
- L1: blind copy/paste, cannot explain, low-level errors, no quality gates
- L2: can deliver happy-path, basic norms, basic tests/lint, but shallow system thinking
- L3: one-person full-stack MVP builder, can refactor AI code, stronger type discipline, edge cases
- L4: team anchor, introduces quality gates, defensive validation, CI, docs, cost/ops thinking
- L5: leader/maintainer, defines patterns/standards, affects ecosystem, deep architecture decisions

Evidence to look for (prefer repo artifacts over claims):
- Spec/quality: refactors, modularity, input validation, tests (unit/integration/property), lint/format, CI
- Reproducibility: dependency locks, one-command run, docker/compose/devcontainer
- Cloud-native: containerization, IaC, deployment configs, resource limits, automation
- AI engineering: agent/tooling, structured prompts, tool abstractions, traces/logs, eval datasets
- Professionalism: docs/ADR, meaningful commits/PRs, careful tradeoffs, security/perf considerations

Scoring mapping: for each dimension, map observed evidence to a rough L1-L5 and convert to 0-100
(L1≈10-30, L2≈30-50, L3≈50-70, L4≈70-85, L5≈85-100). Be conservative when evidence is missing.

TRAJECTORY EVALUATION CONTEXT:
- This evaluation is part of a growth trajectory tracking system
- Commits are grouped into evaluation nodes (minimum 10 commits per node from 2-week periods)
- Scores should generally show INCREASING trend over time as engineers learn and improve
- ONLY decrease scores if there is CLEAR NEGATIVE EVIDENCE (regression in quality, bugs introduced, anti-patterns)
- When previous checkpoint scores are provided, use them as baseline for comparison
- If current work maintains similar quality to previous, scores should be equal or slightly higher
- Significant score increases require clear evidence of new capabilities or improved practices
"""


ProgressCallback = Callable[[str, Dict[str, Any]], None]


def extract_stream_delta(line: str) -> Optional[str]:
    """Extract token text from an OpenAI-compatible SSE data line."""
    raw = (line or "").strip()
    if not raw:
        return None
    if raw.startswith("data:"):
        raw = raw[5:].strip()
    if not raw or raw == "[DONE]":
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    first = choices[0] if isinstance(choices[0], dict) else {}
    delta = first.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str) and content:
            return content

    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content:
            return content

    text = first.get("text")
    return text if isinstance(text, str) and text else None


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
    worktree_base: str = "build",
    expected_feature: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
    max_input_tokens: Optional[int] = None,
):
    return CommitEvaluatorModerate(
        data_dir=data_dir,
        api_key=api_key,
        mode=mode,
        model=model,
        rubric_text=_RUBRIC_SUMMARY,
        language=language,
        parallel_chunking=parallel_chunking,
        max_parallel_workers=max_parallel_workers,
        previous_checkpoint_scores=previous_checkpoint_scores,
        forced_checker_id=forced_checker_id,
        worktree_base=worktree_base,
        expected_feature=expected_feature,
        progress_callback=progress_callback,
        max_input_tokens=max_input_tokens,
    )


class CommitEvaluatorModerate:
    """
    Self-contained evaluator for the AI-Native 2026 rubric.

    IMPORTANT: this plugin must not import from `evaluator/`.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        max_input_tokens: Optional[int] = None,
        data_dir: Optional[str] = None,
        mode: str = "moderate",
        model: Optional[str] = None,
        api_base_url: Optional[str] = None,
        chat_completions_url: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        rubric_text: Optional[str] = None,
        language: str = "en-US",
        parallel_chunking: bool = False,
        max_parallel_workers: int = 3,
        previous_checkpoint_scores: Optional[Dict[str, Any]] = None,
        forced_checker_id: Optional[str] = None,
        worktree_base: str = "build",
        expected_feature: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
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
        if max_input_tokens is None:
            env_max_input_tokens = os.getenv("OSCANNER_LLM_MAX_INPUT_TOKENS")
            if env_max_input_tokens:
                max_input_tokens = int(env_max_input_tokens)
            elif str(model or "").strip() == "deepseek/deepseek-v4-pro":
                max_input_tokens = 1_000_000
            else:
                max_input_tokens = 190_000
        self.max_input_tokens = int(max_input_tokens)
        self.data_dir = Path(data_dir) if data_dir else None
        self.mode = mode
        self.model = model or os.getenv("OSCANNER_LLM_MODEL") or "anthropic/claude-sonnet-4.5"
        self.fallback_models = fallback_models
        self.rubric_text = (rubric_text or "").strip()
        self.language = language
        self.parallel_chunking = parallel_chunking
        self.max_parallel_workers = max_parallel_workers
        self.previous_checkpoint_scores = previous_checkpoint_scores
        self.forced_checker_id = forced_checker_id
        self.worktree_base = worktree_base  # 'build' or 'temp'
        self.expected_feature = (expected_feature or "").strip()
        self.progress_callback = progress_callback

        # Checker API base URL (default to localhost, can be overridden via env)
        self.checker_api_base = os.getenv("OSCANNER_CHECKER_API_BASE", "http://localhost:8000")
        self._checker_cache: Dict[str, Any] = {}  # Cache checker results
        
        # Create HTTP client with connection pooling for better performance
        # httpx.Client is more efficient than requests for concurrent operations
        self._http_client = httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0))
        
        self.dimensions = {
            "spec_quality": "Specification & Built-in Quality",
            "cloud_architecture": "Cloud-Native & Architecture Evolution",
            "ai_engineering": "AI Engineering & Automated Evolution",
            "mastery_professionalism": "Engineering Mastery & Professionalism",
        }
        self.dimension_instructions = {
            "spec_quality": "Evidence: refactors, tests (unit/integration/property), type discipline, edge cases, schema validation, modularity, reproducible builds (docker/compose), lint/format, CI/CD.",
            "cloud_architecture": "Evidence: containerization, IaC (Terraform/Pulumi), K8s configs, deployment automation, resource optimization, architecture docs/ADR, API design, migration patterns (anti-corruption layer).",
            "ai_engineering": "Evidence: agent orchestration, tool definitions, structured prompts, LLM traces/logs, eval datasets, feedback loops, automation scripts, intelligent workflows.",
            "mastery_professionalism": "Evidence: open source collaboration, meaningful commits/PRs, code reviews, documentation, trade-off analysis, security/performance fixes, mentorship, standards definition.",
        }

        self._file_cache: Dict[str, str] = {}
        self._repo_structure: Optional[Dict[str, Any]] = None

    def _build_expected_feature_block(self, is_chinese: bool) -> str:
        if not self.expected_feature:
            return ""

        if is_chinese:
            return (
                "\n\n期望实现功能（评价基线）:\n"
                f"{self.expected_feature}\n"
                "请把上面的期望实现功能作为本次整体评估的核心基线："
                "检查提交、文件内容和仓库结构是否真正实现该功能。"
                "如果实现缺失、不完整或只有表面痕迹，必须降低评分（相关维度分数），"
                "并在 reasoning 中明确写出 **期望实现功能**、**缺失功能** 和扣分原因。"
            )

        return (
            "\n\nEXPECTED FEATURE BASELINE:\n"
            f"{self.expected_feature}\n"
            "Use this expected feature as a core baseline for the overall evaluation. "
            "Check whether the commits, file contents, and repository structure actually implement it. "
            "If the implementation is missing, incomplete, or only superficial, score lower on the relevant dimensions "
            "and explicitly report the expected feature, lacking feature, and scoring rationale in reasoning."
        )

    def __del__(self):
        """Clean up HTTP client on object destruction."""
        if hasattr(self, '_http_client'):
            try:
                self._http_client.close()
            except Exception:
                pass  # Ignore errors during cleanup

    def _emit_progress(self, event: str, data: Dict[str, Any]) -> None:
        if not self.progress_callback:
            return
        try:
            self.progress_callback(event, data)
        except Exception as e:
            print(f"[Streaming] Progress callback failed: {e}")

    def _complete_chat(self, model: str, prompt: str, *, label: str) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 4000,
        }

        if not self.progress_callback:
            resp = self._http_client.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            if not resp.is_success:
                raise RuntimeError(f"{resp.status_code} {resp.text[:200]}")
            data = resp.json()
            if "choices" not in data or not data["choices"]:
                raise RuntimeError("No choices in response")
            return data["choices"][0]["message"]["content"]

        self._emit_progress("section", {"title": label, "status": "running"})
        content_parts: List[str] = []
        stream_payload = dict(payload)
        stream_payload["stream"] = True

        with self._http_client.stream(
            "POST",
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=stream_payload,
        ) as resp:
            if not resp.is_success:
                body = resp.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"{resp.status_code} {body[:200]}")

            for line in resp.iter_lines():
                delta = extract_stream_delta(line)
                if delta is None:
                    continue
                content_parts.append(delta)
                self._emit_progress("token", {"content": delta, "label": label})

        content = "".join(content_parts)
        self._emit_progress("section", {"title": label, "status": "done"})
        return content

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

    def evaluate_repository(
        self,
        *,
        commits: List[Dict[str, Any]],
        repo_label: str,
        max_commits: Optional[int] = None,
        load_files: bool = True,
        use_chunking: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluate a repository as one unit, without filtering commits by author.

        This is used by Courses group evaluation for the tag "整体", where the
        object being scored is the repo's complete performance rather than a
        single contributor's trajectory.
        """
        if not commits:
            return self._get_empty_evaluation(repo_label)
        analyzed_commits = commits if max_commits is None else commits[: int(max_commits)]
        if use_chunking:
            return self._evaluate_engineer_chunked(analyzed_commits, repo_label, load_files=load_files)
        return self._evaluate_repository_standard(analyzed_commits, repo_label, load_files=load_files)

    def _evaluate_repository_standard(self, commits: List[Dict[str, Any]], repo_label: str, *, load_files: bool) -> Dict[str, Any]:
        file_contents: Dict[str, str] = {}
        repo_structure: Optional[Dict[str, Any]] = None
        if self.mode == "moderate" and load_files and self.data_dir:
            file_contents = self._load_relevant_files(commits)
            repo_structure = self._load_repo_structure()

        context_parts, checker_raw_analysis = self._build_context_parts(
            commits,
            repo_label,
            file_contents=file_contents,
            repo_structure=repo_structure,
            commit_limit=None,
        )

        partial_results: List[Dict[str, Any]] = []
        for part_name, part_context in context_parts.items():
            if part_context:
                part_result = self._evaluate_part_with_llm(part_name, part_context, repo_label, chunk_idx=None)
                partial_results.append(part_result)

        if partial_results:
            scores = self._merge_partial_evaluations(partial_results, repo_label, checker_raw_analysis=checker_raw_analysis)
        else:
            context = self._build_commit_context(
                commits,
                repo_label,
                file_contents=file_contents,
                repo_structure=repo_structure,
                commit_limit=None,
            )
            scores = self._evaluate_with_llm(context, repo_label)

        return {
            "username": repo_label,
            "total_commits_analyzed": len(commits),
            "files_loaded": len(file_contents),
            "mode": self.mode,
            "scores": scores,
            "commits_summary": self._summarize_commits(commits),
            "scope": "full_repo",
        }

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
        
        # Use multi-stage evaluation: split context into parts and evaluate separately
        context_parts, checker_raw_analysis = self._build_context_parts(commits, username, file_contents=file_contents, repo_structure=repo_structure)
        
        # Evaluate each part separately
        partial_results: List[Dict[str, Any]] = []
        for part_name, part_context in context_parts.items():
            if part_context:  # Only evaluate non-empty parts
                part_result = self._evaluate_part_with_llm(part_name, part_context, username, chunk_idx=None)
                partial_results.append(part_result)
        
        # Merge all partial results
        if partial_results:
            scores = self._merge_partial_evaluations(partial_results, username, checker_raw_analysis=checker_raw_analysis)
        else:
            # Fallback to single-stage if no parts
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

        if self.parallel_chunking:
            print(f"[Chunking] Using PARALLEL mode with {len(chunks)} chunks (max_workers={self.max_parallel_workers})")
            return self._evaluate_chunks_parallel(chunks, username, load_files=load_files)
        else:
            print(f"[Chunking] Using SEQUENTIAL mode with {len(chunks)} chunks")
            return self._evaluate_chunks_sequential(chunks, username, load_files=load_files)

    def _evaluate_chunks_sequential(self, chunks: List[List[Dict[str, Any]]], username: str, *, load_files: bool) -> Dict[str, Any]:
        """Original sequential chunking strategy"""
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

        # Flatten all commits for summary
        all_commits = [c for chunk in chunks for c in chunk]
        return {
            "username": username,
            "total_commits_analyzed": len(all_commits),
            "files_loaded": len(all_files),
            "mode": self.mode,
            "scores": accumulated or self._fallback_evaluation(""),
            "commits_summary": self._summarize_commits(all_commits),
            "chunked": True,
            "chunks_processed": len(chunks),
            "chunking_strategy": "sequential",
        }

    def _evaluate_chunks_parallel(self, chunks: List[List[Dict[str, Any]]], username: str, *, load_files: bool) -> Dict[str, Any]:
        """New parallel chunking strategy with LLM-based merge"""
        repo_structure = None
        if self.mode == "moderate" and load_files and self.data_dir:
            repo_structure = self._load_repo_structure()

        all_files: Dict[str, str] = {}
        chunk_results: List[Dict[str, Any]] = []

        def evaluate_single_chunk(idx: int, chunk: List[Dict[str, Any]]) -> tuple[int, Dict[str, Any], Dict[str, str]]:
            """Evaluate a single chunk independently"""
            chunk_files: Dict[str, str] = {}
            if self.mode == "moderate" and load_files and self.data_dir:
                chunk_files = self._load_relevant_files(chunk)

            # Build context WITHOUT previous evaluation (parallel chunks are independent)
            context = self._build_commit_context(
                chunk,
                username,
                file_contents=chunk_files,
                repo_structure=repo_structure if idx == 1 else None,
            )

            # Add chunk metadata to context
            context_with_meta = f"CHUNK {idx}/{len(chunks)}\n\n{context}"

            chunk_scores = self._evaluate_with_llm(context_with_meta, username, chunk_idx=idx)
            print(f"[Parallel] Chunk {idx}/{len(chunks)} completed")
            return idx, chunk_scores, chunk_files

        # Execute chunks in parallel
        with ThreadPoolExecutor(max_workers=self.max_parallel_workers) as executor:
            futures = {
                executor.submit(evaluate_single_chunk, idx, chunk): idx
                for idx, chunk in enumerate(chunks, 1)
            }

            for future in as_completed(futures):
                try:
                    idx, scores, files = future.result()
                    chunk_results.append({"chunk_idx": idx, "scores": scores})
                    all_files.update(files)
                except Exception as e:
                    print(f"[Parallel] Chunk evaluation failed: {e}")
                    raise

        # Sort results by chunk index
        chunk_results.sort(key=lambda x: x["chunk_idx"])

        # Merge all chunk results using LLM-based intelligent merge
        print(f"[Parallel] All {len(chunk_results)} chunks completed, merging results...")
        merged_scores = self._merge_chunk_results_with_llm(chunk_results, username)

        # Flatten all commits for summary
        all_commits = [c for chunk in chunks for c in chunk]
        return {
            "username": username,
            "total_commits_analyzed": len(all_commits),
            "files_loaded": len(all_files),
            "mode": self.mode,
            "scores": merged_scores,
            "commits_summary": self._summarize_commits(all_commits),
            "chunked": True,
            "chunks_processed": len(chunks),
            "chunking_strategy": "parallel",
        }

    def _merge_chunk_results_with_llm(self, chunk_results: List[Dict[str, Any]], username: str) -> Dict[str, Any]:
        """Use LLM to intelligently merge all parallel chunk evaluations"""
        is_chinese = self.language == "zh-CN"

        # Build merge prompt
        chunks_summary = []
        for result in chunk_results:
            idx = result["chunk_idx"]
            scores = result["scores"]
            chunks_summary.append(f"Chunk {idx}: {json.dumps(scores, ensure_ascii=False, indent=2)}")

        chunks_text = "\n\n".join(chunks_summary)

        if is_chinese:
            expected_feature_block = self._build_expected_feature_block(is_chinese)
            merge_instruction = f"""你是一位专业的工程能力评估员。下面是对用户 "{username}" 的 {len(chunk_results)} 个独立评估结果。

请综合所有评估结果，生成一个统一的最终评估：
1. 对于数值分数：考虑所有评估的整体趋势，给出合理的综合分数（不要简单平均）
2. 对于推理部分：整合所有评估中的关键发现，提供完整的 **主要优势**、**改进空间**、**整体评估** 部分
{expected_feature_block}

评估结果：
{chunks_text}

返回格式与之前相同的JSON格式。"""
        else:
            expected_feature_block = self._build_expected_feature_block(is_chinese)
            merge_instruction = f"""You are an expert engineering evaluator. Below are {len(chunk_results)} independent evaluations for user "{username}".

Synthesize all evaluations into a unified final assessment:
1. For numeric scores: Consider overall trends across all evaluations, provide reasonable consolidated scores (not simple averaging)
2. For reasoning: Integrate key findings from all evaluations, provide complete **Key Strengths**, **Areas for Growth**, **Overall Assessment** sections
{expected_feature_block}

Evaluation Results:
{chunks_text}

Return the same JSON format as before."""

        # Call LLM for intelligent merge
        try:
            merged = self._evaluate_with_llm(merge_instruction, username, chunk_idx=None)
            print(f"[Parallel] LLM merge completed successfully")
            return merged
        except Exception as e:
            print(f"[Parallel] LLM merge failed, falling back to simple averaging: {e}")
            # Fallback to simple averaging if LLM merge fails
            return self._simple_average_merge(chunk_results)

    def _simple_average_merge(self, chunk_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback: simple averaging of all chunk scores"""
        if not chunk_results:
            return {k: 0 for k in self.dimensions.keys()}

        merged: Dict[str, Any] = {}

        # Average numeric scores
        for k in self.dimensions.keys():
            scores = [r["scores"].get(k, 0) for r in chunk_results]
            merged[k] = int(sum(scores) / len(scores))

        # Concatenate reasoning
        reasonings = [r["scores"].get("reasoning", "") for r in chunk_results if r["scores"].get("reasoning")]
        if reasonings:
            merged["reasoning"] = "\n\n---\n\n".join(f"**Chunk {i+1}:**\n{r}" for i, r in enumerate(reasonings))
        else:
            merged["reasoning"] = "Multiple chunks evaluated."

        return merged

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
        worktree_base: Optional[str] = None,
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
            if worktree_base:
                payload["worktree_base"] = worktree_base
            resp = self._http_client.post(url, json=payload, timeout=120.0)  # Increased to 120s for git clone operations
            if resp.status_code == 200:
                result = resp.json()
                self._checker_cache[cache_key] = result
                return result
            else:
                error_msg = f"Checker API returned HTTP {resp.status_code}: {resp.text[:200]}"
                print(f"[Checker] Warning: Checker {checker_id} failed: {error_msg}")
                return {
                    "success": False,
                    "score": 0.0,
                    "message": error_msg,
                    "analysis": error_msg,
                    "error": error_msg,
                }
        except httpx.TimeoutException:
            error_msg = f"Checker {checker_id} timeout after 120s - service may not be responding"
            print(f"[Checker] Info: {error_msg}")
            return {
                "success": False,
                "score": 0.0,
                "message": error_msg,
                "analysis": error_msg,
                "error": "timeout",
            }
        except httpx.ConnectError:
            error_msg = f"Checker service not available for {checker_id}"
            print(f"[Checker] Info: {error_msg}")
            return {
                "success": False,
                "score": 0.0,
                "message": error_msg,
                "analysis": error_msg,
                "error": "connection_error",
            }
        except Exception as e:
            error_msg = f"Failed to run checker {checker_id}: {type(e).__name__}: {e}"
            print(f"[Checker] Warning: {error_msg}")
            return {
                "success": False,
                "score": 0.0,
                "message": error_msg,
                "analysis": error_msg,
                "error": str(e),
            }

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

    def _build_context_parts(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        *,
        file_contents: Dict[str, str],
        repo_structure: Optional[Dict[str, Any]],
        commit_limit: Optional[int] = 50,
    ) -> tuple:
        """
        Build context as separate parts for multi-stage LLM evaluation.
        Returns: (context_parts_dict, checker_raw_analysis)
        """
        """Build context as separate parts for multi-stage LLM evaluation."""
        parts: Dict[str, str] = {}
        
        # Extract checker keywords and run checkers
        import time
        checker_start = time.time()
        print(f"[Checker] [Plugin] Starting checker processing in _build_context_parts() at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(checker_start))}")
        
        checker_results_summary = []
        platform_owner_repo = self._get_platform_owner_repo_from_data_dir()
        
        if platform_owner_repo:
            platform, owner, repo = platform_owner_repo
            print(f"[Checker] [Plugin] Platform: {platform}, Owner: {owner}, Repo: {repo}")
            
            list_start = time.time()
            checker_list = self._get_checker_list()
            list_elapsed = time.time() - list_start
            print(f"[Checker] [Plugin] _get_checker_list() returned {len(checker_list)} checkers in {list_elapsed:.3f}s")
            
            checker_keyword_map = {c.get("keyword"): c.get("id") for c in checker_list if c.get("enabled")}
            print(f"[Checker] [Plugin] Enabled checkers: {list(checker_keyword_map.keys())}")
            
            # Process commits: check for /checker:xxx keywords
            commits_for_context = commits if commit_limit is None else commits[:commit_limit]
            for c in commits_for_context:
                sha = c.get("sha") or c.get("hash") or ""
                msg = c.get("message") or c.get("commit", {}).get("message") or ""
                keywords = self._extract_checker_keywords(msg)
                
                for keyword in keywords:
                    checker_id = checker_keyword_map.get(keyword)
                    if checker_id:
                        result = self._run_checker(checker_id, platform, owner, repo, sha, worktree_base=self.worktree_base)
                        if result:  # Include result even if success=False
                            checker_results_summary.append({
                                "checker": checker_id,
                                "commit": sha[:8],
                                "score": result.get("score", 0),
                                "message": result.get("message", ""),
                                "analysis": result.get("analysis", "") or result.get("error", ""),  # Include error if analysis is empty
                                "details": result.get("details", []),
                                "success": result.get("success", False),  # Include success status
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
                        files=python_files_list,  # Pass all Python files from checkpoint, or None for full repo scan
                        worktree_base=self.worktree_base
                    )
                    if result:  # Include result even if success=False, so frontend can display error info
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
                            "analysis": result.get("analysis", "") or result.get("error", ""),  # Include error if analysis is empty
                            "details": result.get("details", []),
                            "forced": True,
                            "success": result.get("success", False),  # Include success status
                        })
        
        checker_elapsed = time.time() - checker_start
        print(f"[Checker] [Plugin] Checker processing completed in {checker_elapsed:.3f}s, found {len(checker_results_summary)} results")
        
        # Extract checker raw analysis for final result
        checker_raw_analysis_parts: List[str] = []
        
        # Build checker results part
        if checker_results_summary:
            checker_parts: List[str] = [f"User: {username}", f"Commits: {len(commits)}", ""]
            checker_parts.append("## Code Quality Checker Results")
            for cr in checker_results_summary:
                forced_label = " [FORCED]" if cr.get("forced") else ""
                success_label = " [FAILED]" if not cr.get("success", True) else ""
                checker_parts.append(f"### {cr['checker']}{forced_label}{success_label} (commit {cr['commit']})")
                checker_parts.append(f"Score: {cr['score']}/100")
                checker_parts.append(f"Summary: {cr['message']}")
                if cr.get("analysis"):
                    checker_parts.append("")
                    checker_parts.append("Detailed Analysis:")
                    checker_parts.append(cr["analysis"])
                    # Also collect raw analysis for final result
                    checker_raw_analysis_parts.append(f"**{cr['checker']}{forced_label}{success_label}** (commit {cr['commit']}):\n{cr['analysis']}")
                checker_parts.append("")
            parts["checker_results"] = "\n".join(checker_parts)
        
        checker_raw_analysis = "\n\n".join(checker_raw_analysis_parts) if checker_raw_analysis_parts else None
        
        # Build commits part
        commits_parts: List[str] = [f"User: {username}", f"Commits: {len(commits)}", ""]
        commits_parts.append("COMMITS:")
        commits_for_context = commits if commit_limit is None else commits[:commit_limit]
        for c in commits_for_context:
            sha = c.get("sha") or c.get("hash") or ""
            msg = (c.get("message") or c.get("commit", {}).get("message") or "").split("\n")[0][:160]
            commits_parts.append(f"\n- {sha} {msg}")
            for f in (c.get("files") or [])[:30]:
                if isinstance(f, dict):
                    fn = f.get("filename") or ""
                    patch = f.get("patch") or ""
                    commits_parts.append(f"  * {fn}\n{patch[:4000]}")
        parts["commits"] = "\n".join(commits_parts)
        
        # Build file contents part
        if file_contents:
            files_parts: List[str] = [f"User: {username}", f"Commits: {len(commits)}", ""]
            files_parts.append("RELEVANT FILE CONTENTS:")
            for p, content in list(file_contents.items())[:25]:
                files_parts.append(f"\n--- FILE: {p} ---\n{content[:12000]}")
            parts["file_contents"] = "\n".join(files_parts)
        
        # Build repo structure part
        if repo_structure:
            repo_parts: List[str] = [f"User: {username}", f"Commits: {len(commits)}", ""]
            repo_parts.append("REPO STRUCTURE (truncated):")
            repo_parts.append(json.dumps(repo_structure, ensure_ascii=False)[:8000])
            parts["repo_structure"] = "\n".join(repo_parts)
        
        return parts, checker_raw_analysis

    def _build_commit_context(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        *,
        file_contents: Dict[str, str],
        repo_structure: Optional[Dict[str, Any]],
        commit_limit: Optional[int] = 50,
    ) -> str:
        parts: List[str] = [f"User: {username}", f"Commits: {len(commits)}", ""]
        
        # Extract checker keywords and run checkers FIRST (before other content)
        # This ensures checker results are not truncated when context is too long
        import time
        checker_start = time.time()
        print(f"[Checker] [Plugin] Starting checker processing in _build_commit_context() at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(checker_start))}")
        
        checker_results_summary = []
        platform_owner_repo = self._get_platform_owner_repo_from_data_dir()
        
        if platform_owner_repo:
            platform, owner, repo = platform_owner_repo
            print(f"[Checker] [Plugin] Platform: {platform}, Owner: {owner}, Repo: {repo}")
            
            list_start = time.time()
            checker_list = self._get_checker_list()
            list_elapsed = time.time() - list_start
            print(f"[Checker] [Plugin] _get_checker_list() returned {len(checker_list)} checkers in {list_elapsed:.3f}s")
            
            checker_keyword_map = {c.get("keyword"): c.get("id") for c in checker_list if c.get("enabled")}
            print(f"[Checker] [Plugin] Enabled checkers: {list(checker_keyword_map.keys())}")
            
            # Process commits: check for /checker:xxx keywords
            commits_for_context = commits if commit_limit is None else commits[:commit_limit]
            for c in commits_for_context:
                sha = c.get("sha") or c.get("hash") or ""
                msg = c.get("message") or c.get("commit", {}).get("message") or ""
                keywords = self._extract_checker_keywords(msg)
                
                for keyword in keywords:
                    checker_id = checker_keyword_map.get(keyword)
                    if checker_id:
                        result = self._run_checker(checker_id, platform, owner, repo, sha, worktree_base=self.worktree_base)
                        if result:  # Include result even if success=False
                            checker_results_summary.append({
                                "checker": checker_id,
                                "commit": sha[:8],
                                "score": result.get("score", 0),
                                "message": result.get("message", ""),
                                "analysis": result.get("analysis", "") or result.get("error", ""),  # Include error if analysis is empty
                                "details": result.get("details", []),  # Function-level details
                                "success": result.get("success", False),  # Include success status
                            })
            
            # Force checker on last commit if forced_checker_id is set
            if self.forced_checker_id and commits:
                last_commit = commits[-1]  # Last commit in the checkpoint
                last_sha = last_commit.get("sha") or last_commit.get("hash") or ""
                if last_sha:
                    result = self._run_checker(self.forced_checker_id, platform, owner, repo, last_sha, worktree_base=self.worktree_base)
                    if result:  # Include result even if success=False
                        checker_results_summary.append({
                            "checker": self.forced_checker_id,
                            "commit": last_sha[:8],
                            "score": result.get("score", 0),
                            "message": result.get("message", ""),
                            "analysis": result.get("analysis", "") or result.get("error", ""),  # Include error if analysis is empty
                            "details": result.get("details", []),  # Function-level details
                            "success": result.get("success", False),  # Include success status
                            "forced": True,  # Mark as forced
                        })
        
        checker_elapsed = time.time() - checker_start
        print(f"[Checker] [Plugin] Checker processing completed in {checker_elapsed:.3f}s, found {len(checker_results_summary)} results")
        
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
        commits_for_context = commits if commit_limit is None else commits[:commit_limit]
        for c in commits_for_context:
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

    def _evaluate_part_with_llm(self, part_name: str, part_context: str, username: str, chunk_idx: Optional[int] = None) -> Dict[str, Any]:
        """Evaluate a single context part with LLM."""
        is_chinese = self.language == "zh-CN"
        part_label = {
            "checker_results": "代码质量检查器结果" if is_chinese else "Code Quality Checker Results",
            "commits": "提交记录" if is_chinese else "Commits",
            "file_contents": "文件内容" if is_chinese else "File Contents",
            "repo_structure": "仓库结构" if is_chinese else "Repository Structure",
        }.get(part_name, part_name)
        
        print(f"[Multi-Stage] Evaluating part: {part_name} ({part_label})")
        
        # Build prompt for this part
        prompt_template_tokens = 900
        max_context_tokens = self.max_input_tokens - prompt_template_tokens
        part_context = self._truncate_context(part_context, max_context_tokens)
        
        # Build previous checkpoint context if available
        previous_scores_block = ""
        if self.previous_checkpoint_scores:
            prev_scores = {k: v for k, v in self.previous_checkpoint_scores.items() if k != 'reasoning'}
            if is_chinese:
                previous_scores_block = f"\n\n上一个评估节点的分数（基线参考）:\n{json.dumps(prev_scores, ensure_ascii=False, indent=2)}\n注意：当前评估应该基于上一个节点的分数，除非有明确的负面证据，否则分数应该保持稳定或略有增长。"
            else:
                previous_scores_block = f"\n\nPREVIOUS CHECKPOINT SCORES (baseline reference):\n{json.dumps(prev_scores, ensure_ascii=False, indent=2)}\nNOTE: Current evaluation should build on previous scores. Maintain or gradually increase scores unless clear negative evidence exists."
        expected_feature_block = self._build_expected_feature_block(is_chinese)
        
        # Language-specific instructions
        if is_chinese:
            base_instruction = f'你是一位专业的工程能力评估员。分析用户 "{username}" 的{part_label}数据，并对每个维度评分（0-100分）。'
            mode_note = "\n注意：这是多阶段评估的一部分，请基于这部分数据给出初步评分。" if self.mode == "moderate" else ""
            chunked_instruction = ""
            if chunk_idx:
                chunked_instruction = "\n分块评估：基于之前的评分和新证据更新分数。"
            data_label = "数据"
            dimensions_label = "评估维度"
            return_json_instruction = "重要：必须只返回JSON对象，不要添加任何解释性文字、markdown格式或代码块标记。直接返回JSON，格式如下："
        else:
            base_instruction = f'You are an expert engineering evaluator. Analyze {part_label} data from user "{username}" and score each dimension 0-100.'
            mode_note = "\nNOTE: This is part of a multi-stage evaluation. Provide preliminary scores based on this part of the data." if self.mode == "moderate" else ""
            chunked_instruction = ""
            if chunk_idx:
                chunked_instruction = "\nCHUNKED: Revise the previous assessment by incorporating new evidence."
            data_label = "DATA"
            dimensions_label = "DIMENSIONS"
            return_json_instruction = "IMPORTANT: Return ONLY a JSON object. Do NOT add explanatory text, markdown formatting, or code block markers. Return raw JSON directly in this format:"
        
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
            reasoning_example = f"基于{part_label}数据，提供包含 **主要优势**、**改进空间**、**整体评估** 的推理过程。如期望实现功能缺失，请说明缺失功能。"
            format_note = "每个维度评分范围：0-100"
        else:
            reasoning_example = f"Based on {part_label} data, provide sections with **Key Strengths**, **Areas for Growth**, **Overall Assessment**. If the expected feature is lacking, describe the lacking feature."
            format_note = "Each dimension: score 0-100"
        
        fmt_example = {k: 0 for k in self.dimensions.keys()}
        fmt_example["reasoning"] = reasoning_example
        fmt_text = json.dumps(fmt_example, ensure_ascii=False, indent=2)
        fmt_text_with_note = f"{format_note}\n\n{fmt_text}"
        
        prompt = (
            f'{base_instruction}'
            f"{mode_note}{chunked_instruction}{rubric_block}{previous_scores_block}{expected_feature_block}\n\n{data_label}:\n{part_context}\n\n{dimensions_label}:\n{dims_text}\n\n"
            f"{return_json_instruction}\n{fmt_text_with_note}"
        )
        
        # Call LLM
        models_to_try = [self.model] + (self.fallback_models or [])
        for m in models_to_try:
            try:
                content = self._complete_chat(m, prompt, label=f"评估{part_label}")
                print(f"[Multi-Stage] Part {part_name} response received ({len(content)} chars)")
                result = self._parse_llm_response_with_retry(content, prompt, m)
                result["_part_name"] = part_name  # Mark which part this result came from
                return result
            except Exception as e:
                print(f"[Multi-Stage] Error evaluating part {part_name}: {e}")
                continue
        
        # Fallback if all models fail
        fallback = self._get_fallback_evaluation()
        fallback["_part_name"] = part_name
        return fallback
    
    def _merge_partial_evaluations(self, partial_results: List[Dict[str, Any]], username: str, checker_raw_analysis: Optional[str] = None) -> Dict[str, Any]:
        """Merge multiple partial evaluation results into final scores using weighted average."""
        if not partial_results:
            return self._get_fallback_evaluation()
        
        is_chinese = self.language == "zh-CN"
        
        # Weight different parts differently (checker results are more important)
        part_weights = {
            "checker_results": 2.0,  # Checker results are most important
            "commits": 1.5,           # Commits are important
            "file_contents": 1.0,     # File contents provide context
            "repo_structure": 0.5,    # Repo structure is less important
        }
        
        # Collect all scores with weights
        weighted_scores: Dict[str, List[tuple]] = {}  # List of (score, weight) tuples
        all_reasonings: List[str] = []
        part_names: List[str] = []  # Track which parts contributed
        
        for idx, result in enumerate(partial_results):
            # Try to identify which part this result came from (if available)
            part_name = "unknown"
            if hasattr(result, 'get') and isinstance(result, dict):
                part_name = result.get("_part_name", "unknown")
            
            weight = part_weights.get(part_name, 1.0)
            
            for dim in self.dimensions.keys():
                if dim not in weighted_scores:
                    weighted_scores[dim] = []
                score = result.get(dim, 0)
                if isinstance(score, (int, float)) and score > 0:
                    weighted_scores[dim].append((int(score), weight))
            
            if "reasoning" in result:
                part_label = {
                    "checker_results": "代码质量检查器" if is_chinese else "Code Quality Checker",
                    "commits": "提交记录" if is_chinese else "Commits",
                    "file_contents": "文件内容" if is_chinese else "File Contents",
                    "repo_structure": "仓库结构" if is_chinese else "Repository Structure",
                }.get(part_name, part_name)
                all_reasonings.append(f"**{part_label}**: {result['reasoning']}")
        
        # Calculate weighted average scores
        final_scores: Dict[str, Any] = {}
        for dim in self.dimensions.keys():
            if dim in weighted_scores and weighted_scores[dim]:
                total_weighted_score = sum(score * weight for score, weight in weighted_scores[dim])
                total_weight = sum(weight for _, weight in weighted_scores[dim])
                if total_weight > 0:
                    final_scores[dim] = int(total_weighted_score / total_weight)
                else:
                    final_scores[dim] = 0
            else:
                final_scores[dim] = 0
        
        # Merge reasoning with clear sections
        reasoning_parts: List[str] = []
        
        # Add checker raw analysis first if available (this is the actual checker output)
        if checker_raw_analysis:
            checker_label = "代码质量检查器原始分析" if is_chinese else "Code Quality Checker Raw Analysis"
            reasoning_parts.append(f"**{checker_label}**:\n\n{checker_raw_analysis}")
        
        # Add LLM evaluations from each part
        if all_reasonings:
            reasoning_parts.extend(all_reasonings)
        
        if reasoning_parts:
            merged_reasoning = "\n\n".join(reasoning_parts)
            final_scores["reasoning"] = merged_reasoning
        else:
            final_scores["reasoning"] = "Multi-stage evaluation completed." if not is_chinese else "多阶段评估完成。"
        
        print(f"[Multi-Stage] Merged {len(partial_results)} partial evaluations into final scores")
        return final_scores
    
    def _evaluate_with_llm(self, context: str, username: str, chunk_idx: Optional[int] = None) -> Dict[str, Any]:
        allow_fallback = str(os.getenv("OSCANNER_ALLOW_FALLBACK") or "").strip().lower() in ("1", "true", "yes", "y")
        if not self.api_key:
            print("[ERROR] LLM API key not configured")
            if allow_fallback:
                return self._fallback_evaluation(context)
            raise RuntimeError("LLM not configured (missing API key)")
        prompt = self._build_evaluation_prompt(context, username, chunk_idx=chunk_idx)
        print(f"[DEBUG] Prompt length: {len(prompt)} chars")
        print(f"[DEBUG] Prompt sample (last 500 chars): {prompt[-500:]}")

        models_to_try = [self.model] + (self.fallback_models or [])
        last_err = None
        for m in models_to_try:
            try:
                print(f"[LLM] Calling {m} at {self.api_url}")
                print(f"[DEBUG] Request config: temperature=0.3, max_tokens=4000")

                content = self._complete_chat(m, prompt, label="生成整体评估")
                print(f"[LLM] Response received ({len(content)} chars), parsing...")
                return self._parse_llm_response_with_retry(content, prompt, m)

            except KeyError as e:
                last_err = f"KeyError accessing response structure: {e}"
                print(f"[ERROR] {last_err}")
                continue
            except Exception as e:
                last_err = str(e)
                print(f"[ERROR] LLM request failed for model {m}: {last_err}")
                import traceback
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")
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
                previous_scores_block = f"\n\n上一个评估节点的分数（基线参考）:\n{json.dumps(prev_scores, ensure_ascii=False, indent=2)}\n注意：当前评估应该基于上一个节点的分数，除非有明确的负面证据，否则分数应该保持稳定或略有增长。"
            else:
                previous_scores_block = f"\n\nPREVIOUS CHECKPOINT SCORES (baseline reference):\n{json.dumps(prev_scores, ensure_ascii=False, indent=2)}\nNOTE: Current evaluation should build on previous scores. Maintain or gradually increase scores unless clear negative evidence exists."
        expected_feature_block = self._build_expected_feature_block(is_chinese)

        # Language-specific instructions
        if is_chinese:
            base_instruction = f'你是一位专业的工程能力评估员。分析用户 "{username}" 的数据，并对每个维度评分（0-100分）。'
            mode_note = ""
            if self.mode == "moderate":
                mode_note = "\n注意：你可能会看到提交差异（commit diffs）和文件内容。在有帮助的情况下请使用文件内容。"
            chunked_instruction = ""
            if chunk_idx:
                chunked_instruction = "\n分块评估：基于之前的评分和新证据更新分数。提供完整的推理过程，包括**主要优势**、**改进空间**、**整体评估**部分（不要重复部分）。"
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
                chunked_instruction = "\nCHUNKED: Revise the previous assessment by incorporating new evidence. Provide ONE consolidated reasoning with updated Key Strengths, Areas for Growth, and Overall Assessment sections (do not repeat sections)."
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
            reasoning_example = "使用评分标准。提供包含 **主要优势**、**改进空间**、**整体评估** 的推理过程。如期望实现功能缺失，请说明缺失功能。"
            format_note = "每个维度评分范围：0-100"
            json_instruction = "重要：必须只返回JSON对象，不要添加任何解释性文字、markdown格式或代码块标记。直接返回JSON，格式如下："
        else:
            reasoning_example = "Use the rubric. Provide sections with **Key Strengths**, **Areas for Growth**, **Overall Assessment**. If the expected feature is lacking, describe the lacking feature."
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
        # Use the new reasoning which already consolidates previous + new evidence
        nr = str(new.get("reasoning", "")).strip()
        out["reasoning"] = nr if nr else str(prev.get("reasoning", "")).strip()
        out["chunks_merged"] = chunk_idx
        return out

    def _fallback_evaluation(self, context: str) -> Dict[str, Any]:
        text = (context or "").lower()

        def score_by_keywords(keywords: List[str]) -> int:
            hits = sum(1 for kw in keywords if kw in text)
            if not keywords:
                return 0
            return min(100, int((hits / len(keywords)) * 100))

        # Heuristic keywords tuned toward engineer_level.md signals
        kw = {
            "ai_fullstack": ["refactor", "test", "lint", "type", "validation", "error", "edge", "bugfix"],
            "ai_architecture": ["architecture", "adr", "design", "interface", "module", "boundary", "migration", "trade-off"],
            "cloud_native": ["docker", "compose", "kubernetes", "deploy", "ci", "cd", "terraform", "devcontainer"],
            "open_source": ["pr", "review", "issue", "docs", "changelog", "release", "discussion", "community"],
            "intelligent_dev": ["automation", "script", "tool", "agent", "prompt", "eval", "dataset", "trace"],
            "leadership": ["security", "performance", "optimize", "reliability", "incident", "standard", "best practice"],
        }

        scores: Dict[str, Any] = {}
        for k in self.dimensions.keys():
            scores[k] = score_by_keywords(kw.get(k, []))

        scores["reasoning"] = (
            "**Note:** LLM not available or failed; using rubric-flavored keyword heuristic scoring.\n\n"
            "**Key Strengths:** Scores reflect presence of quality/reproducibility/professionalism signals in artifacts.\n\n"
            "**Areas for Growth:** Configure a working LLM provider for evidence-weighted, context-aware assessment.\n\n"
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
