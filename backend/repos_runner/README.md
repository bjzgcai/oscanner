## Repository Runner

`backend/repos_runner` is the optional FastAPI service that clones submitted
GitHub/Gitee repositories, builds a test-focused repository overview, detects
and runs tests, gathers runtime evidence for feature requirements, and writes a
Markdown test report.

The evaluator backend proxies these APIs through `RUNNER_SERVICE_URL`
(`http://localhost:8001` by default), but the runner can also be called
directly on port `8001`.

## Current Capabilities

- Clone public GitHub and Gitee repositories, including branch, tag, and SHA
  checkouts.
- Preserve existing `REPO_OVERVIEW*.md`, `TEST_REPORT*.md`, and
  `TEST_ARTIFACTS_*` files across fresh clone attempts.
- Generate `REPO_OVERVIEW.md` or `REPO_OVERVIEW_{tag}.md` with `opencode`;
  fall back to the configured messages API when `opencode` is unavailable or
  fails.
- Detect test commands with static project-file rules first, cached
  `test_config.json` second, and LLM parsing as fallback.
- Run setup and test commands in a host sandbox or disposable Docker container.
- Support Python, Node/Jest/Vitest/Mocha, Go, Rust, C/C++, Java/Gradle/Maven,
  Ruby, PHP, .NET, Elixir, Kotlin, Swift, and generic fallback parsing.
- Score plain repositories by code test pass rate, and tagged/requirement-based
  repositories by code tests plus functional acceptance evidence.
- Stream long-running work with Server-Sent Events (SSE).
- Queue expensive jobs in process to avoid overloading the host.
- List/delete cloned repositories and serve generated reports and runtime
  artifact images.

## Run Locally

From the repository root:

```bash
uv sync
cd backend
RUNNER_PORT=8001 uv run python -m repos_runner.server
```

The service starts at `http://localhost:8001`, with OpenAPI docs at
`http://localhost:8001/docs`.

The legacy scripts in this directory also exist:

```bash
cd backend/repos_runner
./start_server.sh
./stop_server.sh
```

For normal Oscanner development, run the evaluator on port `8000` and point it
at the runner:

```bash
export RUNNER_SERVICE_URL=http://localhost:8001
uv run oscanner serve --reload
```

The dashboard runner page is available at `http://localhost:3000/runner` when
the Next.js app is running.

## Environment

The runner loads the first existing env file from:

1. `REPOS_RUNNER_ENV_FILE`
2. `backend/repos_runner/.env`
3. `backend/repos_runner/.env.local`
4. `.env`
5. `.env.local`

Then it calls `load_dotenv(override=False)` for remaining process defaults.

Common variables:

```bash
# Runner server
export RUNNER_PORT=8001
export RUNNER_PUBLIC_BASE_URL=http://localhost:8001

# Provider credentials. Secrets are optional until an LLM path is used.
export OPEN_ROUTER_KEY=sk-or-v1-...
export OPEN_ROUTER_BASE_URL=https://openrouter.ai/api
export OPEN_ROUTER_PRIMARY_MODEL=deepseek/deepseek-v4-pro
export OPEN_ROUTER_FALLBACK_MODEL=z-ai/glm-5.1
export OPEN_ROUTER_FALLBACK_MODELS=z-ai/glm-5.1

# Repository host tokens, used for authenticated clone/API access.
export GITHUB_TOKEN=...
export GITEE_TOKEN=...
export GITEE_ENTERPRISE_TOKEN=...

# LLM model selection.
export REPOS_RUNNER_LLM_MODEL=deepseek/deepseek-v4-pro
export REPOS_RUNNER_OPENCODE_MODEL=openrouter/deepseek/deepseek-v4-pro
export REPOS_RUNNER_OPENCODE_TIMEOUT=600

# Expensive-job queue.
export REPOS_RUNNER_MAX_CONCURRENT_JOBS=1
export REPOS_RUNNER_MAX_PENDING_JOBS=100

# Execution backend: auto, host, or docker.
export REPOS_RUNNER_EXECUTOR=auto
export REPOS_RUNNER_DOCKER_IMAGE=oscanner-repos-runner:py3.12-node
export REPOS_RUNNER_DOCKER_NETWORK=bridge
export REPOS_RUNNER_DOCKER_MEMORY=2g
export REPOS_RUNNER_DOCKER_CPUS=2
export REPOS_RUNNER_DOCKER_PIDS=512

# Optional README compatibility assistant for runtime startup commands.
export REPOS_RUNNER_RUNTIME_COMPAT_LLM=false
export REPOS_RUNNER_RUNTIME_COMPAT_MODEL=deepseek/deepseek-v4-pro
```

