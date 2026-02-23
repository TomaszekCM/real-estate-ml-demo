#!/bin/bash
set -e

echo "Starting Django application..."

# Wait for database to be ready
echo "Waiting for database to be ready..."
until python manage.py dbshell --command="SELECT 1;" > /dev/null 2>&1; do
    echo "Database is unavailable - sleeping"
    sleep 1
done
echo "Database is ready!"

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn \
    --workers $GUNICORN_WORKERS \
    --bind $GUNICORN_BIND \
    --worker-class sync \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 30 \
    --keep-alive 2 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    $GUNICORN_MODULE