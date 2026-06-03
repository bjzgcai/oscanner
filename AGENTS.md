# Oscanner Skill Evaluator - Agent Instructions

These instructions apply to `/home/carter/working/eval`.

## Project Overview

Oscanner Skill Evaluator is an AI-assisted engineer capability assessment system. It extracts GitHub/Gitee repository activity, evaluates contributors with plugin-defined rubrics, serves FastAPI APIs, and provides a Next.js dashboard.

- Python package/CLI: `oscanner-skill-evaluator`, command `oscanner`
- Main backend: FastAPI evaluator on port `8000`
- Optional runner backend: FastAPI repos runner on port `8001`
- Dashboard: Next.js webapp on port `3000`
- Dependency manager: prefer `uv` with `pyproject.toml` and `uv.lock`

## Code Structure

### Backend: `backend/evaluator/`

- `server.py`: main FastAPI application and API router wiring
- `routes/`: API endpoints for evaluation, batch work, trajectory, data, config, plugins, runner proxy, benchmark, and checkers
- `services/`: evaluation, extraction, merge, plugin, and trajectory logic
- `collectors/`: GitHub and Gitee API collectors
- `analyzers/`: commit, code, and collaboration analysis
- `schemas/`: Pydantic schemas for evaluation and trajectory APIs
- `config/`: environment and token loading
- `utils/`: repo parsing, commit helpers, git worktrees, data loading
- `validation/`: benchmark dataset and validation runner
- `tools/`: extraction and migration utilities

### Runner: `backend/repos_runner/`

- `server.py`: optional repo testing/exploration API on port `8001`
- `routes/runner.py`: runner endpoints
- `services/repo_service/`: clone, lifecycle, detection, venv, coverage, parsing, LLM, report, and execution logic
- Treat cloned repositories and generated reports as runtime data, not source files.

### CLI: `cli/`

- `cli.py`: unified `oscanner` command for `init`, `serve`, `dashboard`, `dev`, extraction, and related operations.
- Prefer adding user-facing workflows here instead of scattered shell scripts when the behavior belongs in the product.

### Frontend: `frontend/webapp/`

- Next.js App Router, TypeScript, React, Ant Design, charts, and Tailwind/CSS.
- `app/`: routes such as dashboard, repos, runner, trajectory, validation, and settings
- `components/`: dashboard, repository runner, validation, settings, plugin renderers, and shared contexts
- `utils/apiBase.ts`: API base URL handling
- `scripts/gen-plugin-view-map.mjs`: generates `components/generated/pluginViewMap.ts`; npm scripts run it before dev/build/lint/start.

### Static Site: `frontend/pages/`

Optional GitHub Pages/Jekyll static site. Keep this separate from the Next.js dashboard.

### Plugins: `plugins/`

- `zgc_simple/`: traditional six-dimension evaluator
- `zgc_ai_native_2026/`: AI-Native 2026 rubric evaluator
- `_shared/`: shared scan/view utilities
- Each plugin uses `index.yaml`, backend scan code in `scan/`, React views in `view/`, and optional `i18n/`.
- When changing plugin UI, keep backend scan output shape and frontend view expectations aligned.

### Checkers: `checkers/`

External checker implementations and `checker_list.yaml`; currently includes `ccn`.

### Tests And Docs

- Tests live under `tests/` by area: evaluator, repos_runner, routes, GitHub/Gitee APIs, and checkers.
- Architecture docs live under `docs/`; update them when changing major boundaries or workflows.

## Running Locally

- Install/sync dependencies: `uv sync`
- Configure local secrets: `uv run oscanner init`
- Backend only: `uv run oscanner serve --reload`
- Dashboard only: `uv run oscanner dashboard --install`
- Backend + dashboard: `uv run oscanner dev --reload --install`
- All tests: `uv run pytest`
- Targeted tests: `uv run pytest tests/<area>/<test_file>.py -v`
- Frontend dev: `cd frontend/webapp && npm run dev`
- Frontend build: `cd frontend/webapp && npm run build`
- Frontend lint: `cd frontend/webapp && npm run lint`

