#!/bin/bash
# Start the Repository Runner server

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting Repository Runner Server..."
echo "Project root: $PROJECT_ROOT"

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/evaluator/venv" ]; then
    echo "Error: Virtual environment not found at $PROJECT_ROOT/evaluator/venv"
    echo "Please create a virtual environment first:"
    echo "  cd $PROJECT_ROOT/evaluator && python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
source "$PROJECT_ROOT/evaluator/venv/bin/activate"

# Install repos_runner dependencies if needed
echo "Checking dependencies..."
pip install -q -r "$PROJECT_ROOT/repos_runner/requirements.txt"

# Set working directory to project root
cd "$PROJECT_ROOT"

# Set default port if not specified
export RUNNER_PORT=${RUNNER_PORT:-8001}

# Run the server
echo "Starting server on port $RUNNER_PORT..."
python -m repos_runner.server
