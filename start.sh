#!/bin/bash
# Auth Service Startup Script

echo "Starting OneDocs Auth Service on port 8001..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