When `REPOS_RUNNER_OPENCODE_MODEL` starts with `openrouter/`, an OpenRouter key
must be available as `OPEN_ROUTER_KEY` or `OPENROUTER_API_KEY`. The opencode
environment also reads runner/evaluator `.env` files as a fallback for
`OPEN_ROUTER_KEY`.

## API Overview

All runner routes are mounted under `/api/runner`. Streaming endpoints return
SSE lines in this shape:

```text
data: {"event":"progress","data":{"message":"..."}}
data: {"event":"status","data":{"status":"completed","results":{...}}}
```

Failure events use:

```text
data: {"event":"status","data":{"status":"failed","error":"..."}}
```

### `POST /api/runner/run-all`

Runs the normal clone -> explore -> test pipeline and streams progress.

Request:

```json
{
  "repo_url": "https://github.com/owner/repo",
  "sha": null,
  "tag": null,
  "branch": null,
  "tag_message": null,
  "grading_rubric": null,
  "skip_clone": false,
  "skip_explore": false,
  "clone_timeout": 300,
  "setup_timeout": 300,
  "test_timeout": 600,
  "pipeline_timeout": 1800
}
```

Behavior:

- Clones to the normalized storage path unless `skip_clone=true`.
- Uses `tag_message` as feature requirements when supplied.
- If no `tag_message` is supplied and `tag` is set, attempts to fetch a Gitee
  tag annotation.
- If neither path yields requirements, reads README requirements from
  `README.md`, `README.en.md`, `README.txt`, or `README`, filtering TODO,
  roadmap, future, planned, incomplete, and explicitly unimplemented sections.
- Generates a tag-specific overview/report when `tag` is set.
- Returns `clone_metadata`, `overview_path`, `results`, `report_content`, and
  token usage when tracked.

`skip_clone=true` reuses the expected storage path for the requested
repo/ref. `skip_explore=true` reuses an existing `REPO_OVERVIEW*.md` only when
the expected file exists.

### `POST /api/runner/batch-run`

Runs multiple `RunAllRequest` objects concurrently and streams per-repository
events. `max_concurrency` is capped at `3`, and each individual pipeline still
passes through the global runner queue.

Request:

```json
{
  "repos": [
    {"repo_url": "https://github.com/owner/repo-a"},
    {"repo_url": "https://gitee.com/owner/repo-b", "tag": "v1"}
  ],
  "max_concurrency": 3
}
```

Events:

- `progress`: `{"repo": "<url>", "message": "..."}`
- `repo_done`: per-repo completion or failure
- `batch_done`: final `{total, succeeded, failed}` summary

### `POST /api/runner/clone`

Clones a single repository and returns metadata.

```json
{
  "repo_url": "https://github.com/owner/repo",
  "sha": null,
  "tag": null,
  "branch": null,
  "clone_timeout": 300
}
```

Response includes:

```json
{
  "repo_name": "github/owner/repo/default",
  "display_name": "repo",
  "default_branch": "main",
  "latest_commit_id": "abc123...",
  "clone_path": "/home/user/.local/share/oscanner/repos/github/owner/repo/default/source",
  "platform": "github",
  "owner": "owner",
  "branch": null
}
```

Supported URL forms include:

- `https://github.com/owner/repo`
- `https://gitee.com/owner/repo.git`
- `github.com/owner/repo`
- `git@github.com:owner/repo.git`
- `https://github.com/owner/repo/tree/branch-name`

Only `github.com` and `gitee.com` hosts are accepted. Owner and repository
segments must be simple safe path segments.

### `POST /api/runner/explore`

Streams repository exploration and writes `REPO_OVERVIEW.md` or
`REPO_OVERVIEW_{tag}.md`.

