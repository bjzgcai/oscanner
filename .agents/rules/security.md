# Security Guidelines

## API Token Management
- GitHub token: `GITHUB_TOKEN` env var (5000 requests/hour versus 60 without)
- Gitee tokens: `GITEE_TOKEN` (public) and `GITEE_ENTERPRISE_TOKEN`
- LLM key priority: `OSCANNER_LLM_API_KEY` > `OPENAI_API_KEY` > `OPEN_ROUTER_KEY`

## Secret Storage
- Config location: `~/.local/share/oscanner/.env.local`
- Mask secrets as first 4 plus last 4 characters, for example `abcd...wxyz`
- Never return secrets in API responses; always mask

## Data Privacy
- Local storage only by default; no cloud upload
- User directory-specific storage: `~/.local/share/oscanner/`
- Data can be deleted manually
- No PII collected beyond git commit metadata

## Input Validation
- Sanitize repository URLs before API calls
- Validate author names; reject unsafe special characters
- Check file paths before write operations
- Account for GitHub/Gitee API rate limiting

## Authentication
- Environment variable priority: `.env.local` in CWD > user dotfile > `.env` > process env
- No authentication on local API server; assumes trusted environment
- External API tokens are passed in `Authorization: token {token}` headers
