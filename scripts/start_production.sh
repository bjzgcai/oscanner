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
echo -e "  Webapp Port:    ${GREEN}${WEBAPP_PORT}${NC}"
echo -e "  Rebuild:        ${REBUILD}"
echo -e "  Daemon Mode:    ${DAEMON}"
echo ""

# Kill existing processes
echo -e "${BLUE}Checking for existing processes...${NC}"
KILLED=false

# Kill evaluator processes
if pgrep -f "oscanner serve" > /dev/null; then
    echo -e "${YELLOW}Stopping existing evaluator processes...${NC}"
    pkill -f "oscanner serve" || true
    KILLED=true
fi

# Kill webapp processes
if pgrep -f "next start" > /dev/null; then
    echo -e "${YELLOW}Stopping existing webapp processes...${NC}"
    pkill -f "next start" || true
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
    # Add uv to PATH for current session
    export PATH="$HOME/.cargo/bin:$PATH"
fi

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
if [ ! -d ".next" ] || [ "$REBUILD" = true ]; then
    echo -e "${YELLOW}Building webapp...${NC}"
    npm run build
    echo -e "${GREEN}✓${NC} Webapp built successfully"
else
    echo -e "${GREEN}✓${NC} Webapp already built"
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    pkill -f "oscanner serve" 2>/dev/null || true
    pkill -f "next start" 2>/dev/null || true
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
    nohup bash -c "PORT=$EVALUATOR_PORT uv run oscanner serve" > "${PROJECT_ROOT}/evaluator.log" 2>&1 &
else
    PORT=$EVALUATOR_PORT uv run oscanner serve > "${PROJECT_ROOT}/evaluator.log" 2>&1 &
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

# Start webapp frontend
echo ""
echo -e "${BLUE}Starting webapp frontend...${NC}"
cd "${PROJECT_ROOT}/frontend/webapp"

if [ "$DAEMON" = true ]; then
    nohup bash -c "PORT=$WEBAPP_PORT npm start" > ../webapp.log 2>&1 &
else
    PORT=$WEBAPP_PORT npm start > ../webapp.log 2>&1 &
fi
WEBAPP_PID=$!
echo -e "${GREEN}✓${NC} Webapp started (PID: ${WEBAPP_PID})"
echo -e "  Logs: ${PROJECT_ROOT}/webapp.log"
echo -e "  URL:  http://localhost:${WEBAPP_PORT}"

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}✓ All services running${NC}"
echo -e "${BLUE}======================================${NC}"

if [ "$DAEMON" = true ]; then
    echo -e "\n${GREEN}Services are running in daemon mode${NC}"
    echo -e "View logs: tail -f ${PROJECT_ROOT}/evaluator.log ${PROJECT_ROOT}/webapp.log"
    echo -e "Stop services: pkill -f 'oscanner serve|next start'\n"
else
    echo -e "\nPress Ctrl+C to stop all services\n"
    # Wait for processes
    wait $EVALUATOR_PID $WEBAPP_PID
fi
