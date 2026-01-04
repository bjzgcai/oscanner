#!/bin/bash
# Quick start script for Engineer Skill Evaluator

echo "========================================"
echo "Engineer Skill Evaluator - Quick Start"
echo "========================================"
echo ""

# Check if .env.local exists
if [ ! -f .env.local ]; then
    echo "⚠️  Warning: .env.local not found"
    echo "   Create .env.local with your OPEN_ROUTER_KEY"
    echo ""
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.deps_installed" ]; then
    echo "📥 Installing dependencies..."
    pip install -q fastapi uvicorn python-dotenv requests anthropic
    touch venv/.deps_installed
fi

# Create necessary directories
mkdir -p cache evaluations/cache data

# Start the server
echo ""
echo "🚀 Starting server..."
echo "   Open dashboard.html in your browser"
echo ""
python server.py
