"""
Validation strategies for testing evaluation system accuracy and reliability
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import statistics
import json

from .benchmark_dataset import TestRepository, SkillLevel, DimensionStrength


@dataclass
class ValidationResult:
    """Result from a validation test"""
    test_name: str
    passed: bool
    score: float  # 0-100
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
            "errors": self.errors,
            "warnings": self.warnings,
            "timestamp": self.timestamp,
        }


class BaseValidator(ABC):
    """Base class for all validators"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def validate(self, evaluation_results: Dict[str, Any]) -> ValidationResult:
        """
        Run validation test

        Args:
            evaluation_results: Dict mapping repo identifier to evaluation result

        Returns:
            ValidationResult with test outcome
        """
        pass


class ConsistencyValidator(BaseValidator):
    """
    Tests consistency: same repo evaluated multiple times should give similar scores
    Target: variance < 5 points across 3 runs
    """

    def __init__(self, variance_threshold: float = 5.0):
        super().__init__("Consistency Test")
        self.variance_threshold = variance_threshold

    async def validate(self, evaluation_results: Dict[str, Any]) -> ValidationResult:
        """
        Expects evaluation_results to contain multiple runs per repo:
        {
            "repo_id": {
                "runs": [
                    {"overall_score": 85, "dimensions": {...}},
                    {"overall_score": 87, "dimensions": {...}},
                    {"overall_score": 84, "dimensions": {...}},
                ]
            }
        }
        """
        errors = []
        warnings = []
        details = {}
        passed_count = 0
        total_count = 0

        for repo_id, result_data in evaluation_results.items():
            runs = result_data.get("runs", [])
            if len(runs) < 2:
                warnings.append(f"{repo_id}: Need at least 2 runs for consistency test")
                continue

            scores = [run.get("overall_score", 0) for run in runs]
            variance = statistics.variance(scores) if len(scores) > 1 else 0
            std_dev = statistics.stdev(scores) if len(scores) > 1 else 0
            mean_score = statistics.mean(scores)

            passed = variance < self.variance_threshold ** 2  # variance threshold

            details[repo_id] = {
                "scores": scores,
                "mean": round(mean_score, 2),
                "variance": round(variance, 2),
                "std_dev": round(std_dev, 2),
                "passed": passed,
            }

            total_count += 1
            if passed:
                passed_count += 1
            else:
                errors.append(
                    f"{repo_id}: High variance ({std_dev:.2f}), "
                    f"scores: {[round(s, 1) for s in scores]}"
                )

        pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0
        overall_passed = pass_rate >= 90  # 90% of repos should be consistent

        return ValidationResult(
            test_name=self.name,
            passed=overall_passed,
            score=pass_rate,
            details={
                "pass_rate": round(pass_rate, 2),
                "passed_count": passed_count,
                "total_count": total_count,
                "variance_threshold": self.variance_threshold,
                "repos": details,
            },
            errors=errors,
            warnings=warnings,
        )


class CorrelationValidator(BaseValidator):
    """
    Tests correlation with expected scores/levels
    Target: correlation > 0.7 with ground truth
    """

    def __init__(self, target_correlation: float = 0.7):
        super().__init__("Correlation Test")
        self.target_correlation = target_correlation

    async def validate(self, evaluation_results: Dict[str, Any]) -> ValidationResult:
        """
        Expects evaluation_results with expected scores:
        {
            "repo_id": {
                "actual_score": 85,
                "expected_range": (80, 90),
                "skill_level": "expert"
            }
        }
        """
        errors = []
        warnings = []
        details = {}

        # Collect data points
        actual_scores = []
        expected_midpoints = []
        within_range_count = 0
        total_with_expectations = 0

        for repo_id, result_data in evaluation_results.items():
            actual = result_data.get("actual_score")
            expected_range = result_data.get("expected_range")

            if actual is None:
                warnings.append(f"{repo_id}: No actual score")
                continue

            if expected_range and len(expected_range) == 2:
                expected_min, expected_max = expected_range
                expected_mid = (expected_min + expected_max) / 2

                actual_scores.append(actual)
                expected_midpoints.append(expected_mid)

                within_range = expected_min <= actual <= expected_max
                total_with_expectations += 1
                if within_range:
                    within_range_count += 1

                details[repo_id] = {
                    "actual": round(actual, 2),
                    "expected_range": expected_range,
                    "expected_mid": round(expected_mid, 2),
                    "within_range": within_range,
                    "deviation": round(actual - expected_mid, 2),
                }

                if not within_range:
                    errors.append(
                        f"{repo_id}: Score {actual:.1f} outside expected range "
                        f"[{expected_min}, {expected_max}]"
                    )

        # Calculate correlation
        correlation = 0.0
        if len(actual_scores) >= 2:
            try:
                correlation = self._pearson_correlation(actual_scores, expected_midpoints)
            except Exception as e:
                warnings.append(f"Could not calculate correlation: {e}")

        within_range_pct = (
            (within_range_count / total_with_expectations * 100)
            if total_with_expectations > 0
            else 0
        )

        # Pass if correlation > target OR within-range > 80%
        passed = correlation >= self.target_correlation or within_range_pct >= 80

        return ValidationResult(
            test_name=self.name,
            passed=passed,
            score=max(correlation * 100, within_range_pct),
            details={
                "correlation": round(correlation, 3),
                "target_correlation": self.target_correlation,
                "within_range_count": within_range_count,
                "total_with_expectations": total_with_expectations,
                "within_range_percentage": round(within_range_pct, 2),
                "repos": details,
            },
            errors=errors,
            warnings=warnings,
        )

    def _pearson_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        sum_y2 = sum(yi ** 2 for yi in y)

        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

        if denominator == 0:
            return 0.0

        return numerator / denominator


