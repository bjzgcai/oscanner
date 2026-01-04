#!/bin/bash

echo "🎭 Ink & Memory - Testing Simplified Version"
echo "============================================"
echo ""
echo "Choose version to test:"
echo "1) Original (complex) - TipTap, stateful backend"
echo "2) Simplified - Clean energy model, stateless backend"
echo ""
read -p "Enter choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    echo "Starting ORIGINAL version..."

    # Kill any existing backend
    pkill -f "python.*server.py" 2>/dev/null

    # Start original backend
    cd backend
    source .venv/bin/activate
    OPENAI_API_KEY=sk-yz0JLc7sGbCHnwam70Bc9e29Dc684bAe904102C95dF32fB1 \
    OPENAI_BASE_URL=https://api.dou.chat/v1 \
    python server.py &
    BACKEND_PID=$!

    cd ../frontend
    echo ""
    echo "✅ Backend started (PID: $BACKEND_PID)"
    echo "✅ Starting frontend..."
    echo ""
    echo "📌 Open: http://localhost:5173/ink-and-memory/"
    echo "   (Original version with TipTap editor)"
    echo ""
    echo "Press Ctrl+C to stop both frontend and backend"

    # Start frontend (this will block)
    npm run dev

    # When frontend is stopped, kill backend too
    kill $BACKEND_PID 2>/dev/null

elif [ "$choice" = "2" ]; then
    echo "Starting SIMPLIFIED version..."

    # Kill any existing backend
    pkill -f "python.*server" 2>/dev/null

    # Start simplified backend
    cd backend
    source .venv/bin/activate
    OPENAI_API_KEY=sk-yz0JLc7sGbCHnwam70Bc9e29Dc684bAe904102C95dF32fB1 \
    OPENAI_BASE_URL=https://api.dou.chat/v1 \
    python server_simple.py &
    BACKEND_PID=$!

    cd ../frontend
    echo ""
    echo "✅ Backend started (PID: $BACKEND_PID)"
    echo "✅ Starting frontend..."
    echo ""
    echo "📌 Open: http://localhost:5173/ink-and-memory/#simple"
    echo "   (Simplified version with clean energy model)"
    echo ""
    echo "Key differences:"
    echo "- Simple textarea instead of TipTap"
    echo "- Trace-based energy tracking"
    echo "- Stateless backend"
    echo "- 55% less code!"
    echo ""
    echo "Press Ctrl+C to stop both frontend and backend"

    # Start frontend (this will block)
    npm run dev

    # When frontend is stopped, kill backend too
    kill $BACKEND_PID 2>/dev/null

else
    echo "Invalid choice. Please run again and select 1 or 2."
    exit 1
fi