#!/bin/bash
# Start FastAPI server (port configured in .env.local)
cd "$(dirname "$0")/evaluator"
source venv/bin/activate

# Load environment variables from .env.local
if [ -f .env.local ]; then
  export $(cat .env.local | grep -v '^#' | xargs)
fi

# Use PORT from environment, default to 8000 if not set
PORT=${PORT:-8000}
echo "Starting evaluator server on port ${PORT}..."
python server.py
