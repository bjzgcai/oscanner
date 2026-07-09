# Oscanner Evaluator Backend

The evaluator backend is the FastAPI service for Oscanner Skill Evaluator. It
loads GitHub/Gitee repository activity into local XDG storage, evaluates authors
or repositories with plugin-defined rubrics, exposes trajectory and validation
APIs, and can proxy the optional repository runner service.

The current backend is route/service based: `server.py` wires middleware,
routers, environment loading, and optional static dashboard serving; most
business logic lives in `routes/` and `services/`.

## What It Provides

- FastAPI API service on port `8000`
- Optional bundled static dashboard served at `/` when packaged with
  `cli/dashboard_dist/`
- GitHub and Gitee extraction into local repository data directories
- Author discovery using lightweight provider APIs when possible, then local
  extraction as fallback
- Plugin-driven evaluation with the default `zgc_ai_native_2026` rubric
- Multi-email and legacy alias aggregation for author identity matching
- Batch extraction, common contributor search, and cross-repo contributor
  comparison
- Growth trajectory APIs, including streaming and durable polling variants
- Repository-wide group analysis for course/public evaluation integrations
- Checker discovery/execution and benchmark validation endpoints
- Runner proxy endpoints for the optional repos runner service on port `8001`

## Quick Start

### Install From PyPI

```bash
pip install oscanner-skill-evaluator
oscanner init
oscanner serve
```

Open:

- API root or bundled dashboard: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

If you want the source Next.js dashboard during development:

```bash
oscanner dashboard --install
```

The dashboard dev server runs on `http://localhost:3000`.

### Run From Source

```bash
uv sync
uv run oscanner init
uv run oscanner dev --reload --install
```

Useful variants:

```bash
uv run oscanner serve --reload
uv run oscanner dashboard --install
uv run pytest
```

## CLI Commands

The Python package exposes the `oscanner` command.

```bash
oscanner init          # Create or update .env.local configuration
oscanner serve         # Start the FastAPI evaluator backend
oscanner dashboard     # Start the Next.js dashboard dev server
oscanner dev           # Start backend and dashboard together
oscanner extract       # Extract GitHub repo data to an explicit output dir
oscanner --version
oscanner -U            # Upgrade the installed package
```

Development checkouts also expose `oscanner publish`.

Common flags:

- `oscanner serve --host 0.0.0.0 --port 8000 --reload`
- `oscanner dashboard --port 3000 --install`
- `oscanner dev --backend-port 8000 --frontend-port 3000 --no-open`
- `oscanner extract https://github.com/owner/repo --out ./data --max-commits 500`

## Architecture

