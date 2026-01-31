#!/bin/bash

# Quick start script for GitHub Data Collector API Server

echo "=================================================="
echo "GitHub Data Collector API Server - Quick Start"
echo "=================================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Use explicit venv paths for reliability
VENV_PYTHON="venv/bin/python"
VENV_PIP="venv/bin/pip"

# Install/update dependencies
echo "Checking dependencies..."
if [ ! -f "venv/.deps_installed" ] || [ "requirements.txt" -nt "venv/.deps_installed" ]; then
    echo "Installing dependencies..."
    $VENV_PIP install -q -r requirements.txt
    # Create marker file to track installation
    touch venv/.deps_installed
else
    echo "Dependencies already installed"
fi

# Set GitHub token if provided
if [ -n "$1" ]; then
    export GITHUB_TOKEN="$1"
    echo "GitHub token configured"
fi

# Set port if provided as second argument, otherwise default to 8000
if [ -n "$2" ]; then
    export PORT="$2"
fi

# Start the server
echo ""
echo "=================================================="
echo "Starting server..."
echo "Note: If port is in use, it will auto-select the next available port"
echo "=================================================="
echo ""

$VENV_PYTHON server.py
