"""
Core evaluation engine for the Engineer Capability Assessment System
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json

from .dimensions import get_all_evaluators, DimensionScore
from .collectors.github import GitHubCollector
from .collectors.gitee import GiteeCollector
from .analyzers.code_analyzer import CodeAnalyzer
from .analyzers.commit_analyzer import CommitAnalyzer
from .analyzers.collaboration_analyzer import CollaborationAnalyzer


@dataclass
class EvaluationResult:
    """Result of engineer capability evaluation"""
    github_username: Optional[str]
    gitee_username: Optional[str]
    repos: List[str]
    dimension_scores: List[DimensionScore]
    overall_score: float
    summary: Dict[str, Any]

    def get_strengths(self) -> List[str]:
        """Get all identified strengths"""
        strengths = []
        for dim in self.dimension_scores:
            strengths.extend([f"[{dim.name}] {s}" for s in dim.strengths])
        return strengths

    def get_weaknesses(self) -> List[str]:
        """Get all identified weaknesses"""
        weaknesses = []
        for dim in self.dimension_scores:
            weaknesses.extend([f"[{dim.name}] {w}" for w in dim.weaknesses])
        return weaknesses

    def get_top_dimensions(self, n: int = 3) -> List[DimensionScore]:
        """Get top N performing dimensions"""
        return sorted(self.dimension_scores, key=lambda x: x.score, reverse=True)[:n]

    def get_bottom_dimensions(self, n: int = 3) -> List[DimensionScore]:
        """Get bottom N performing dimensions"""
        return sorted(self.dimension_scores, key=lambda x: x.score)[:n]

    def get_report(self, format: str = "text") -> str:
        """
        Generate evaluation report

        Args:
            format: "text" or "json"
        """
        if format == "json":
            return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

        # Text format
        lines = []
        lines.append("=" * 80)
        lines.append("ENGINEER CAPABILITY ASSESSMENT REPORT")
        lines.append("=" * 80)
        lines.append("")

        # User info
        if self.github_username:
            lines.append(f"GitHub: {self.github_username}")
        if self.gitee_username:
            lines.append(f"Gitee: {self.gitee_username}")
        lines.append(f"Repositories analyzed: {len(self.repos)}")
        lines.append("")

        # Overall score
        lines.append(f"Overall Score: {self.overall_score:.1f}/100")
        lines.append("")

        # Dimension scores
        lines.append("-" * 80)
        lines.append("DIMENSIONAL ANALYSIS")
        lines.append("-" * 80)
        lines.append("")

        for dim in self.dimension_scores:
            lines.append(f"## {dim.name}")
            lines.append(f"Score: {dim.score:.1f}/100")
            lines.append("")

            if dim.strengths:
                lines.append("Strengths:")
                for strength in dim.strengths:
                    lines.append(f"  ✓ {strength}")
                lines.append("")

            if dim.weaknesses:
                lines.append("Areas for Improvement:")
                for weakness in dim.weaknesses:
                    lines.append(f"  • {weakness}")
                lines.append("")

            lines.append("")

        # Summary
        lines.append("-" * 80)
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append("")

        top_dims = self.get_top_dimensions(3)
        lines.append("Top Strengths:")
        for i, dim in enumerate(top_dims, 1):
            lines.append(f"{i}. {dim.name} ({dim.score:.1f}/100)")
        lines.append("")

        bottom_dims = self.get_bottom_dimensions(3)
        lines.append("Areas to Develop:")
        for i, dim in enumerate(bottom_dims, 1):
            lines.append(f"{i}. {dim.name} ({dim.score:.1f}/100)")
        lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "github_username": self.github_username,
            "gitee_username": self.gitee_username,
            "repos": self.repos,
            "dimension_scores": [
                {
                    "name": dim.name,
                    "score": dim.score,
                    "strengths": dim.strengths,
                    "weaknesses": dim.weaknesses,
                    "details": dim.details
                }
                for dim in self.dimension_scores
            ],
            "overall_score": self.overall_score,
            "summary": self.summary
        }


class EngineerEvaluator:
    """Main evaluator class for engineer capability assessment"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize evaluator

        Args:
            config: Configuration dictionary with API tokens and settings
        """
        self.config = config or {}
        self.github_collector = GitHubCollector(self.config.get("github_token"))
        self.gitee_collector = GiteeCollector(self.config.get("gitee_token"))
        self.code_analyzer = CodeAnalyzer()
        self.commit_analyzer = CommitAnalyzer()
        self.collaboration_analyzer = CollaborationAnalyzer()
        self.evaluators = get_all_evaluators()

    def evaluate(
        self,
        github_username: Optional[str] = None,
        gitee_username: Optional[str] = None,
        repos: Optional[List[str]] = None
    ) -> EvaluationResult:
        """
        Evaluate engineer capabilities

        Args:
            github_username: GitHub username
            gitee_username: Gitee username
            repos: List of repository URLs to analyze

        Returns:
            EvaluationResult with scores and analysis
        """
        # Collect data from all sources
        data = self._collect_data(github_username, gitee_username, repos or [])

        # Run dimension evaluations
        dimension_scores = []
        for evaluator in self.evaluators:
            score = evaluator.evaluate(data)
            dimension_scores.append(score)

        # Calculate overall score (weighted average)
        overall_score = sum(dim.score for dim in dimension_scores) / len(dimension_scores)

        # Generate summary
        summary = self._generate_summary(data, dimension_scores)

        return EvaluationResult(
            github_username=github_username,
            gitee_username=gitee_username,
            repos=repos or [],
            dimension_scores=dimension_scores,
            overall_score=overall_score,
            summary=summary
        )

    def _collect_data(
        self,
        github_username: Optional[str],
        gitee_username: Optional[str],
        repos: List[str]
    ) -> Dict[str, Any]:
        """Collect data from all sources"""
        data = {
            "github_username": github_username,
            "gitee_username": gitee_username,
            "repos": repos
        }

        # Collect from GitHub
        if github_username:
            try:
                github_data = self.github_collector.collect_user_data(github_username)
                data.update(github_data)
            except Exception as e:
                print(f"Warning: Failed to collect GitHub data: {e}")

        # Collect from Gitee
        if gitee_username:
            try:
                gitee_data = self.gitee_collector.collect_user_data(gitee_username)
                # Merge gitee data with existing data
                self._merge_platform_data(data, gitee_data)
            except Exception as e:
                print(f"Warning: Failed to collect Gitee data: {e}")

        # Collect from specific repos
        for repo_url in repos:
            try:
                if "github.com" in repo_url:
                    repo_data = self.github_collector.collect_repo_data(repo_url)
                elif "gitee.com" in repo_url:
                    repo_data = self.gitee_collector.collect_repo_data(repo_url)
                else:
                    continue
                self._merge_repo_data(data, repo_data)
            except Exception as e:
                print(f"Warning: Failed to collect data from {repo_url}: {e}")

        # Run analyzers
        data = self.code_analyzer.analyze(data)
        data = self.commit_analyzer.analyze(data)
        data = self.collaboration_analyzer.analyze(data)

        return data

    def _merge_platform_data(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge data from different platforms"""
        # Aggregate numeric values
        numeric_keys = [
            "total_contributions", "pr_reviews_given", "issues_created",
            "issues_resolved", "repos_contributed_to"
        ]
        for key in numeric_keys:
            if key in source:
                target[key] = target.get(key, 0) + source[key]

        # Merge lists
        list_keys = [
            "ml_frameworks", "ml_pipeline_repos", "api_designs",
            "orchestration_configs", "cicd_configs", "iac_files",
            "automation_scripts", "ai_tool_configs", "owned_projects"
        ]
        for key in list_keys:
            if key in source:
                target[key] = list(set(target.get(key, []) + source[key]))

    def _merge_repo_data(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge data from specific repositories"""
        self._merge_platform_data(target, source)

    def _generate_summary(
        self,
        data: Dict[str, Any],
        dimension_scores: List[DimensionScore]
    ) -> Dict[str, Any]:
        """Generate evaluation summary"""
        return {
            "total_repos_analyzed": len(data.get("repos", [])),
            "data_points_collected": sum(1 for v in data.values() if v),
            "average_score": sum(dim.score for dim in dimension_scores) / len(dimension_scores),
            "score_distribution": {
                "excellent (80-100)": sum(1 for dim in dimension_scores if dim.score >= 80),
                "good (60-79)": sum(1 for dim in dimension_scores if 60 <= dim.score < 80),
                "fair (40-59)": sum(1 for dim in dimension_scores if 40 <= dim.score < 60),
                "needs_improvement (<40)": sum(1 for dim in dimension_scores if dim.score < 40)
            }
        }