class DimensionValidator(BaseValidator):
    """
    Tests dimension-specific expectations:
    - Repos strong in dimension X should score high in X
    - Dimension scores should vary independently
    """

    def __init__(self):
        super().__init__("Dimension Validation Test")

    async def validate(self, evaluation_results: Dict[str, Any]) -> ValidationResult:
        """
        Expects evaluation_results with dimension expectations:
        {
            "repo_id": {
                "actual_dimensions": {
                    "ai_model": 88,
                    "cloud_native": 65,
                    ...
                },
                "strong_dimensions": ["ai_model"],
                "weak_dimensions": ["cloud_native"],
                "expected_dimension_scores": {
                    "ai_model": (85, 95)
                }
            }
        }
        """
        errors = []
        warnings = []
        details = {}

        strong_match_count = 0
        strong_total = 0
        weak_match_count = 0
        weak_total = 0

        for repo_id, result_data in evaluation_results.items():
            actual_dims = result_data.get("actual_dimensions", {})
            strong_dims = result_data.get("strong_dimensions", [])
            weak_dims = result_data.get("weak_dimensions", [])
            expected_dim_scores = result_data.get("expected_dimension_scores", {})

            repo_details = {
                "actual_dimensions": actual_dims,
                "strong_checks": {},
                "weak_checks": {},
                "expected_checks": {},
            }

            # Check strong dimensions (should be > 75)
            for dim in strong_dims:
                dim_name = dim.value if hasattr(dim, 'value') else str(dim)
                score = actual_dims.get(dim_name, 0)
                passed = score >= 75

                repo_details["strong_checks"][dim_name] = {
                    "score": score,
                    "threshold": 75,
                    "passed": passed,
                }

                strong_total += 1
                if passed:
                    strong_match_count += 1
                else:
                    errors.append(
                        f"{repo_id}: Expected strong in {dim_name}, "
                        f"but scored {score:.1f} (< 75)"
                    )

            # Check weak dimensions (should be < 60)
            for dim in weak_dims:
                dim_name = dim.value if hasattr(dim, 'value') else str(dim)
                score = actual_dims.get(dim_name, 0)
                passed = score < 60

                repo_details["weak_checks"][dim_name] = {
                    "score": score,
                    "threshold": 60,
                    "passed": passed,
                }

                weak_total += 1
                if passed:
                    weak_match_count += 1
                else:
                    warnings.append(
                        f"{repo_id}: Expected weak in {dim_name}, "
                        f"but scored {score:.1f} (>= 60)"
                    )

            # Check specific expected dimension scores
            for dim_name, (expected_min, expected_max) in expected_dim_scores.items():
                score = actual_dims.get(dim_name, 0)
                within_range = expected_min <= score <= expected_max

                repo_details["expected_checks"][dim_name] = {
                    "score": score,
                    "expected_range": (expected_min, expected_max),
                    "passed": within_range,
                }

                if not within_range:
                    errors.append(
                        f"{repo_id}: {dim_name} score {score:.1f} "
                        f"outside expected [{expected_min}, {expected_max}]"
                    )

            details[repo_id] = repo_details

        # Calculate pass rates
        strong_rate = (strong_match_count / strong_total * 100) if strong_total > 0 else 100
        weak_rate = (weak_match_count / weak_total * 100) if weak_total > 0 else 100
        overall_rate = (strong_rate + weak_rate) / 2

        passed = overall_rate >= 70  # 70% of dimension expectations should match

        return ValidationResult(
            test_name=self.name,
            passed=passed,
            score=overall_rate,
            details={
                "strong_dimension_match_rate": round(strong_rate, 2),
                "weak_dimension_match_rate": round(weak_rate, 2),
                "strong_match_count": strong_match_count,
                "strong_total": strong_total,
                "weak_match_count": weak_match_count,
                "weak_total": weak_total,
                "repos": details,
            },
            errors=errors,
            warnings=warnings,
        )