```text
backend/evaluator/
|-- server.py                 # FastAPI app, middleware, router wiring, dashboard mount
|-- routes/                   # HTTP endpoints
|   |-- plugins.py            # Plugin list/default
|   |-- config.py             # LLM and platform-token settings
|   |-- data.py               # Author discovery and Gitee commit fetch
|   |-- evaluation.py         # Author evaluation and merge endpoint
|   |-- batch.py              # Batch extraction/comparison
|   |-- trajectory.py         # Trajectory, one-off, group-analysis APIs
|   |-- runner_proxy.py       # Proxy to repos_runner service
|   |-- benchmark.py          # Validation dataset APIs
|   `-- checkers.py           # Checker list/run APIs
|-- services/                 # Shared business logic
|   |-- collaboration_evidence.py
|   |-- extraction_service.py
|   |-- evaluation_service.py
|   |-- merge_service.py
|   |-- plugin_service.py
|   |-- trajectory_service.py
|   `-- trajectory_poll_store.py
|-- collectors/               # GitHub and Gitee collectors
|-- analyzers/                # Commit, code, and collaboration analyzers
|-- schemas/                  # Pydantic API schemas
|-- config/                   # Env loading, token lookup, secret masking
|-- utils/                    # Repo parsing, commit helpers, data loading
|-- validation/               # Benchmark dataset and validation runner
`-- tools/                    # Extraction and migration helpers
```

Related project roots:

```text
plugins/                      # Evaluation plugins
checkers/                     # External code-quality checkers
backend/repos_runner/         # Optional runner API, proxied by /api/runner/*
frontend/webapp/              # Next.js dashboard
```

## Service Layer Reference

Routes should stay thin. The evaluator's reusable behavior is concentrated in
`services/`, with a small subset re-exported from `services/__init__.py` for
router compatibility.

| Service | Main responsibility | Called by |
| --- | --- | --- |
| `plugin_service.py` | Discover installed plugins, choose the default plugin, and validate requested plugin IDs with clear API errors. | `plugins.py`, `evaluation.py`, `batch.py`, `trajectory.py`, `benchmark.py` |
| `extraction_service.py` | Extract, incrementally sync, and refresh GitHub/Gitee repository data. GitHub uses the moderate extractor then a git fallback; Gitee uses direct API calls. It also fetches specific boundary SHAs and writes filtered `repo_files/` snapshots. | `data.py`, `batch.py`, `evaluation.py`, `trajectory_service.py`, `benchmark.py` |
| `evaluation_service.py` | Build plugin evaluators, filter author commits, enforce the 10M-character input guardrail, run author evaluations with heartbeat progress logs, merge incremental fields, and build structured commit/file evidence links. | `evaluation.py`, `trajectory_service.py`, `benchmark.py` |
| `merge_service.py` | Merge multiple identity evaluations by commit-count weights. Numeric plugin scores are averaged; reasoning is merged with the configured LLM when available, otherwise concatenated. | `evaluation.py`, `batch.py` |
| `collaboration_evidence.py` | Normalize evidence source requests and cache provider collaboration evidence such as PR discussions, review comments, approvals, issue triage, and maintainer decisions. `commit_diffs` is always included as the local default source. | `trajectory_service.py` |
| `trajectory_service.py` | Orchestrate repository sync, growth trajectory checkpoints, inclusive SHA range filtering, full-repository group analysis, checker/plugin evaluator options, evidence enrichment, and token usage summaries. | `trajectory.py` |
| `trajectory_poll_store.py` | Persist one-off trajectory poll jobs and events in SQLite so clients can resume long-running jobs with a cursor. | `trajectory.py` |

Important service details:

- `extract_github_data()` writes through
  `backend.evaluator.tools.extract_repo_data_moderate` and falls back to a
  local git clone path when API extraction fails, times out, or returns no
  commit JSON files.
- `sync_github_data_incremental()` and `sync_gitee_data_incremental()` update
  existing local data by fetching only missing latest commits, then refresh the
  filtered repository snapshot used by plugin file loading.
- `sync_github_commits_by_sha()` and `sync_gitee_commits_by_sha()` fill gaps for
  requested boundary commits, which matters for SHA-range trajectory and group
  analysis.
- `ensure_repo_evaluation_input_within_limit()` rejects oversized evaluations
  before plugin/LLM work begins. It counts commit messages plus text from the
  current `repo_files/` snapshot.
- `build_evidence_links()` emits reviewable GitHub/Gitee commit, file, and
  directory links for the commits actually sent to an evaluator.
- `analyze_growth_trajectory()` supports `checkpoint_strategy=period` for
  two-week, 10-commit-minimum checkpoint grouping and
  `checkpoint_strategy=none` for one inclusive SHA range or one full accumulated
  checkpoint.
- `analyze_group_repositories()` evaluates whole repositories, not just one
  author. It syncs repositories concurrently, refreshes snapshots at `end_sha`
  when supplied, and passes optional checker, worktree, expected-feature, and
  collaboration-evidence settings into compatible plugin factories.

## Configuration

Run `oscanner init` or configure the user dotfile directly.

Default user config path:

```text
~/.local/share/oscanner/.env.local
```

Runtime environment loading order:

1. `backend/evaluator/.env`
2. `backend/evaluator/.env.local`
3. Current working directory `.env`
4. Current working directory `.env.local`
5. User dotfile from `OSCANNER_HOME`/XDG storage
6. Default dotenv lookup

Existing non-empty process environment variables are not overwritten by loaded
files.

Important variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `OSCANNER_LLM_API_KEY` | Primary OpenAI-compatible LLM key | none |
| `OPENAI_API_KEY` | Secondary LLM key | none |
| `OPEN_ROUTER_KEY` | OpenRouter fallback key | none |
| `OSCANNER_LLM_MODEL` | Default model | `deepseek/deepseek-v4-pro` |
| `OSCANNER_LLM_BASE_URL` | OpenAI-compatible base URL | OpenRouter base URL in plugin code |
| `OPENAI_BASE_URL` | Alternate OpenAI-compatible base URL | none |
| `OSCANNER_LLM_CHAT_COMPLETIONS_URL` | Full chat completions URL override | none |
| `OSCANNER_LLM_FALLBACK_MODELS` | Comma-separated fallback model IDs | none |
| `GITHUB_TOKEN` | GitHub API token | none |
| `GITEE_TOKEN` | Gitee API token | none |
| `GITEE_ENTERPRISE_TOKEN` | Gitee enterprise token | none |
| `OSCANNER_HOME` | Base state directory | `~/.local/share/oscanner` |
| `OSCANNER_DATA_DIR` | Repository data override | `{OSCANNER_HOME}/data` |
| `OSCANNER_PLUGINS_DIR` | Plugin directory override | repo `plugins/` |
| `OSCANNER_TRAJECTORY_POLL_DB` | SQLite path for durable trajectory poll jobs | `{OSCANNER_DATA_DIR}/trajectory_poll_jobs.sqlite3` |
| `PORT` | Evaluator server port | `8000` |
| `RUNNER_SERVICE_URL` | Repos runner backend URL | `http://localhost:8001` |

