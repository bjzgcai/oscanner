"""Justice-profile reporting for benchmark validation runs."""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .validators import ValidationResult


PASS_THRESHOLD = 85.0
WARN_THRESHOLD = 70.0


@dataclass(frozen=True)
class JusticeCheckDefinition:
    """Static definition for one public justice check."""

    check_id: str
    label: str
    source_tests: List[str] = field(default_factory=list)


@dataclass
class JusticeCheck:
    """Result for one justice check."""

    check_id: str
    label: str
    status: str
    score: Optional[float]
    source_tests: List[str]
    failed_cases: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.check_id,
            "label": self.label,
            "status": self.status,
            "score": self.score,
            "source_tests": self.source_tests,
            "failed_cases": self.failed_cases,
            "warnings": self.warnings,
        }


@dataclass
class JusticeProfile:
    """Dashboard-oriented benchmark justice profile."""

    checks: List[JusticeCheck]

    def to_dict(self) -> Dict[str, Any]:
        serialized_checks = [check.to_dict() for check in self.checks]
        summary = {
            "pass": sum(1 for check in self.checks if check.status == "PASS"),
            "warn": sum(1 for check in self.checks if check.status == "WARN"),
            "fail": sum(1 for check in self.checks if check.status == "FAIL"),
        }
        scored_checks = [check.score for check in self.checks if check.score is not None]
        aggregate_score = (
            round(sum(scored_checks) / len(scored_checks), 2)
            if scored_checks
            else None
        )

        return {
            "overall_status": (
                "Pass"
                if summary["warn"] == 0 and summary["fail"] == 0
                else "Needs Attention"
            ),
            "summary": summary,
            "checks": serialized_checks,
            "aggregate": {
                "score": aggregate_score,
                "authoritative": False,
                "label": "Non-authoritative trend summary",
            },
        }


CHECK_DEFINITIONS = [
    JusticeCheckDefinition(
        check_id="ordering_justice",
        label="Ordering Justice",
        source_tests=["Ordering Validation Test", "Temporal Evolution Test"],
    ),
    JusticeCheckDefinition(
        check_id="cross_language_justice",
        label="Cross-Language Justice",
    ),
    JusticeCheckDefinition(
        check_id="evidence_justice",
        label="Evidence Justice",
    ),
    JusticeCheckDefinition(
        check_id="applicability_justice",
        label="Applicability Justice",
    ),
    JusticeCheckDefinition(
        check_id="stability_justice",
        label="Stability Justice",
        source_tests=["Consistency Test"],
    ),
    JusticeCheckDefinition(
        check_id="calibration_accuracy",
        label="Calibration Accuracy",
        source_tests=["Correlation Test", "Dimension Validation Test"],
    ),
]


def build_justice_profile(validation_results: Iterable[ValidationResult]) -> Dict[str, Any]:
    """Build a public justice profile from low-level validation results."""
    results_by_name = {result.test_name: result for result in validation_results}
    checks = [
        _build_check(definition, results_by_name)
        for definition in CHECK_DEFINITIONS
    ]
    return JusticeProfile(checks=checks).to_dict()


def _build_check(
    definition: JusticeCheckDefinition,
    results_by_name: Dict[str, ValidationResult],
) -> JusticeCheck:
    source_results = [
        results_by_name[source_test]
        for source_test in definition.source_tests
        if source_test in results_by_name
    ]

    if not source_results:
        return JusticeCheck(
            check_id=definition.check_id,
            label=definition.label,
            status="WARN",
            score=None,
            source_tests=definition.source_tests,
            warnings=[f"No validation source has run for {definition.label}."],
        )

    score = round(sum(result.score for result in source_results) / len(source_results), 2)
    failed_cases = [
        error
        for result in source_results
        for error in result.errors
    ]
    warnings = [
        warning
        for result in source_results
        for warning in result.warnings
    ]

    return JusticeCheck(
        check_id=definition.check_id,
        label=definition.label,
        status=_status_for_score(score),
        score=score,
        source_tests=[result.test_name for result in source_results],
        failed_cases=failed_cases,
        warnings=warnings,
    )


def _status_for_score(score: float) -> str:
    if score >= PASS_THRESHOLD:
        return "PASS"
    if score >= WARN_THRESHOLD:
        return "WARN"
    return "FAIL"
