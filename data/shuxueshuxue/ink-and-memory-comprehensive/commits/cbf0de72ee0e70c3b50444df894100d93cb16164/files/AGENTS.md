# Repository Guidelines

## Project Structure & Module Organization
The workspace is split into `backend/` (PolyCLI server, analyzers, deck scheduler) and `frontend/` (React + TipTap UI). `backend/config.py`, `server.py`, and `stateful_analyzer.py` drive voice logic, while `prompts/` and `data/` keep prompt templates and SQLite seeds. React sources live in `frontend/src/` with `components/`, `extensions/` for custom TipTap nodes, and `api/` for fetch helpers; public fonts stay under `frontend/public/`. Reference assets are under `assets/`, with longer-form docs in `docs/`.

## Build, Test, and Development Commands
Backend: `cd backend && uv venv && source .venv/bin/activate` to prep deps, then `uv pip install -e ../PolyCLI` and `python server.py` to boot `http://localhost:8765`. Frontend: `cd frontend && npm install` once, then `npm run dev` for Vite, `npm run build` for prod bundles, and `npm run preview` to sanity-check output. Use `npm run lint` before submitting React changes.

## Coding Style & Naming Conventions
TypeScript files use 2-space indentation, React components are PascalCase within `components/`, hooks/utilities stay camelCase. Prefer functional components with explicit prop typings and co-locate styles with the component. Python follows PEP 8 (4 spaces, snake_case for functions) and places voice prompts near their configs; tap the existing `@@@` markers for complex logic you modify. Keep secrets (API keys, proxy details) inside `backend/models.json` or env vars, never inline.

## Testing Guidelines
Run `cd backend && ./run_tests.sh` for the full database + API suite. Individual modules live in `backend/tests/` where filenames start with `test_*.py`; mirror that pattern when adding coverage (e.g., new endpoint → `test_new_endpoint.py`). The script spins up a temporary server and SQLite db, so ensure port 8765 is free. Frontend currently relies on manual verification; if you add Vitest or Playwright, document the command next to `package.json`.

## Commit & Pull Request Guidelines
Recent Git history favors short, imperative subject lines (e.g., "Add deck publishing backend"). Keep commits scoped to one concern and include context about affected personas or decks when relevant. Pull requests should describe frontend/backend touchpoints, list new commands or migrations, and link issues. Include screenshots or GIFs for UI tweaks and paste the exact `run_tests.sh` / lint output so reviewers can trust the state.

## Security & Configuration Tips
Do not commit populated `backend/models.json`, `ink_and_memory.db`, or real PolyCLI credentials. When sharing repro steps, redact API keys and consider `.env` overrides instead of editing checked-in files. If you need to inspect traffic, prefer local proxies configured via `proxy_config.py` so secrets stay off commits.

## Operational Notes
- Calendar and timeline now share the same session grouping via `frontend/src/utils/sessionGrouping.ts`; both pull captions from `user_sessions` rather than separate logic. If you add new date-derived features, reuse this helper instead of reimplementing grouping.
- Every session persisted to `user_sessions` must have `editor_state.createdAt`. `ensureStateForPersistence()` in `App.tsx` enforces this before manual saves or auto-save, and `saveSessionToDatabase()` is the single pathway for writing sessions (auto-save + “Save today”). Do not bypass these helpers; otherwise sessions missing `createdAt` will reappear.
- Timeline issues usually stem from legacy rows lacking `createdAt`. If you ever see placeholders despite real text, inspect `user_sessions.editor_state_json` for that field, or run a one-off backfill before hunting frontend bugs.
- Backend services force UTC (`TZ=UTC`) via `server.py` / `scheduler.py`. SQLite timestamps are stored in UTC, and frontend code now parses them as UTC before formatting to the user’s local timezone. If you add new Python entrypoints, set `TZ=UTC` or explicitly use `datetime.utcnow()` so timestamps stay consistent.
- Frontend auto-detects the browser timezone (via `Intl.DateTimeFormat().resolvedOptions().timeZone`) after login and pushes it to `/api/preferences`. Backend stores this as `user_preferences.timezone`. If you add new clients or scripts that modify preferences, include the timezone field so the scheduler has accurate offsets.
- Production static assets live at `/var/www/lexicalmathical.com/ink-and-memory/` on 101.201.227.31. Deployments are `npm run build` followed by `rsync dist/ root@...:/var/www/lexicalmathical.com/ink-and-memory/` using `serverManagement/keys/Jeffry.pem`.
- Direct SQLite maintenance happens in `/root/ink-and-memory/backend/data/ink-and-memory.db`. Use `python3` helpers (since `sqlite3` CLI isn’t installed) for ad-hoc queries, and always reset `editor_state.createdAt` when you manually adjust session dates.
- Remote deployment hygiene:
  - The backend runs inside a tmux session named `ink-and-memory` at `/root/ink-and-memory/backend`. Always restart it by killing the old session (`tmux kill-session -t ink-and-memory`) and creating a fresh one (`tmux new -d -s ink-and-memory 'source .venv/bin/activate && python server.py'`). Sending repeated `C-c` without restarting leaves uvicorn waiting for stdin, causing Nginx to serve 502s.
  - After any backend restart, verify the port before declaring success: `curl -I http://127.0.0.1:8765/health` (or `/polycli`) should hit Uvicorn. If you still see 502 from curl, the process probably wasn’t started inside tmux correctly.
  - Control panel proxy rules expect the FastAPI app on `127.0.0.1:8765`; do not change the bind address without updating `/etc/nginx/sites-available/ink-and-memory`.
