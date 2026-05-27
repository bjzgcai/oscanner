# Production Deployment Guide

## Quick Start - One-Line Deployment

```bash
./deploy.sh
```

This will automatically:
1. SSH to the remote server
2. Pull latest changes from git
3. Install/update dependencies
4. Build the webapp
5. Restart both services

## Prerequisites

### Local Machine
1. Configure `.env.production` with remote server details (see below)
2. Ensure SSH access to the remote server

### Remote Server (First-Time Setup)

#### 1. Required Environment Variables

Create these files on the remote server before first deployment:

**`/data/app/backend/evaluator/.env.local`**
```bash
# Server Configuration
PORT=8000

# Open Router API Key (Required for LLM evaluations)
# Get your API key from: https://openrouter.ai/keys
OPEN_ROUTER_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Gitee Access Tokens (Required for Gitee repository analysis)
# Generate tokens from: https://gitee.com/profile/personal_access_tokens
GITEE_TOKEN=your_enterprise_gitee_token_here

# Optional: GitHub Token (for higher rate limits)
# Without token: 60 requests/hour, With token: 5000 requests/hour
# GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**`/data/app/frontend/webapp/.env.local`**
```bash
# Webapp Server Port
PORT=3000

# API Server URL (optional, for development proxy)
# In production, this is ignored as webapp is served by FastAPI
# NEXT_PUBLIC_API_SERVER_URL=http://localhost:8000
```

#### 2. Required Software

The deployment script will automatically install:
- **uv** (Python package manager) - auto-installed if missing
- **Node.js dependencies** - auto-installed via npm
- **Python dependencies** - auto-synced via uv

You only need to ensure these are available:
- **Git** - for cloning/pulling code
- **Node.js & npm** - for webapp (recommend v18+)
- **Bash** - for running scripts

## Configuration Files

### `.env.production` (Local - for deployment script)

```bash
# Remote server details
REMOTE_HOST=10.1.132.63
REMOTE_USER=ubuntu
REMOTE_PATH=/data/app

# Port configuration (for display only)
EVALUATOR_PORT=8000
WEBAPP_PORT=3000
```

## Deployment Commands

### Standard Deployment
```bash
./deploy.sh
```

### Force Rebuild (rebuild webapp even if already built)
```bash
./deploy.sh --rebuild
```

### Manual Deployment (on remote server)
```bash
ssh ubuntu@10.1.132.63
cd /data/app
git pull origin main
./start_production.sh --daemon
```

## Managing Services

### View Logs
```bash
# From local machine
ssh ubuntu@10.1.132.63 'tail -f /data/app/evaluator.log'

# On remote server
tail -f /data/app/evaluator.log
tail -f /data/app/frontend/webapp.log
```

### Stop Services
```bash
# From local machine
ssh ubuntu@10.1.132.63 "pkill -f 'oscanner serve|next start'"

# On remote server
pkill -f "oscanner serve"
pkill -f "next start"
```

### Restart Services
```bash
./deploy.sh
# OR manually on server:
./start_production.sh --daemon
```

## Access URLs

After deployment, services will be available at:
- **Evaluator API**: http://10.1.132.63:8000
- **Webapp Dashboard**: http://10.1.132.63:3000

## Troubleshooting

### Deployment fails with "Permission denied"
Ensure your SSH key is added to the remote server:
```bash
ssh-copy-id ubuntu@10.1.132.63
```

### Services fail to start
Check the logs on remote server:
```bash
ssh ubuntu@10.1.132.63 'cat /data/app/evaluator.log'
```

### Port already in use
Stop existing processes:
```bash
ssh ubuntu@10.1.132.63 "pkill -f 'oscanner serve|next start'"
```

### Missing environment variables
Verify `.env.local` files exist on remote server with required API keys:
```bash
ssh ubuntu@10.1.132.63 'ls -la /data/app/backend/evaluator/.env.local'
ssh ubuntu@10.1.132.63 'ls -la /data/app/frontend/webapp/.env.local'
```

## Security Notes

### Required Secrets (Manual Setup)

These secrets **MUST** be set manually on each new remote server:

1. **OPEN_ROUTER_KEY** - Required for LLM evaluations
   - Get from: https://openrouter.ai/keys
   - File: `backend/evaluator/.env.local`

2. **GITEE_TOKEN** - Required for Gitee repository analysis
   - Get from: https://gitee.com/profile/personal_access_tokens
   - File: `backend/evaluator/.env.local`

3. **GITHUB_TOKEN** (Optional) - For higher GitHub API rate limits
   - Get from: https://github.com/settings/tokens
   - File: `backend/evaluator/.env.local`

### Security Best Practices

- Never commit `.env.local` files to git
- Use SSH keys instead of passwords
- Keep API tokens secure and rotate them regularly
- Use environment-specific ports (dev and internal prod: 3000/8000)

## Script Options

### `start_production.sh` Options

- `--daemon` - Run services in background (required for remote deployment)
- `--rebuild` - Force rebuild of webapp even if `.next/` exists

### `deploy.sh` Options

- `--rebuild` - Pass rebuild flag to remote `start_production.sh`
