#!/bin/bash
# Comprehensive test runner for Ink & Memory backend

set -e  # Exit on first error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}   Ink & Memory Backend Test Suite${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Activate virtual environment
if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ Virtual environment not found${NC}"
    echo "Run: uv venv && source .venv/bin/activate && uv pip install -e ../PolyCLI"
    exit 1
fi

source .venv/bin/activate

# Check if database exists
if [ ! -f "data/ink-and-memory.db" ]; then
    echo -e "${YELLOW}⚠️  Database not found, creating...${NC}"
    python database.py
fi

# Test 1: Database layer
echo -e "\n${BLUE}[1/3] Testing Database Layer${NC}"
echo "----------------------------------------"
python tests/test_database.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database tests passed${NC}"
else
    echo -e "${RED}❌ Database tests failed${NC}"
    exit 1
fi

# Test 2: Server startup
echo -e "\n${BLUE}[2/3] Testing Server Startup${NC}"
echo "----------------------------------------"

# Kill any existing server
lsof -ti:8765 | xargs kill -9 2>/dev/null || true

# Start server in background (disable proxy for local testing)
echo "Starting server..."
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
python server.py > /tmp/test_server.log 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for server to start
echo "Waiting for server to be ready..."
for i in {1..10}; do
    if curl -s http://127.0.0.1:8765/ > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Server is responding${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}❌ Server failed to start after 10 seconds${NC}"
        echo "Server logs:"
        cat /tmp/test_server.log
        kill $SERVER_PID 2>/dev/null
        exit 1
    fi
    sleep 1
done

# Test 3: API endpoints
echo -e "\n${BLUE}[3/3] Testing API Endpoints${NC}"
echo "----------------------------------------"
python tests/test_api_endpoints.py
API_TEST_RESULT=$?

# Cleanup
echo -e "\n${BLUE}Cleaning up...${NC}"
kill $SERVER_PID 2>/dev/null || true
sleep 1
echo "Server stopped"

# Final result
echo ""
echo -e "${BLUE}============================================================${NC}"
if [ $API_TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
    echo -e "${BLUE}============================================================${NC}"
    exit 0
else
    echo -e "${RED}❌ API TESTS FAILED${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""
    echo "Server logs:"
    cat /tmp/test_server.log | tail -50
    exit 1
fi
