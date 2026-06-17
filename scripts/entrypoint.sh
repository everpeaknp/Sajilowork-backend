#!/bin/bash

# Exit on error
set -o errexit
set -o pipefail
set -o nounset

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Creating superuser if it doesn't exist..."
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
"

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Daphne server..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