LLM key lookup priority is:

```text
OSCANNER_LLM_API_KEY -> OPENAI_API_KEY -> OPEN_ROUTER_KEY
```

Secrets returned by config APIs are masked.

## Local Data Storage

Repository data is stored under:

```text
~/.local/share/oscanner/data/{platform}/{owner}/{repo}/
```

If a branch/ref namespace is supplied by supported flows, data is stored under:

```text
~/.local/share/oscanner/data/{platform}/{owner}/{repo}/refs/{safe_ref}/
```

Typical repository data:

```text
repo_info.json
repo_tree.json
commits_index.json
commits_list.json
sync_state.json
commits/
  {sha}.json
  {sha}.diff
files/
  {paths mentioned by diffs}
repo_files/
  {filtered current snapshot}
repo_files_manifest.json
collaboration_evidence.json
```

`sync_state.json` records extraction state such as last synced time, last commit
SHA, and fetched commit counts. Extraction APIs update repository data, but the
HTTP evaluation endpoint computes fresh results from local data and does not
persist evaluation-result cache files.

`collaboration_evidence.json` is written only when trajectory or group analysis
requests provider collaboration sources beyond local `commit_diffs`. The default
cache TTL is 24 hours.

Durable trajectory polling jobs are stored separately in SQLite:

```text
~/.local/share/oscanner/data/trajectory_poll_jobs.sqlite3
```

Override that path with `OSCANNER_TRAJECTORY_POLL_DB` when running multiple
isolated evaluator instances on the same machine.

## Main HTTP Flows

### Author Discovery

```text
GET /api/authors/{owner}/{repo}?platform=github
```

Current flow:

1. Disable HTTP caching for the response.
2. For GitHub, try GraphQL commit author history if `GITHUB_TOKEN` is set.
3. For Gitee, try the contributors API if `GITEE_TOKEN` is set.
4. If lightweight provider discovery fails or is unavailable, extract local
   repository data.
5. Scan local commit JSON files and merge author groups by email/name.

Response includes `author`, `email`, `commits`, and, when available,
`provider_login`, `avatar_url`, `html_url`, or `aliases`.

### Author Evaluation

```text
POST /api/evaluate/{owner}/{repo}/{author}?platform=github&plugin=zgc_ai_native_2026&model=deepseek/deepseek-v4-pro&language=en-US
```

Current flow:

1. Resolve the LLM key and plugin.
2. Parse email identities from the route identity or request body keys
   `email`, `emails`, or `author_emails`.
3. Load local repository data from the platform/ref data directory.
4. Filter commits by email or author/alias.
5. Create the plugin evaluator with `data_dir`, `api_key`, `model`, and
   `language`.
6. Evaluate up to 150 matching commits with file context enabled.
7. Return scores, reasoning, commit summary, plugin metadata, token usage when
   supplied by the plugin, and structured evidence links.

The endpoint requires local data to exist. Use `/api/authors/*`,
`/api/batch/extract`, or an extraction tool first.

Multi-email example:

```bash
curl -X POST "http://localhost:8000/api/evaluate/owner/repo/alice%40example.com?plugin=zgc_ai_native_2026" \
  -H "Content-Type: application/json" \
  -d '{"emails": ["alice@example.com", "alice@work.example"]}'
```

When more than one identity has commits, each identity is evaluated separately
and merged with commit-count weights.

### Batch Repository Work

```text
POST /api/batch/extract
POST /api/batch/common-contributors
POST /api/batch/compare-contributor
```

`/api/batch/extract` accepts 2-5 GitHub or Gitee URLs. URLs may include refs
supported by the repo parser. Existing extracted data is skipped.

`/api/batch/common-contributors` loads local commit data and groups contributors
using:

1. GitHub ID or login
2. User-provided emails or legacy aliases
3. Fuzzy first-name matching for orphaned authors
4. Exact normalized name fallback

`/api/batch/compare-contributor` evaluates one contributor across up to 10
repositories and returns per-repo numeric plugin scores plus aggregate values
for dashboard charts.

### Trajectory And Group Analysis

```text
POST /api/trajectory/analyze
POST /api/trajectory/analyze_stream
POST /api/trajectory/analyze_one-off
POST /api/trajectory/analyze_one_off_stream
POST /api/trajectory/analyze_one_off_poll
GET  /api/trajectory/analyze_one_off_poll/{job_id}
POST /api/courses/group_analyse_code
```

Trajectory requests accept `username` or `email` plus `repo_urls`; identity
aliases can be supplied with `emails`, `author_emails`, or legacy alias fields.

Supported query parameters include:

- `plugin`
- `model`
- `language`
- `forced_checker`
- `worktree_base=build|temp`
- `checkpoint_strategy=period|none`
- `start_sha` and `end_sha` for one-off commit range analysis

One-off trajectory mode can evaluate a specific inclusive SHA range. If
`username` is explicitly `null` for Gitee inputs, the backend attempts to infer
all Gitee authors from commits and evaluate with those identities.

Streaming endpoints emit server-sent events. Poll endpoints start durable jobs
stored in SQLite and return new events with a `cursor`.

`/api/courses/group_analyse_code` evaluates whole repositories rather than a
single author and supports optional `expected_feature` and evidence sources.

### Runner Proxy

The evaluator proxies `/api/runner/*` to the optional repos runner service.

Important endpoints:

```text
POST /api/runner/run-all
POST /api/runner/run-all_poll
GET  /api/runner/run-all_poll/{job_id}
```

`run-all` streams clone, exploration, and test execution progress from the
runner. The poll variant persists progress events so clients can resume after
connection drops.

### Checkers And Benchmark Validation

```text
GET  /api/checkers/list
POST /api/checkers/run
GET  /api/benchmark/dataset
GET  /api/benchmark/repos
POST /api/benchmark/validate
```

Checkers are discovered from `checkers/`. `POST /api/checkers/run` can ensure a
shallow repository clone exists for a target commit and run a checker against
changed files or an explicit file list.

Benchmark APIs expose the validation dataset and can run validation through the
same plugin evaluation path.

## Endpoint Inventory

Infrastructure:

```text
GET /health
GET /version
GET /
GET /favicon.ico
```

Plugins and config:

```text
GET  /api/plugins
GET  /api/plugins/default
GET  /api/config/llm
POST /api/config/llm
GET  /api/llm/status
POST /api/config/check-platform-tokens
```

Data and evaluation:

```text
GET  /api/authors/{owner}/{repo}
GET  /api/gitee/commits/{owner}/{repo}
POST /api/evaluate/{owner}/{repo}/{author}
POST /api/merge-evaluations
POST /api/gitee/evaluate/{owner}/{repo}/{contributor}
```

Batch:

```text
POST /api/batch/extract
POST /api/batch/common-contributors
POST /api/batch/compare-contributor
```

Trajectory and courses:

```text
POST /api/trajectory/analyze
POST /api/trajectory/analyze_stream
POST /api/courses/group_analyse_code
POST /api/trajectory/analyze_one-off
POST /api/trajectory/analyze_one_off_stream
POST /api/trajectory/analyze_one_off_poll
GET  /api/trajectory/analyze_one_off_poll/{job_id}
```

Runner, checkers, benchmark:

