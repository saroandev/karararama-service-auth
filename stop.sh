#!/bin/bash

# OneDocs Auth Service Stop Script

echo "🛑 Stopping OneDocs Auth Service..."
echo ""

# Stop FastAPI (if running in background)
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    echo "🔴 Stopping FastAPI server..."
    pkill -f "uvicorn app.main:app"
    echo "✅ FastAPI server stopped"
else
    echo "⚠️  FastAPI server not running"
fi

# Stop Docker containers
echo ""
echo "🐳 Stopping Docker containers..."
docker-compose down

echo ""
echo "✅ All services stopped"