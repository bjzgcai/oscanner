---
name: test-explore
description: Systematically explore codebase, plan test suite, run tests, and generate scored test report. Use this skill when you need to understand test coverage and quality metrics for a component or module.
---

This skill provides a standardized workflow for exploring, planning, executing, and scoring tests for any codebase component.

## Workflow Steps

### 1. Explore Phase
**Objective**: Understand the codebase structure and identify testable components

**Actions**:
- Identify all source files in the target component/module
- Read core service files, API endpoints, and utilities
- Analyze dependencies and external integrations
- Document the component's:
  - Main functions and their responsibilities
  - Input/output types and validation
  - Error handling patterns
  - External dependencies (APIs, databases, file systems)

**Output**: Create or update a section in README documenting:
- Component architecture overview
- Key functions/classes to test
- Critical paths requiring coverage

### 2. Plan Phase
**Objective**: Design comprehensive test suite

**Test Categories**:
1. **Unit Tests**: Individual functions/methods
   - Happy path scenarios
   - Edge cases (empty inputs, null values, boundaries)
   - Error conditions

2. **Integration Tests**: Component interactions
   - API endpoint flows
   - Database operations
   - File system operations
   - External service mocking

3. **End-to-End Tests**: Complete user workflows
   - Full request/response cycles
   - Multi-step processes
   - Real-world scenarios

**Actions**:
- Create test file structure (e.g., `tests/test_<component>.py`)
- Write test plan document listing:
  - Test file names
  - Test function names
  - What each test validates
  - Expected outcomes

**Output**: Test plan document with estimated coverage targets

### 3. Execute Phase
**Objective**: Run tests and collect metrics

**Actions**:
- Install test dependencies if needed (`pip install -e ".[dev]"`)
- Run pytest with coverage:
  ```bash
  pytest <component>/tests/ -v --cov=<component> --cov-report=term-missing --cov-report=json
  ```
- Capture:
  - Total test count
  - Passed count
  - Failed count
  - Skipped count
  - Error details for failures
  - Coverage percentage
  - Execution time

**Output**: Raw test results and coverage data

### 4. Score Phase
**Objective**: Calculate quality metrics and generate report

**Scoring Formula**:
```
Base Score = (Passed / Total) × 100
Coverage Bonus = Coverage% × 0.3
Critical Path Penalty = -10 per missing critical test
Final Score = min(100, Base Score + Coverage Bonus - Penalties)
```

**Grade Scale**:
- 90-100: Excellent - Production ready
- 70-89: Good - Minor gaps acceptable
- 50-69: Fair - Needs improvement
- 0-49: Poor - Significant gaps

**Quality Metrics**:
- Pass Rate: `(Passed / Total) × 100%`
- Coverage: `Covered Lines / Total Lines × 100%`
- Critical Coverage: All critical paths tested (Y/N)
- Test Distribution: Unit vs Integration vs E2E ratio

**Actions**:
- Calculate all metrics
- Generate markdown report
- Identify gaps and recommend improvements

**Output**: Test report saved as `TEST_REPORT.md`

## Test Report Format

The generated report is saved as `TEST_REPORT.md` in the repository directory:
- For repos_runner service: `repos_runner/REPOS_RUNNER_TEST_REPORT.md`
- For analyzed repos: `~/.local/share/oscanner/repos/{repo_name}/TEST_REPORT.md`

The report includes:

```markdown
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
- ✅ test_function_name_happy_path
- ✅ test_function_name_edge_case
- ❌ test_function_name_error_handling (details)

### Integration Tests (X/Y passed)
- ✅ test_api_endpoint_valid_input
- ❌ test_api_endpoint_invalid_input (details)

### End-to-End Tests (X/Y passed)
- ✅ test_full_workflow
- ⏭️ test_complex_scenario (skipped - requires external service)

## Coverage Analysis

### Well-Covered (>80%)
- module1.py: 95%
- module2.py: 87%

### Needs Attention (<80%)
- module3.py: 45% (missing error handling tests)
- module4.py: 60% (missing edge case tests)

## Critical Path Coverage
- ✅ Clone repository flow
- ✅ API authentication
- ❌ Error recovery mechanisms (MISSING)
- ✅ Data validation

## Recommendations

1. **Priority 1 (Critical)**:
   - Add tests for error recovery in module3.py
   - Test timeout handling in async operations

2. **Priority 2 (Important)**:
   - Increase edge case coverage in module4.py
   - Add integration tests for cross-module workflows

3. **Priority 3 (Nice to have)**:
   - Add performance benchmarks
   - Test concurrent request handling

## Failed Test Details

### test_api_endpoint_invalid_input
```
AssertionError: Expected 400 status code, got 500
File: tests/test_api.py, Line: 45
```

## Next Steps
1. Fix X failing tests
2. Add Y missing critical tests
3. Improve coverage in Z modules
4. Re-run tests and aim for 85%+ coverage
```

## Usage Examples

### Explore entire repos_runner component
```
/test-explore repos_runner
```

### Explore specific module
```
/test-explore repos_runner/services/repo_service.py
```

### Quick check (skip plan, just run existing tests)
```
/test-explore --quick
```

## Best Practices

1. **Always start with exploration** - Don't write tests blindly
2. **Prioritize critical paths** - Core functionality first, edge cases second
3. **Use mocking wisely** - Mock external dependencies, not internal logic
4. **Keep tests isolated** - Each test should be independent
5. **Document test intent** - Use descriptive test names and docstrings
6. **Update as code changes** - Re-run after significant refactors
7. **Aim for 80%+ coverage** - But 100% coverage doesn't mean bug-free

## Integration with Development Workflow

This skill should be used:
- **Before committing major changes** - Verify nothing broke
- **Before creating PRs** - Ensure quality standards
- **During code reviews** - Provide objective metrics
- **After bug fixes** - Verify fix and add regression test
- **For new features** - Plan tests alongside implementation

## Customization

The test exploration can be customized based on:
- **Language/Framework**: Adapt for pytest, jest, go test, etc.
- **Component Type**: Services need integration tests, utilities need unit tests
- **Risk Level**: High-risk components need higher coverage
- **Complexity**: Complex logic needs more edge case tests