```text
POST /api/runner/run-all
POST /api/runner/run-all_poll
GET  /api/runner/run-all_poll/{job_id}
ANY  /api/runner/{path}
GET  /api/checkers/list
POST /api/checkers/run
GET  /api/benchmark/dataset
GET  /api/benchmark/repos
POST /api/benchmark/validate
```

## Example API Calls

```bash
curl "http://localhost:8000/health"
curl "http://localhost:8000/api/plugins"
curl "http://localhost:8000/api/llm/status"
```

Configure OpenRouter:

```bash
curl -X POST "http://localhost:8000/api/config/llm" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "openrouter",
    "openrouter_key": "sk-or-v1-your-key",
    "model": "deepseek/deepseek-v4-pro"
  }'
```

Configure an OpenAI-compatible provider:

```bash
curl -X POST "http://localhost:8000/api/config/llm" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "openai",
    "api_key": "your-key",
    "base_url": "https://api.example.com/v1",
    "model": "provider/model-id",
    "fallback_models": "provider/fallback-id"
  }'
```

Extract and evaluate:

```bash
curl -X POST "http://localhost:8000/api/batch/extract" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://github.com/owner/repo", "https://gitee.com/owner/repo2"]}'

curl "http://localhost:8000/api/authors/owner/repo?platform=github"

curl -X POST "http://localhost:8000/api/evaluate/owner/repo/alice%40example.com?platform=github&plugin=zgc_ai_native_2026"
```

Find and compare common contributors:

```bash
curl -X POST "http://localhost:8000/api/batch/common-contributors" \
  -H "Content-Type: application/json" \
  -d '{
    "repos": [
      {"platform": "github", "owner": "owner1", "repo": "repo1"},
      {"platform": "github", "owner": "owner2", "repo": "repo2"}
    ],
    "author_emails": ["alice@example.com", "alice@work.example"]
  }'

curl -X POST "http://localhost:8000/api/batch/compare-contributor" \
  -H "Content-Type: application/json" \
  -d '{
    "contributor": "alice@example.com",
    "author_emails": ["alice@example.com", "alice@work.example"],
    "repos": [
      {"platform": "github", "owner": "owner1", "repo": "repo1"},
      {"platform": "github", "owner": "owner2", "repo": "repo2"}
    ],
    "plugin": "zgc_ai_native_2026"
  }'
```

One-off trajectory range:

```bash
curl -X POST "http://localhost:8000/api/trajectory/analyze_one-off?start_sha=abc123&end_sha=def456&checkpoint_strategy=none" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice@example.com",
    "repo_urls": ["https://github.com/owner/repo"],
    "emails": ["alice@example.com"]
  }'
```

## Default Plugin: ZGC AI-Native 2026

The bundled default plugin is `zgc_ai_native_2026`. It emits four primary score
keys from 0 to 100:

- `spec_quality`: specification implementation, testing, validation, type/schema
  discipline, maintainability, and reproducibility
- `cloud_architecture`: architecture evolution, cloud-native readiness,
  deployment automation, API design, and migration patterns
- `ai_engineering`: AI workflows, agent/tool design, prompt structure,
  evaluation loops, and automation
- `mastery_professionalism`: engineering maturity, collaboration,
  documentation, handoff quality, trade-offs, security, and performance work

The plugin folds collaboration evidence into `mastery_professionalism`. It may
also add fields such as `token_usage`, checker evidence, warnings, and
structured markdown reasoning.

For large prompts, the plugin evaluates commits in token-budgeted sequential
chunks and carries previous chunk findings into later chunks. The response marks
this with:

```json
{
  "chunked": true,
  "chunks_processed": 3,
  "chunking_strategy": "sequential"
}
```

The service also rejects extremely large repository inputs before LLM evaluation
when the repository snapshot plus commit messages exceed the 10M-character
guardrail.

## Plugin Contract

Plugins live in `plugins/{plugin_id}/` unless `OSCANNER_PLUGINS_DIR` is set.
Each plugin has an `index.yaml`.

```yaml
id: zgc_ai_native_2026
name: "ZGC AI-Native 2026"
version: "0.1.0"
description: "Rubric-guided evaluation based on engineer_level.md (2026 AI-Native standard)."
default: true
scan_entry: "scan/__init__.py"
view_single_entry: "view/single_repo.tsx"
view_compare_entry: "view/multi_repo_compare.tsx"
view_trajectory_checkpoint_entry: "view/trajectory_checkpoint.tsx"
view_entry: "view/index.tsx"
```

