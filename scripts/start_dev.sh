#!/bin/bash
# Development startup script for Engineer Skill Evaluator
# Starts evaluator, repos runner, and webapp in development mode.

set -e  # Exit on error

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Engineer Skill Evaluator - Development${NC}"
echo -e "${BLUE}======================================${NC}\n"

# Load an env file using shell parsing so quoted values keep working.
load_env_file() {
    local env_file=$1
    local label=$2

    if [ -f "$env_file" ]; then
        echo -e "${GREEN}✓${NC} Loading ${label} configuration from ${env_file#${PROJECT_ROOT}/}"
        set -a
        # shellcheck disable=SC1090
        . "$env_file"
        set +a
    fi
}

pick_env_file() {
    local env_dir=$1
    if [ -f "${env_dir}/.env.local" ]; then
        echo "${env_dir}/.env.local"
    elif [ -f "${env_dir}/.env" ]; then
        echo "${env_dir}/.env"
    fi
}

wait_for_health() {
    local url=$1
    local pid=$2
    local service_name=$3
    local attempts=${4:-40}

    for _ in $(seq 1 "$attempts"); do
        if curl -fsS --max-time 1 "$url" >/dev/null 2>&1; then
            return 0
        fi
        if ! kill -0 "$pid" 2>/dev/null; then
            echo -e "${RED}✗${NC} Error: ${service_name} process exited before becoming healthy."
            return 1
        fi
        sleep 0.5
    done

    echo -e "${RED}✗${NC} Error: ${service_name} did not become healthy: ${url}"
    return 1
}

cleanup() {
    local exit_code=${1:-0}
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    local pids
    pids=$(jobs -p)
    if [ -n "$pids" ]; then
        kill $pids 2>/dev/null || true
    fi
    exit "$exit_code"
}

trap cleanup SIGINT SIGTERM

# Load evaluator environment variables
EVALUATOR_ENV="$(pick_env_file "${PROJECT_ROOT}/backend/evaluator")"
if [ -n "$EVALUATOR_ENV" ]; then
    load_env_file "$EVALUATOR_ENV" "evaluator"
else
    echo -e "${YELLOW}⚠${NC} Warning: backend/evaluator/.env(.local) not found, using defaults"
fi

# Set evaluator port (default: 8000)
EVALUATOR_PORT=${PORT:-8000}
export EVALUATOR_PORT
unset PORT

# Load repos_runner environment variables
RUNNER_ENV="$(pick_env_file "${PROJECT_ROOT}/backend/repos_runner")"
if [ -n "$RUNNER_ENV" ]; then
    load_env_file "$RUNNER_ENV" "repos_runner"
    export REPOS_RUNNER_ENV_FILE="$RUNNER_ENV"
else
    echo -e "${YELLOW}⚠${NC} Warning: backend/repos_runner/.env(.local) not found"
fi

# Set repos runner port (default: 8001)
RUNNER_PORT=${RUNNER_PORT:-${PORT:-8001}}
export RUNNER_PORT
unset PORT

# Load webapp environment variables
WEBAPP_ENV="$(pick_env_file "${PROJECT_ROOT}/frontend/webapp")"
if [ -n "$WEBAPP_ENV" ]; then
    echo -e "${GREEN}✓${NC} Loading webapp configuration from ${WEBAPP_ENV#${PROJECT_ROOT}/}"
    # Parse webapp PORT separately to avoid conflict with backend PORT.
    WEBAPP_PORT=$(grep "^PORT=" "$WEBAPP_ENV" | cut -d '=' -f2)
    WEBAPP_PORT=${WEBAPP_PORT:-3000}
else
    echo -e "${YELLOW}⚠${NC} Warning: frontend/webapp/.env(.local) not found, using defaults"
    WEBAPP_PORT=3000
fi
export PORT=$WEBAPP_PORT
export NEXT_PUBLIC_API_SERVER_URL="http://localhost:${EVALUATOR_PORT}"
export NEXT_PUBLIC_RUNNER_SERVER_URL="http://localhost:${RUNNER_PORT}"

echo ""
echo -e "${BLUE}Configuration:${NC}"
echo -e "  Evaluator Port: ${GREEN}${EVALUATOR_PORT}${NC}"
echo -e "  Runner Port:    ${GREEN}${RUNNER_PORT}${NC}"
echo -e "  Webapp Port:    ${GREEN}${WEBAPP_PORT}${NC}"
echo ""

