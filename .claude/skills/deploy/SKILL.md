---
name: deploy
description: Deploy all services (evaluator backend, repos_runner backend, and webapp frontend) to the remote production server at 112.126.63.117. Handles first-time setup (git clone) and subsequent deployments (git pull + restart). Supports --rebuild to force frontend rebuild and --status to only check service status.
---

Deploy all services to the remote production server.

## Server Details

- **Host**: `112.126.63.117`
- **User**: `ecs-user`
- **SSH Key**: `~/.ssh/wu.pem`
- **Remote Path**: `/home/ecs-user/oscanner` (default, override with `REMOTE_PATH=...` argument)
- **Evaluator Port**: `8000`
- **Repos Runner Port**: `8001`
- **Webapp Port**: `3000`

## Usage

```
/deploy              # Standard deploy (git pull + restart services)
/deploy --rebuild    # Force rebuild of webapp even if .next/ exists
/deploy --status     # Only check current service status (no deploy)
/deploy --setup      # First-time setup: clone repo and configure environment
```

## Workflow

Parse the user's arguments first:
- `--rebuild` → pass `--rebuild` to `start_production.sh`
- `--status` → skip deploy, only run status check
- `--setup` → run first-time clone and environment setup
- `REMOTE_PATH=/some/path` → override default remote path

### Step 1: Commit and push local changes

Skip this step if `--status` or `--setup` was passed.

Check for uncommitted or unpushed local changes:
```bash
git status --short
git log origin/main..HEAD --oneline
```

If there are **uncommitted changes** (staged or unstaged tracked files), create a commit:
```bash
git add -A
git commit -m "feature: <brief description of changes>"
```

If there are **unpushed commits** (local commits ahead of origin/main), push them:
```bash
git push origin main
```



### Step 2: Validate SSH connectivity

Run:
```bash
ssh -i ~/.ssh/wu.pem -o ConnectTimeout=10 -o BatchMode=yes ecs-user@112.126.63.117 "echo 'SSH OK'"
```

If this fails, stop and report the error. Common causes:
- SSH key not found at `~/.ssh/wu.pem`
- Server unreachable
- Key not authorized on server

### Step 3: Determine remote path

Use default `/home/ecs-user/oscanner` unless overridden. Assign to `RPATH`.

### Step 4 (--status only): Check service status

```bash
ssh -i ~/.ssh/wu.pem ecs-user@112.126.63.117 "
  echo '=== Running Processes ==='
  pgrep -fa 'backend.evaluator.server' || echo 'Evaluator: NOT RUNNING'
  pgrep -fa 'repos_runner.server' || echo 'Repos Runner: NOT RUNNING'
  pgrep -fa 'serve out -l' || echo 'Webapp: NOT RUNNING'
  echo ''
  echo '=== Port Status ==='
  ss -tlnp 2>/dev/null | grep -E ':8000|:8001|:3000' || echo 'No services on ports 8000/8001/3000'
  echo ''
  echo '=== Recent Evaluator Log (last 20 lines) ==='
  tail -n 20 ${RPATH}/evaluator.log 2>/dev/null || echo 'No evaluator log found'
  echo ''
  echo '=== Recent Repos Runner Log (last 20 lines) ==='
  tail -n 20 ${RPATH}/repos_runner.log 2>/dev/null || echo 'No repos_runner log found'
  echo ''
  echo '=== Recent Webapp Log (last 20 lines) ==='
  tail -n 20 ${RPATH}/frontend/webapp.log 2>/dev/null || echo 'No webapp log found'
"
```

Then stop — do not proceed to deploy steps.

### Step 5 (--setup only): First-time clone

Check if repo already exists:
```bash
ssh -i ~/.ssh/wu.pem ecs-user@112.126.63.117 "test -d ${RPATH}/.git && echo EXISTS || echo MISSING"
```

If MISSING, get the git remote URL from the local repo:
```bash
git remote get-url origin
```

Then clone on remote:
```bash
ssh -i ~/.ssh/wu.pem ecs-user@112.126.63.117 "
  mkdir -p $(dirname ${RPATH}) &&
  git clone <remote_url> ${RPATH}
"
```

