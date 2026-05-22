from evaluator.validation.validators import ValidationResult
from evaluator.validation.justice import build_justice_profile
from evaluator.validation.validation_runner import ValidationRunResult


def _result(name: str, score: float, errors=None, warnings=None) -> ValidationResult:
    return ValidationResult(
        test_name=name,
        passed=score >= 70,
        score=score,
        errors=errors or [],
        warnings=warnings or [],
    )


def test_justice_profile_reports_six_independent_checks():
    profile = build_justice_profile([
        _result("Ordering Validation Test", 90),
        _result("Temporal Evolution Test", 80),
        _result("Consistency Test", 95),
        _result("Correlation Test", 74),
        _result("Dimension Validation Test", 84),
    ])

    checks = {check["id"]: check for check in profile["checks"]}

    assert list(checks) == [
        "ordering_justice",
        "cross_language_justice",
        "evidence_justice",
        "applicability_justice",
        "stability_justice",
        "calibration_accuracy",
    ]
    assert checks["ordering_justice"]["status"] == "PASS"
    assert checks["ordering_justice"]["score"] == 85.0
    assert checks["stability_justice"]["status"] == "PASS"
    assert checks["calibration_accuracy"]["status"] == "WARN"
    assert checks["calibration_accuracy"]["score"] == 79.0
    assert checks["evidence_justice"]["status"] == "WARN"
    assert checks["evidence_justice"]["score"] is None
    assert checks["evidence_justice"]["warnings"] == [
        "No validation source has run for Evidence Justice."
    ]

    assert profile["aggregate"]["authoritative"] is False
    assert profile["summary"] == {"pass": 2, "warn": 4, "fail": 0}
    assert profile["overall_status"] == "Needs Attention"


def test_justice_profile_preserves_failed_case_details():
    profile = build_justice_profile([
        _result(
            "Consistency Test",
            45,
            errors=["repo-a: High variance (12.0), scores: [50, 70, 40]"],
            warnings=["repo-b: Need at least 2 runs for consistency test"],
        ),
    ])

    checks = {check["id"]: check for check in profile["checks"]}
    stability = checks["stability_justice"]

    assert stability["status"] == "FAIL"
    assert stability["failed_cases"] == [
        "repo-a: High variance (12.0), scores: [50, 70, 40]"
    ]
    assert stability["warnings"] == [
        "repo-b: Need at least 2 runs for consistency test"
    ]
    assert profile["summary"]["fail"] == 1


def test_validation_run_result_serializes_justice_profile():
    justice_profile = build_justice_profile([
        _result("Consistency Test", 95),
    ])
    result = ValidationRunResult(
        run_id="run-1",
        timestamp="2026-05-22T00:00:00",
        dataset_stats={"total": 1},
        evaluation_count=1,
        validation_results=[],
        justice_profile=justice_profile,
        overall_passed=False,
        overall_score=0,
        duration_seconds=1.25,
    )

    serialized = result.to_dict()

    assert serialized["justice_profile"] == justice_profile
    assert serialized["justice_profile"]["aggregate"]["authoritative"] is False
