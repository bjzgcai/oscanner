# API OpenAPI Guide

This document is the integration entry point for external systems that need to call the Oscanner evaluator and repository runner services.

## OpenAPI Specs

Canonical OpenAPI 3.1 specs are checked in here. They include stable `operationId` values, service metadata, and default local `servers` entries for client generation:

- Evaluator service: [`openapi/evaluator.openapi.json`](openapi/evaluator.openapi.json)
- Repository runner service: [`openapi/repos_runner.openapi.json`](openapi/repos_runner.openapi.json)

When the services are running, FastAPI also serves live OpenAPI and Swagger UI:

| Service | Default URL | OpenAPI JSON | Swagger UI |
| --- | --- | --- | --- |
| Evaluator | `http://localhost:8000` | `http://localhost:8000/openapi.json` | `http://localhost:8000/docs` |
| Repos runner | `http://localhost:8001` | `http://localhost:8001/openapi.json` | `http://localhost:8001/docs` |

The evaluator also proxies runner calls under `/api/runner/*` when `RUNNER_SERVICE_URL` points to the runner service, defaulting to `http://localhost:8001`.

## Authentication And Configuration

The public API does not use per-request authentication headers. Instead, configure service-side environment variables before starting the services:

- `OSCANNER_LLM_API_KEY`, `OPENAI_API_KEY`, or `OPEN_ROUTER_KEY` for LLM-backed evaluation and repo exploration.
- `GITHUB_TOKEN` for GitHub extraction and author discovery.
- `GITEE_TOKEN` or `GITEE_ENTERPRISE_TOKEN` for Gitee extraction.
- `RUNNER_SERVICE_URL` on the evaluator when using evaluator-side runner proxy endpoints.

Do not send raw secrets in API payloads unless calling the explicit local configuration endpoints.

## Common Response And Error Format

Most JSON endpoints return a `success` boolean plus endpoint-specific data. FastAPI validation and application errors use the standard FastAPI shape:

```json
{
  "detail": "Human-readable error message or validation error list"
}
```

Streaming endpoints use Server-Sent Events (`text/event-stream`). Runner streams usually send frames like:

```text
data: {"event":"progress","data":{"message":"Cloning repository..."}}

data: {"event":"status","data":{"status":"completed","results":{}}}
```

Trajectory streams use named SSE events:

```text
event: progress
data: {"message":"syncing repository data"}
```

## Evaluator Service

Base URL: `http://localhost:8000`

Primary responsibilities:

- Extract GitHub/Gitee repository activity.
- Discover authors and commit identities.
- Evaluate individual contributors with plugin-defined rubrics.
- Analyze growth trajectories and group repositories.
- Proxy repository runner jobs.
- Manage plugins, LLM config, benchmark data, and checkers.

### Health And Metadata

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Service health check. |
| `GET` | `/version` | Git commit for the deployed service. |
| `GET` | `/` | Dashboard root when bundled, otherwise API landing page. |

### Plugin And Config Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/plugins` | List installed evaluator plugins. |
| `GET` | `/api/plugins/default` | Return the default plugin ID. |
| `GET` | `/api/config/llm` | Return masked local LLM configuration. |
| `POST` | `/api/config/llm` | Update local LLM configuration. |
| `GET` | `/api/llm/status` | Check whether an LLM key is configured. |
| `POST` | `/api/config/check-platform-tokens` | Check platform token availability for requested platforms. |

### Data And Author Discovery

| Method | Path | Query | Description |
| --- | --- | --- | --- |
| `GET` | `/api/authors/{owner}/{repo}` | `platform=github|gitee` | Discover commit authors for a repository, extracting local data if needed. |
| `GET` | `/api/gitee/commits/{owner}/{repo}` | `limit`, `is_enterprise` | Fetch Gitee commits directly. |
| `POST` | `/api/batch/extract` | - | Extract 2-5 repositories from URLs. |
| `POST` | `/api/batch/common-contributors` | - | Find contributors common to multiple local repositories. |
| `POST` | `/api/batch/compare-contributor` | - | Evaluate/compare one contributor across repositories. |

Example author discovery:

```bash
curl "http://localhost:8000/api/authors/openai/codex?platform=github"
```

Example batch extraction:

```bash
curl -X POST http://localhost:8000/api/batch/extract \
  -H 'Content-Type: application/json' \
  -d '{"urls":["https://github.com/owner/repo-a","https://gitee.com/owner/repo-b"]}'
```

### Contributor Evaluation

| Method | Path | Query | Description |
| --- | --- | --- | --- |
| `POST` | `/api/evaluate/{owner}/{repo}/{author}` | `platform`, `branch`, `model`, `plugin`, `language` | Evaluate one GitHub or Gitee author from already extracted local data. Body may include `email`, `emails`, `author_emails`, or legacy `aliases`. |
| `POST` | `/api/gitee/evaluate/{owner}/{repo}/{contributor}` | `limit`, `is_enterprise`, `plugin` | Legacy Gitee-only evaluation path. |
| `POST` | `/api/merge-evaluations` | - | Merge multiple weighted evaluation results. |

Example evaluation:

```bash
curl -X POST "http://localhost:8000/api/evaluate/owner/repo/alice?platform=github&plugin=zgc_ai_native_2026&language=en-US" \
  -H 'Content-Type: application/json' \
  -d '{"emails":["alice@example.com"]}'
```

The standard evaluation response follows `EvaluationResponseSchema` in the OpenAPI spec and includes:

