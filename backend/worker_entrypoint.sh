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
# Default concurrency to 2 to avoid OOM with heavy ML models
CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-2}

if [ "$DEBUG" = "True" ]; then
    echo "Starting Celery worker in debug mode on port ${CELERY_DEBUG_PORT:-8004} with concurrency ${CELERY_CONCURRENCY}..."
    python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:${CELERY_DEBUG_PORT:-8004} -m celery -A diavgeia_project worker -l INFO --concurrency=${CELERY_CONCURRENCY}
else
    echo "Starting Celery worker in production mode with concurrency ${CELERY_CONCURRENCY}..."
    celery -A diavgeia_project worker -l INFO --concurrency=${CELERY_CONCURRENCY}
fi