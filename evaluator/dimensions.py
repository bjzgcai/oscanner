"""
Six-Dimensional Evaluation Framework

Each dimension evaluates specific aspects of engineer capabilities.
"""

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class DimensionScore:
    """Score for a single dimension"""
    name: str
    score: float  # 0-100
    strengths: List[str]
    weaknesses: List[str]
    details: Dict[str, Any]


class DimensionEvaluator:
    """Base class for dimension evaluators"""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight

    def evaluate(self, data: Dict[str, Any]) -> DimensionScore:
        """Evaluate this dimension based on collected data"""
        raise NotImplementedError


class AIModelFullStackEvaluator(DimensionEvaluator):
    """
    Dimension 1: AI Model Full-Stack & Trade-off Capability
    Focus: Research-production mutual promotion innovation, system optimization
    """

    def __init__(self):
        super().__init__("AI Model Full-Stack & Trade-off Capability")

    def evaluate(self, data: Dict[str, Any]) -> DimensionScore:
        score = 0.0
        strengths = []
        weaknesses = []
        details = {}

        # Analyze AI/ML framework usage
        ml_frameworks = data.get("ml_frameworks", [])
        if ml_frameworks:
            score += min(len(ml_frameworks) * 10, 30)
            strengths.append(f"Experience with {len(ml_frameworks)} ML frameworks")
            details["frameworks"] = ml_frameworks
        else:
            weaknesses.append("Limited ML framework experience")

        # Analyze model optimization commits
        optimization_commits = data.get("optimization_commits", 0)
        if optimization_commits > 10:
            score += 25
            strengths.append("Strong focus on model optimization")
        elif optimization_commits > 5:
            score += 15
        else:
            weaknesses.append("Limited model optimization work")

        # Analyze end-to-end ML pipelines
        pipeline_repos = data.get("ml_pipeline_repos", [])
        if pipeline_repos:
            score += 25
            strengths.append("End-to-end ML pipeline implementation")
            details["pipelines"] = pipeline_repos
        else:
            weaknesses.append("No complete ML pipeline projects")

        # Analyze model selection and trade-offs (from documentation)
        trade_off_docs = data.get("trade_off_documentation", 0)
        if trade_off_docs > 5:
            score += 20
            strengths.append("Well-documented trade-off decisions")
        else:
            weaknesses.append("Limited documentation of model trade-offs")

        return DimensionScore(
            name=self.name,
            score=min(score, 100),
            strengths=strengths,
            weaknesses=weaknesses,
            details=details
        )


class AINativeArchitectureEvaluator(DimensionEvaluator):
    """
    Dimension 2: AI Native Architecture & Communication Design
    Focus: Production-level platform, research-production mutual promotion innovation
    """

    def __init__(self):
        super().__init__("AI Native Architecture & Communication Design")

    def evaluate(self, data: Dict[str, Any]) -> DimensionScore:
        score = 0.0
        strengths = []
        weaknesses = []
        details = {}

        # Analyze API design for AI services
        api_designs = data.get("api_designs", [])
        if len(api_designs) > 5:
            score += 30
            strengths.append("Extensive AI service API design")
            details["apis"] = api_designs
        elif len(api_designs) > 0:
            score += 15
            strengths.append("Some AI service API experience")
        else:
            weaknesses.append("Limited AI service API design")

        # Analyze architecture documentation
        arch_docs = data.get("architecture_docs", 0)
        if arch_docs > 10:
            score += 25
            strengths.append("Strong architectural documentation")
        elif arch_docs > 3:
            score += 15
        else:
            weaknesses.append("Insufficient architecture documentation")

        # Analyze microservices/distributed AI systems
        distributed_systems = data.get("distributed_ai_systems", [])
        if distributed_systems:
            score += 25
            strengths.append("Distributed AI system experience")
            details["distributed_systems"] = distributed_systems
        else:
            weaknesses.append("Limited distributed system experience")

        # Analyze communication patterns (issues, PRs, docs)
        communication_quality = data.get("communication_quality_score", 0)
        score += min(communication_quality * 20, 20)
        if communication_quality > 0.7:
            strengths.append("High-quality technical communication")
        else:
            weaknesses.append("Communication could be improved")

        return DimensionScore(
            name=self.name,
            score=min(score, 100),
            strengths=strengths,
            weaknesses=weaknesses,
            details=details
        )


