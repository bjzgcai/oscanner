"""T/SIA 058-2026 Youth AI Innovation scan plugin.

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


class TSIA058CommitEvaluator(_base.CommitEvaluatorModerate):
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
        self.dimensions = {'cognition_ai_literacy': 'Cognition: AI Literacy & Principles', 'cognition_methods_tools': 'Cognition: Methods & Tool Understanding', 'cognition_interdisciplinary': 'Cognition: Interdisciplinary Integration', 'application_programming': 'Application: Programming Implementation', 'application_hardware_integration': 'Application: Hardware & System Integration', 'application_generative_ai': 'Application: Generative AI Collaboration', 'innovation_problem_insight': 'Innovation: Problem Insight', 'innovation_solution_prototype': 'Innovation: Solution Design & Prototype', 'innovation_presentation_value': 'Innovation: Presentation & Value', 'responsibility_human_centered': 'Responsibility: Human-Centered Benefit', 'responsibility_data_privacy': 'Responsibility: Data Privacy & IP', 'responsibility_ethics_risk': 'Responsibility: Ethics & Risk Prevention'}
        self.dimension_instructions = {'cognition_ai_literacy': 'Evidence: explanations/docs showing AI concepts, data-model-inference flow, algorithm/model task understanding and GenAI/LLM concepts.', 'cognition_methods_tools': 'Evidence: appropriate tool selection, method rationale, technical boundaries, comparisons and limitations stated in docs or code.', 'cognition_interdisciplinary': 'Evidence: domain research and integration with science, social, humanities, arts or real-world context.', 'application_programming': 'Evidence: Scratch/Python/JS/etc implementation, debugging, algorithms, data processing, tests and version-control practice.', 'application_hardware_integration': 'Evidence: sensors, actuators, embedded/edge deployment, hardware logs, control loops and safety notes; score conservatively if not a hardware project.', 'application_generative_ai': 'Evidence: prompt structure, roles/constraints/examples, workflows, agent/knowledge-base/tool use, multimodal outputs and quality evaluation.', 'innovation_problem_insight': 'Evidence: user/scenario research, pain-point definition, target planning and problem framing.', 'innovation_solution_prototype': 'Evidence: original solution design, phased goals, runnable prototype, stability evidence and iterative improvements.', 'innovation_presentation_value': 'Evidence: README/report/demo/video materials, project narrative, social value, application potential and shareable/open outputs.', 'responsibility_human_centered': 'Evidence: public-interest reasoning, human agency, sustainability, resource/energy awareness and social-impact reflection.', 'responsibility_data_privacy': 'Evidence: data-source disclosure, privacy handling, secret/account safety, copyright/IP attribution and license hygiene.', 'responsibility_ethics_risk': 'Evidence: bias/fairness checks, explainability/traceability, hallucination verification, harmful-content controls and compliance self-checks.'}
        self.dimension_titles_zh = {'cognition_ai_literacy': '认知-人工智能通识原理', 'cognition_methods_tools': '认知-方法论与工具理解', 'cognition_interdisciplinary': '认知-跨学科融合认知', 'application_programming': '应用-编程实现技能', 'application_hardware_integration': '应用-软硬件集成技能', 'application_generative_ai': '应用-生成式AI协同技能', 'innovation_problem_insight': '创新-问题洞察', 'innovation_solution_prototype': '创新-方案设计与原型实现', 'innovation_presentation_value': '创新-成果展示与价值', 'responsibility_human_centered': '责任-智能向善价值取向', 'responsibility_data_privacy': '责任-信息安全与数据隐私', 'responsibility_ethics_risk': '责任-公平伦理与风险防范'}


CommitEvaluatorModerate = TSIA058CommitEvaluator


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
    return TSIA058CommitEvaluator(
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
