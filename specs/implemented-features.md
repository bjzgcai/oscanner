# Oscanner Implemented Features

Last reviewed: 2026-06-04

## Product Scope

Oscanner Skill Evaluator is an AI-assisted engineering capability assessment
system. It extracts repository activity from GitHub and Gitee, evaluates
contributors with plugin-defined rubrics, serves FastAPI APIs, provides an
optional repository test runner, and exposes a Next.js dashboard.

## Runtime Components

### Evaluator API

- Location: `backend/evaluator/`
- Main app: `backend/evaluator/server.py`
- Default port: `8000`
- Framework: FastAPI
- Health and metadata:
  - `GET /health`
  - `GET /version`
  - `GET /`
- Router groups:
  - Plugins: `backend/evaluator/routes/plugins.py`
  - LLM and token config: `backend/evaluator/routes/config.py`
  - Repository authors and commits: `backend/evaluator/routes/data.py`
  - Single-repo evaluations and merge: `backend/evaluator/routes/evaluation.py`
  - Batch extraction and cross-repo comparison: `backend/evaluator/routes/batch.py`
  - Benchmark validation: `backend/evaluator/routes/benchmark.py`
  - Trajectory and course/group analysis: `backend/evaluator/routes/trajectory.py`
  - Runner proxy: `backend/evaluator/routes/runner_proxy.py`
  - External checkers: `backend/evaluator/routes/checkers.py`

Implemented behavior:

- Loads runtime environment from evaluator `.env`, legacy `.env.local`, current
  working directory env files, and user-local Oscanner config.
- Creates required XDG/user-local data directories on startup.
- Registers all API routers before optionally mounting a bundled dashboard.
- Allows CORS in development and strips trailing slashes from API requests for
  dashboard static export compatibility.
- Serves bundled Next.js dashboard assets from the installed CLI package when
  present.

### Repository Data Extraction

Implemented behavior:

- Supports GitHub and Gitee repository URLs through shared parsing utilities.
- Extracts commits, diffs, file context, contributors, and repository snapshots
  through provider-specific collectors and services.
- Supports cached local data and incremental sync paths.
- Uses provider tokens when configured to reduce rate-limit pressure.
- Preserves branch/ref-aware data directories for batch and course workflows.
- Enforces a 10M-token repository evaluator guardrail before LLM work in the
  main incremental evaluator path, Gitee contributor path, and trajectory/group
  evaluation paths.

Primary APIs:

- `GET /api/authors/{owner}/{repo}`
- `GET /api/gitee/commits/{owner}/{repo}`
- `POST /api/batch/extract`
- `POST /api/batch/common-contributors`
- `POST /api/batch/compare-contributor`

### Evaluation

Implemented behavior:

- Evaluates a contributor in one repository with a selected plugin and model.
- Supports email identity lists and alias-like request fields for more reliable
  author matching.
- Provides a Gitee-specific contributor route alongside the generic GitHub-style
  route.
- Merges multiple evaluation outputs into one aggregate result.
- Delegates plugin-specific scan behavior through the plugin registry.
- Emits plugin-defined score dimensions rather than assuming fixed dimension
  keys in comparison views.

Primary APIs:

- `POST /api/evaluate/{owner}/{repo}/{author}`
- `POST /api/gitee/evaluate/{owner}/{repo}/{contributor}`
- `POST /api/merge-evaluations`

### Trajectory and Group Analysis

Implemented behavior:

- Analyzes contributor growth over time with checkpointed commit windows.
- Supports normal, streaming, one-off, one-off streaming, and polling flows.
- Supports multi-repository and group/course-style payloads.
- Accepts aliases, email identities, branch refs, explicit SHA boundaries, and
  evidence source controls.
- Maintains compatibility output for single-repo clients.
- Retries boundary commits for GitHub and Gitee so checkpoint windows can include
  requested start/end commits.
- Persists poll events in memory for clients that cannot keep long SSE
  connections open.

Primary APIs:

- `POST /api/trajectory/analyze`
- `POST /api/trajectory/analyze_stream`
- `POST /api/trajectory/analyze_one-off`
- `POST /api/trajectory/analyze_one_off_stream`
- `POST /api/trajectory/analyze_one_off_poll`
- `GET /api/trajectory/analyze_one_off_poll/{job_id}`
- `POST /api/courses/group_analyse_code`

### Plugin System

Implemented behavior:

- Discovers plugins from `plugins/`.
- Resolves default plugin metadata and backend scan entry points.
- Allows dashboard rendering through plugin-specific React view entries.
- Ships `zgc_ai_native_2026` as the default plugin.

Default plugin:

- ID: `zgc_ai_native_2026`
- Manifest: `plugins/zgc_ai_native_2026/index.yaml`
- Backend scan: `plugins/zgc_ai_native_2026/scan/__init__.py`
- Views:
  - Single repo: `plugins/zgc_ai_native_2026/view/single_repo.tsx`
  - Multi repo comparison: `plugins/zgc_ai_native_2026/view/multi_repo_compare.tsx`
  - Trajectory checkpoint: `plugins/zgc_ai_native_2026/view/trajectory_checkpoint.tsx`
- Rubric focus:
  - Specification and built-in quality
  - Cloud-native and architecture evolution
  - AI engineering and automated evolution
  - Engineering mastery and professionalism

Primary APIs:

- `GET /api/plugins`
- `GET /api/plugins/default`

### Configuration

Implemented behavior:

- Reads and writes LLM configuration through API and CLI flows.
- Masks secrets in responses.
- Checks platform token availability without returning raw token values.
- Supports OpenAI-compatible base URLs, explicit chat completions URLs, fallback
  models, GitHub tokens, and Gitee tokens.