class CloudNativeEvaluator(DimensionEvaluator):
    """
    Dimension 3: Cloud Native & Constraint Engineering
    Focus: Production-level platform, system optimization
    """

    def __init__(self):
        super().__init__("Cloud Native & Constraint Engineering")

    def evaluate(self, data: Dict[str, Any]) -> DimensionScore:
        score = 0.0
        strengths = []
        weaknesses = []
        details = {}

        # Analyze containerization
        docker_files = data.get("dockerfile_count", 0)
        if docker_files > 5:
            score += 20
            strengths.append("Extensive containerization experience")
        elif docker_files > 0:
            score += 10
            strengths.append("Basic containerization knowledge")
        else:
            weaknesses.append("Limited containerization experience")

        # Analyze orchestration (K8s, etc.)
        orchestration_files = data.get("orchestration_configs", [])
        if orchestration_files:
            score += 25
            strengths.append("Container orchestration experience")
            details["orchestration"] = orchestration_files
        else:
            weaknesses.append("No orchestration experience visible")

        # Analyze CI/CD pipelines
        cicd_configs = data.get("cicd_configs", [])
        if len(cicd_configs) > 5:
            score += 25
            strengths.append("Advanced CI/CD pipeline implementation")
        elif len(cicd_configs) > 0:
            score += 15
            strengths.append("Basic CI/CD setup")
        else:
            weaknesses.append("No CI/CD pipeline configuration")

        # Analyze IaC (Infrastructure as Code)
        iac_files = data.get("iac_files", [])
        if iac_files:
            score += 20
            strengths.append("Infrastructure as Code practices")
            details["iac"] = iac_files
        else:
            weaknesses.append("Limited IaC implementation")

        # Analyze resource optimization
        optimization_commits = data.get("resource_optimization_commits", 0)
        if optimization_commits > 5:
            score += 10
            strengths.append("Focus on resource optimization")

        return DimensionScore(
            name=self.name,
            score=min(score, 100),
            strengths=strengths,
            weaknesses=weaknesses,
            details=details
        )


class OpenSourceCollaborationEvaluator(DimensionEvaluator):
    """
    Dimension 4: Open Source Collaboration & Requirements Translation
    Focus: Open source co-construction, research-production mutual promotion innovation
    """

    def __init__(self):
        super().__init__("Open Source Collaboration & Requirements Translation")

    def evaluate(self, data: Dict[str, Any]) -> DimensionScore:
        score = 0.0
        strengths = []
        weaknesses = []
        details = {}

        # Analyze contribution frequency
        total_contributions = data.get("total_contributions", 0)
        if total_contributions > 200:
            score += 20
            strengths.append("Highly active contributor")
        elif total_contributions > 50:
            score += 15
            strengths.append("Regular contributor")
        elif total_contributions > 10:
            score += 10
        else:
            weaknesses.append("Limited contribution activity")

        # Analyze PR quality and reviews
        pr_reviews = data.get("pr_reviews_given", 0)
        if pr_reviews > 50:
            score += 20
            strengths.append("Active code reviewer")
        elif pr_reviews > 10:
            score += 10
        else:
            weaknesses.append("Limited code review participation")

        # Analyze issue management
        issues_created = data.get("issues_created", 0)
        issues_resolved = data.get("issues_resolved", 0)
        if issues_created > 20 and issues_resolved > 10:
            score += 20
            strengths.append("Strong issue management")
        elif issues_created > 5 or issues_resolved > 5:
            score += 10
        else:
            weaknesses.append("Limited issue management activity")

        # Analyze cross-repo collaboration
        repos_contributed = data.get("repos_contributed_to", 0)
        if repos_contributed > 10:
            score += 20
            strengths.append("Wide collaboration across projects")
        elif repos_contributed > 3:
            score += 10
        else:
            weaknesses.append("Limited cross-project collaboration")

        # Analyze requirements translation (feature implementation from issues)
        feature_implementations = data.get("feature_implementations", 0)
        if feature_implementations > 10:
            score += 20
            strengths.append("Strong requirements-to-code translation")
        elif feature_implementations > 3:
            score += 10
        else:
            weaknesses.append("Limited feature implementation tracking")

        details["contribution_summary"] = {
            "total_contributions": total_contributions,
            "pr_reviews": pr_reviews,
            "issues_created": issues_created,
            "issues_resolved": issues_resolved,
            "repos_contributed": repos_contributed
        }

        return DimensionScore(
            name=self.name,
            score=min(score, 100),
            strengths=strengths,
            weaknesses=weaknesses,
            details=details
        )


