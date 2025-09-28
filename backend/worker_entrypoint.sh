#!/bin/sh

# Wait for database
echo "Waiting for database..."
python manage.py wait_for_db

# Wait for Loki
echo "Waiting for Loki..."
python manage.py wait_for_loki

# Wait for Redis/RabbitMQ
echo "Waiting for broker..."
sleep 5

# Run celery worker with or without debugging
if [ "$DEBUG" = "True" ]; then
    echo "Starting Celery worker in debug mode on port ${CELERY_DEBUG_PORT:-8004}..."
    python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:${CELERY_DEBUG_PORT:-8004} -m celery -A diavgeia_project worker -l INFO
else
    echo "Starting Celery worker in production mode..."
    celery -A diavgeia_project worker -l INFO
fi