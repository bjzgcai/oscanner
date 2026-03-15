#!/bin/bash
# Production deployment script for Engineer Skill Evaluator
# Automatically installs dependencies, builds, and starts/restarts services
# Usage: ./start_production.sh [--rebuild] [--daemon]

set -e  # Exit on error

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Parse arguments
REBUILD=false
DAEMON=false
for arg in "$@"; do
    case $arg in
        --rebuild) REBUILD=true ;;
        --daemon) DAEMON=true ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Engineer Skill Evaluator - Production${NC}"
echo -e "${BLUE}======================================${NC}\n"

# Load evaluator environment variables
EVALUATOR_ENV="${PROJECT_ROOT}/backend/evaluator/.env.local"
if [ -f "$EVALUATOR_ENV" ]; then
    echo -e "${GREEN}✓${NC} Loading evaluator configuration from .env.local"
    export $(cat "$EVALUATOR_ENV" | grep -v '^#' | grep -v '^$' | xargs)
else
    echo -e "${YELLOW}⚠${NC} Warning: backend/evaluator/.env.local not found, using defaults"
fi

# Set evaluator port (default: 8000)
EVALUATOR_PORT=${PORT:-8000}
export EVALUATOR_PORT

# Load repos_runner environment variables
REPOS_RUNNER_ENV="${PROJECT_ROOT}/backend/repos_runner/.env.local"
if [ -f "$REPOS_RUNNER_ENV" ]; then
    echo -e "${GREEN}✓${NC} Loading repos_runner configuration from .env.local"
    REPOS_RUNNER_PORT=$(grep "^PORT=" "$REPOS_RUNNER_ENV" | cut -d '=' -f2)
    REPOS_RUNNER_PORT=${REPOS_RUNNER_PORT:-8001}
else
    REPOS_RUNNER_PORT=8001
fi
export REPOS_RUNNER_PORT

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
echo -e "  Evaluator Port:    ${GREEN}${EVALUATOR_PORT}${NC}"
echo -e "  Repos Runner Port: ${GREEN}${REPOS_RUNNER_PORT}${NC}"
echo -e "  Webapp Port:       ${GREEN}${WEBAPP_PORT}${NC}"
echo -e "  Rebuild:           ${REBUILD}"
echo -e "  Daemon Mode:       ${DAEMON}"
echo ""

# Kill existing processes
echo -e "${BLUE}Checking for existing processes...${NC}"
KILLED=false

# Kill evaluator processes
if pgrep -f "oscanner serve|backend.evaluator.server" > /dev/null; then
    echo -e "${YELLOW}Stopping existing evaluator processes...${NC}"
    pkill -f "oscanner serve|backend.evaluator.server" || true
    KILLED=true
fi

# Kill repos_runner processes
if pgrep -f "repos_runner.server" > /dev/null; then
    echo -e "${YELLOW}Stopping existing repos_runner processes...${NC}"
    pkill -f "repos_runner.server" || true
    KILLED=true
fi

# Kill webapp processes
if pgrep -f "npx serve|serve out -l ${WEBAPP_PORT} -s" > /dev/null; then
    echo -e "${YELLOW}Stopping existing webapp processes...${NC}"
    pkill -f "npx serve|serve out -l ${WEBAPP_PORT} -s" || true
    KILLED=true
fi

if [ "$KILLED" = true ]; then
    echo -e "${GREEN}✓${NC} Existing processes stopped"
    sleep 2
else
    echo -e "${GREEN}✓${NC} No existing processes found"
fi

# Install/check evaluator dependencies
echo ""
echo -e "${BLUE}Checking evaluator dependencies...${NC}"
cd "${PROJECT_ROOT}"

if ! command -v uv >/dev/null 2>&1; then
    echo -e "${YELLOW}Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Ensure uv is discoverable in non-interactive SSH shells.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
echo -e "${GREEN}✓${NC} uv is available"

# Sync Python dependencies (uv handles this automatically)
echo -e "${YELLOW}Syncing Python dependencies...${NC}"
uv sync
echo -e "${GREEN}✓${NC} Python dependencies ready"

# Install/check webapp dependencies
echo ""
echo -e "${BLUE}Checking webapp dependencies...${NC}"
cd "${PROJECT_ROOT}/frontend/webapp"

if [ ! -d "node_modules" ] || [ "$REBUILD" = true ]; then
    echo -e "${YELLOW}Installing Node.js dependencies...${NC}"
    npm install
    echo -e "${GREEN}✓${NC} Node.js dependencies installed"
else
    echo -e "${GREEN}✓${NC} Node.js dependencies already installed"
fi

# Build webapp
if [ ! -d "out" ] || [ "$REBUILD" = true ]; then
    echo -e "${YELLOW}Building webapp...${NC}"
    npm run build
    echo -e "${GREEN}✓${NC} Webapp built successfully"