class IntelligentDevelopmentEvaluator(DimensionEvaluator):
    """
    Dimension 5: Intelligent Development & Human-Machine Collaboration
    Focus: All specialties
    """

    def __init__(self):
        super().__init__("Intelligent Development & Human-Machine Collaboration")

    def evaluate(self, data: Dict[str, Any]) -> DimensionScore:
        score = 0.0
        strengths = []
        weaknesses = []
        details = {}

        # Analyze automation tools
        automation_scripts = data.get("automation_scripts", [])
        if len(automation_scripts) > 10:
            score += 25
            strengths.append("Extensive automation implementation")
        elif len(automation_scripts) > 3:
            score += 15
            strengths.append("Some automation practices")
        else:
            weaknesses.append("Limited automation tooling")

        # Analyze AI-assisted development indicators
        ai_tool_configs = data.get("ai_tool_configs", [])
        if ai_tool_configs:
            score += 20
            strengths.append("AI-assisted development practices")
            details["ai_tools"] = ai_tool_configs

        # Analyze code generation patterns
        generated_code_indicators = data.get("generated_code_score", 0)
        if generated_code_indicators > 0.3:
            score += 15
            strengths.append("Effective use of code generation")

        # Analyze testing automation
        test_automation = data.get("test_automation_score", 0)
        score += min(test_automation * 20, 20)
        if test_automation > 0.7:
            strengths.append("Strong test automation")
        else:
            weaknesses.append("Test automation could be improved")

        # Analyze tooling development
        custom_tools = data.get("custom_tools_developed", 0)
        if custom_tools > 5:
            score += 20
            strengths.append("Custom tooling development")
        elif custom_tools > 0:
            score += 10
        else:
            weaknesses.append("Limited custom tool development")

        return DimensionScore(
            name=self.name,
            score=min(score, 100),
            strengths=strengths,
            weaknesses=weaknesses,
            details=details
        )


class EngineeringLeadershipEvaluator(DimensionEvaluator):
    """
    Dimension 6: Engineering Leadership & System Trade-offs
    Focus: System optimization, production-level platform, research-production mutual promotion innovation
    """

    def __init__(self):
        super().__init__("Engineering Leadership & System Trade-offs")

    def evaluate(self, data: Dict[str, Any]) -> DimensionScore:
        score = 0.0
        strengths = []
        weaknesses = []
        details = {}

        # Analyze mentorship indicators
        mentorship_score = data.get("mentorship_score", 0)
        if mentorship_score > 0.7:
            score += 20
            strengths.append("Active mentor and reviewer")
        elif mentorship_score > 0.3:
            score += 10
        else:
            weaknesses.append("Limited mentorship activity")

        # Analyze architectural decisions
        architecture_commits = data.get("architecture_commits", 0)
        if architecture_commits > 10:
            score += 25
            strengths.append("Significant architectural contributions")
        elif architecture_commits > 3:
            score += 15
        else:
            weaknesses.append("Limited architectural decision making")

        # Analyze trade-off documentation
        trade_off_docs = data.get("trade_off_documentation", 0)
        if trade_off_docs > 5:
            score += 20
            strengths.append("Well-documented technical decisions")
        else:
            weaknesses.append("Limited decision documentation")

        # Analyze project ownership
        owned_projects = data.get("owned_projects", [])
        if len(owned_projects) > 3:
            score += 20
            strengths.append("Multiple project ownership")
            details["owned_projects"] = owned_projects
        elif len(owned_projects) > 0:
            score += 10
            strengths.append("Project ownership experience")
        else:
            weaknesses.append("No clear project ownership")

        # Analyze team collaboration
        collaboration_score = data.get("team_collaboration_score", 0)
        score += min(collaboration_score * 15, 15)
        if collaboration_score > 0.7:
            strengths.append("Strong team collaboration")
        else:
            weaknesses.append("Team collaboration could improve")

        return DimensionScore(
            name=self.name,
            score=min(score, 100),
            strengths=strengths,
            weaknesses=weaknesses,
            details=details
        )


# Factory function to get all evaluators
def get_all_evaluators() -> List[DimensionEvaluator]:
    """Get all dimension evaluators"""
    return [
        AIModelFullStackEvaluator(),
        AINativeArchitectureEvaluator(),
        CloudNativeEvaluator(),
        OpenSourceCollaborationEvaluator(),
        IntelligentDevelopmentEvaluator(),
        EngineeringLeadershipEvaluator()
    ]
