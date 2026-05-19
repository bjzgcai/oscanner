# Oscanner / Courses Feature Logic

## Core Domain

Courses manages teaching entities. Oscanner performs scans.

- **Course**: a complete teaching subject.
- **Session / Cohort**: a concrete course offering.
- **Student**: a learner with a repository.
- **Checkpoint**: an assignment/evaluation node.
- **Tag**: the Git marker for the submitted checkpoint, usually matching the assignment issue title.
- **V&V scan**: verification plus validation of the tagged code.
- **Growth trajectory**: score and capability changes across checkpoints.

## Main Workflows

### 1. Course Code Quality Scan

Courses endpoint:

```text
POST /api/courses/group_analyse_code
```

Courses builds a student/repository batch, resolves tag windows, and calls Oscanner:

```text
POST {oscanner_api_url}/api/courses/group_analyse_code
```

Accepted Oscanner payload shapes:

```json
{
  "students": [
    {
      "id": "student-id",
      "repo_url": "https://gitee.com/org/repo",
      "tag": "Coursework_Submit_2.3",
      "start_sha": "optional-inclusive-start",
      "end_sha": "optional-inclusive-end"
    }
  ],
  "expected_feature": "Optional requirement baseline for scoring"
}
```

Oscanner also accepts `repositories`, `repos`, or a single `repo_url` for compatibility.

Current behavior:

- `tag="整体"` triggers full-repository evaluation.
- Normal assignment tags are narrowed only when Courses resolves and passes `start_sha` / `end_sha`.
- Gitee tags are resolved by suffix in Courses, then passed as per-repository `start_sha` / `end_sha`.
- If no SHA boundary is provided, Oscanner evaluates all stored commits for that repository.
- Repository-scoped group evaluation does not filter by author.
- Results include `success`, `results`, `summary`, optional `token_usage`, and per-row `checkpoint`.

### 2. Single Checkpoint / Public Evaluation

Courses can call Oscanner one-off analysis for a single repo:

```text
POST /api/trajectory/analyze_one-off?checkpoint_strategy=none&start_sha=...&end_sha=...
```

Payload:

```json
{
  "username": "CarterWu",
  "repo_urls": ["https://gitee.com/zgcai/oscanner"],
  "aliases": ["CarterWu", "wu-yanbiao"],
  "expected_feature": "Optional feature description"
}
```

Rules:

- `username` may be omitted; Oscanner tries to infer it from the first commit author.
- `username=null` on Gitee can infer all authors and use aliases to approximate whole-repo author coverage.
- `checkpoint_strategy=none` creates one checkpoint with no minimum commit count.
- The response contains one final `checkpoint` plus `commits_analyzed`.

### 3. Repository Test Runner

Courses test endpoint calls:

```text
POST {oscanner_api_url}/api/runner/run-all
```

Payload:

```json
{
  "repo_url": "https://gitee.com/org/repo",
  "sha": "optional-commit-sha",
  "tag": "resolved-tag-or-requested-tag",
  "tag_message": "## Course tag requirements\n\n...\n\n## Repository tag description\n\n..."
}
```

Runner logic:

- `sha` has priority over `tag`.
- `tag_message` is the merged requirement source from Courses and is forwarded into exploration, runtime evidence, feature extraction, and the final report.
- If no forwarded `tag_message` exists and a Gitee `tag` exists, runner can fetch the tag annotation itself.
- Output files are tag-scoped:
  - `REPO_OVERVIEW_{tag}.md`
  - `TEST_REPORT_{tag}.md`
  - `TEST_ARTIFACTS_{tag}/...`
- The SSE stream emits progress events and a final status event with `results`, `report_content`, and `token_usage`.

### 4. Long-Term Growth Trajectory

Oscanner dashboard endpoint:

```text
POST /api/trajectory/analyze
```

Behavior:

- Syncs all configured repos.
- Filters commits by username and aliases.
- Groups commits into two-week periods from the repository start date.
- Accumulates periods until at least 10 commits are available.
- Creates checkpoint evaluations and growth comparisons.
- Passes previous checkpoint scores into later plugin prompts to reduce noisy score jumps.

## Special Course Tags

- `Coursework_Submit_1.1`, `Coursework_Submit_1.2`, `Coursework_Submit_2.1`: zero checkpoints in Courses.
- `Coursework_Submit_4.3`: Courses uses CI/CD file audit mode for tests.
- `整体`: Courses calls Oscanner group repository evaluation for the full repository history.

## Data Persistence

Oscanner stores extracted and generated runtime data under user-local paths:

- data: `~/.local/share/oscanner/data`
- cloned runner repos: `~/.local/share/oscanner/repos`

Courses stores course-level results in its own course data files:

- `code_quality.json`: code-quality checkpoints/results.
- `test.json`: runner/test checkpoints/results.

## Current Feature Status

| Feature | Status | Notes |
| --- | --- | --- |
| Plugin code-quality scoring | Done | `zgc_ai_native_2026` and `zgc_simple` |
| One-off commit-window scan | Done | Inclusive `start_sha` / `end_sha` |
| Period growth trajectory | Done | Two-week periods, 10-commit minimum |
| Course group code scan | Done | Whole-repo group endpoint in Oscanner |
| Full repo `整体` scan | Done | Uses repository evaluator path |
| Runner `run-all` pipeline | Done | Clone, explore, tests, evidence, report |
| Course `tag_message` forwarding | Done | Teacher + repo tag requirements |
| Runtime screenshots/artifacts | Done | Runner stores artifacts; Courses proxies links |
| Expected feature scoring baseline | Partly done | Oscanner accepts it; Courses should pass it where needed |
| API contract docs | Needs work | Main README/docs do not yet describe course endpoints enough |

## Important Implementation Notes

- Keep route handlers thin and preserve service ownership:
  - API wiring: `backend/evaluator/routes/`
  - orchestration: `backend/evaluator/services/trajectory_service.py`
  - runner execution: `backend/repos_runner/services/repo_service/`
  - course orchestration: sibling `courses/backend/routers/courses/`
- Do not hand-edit `frontend/webapp/components/generated/pluginViewMap.ts`; update plugin view entries and rerun the generator.
- Do not log raw tokens or write `.env.local` / `.env.prod` contents into docs or reports.
- Validate repository URLs and file paths through existing helpers rather than new ad hoc parsing.
