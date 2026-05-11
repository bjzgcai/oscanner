# Docker Repo Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run repository setup, tests, and runtime evidence collection inside an isolated Docker container while preserving generated reports and report-linked artifacts.

**Architecture:** Add an execution-session abstraction in `backend/repos_runner/services/sandbox.py`. Host execution keeps the existing `run_sandboxed` behavior; Docker execution starts one disposable container with the cloned repo mounted at `/workspace`, runs setup/test/runtime commands through `docker exec`, and removes the container at the end.

**Tech Stack:** Python stdlib, pytest, Docker CLI, FastAPI repos_runner service.

---

### Task 1: Docker Execution Session

**Files:**
- Modify: `backend/repos_runner/services/sandbox.py`
- Test: `tests/repos_runner/test_docker_sandbox.py`

- [ ] Write tests that monkeypatch `subprocess.run` and assert Docker uses `docker run -d --rm`, bind-mounts the repo, sets `/workspace`, and runs commands through `docker exec`.
- [ ] Implement `DockerSandboxSession`, `HostSandboxSession`, `create_execution_session`, and executor selection helpers.
- [ ] Run: `uv run pytest tests/repos_runner/test_docker_sandbox.py -v`

### Task 2: Runner Integration

**Files:**
- Modify: `backend/repos_runner/services/repo_service/runner.py`
- Test: `tests/repos_runner/test_runner_docker_executor.py`

- [ ] Write a test that forces the Docker executor and verifies Python setup/test commands are not rewritten to host venv paths.
- [ ] Wrap setup, tests, and runtime evidence in one execution session.
- [ ] Keep `TEST_REPORT_{tag}.md`, `.test_report.json`, `test_config.json`, and runtime artifacts in the mounted clone directory.
- [ ] Run: `uv run pytest tests/repos_runner/test_runner_docker_executor.py -v`

### Task 3: Runtime Evidence In Container

**Files:**
- Modify: `backend/repos_runner/services/repo_service/runtime_evidence.py`
- Test: `tests/repos_runner/test_runtime_evidence.py`

- [ ] Extend runtime evidence to accept an execution session.
- [ ] For Docker sessions, start documented services inside the container and probe `127.0.0.1` from inside the same container.
- [ ] Skip host port baseline checks for Docker sessions.
- [ ] Run: `uv run pytest tests/repos_runner/test_runtime_evidence.py -v`

### Task 4: Preserve Report Artifacts

**Files:**
- Modify: `backend/repos_runner/services/repo_service/clone.py`
- Test: `tests/repos_runner/test_clone_preserve_reports.py`

- [ ] Add a failing test showing `TEST_ARTIFACTS_*` directories survive a fresh clone.
- [ ] Preserve directories as well as report/overview files.
- [ ] Run: `uv run pytest tests/repos_runner/test_clone_preserve_reports.py -v`

### Task 5: Focused Verification

**Files:**
- Test: `tests/repos_runner/`

- [ ] Run: `uv run pytest tests/repos_runner -v`
- [ ] Check `git status --short` and confirm only intended files changed.
