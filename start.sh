#!/bin/bash

# OneDocs Auth Service Starter Script

echo "🚀 Starting OneDocs Auth Service..."
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if PostgreSQL is running
echo "🔍 Checking PostgreSQL..."
if ! docker ps | grep -q onedocs-auth-db; then
    echo "⚠️  PostgreSQL container not running. Starting..."
    docker-compose up -d
    echo "⏳ Waiting for PostgreSQL to be ready..."
    sleep 3
else
    echo "✅ PostgreSQL is running"
fi

# Activate virtual environment and start FastAPI
echo ""
echo "🌐 Starting FastAPI server on http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo "📖 ReDoc: http://localhost:8000/redoc"
echo ""
echo "Press CTRL+C to stop the server"
echo ""

source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000