Primary APIs:

- `GET /api/config/llm`
- `POST /api/config/llm`
- `GET /api/llm/status`
- `POST /api/config/check-platform-tokens`

### Repository Runner

- Location: `backend/repos_runner/`
- Main app: `backend/repos_runner/server.py`
- Default port: `8001`
- Router: `backend/repos_runner/routes/runner.py`

Implemented behavior:

- Clones GitHub and Gitee repositories into user-local runtime storage.
- Supports shallow clone, ref-aware clone metadata, and repository cleanup.
- Generates repository overviews with opencode and LLM fallback paths.
- Detects and runs tests for Python, JavaScript/TypeScript, Go, Rust, Java, and
  C/C++ projects.
- Supports host, Docker, and auto executor modes.
- Streams clone/explore/test/run-all progress over Server-Sent Events.
- Provides queue status, cloned repo listing, artifact retrieval, and active
  report retrieval.
- Produces `TEST_REPORT.md` or `TEST_REPORT_{tag}.md` with code test results,
  feature acceptance, runtime evidence, screenshots when available, scoring, and
  recommendations.
- Treats LLM-suggested runtime commands as untrusted and validates them against
  the safe startup allowlist.

Primary runner APIs:

- `POST /api/runner/clone`
- `POST /api/runner/explore`
- `GET /api/runner/detect-tests`
- `POST /api/runner/run-tests`
- `POST /api/runner/run-all`
- `POST /api/runner/batch-run`
- `GET /api/runner/queue`
- `GET /api/runner/repos`
- `DELETE /api/runner/repo`
- `GET /api/runner/artifact`
- `GET /api/runner/report`

Evaluator proxy APIs:

- `POST /api/runner/run-all`
- `POST /api/runner/run-all_poll`
- `GET /api/runner/run-all_poll/{job_id}`
- passthrough proxy for other `/api/runner/{path}` requests

### External Checkers

Implemented behavior:

- Loads checker metadata from `checkers/checker_list.yaml`.
- Lists available checkers.
- Clones or resolves a checked-out repository safely before running a checker.
- Runs checker implementations such as `ccn` and returns structured results.

Primary APIs:

- `GET /api/checkers/list`
- `POST /api/checkers/run`

### Benchmark Validation

Implemented behavior:

- Serves benchmark dataset and repository metadata.
- Runs validation against benchmark repositories using the current evaluator
  function and selected plugin/model.
- Reports pinning summaries when benchmark repos specify fixed refs.

Primary APIs:

- `GET /api/benchmark/dataset`
- `GET /api/benchmark/repos`
- `POST /api/benchmark/validate`

## Dashboard

- Location: `frontend/webapp/`
- Framework: Next.js App Router, React, TypeScript, Ant Design, Tailwind/CSS
- Default dev port: `3000`

Implemented pages:

- `/`: redirects to `/trajectory`
- `/trajectory`: trajectory analysis and charts
- `/runner`: repository runner UI
- `/repos`: repository analysis
- `/validation`: benchmark validation dashboard
- `/settings`: settings UI

Implemented behavior:

- Uses API base URL helper for local split-origin development and packaged
  same-origin deployment.
- Provides app settings, user settings, locale, model, and plugin context.
- Renders plugin-specific single-repo, comparison, and trajectory checkpoint
  views through generated plugin view maps.
- Includes LLM configuration modal and API docs link.
- Supports streaming runner and trajectory interactions where endpoints expose
  SSE or polling alternatives.

## CLI

- Location: `cli/cli.py`
- Command name: `oscanner`

Implemented commands:

- `oscanner init`: interactive or non-interactive environment setup.
- `oscanner serve`: starts evaluator FastAPI on the requested host/port.
- `oscanner extract`: extracts repository data with diffs and file context.
- `oscanner dashboard`: starts the Next.js dashboard or prints instructions.
- `oscanner dev`: starts backend and dashboard together.
- `oscanner publish`: development-only package publishing helper when running
  from a repository checkout.
- `oscanner --upgrade`: upgrades the installed package in the current Python
  environment.

Implemented CLI safeguards:

- Masks secrets in prompts and output.
- Checks for `uv`, `npm`, and compatible Node.js versions where needed.
- Can terminate stale local dev processes with safe heuristics when requested.
- Injects `NEXT_PUBLIC_API_SERVER_URL` for split frontend/backend development.

## Data and Storage

Implemented behavior:

- Uses XDG/user-local storage by default.
- Supports `OSCANNER_HOME` and data-specific environment overrides.
- Stores extracted data, cloned runner repositories, and reports under
  user-local runtime directories rather than the source tree by default.
- Keeps local config commonly under `~/.local/share/oscanner/.env.local`.

## Security Boundaries

Implemented behavior:

- Centralizes repository URL parsing instead of using ad hoc parsing in core
  workflows.
- Masks secrets in configuration flows.
- Treats cloned repositories and generated reports as runtime data.
- Preserves runner path validation, sandbox selection, and safe command
  allowlists for repository execution.
- Does not use forks or stars in scoring because they are easy to manipulate and
  weak evidence for contribution quality.

## Test Coverage Surface

Implemented test areas include:

- Evaluator routes and services
- GitHub/Gitee extraction behavior
- Provider parity and boundary commit handling
- Group and trajectory analysis
- Repos runner behavior
- Checker integration
- Plugin output and dashboard rendering helpers
- Frontend TypeScript/React behavior through lint/build and component tests

Use targeted tests first, then broaden to `uv run pytest` or
`cd frontend/webapp && npm run build` for high-risk changes.
