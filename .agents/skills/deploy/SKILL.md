---
name: deploy
description: Use when deploying or checking production status for evaluator, repos_runner, or webapp services on 10.1.132.63.
---

# Deploy

Deploy all services to the remote production server.

## Server Details

- Host: `10.1.132.63`
- User: `ubuntu`
- SSH command: `ssh ubuntu@10.1.132.63`
- Remote path: `/data/app` by default; allow `REMOTE_PATH=...` to override
- Evaluator port: `8000`
- Repos Runner port: `8001`
- Webapp port: `3000`

## Invocation

Accept these user intents:

```text
deploy
deploy --rebuild
deploy --status
deploy --setup
deploy REMOTE_PATH=/some/path
```

Parse arguments first:
- `--rebuild`: pass `--rebuild` to `start_production.sh`.
- `--status`: skip deployment and only run status checks.
- `--setup`: run first-time clone and environment setup.
- `REMOTE_PATH=/some/path`: override the default remote path.

## Step 1: Commit and Push Local Changes

Skip this step when `--status` or `--setup` is passed.

Check for uncommitted or unpushed local changes:

```bash
git status --short
git log origin/main..HEAD --oneline
```

If there are uncommitted tracked changes, create a concise commit:

```bash
git add -A
git commit -m "feature: <brief description of changes>"
```

If there are unpushed commits, push them:

```bash
git push origin main
```

## Step 2: Validate SSH Connectivity

Run:

```bash
ssh -o ConnectTimeout=10 -o BatchMode=yes ubuntu@10.1.132.63 "echo 'SSH OK'"
```

If this fails, stop and report the exact error. Common causes:
- Server unreachable from the current network.
- Server unreachable.
- The local SSH key or SSH agent is not authorized for `ubuntu`.

## Step 3: Determine Remote Path

Use `/data/app` unless the user passed `REMOTE_PATH=...`. Assign this to `RPATH`.

## Step 4: Status Only

When `--status` is passed, run:

```bash
ssh ubuntu@10.1.132.63 "
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

Then stop.

## Step 5: First-Time Setup

When `--setup` is passed, check whether the repo already exists:

```bash
ssh ubuntu@10.1.132.63 "test -d ${RPATH}/.git && echo EXISTS || echo MISSING"
```

If missing, get the local remote URL:

```bash
git remote get-url origin
```

Clone on the remote server:

```bash
ssh ubuntu@10.1.132.63 "
  mkdir -p $(dirname ${RPATH}) &&
  git clone <remote_url> ${RPATH}
"
```

After cloning, tell the user to SSH into the server and create `${RPATH}/backend/evaluator/.env.local` with required API keys:

```env
PORT=8000
OPEN_ROUTER_KEY=sk-or-v1-...
GITEE_TOKEN=your_token
GITHUB_TOKEN=your_token
```

Then stop and ask the user to run deploy again after the environment file exists.

## Step 6: Pull Latest Changes

Use the auto branch identified in Step 1, or `origin/main` if no push was needed:

```bash
ssh ubuntu@10.1.132.63 "
  cd ${RPATH} &&
  git fetch origin &&
  git reset --hard <auto_branch_or_origin/main> &&
  echo 'Git pull complete, on branch: <branch_name>'
"
```

If the directory does not exist, suggest running deploy with `--setup` first.

## Step 7: Start or Restart Services

```bash
ssh ubuntu@10.1.132.63 "
  cd ${RPATH} &&
  chmod +x scripts/start_production.sh &&
  bash scripts/start_production.sh --daemon ${REBUILD_FLAG}
"
```

Set `REBUILD_FLAG` to `--rebuild` only when the user passed `--rebuild`.

## Step 8: Verify Services

Wait about 5 seconds, then check:

```bash
ssh ubuntu@10.1.132.63 "
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

## Step 9: Report Results

Print a clear summary:

```text
Deployment Complete

Services running on 10.1.132.63:
  Evaluator API:   http://10.1.132.63:8000
  Evaluator Docs:  http://10.1.132.63:8000/docs
  Repos Runner:    http://10.1.132.63:8001
  Webapp:          http://10.1.132.63:3000

Useful commands:
  Check status: deploy --status
  View logs: ssh ubuntu@10.1.132.63 'tail -f /data/app/evaluator.log /data/app/repos_runner.log'
  Stop services: ssh ubuntu@10.1.132.63 "pkill -f 'backend.evaluator.server|repos_runner.server|serve out -l'"
  Restart: deploy
```

## Error Handling

- SSH connection fails: report the exact error and check network reachability and SSH authorization.
- Git push fails: show error output, do not proceed, and do not force push.
- Remote git update fails: show error output and do not proceed.
- `start_production.sh` fails: show the last 30 lines of evaluator or repos_runner logs and suggest `--rebuild` when appropriate.
- Service is not running after deploy: show log tails and suggest checking `.env.local`.
- Port already in use: `start_production.sh` should handle this via `pkill`; if it persists, report and suggest manual intervention.

## Important Notes

- The server is reached through the default SSH configuration with `ssh ubuntu@10.1.132.63`.
- Backend `.env.local` with API keys must exist on the remote server before first deploy.
- The `uv` Python package manager is auto-installed by `start_production.sh` if missing.
- Node.js v18 or newer must be installed on the remote server.
- Logs are at `${RPATH}/evaluator.log`, `${RPATH}/repos_runner.log`, and `${RPATH}/frontend/webapp.log`.
- Pushing to Gitee creates an `auto***` branch; deploy from that branch rather than `origin/main`.
