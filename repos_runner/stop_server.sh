#!/bin/bash
# Stop the Repository Runner server

echo "Stopping Repository Runner Server..."

# Find and kill the process running on port 8001 (default RUNNER_PORT)
PORT=${RUNNER_PORT:-8001}

# Find PID using lsof
PID=$(lsof -ti:$PORT)

if [ -z "$PID" ]; then
    echo "No server found running on port $PORT"
    exit 0
fi

echo "Found server process: $PID"
kill $PID

# Wait a moment and check if it's still running
sleep 1
if kill -0 $PID 2>/dev/null; then
    echo "Process still running, forcing kill..."
    kill -9 $PID
fi

echo "Server stopped successfully"
