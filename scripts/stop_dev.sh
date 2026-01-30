#!/bin/bash
# Development stop script for Engineer Skill Evaluator
# Stops both the evaluator backend and webapp frontend

set -e  # Exit on error

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Stopping Development Services${NC}"
echo -e "${BLUE}======================================${NC}\n"

# Load environment variables to get ports
EVALUATOR_ENV="${PROJECT_ROOT}/backend/evaluator/.env.local"
if [ -f "$EVALUATOR_ENV" ]; then
    export $(cat "$EVALUATOR_ENV" | grep -v '^#' | grep -v '^$' | xargs)
fi

WEBAPP_ENV="${PROJECT_ROOT}/frontend/webapp/.env.local"
if [ -f "$WEBAPP_ENV" ]; then
    WEBAPP_PORT=$(grep "^PORT=" "$WEBAPP_ENV" | cut -d '=' -f2)
    WEBAPP_PORT=${WEBAPP_PORT:-3000}
else
    WEBAPP_PORT=3000
fi

EVALUATOR_PORT=${PORT:-8000}
RUNNER_PORT=${RUNNER_PORT:-8001}

echo -e "${BLUE}Stopping services on ports:${NC}"
echo -e "  Evaluator: ${YELLOW}${EVALUATOR_PORT}${NC}"
echo -e "  Runner:    ${YELLOW}${RUNNER_PORT}${NC}"
echo -e "  Webapp:    ${YELLOW}${WEBAPP_PORT}${NC}"
echo ""

# Function to stop process by port
stop_by_port() {
    local port=$1
    local service_name=$2

    # Find PID using the port
    local pid=$(lsof -ti:$port 2>/dev/null)

    if [ -z "$pid" ]; then
        echo -e "${YELLOW}⚠${NC} No process found on port $port ($service_name)"
        return 0
    fi

    echo -e "${BLUE}Stopping $service_name (PID: $pid)...${NC}"
    kill $pid 2>/dev/null || true

    # Wait a bit and check if process is still running
    sleep 1
    if kill -0 $pid 2>/dev/null; then
        echo -e "${YELLOW}Process still running, force killing...${NC}"
        kill -9 $pid 2>/dev/null || true
    fi

    echo -e "${GREEN}✓${NC} $service_name stopped"
}

# Stop evaluator backend
stop_by_port $EVALUATOR_PORT "Evaluator Backend"

# Stop repos_runner backend
stop_by_port $RUNNER_PORT "Repos Runner Backend"

# Stop webapp frontend
stop_by_port $WEBAPP_PORT "Webapp Frontend"

# Additionally, kill any remaining Python server.py or npm run dev processes
echo ""
echo -e "${BLUE}Cleaning up any remaining processes...${NC}"

# Kill any remaining evaluator server processes
pkill -f "python.*server.py" 2>/dev/null && echo -e "${GREEN}✓${NC} Cleaned up server processes" || true

# Kill any remaining repos_runner server processes
pkill -f "python.*repos_runner.server" 2>/dev/null && echo -e "${GREEN}✓${NC} Cleaned up repos_runner processes" || true

# Kill any remaining Next.js dev processes
pkill -f "next dev" 2>/dev/null && echo -e "${GREEN}✓${NC} Cleaned up Next.js processes" || true

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}✓ All development services stopped${NC}"
echo -e "${BLUE}======================================${NC}\n"