class TemporalValidator(BaseValidator):
    """
    Tests temporal evolution:
    - Same developer over time should show growth
    - Later work should score higher than earlier work
    """

    def __init__(self):
        super().__init__("Temporal Evolution Test")

    async def validate(self, evaluation_results: Dict[str, Any]) -> ValidationResult:
        """
        Expects evaluation_results grouped by temporal groups:
        {
            "developer_name": {
                "timeline": [
                    {"period": "2009-2010", "score": 65, "repo_id": "..."},
                    {"period": "2020-2025", "score": 88, "repo_id": "..."},
                ]
            }
        }
        """
        errors = []
        warnings = []
        details = {}

        growth_shown_count = 0
        total_groups = 0

        for dev_name, group_data in evaluation_results.items():
            timeline = sorted(group_data.get("timeline", []), key=lambda x: x.get("period", ""))

            if len(timeline) < 2:
                warnings.append(f"{dev_name}: Need at least 2 time points")
                continue

            total_groups += 1

            # Check if scores generally increase over time
            scores = [point.get("score", 0) for point in timeline]
            periods = [point.get("period", "") for point in timeline]

            # Simple check: last score should be higher than first
            growth_delta = scores[-1] - scores[0]
            shows_growth = growth_delta > 10  # At least 10 point improvement

            if shows_growth:
                growth_shown_count += 1

            details[dev_name] = {
                "timeline": [
                    {
                        "period": periods[i],
                        "score": round(scores[i], 2),
                        "repo_id": timeline[i].get("repo_id"),
                    }
                    for i in range(len(timeline))
                ],
                "growth_delta": round(growth_delta, 2),
                "shows_growth": shows_growth,
            }

            if not shows_growth:
                errors.append(
                    f"{dev_name}: Expected growth but delta is only {growth_delta:.1f} "
                    f"(from {scores[0]:.1f} to {scores[-1]:.1f})"
                )

        growth_rate = (growth_shown_count / total_groups * 100) if total_groups > 0 else 0
        passed = growth_rate >= 80  # 80% should show growth

        return ValidationResult(
            test_name=self.name,
            passed=passed,
            score=growth_rate,
            details={
                "growth_rate": round(growth_rate, 2),
                "growth_shown_count": growth_shown_count,
                "total_groups": total_groups,
                "developers": details,
            },
            errors=errors,
            warnings=warnings,
        )


class OrderingValidator(BaseValidator):
    """
    Tests expected orderings:
    - Expert > Senior > Intermediate > Novice
    - Known pairs should have expected relative ranking
    """

    def __init__(self):
        super().__init__("Ordering Validation Test")

    async def validate(self, evaluation_results: Dict[str, Any]) -> ValidationResult:
        """
        Expects evaluation_results with skill levels:
        {
            "repo_id": {
                "score": 85,
                "skill_level": "expert"
            }
        }
        """
        errors = []
        warnings = []

        # Group by skill level
        by_level = {}
        for repo_id, result_data in evaluation_results.items():
            level = result_data.get("skill_level")
            score = result_data.get("score", 0)

            if level:
                level_name = level.value if hasattr(level, 'value') else str(level)
                if level_name not in by_level:
                    by_level[level_name] = []
                by_level[level_name].append(score)

        # Calculate average scores per level
        level_averages = {
            level: statistics.mean(scores) for level, scores in by_level.items()
        }

        # Expected ordering
        expected_order = ["expert", "architect", "senior", "intermediate", "novice"]
        actual_order = sorted(
            level_averages.keys(), key=lambda l: level_averages[l], reverse=True
        )

        # Check if ordering matches
        ordering_violations = []
        for i in range(len(expected_order) - 1):
            if expected_order[i] in level_averages and expected_order[i + 1] in level_averages:
                higher = expected_order[i]
                lower = expected_order[i + 1]

                if level_averages[higher] <= level_averages[lower]:
                    violation = (
                        f"{higher} (avg: {level_averages[higher]:.1f}) should be > "
                        f"{lower} (avg: {level_averages[lower]:.1f})"
                    )
                    ordering_violations.append(violation)
                    errors.append(violation)

        passed = len(ordering_violations) == 0

        return ValidationResult(
            test_name=self.name,
            passed=passed,
            score=100 if passed else 0,
            details={
                "level_averages": {k: round(v, 2) for k, v in level_averages.items()},
                "expected_order": expected_order,
                "actual_order": actual_order,
                "violations": ordering_violations,
            },
            errors=errors,
            warnings=warnings,
        )