if [ "${OSCANNER_START_DEV_PRINT_CONFIG:-}" = "1" ]; then
    echo "EVALUATOR_PORT=${EVALUATOR_PORT}"
    echo "RUNNER_PORT=${RUNNER_PORT}"
    echo "WEBAPP_PORT=${WEBAPP_PORT}"
    echo "NEXT_PUBLIC_API_SERVER_URL=${NEXT_PUBLIC_API_SERVER_URL}"
    echo "NEXT_PUBLIC_RUNNER_SERVER_URL=${NEXT_PUBLIC_RUNNER_SERVER_URL}"
    exit 0
fi

# Start evaluator backend in development mode (with reload)
echo -e "${BLUE}Starting evaluator backend (development mode with auto-reload)...${NC}"
cd "${PROJECT_ROOT}"

# Detect Python executable (prefer virtual environment)
if [ -f "${PROJECT_ROOT}/.venv/bin/python" ]; then
    PYTHON="${PROJECT_ROOT}/.venv/bin/python"
elif [ -f "${PROJECT_ROOT}/venv/bin/python" ]; then
    PYTHON="${PROJECT_ROOT}/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
else
    echo -e "${RED}✗${NC} Error: Python not found."
    exit 1
fi

# Use PYTHONPATH to include backend and project root for module imports.
export PYTHONPATH="${PROJECT_ROOT}/backend:${PROJECT_ROOT}:${PYTHONPATH}"

# Run the backend server directly via Python module
PORT=$EVALUATOR_PORT $PYTHON -m uvicorn backend.evaluator.server:app \
    --host 0.0.0.0 \
    --port $EVALUATOR_PORT \
    --reload \
    --reload-dir "${PROJECT_ROOT}/backend/evaluator" \
    --reload-dir "${PROJECT_ROOT}/cli" &
EVALUATOR_PID=$!
echo -e "${GREEN}✓${NC} Evaluator started (PID: ${EVALUATOR_PID})"
echo -e "  URL:  http://localhost:${EVALUATOR_PORT}"
echo -e "  Docs: http://localhost:${EVALUATOR_PORT}/docs"

# Check if evaluator is actually reachable.
wait_for_health "http://127.0.0.1:${EVALUATOR_PORT}/health" "$EVALUATOR_PID" "Evaluator" || cleanup 1

# Start repos_runner backend in development mode (with reload)
echo ""
echo -e "${BLUE}Starting repos_runner backend (development mode with auto-reload)...${NC}"
cd "${PROJECT_ROOT}"

# Run repos_runner server directly via Python module (it sets up its own sys.path)
RUNNER_PORT=$RUNNER_PORT $PYTHON -m uvicorn backend.repos_runner.server:app \
    --host 0.0.0.0 \
    --port $RUNNER_PORT \
    --reload \
    --reload-dir "${PROJECT_ROOT}/backend/repos_runner" &
RUNNER_PID=$!
echo -e "${GREEN}✓${NC} Repos Runner started (PID: ${RUNNER_PID})"
echo -e "  URL:  http://localhost:${RUNNER_PORT}"
echo -e "  Docs: http://localhost:${RUNNER_PORT}/docs"

# Check if runner is actually reachable before starting the webapp.
wait_for_health "http://127.0.0.1:${RUNNER_PORT}/health" "$RUNNER_PID" "Repos Runner" || cleanup 1

# Start webapp frontend in development mode
echo ""
echo -e "${BLUE}Starting webapp frontend (development mode with hot-reload)...${NC}"
cd "${PROJECT_ROOT}/frontend/webapp"

if [ ! -d "node_modules" ]; then
    echo -e "${RED}✗${NC} Error: node_modules not found in frontend/webapp/"
    echo "  Please run: cd frontend/webapp && npm install"
    exit 1
fi

PORT=$WEBAPP_PORT \
NEXT_PUBLIC_API_SERVER_URL="$NEXT_PUBLIC_API_SERVER_URL" \
NEXT_PUBLIC_RUNNER_SERVER_URL="$NEXT_PUBLIC_RUNNER_SERVER_URL" \
npm run dev &
WEBAPP_PID=$!
echo -e "${GREEN}✓${NC} Webapp started (PID: ${WEBAPP_PID})"
echo -e "  URL: http://localhost:${WEBAPP_PORT}"

wait_for_health "http://127.0.0.1:${WEBAPP_PORT}" "$WEBAPP_PID" "Webapp" || cleanup 1

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}✓ All services running in development mode${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "\nPress Ctrl+C to stop all services\n"

# Wait for processes
wait $EVALUATOR_PID $RUNNER_PID $WEBAPP_PID
