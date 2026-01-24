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
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


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
"""


def create_commit_evaluator(
    *,
    data_dir: str,
    api_key: str,
    model: Optional[str] = None,
    mode: str = "moderate",
    language: str = "en-US",
    parallel_chunking: bool = False,
    max_parallel_workers: int = 5,
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
        max_input_tokens: int = 190000,
        data_dir: Optional[str] = None,
        mode: str = "moderate",
        model: Optional[str] = None,
        api_base_url: Optional[str] = None,
        chat_completions_url: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        rubric_text: Optional[str] = None,
        language: str = "en-US",
        parallel_chunking: bool = False,
        max_parallel_workers: int = 5,
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
        self.rubric_text = (rubric_text or "").strip()
        self.language = language
        self.parallel_chunking = parallel_chunking
        self.max_parallel_workers = max_parallel_workers

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
        if "author" in commit and isinstance(commit["author"], str):
            return commit["author"].lower() == username.lower()
        if "commit" in commit:
            author = commit.get("commit", {}).get("author", {}).get("name", "")
            return bool(author) and author.lower() == username.lower()
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

        # Merge all chunk results using simple averaging (fast)
        print(f"[Parallel] All {len(chunk_results)} chunks completed, merging results...")
        merged_scores = self._simple_average_merge(chunk_results)

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
            merge_instruction = f"""你是一位专业的工程能力评估员。下面是对用户 "{username}" 的 {len(chunk_results)} 个独立评估结果。

请综合所有评估结果，生成一个统一的最终评估：
1. 对于数值分数：考虑所有评估的整体趋势，给出合理的综合分数（不要简单平均）
2. 对于推理部分：整合所有评估中的关键发现，提供完整的 **主要优势**、**改进空间**、**整体评估** 部分

评估结果：
{chunks_text}

返回格式与之前相同的JSON格式。"""
        else:
            merge_instruction = f"""You are an expert engineering evaluator. Below are {len(chunk_results)} independent evaluations for user "{username}".

Synthesize all evaluations into a unified final assessment:
1. For numeric scores: Consider overall trends across all evaluations, provide reasonable consolidated scores (not simple averaging)
2. For reasoning: Integrate key findings from all evaluations, provide complete **Key Strengths**, **Areas for Growth**, **Overall Assessment** sections

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

    def _build_commit_context(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        *,
        file_contents: Dict[str, str],
        repo_structure: Optional[Dict[str, Any]],
    ) -> str:
        parts: List[str] = [f"User: {username}", f"Commits: {len(commits)}", ""]
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
                resp = requests.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": m,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 1500,
                    },
                    timeout=90,
                )
                if not resp.ok:
                    last_err = f"{resp.status_code} {resp.text[:200]}"
                    print(f"[ERROR] LLM API returned error: {last_err}")
                    continue
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                print(f"[LLM] Response received, parsing...")
                return self._parse_llm_response(content)
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
            reasoning_line = (
                "  \"reasoning\": \"使用评分标准。提供包含 **主要优势**、**改进空间**、**整体评估** 的推理过程。\""
            )
        else:
            reasoning_line = (
                "  \"reasoning\": \"Use the rubric. Provide sections with **Key Strengths**, **Areas for Growth**, **Overall Assessment**.\""
            )
        fmt_lines = ["{"] + [f'  "{k}": <0-100>,' for k in self.dimensions.keys()] + [reasoning_line, "}"]
        fmt_text = "\n".join(fmt_lines)

        return (
            f'{base_instruction}'
            f"{mode_note}{chunked_instruction}{rubric_block}\n\n{data_label}:\n{context}\n\n{dimensions_label}:\n{dims_text}\n\n"
            f"{return_json_instruction}:\n{fmt_text}"
        )

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
                out: Dict[str, Any] = {}
                for k in self.dimensions.keys():
                    out[k] = min(100, max(0, int(data.get(k, 0))))
                if "reasoning" in data:
                    out["reasoning"] = self._format_reasoning(str(data["reasoning"]))
                else:
                    # LLM didn't provide reasoning - add placeholder
                    print("[WARNING] LLM response missing 'reasoning' field")
                    out["reasoning"] = "LLM evaluation completed but reasoning was not provided."
                return out
        except Exception as e:
            print(f"[ERROR] Failed to parse LLM response: {e}")
            print(f"[ERROR] LLM response content: {content[:500]}")

        # Fallback with reasoning
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
        return {
            "username": username,
            "total_commits_analyzed": 0,
            "files_loaded": 0,
            "mode": self.mode,
            "scores": {k: 0 for k in self.dimensions.keys()},
            "commits_summary": {"total_additions": 0, "total_deletions": 0, "files_changed": 0, "languages": []},
        }


