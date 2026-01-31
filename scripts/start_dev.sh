#!/bin/bash
# Development startup script for Engineer Skill Evaluator
# Starts both the evaluator backend and webapp frontend in development mode

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

# Load evaluator environment variables
EVALUATOR_ENV="${PROJECT_ROOT}/backend/evaluator/.env.local"
if [ -f "$EVALUATOR_ENV" ]; then
    echo -e "${GREEN}✓${NC} Loading evaluator configuration from .env.local"
    export $(cat "$EVALUATOR_ENV" | grep -v '^#' | grep -v '^$' | xargs)
else
    echo -e "${YELLOW}⚠${NC} Warning: backend/evaluator/.env.local not found, using defaults"
fi

# Load repos_runner environment variables
RUNNER_ENV="${PROJECT_ROOT}/backend/repos_runner/.env.local"
if [ -f "$RUNNER_ENV" ]; then
    echo -e "${GREEN}✓${NC} Loading repos_runner configuration from .env.local"
    export $(cat "$RUNNER_ENV" | grep -v '^#' | grep -v '^$' | xargs)
else
    echo -e "${YELLOW}⚠${NC} Warning: backend/repos_runner/.env.local not found"
fi

# Set evaluator port (default: 8000)
EVALUATOR_PORT=${PORT:-8000}
export EVALUATOR_PORT

# Set repos runner port (default: 8001)
RUNNER_PORT=${RUNNER_PORT:-8001}
export RUNNER_PORT

# Load webapp environment variables
WEBAPP_ENV="${PROJECT_ROOT}/frontend/webapp/.env.local"
if [ -f "$WEBAPP_ENV" ]; then
    echo -e "${GREEN}✓${NC} Loading webapp configuration from .env.local"
    # Parse webapp PORT separately to avoid conflict
    WEBAPP_PORT=$(grep "^PORT=" "$WEBAPP_ENV" | cut -d '=' -f2)
    WEBAPP_PORT=${WEBAPP_PORT:-3000}
else
    echo -e "${YELLOW}⚠${NC} Warning: frontend/webapp/.env.local not found, using defaults"
    WEBAPP_PORT=3000
fi
export PORT=$WEBAPP_PORT

echo ""
echo -e "${BLUE}Configuration:${NC}"
echo -e "  Evaluator Port: ${GREEN}${EVALUATOR_PORT}${NC}"
echo -e "  Runner Port:    ${GREEN}${RUNNER_PORT}${NC}"
echo -e "  Webapp Port:    ${GREEN}${WEBAPP_PORT}${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

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

# Use PYTHONPATH to include project root for backend module imports
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

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

# Wait a bit for evaluator to start
sleep 2

# Check if evaluator is running
if ! kill -0 $EVALUATOR_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Error: Evaluator failed to start."
    exit 1
fi

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

# Wait a bit for runner to start
sleep 2

# Check if runner is running
if ! kill -0 $RUNNER_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Error: Repos Runner failed to start."
    exit 1
fi

# Start webapp frontend in development mode
echo ""
echo -e "${BLUE}Starting webapp frontend (development mode with hot-reload)...${NC}"
cd "${PROJECT_ROOT}/frontend/webapp"

if [ ! -d "node_modules" ]; then
    echo -e "${RED}✗${NC} Error: node_modules not found in frontend/webapp/"
    echo "  Please run: cd frontend/webapp && npm install"
    exit 1
fi

PORT=$WEBAPP_PORT npm run dev &
WEBAPP_PID=$!
echo -e "${GREEN}✓${NC} Webapp started (PID: ${WEBAPP_PID})"
echo -e "  URL: http://localhost:${WEBAPP_PORT}"

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}✓ All services running in development mode${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "\nPress Ctrl+C to stop all services\n"

# Wait for processes
wait $EVALUATOR_PID $RUNNER_PID $WEBAPP_PID
