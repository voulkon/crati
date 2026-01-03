"""
Celery configuration.

Contains all Celery-related settings including broker, backend, and worker resource limits.
"""

import os
import sys

# Celery settings
CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//"
)
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXPIRES = 86400  # 1 day in seconds

# Worker Resource Limits
CELERY_WORKER_MAX_TASKS_PER_CHILD = int(os.environ.get("CELERY_WORKER_MAX_TASKS_PER_CHILD", 100))  # Restart worker process after 100 tasks to release memory
# Increased from 5 to amortize the heavy Docling initialization cost (5.4s per worker)
# This means the 5.4s overhead is spread across 100 documents instead of 5
CELERY_WORKER_MAX_MEMORY_PER_CHILD = int(os.environ.get("CELERY_WORKER_MAX_MEMORY_PER_CHILD", 2500000))  # 2.5GB (in KB) - Restart if memory exceeds this
# Increased from 1GB to accommodate Docling's memory requirements (~1.5-2GB peak with concurrency=2)

# Log the configuration on startup (only in worker processes)
if 'celery' in os.environ.get('_', '').lower() or 'celery' in ' '.join(sys.argv).lower():
    print("=" * 50, file=sys.stderr)
    print("📊 Django Celery Settings Loaded:", file=sys.stderr)
    print(f"  CELERY_WORKER_MAX_TASKS_PER_CHILD: {CELERY_WORKER_MAX_TASKS_PER_CHILD}", file=sys.stderr)
    print(f"  CELERY_WORKER_MAX_MEMORY_PER_CHILD: {CELERY_WORKER_MAX_MEMORY_PER_CHILD} KB (~{CELERY_WORKER_MAX_MEMORY_PER_CHILD//1024//1024}GB)", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