Query parameters:

- `clone_path`: cloned repository source directory.
- `feature_requirements`: optional requirements text to include in exploration.
- `tag`: optional tag name used for the output filename.

The primary path runs:

```text
opencode run --agent plan --dir <clone_path> --model <model> <prompt>
```

The fallback builds a local context from repository files and calls the
configured messages API.

### `GET /api/runner/detect-tests`

Detects setup/test commands without running them.

Query parameters:

- `overview_path`: path to `REPO_OVERVIEW*.md`.
- `feature_requirements`: optional display-only requirements; extracted into
  `validation_features` in the returned payload.

Detection order:

1. Existing `test_config.json`.
2. Static framework detection from files such as `pyproject.toml`,
   `package.json`, `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle`,
   `CMakeLists.txt`, `Gemfile`, `*.csproj`, and `mix.exs`.
3. LLM extraction from `REPO_OVERVIEW*.md`.

### `POST /api/runner/run-tests`

Streams setup, code test execution, feature coverage checks, runtime evidence,
and report generation for an already cloned/explored repository.

Required query parameters:

- `clone_path`
- `overview_path`

Optional query parameters:

- `setup_timeout`: per setup command, default `300`.
- `test_timeout`: per test command, default `600`.
- `feature_requirements` or `tag_message`: functional acceptance requirements.
- `tag`: output suffix for `TEST_REPORT_{tag}.md`.
- `grading_rubric`: rubric text; defaults to the shared AI-Native 2026 rubric.

Completion includes `results` and inline `report_content`. The internal result
contains `total`, `passed`, `failed`, `score`, `score_breakdown`, `details`,
`test_cases`, `report_path`, and, when applicable, `feature_coverage`,
`tag_message`, and `runtime_evidence`. The API strips `grading_rubric` from
streamed responses to avoid returning large rubric text.

### Lifecycle And Artifacts

- `GET /api/runner/queue`: returns `{max_concurrent, running, pending,
  max_pending}` for the in-process queue.
- `GET /api/runner/repos`: lists cloned repositories with size, overview/report
  flags, `test_config.json` flag, and tag/default report filenames.
- `DELETE /api/runner/repo?repo_name=<key>`: deletes the checkout workspace and
  returns freed disk space.
- `GET /api/runner/report?repo_url=<url>&tag=<tag>`: returns report content.
  While an active `run-all` is still producing the report, this may return
  HTTP `202` with `{"status":"testing"}`.
- `GET /api/runner/artifact?repo_url=<url>&path=<relative-image>` or
  `GET /api/runner/artifact?repo_name=<key>&path=<relative-image>`: serves
  image files under `TEST_ARTIFACTS_*`. Only `.png`, `.jpg`, `.jpeg`, `.webp`,
  and `.gif` files are allowed, and paths must stay inside the clone.

The service also exposes `GET /health` and `GET /version` outside the runner
router.

## Storage Layout

Runner state is stored below:

1. `OSCANNER_HOME`
2. `XDG_DATA_HOME/oscanner`
3. `~/.local/share/oscanner`

Repository checkouts use this structure:

```text
<oscanner-home>/repos/
└── {platform}/
    └── {owner}/
        └── {repo}/
            └── {ref}/
                └── source/
                    ├── REPO_OVERVIEW.md
                    ├── REPO_OVERVIEW_{tag}.md
                    ├── TEST_REPORT.md
                    ├── TEST_REPORT_{tag}.md
                    ├── TEST_ARTIFACTS_{tag}/
                    ├── test_config.json
                    ├── .test_report.json
                    ├── .test_report.txt
                    ├── .venv_{dependency_hash}/
                    └── ...
```

The `{ref}` segment is:

- `default` for default-branch checkouts.
- `branch-{branch}` for branch or `/tree/<branch>` checkouts.
- `tag-{tag}` for tag checkouts.
- `sha-{sha}` for SHA checkouts.

The API `repo_name` is the storage key
`{platform}/{owner}/{repo}/{ref}`.

## Pipeline Logic

### Cloning

