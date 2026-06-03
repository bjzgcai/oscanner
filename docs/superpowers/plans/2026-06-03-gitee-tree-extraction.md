# Gitee Tree Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch Gitee recursive repository trees and use them to populate evaluation snapshot files when git snapshot extraction is unavailable.

**Architecture:** Add focused helpers in `backend/evaluator/services/extraction_service.py` to fetch `git/trees/{sha}?recursive=1`, save `repo_tree.json`, and write filtered blob contents to `repo_files/` plus `repo_files_manifest.json`. Call the helper after Gitee full, incremental, and boundary sync paths when the existing git snapshot helper returns false.

**Tech Stack:** Python, requests, pytest, existing Oscanner extraction service and data-loader path filters.

---

### Task 1: Full Gitee Extraction Tree Fallback

**Files:**
- Modify: `tests/gitee_api/test_extraction.py`
- Modify: `backend/evaluator/services/extraction_service.py`

- [ ] **Step 1: Write failing test** for full extraction fetching `/git/trees/{sha}` with `recursive=1` and writing `repo_files_manifest.json`.
- [ ] **Step 2: Run targeted pytest** and confirm it fails because tree extraction is missing.
- [ ] **Step 3: Add helper implementation** for tree fetch, tree entry filtering, content fetch, and manifest writing.
- [ ] **Step 4: Run targeted pytest** and confirm it passes.

### Task 2: Incremental Gitee Snapshot Fallback

**Files:**
- Modify: `tests/gitee_api/test_extraction.py`
- Modify: `backend/evaluator/services/extraction_service.py`

- [ ] **Step 1: Write failing test** for incremental sync using tree fallback when git snapshot returns false.
- [ ] **Step 2: Run targeted pytest** and confirm it fails because incremental sync does not call the tree fallback.
- [ ] **Step 3: Call the shared helper** from incremental sync and boundary sync after unsuccessful git snapshot extraction.
- [ ] **Step 4: Run Gitee extraction tests** and confirm they pass.

### Task 3: Verification

**Files:**
- Verify: `tests/gitee_api/test_extraction.py`

- [ ] **Step 1: Run targeted tests:** `uv run pytest tests/gitee_api/test_extraction.py -v`.
- [ ] **Step 2: Inspect changed files:** `git diff --stat && git diff --check`.