- `success`
- `evaluation.username`
- `evaluation.scores`
- `evaluation.commits_summary`
- `evaluation.plugin` and `evaluation.plugin_version`
- `metadata.timestamp`

### Trajectory And Course Analysis

| Method | Path | Query | Description |
| --- | --- | --- | --- |
| `POST` | `/api/trajectory/analyze` | `plugin`, `model`, `language`, `forced_checker`, `worktree_base`, `checkpoint_strategy` | Analyze growth trajectory across repositories. |
| `POST` | `/api/trajectory/analyze_stream` | Same as above | Streaming trajectory analysis. |
| `POST` | `/api/trajectory/analyze_one-off` | Above plus `start_sha`, `end_sha` | One-off trajectory-style evaluation without storing normal trajectory state. |
| `POST` | `/api/trajectory/analyze_one_off_stream` | Same as one-off | Streaming one-off analysis. |
| `POST` | `/api/trajectory/analyze_one_off_poll` | Same as one-off | Start a durable one-off analysis job. |
| `GET` | `/api/trajectory/analyze_one_off_poll/{job_id}` | `cursor` | Poll durable one-off analysis events. |
| `POST` | `/api/courses/group_analyse_code` | `plugin`, `language`, `max_fetch_workers`, `forced_checker`, `worktree_base` | Analyze a group/course payload of repositories. |

Common payload fields include `repo_url`, `repo_urls`, `repositories`, `students`, `username`, `email`, `emails`, `author_emails`, `aliases`, and `evidence_sources`. See the generated evaluator OpenAPI file for the full permissive request schemas.

### Runner Proxy Endpoints On Evaluator

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/runner/run-all` | Proxy runner clone -> explore -> test pipeline as an SSE stream. |
| `POST` | `/api/runner/run-all_poll` | Start a durable proxied runner job. |
| `GET` | `/api/runner/run-all_poll/{job_id}` | Poll durable proxied runner events. |
| `GET/POST/PUT/PATCH/DELETE` | `/api/runner/{path}` | Generic proxy to the repos_runner service. |

Use these endpoints when callers only know the evaluator base URL and the evaluator is configured with `RUNNER_SERVICE_URL`.

### Benchmark And Checker Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/benchmark/dataset` | Get benchmark dataset metadata. |
| `GET` | `/api/benchmark/repos` | List benchmark repositories with pagination and category filter. |
| `POST` | `/api/benchmark/validate` | Run benchmark validation. |
| `GET` | `/api/checkers/list` | List available code checkers. |
| `POST` | `/api/checkers/run` | Run a checker on a specific commit. |

## Repository Runner Service

Base URL: `http://localhost:8001`

Primary responsibilities:

- Clone public GitHub/Gitee repositories.
- Explore repository structure and generate `REPO_OVERVIEW.md`.
- Detect setup/test commands.
- Run tests in controlled runtime directories.
- Produce test reports and runtime evidence artifacts.

### Health And Metadata

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Service health check. |
| `GET` | `/version` | Git commit for the deployed service. |

### Clone, Explore, And Test

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| `POST` | `/api/runner/clone` | JSON `RepoCloneRequest` | Repository metadata including `clone_path`. |
| `POST` | `/api/runner/explore` | Query `clone_path`, optional `feature_requirements`, `tag` | SSE progress and final `overview_path`. |
| `GET` | `/api/runner/detect-tests` | Query `overview_path`, optional `feature_requirements` | Detected setup/test commands and validation features. |
| `POST` | `/api/runner/run-tests` | Query `clone_path`, `overview_path`, timeouts, optional requirements/rubric | SSE progress and final test results/report. |
| `POST` | `/api/runner/run-all` | JSON `RunAllRequest` | SSE clone -> explore -> test pipeline. |
| `POST` | `/api/runner/batch-run` | JSON `BatchRunRequest` | SSE batch pipeline events, max concurrency capped at 3. |

`RepoCloneRequest` fields:

```json
{
  "repo_url": "https://github.com/owner/repo",
  "sha": null,
  "tag": null,
  "branch": null,
  "clone_timeout": 300
}
```

`RunAllRequest` fields:

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

Example full runner pipeline:

```bash
curl -N -X POST http://localhost:8001/api/runner/run-all \
  -H 'Content-Type: application/json' \
  -d '{"repo_url":"https://github.com/owner/repo","setup_timeout":300,"test_timeout":600}'
```

### Runner Lifecycle And Artifacts

| Method | Path | Query | Description |
| --- | --- | --- | --- |
| `GET` | `/api/runner/queue` | - | Current in-process runner queue snapshot. |
| `GET` | `/api/runner/repos` | - | List cloned repositories and disk/report status. |
| `DELETE` | `/api/runner/repo` | `repo_name` | Delete a cloned repository and associated runtime files. |
| `GET` | `/api/runner/report` | `repo_url`, optional `tag` | Return `TEST_REPORT.md` or tag-specific report content. |
| `GET` | `/api/runner/artifact` | `path`, plus `repo_url` or `repo_name` | Serve evidence images from `TEST_ARTIFACTS_*`. |

## Keeping Specs Updated

Regenerate the checked-in specs after changing FastAPI routes, schemas, response models, service metadata, or OpenAPI tag definitions:

```bash
.venv312/bin/python scripts/export_openapi.py
```

The exporter writes both `docs/openapi/evaluator.openapi.json` and `docs/openapi/repos_runner.openapi.json`, and fails if any generated `operationId` values are duplicated. If `.venv312` is not present, use any Python 3.12 environment with the project dependencies installed.
