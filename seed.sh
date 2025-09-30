#!/bin/bash

# Database Seeding Script

echo "🌱 Seeding database..."
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    exit 1
fi

# Check if PostgreSQL is running
if ! docker ps | grep -q onedocs-auth-db; then
    echo "❌ PostgreSQL container not running!"
    echo "Please run: docker-compose up -d"
    exit 1
fi

# Run seed script
source venv/bin/activate && python app/db_seed.py

echo ""
echo "✅ Database seeding completed!"