## Backend Guidelines

- Keep FastAPI route handlers thin; put reusable behavior in `services/`, `collectors/`, `analyzers/`, or `utils/`.
- Use Pydantic schemas from `backend/evaluator/schemas/` for API contracts.
- Preserve GitHub/Gitee collector behavior around rate limits, tokens, incremental sync, and cached data.
- Treat GitHub and Gitee as first-class providers in shared workflows. When adding extraction, sync, trajectory, batch, author, collaboration, checker, or URL behavior for one provider, either implement and test the equivalent path for the other provider or document an intentional limitation.
- Prefer XDG/user-local storage helpers from `paths.py`; avoid hardcoded absolute data paths.
- Keep plugin discovery and scan contracts stable unless updating all affected plugins and views.
- For repository URL handling, use the existing parser and security checks rather than ad hoc string handling.

## Runner Guidelines

- Treat repo execution as untrusted input. Preserve sandbox, path validation, clone lifecycle, and URL security checks.
- Do not write outside intended runtime directories.
- Keep test reports and coverage output deterministic enough for automated consumers.

## Frontend Guidelines

- Use existing Ant Design and local component patterns.
- Keep plugin-specific UI inside plugin `view/` files when the display belongs to a plugin.
- Keep shared dashboard behavior in `frontend/webapp/components/` and API URL logic in `utils/apiBase.ts`.
- Regenerate the plugin view map through npm scripts; do not hand-edit generated output unless the generator is also updated.
- Support both local dev with `NEXT_PUBLIC_API_SERVER_URL=http://localhost:8000` and packaged same-origin dashboard behavior.

## Security And Data

Follow `.agents/rules/security.md`.

- Token priority includes `OSCANNER_LLM_API_KEY`, `OPENAI_API_KEY`, `OPEN_ROUTER_KEY`, `GITHUB_TOKEN`, `GITEE_TOKEN`, and `GITEE_ENTERPRISE_TOKEN`.
- Local config is commonly stored under `~/.local/share/oscanner/.env.local`.
- Never return or log raw secrets. Mask secrets as first 4 plus last 4 characters when needed.
- Validate repository URLs, author names, and file paths before API calls or writes.
- Do not commit generated cache data, cloned repositories, local reports, or `.env.local` files.

## Testing

Follow `.agents/rules/testing.md` for test strategy.

- Prefer real public repositories for collector/evaluation integration tests when appropriate, but isolate external dependencies for unit tests.
- Cover valid inputs, invalid repo URLs, missing data, rate limits, bad LLM responses, corrupted cache files, and multi-alias merge behavior when touching those areas.
- Run the smallest meaningful targeted pytest command first, then broaden to `uv run pytest` for shared or high-risk changes.
- For frontend changes, run `npm run lint` or `npm run build` in `frontend/webapp` when the change affects TypeScript, routing, plugin views, or generated view maps.

## Local Agent Assets

- `.agents/skills/deploy/SKILL.md`: use for deploy, redeploy, setup, or production status on `10.1.132.63`.
- `.agents/skills/test-explore/SKILL.md`: use when asked to evaluate test coverage, quality, or gaps.
- `.agents/rules/security.md`: security and token handling rules.
- `.agents/rules/testing.md`: testing strategy and expected coverage areas.
- `.agents/tasks/`: project task notes and design history.

## Deployment

Use `.agents/skills/deploy/SKILL.md` for production work.

- Host: `ubuntu@10.1.132.63`
- SSH command: `ssh ubuntu@10.1.132.63`
- Default remote path: `/data/app`
- Evaluator API: port `8000`
- Repos Runner: port `8001`
- Webapp: port `3000`

Do not deploy without confirming local changes are committed/pushed according to the deploy skill. Do not force-push.

## Git Workflow

- Work from the current tree and preserve unrelated user changes.
- Prefer Conventional Commit style (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).
- Do not mention Codex, Claude, Anthropic, or other agent branding in commits.
- Keep files inside this repo unless the user explicitly asks otherwise.
- Clean temporary files before finishing.
