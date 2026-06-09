#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SSH_TARGET="${OSCANNER_DEPLOY_SSH_TARGET:-ubuntu@10.1.132.63}"
REMOTE_PATH="${OSCANNER_DEPLOY_REMOTE_PATH:-/data/app}"
REMOTE_NAME="${OSCANNER_DEPLOY_REMOTE_NAME:-origin}"
DEPLOY_REF="${OSCANNER_DEPLOY_REF:-}"

REBUILD_FLAG=""
RUN_STATUS=0
RUN_SETUP=0
SKIP_GIT_CHECK=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options] [REMOTE_PATH=/path]

Deploy Oscanner evaluator, repos runner, and webapp services to the internal
server without running git add, git commit, or git push.

Options:
  --rebuild          Pass --rebuild to scripts/start_production.sh.
  --status           Only check remote process, port, log, and HTTP status.
  --setup            First-time setup: create remote path and clone the repo.
  --skip-git-check   Do not stop on dirty or unpushed local changes.
  --ref <ref>        Remote git ref to deploy, for example origin/main.
  -h, --help         Show this help.

Environment overrides:
  OSCANNER_DEPLOY_SSH_TARGET    default: ubuntu@10.1.132.63
  OSCANNER_DEPLOY_REMOTE_PATH   default: /data/app
  OSCANNER_DEPLOY_REMOTE_NAME   default: origin
  OSCANNER_DEPLOY_REF           default: origin/<current-branch>
EOF
}

log() {
  printf '\n==> %s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found"
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --rebuild)
        REBUILD_FLAG="--rebuild"
        ;;
      --status)
        RUN_STATUS=1
        ;;
      --setup)
        RUN_SETUP=1
        ;;
      --skip-git-check)
        SKIP_GIT_CHECK=1
        ;;
      --ref)
        shift
        [ "$#" -gt 0 ] || die "--ref requires a value"
        DEPLOY_REF="$1"
        ;;
      REMOTE_PATH=*)
        REMOTE_PATH="${1#REMOTE_PATH=}"
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        usage >&2
        die "unknown option: $1"
        ;;
    esac
    shift
  done
}

resolve_deploy_ref() {
  if [ -n "$DEPLOY_REF" ]; then
    return
  fi

  local branch
  branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
  [ "$branch" != "HEAD" ] || die "cannot infer deploy ref from detached HEAD; pass --ref origin/<branch>"
  DEPLOY_REF="${REMOTE_NAME}/${branch}"
}

check_local_git_state() {
  [ "$SKIP_GIT_CHECK" -eq 0 ] || return

  log "Checking local git state"
  local status
  status="$(git -C "$REPO_ROOT" status --short)"
  if [ -n "$status" ]; then
    printf '%s\n' "$status"
    die "local worktree has uncommitted changes; commit/push manually first or pass --skip-git-check"
  fi

  local upstream
  upstream="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
  if [ -n "$upstream" ]; then
    local unpushed
    unpushed="$(git -C "$REPO_ROOT" log "$upstream..HEAD" --oneline)"
    if [ -n "$unpushed" ]; then
      printf '%s\n' "$unpushed"
      die "local commits are not pushed; push manually first or pass --skip-git-check"
    fi
  else
    log "No upstream configured; skipping unpushed-commit check"
  fi
}

check_ssh() {
  require_command ssh
  log "Checking SSH connectivity"
  ssh -o ConnectTimeout=10 -o BatchMode=yes "$SSH_TARGET" "echo 'SSH OK'"
}

status_check() {
  log "Checking remote status"
  ssh "$SSH_TARGET" "
    echo '=== Running Processes ==='
    pgrep -fa 'backend.evaluator.server' || echo 'Evaluator: NOT RUNNING'
    pgrep -fa 'repos_runner.server' || echo 'Repos Runner: NOT RUNNING'
    pgrep -fa 'serve out -l' || echo 'Webapp: NOT RUNNING'
    echo ''
    echo '=== Port Status ==='
    ss -tlnp 2>/dev/null | grep -E ':8000|:8001|:3000' || echo 'No services on ports 8000/8001/3000'
    echo ''
    echo '=== Data Directory ==='
    ls -la /data 2>/dev/null || echo '/data not found or not readable'
    echo ''
    echo '=== Recent Evaluator Log (last 20 lines) ==='
    tail -n 20 '${REMOTE_PATH}/evaluator.log' 2>/dev/null || echo 'No evaluator log found'
    echo ''
    echo '=== Recent Repos Runner Log (last 20 lines) ==='
    tail -n 20 '${REMOTE_PATH}/repos_runner.log' 2>/dev/null || echo 'No repos_runner log found'
    echo ''
    echo '=== Recent Webapp Log (last 20 lines) ==='
    tail -n 20 '${REMOTE_PATH}/frontend/webapp.log' 2>/dev/null || echo 'No webapp log found'
    echo ''
    echo '=== Webapp HTTP Status ==='
    curl -I http://127.0.0.1:3000/ 2>/dev/null || true
    if test -d '${REMOTE_PATH}/frontend/webapp/out/oscanner'; then
      curl -I http://127.0.0.1:3000/oscanner/ 2>/dev/null || true
    fi
  "
}