After cloning, remind the user:
> **Action required**: SSH into the server and create `${RPATH}/backend/evaluator/.env.local` with your API keys:
> ```
> PORT=8000
> OPEN_ROUTER_KEY=sk-or-v1-...
> GITEE_TOKEN=your_token
> GITHUB_TOKEN=your_token  # optional
> ```
> Then run `/deploy` to start services.

Then stop.

### Step 6: Pull latest changes

Use the auto branch identified in Step 1 (or `origin/main` if no push was needed):

```bash
ssh -i ~/.ssh/wu.pem ecs-user@112.126.63.117 "
  cd ${RPATH} &&
  git fetch origin &&
  git reset --hard <auto_branch_or_origin/main> &&
  echo 'Git pull complete, on branch: <branch_name>'
"
```

If the directory does not exist, suggest running `/deploy --setup` first.

### Step 7: Start / restart all services

```bash
ssh -i ~/.ssh/wu.pem ecs-user@112.126.63.117 "
  cd ${RPATH} &&
  chmod +x scripts/start_production.sh &&
  bash scripts/start_production.sh --daemon ${REBUILD_FLAG}
"
```

Where `${REBUILD_FLAG}` is `--rebuild` if the user passed `--rebuild`, otherwise empty.

### Step 8: Verify services are running

Wait ~5 seconds, then check:
```bash
ssh -i ~/.ssh/wu.pem ecs-user@112.126.63.117 "
  echo '=== Service Health Check ==='
  pgrep -fa 'backend.evaluator.server' && echo 'Evaluator: RUNNING' || echo 'Evaluator: NOT RUNNING'
  pgrep -fa 'repos_runner.server' && echo 'Repos Runner: RUNNING' || echo 'Repos Runner: NOT RUNNING'
  pgrep -fa 'serve out -l' && echo 'Webapp: RUNNING' || echo 'Webapp: NOT RUNNING'
  echo ''
  echo '=== Last 10 lines of evaluator.log ==='
  tail -n 10 ${RPATH}/evaluator.log 2>/dev/null || echo 'No log yet'
  echo ''
  echo '=== Last 10 lines of repos_runner.log ==='
  tail -n 10 ${RPATH}/repos_runner.log 2>/dev/null || echo 'No log yet'
"
```

### Step 9: Report results

Print a clear summary:
```
======================================
  Deployment Complete!
======================================

Services running on 112.126.63.117:
  Evaluator API:   http://112.126.63.117:8000
  Evaluator Docs:  http://112.126.63.117:8000/docs
  Repos Runner:    http://112.126.63.117:8001
  Webapp:          http://112.126.63.117:3000

Useful commands:
  Check status:  /deploy --status
  View logs:     ssh -i ~/.ssh/wu.pem ecs-user@112.126.63.117 'tail -f /home/ecs-user/oscanner/evaluator.log /home/ecs-user/oscanner/repos_runner.log'
  Stop services: ssh -i ~/.ssh/wu.pem ecs-user@112.126.63.117 "pkill -f 'backend.evaluator.server|repos_runner.server|serve out -l'"
  Restart:       /deploy
```

## Error Handling

- **SSH connection fails**: Report exact error, check key path and server reachability
- **git push fails** (diverged history, etc.): Show error output, do not proceed, do not force push
- **git pull fails** (merge conflicts, etc.): Show error output, do not proceed
- **start_production.sh fails**: Show last 30 lines of evaluator.log or repos_runner.log, suggest `/deploy --rebuild`
- **Service not running after deploy**: Show log tail, suggest checking `.env.local` exists on server
- **Port already in use**: The script handles this automatically via `pkill`, but if it persists, report and suggest manual intervention

## Important Notes

- The SSH key at `~/.ssh/wu.pem` must have correct permissions (`chmod 600 ~/.ssh/wu.pem`)
- Backend `.env.local` with API keys must exist on the remote server before first deploy
- The `uv` Python package manager is auto-installed by `start_production.sh` if missing
- Node.js (v18+) must be pre-installed on the remote server
- Logs are at `${RPATH}/evaluator.log`, `${RPATH}/repos_runner.log`, and `${RPATH}/frontend/webapp.log`
- Pushing to Gitee creates an `auto***` branch — always deploy from this branch, not `origin/main`
