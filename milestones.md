# Oscanner / Courses Milestones

## v1.0 Current Capability Baseline

Oscanner is now the evaluation backend used by the standalone dashboard and by the sibling Courses system. The current logic is split into three major paths:

1. **Read-only code quality evaluation**
   - API: `POST /api/trajectory/analyze_one-off`
   - Course batch API: `POST /api/courses/group_analyse_code`
   - Uses GitHub/Gitee commit data, diffs, repository snapshots, plugin rubrics, optional checkers, and an optional `expected_feature` baseline.
   - Supports `start_sha` / `end_sha` commit windows. In one-off mode, the range is inclusive and has no 10-commit minimum.
   - Supports `checkpoint_strategy=period` for long-term growth nodes and `checkpoint_strategy=none` for course/checkpoint scans.

2. **Repository execution and V&V testing**
   - Evaluator proxy API: `POST /api/runner/run-all`
   - Runner API: `POST /api/runner/run-all`
   - Pipeline: clone repository, checkout `sha` or `tag`, generate `REPO_OVERVIEW_{tag}.md`, run tests, collect runtime/static evidence, and write `TEST_REPORT_{tag}.md`.
   - Courses can forward a merged `tag_message` so Oscanner tests against both teacher requirements and repository tag/issue descriptions.
   - Runner emits SSE progress and a final status payload containing scores, report content, token usage, and artifacts.

3. **Growth trajectory analysis**
   - API: `POST /api/trajectory/analyze`
   - Streaming API: `POST /api/trajectory/analyze_stream`
   - Tracks author or alias groups across one or more repositories.
   - Default strategy groups commits into two-week periods and creates a checkpoint only when at least 10 commits are accumulated.
   - Previous checkpoint scores are passed back into plugin prompts so later scores are continuity-aware.

## Course Integration Contract

Courses is the orchestration layer for classes, students, assignments, and reports. Oscanner is the scanner/evaluator layer.

### Courses responsibilities

- Maintains course data, student lists, tags, teacher assignment requirements, and cached `code_quality.json` / `test.json` results.
- Resolves assignment tags such as `Coursework_Submit_2.3`.
- For Gitee, matches tag suffixes and resolves the commit window from the previous tag to the current tag when possible.
- Passes resolved commit boundaries as per-repository `start_sha` / `end_sha`; Oscanner does not narrow group commits from the tag text alone.
- Handles special course cases:
  - zero checkpoints: `Coursework_Submit_1.1`, `Coursework_Submit_1.2`, `Coursework_Submit_2.1`
  - full-repository evaluation: `整体`
  - CI/CD file audit test mode: `Coursework_Submit_4.3`
- Calls Oscanner with `oscanner_api_url`, then persists the returned checkpoint/result back into course storage.

### Oscanner responsibilities

- Validates platform tokens and repository URLs.
- Syncs GitHub/Gitee repository data into XDG/user-local storage.
- Evaluates code through plugin-defined rubrics:
  - `zgc_ai_native_2026`: AI-Native 2026 four-dimension rubric.
  - `zgc_simple`: legacy six-dimension rubric.
- Supports course-shaped payloads under `/api/courses/group_analyse_code`:
  - `students`, `repositories`, `repos`, or single `repo_url`
  - per-repo `start_sha` / `end_sha`
  - optional `tag`
  - optional `expected_feature`
- For `tag="整体"`, evaluates each repository as a whole repo with `evaluate_repository`, not as a single-author trajectory.
- Proxies test execution to `repos_runner` and preserves tag-specific reports and artifacts.

## Completed

### Code Quality Evaluation

- Plugin-based LLM scoring is implemented.
- Single-repo and multi-repo contributor evaluation exist.
- One-off checkpoint scans support optional username inference.
- `username=null` for Gitee one-off scans can infer all authors and use aliases to avoid single-author filtering.
- Commit range filtering supports:
  - no SHA: all commits
  - only `start_sha`: from start commit to latest
  - only `end_sha`: first commit to end commit
  - equal `start_sha` / `end_sha`: single commit
  - invalid or missing SHAs: clear failure response
- Course group scans evaluate repositories in a shared batch with a stable model/rubric/runtime setup.
- Gitee boundary commits can be fetched explicitly when the requested tag SHA is missing from the local branch history.
- Plugin token usage can be returned and summarized for Courses.

### Test Runner

- `run-all` is implemented with SSE streaming.
- Runner supports `sha`, `tag`, and `tag_message`.
- `tag_message` is forwarded from Courses instead of being overwritten by remote tag annotation.
- Reports are tag-versioned as `TEST_REPORT_{tag}.md`.
- Repository overviews are tag-versioned as `REPO_OVERVIEW_{tag}.md`.
- Runtime evidence and screenshots are collected and can be proxied back to Courses.
- Docker sandbox support exists for safer repository execution.

### Growth Trajectory

- Period-based checkpoints are implemented.
- One-off checkpoints are implemented for course-style scans.
- Growth comparison is generated against the previous checkpoint.
- Frontend trajectory charts and plugin checkpoint renderers are wired.
- Backend schemas define `TrajectoryCheckpoint`, `CommitsRange`, `TrajectoryData`, and `TrajectoryResponse`.

## Remaining Work

### Course-facing product polish

- Document the `/api/courses/group_analyse_code` request/response contract in the main API docs.
- Make `expected_feature` available from Courses for group code scans when teacher requirements should affect code-quality scoring, not only runner V&V.
- Add clearer public examples for `commit_window=previous_tag_to_tag` and `commit_window=from_start_to_tag`.
- Align UI wording around Course, Session, Student, Checkpoint, Tag, and V&V with `keywords.md`.

### Evaluation quality

- Expand checker integrations beyond the current configured checker list.
- Add stronger deterministic fallbacks for LLM parse failures without hiding the failure from Courses.
- Improve scoring calibration between read-only code quality and runtime test evidence.
- Add more fixtures around missing tags, empty repositories, and multi-author repositories.

### Operations

- Keep the default model path explicit for course scans: `deepseek/deepseek-v4-pro`.
- Keep token setup visible: `OSCANNER_LLM_API_KEY`, `GITHUB_TOKEN`, `GITEE_TOKEN`.
- Avoid persisting raw secrets in logs or reports.
