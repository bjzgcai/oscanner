# Backend Evaluator Overview

`backend/evaluator` provides the main Oscanner evaluator API. It collects
repository activity, discovers contributors, runs plugin-based LLM evaluations,
and exposes those workflows through FastAPI.

Oscanner does not own consumer-facing cache strategy. Callers that want reuse
should cache above this layer.

## Main Features

- **FastAPI service shell**: Health, version, root endpoints, CORS,
  trailing-slash handling, optional bundled dashboard serving, and router wiring
  in `server.py`.
- **Plugin management**: Discovers local evaluator plugins, returns plugin
  metadata and default plugin details, and loads plugin scan modules. See
  `routes/plugins.py`.
- **LLM and platform config**: Reads and writes masked LLM config,
  GitHub/Gitee tokens, provider mode, base URL, model, fallback models, and
  token readiness checks. See `routes/config.py`.
- **Repository data extraction and author discovery**: Extracts GitHub/Gitee
  commit data into local storage, fetches Gitee commits, and lists authors with
  commit counts. See `routes/data.py`.
- **Single contributor evaluation**: Evaluates a GitHub or Gitee author using a
  selected plugin, model, and language. Oversized LLM inputs are split into
  sequential token-budget chunks; aliases are supported. See `routes/evaluation.py`.
- **Evaluation merging**: Merges multiple weighted evaluations, especially for
  multi-alias identity aggregation. See `routes/evaluation.py`.
- **Batch workflows**: Batch extracts two to five repositories, finds common
  contributors across repositories, and compares one contributor across multiple
  repositories. See `routes/batch.py`.
- **Growth trajectory analysis**: Analyzes engineer growth over time across
  repositories. Supports aliases, commit ranges, forced checkers, checkpoint
  strategies, and SSE streaming. See `routes/trajectory.py`.
- **Course and group code analysis**: Provides a course-compatible full
  repository group evaluation endpoint, including streaming mode and an
  expected-feature evaluation baseline. See `routes/trajectory.py`.
- **One-off external evaluation**: Performs one-off trajectory or checkpoint
  judgment without saving cache. Supports optional `start_sha`/`end_sha`,
  username inference, and a streaming variant. See `routes/trajectory.py`.
- **Benchmark validation**: Exposes benchmark dataset metadata, paginated
  benchmark repositories, validation runs, and stored benchmark evaluations. See
  `routes/benchmark.py`.
- **Checker integration**: Discovers external checkers and runs them against a
  specific commit in an isolated git worktree. See `routes/checkers.py`.
- **Repos runner proxy**: Forwards `/api/runner/*` calls to the separate repo
  runner service on port `8001`, including streaming `run-all`. See
  `routes/runner_proxy.py`.

## Supporting Layers

Below the API layer, `backend/evaluator` also provides:

- Collectors
- Extraction services
- Plugin and checker registries
- XDG storage path helpers
- Commit loading and filtering utilities
- Trajectory and evaluation services
