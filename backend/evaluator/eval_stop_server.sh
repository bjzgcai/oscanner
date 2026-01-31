#!/bin/bash

echo "============================================"
echo "Stopping Engineer Skill Evaluator Server"
echo "============================================"

# Find the PID of the running server
PID=$(ps aux | grep '[p]ython.*server.py' | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "No server process found"
    exit 0
fi

echo "Found server process: PID $PID"
echo "Stopping server..."

kill $PID

# Wait a bit and check if it stopped
sleep 1

if ps -p $PID > /dev/null 2>&1; then
    echo "Server still running, forcing shutdown..."
    kill -9 $PID
    sleep 1
fi

if ps -p $PID > /dev/null 2>&1; then
    echo "Failed to stop server (PID $PID)"
    exit 1
else
    echo "Server stopped successfully"
fi
