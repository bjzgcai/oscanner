"""T/SIA 057-2026 AI Agent Engineer scan plugin.

This plugin reuses the repository-evidence scan engine from zgc_ai_native_2026
and swaps in the T/SIA-specific rubric and dimensions. It is an evidence mapper,
not a replacement for official theory exams, onsite practice, or expert review.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def _load_base_scan_module():
    scan_path = Path(__file__).resolve().parents[2] / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("oscanner_plugin_zgc_ai_native_2026_scan_base", scan_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load base scan module from {scan_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_base = _load_base_scan_module()
extract_stream_delta = _base.extract_stream_delta
extract_stream_usage = _base.extract_stream_usage
ProgressCallback = Callable[[str, Dict[str, Any]], None]


def _load_rubric_summary() -> str:
    return (Path(__file__).resolve().parents[1] / "rubric.md").read_text(encoding="utf-8").strip()


_RUBRIC_SUMMARY = _load_rubric_summary()


class TSIA057CommitEvaluator(_base.CommitEvaluatorModerate):
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
        collaboration_evidence: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        super().__init__(
            api_key=api_key,
            max_input_tokens=max_input_tokens,
            data_dir=data_dir,
            model=model,
            api_base_url=api_base_url,
            chat_completions_url=chat_completions_url,
            fallback_models=fallback_models,
            rubric_text=rubric_text or _RUBRIC_SUMMARY,
            language=language,
            previous_checkpoint_scores=previous_checkpoint_scores,
            forced_checker_id=forced_checker_id,
            worktree_base=worktree_base,
            expected_feature=expected_feature,
            collaboration_evidence=collaboration_evidence,
            progress_callback=progress_callback,
        )
        self.dimensions = {'p1_scenario_requirements': 'P1 Scenario & Business Requirements Analysis', 'p2_agent_system_architecture': 'P2 Agent System Architecture', 'd1_llm_application': 'D1 Large Model Application', 'd2_data_knowledge_engineering': 'D2 Data & Knowledge Engineering', 'd3_software_engineering': 'D3 Software Engineering Foundation', 'd4_agent_orchestration': 'D4 Agent Orchestration', 'd5_multi_agent_integration': 'D5 Multi-Agent Collaboration & System Integration', 'o1_deployment_operations': 'O1 Agent Deployment & Operations', 'o2_agentops_optimization': 'O2 AgentOps Operation & Optimization', 'm1_security_compliance': 'M1 Security & Compliance Governance', 'm2_project_management': 'M2 Project Management', 'm3_transformation_change': 'M3 Change & Transformation'}
        self.dimension_instructions = {'p1_scenario_requirements': 'Evidence: requirements docs, user/role/process analysis, expected_feature alignment, acceptance criteria, ROI/value/risk notes.', 'p2_agent_system_architecture': 'Evidence: architecture docs/ADR, AI infra, model selection, RAG/context/Skills/plugin planning, observability and cost trade-offs.', 'd1_llm_application': 'Evidence: LLM API use, prompt templates, parameters, context handling, model A/B tests, CoT/ReAct, fallback/retry and routing.', 'd2_data_knowledge_engineering': 'Evidence: data ingestion/cleaning/labeling, embeddings/vector DB, RAG, knowledge base maintenance, data governance and privacy controls.', 'd3_software_engineering': 'Evidence: typed code, tests, lint/format, Git hygiene, CI/CD, Docker, modularity, schema validation, refactors and quality gates.', 'd4_agent_orchestration': 'Evidence: workflow/task decomposition, tool/API nodes, Skills modules, state/variable management, branching/loops, exception handling and production patterns.', 'd5_multi_agent_integration': 'Evidence: multi-agent protocols, A2A/MCP use, task dispatch, result aggregation, enterprise/external API integration and interface governance.', 'o1_deployment_operations': 'Evidence: deployment configs, environment/version management, logs, monitoring, alerts, performance/cost controls, SLA and AgentOps platform work.', 'o2_agentops_optimization': 'Evidence: bad-case analysis, feedback collection, golden datasets, automated evals, RAG/prompt/fine-tune iteration, A/B testing and ROI metrics.', 'm1_security_compliance': 'Evidence: prompt-injection defenses, secrets handling, data masking, access control, output moderation, security tests, compliance/audit docs.', 'm2_project_management': 'Evidence: task planning, milestones, risk tracking, coordination docs, issue/PR hygiene, delivery notes and cross-functional collaboration.', 'm3_transformation_change': 'Evidence: enablement docs, training materials, process redesign, reusable standards, AI adoption guidance and organizational change artifacts.'}
        self.dimension_titles_zh = {'p1_scenario_requirements': 'P1 场景与业务需求分析', 'p2_agent_system_architecture': 'P2 智能体系统架构', 'd1_llm_application': 'D1 大模型应用', 'd2_data_knowledge_engineering': 'D2 数据与知识工程', 'd3_software_engineering': 'D3 软件工程基础', 'd4_agent_orchestration': 'D4 智能体编排', 'd5_multi_agent_integration': 'D5 多智能体协同与系统集成', 'o1_deployment_operations': 'O1 智能体部署与运维', 'o2_agentops_optimization': 'O2 智能体运营与调优', 'm1_security_compliance': 'M1 安全与合规治理', 'm2_project_management': 'M2 项目管理', 'm3_transformation_change': 'M3 变革与转型'}


CommitEvaluatorModerate = TSIA057CommitEvaluator


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
    collaboration_evidence: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[ProgressCallback] = None,
    max_input_tokens: Optional[int] = None,
):
    return TSIA057CommitEvaluator(
        data_dir=data_dir,
        api_key=api_key,
        model=model,
        language=language,
        previous_checkpoint_scores=previous_checkpoint_scores,
        forced_checker_id=forced_checker_id,
        worktree_base=worktree_base,
        expected_feature=expected_feature,
        collaboration_evidence=collaboration_evidence,
        progress_callback=progress_callback,
        max_input_tokens=max_input_tokens,
    )