else
    echo -e "${GREEN}✓${NC} Webapp already built"
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    pkill -f "oscanner serve|backend.evaluator.server" 2>/dev/null || true
    pkill -f "repos_runner.server" 2>/dev/null || true
    pkill -f "npx serve|serve out -l ${WEBAPP_PORT} -s" 2>/dev/null || true
    exit 0
}

if [ "$DAEMON" = false ]; then
    trap cleanup SIGINT SIGTERM
fi

# Start evaluator backend
echo ""
echo -e "${BLUE}Starting evaluator backend...${NC}"
cd "${PROJECT_ROOT}"

if [ "$DAEMON" = true ]; then
    nohup bash -c "uv run uvicorn backend.evaluator.server:app --host 0.0.0.0 --port $EVALUATOR_PORT" > "${PROJECT_ROOT}/evaluator.log" 2>&1 &
else
    uv run uvicorn backend.evaluator.server:app --host 0.0.0.0 --port $EVALUATOR_PORT > "${PROJECT_ROOT}/evaluator.log" 2>&1 &
fi
EVALUATOR_PID=$!
echo -e "${GREEN}✓${NC} Evaluator started (PID: ${EVALUATOR_PID})"
echo -e "  Logs: ${PROJECT_ROOT}/evaluator.log"
echo -e "  URL:  http://localhost:${EVALUATOR_PORT}"

# Wait a bit for evaluator to start
sleep 3

# Check if evaluator is running
if ! kill -0 $EVALUATOR_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Error: Evaluator failed to start. Check evaluator.log for details."
    tail -n 20 "${PROJECT_ROOT}/evaluator.log"
    exit 1
fi

# Start repos_runner backend
echo ""
echo -e "${BLUE}Starting repos_runner backend...${NC}"
cd "${PROJECT_ROOT}"

if [ "$DAEMON" = true ]; then
    nohup bash -c "uv run uvicorn backend.repos_runner.server:app --host 0.0.0.0 --port $REPOS_RUNNER_PORT" > "${PROJECT_ROOT}/repos_runner.log" 2>&1 &
else
    uv run uvicorn backend.repos_runner.server:app --host 0.0.0.0 --port $REPOS_RUNNER_PORT > "${PROJECT_ROOT}/repos_runner.log" 2>&1 &
fi
REPOS_RUNNER_PID=$!
echo -e "${GREEN}✓${NC} Repos Runner started (PID: ${REPOS_RUNNER_PID})"
echo -e "  Logs: ${PROJECT_ROOT}/repos_runner.log"
echo -e "  URL:  http://localhost:${REPOS_RUNNER_PORT}"

sleep 2

if ! kill -0 $REPOS_RUNNER_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Error: Repos Runner failed to start. Check repos_runner.log for details."
    tail -n 20 "${PROJECT_ROOT}/repos_runner.log"
    exit 1
fi

# Start webapp frontend
echo ""
echo -e "${BLUE}Starting webapp frontend...${NC}"
cd "${PROJECT_ROOT}/frontend/webapp"

if [ "$DAEMON" = true ]; then
    nohup bash -c "npx serve out -l $WEBAPP_PORT -s" > ../webapp.log 2>&1 &
else
    npx serve out -l $WEBAPP_PORT -s > ../webapp.log 2>&1 &
fi
WEBAPP_PID=$!
echo -e "${GREEN}✓${NC} Webapp started (PID: ${WEBAPP_PID})"
echo -e "  Logs: ${PROJECT_ROOT}/frontend/webapp.log"
echo -e "  URL:  http://localhost:${WEBAPP_PORT}"

sleep 2

if ! kill -0 $WEBAPP_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Error: Webapp failed to start. Check frontend/webapp.log for details."
    tail -n 20 "${PROJECT_ROOT}/frontend/webapp.log"
    exit 1
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}✓ All services running${NC}"
echo -e "${BLUE}======================================${NC}"

if [ "$DAEMON" = true ]; then
    echo -e "\n${GREEN}Services are running in daemon mode${NC}"
    echo -e "View logs: tail -f ${PROJECT_ROOT}/evaluator.log ${PROJECT_ROOT}/repos_runner.log ${PROJECT_ROOT}/frontend/webapp.log"
    echo -e "Stop services: pkill -f 'oscanner serve|backend.evaluator.server'; pkill -f 'repos_runner.server'; pkill -f 'npx serve|serve out -l ${WEBAPP_PORT} -s'\n"
else
    echo -e "\nPress Ctrl+C to stop all services\n"
    # Wait for processes
    wait $EVALUATOR_PID $REPOS_RUNNER_PID $WEBAPP_PID
fi
