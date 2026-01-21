# Security Guidelines

## API Token Management
- **GitHub Token**: via `GITHUB_TOKEN` env var (5000 req/hr vs 60 without)
- **Gitee Token**: `GITEE_TOKEN` (public) + `GITEE_ENTERPRISE_TOKEN`
- **LLM Keys**: Priority: `OSCANNER_LLM_API_KEY` > `OPENAI_API_KEY` > `OPEN_ROUTER_KEY`

## Secret Storage
- Config location: `~/.local/share/oscanner/.env.local`
- Masking pattern: `abcd...wxyz` (show first 4 + last 4 chars)
- **Never return secrets in API responses** - always mask

## Data Privacy
- Local storage only (no cloud upload by default)
- User directory-specific: `~/.local/share/oscanner/`
- Can be deleted manually
- No PII collected beyond git commit metadata

## Input Validation
- Sanitize repo URLs before API calls
- Validate author names (no special chars)
- Check file paths before write operations
- Rate limiting on API endpoints (inherited from GitHub/Gitee)

## Authentication
- Environment variables priority: `.env.local` (CWD) > user dotfile > `.env` > process env
- No authentication on local API server (assumes trusted environment)
- External API tokens: passed in `Authorization: token {token}` header
