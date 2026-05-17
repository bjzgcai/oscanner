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

import copy
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

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
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


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


def extract_stream_usage(line: str) -> Optional[Dict[str, Any]]:
    """Extract provider usage from an OpenAI-compatible SSE data line."""
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

    usage = payload.get("usage")
    return usage if isinstance(usage, dict) else None


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
    progress_callback: Optional[ProgressCallback] = None,
    max_input_tokens: Optional[int] = None,
):
    return CommitEvaluatorModerate(
        data_dir=data_dir,
        api_key=api_key,
        model=model,
        rubric_text=_RUBRIC_SUMMARY,
        language=language,
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

    DIMENSION_ASSESSMENT_MAX_CHARS = 600
    CONCLUSION_MAX_CHARS = 600

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        max_input_tokens: Optional[int] = None,
        data_dir: Optional[str] = None,
        model: Optional[str] = None,
        api_base_url: Optional[str] = None,
        chat_completions_url: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        rubric_text: Optional[str] = None,
        language: str = "en-US",
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
        self.model = model or os.getenv("OSCANNER_LLM_MODEL") or "deepseek/deepseek-v4-pro"
        self.fallback_models = fallback_models
        self.rubric_text = (rubric_text or "").strip()
        self.language = language
        self.previous_checkpoint_scores = previous_checkpoint_scores
        self.forced_checker_id = forced_checker_id
        self.worktree_base = worktree_base  # 'build' or 'temp'
        self.expected_feature = (expected_feature or "").strip()
        self.progress_callback = progress_callback
        self._token_usage_records: List[Dict[str, Any]] = []
        self._latest_dimension_evidence: Dict[str, List[Dict[str, Any]]] = {}

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
        self.dimension_titles_zh = {
            "spec_quality": "规范与内建质量",
            "cloud_architecture": "云原生与架构演进",
            "ai_engineering": "AI工程与自动演进",
            "mastery_professionalism": "工程修养与职业素养",
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
                "只根据提交信息和提交差异检查是否真正实现该功能；仓库快照文件和仓库结构只能作为理解提交的背景。"
                "如果实现缺失、不完整或只有表面痕迹，必须降低评分（相关维度分数），"
                "并在 reasoning 中明确写出 **期望实现功能**、**缺失功能** 和扣分原因。"
            )

        return (
            "\n\nEXPECTED FEATURE BASELINE:\n"
            f"{self.expected_feature}\n"
            "Use this expected feature as a core baseline for the overall evaluation. "
            "Check whether the commit messages and commit diffs actually implement it. "
            "Use repository snapshot files and repo structure only as background for understanding those commits. "
            "If the implementation is missing, incomplete, or only superficial, score lower on the relevant dimensions "
            "and explicitly report the expected feature, lacking feature, and scoring rationale in reasoning."
        )

    @staticmethod
    def _score_to_level(score: Any) -> str:
        try:
            numeric = int(score)
        except (TypeError, ValueError):
            numeric = 0
        if numeric >= 85:
            return "L5"
        if numeric >= 70:
            return "L4"
        if numeric >= 50:
            return "L3"
        if numeric >= 30:
            return "L2"
        return "L1"

    @staticmethod
    def _commit_sha(commit: Dict[str, Any]) -> str:
        return str(commit.get("sha") or commit.get("hash") or "").strip()

    @staticmethod
    def _commit_message(commit: Dict[str, Any]) -> str:
        raw = commit.get("message") or commit.get("commit", {}).get("message") or ""
        return str(raw).splitlines()[0].strip()

    @staticmethod
    def _commit_files(commit: Dict[str, Any], limit: int = 6) -> List[str]:
        files: List[str] = []
        for item in commit.get("files") or []:
            if isinstance(item, dict):
                filename = item.get("filename") or item.get("path") or item.get("name")
            else:
                filename = item
            if filename:
                files.append(str(filename))
            if len(files) >= limit:
                break
        return files

    def _dimension_matches_for_commit(self, commit: Dict[str, Any]) -> List[str]:
        message = self._commit_message(commit)
        files = self._commit_files(commit, limit=20)
        haystack = f"{message} {' '.join(files)}".lower()
        keyword_map = {
            "spec_quality": [
                "test", "spec", "schema", "valid", "lint", "format", "type", "refactor",
                "quality", "coverage", "bug", "fix", "edge", "unit", "integration",
            ],
            "cloud_architecture": [
                "docker", "compose", "k8s", "kubernetes", "helm", "deploy", "deployment",
                "workflow", "ci", "cd", "terraform", "pulumi", "infra", "architecture",
                "migration", "api", "server", "config",
            ],
            "ai_engineering": [
                "ai", "llm", "prompt", "agent", "tool", "eval", "trace", "model",
                "openai", "checker", "automation", "workflow", "rag", "embedding",
            ],
            "mastery_professionalism": [
                "doc", "readme", "adr", "security", "performance", "perf", "tradeoff",
                "trade-off", "review", "changelog", "license", "contributing", "fix",
            ],
        }
        matches: List[str] = []
        for dimension, keywords in keyword_map.items():
            if any(keyword in haystack for keyword in keywords):
                matches.append(dimension)
        return matches

    def _build_dimension_evidence(
        self,
        commits: List[Dict[str, Any]],
        checker_results_summary: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        evidence: Dict[str, List[Dict[str, Any]]] = {key: [] for key in self.dimensions.keys()}
        seen: Dict[str, set] = {key: set() for key in self.dimensions.keys()}

        def add_entry(dimension: str, entry: Dict[str, Any]) -> None:
            if dimension not in evidence:
                return
            key = (entry.get("sha"), entry.get("message"), tuple(entry.get("files") or []), entry.get("checker"))
            if key in seen[dimension]:
                return
            seen[dimension].add(key)
            if len(evidence[dimension]) < 5:
                evidence[dimension].append(entry)

        for commit in commits:
            sha = self._commit_sha(commit)
            message = self._commit_message(commit)
            files = self._commit_files(commit)
            if not sha and not message and not files:
                continue
            entry = {
                "sha": sha[:8] if sha else "",
                "message": message[:180] if message else "(no commit message)",
                "files": files,
            }
            for dimension in self._dimension_matches_for_commit(commit):
                add_entry(dimension, entry)

        for checker in checker_results_summary:
            checker_id = str(checker.get("checker") or "").strip()
            if not checker_id:
                continue
            add_entry(
                "spec_quality",
                {
                    "sha": str(checker.get("commit") or "").strip(),
                    "message": str(checker.get("message") or "Code quality checker result")[:180],
                    "files": [],
                    "checker": checker_id,
                    "score": checker.get("score", 0),
                },
            )

        fallback_commits = []
        for commit in commits[:3]:
            sha = self._commit_sha(commit)
            message = self._commit_message(commit)
            files = self._commit_files(commit)
            if sha or message or files:
                fallback_commits.append({
                    "sha": sha[:8] if sha else "",
                    "message": message[:180] if message else "(no commit message)",
                    "files": files,
                    "fallback": True,
                })

        for dimension in evidence:
            if not evidence[dimension]:
                for entry in fallback_commits:
                    add_entry(dimension, entry)
        return evidence

    @staticmethod
    def _format_evidence_entry(entry: Dict[str, Any], *, is_chinese: bool) -> str:
        sha = entry.get("sha") or "unknown"
        message = entry.get("message") or "(no commit message)"
        files = entry.get("files") or []
        checker = entry.get("checker")
        checker_suffix = ""
        if checker:
            score = entry.get("score", 0)
            checker_suffix = f"；checker={checker}，score={score}/100" if is_chinese else f"; checker={checker}, score={score}/100"
        files_text = ", ".join(str(f) for f in files[:6]) if files else ("未记录文件路径" if is_chinese else "no file paths recorded")
        if is_chinese:
            return f"- commit `{sha}`：{message}；文件：{files_text}{checker_suffix}"
        return f"- commit `{sha}`: {message}; files: {files_text}{checker_suffix}"

    def _reasoning_heading_labels(self, is_chinese: bool) -> Dict[str, List[str]]:
        labels: Dict[str, List[str]] = {}
        for key, english_title in self.dimensions.items():
            dimension_labels = [english_title]
            zh_title = self.dimension_titles_zh.get(key)
            if zh_title:
                dimension_labels.append(zh_title)
            labels[key] = dimension_labels

        labels["_conclusion"] = (
            ["结论与建议", "Conclusion And Suggestions", "Conclusion and Suggestions", "Conclusion"]
            if is_chinese
            else ["Conclusion And Suggestions", "Conclusion and Suggestions", "Conclusion", "结论与建议"]
        )
        return labels

    def _extract_reasoning_sections(self, reasoning: str, *, is_chinese: bool) -> Dict[str, str]:
        text = self._format_reasoning(reasoning)
        if not text:
            return {}

        labels = self._reasoning_heading_labels(is_chinese)
        label_to_key = {
            label.casefold(): key
            for key, key_labels in labels.items()
            for label in key_labels
        }
        label_pattern = "|".join(
            re.escape(label)
            for label in sorted(label_to_key.keys(), key=len, reverse=True)
        )
        heading_re = re.compile(
            rf"(?P<prefix>^|\n|:\s*)"
            rf"(?P<marker>#{{1,6}}\s*)?"
            rf"(?:\*\*)?\s*(?P<label>{label_pattern})\s*(?:\*\*)?\s*(?:[:：])?",
            re.IGNORECASE,
        )

        matches = []
        for match in heading_re.finditer(text):
            label = match.group("label").casefold()
            key = label_to_key.get(label)
            if key:
                matches.append((match.start(), match.end(), key))

        sections: Dict[str, str] = {}
        for idx, (start, end, key) in enumerate(matches):
            next_start = matches[idx + 1][0] if idx + 1 < len(matches) else len(text)
            body = text[end:next_start].strip(" \n\t:-：")
            if body and key not in sections:
                sections[key] = body
        return sections

    @staticmethod
    def _compact_reasoning_excerpt(text: str, max_chars: int) -> str:
        cleaned_lines = []
        for line in (text or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("- commit `", "* commit `")):
                continue
            cleaned_lines.append(stripped)
        compact = " ".join(cleaned_lines)
        compact = re.sub(r"\s+", " ", compact).strip()
        if len(compact) <= max_chars:
            return compact

        cut = compact[:max_chars].rstrip()
        for separator in ("。", "；", ";", "."):
            pos = cut.rfind(separator)
            if pos >= max_chars * 0.55:
                return cut[: pos + 1].strip()
        return f"{cut.rstrip()}..."

    def _dimension_assessment(
        self,
        dimension_key: str,
        all_reasonings: List[str],
        *,
        is_chinese: bool,
    ) -> str:
        snippets: List[str] = []
        seen = set()
        for reasoning in all_reasonings:
            section = self._extract_reasoning_sections(reasoning, is_chinese=is_chinese).get(dimension_key, "")
            excerpt = self._compact_reasoning_excerpt(section, self.DIMENSION_ASSESSMENT_MAX_CHARS)
            if excerpt and excerpt not in seen:
                snippets.append(excerpt)
                seen.add(excerpt)
            if len(snippets) >= 2:
                break
        return "\n\n".join(snippets)

    def _build_conclusion(
        self,
        final_scores: Dict[str, Any],
        all_reasonings: List[str],
        *,
        is_chinese: bool,
    ) -> List[str]:
        conclusion_snippets: List[str] = []
        seen = set()
        for reasoning in all_reasonings:
            section = self._extract_reasoning_sections(reasoning, is_chinese=is_chinese).get("_conclusion", "")
            excerpt = self._compact_reasoning_excerpt(section, self.CONCLUSION_MAX_CHARS)
            if excerpt and excerpt not in seen:
                conclusion_snippets.append(excerpt)
                seen.add(excerpt)
            if len(conclusion_snippets) >= 2:
                break

        ranked_dimensions = sorted(
            self.dimensions.keys(),
            key=lambda key: int(final_scores.get(key, 0) or 0),
        )
        low_dimensions = ranked_dimensions[:2]
        low_text = "、".join(
            f"{self.dimension_titles_zh.get(key, self.dimensions[key])}（{int(final_scores.get(key, 0) or 0)}/100，{self._score_to_level(final_scores.get(key, 0))}）"
            for key in low_dimensions
        )
        low_text_en = ", ".join(
            f"{self.dimensions[key]} ({int(final_scores.get(key, 0) or 0)}/100, {self._score_to_level(final_scores.get(key, 0))})"
            for key in low_dimensions
        )
        high_key = ranked_dimensions[-1] if ranked_dimensions else ""

        if is_chinese:
            title = "## 结论与建议"
            if conclusion_snippets:
                summary = " ".join(conclusion_snippets)
                summary = re.sub(r"^(结论|总结|建议)\s*[:：]\s*", "", summary).strip()
                conclusion = f"结论：{summary}"
            else:
                high_text = self.dimension_titles_zh.get(high_key, self.dimensions.get(high_key, "")) if high_key else "当前证据"
                conclusion = f"结论：本次评估的主要差距集中在 {low_text}；相对较强的信号来自 {high_text}。"
            suggestion = f"建议：下一阶段优先围绕 {low_text} 建立可复现的改进闭环，并让后续提交明确呈现验证、自动化和设计取舍。"
            return [title, "", conclusion, suggestion]

        title = "## Conclusion And Suggestions"
        if conclusion_snippets:
            summary = " ".join(conclusion_snippets)
            summary = re.sub(r"^(conclusion|summary|suggestion)s?\s*:\s*", "", summary, flags=re.IGNORECASE).strip()
            conclusion = f"Conclusion: {summary}"
        else:
            high_text = self.dimensions.get(high_key, "available evidence") if high_key else "available evidence"
            conclusion = f"Conclusion: The largest gaps are in {low_text_en}; the strongest signal comes from {high_text}."
        suggestion = f"Suggestion: Prioritize {low_text_en} with reproducible improvement loops, and make later commits show verification, automation, and design trade-offs clearly."
        return [title, "", conclusion, suggestion]

    def _format_structured_reasoning(
        self,
        final_scores: Dict[str, Any],
        all_reasonings: List[str],
        checker_raw_analysis: Optional[str],
    ) -> str:
        is_chinese = self.language == "zh-CN"
        evidence = self._latest_dimension_evidence or {key: [] for key in self.dimensions.keys()}
        sections: List[str] = []

        for key, english_title in self.dimensions.items():
            title = self.dimension_titles_zh.get(key, english_title) if is_chinese else english_title
            score = int(final_scores.get(key, 0) or 0)
            level = self._score_to_level(score)
            if is_chinese:
                sections.append(f"## {title}\n\n分数：{score}/100\n等级：{level}\n\n证据：")
            else:
                sections.append(f"## {title}\n\nScore: {score}/100\nLevel: {level}\n\nEvidence:")

            entries = evidence.get(key) or []
            if entries:
                sections.extend(self._format_evidence_entry(entry, is_chinese=is_chinese) for entry in entries)
            else:
                sections.append("- 暂无可定位到提交和文件路径的直接证据。" if is_chinese else "- No direct commit/file evidence was available.")

            dimension_reasoning = self._dimension_assessment(key, all_reasonings, is_chinese=is_chinese)
            if dimension_reasoning:
                label = "评估判断" if is_chinese else "Assessment"
                sections.append("")
                sections.append(f"{label}：{dimension_reasoning}")
            if checker_raw_analysis and key == "spec_quality":
                label = "检查器摘要" if is_chinese else "Checker Summary"
                sections.append("")
                sections.append(f"{label}：{checker_raw_analysis[:800]}")
            sections.append("")

        sections.extend(self._build_conclusion(final_scores, all_reasonings, is_chinese=is_chinese))
        return "\n".join(sections).strip()

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

    @staticmethod
    def _token_count(value: Any) -> Optional[int]:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)) and value >= 0:
            return int(value)
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            if cleaned.isdigit():
                return int(cleaned)
        return None

    @classmethod
    def _normalize_token_usage(cls, usage: Any, source: str = "provider") -> Optional[Dict[str, Any]]:
        if not isinstance(usage, dict):
            return None

        input_tokens = (
            cls._token_count(usage.get("input_tokens"))
            or cls._token_count(usage.get("inputTokens"))
            or cls._token_count(usage.get("prompt_tokens"))
            or cls._token_count(usage.get("promptTokens"))
        )
        output_tokens = (
            cls._token_count(usage.get("output_tokens"))
            or cls._token_count(usage.get("outputTokens"))
            or cls._token_count(usage.get("completion_tokens"))
            or cls._token_count(usage.get("completionTokens"))
        )
        total_tokens = (
            cls._token_count(usage.get("total_tokens"))
            or cls._token_count(usage.get("totalTokens"))
        )

        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        if input_tokens is None and total_tokens is not None and output_tokens is not None:
            input_tokens = max(total_tokens - output_tokens, 0)
        if output_tokens is None and total_tokens is not None and input_tokens is not None:
            output_tokens = max(total_tokens - input_tokens, 0)

        if input_tokens is None and output_tokens is None and total_tokens is None:
            return None

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "source": source,
        }

    @staticmethod
    def _estimate_token_count(text: str) -> Optional[int]:
        normalized = str(text or "").strip()
        if not normalized:
            return None
        cjk_count = len(CJK_PATTERN.findall(normalized))
        compact_non_cjk = CJK_PATTERN.sub("", normalized)
        compact_non_cjk = re.sub(r"\s+", "", compact_non_cjk)
        non_cjk_estimate = math.ceil(len(compact_non_cjk) / 4) if compact_non_cjk else 0
        return max(1, cjk_count + non_cjk_estimate)

    def _record_chat_token_usage(
        self,
        *,
        prompt: str,
        content: str,
        provider_usage: Optional[Dict[str, Any]],
    ) -> None:
        usage = self._normalize_token_usage(provider_usage, source="provider")
        if not usage:
            input_tokens = self._estimate_token_count(prompt)
            output_tokens = self._estimate_token_count(content)
            if input_tokens is None and output_tokens is None:
                return
            usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": (input_tokens or 0) + (output_tokens or 0),
                "source": "estimated",
            }
        self._token_usage_records.append(usage)

    def _reset_token_usage(self) -> None:
        self._token_usage_records = []

    def _summarize_token_usage(self) -> Optional[Dict[str, Any]]:
        if not self._token_usage_records:
            return None

        summary: Dict[str, Any] = {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "source": "provider"
            if all(record.get("source") == "provider" for record in self._token_usage_records)
            else "estimated",
        }
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            values = [
                record.get(field)
                for record in self._token_usage_records
                if isinstance(record.get(field), int)
            ]
            if values:
                summary[field] = sum(values)

        if summary["total_tokens"] is None and (
            summary["input_tokens"] is not None or summary["output_tokens"] is not None
        ):
            summary["total_tokens"] = (summary["input_tokens"] or 0) + (summary["output_tokens"] or 0)

        return summary

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
            content = data["choices"][0]["message"]["content"]
            self._record_chat_token_usage(prompt=prompt, content=content, provider_usage=data.get("usage"))
            return content

        self._emit_progress("section", {"title": label, "status": "running"})
        content_parts: List[str] = []
        stream_payload = dict(payload)
        stream_payload["stream"] = True
        stream_payload["stream_options"] = {"include_usage": True}
        provider_usage: Optional[Dict[str, Any]] = None

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
                usage = extract_stream_usage(line)
                if usage:
                    provider_usage = usage
                delta = extract_stream_delta(line)
                if delta is None:
                    continue
                content_parts.append(delta)
                self._emit_progress("token", {"content": delta, "label": label})

        content = "".join(content_parts)
        self._record_chat_token_usage(prompt=prompt, content=content, provider_usage=provider_usage)
        self._emit_progress("section", {"title": label, "status": "done"})
        return content

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

    def evaluate_repository(
        self,
        *,
        commits: List[Dict[str, Any]],
        repo_label: str,
        max_commits: Optional[int] = None,
        load_files: bool = True,
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
        if self._commits_exceed_prompt_budget(
            analyzed_commits,
            repo_label,
            load_files=load_files,
            include_all_repo_snapshot=True,
        ):
            return self._evaluate_engineer_chunked(analyzed_commits, repo_label, load_files=load_files)
        return self._evaluate_repository_standard(analyzed_commits, repo_label, load_files=load_files)

    def _evaluate_repository_standard(self, commits: List[Dict[str, Any]], repo_label: str, *, load_files: bool) -> Dict[str, Any]:
        self._reset_token_usage()
        file_contents: Dict[str, str] = {}
        repo_structure: Optional[Dict[str, Any]] = None
        if load_files and self.data_dir:
            file_contents = self._load_context_files(commits, include_all_repo_snapshot=True)
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

        result = {
            "username": repo_label,
            "total_commits_analyzed": len(commits),
            "files_loaded": len(file_contents),
            "mode": "moderate",
            "scores": scores,
            "commits_summary": self._summarize_commits(commits),
            "scope": "full_repo",
        }
        token_usage = self._summarize_token_usage()
        if token_usage:
            result["token_usage"] = token_usage
        return result

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
        self._reset_token_usage()
        file_contents: Dict[str, str] = {}
        repo_structure: Optional[Dict[str, Any]] = None
        if load_files and self.data_dir:
            file_contents = self._load_context_files(commits)
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
        
        result = {
            "username": username,
            "total_commits_analyzed": len(commits),
            "files_loaded": len(file_contents),
            "mode": "moderate",
            "scores": scores,
            "commits_summary": self._summarize_commits(commits),
        }
        token_usage = self._summarize_token_usage()
        if token_usage:
            result["token_usage"] = token_usage
        return result

    def _prompt_token_count(self, context: str, username: str, *, chunk_idx: Optional[int] = None) -> int:
        prompt = self._build_evaluation_prompt(context, username, chunk_idx=chunk_idx)
        return self._estimate_tokens(prompt)

    def _commits_exceed_prompt_budget(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        *,
        load_files: bool,
        include_all_repo_snapshot: bool = False,
    ) -> bool:
        file_contents: Dict[str, str] = {}
        repo_structure: Optional[Dict[str, Any]] = None
        if load_files and self.data_dir:
            file_contents = self._load_context_files(
                commits,
                include_all_repo_snapshot=include_all_repo_snapshot,
            )
            repo_structure = self._load_repo_structure()
        context = self._build_commit_context(
            commits,
            username,
            file_contents=file_contents,
            repo_structure=repo_structure,
            commit_limit=None,
        )
        prompt_tokens = self._prompt_token_count(context, username)
        if prompt_tokens > self.max_input_tokens:
            print(
                f"[Chunking] Prompt estimate {prompt_tokens} tokens exceeds "
                f"budget {self.max_input_tokens}; splitting sequentially"
            )
            return True
        return False

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

    def _split_commits_for_prompt_budget(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        *,
        load_files: bool,
    ) -> Tuple[List[List[Dict[str, Any]]], List[Dict[str, Any]]]:
        repo_structure = None
        if load_files and self.data_dir:
            repo_structure = self._load_repo_structure()

        chunks: List[List[Dict[str, Any]]] = []
        input_budget_errors: List[Dict[str, Any]] = []
        current: List[Dict[str, Any]] = []
        for commit in commits:
            candidate = [*current, commit]
            candidate_files: Dict[str, str] = {}
            if load_files and self.data_dir:
                candidate_files = self._load_context_files(candidate)
            context = self._build_commit_context(
                candidate,
                username,
                file_contents=candidate_files,
                repo_structure=repo_structure if not chunks else None,
                commit_limit=None,
            )
            if self._prompt_token_count(context, username, chunk_idx=len(chunks) + 1) <= self.max_input_tokens:
                current = candidate
                continue
            if current:
                chunks.append(current)
                current = [commit]
                single_files: Dict[str, str] = {}
                if load_files and self.data_dir:
                    single_files = self._load_context_files(current)
                single_context = self._build_commit_context(
                    current,
                    username,
                    file_contents=single_files,
                    repo_structure=None,
                    commit_limit=None,
                )
                if self._prompt_token_count(single_context, username, chunk_idx=len(chunks) + 1) > self.max_input_tokens:
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
        return chunks, input_budget_errors

    def _evaluate_engineer_chunked(self, commits: List[Dict[str, Any]], username: str, *, load_files: bool) -> Dict[str, Any]:
        chunks, input_budget_errors = self._split_commits_for_prompt_budget(commits, username, load_files=load_files)
        print(f"[Chunking] Using token-budget SEQUENTIAL mode with {len(chunks)} chunks")
        return self._evaluate_chunks_sequential(
            chunks,
            username,
            load_files=load_files,
            input_budget_errors=input_budget_errors,
        )

    def _evaluate_chunks_sequential(
        self,
        chunks: List[List[Dict[str, Any]]],
        username: str,
        *,
        load_files: bool,
        input_budget_errors: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Evaluate budget-sized chunks in chronological order."""
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

        # Flatten all commits for summary
        all_commits = [c for chunk in chunks for c in chunk]
        if accumulated is None:
            raise RuntimeError("LLM evaluation failed: no chunks were evaluated")

        result = {
            "username": username,
            "total_commits_analyzed": len(all_commits),
            "files_loaded": len(all_files),
            "mode": "moderate",
            "scores": accumulated,
            "commits_summary": self._summarize_commits(all_commits),
            "chunked": True,
            "chunks_processed": len(chunks),
            "chunking_strategy": "sequential",
        }
        if input_budget_errors:
            warnings = [error["message"] for error in input_budget_errors]
            result["input_truncated"] = True
            result["warnings"] = warnings
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
                        files=python_files_list,
                        worktree_base=self.worktree_base
                    )
                    if result:  # Include result even if success=False, so frontend can display error info
                        # Update message to indicate checkpoint scope
                        message = result.get("message", "")
                        message = f"Checked {len(all_python_files)} Python files across {len(commits)} commits in checkpoint. {message}"
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
        self._latest_dimension_evidence = self._build_dimension_evidence(commits, checker_results_summary)
        
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
        if repo_structure:
            commits_parts.append("BACKGROUND REPO STRUCTURE (not scoring evidence; use only to understand commit diffs/messages):")
            commits_parts.append(json.dumps(repo_structure, ensure_ascii=False)[:8000])
            commits_parts.append("")
        if file_contents:
            commits_parts.append("BACKGROUND REPOSITORY FILES (not scoring evidence; use only to understand files referenced by commit diffs/messages):")
            for p, content in file_contents.items():
                commits_parts.append(f"\n--- FILE: {p} ---\n{content}")
            commits_parts.append("")
        commits_parts.append("COMMITS:")
        commits_for_context = commits if commit_limit is None else commits[:commit_limit]
        for c in commits_for_context:
            sha = c.get("sha") or c.get("hash") or ""
            msg = c.get("message") or c.get("commit", {}).get("message") or ""
            commits_parts.append(f"\n- {sha} {msg}")
            for f in (c.get("files") or []):
                if isinstance(f, dict):
                    fn = f.get("filename") or ""
                    patch = f.get("patch") or ""
                    commits_parts.append(f"  * {fn}\n{patch}")
        parts["commits"] = "\n".join(commits_parts)

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
            
            # Force checker only on changed Python files; whole-repo checker output is not valid author/range evidence.
            if self.forced_checker_id and commits:
                all_python_files = set()
                for commit in commits:
                    commit_files = commit.get("files", [])
                    if isinstance(commit_files, list):
                        for f in commit_files:
                            filename = f.get("filename", "") if isinstance(f, dict) else str(f)
                            if filename.endswith(".py"):
                                all_python_files.add(filename)
                last_commit = commits[-1]  # Last commit in the checkpoint
                last_sha = last_commit.get("sha") or last_commit.get("hash") or ""
                if last_sha and all_python_files:
                    result = self._run_checker(
                        self.forced_checker_id,
                        platform,
                        owner,
                        repo,
                        last_sha,
                        files=sorted(all_python_files),
                        worktree_base=self.worktree_base,
                    )
                    if result:  # Include result even if success=False
                        message = result.get("message", "")
                        message = f"Checked {len(all_python_files)} Python files across {len(commits)} commits in checkpoint. {message}"
                        checker_results_summary.append({
                            "checker": self.forced_checker_id,
                            "commit": last_sha[:8],
                            "score": result.get("score", 0),
                            "message": message,
                            "analysis": result.get("analysis", "") or result.get("error", ""),  # Include error if analysis is empty
                            "details": result.get("details", []),  # Function-level details
                            "success": result.get("success", False),  # Include success status
                            "forced": True,  # Mark as forced
                        })
        
        checker_elapsed = time.time() - checker_start
        print(f"[Checker] [Plugin] Checker processing completed in {checker_elapsed:.3f}s, found {len(checker_results_summary)} results")
        
        self._latest_dimension_evidence = self._build_dimension_evidence(commits, checker_results_summary)

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
        commits_for_context = commits if commit_limit is None else commits[:commit_limit]
        for c in commits_for_context:
            sha = c.get("sha") or c.get("hash") or ""
            msg = c.get("message") or c.get("commit", {}).get("message") or ""
            parts.append(f"\n- {sha} {msg}")
            for f in (c.get("files") or []):
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
            "container": ("Dockerfile", "docker-compose.yml", "compose.yml", ".github/workflows/ci.yml"),
        }

        has_python = any(path.endswith((".py", ".pyi")) for path in changed_paths)
        has_node = any(path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")) for path in changed_paths)
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

    def _related_context_paths(self, changed_paths: Set[str], changed_contents: Dict[str, str], available_paths: Set[str]) -> Set[str]:
        selected: Set[str] = set()
        for path, content in changed_contents.items():
            if path.endswith((".py", ".pyi")):
                selected.update(self._python_import_candidates(path, content, available_paths))
            elif path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
                selected.update(self._js_import_candidates(path, content, available_paths))
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
            mode_note = (
                "\n注意：这是多阶段评估的一部分。只有提交信息、提交差异（commit diffs）和代码检查器结果可以作为评分证据。"
                "仓库快照文件和仓库结构只能作为背景帮助理解提交，不得单独用于评分或作为证据引用。"
            )
            chunked_instruction = ""
            if chunk_idx:
                chunked_instruction = "\n分块评估：基于之前的评分和新证据更新分数。"
            data_label = "数据"
            dimensions_label = "评估维度"
            return_json_instruction = "重要：必须只返回JSON对象，不要添加任何解释性文字、markdown格式或代码块标记。直接返回JSON，格式如下："
        else:
            base_instruction = f'You are an expert engineering evaluator. Analyze {part_label} data from user "{username}" and score each dimension 0-100.'
            mode_note = (
                "\nNOTE: This is part of a multi-stage evaluation. "
                "Only commit messages, commit diffs, and checker results are scoring evidence. "
                "Repository snapshot files and repo structure are background only. "
                "Do not cite repository snapshot files or repo structure as evidence unless the same path appears in a commit message or diff."
            )
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
            reasoning_example = (
                f"基于{part_label}数据，按四个维度组织 reasoning："
                "**规范与内建质量**、**云原生与架构演进**、**AI工程与自动演进**、**工程修养与职业素养**。"
                "每个维度写出评分对应的 L1-L5 等级，并引用来自 commit sha、commit message 和 commit diff 的可见证据（文件名/路径必须来自提交差异或提交信息）。"
                "最后写 **结论与建议**，该部分只给总结和建议，不重复证明细节。"
            )
            format_note = "每个维度评分范围：0-100"
        else:
            reasoning_example = (
                f"Based on {part_label} data, structure reasoning by the four dimensions: "
                "**Specification & Built-in Quality**, **Cloud-Native & Architecture Evolution**, "
                "**AI Engineering & Automated Evolution**, and **Engineering Mastery & Professionalism**. "
                "For each dimension include the L1-L5 level and visible evidence from commit sha, commit message, and commit diff (file names/paths must come from commit diffs or messages). "
                "End with **Conclusion And Suggestions** containing only summary and recommendations, without repeating proof details."
            )
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
        prompt_tokens = self._estimate_tokens(prompt)
        if prompt_tokens > self.max_input_tokens:
            raise RuntimeError(
                f"LLM input exceeds model budget ({prompt_tokens} > {self.max_input_tokens} estimated tokens)."
            )
        
        # Call LLM
        models_to_try = [self.model] + (self.fallback_models or [])
        last_err = None
        for m in models_to_try:
            try:
                content = self._complete_chat(m, prompt, label=f"评估{part_label}")
                print(f"[Multi-Stage] Part {part_name} response received ({len(content)} chars)")
                result = self._parse_llm_response_with_retry(content, prompt, m)
                result["_part_name"] = part_name  # Mark which part this result came from
                return result
            except Exception as e:
                last_err = str(e)
                print(f"[Multi-Stage] Error evaluating part {part_name}: {e}")
                continue
        
        raise RuntimeError(f"LLM part evaluation failed for {part_name}: {last_err}")
    
    def _merge_partial_evaluations(self, partial_results: List[Dict[str, Any]], username: str, checker_raw_analysis: Optional[str] = None) -> Dict[str, Any]:
        """Merge multiple partial evaluation results into final scores using weighted average."""
        if not partial_results:
            raise RuntimeError("LLM evaluation failed: no partial results to merge")
        
        is_chinese = self.language == "zh-CN"
        
        # Weight different parts differently (checker results are more important)
        part_weights = {
            "checker_results": 2.0,  # Checker results are most important
            "commits": 1.5,           # Commits are important
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
            if part_name == "unknown":
                part_name = "commits"

            if part_name not in part_weights:
                continue
            
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
        
        final_scores["reasoning"] = self._format_structured_reasoning(
            final_scores,
            all_reasonings,
            checker_raw_analysis,
        )
        
        print(f"[Multi-Stage] Merged {len(partial_results)} partial evaluations into final scores")
        return final_scores
    
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
                previous_scores_block = f"\n\n上一个评估节点的分数（基线参考）:\n{json.dumps(prev_scores, ensure_ascii=False, indent=2)}\n注意：当前评估应该基于上一个节点的分数，除非有明确的负面证据，否则分数应该保持稳定或略有增长。"
            else:
                previous_scores_block = f"\n\nPREVIOUS CHECKPOINT SCORES (baseline reference):\n{json.dumps(prev_scores, ensure_ascii=False, indent=2)}\nNOTE: Current evaluation should build on previous scores. Maintain or gradually increase scores unless clear negative evidence exists."
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
                chunked_instruction = "\n分块评估：基于之前的评分和新证据更新分数。提供完整的推理过程，包括**主要优势**、**改进空间**、**整体评估**部分（不要重复部分）。"
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
            reasoning_example = (
                "使用评分标准。reasoning 必须包含四个维度章节："
                "**规范与内建质量**、**云原生与架构演进**、**AI工程与自动演进**、**工程修养与职业素养**。"
                "每个章节写明该维度分数、L1-L5 等级，并列出来自 commit sha、commit message 和 commit diff 的证据（文件名/路径必须来自提交差异或提交信息）。"
                "最后提供 **结论与建议**，只总结和给建议，不重复证明细节。"
            )
            format_note = "每个维度评分范围：0-100"
            json_instruction = "重要：必须只返回JSON对象，不要添加任何解释性文字、markdown格式或代码块标记。直接返回JSON，格式如下："
        else:
            reasoning_example = (
                "Use the rubric. The reasoning must contain four dimension sections: "
                "**Specification & Built-in Quality**, **Cloud-Native & Architecture Evolution**, "
                "**AI Engineering & Automated Evolution**, and **Engineering Mastery & Professionalism**. "
                "Each section must include the dimension score, L1-L5 level, and evidence from commit sha, commit message, and commit diff (file names/paths must come from commit diffs or messages). "
                "End with **Conclusion And Suggestions** containing only summary and recommendations, without repeating proof details."
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
        
        try:
            return self._parse_llm_response(content)
        except Exception as parse_error:
            error_msg = str(parse_error)
            print(f"[ERROR] Failed to parse LLM response: {error_msg}")
            
            if retry_count >= max_retries:
                print(f"[ERROR] Max retries ({max_retries}) reached")
                return self._handle_parse_retry_failure(error_msg)
            
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
                    return self._handle_parse_retry_failure(f"Retry LLM API returned error: {resp.status_code}")
                
                retry_data = resp.json()
                if "choices" not in retry_data or not retry_data["choices"]:
                    print(f"[ERROR] No choices in retry API response")
                    return self._handle_parse_retry_failure("No choices in retry API response")
                
                retry_content = retry_data["choices"][0]["message"]["content"]
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
        # Use the new reasoning which already consolidates previous + new evidence
        nr = str(new.get("reasoning", "")).strip()
        out["reasoning"] = nr if nr else str(prev.get("reasoning", "")).strip()
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
