# C/C++ and Java Language Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add C/C++ runner support, improve Java/C/C++ evaluation context, and advertise supported languages in the courses app.

**Architecture:** Extend existing static detection and generic runner discovery tables rather than adding a new runner subsystem. Extend plugin snapshot context helpers in both bundled plugins with matching language-specific root manifests and local dependency resolution.

**Tech Stack:** Python, pytest, FastAPI repo runner internals, React/Vite homepage, Markdown docs.

---

### Task 1: Runner Tests

**Files:**
- Create: `tests/repos_runner/test_language_support.py`

- [ ] Add tests for CMake, Make, Meson, and Bazel static detection.
- [ ] Add tests for C/C++ test-file discovery.
- [ ] Add tests for `ctest` and GoogleTest output parsing.
- [ ] Run: `uv run pytest tests/repos_runner/test_language_support.py -v`
- [ ] Expected: tests fail because C/C++ support is not implemented yet.

### Task 2: Runner Implementation

**Files:**
- Modify: `backend/repos_runner/services/repo_service/detection.py`
- Modify: `backend/repos_runner/services/repo_service/runner.py`
- Modify: `backend/repos_runner/services/repo_service/parsing.py`

- [ ] Add C/C++ entries to `_FRAMEWORK_MAP`.
- [ ] Add `cpp` to `_LANG_DISCOVERY`.
- [ ] Include `cpp` in unknown-language test-file fallback.
- [ ] Keep `_build_discovered_command` returning `None` for `cpp` so build-system commands remain authoritative.
- [ ] Add regex parsing for `ctest` and GoogleTest summaries.
- [ ] Run: `uv run pytest tests/repos_runner/test_language_support.py -v`
- [ ] Expected: tests pass.

### Task 3: Evaluation Context Tests

**Files:**
- Modify: `tests/evaluator/test_repo_snapshot_context.py`

- [ ] Add a simple-plugin test for C++ changed files selecting `CMakeLists.txt` and local headers.
- [ ] Add an AI-native-plugin test for Java changed files selecting `pom.xml` and imported classes.
- [ ] Run: `uv run pytest tests/evaluator/test_repo_snapshot_context.py -v`
- [ ] Expected: new tests fail before plugin context support is implemented.

### Task 4: Evaluation Context Implementation

**Files:**
- Modify: `plugins/zgc_simple/scan/__init__.py`
- Modify: `plugins/zgc_ai_native_2026/scan/__init__.py`

- [ ] Add Java and C/C++ root manifest groups.
- [ ] Add C/C++ local include candidate selection.
- [ ] Add Java import and package candidate selection.
- [ ] Wire those helpers into `_related_context_paths`.
- [ ] Run: `uv run pytest tests/evaluator/test_repo_snapshot_context.py -v`
- [ ] Expected: tests pass.

### Task 5: Courses Docs and Homepage

**Files:**
- Modify: `/home/carter/working/courses/backend/README.md`
- Modify: `/home/carter/working/courses/frontend/src/pages/HomePage.jsx`

- [ ] Add supported-language copy to the course backend README.
- [ ] Add a compact supported-language section to the homepage.
- [ ] Run frontend verification from `/home/carter/working/courses/frontend`: `npm run build`.
- [ ] Expected: build passes.

### Task 6: Final Verification

- [ ] Run: `uv run pytest tests/repos_runner/test_language_support.py tests/evaluator/test_repo_snapshot_context.py -v`
- [ ] Run courses frontend build if not already run.
- [ ] Review `git diff --stat` in both repos.