setup_remote() {
  local remote_url
  remote_url="$(git -C "$REPO_ROOT" remote get-url "$REMOTE_NAME")"

  log "Checking whether remote repository already exists"
  local exists
  exists="$(ssh "$SSH_TARGET" "test -d '${REMOTE_PATH}/.git' && echo EXISTS || echo MISSING")"
  if [ "$exists" = "EXISTS" ]; then
    log "Remote repository already exists at ${REMOTE_PATH}"
    return
  fi

  log "Cloning repository to ${REMOTE_PATH}"
  ssh "$SSH_TARGET" "
    sudo mkdir -p '${REMOTE_PATH}' &&
    sudo chown -R ubuntu:ubuntu '${REMOTE_PATH}' &&
    git clone '${remote_url}' '${REMOTE_PATH}'
  "

  cat <<EOF

Remote clone is ready. Before deploying, create:
  ${REMOTE_PATH}/backend/evaluator/.env.local

Include production API keys and persistent data config such as:
  PORT=8000
  OSCANNER_HOME=/data

Then run this script again without --setup.
EOF
}

update_remote_code() {
  log "Updating remote code to ${DEPLOY_REF}"
  ssh "$SSH_TARGET" "
    set -e
    test -d '${REMOTE_PATH}/.git' || {
      echo 'Remote repository missing at ${REMOTE_PATH}. Run with --setup first.'
      exit 1
    }
    cd '${REMOTE_PATH}'
    git fetch '${REMOTE_NAME}'
    git reset --hard '${DEPLOY_REF}'
    echo 'Git update complete:'
    git --no-pager log -1 --oneline
  "
}

restart_services() {
  log "Starting/restarting production services"
  ssh "$SSH_TARGET" "
    set -e
    cd '${REMOTE_PATH}'
    chmod +x scripts/start_production.sh
    bash scripts/start_production.sh --daemon ${REBUILD_FLAG}
  "
}

verify_services() {
  log "Waiting for services"
  sleep 5

  log "Verifying remote services"
  ssh "$SSH_TARGET" "
    echo '=== Service Health Check ==='
    pgrep -fa 'backend.evaluator.server' && echo 'Evaluator: RUNNING' || echo 'Evaluator: NOT RUNNING'
    pgrep -fa 'repos_runner.server' && echo 'Repos Runner: RUNNING' || echo 'Repos Runner: NOT RUNNING'
    pgrep -fa 'serve out -l' && echo 'Webapp: RUNNING' || echo 'Webapp: NOT RUNNING'
    echo ''
    echo '=== Data Directory ==='
    ls -la /data 2>/dev/null || echo '/data not found or not readable'
    echo ''
    echo '=== Last 10 lines of evaluator.log ==='
    tail -n 10 '${REMOTE_PATH}/evaluator.log' 2>/dev/null || echo 'No log yet'
    echo ''
    echo '=== Last 10 lines of repos_runner.log ==='
    tail -n 10 '${REMOTE_PATH}/repos_runner.log' 2>/dev/null || echo 'No log yet'
    echo ''
    echo '=== Webapp HTTP Check ==='
    curl -I http://127.0.0.1:3000/ 2>/dev/null || true
    if test -d '${REMOTE_PATH}/frontend/webapp/out/oscanner'; then
      curl -I http://127.0.0.1:3000/oscanner/ 2>/dev/null || true
    fi
  "
}

parse_args "$@"
resolve_deploy_ref
check_ssh

if [ "$RUN_STATUS" -eq 1 ]; then
  status_check
  exit 0
fi

if [ "$RUN_SETUP" -eq 1 ]; then
  setup_remote
  exit 0
fi

check_local_git_state
update_remote_code
restart_services
verify_services

cat <<EOF

Deployment complete.

Services on 10.1.132.63:
  Evaluator API:   http://10.1.132.63:8000
  Evaluator Docs:  http://10.1.132.63:8000/docs
  Repos Runner:    http://10.1.132.63:8001
  Webapp:          http://10.1.132.63:3000
  Remote path:     ${REMOTE_PATH}

Useful commands:
  Status: $(basename "$0") --status
  Logs:   ssh ${SSH_TARGET} 'tail -f ${REMOTE_PATH}/evaluator.log ${REMOTE_PATH}/repos_runner.log ${REMOTE_PATH}/frontend/webapp.log'
EOF