The scan module must expose a factory compatible with:

```python
def create_commit_evaluator(
    *,
    data_dir: str,
    api_key: str,
    model: str | None = None,
    language: str = "en-US",
):
    ...
```

Evaluator methods used by the backend include:

```python
evaluate_engineer(commits=commits, username=identity, max_commits=150, load_files=True)
evaluate_repository(commits=commits, repo_label=label, max_commits=None, load_files=True)
```

Plugin UI entries are consumed by the frontend plugin view-map generator. When
changing plugin UI entries, update both `index.yaml` and the corresponding view
files, then run the frontend scripts that regenerate the view map.

## Evaluation Response Shape

Typical author evaluation response:

```json
{
  "success": true,
  "evaluation": {
    "username": "alice@example.com",
    "mode": "moderate",
    "total_commits_analyzed": 42,
    "files_loaded": 18,
    "scores": {
      "spec_quality": 72,
      "cloud_architecture": 64,
      "ai_engineering": 80,
      "mastery_professionalism": 68,
      "reasoning": "Markdown analysis..."
    },
    "commits_summary": {
      "total_additions": 1200,
      "total_deletions": 300,
      "files_changed": 27,
      "languages": ["py", "ts"]
    },
    "incremental": false,
    "last_commit_sha": "abc123...",
    "total_commits_evaluated": 42,
    "new_commits_count": 42,
    "evaluated_at": "2026-06-05T12:00:00",
    "plugin": "zgc_ai_native_2026",
    "plugin_version": "0.1.0",
    "evidence_links": []
  },
  "metadata": {
    "timestamp": "2026-06-05T12:00:00"
  }
}
```

`incremental` fields remain in the schema for compatibility. The current HTTP
route does not load a previous saved evaluation, so normal API evaluations are
fresh computations from local repository data.

## Frontend Dashboard

The Next.js dashboard lives in `frontend/webapp/` and has App Router pages for:

- `/` single repository author evaluation
- `/repos` multi-repository contributor comparison
- `/runner` repository runner UI
- `/trajectory` trajectory analysis
- `/validation` benchmark validation
- `/settings` LLM and platform-token configuration

Use the existing Ant Design and plugin view patterns. Plugin view map generation
is handled by frontend npm scripts.

For local dashboard development:

```bash
cd frontend/webapp
npm run dev
npm run lint
npm run build
```

For PyPI-style usage, the backend can serve the bundled dashboard at `/` when
static files exist in `cli/dashboard_dist/`.

## Testing

Backend:

```bash
uv run pytest
uv run pytest tests/routes -v
uv run pytest tests/evaluator -v
```

Frontend, when TypeScript or dashboard behavior changes:

```bash
cd frontend/webapp
npm run lint
npm run build
```

Prefer targeted tests first, then broaden when shared route/service behavior is
touched.

## Troubleshooting

`LLM not configured`

Set one of `OSCANNER_LLM_API_KEY`, `OPENAI_API_KEY`, or `OPEN_ROUTER_KEY`, or run
`oscanner init`.

`No local data found`

The evaluation route does not extract data itself. Call `/api/authors/*`,
`/api/batch/extract`, or an extraction CLI/tool before evaluating.

Missing GitHub/Gitee token during trajectory analysis

Trajectory endpoints require provider tokens for the platforms being analyzed.
Configure `GITHUB_TOKEN` and/or `GITEE_TOKEN` in Settings or `.env.local`.

Runner unavailable

Start the optional repos runner service on port `8001`, or set
`RUNNER_SERVICE_URL` to the active runner URL.

Repository input too large

The evaluation service rejects oversized repository inputs with HTTP 413 and the
message `the repo is too big exceeding 10M tokens!`. Reduce repository scope,
branch/ref, or snapshot size.

## Related Documentation

- Project root README: `../../README.md`
- Evaluator schemas: `schemas/README.md`
- Validation docs: `validation/README.md`
- Trajectory SHA range notes: `../../TRAJECTORY_SHA_RANGE_IMPLEMENTATION.md`
