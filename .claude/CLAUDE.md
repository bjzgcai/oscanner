# CLAUDE Project

## Purpose
Engineer capability assessment system using multi-dimensional evaluation framework and automated repository testing.

## Structure
- **backend/evaluator/** - FastAPI evaluation service (port 8000, data extraction, LLM evaluation)
- **backend/repos_runner/** - FastAPI repository testing service (port 8001, clone, explore, test)
- **frontend/webapp/** - Next.js dashboard (port 3000, charts, PDF export, plugin UI)
- **frontend/pages/** - GitHub Pages static site (optional)
- **cli/** - CLI wrapper (commands: init, serve, dev, dashboard)
- **plugins/** - Plugin system (zgc_simple, zgc_ai_native_2026, _shared)
- **checkers/** - Code quality checker system (CCN, etc.)

## Core Features

### 1. Plugin System
Modular evaluation framework with two assessment standards:
- **zgc_simple** - Six-dimensional traditional software engineering evaluation
- **zgc_ai_native_2026** - Four-dimensional AI-Native 2026 rubric (L1-L5)
- Plugin discovery via `index.yaml` (scan_entry, view_entry)
- Each plugin provides: `create_commit_evaluator()` + React components

### 2. Data Pipeline
```
API Fetch → Local Cache → Plugin Evaluation → Result Cache
   ↓            ↓               ↓                 ↓
commits    commits/        LLM scores        evaluations/
from       {sha}.json      + reasoning       {author}_{plugin}.json
Platform
```
**Incremental sync:** Track last sync in `sync_state.json`, fetch only new commits, merge into `commits_index.json`

### 3. Multi-Platform Support
- GitHub + Gitee (public + enterprise)
- Auto-detect platform from URL
- Rate limits: GitHub 5000/hr with token (60 without)

### 4. Author Alias Aggregation
Multiple identities → one evaluation:
- Evaluate each alias separately (reuse caches)
- Weighted average by commit count
- LLM synthesis for unified analysis (~88% token savings)

### 5. Trajectory Analysis
Growth tracking with checkpoint strategy:
- **period** - Time-based checkpoints (default)
- **none** - Single analysis for all commits
- Git worktree for commit-specific checks
- Incremental updates with previous checkpoint comparison

### 6. Batch Operations
Multi-repo processing:
- `/api/batch/extract` - Extract multiple repos in parallel
- `/api/batch/evaluate` - Evaluate multiple repos

### 7. Repos Runner (SSE Streaming)
Unknown repository analysis:
- **Clone** - Shallow clone (depth=1)
- **Explore** - Generate `REPO_OVERVIEW.md` via Claude Sonnet 4.5 (SSE streaming)
- **Run Tests** - Auto-detect test commands, isolated `.venv`, execute tests (SSE streaming)
- **Run All** - Combined clone + explore + test pipeline
- Output: `TEST_REPORT.md` with pass/fail metrics (0-100 score)

### 8. Checker System
Code quality checkers invoked via `/checker:keyword` in commits:
- **CCN** - Cyclomatic complexity checker (threshold: 20)
- Git worktree for commit checkout
- JSON results cached per commit

### 9. Benchmark Validation
Validation framework for testing evaluation accuracy (optional module)

## Data Directory
```
~/.local/share/oscanner/
├── data/{platform}/{owner}/{repo}/
│   ├── commits_index.json           # Summary index
│   ├── commits/{sha}.json           # Individual commits + diffs
│   ├── repo_info.json              # Repository metadata
│   └── sync_state.json             # Last sync checkpoint
├── evaluations/{platform}/{owner}/{repo}/
│   └── {author}_{plugin}.json      # Cached evaluation results
├── track/
│   └── {author1,author2,...}.json  # Trajectory analysis cache
├── checkers/
│   └── {platform}/{owner}/{repo}/commits/{sha}/
│       └── {checker_id}.json       # Checker results
└── repos/
    └── {repo_name}/                # Cloned repos for testing
        ├── REPO_OVERVIEW.md
        ├── TEST_REPORT.md
        └── .venv/
```
Priority: `OSCANNER_HOME` > `XDG_DATA_HOME` > `~/.local/share`

## Development Workflow
- Develop on main branch directly
- Commit message: `fix #issue_number` to link PR to issue
- Push triggers auto-PR generation via Gitee workflow
- Clean up temporary files after task completion