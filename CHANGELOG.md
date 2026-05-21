# Changelog

All notable changes to Oscanner Skill Evaluator are summarized from the git
history.

The package version in `pyproject.toml` is currently `0.1.6`; later work has not
been tagged as a release in this repository. Latest commit covered: `1953ff4` on
2026-05-21.

## 2026-04 to 2026-05

### Added

- Added stream-mode evaluation and streaming group evaluation.
- Added runtime evidence analysis for repository runs.
- Added Docker sandbox runner support.
- Added tag-message support for runner execution.
- Added DeepSeek V4 Pro and configurable cache usage for evaluations.
- Added filtered full-repository snapshot context extraction at `end_sha` for
  GitHub and Gitee evaluations, including `repo_files` manifests for richer
  plugin reasoning.
- Added a 10M-token evaluator guardrail that stops oversized evaluation
  requests before LLM work begins.
- Added Oscanner repository runner flows across backend proxy and frontend UI,
  including streaming, durable polling, artifacts, reports, token usage, and
  configured API routing.
- Added namespaced repository-runner storage with migration tooling.
- Added runner concurrency limits, clone and pipeline timeout controls,
  transient clone retries, and `opencode`-based repository exploration.
- Added local agent skills and refreshed repository agent instructions.

### Changed

- Improved group evaluation behavior and excluded low-value files from analysis.
- Improved evaluator extraction and repository path handling.
- Preserved both report and overview markdown after fresh clones.
- Sped up Gitee author lookup.
- Removed the strict cache contract from evaluator APIs and matching frontend
  controls.
- Reworked plugin token-budget handling, final reasoning structure, and
  AI-native runtime evidence reporting.
- Expanded repository-runner runtime evidence scoring, Docker evidence handling,
  artifact reporting, and no-test command summaries.
- Normalized repository URL handling across backend routes, runner storage, and
  frontend inputs.
- Simplified the validation benchmark flow and related dashboard UI.

### Fixed

- Surfaced LLM parse failures more clearly.
- Handled Gitee group boundary commits.
- Disabled stale caching for author APIs and forced trajectory sync when cache
  is disabled.
- Excluded a known internal author from commit analysis.
- Secured repository path handling and masked authenticated Git URLs in clone
  command errors, Git stderr, and extractor process arguments.
- Fixed GitHub author discovery to use faster commit-only extraction, skip
  unnecessary snapshots, and time out extractor requests.
- Kept runner reports and responses responsive during long test runs and skipped
  long-lived service commands.
- Handled empty LLM retry responses and missing runtime-evidence paths.
- Routed runner API calls through the configured base URL and isolated the
  repository-runner production port.

## 2026-03

### Added

- Added repository-runner batch operations and resource sandbox management.
- Added Gitee file-content fetching and updated trajectory defaults.
- Added runner tag checkout, recursive test discovery, auth-token clone support,
  and tag-aware report/version output.
- Added SSE report content events, Chinese-localized `TEST_REPORT` output, a
  `/report` endpoint, and `/version` endpoints for both backend services.
- Added configurable runner LLM models and OpenRouter fallback model routing.

### Changed

- Split the repository runner service into focused submodules.
- Tuned repository analysis and report formatting.
- Updated deploy scripts, evaluator scripts, line endings, and executable
  permissions.
- Raised sandbox process limits where needed and removed per-language sandbox
  limits from the test runner.

### Fixed

- Fixed production webapp build root issues, static dashboard serving, strict
  TypeScript score casts, and package inclusion.
- Fixed run-all connection errors, asyncio cancellation handling, coverage
  service behavior, empty overview language detection, and runner timeout limits.
- Fixed runner environment priority, OpenRouter response parsing, missing final
  text fallback, Anthropic auth-token credentials, and evaluator env loading.

## 2026-02

### Added

- Added checkpoint strategy support and one-off trajectory analysis.
- Added run-all runner endpoints and SHA range filtering for trajectory and
  runner APIs.
- Added Compare Students with runner proxy integration before later removing the
  feature during project simplification.
- Added checker management and a cyclomatic complexity checker.
- Added architecture discussion documents and project target definitions.

### Changed

- Reworked project structure and documentation.
- Removed legacy PQ and Compare Students modules as the evaluator direction
  changed.
- Updated async handling, API endpoint URLs, documentation, and milestones.

## 2026-01

### Added

- Added package and CLI support with `uv`, `pyproject.toml`, and the
  `oscanner` command.
- Published package versions `0.1.4` and `0.1.6`.
- Added deployment automation, configurable ports, Gitee CI updates, and
  production dependency management.
- Added batch repository processing, cross-repo contributor comparison,
  user-selectable AI models, Markdown report rendering, and Markdown export.
- Added plugin-based scanning, plugin input view constraints, plugin discovery,
  and an AI-Native 2026 evaluation plugin.
- Added language pack support, bilingual UI/plugin support, API proxying for
  webapp dev mode, settings persistence, and centralized LLM settings.
- Added an automated validation framework with 60+ benchmark repositories and a
  validation dashboard.
- Added growth trajectory tracking with checkpoint expansion, period
  accumulation, multi-author analysis, grouped username caching, and trajectory
  configuration UI.
- Added repository runner service with batch analysis UI, per-repository virtual
  environments, automated test reports, SSE streaming, test detection, output
  parsing, and i18n support.
- Added PQ activity tracking and percentage charting before that module was
  removed in the February simplification.
- Added project documentation, contributing guides, engineer-level standards,
  keywords, and a Gitee Pages/Jekyll site.

### Changed

- Migrated from the early dashboard into the React/Next.js webapp structure and
  cleaned project data directories.
- Modularized the FastAPI server into routes, services, and config layers.
- Reworked UI styling, navigation, landing route behavior, score visualization,
  and repository breakdown display.
- Replaced PDF export with Markdown export.
- Made caching default behavior while also adding explicit cache controls for
  evaluation requests.

### Fixed

- Improved token documentation, incremental sync, author aliases, and consistent
  author lists across cache states.
- Required explicit user action for contributor evaluation instead of automatic
  evaluation.
- Fixed plugin discovery, import names, base-path behavior, Gitee Pages
  compatibility, missing dependencies, startup scripts, NVM deployment setup,
  production chart cleanup, LLM parsing reliability, and reasoning accumulation.

## 2025-12

### Added

- Created the initial engineer capability assessment dashboard.
- Added metrics, commit extraction, caching, Gitee support, repository URL
  autocomplete, and LLM-powered commit evaluation with a FastAPI backend.
- Added the MIT license and initial README architecture updates.

### Changed

- Reorganized early usage documentation, server port documentation, project
  structure notes, and cached data handling.

### Fixed

- Fixed early cached data issues.
