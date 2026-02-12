#!/bin/bash

# Exit on error
set -e

echo "Waiting for PostgreSQL to be ready..."

# Wait for PostgreSQL to be ready using psql
max_retries=30
counter=0

until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; do
    counter=$((counter + 1))
    if [ $counter -gt $max_retries ]; then
        echo "Failed to connect to PostgreSQL after $max_retries attempts"
        exit 1
    fi
    echo "PostgreSQL is unavailable - sleeping (attempt $counter/$max_retries)"
    sleep 2
done

echo "PostgreSQL is up - executing migrations"

# Check for multiple heads and merge if necessary
HEAD_COUNT=$(alembic heads 2>&1 | grep -c "^[a-f0-9]")
if [ "$HEAD_COUNT" -gt 1 ]; then
    echo "Multiple heads detected, creating merge migration..."
    alembic merge -m "auto_merge_heads" heads
fi

# Run database migrations
alembic upgrade head

echo "Migrations completed - seeding database"

# Set PYTHONPATH and run database seeding
export PYTHONPATH=/app:$PYTHONPATH
python -m app.db_seed

echo "Database seeding completed - starting application"

# Switch to appuser and execute the main container command
exec gosu appuser "$@"
