#!/bin/bash
# Development startup script for Engineer Skill Evaluator
# Starts both the evaluator backend and webapp frontend in development mode

set -e  # Exit on error

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

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
EVALUATOR_ENV="${PROJECT_ROOT}/evaluator/.env.local"
if [ -f "$EVALUATOR_ENV" ]; then
    echo -e "${GREEN}✓${NC} Loading evaluator configuration from .env.local"
    export $(cat "$EVALUATOR_ENV" | grep -v '^#' | grep -v '^$' | xargs)
else
    echo -e "${YELLOW}⚠${NC} Warning: evaluator/.env.local not found, using defaults"
fi

# Load repos_runner environment variables
RUNNER_ENV="${PROJECT_ROOT}/repos_runner/.env.local"
if [ -f "$RUNNER_ENV" ]; then
    echo -e "${GREEN}✓${NC} Loading repos_runner configuration from .env.local"
    export $(cat "$RUNNER_ENV" | grep -v '^#' | grep -v '^$' | xargs)
else
    echo -e "${YELLOW}⚠${NC} Warning: repos_runner/.env.local not found"
fi

# Set evaluator port (default: 8000)
EVALUATOR_PORT=${PORT:-8000}
export EVALUATOR_PORT

# Set repos runner port (default: 8001)
RUNNER_PORT=${RUNNER_PORT:-8001}
export RUNNER_PORT

# Load webapp environment variables
WEBAPP_ENV="${PROJECT_ROOT}/webapp/.env.local"
if [ -f "$WEBAPP_ENV" ]; then
    echo -e "${GREEN}✓${NC} Loading webapp configuration from .env.local"
    # Parse webapp PORT separately to avoid conflict
    WEBAPP_PORT=$(grep "^PORT=" "$WEBAPP_ENV" | cut -d '=' -f2)
    WEBAPP_PORT=${WEBAPP_PORT:-3000}
else
    echo -e "${YELLOW}⚠${NC} Warning: webapp/.env.local not found, using defaults"
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

if ! command -v uv >/dev/null 2>&1; then
    echo -e "${RED}✗${NC} Error: uv is not installed."
    echo "  Install uv first: https://docs.astral.sh/uv/"
    exit 1
fi

PORT=$EVALUATOR_PORT uv run oscanner serve --reload &
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

# Check if virtual environment exists
if [ ! -d "${PROJECT_ROOT}/evaluator/venv" ]; then
    echo -e "${RED}✗${NC} Error: Virtual environment not found at ${PROJECT_ROOT}/evaluator/venv"
    echo "  Please create a virtual environment first:"
    echo "  cd ${PROJECT_ROOT}/evaluator && python3 -m venv venv"
    exit 1
fi

# Install repos_runner dependencies if needed
source "${PROJECT_ROOT}/evaluator/venv/bin/activate"
pip install -q -r "${PROJECT_ROOT}/repos_runner/requirements.txt"

RUNNER_PORT=$RUNNER_PORT python -m repos_runner.server &
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
cd "${PROJECT_ROOT}/webapp"

if [ ! -d "node_modules" ]; then
    echo -e "${RED}✗${NC} Error: node_modules not found in webapp/"
    echo "  Please run: cd webapp && npm install"
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
