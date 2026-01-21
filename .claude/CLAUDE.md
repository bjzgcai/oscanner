# CLAUDE Project

## Purpose
Engineer capability assessment system using six-dimensional evaluation framework.

## Structure
- evaluator  # FastAPI backend - evaluation engine & data collection
- webapp     # Next.js frontend - dashboard with charts & PDF export
- oscanner   # CLI package

## Core Logic

### 1. Author Alias (Multi-Identity Aggregation)
Engineers may use different names across platforms (e.g., "CarterWu", "wu-yanbiao", "吴炎标").
- Separate evaluation per alias → cached results
- Weighted merge based on commit count
- LLM synthesis for unified analysis
- **Token savings: ~88%** (cached evaluations reused)

### 2. Multi-Platform Support (GitHub/Gitee)
- Unified collector interface: GitHubCollector, GiteeCollector
- Platform-specific API handling (public + enterprise Gitee)
- Consistent data structure across platforms
- URL parsing: auto-detect platform from repo URL

### 3. Incremental Evaluation
- Tracks sync state: `sync_state.json` (last_commit_sha, last_commit_date)
- Fetches only new commits since last sync ("since" parameter)
- Atomic writes prevent data corruption
- Merges new data into `commits_index.json`
- **Cache strategy**: API response → Local data → Evaluation results

### 4. Data Directory
```
~/.local/share/oscanner/
├── data/{platform}/{owner}/{repo}/      # Extracted commits & diffs
└── evaluations/{platform}/{owner}/{repo}/{author}.json  # Cached results
```
Priority: `OSCANNER_HOME` > `XDG_DATA_HOME` > `~/.local/share`

### 5. Six Dimensions
1. AI Model Full-Stack & Trade-off
2. AI Native Architecture & Communication
3. Cloud Native Engineering
4. Open Source Collaboration
5. Intelligent Development
6. Engineering Leadership

## Development Workflow
- Develop on main branch directly
- Auto-push triggers PR generation via Gitee workflow
- Connect PR to issue: use commit message format "fix: #issue_number"
- If no issue: use normal commit message

## Cleanup
Remove temporary files (.md, scratch files) after task completion.