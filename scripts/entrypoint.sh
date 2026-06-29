#!/bin/bash

# Exit on error
set -o errexit
set -o pipefail
set -o nounset

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo "Running database migrations..."
    python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput --clear
    if [ ! -d staticfiles ] || [ "$(find staticfiles -type f 2>/dev/null | wc -l | tr -d ' ')" -lt 50 ]; then
        echo "ERROR: collectstatic did not populate staticfiles/ — admin CSS will be missing."
        exit 1
    fi
    echo "Static files ready ($(find staticfiles -type f | wc -l | tr -d ' ') files)."
fi

if [ "${START_SERVER:-1}" = "1" ]; then
    echo "Starting Daphne server..."
    exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
fi
