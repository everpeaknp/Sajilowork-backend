#!/bin/bash

# Exit on error
set -o errexit
set -o pipefail
set -o nounset

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo "Running database migrations..."
    python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

if [ "${START_SERVER:-1}" = "1" ]; then
    echo "Starting Daphne server..."
    exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
fi
