#!/bin/bash
set -e

echo "==> Waiting for PostgreSQL..."
ATTEMPT=0
MAX_ATTEMPTS=30
until pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" > /dev/null 2>&1; do
    ATTEMPT=$((ATTEMPT + 1))
    if [ "$ATTEMPT" -gt "$MAX_ATTEMPTS" ]; then
        echo "==> PostgreSQL not ready after $MAX_ATTEMPTS attempts. Exiting."
        exit 1
    fi
    echo "==> Waiting for PostgreSQL ($ATTEMPT/$MAX_ATTEMPTS)..."
    sleep 2
done
echo "==> PostgreSQL is ready."

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Starting uvicorn (production)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
