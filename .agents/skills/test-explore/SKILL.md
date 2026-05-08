---
name: test-explore
description: Use when evaluating test coverage, test quality, or test gaps for a component, module, service, or repository.
---

# Test Explore

Use this workflow to explore a component, plan meaningful tests, run the suite, collect coverage, and produce a scored test report.

## Workflow

### 1. Explore

Objective: understand the code structure and identify testable behavior.

Actions:
- Identify source files in the target component or module.
- Read core service files, API endpoints, utilities, and data models.
- Analyze dependencies and external integrations.
- Document main functions/classes, input and output types, validation, error handling, and external dependencies.

Output:
- Add or update a README section with architecture overview, key units to test, and critical paths needing coverage.

### 2. Plan

Objective: design a comprehensive test suite before changing code.

Test categories:
- Unit tests: happy paths, edge cases, boundaries, and error conditions for individual functions or methods.
- Integration tests: API endpoint flows, database/file-system behavior, and external-service boundaries.
- End-to-end tests: complete user workflows and multi-step scenarios.

Actions:
- Create the test file structure, such as `tests/test_<component>.py`.
- Write a test plan listing test file names, test function names, behavior validated, and expected outcomes.

Output:
- Test plan document with coverage targets.

### 3. Execute

Objective: run tests and collect metrics.

Actions:
- Install test dependencies if needed: `pip install -e ".[dev]"`.
- Run pytest with coverage:

```bash
pytest <component>/tests/ -v --cov=<component> --cov-report=term-missing --cov-report=json
```

Capture:
- Total, passed, failed, skipped, and errored tests.
- Failure details.
- Coverage percentage.
- Execution time.

Output:
- Raw test results and coverage data.

### 4. Score

Objective: calculate quality metrics and generate a report.

Scoring formula:

```text
Base Score = (Passed / Total) * 100
Coverage Bonus = Coverage% * 0.3
Critical Path Penalty = -10 per missing critical test
Final Score = min(100, Base Score + Coverage Bonus - Penalties)
```

Grade scale:
- 90-100: Excellent, production ready
- 70-89: Good, minor gaps acceptable
- 50-69: Fair, needs improvement
- 0-49: Poor, significant gaps

Quality metrics:
- Pass rate: `(Passed / Total) * 100%`
- Coverage: `Covered Lines / Total Lines * 100%`
- Critical coverage: all critical paths tested, yes or no
- Test distribution: unit versus integration versus E2E ratio

Output:
- Markdown test report saved as `TEST_REPORT.md`.
- For `repos_runner`: `repos_runner/REPOS_RUNNER_TEST_REPORT.md`.
- For analyzed repositories: `~/.local/share/oscanner/repos/{repo_name}/TEST_REPORT.md`.

## Report Format

Use this structure:

````markdown
# Test Report: <Component Name>

**Generated**: YYYY-MM-DD HH:MM:SS
**Overall Score**: XX/100 (Grade)

## Summary
- **Total Tests**: X
- **Passed**: X (XX%)
- **Failed**: X (XX%)
- **Skipped**: X (XX%)
- **Coverage**: XX%
- **Execution Time**: X.XXs

## Test Results

### Unit Tests (X/Y passed)
- PASS test_function_name_happy_path
- PASS test_function_name_edge_case
- FAIL test_function_name_error_handling (details)

### Integration Tests (X/Y passed)
- PASS test_api_endpoint_valid_input
- FAIL test_api_endpoint_invalid_input (details)

### End-to-End Tests (X/Y passed)
- PASS test_full_workflow
- SKIP test_complex_scenario (requires external service)

## Coverage Analysis

### Well-Covered (>80%)
- module1.py: 95%
- module2.py: 87%

### Needs Attention (<80%)
- module3.py: 45% (missing error handling tests)
- module4.py: 60% (missing edge case tests)

## Critical Path Coverage
- PASS Clone repository flow
- PASS API authentication
- MISSING Error recovery mechanisms
- PASS Data validation

## Recommendations

1. Priority 1: add tests for missing critical paths.
2. Priority 2: increase edge-case and integration coverage.
3. Priority 3: add performance or concurrency checks where useful.

## Failed Test Details

### test_api_endpoint_invalid_input
```text
AssertionError: Expected 400 status code, got 500
File: tests/test_api.py, Line: 45
````

## Next Steps
1. Fix failing tests.
2. Add missing critical tests.
3. Improve low-coverage modules.
4. Re-run tests and aim for 85%+ coverage.
```

## Usage Prompts

- `Use $test-explore on repos_runner.`
- `Use $test-explore on repos_runner/services/repo_service.py.`
- `Use $test-explore for a quick check of existing tests only.`

## Best Practices

- Always start with exploration; do not write tests blindly.
- Prioritize critical paths before edge cases.
- Mock external dependencies, not internal logic.
- Keep tests isolated and independent.
- Use descriptive test names and docstrings.
- Re-run after significant refactors.
- Aim for 80%+ coverage, while remembering that coverage alone does not prove correctness.
