# Oscanner Skill Evaluator

[中文 README](README.md) | [English README](README_en.md)

Oscanner is an AI-assisted engineer capability assessment system. It extracts GitHub/Gitee repository activity, evaluates contributors with plugin-defined rubrics, serves FastAPI APIs, and provides a Next.js dashboard.

The bundled default rubric is `zgc_ai_native_2026`, which scores:

- `spec_quality`
- `cloud_architecture`
- `ai_engineering`
- `mastery_professionalism`

Contributor identity is email-first. Use commit email addresses for evaluation, and provide multiple emails when one contributor commits under more than one address.

## Quick Start

```bash
uv sync
uv run oscanner init
uv run oscanner dev --reload --install
```

Default local services:

- Evaluator API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:3000

## LLM Configuration

Run the initializer:

```bash
uv run oscanner init
```

Supported key priority:

- `OSCANNER_LLM_API_KEY`
- `OPENAI_API_KEY`
- `OPEN_ROUTER_KEY`

For OpenAI-compatible providers:

```bash
OSCANNER_LLM_BASE_URL=https://api.example.com/v1
OSCANNER_LLM_API_KEY=sk-your-key
OSCANNER_LLM_MODEL=deepseek/deepseek-v4-pro
```

If the provider uses a non-standard chat completions path:

```bash
OSCANNER_LLM_CHAT_COMPLETIONS_URL=https://api.example.com/v1/chat/completions
```

Recommended platform tokens:

```bash
GITHUB_TOKEN=ghp_your-token
GITEE_TOKEN=your-gitee-token
GITEE_ENTERPRISE_TOKEN=your-enterprise-token
```

## CLI Commands

```bash
uv run oscanner serve --reload
uv run oscanner dashboard --install
uv run oscanner dev --reload --install
```

Extraction and other workflows are available through:

```bash
uv run oscanner --help
```

## Dashboard Workflow

1. Enter one or more GitHub/Gitee repository URLs.
2. Fetch repository data.
3. Select a contributor.
4. Optionally enter multiple commit emails for the same contributor.
5. Run the AI-Native evaluation and inspect plugin-rendered results.

The dashboard validates email format before sending evaluation requests.

## API Examples

Evaluate a single email identity:

```bash
curl -X POST \
  "http://localhost:8000/api/evaluate/octocat/Hello-World/alice%40example.com?plugin=zgc_ai_native_2026" \
  -H "Content-Type: application/json" \
  -d '{"emails":["alice@example.com"]}'
```

Evaluate and merge multiple email identities:

```bash
curl -X POST \
  "http://localhost:8000/api/evaluate/octocat/Hello-World/alice%40example.com?plugin=zgc_ai_native_2026" \
  -H "Content-Type: application/json" \
  -d '{"emails":["alice@example.com","alice@work.com"]}'
```

Compare a contributor across repositories:

```bash
curl -X POST "http://localhost:8000/api/batch/compare-contributor" \
  -H "Content-Type: application/json" \
  -d '{
    "contributor": "alice@example.com",
    "author_emails": ["alice@example.com", "alice@work.com"],
    "repos": [
      {"owner": "owner", "repo": "repo1", "platform": "github"},
      {"owner": "owner", "repo": "repo2", "platform": "gitee"}
    ],
    "plugin": "zgc_ai_native_2026"
  }'
```

## Project Structure

```text
backend/evaluator/       FastAPI evaluator, routes, services, collectors, schemas
backend/repos_runner/    Optional repository runner API
cli/                     `oscanner` command
frontend/webapp/         Next.js dashboard
frontend/pages/          Optional static site
plugins/zgc_ai_native_2026/
plugins/_shared/         Shared plugin scan/view utilities
checkers/                External checker implementations
tests/                   Backend, route, runner, frontend-helper, and checker tests
docs/                    Architecture and workflow docs
```

## Development

Backend tests:

```bash
uv run pytest
```

Frontend tests:

```bash
cd frontend/webapp
npm test
```

Frontend lint/build:

```bash
cd frontend/webapp
npm run lint
npm run build
```

Regenerate plugin view imports:

```bash
cd frontend/webapp
npm run gen:plugin-view-map
```

## Notes

- Treat GitHub and Gitee as first-class providers.
- Use commit email identities for contributor evaluation.
- Plugin score keys are dynamic; consumers should read `scores`, `dimension_keys`, and `dimension_names` instead of assuming a fixed rubric.
- Runtime data, cloned repos, generated reports, and local `.env.local` files should not be committed.