- Parses and validates GitHub/Gitee URLs through `paths.py`.
- Injects `GITHUB_TOKEN`, `GITEE_TOKEN`, or `GITEE_ENTERPRISE_TOKEN` into HTTPS
  clone URLs when available, and masks credentials in errors.
- Retries transient clone errors up to three times.
- Uses shallow clone/fetch paths where possible:
  - SHA: shallow fetch the SHA, then checkout. If that fails, fall back to full
    clone before checkout.
  - Tag: shallow fetch `refs/tags/<tag>`, then checkout.
  - Branch: `git clone --depth 1 --single-branch --branch <branch>`.
  - Default: `git clone --depth 1 --single-branch`.

### Exploration

Exploration prompts for a compact overview with:

- project type
- test framework
- setup commands
- test commands
- optional tag/requirements section

When `opencode` fails or is missing, the fallback context builder samples local
repository files and calls the messages API. The generated overview is written
inside the clone.

### Test Detection And Command Normalization

Static detection maps known project files to setup/test commands. After that,
the runner recursively discovers test files and may replace fragile commands
with path-aware commands for Python, Node, Ruby, and PHP. Examples:

- Python: `pytest <path> --json-report --json-report-file=.test_report.json -v`
- Vitest: `npx vitest run <path> --reporter=json > .test_report.json`
- Jest: `npx jest <path> --json --outputFile=.test_report.json`

For Python projects, setup commands are augmented with discovered
`requirements*.txt` files and `pytest pytest-json-report`. Per-repository host
virtual environments are named `.venv_{dependency_hash}` and stale hash
directories are removed automatically.

Long-lived service commands such as `npm run dev`, `vite`, `uvicorn`,
`fastapi run`, `flask run`, `next dev`, and `python scripts/dev-*` are removed
from code-test execution and treated as runtime evidence instead.

### Execution Isolation

The runner uses `REPOS_RUNNER_EXECUTOR`:

- `auto`: use Docker when the CLI and daemon are available, otherwise host.
- `docker`: require Docker.
- `host`: run on the current host sandbox.

Host execution:

- macOS uses `sandbox-exec` with repo/temp write access, local-only outbound
  network, no inbound network, and remote outbound network denied.
- Linux applies resource limits without Seatbelt.
- Other platforms use best-effort subprocess timeouts.

Docker execution:

- Starts a disposable container for one repository run.
- Mounts the clone at `/workspace`.
- Runs setup, tests, and runtime evidence in the same container.
- Keeps generated reports and artifacts on the host through the bind mount.
- Uses memory, CPU, PID, network, and image settings from env variables.

### Runtime Evidence

When functional requirements are available, runtime evidence reads:

- `README.md`
- `README.en.md`
- `AGENT.md`
- `AGENTS.md`
- up to 20 Markdown files under `docs/`

It records simple documented setup context such as `cd <relative-dir>`,
`python -m venv`, virtualenv activation, `pip install -r ...`, and package
manager install commands. It only starts/checks allowlisted command families:

- `python scripts/dev-*.py`
- `python scripts/start.py start`
- `python scripts/check.py`
- `python scripts/tasks.py check`
- `uvicorn <module>:<app> --port <port>`
- `python -m uvicorn <module>:<app> --port <port>`
- `npm run dev`

For `uvicorn` and `npm run dev`, host binding is normalized to `127.0.0.1`.
Windows virtualenv activation examples are converted to Linux/Docker-compatible
activation when safe. Arbitrary README shell commands are not executed.

If `REPOS_RUNNER_RUNTIME_COMPAT_LLM=true`, an LLM may suggest missing startup
commands from docs and repository paths. Its output is untrusted: only JSON
suggestions that normalize back into the same allowlisted command families are
used.

Runtime evidence can include static inventory, environment checks, HTTP/API
checks, DOM dumps, screenshots, and command logs under
`TEST_ARTIFACTS_{tag}/runtime-evidence/`.

## Scoring And Reports

Without requirements:

```text
score = code_test_pass_rate * 100
```

With `tag_message`, README-derived requirements, or explicit
`feature_requirements`:

```text
code_score = code_test_pass_rate * 30
functionality_score = functionality_coverage_ratio * 70
score = code_score + functionality_score
```

