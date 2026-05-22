# Benchmark Justice Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a benchmark justice-profile report that exposes separate pass/warn/fail gates for the justice checks described in the design spec.

**Architecture:** Keep existing benchmark validators unchanged and add a focused `justice.py` translation layer that maps available validation results into the six public justice checks. `ValidationRunner` will attach this profile to returned run results so API consumers can render the dashboard-style report.

**Tech Stack:** Python dataclasses, existing evaluator validation package, pytest.

---

### Task 1: Justice Profile Model And Builder

**Files:**
- Create: `backend/evaluator/validation/justice.py`
- Test: `tests/evaluator/test_benchmark_justice_profile.py`

- [x] **Step 1: Write the failing test**

Create `tests/evaluator/test_benchmark_justice_profile.py` with tests that construct existing `ValidationResult` objects and assert the justice profile has six independent checks, maps existing validator names to the correct justice IDs, marks missing future checks as `WARN`, keeps aggregate score non-authoritative, and surfaces failed cases from validator errors.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/evaluator/test_benchmark_justice_profile.py -v`

Expected: fail during import because `evaluator.validation.justice` does not exist.

- [x] **Step 3: Write minimal implementation**

Create `backend/evaluator/validation/justice.py` with:

- `JusticeCheck` dataclass.
- `JusticeProfile` dataclass.
- `build_justice_profile(validation_results)` function.
- Thresholds: `PASS >= 85`, `WARN >= 70`, `FAIL < 70`.
- Missing check behavior: `WARN` with warning text that the source validation has not run.
- Source mapping:
  - Ordering justice: `Ordering Validation Test`, `Temporal Evolution Test`
  - Cross-language justice: no source yet
  - Evidence justice: no source yet
  - Applicability justice: no source yet
  - Stability justice: `Consistency Test`
  - Calibration accuracy: `Correlation Test`, `Dimension Validation Test`

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/evaluator/test_benchmark_justice_profile.py -v`

Expected: pass.

### Task 2: Attach Justice Profile To Validation Results

**Files:**
- Modify: `backend/evaluator/validation/validation_runner.py`
- Test: `tests/evaluator/test_benchmark_justice_profile.py`

- [x] **Step 1: Write the failing test**

Extend `tests/evaluator/test_benchmark_justice_profile.py` with a test that instantiates `ValidationRunResult` with a justice profile dictionary and asserts `to_dict()` includes `justice_profile`.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/evaluator/test_benchmark_justice_profile.py -v`

Expected: fail because `ValidationRunResult` does not accept or serialize `justice_profile`.

- [x] **Step 3: Write minimal implementation**

Modify `backend/evaluator/validation/validation_runner.py` to:

- import `build_justice_profile`
- add `justice_profile: Dict[str, Any] = field(default_factory=dict)` to `ValidationRunResult`
- include `justice_profile` in `to_dict()`
- build the justice profile from `validation_results` inside `run_full_validation()`

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/evaluator/test_benchmark_justice_profile.py -v`

Expected: pass.

### Task 3: Verification

**Files:**
- Verify: `backend/evaluator/validation/justice.py`
- Verify: `backend/evaluator/validation/validation_runner.py`
- Verify: `tests/evaluator/test_benchmark_justice_profile.py`

- [x] **Step 1: Run targeted tests**

Run: `uv run pytest tests/evaluator/test_benchmark_justice_profile.py tests/routes/test_cache_contract_removed.py -v`

Expected: pass.

- [x] **Step 2: Run diff checks**

Run: `git diff --check`

Expected: no whitespace errors.

- [x] **Step 3: Commit**

Run:

```bash
git add backend/evaluator/validation/justice.py backend/evaluator/validation/validation_runner.py tests/evaluator/test_benchmark_justice_profile.py docs/superpowers/plans/2026-05-22-benchmark-justice-suite.md
git commit -m "feat: add benchmark justice profile"
```
