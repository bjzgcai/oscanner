# CLAUDE Project

## Purpose
Engineer capability assessment system using multi-dimensional evaluation framework and automated repository testing.

## Structure
- **evaluator/** - FastAPI backend (evaluation engine, data extraction, API endpoints)
- **webapp/** - Next.js frontend (dashboard with charts, PDF export, plugin UI)
- **oscanner/** - CLI wrapper (commands: init, serve, dev, dashboard, extract)
- **repos_runner/** - Repository testing service (clone, explore, run tests)
- **plugins/** - Plugin system (zgc_simple, zgc_ai_native_2026, _shared)

## Core Logic

### 1. Plugin System
Modular evaluation framework supporting different assessment standards:
- **zgc_simple** - Six-dimensional evaluation (default)
- **zgc_ai_native_2026** - AI-Native 2026 four-dimensional rubric
- Plugin discovery via `index.yaml` (scan_entry, view_entry)
- Each plugin provides: `create_commit_evaluator()` + React components

### 2. Data Pipeline
```
API Fetch → Local Cache → Plugin Evaluation → Result Cache
   ↓            ↓               ↓                 ↓
commits    commits/        LLM scores        evaluations/
from       {sha}.json      + reasoning       {author}_{plugin}.json
GitHub
```

**Incremental sync:**
- Track last sync: `sync_state.json` (last_commit_sha, last_commit_date)
- Fetch only new commits since last checkpoint
- Merge new data into `commits_index.json`
- Weighted merge with previous evaluation by commit count

### 3. Author Alias (Multi-Identity Aggregation)
Same engineer, multiple names (e.g., "CarterWu", "wu-yanbiao", "吴炎标"):
- Evaluate each alias separately → cached results (reuse existing caches)
- Weighted average of scores by commit count
- LLM synthesis for unified analysis text
- **Token savings: ~88%** (only merge summary needed, not re-evaluation)

### 4. Multi-Platform Support
- GitHub API + Gitee API (public + enterprise)
- Unified data structure across platforms
- Auto-detect platform from repo URL
- Rate limits: GitHub 5000/hr with token (60 without), Gitee similar

### 5. Repos Runner (Automated Testing)
Independent service for unknown repository analysis:
- **Clone** - Shallow clone (depth=1) from GitHub/Gitee (standard REST response)
- **Explore** - Generate `REPO_OVERVIEW.md` via Claude Sonnet 4.5 with **Server-Sent Events (SSE)** streaming
  - Real-time progress updates: "Analyzing repository...", "Generating overview...", character count, etc.
  - Frontend receives and displays progress messages as they happen
  - Events: `{"event": "progress", "data": {"message": "..."}}` and `{"event": "status", "data": {...}}`
- **Run Tests** - Auto-detect test commands, create isolated `.venv`, execute tests via **SSE streaming**
  - Real-time test execution progress: "Running test 1/5: pytest", "Test 1 passed", etc.
  - Completion event includes full results with pass/fail metrics
- Output: `TEST_REPORT.md` with pass/fail metrics (0-100 score)
- Isolated environments per repo to prevent dependency conflicts

### 6. Data Directory
```
~/.local/share/oscanner/
├── data/{platform}/{owner}/{repo}/
│   ├── commits_index.json           # Summary index
│   ├── commits/{sha}.json           # Individual commits + diffs
│   ├── repo_info.json              # Repository metadata
│   └── sync_state.json             # Last sync checkpoint
├── evaluations/{platform}/{owner}/{repo}/
│   └── {author}_{plugin_id}.json   # Cached evaluation results
├── track/
│   └── {author1,author2,...}.json  # Trajectory tracking cache
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
- Remove temporary files (.md, scratch files) after task completion