The runner still calculates and reports `code_relevance_ratio`, but the current
weighted score does not multiply code-test points by relevance. Functional
coverage is merged from test-file feature coverage and runtime evidence.

Reports are Markdown files written as:

- `TEST_REPORT.md`
- `TEST_REPORT_{tag}.md`

They include:

- summary and grade
- code test counts and failed output snippets
- supplied or inferred functional requirements
- execution process
- feature coverage
- runtime evidence sections and artifact image links
- score breakdown
- grading rubric section

## Architecture

```text
repos_runner/
├── server.py                         # FastAPI app, env loading, CORS, health/version
├── routes/
│   └── runner.py                     # API routes, SSE streams, queue use, artifacts
├── schemas/
│   └── __init__.py                   # Pydantic request/response models
├── services/
│   ├── sandbox.py                    # Host/Docker execution sessions
│   ├── task_queue.py                 # In-process FIFO runner queue
│   └── repo_service/
│       ├── paths.py                  # URL parsing, storage keys, Gitee tag API
│       ├── clone.py                  # Clone/fetch/checkout logic
│       ├── explore.py                # opencode and messages-API overview generation
│       ├── detection.py              # Static/LLM test command detection
│       ├── runner.py                 # Setup, tests, scoring, report orchestration
│       ├── runtime_evidence.py       # README-driven runtime evidence
│       ├── coverage.py               # Feature extraction and coverage checks
│       ├── parsing.py                # Test output/report parsing
│       ├── report.py                 # TEST_REPORT*.md generation
│       ├── venv.py                   # Hash-based per-repo Python venvs
│       └── lifecycle.py              # List/delete cloned repositories
├── docker/
│   └── Dockerfile                    # Optional Docker executor image
├── grading.py                        # Shared default grading rubric loader
├── requirements.txt
├── start_server.sh
└── stop_server.sh
```

## Testing The Runner Code

Project tests for this area live in the repository-level `tests/` tree. Use the
smallest relevant target first:

```bash
uv run pytest tests/repos_runner -v
uv run pytest tests/routes -k runner -v
```

Broaden to all tests when changing shared URL parsing, sandboxing, scoring,
collector integration, or proxy behavior:

```bash
uv run pytest
```

For manual streaming checks, use `curl -N` so events are not buffered:

```bash
curl -N -X POST "http://localhost:8001/api/runner/run-all" \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/owner/repo","pipeline_timeout":1800}'
```

## Troubleshooting

### Runner Import Fails

Run the server from `backend` or set `PYTHONPATH` so `repos_runner` is importable:

```bash
cd backend
uv run python -m repos_runner.server
```

### API Key Missing

Static clone and static test detection do not need an LLM key. Exploration
fallback, LLM test detection, feature extraction, feature coverage, and optional
runtime compatibility suggestions do. Configure `OPEN_ROUTER_KEY`.

### Port Already In Use

Change the runner port:

```bash
RUNNER_PORT=8002 uv run python -m repos_runner.server
```

If repository services conflict with host ports, prefer Docker execution:

```bash
export REPOS_RUNNER_EXECUTOR=docker
cd backend
uv run python -m repos_runner.server
```

### Queue Is Full

`run-all`, `batch-run`, and `run-tests` acquire the global in-process queue.
Increase `REPOS_RUNNER_MAX_PENDING_JOBS` or run another runner process if the
queue rejects requests. Increase `REPOS_RUNNER_MAX_CONCURRENT_JOBS` only when
the machine can safely handle multiple untrusted repository executions.

### Clone Failures

- Confirm the URL is a GitHub or Gitee repository URL.
- Use a token for private or rate-limited repositories.
- Check network and disk space.
- For tag runs, confirm the tag exists. Gitee tag annotation lookup is
  best-effort and only applies to Gitee repositories.

### Timeouts

`run-all` accepts timeout fields:

- `clone_timeout`: seconds allowed per git operation, default `300`.
- `setup_timeout`: seconds allowed per setup command, default `300`.
- `test_timeout`: seconds allowed per test command, default `600`.
- `pipeline_timeout`: seconds allowed for the active clone/explore/test
  pipeline, default `1800`.
