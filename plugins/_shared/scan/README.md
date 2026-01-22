# Scan Plugin Contract (Developer Guide)

This document defines **exactly** what a scan plugin must expose under:

- `plugins/<plugin_id>/scan/__init__.py`

The backend loads scan plugins dynamically via file path (not via Python package import),
so treat each plugin as a **self-contained module**.

## Required Exports (Must)

### 1) `create_commit_evaluator(...)`

Your `scan/__init__.py` **must** export a function:

```python
def create_commit_evaluator(
    *,
    data_dir: str,
    api_key: str,
    model: str | None = None,
    mode: str = "moderate",
):
    ...
```

- **data_dir**: absolute path to this repo's local data directory (commits, files, repo_structure, etc).
- **api_key**: OpenAI-compatible bearer token (already resolved by backend; do not print it).
- **model**: per-request override (may be None).
- **mode**: evaluation mode (currently `"moderate"` is the common default).

Return value: an **evaluator object** that provides `evaluate_engineer(...)` (next section).

## Evaluator Interface (Must)

### 2) `evaluate_engineer(commits, username, ...) -> dict`

The object returned by `create_commit_evaluator(...)` must provide:

```python
def evaluate_engineer(
    self,
    *,
    commits: list[dict],
    username: str,
    max_commits: int | None = None,
    load_files: bool = True,
    use_chunking: bool = True,
) -> dict:
    ...
```

- **commits**: list of commit objects (dict). Each commit may contain:
  - `sha` / `hash`
  - `message` (or `commit.message`)
  - `author` (or `commit.author.name`)
  - `files`: list of `{ filename, patch, ... }`
  - `stats`: `{ additions, deletions, total }`
- **username**: selected contributor name (string).

## Output Contract (Must / Should)

### Minimum required output (Must)

Return a JSON-serializable dict that contains at least:

- `scores`: a dict containing:
  - **six dimension scores** (0–100; int/float are both acceptable), keys:
    - `ai_fullstack`
    - `ai_architecture`
    - `cloud_native`
    - `open_source`
    - `intelligent_dev`
    - `leadership`
  - `reasoning`: a markdown-friendly string (recommended)

### Recommended output (Should)

To improve UX, also include:

- `total_commits_analyzed`: int
- `commits_summary`: `{ total_additions, total_deletions, files_changed, languages }`

### Backend-injected fields (Note)

The backend will attach these fields to the final response for **verifiability**:

- `plugin` / `plugin_version` / `plugin_scan_path`

Your plugin does **not** need to set them, but it may if it wants (backend will still set final values).

## Guidance (Strongly Recommended)

- Keep scan code **self-contained**: avoid importing from `evaluator/` to reduce coupling.
- Do not use “optional module import” patterns; do not use `typing.TYPE_CHECKING`.
- If LLM is not configured, either:
  - raise a clear error, or
  - (if you support fallback) return a conservative heuristic `scores`.


