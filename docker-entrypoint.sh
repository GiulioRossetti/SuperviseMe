#!/bin/bash
set -e

echo "SuperviseMe Container Initialization"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h ${PG_HOST:-postgres} -p ${PG_PORT:-5432} -U ${PG_USER:-superviseme_user}; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is ready!"

# Initialize database if needed
echo "Checking database initialization..."
cd /app

# Create database and schema if it doesn't exist (handled by PostgreSQL init scripts)
# Run database seeding
if [ "${SKIP_DB_SEED}" != "true" ]; then
    echo "Running database seeding..."
    python seed_database.py
else
    echo "Skipping database seeding (SKIP_DB_SEED=true)"
fi

echo "Initialization complete!"

# Start the application
exec "$@"