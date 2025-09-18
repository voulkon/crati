import os
from celery import Celery
from diavgeia_project.otel_setup import setup_tracing

# Instrument Celery
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diavgeia_project.settings")

# Initialize OpenTelemetry for Celery
tracer = setup_tracing(service_name="diavgeia-celery")

app = Celery("diavgeia_project")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Instrument Celery after creating the app
CeleryInstrumentor().instrument(app=app)

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure result backend to store task results
app.conf.update(
    result_backend="django-db",  # Store results in Django's database
    task_track_started=True,  # Track when tasks are started
    result_expires=86400,  # Results expire after 1 day (in seconds)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    worker_prefetch_multiplier=1,  # Don't let workers grab too many tasks at once
)

app.conf.beat_schedule = {
    # "persist-analytics-daily": {
    #     "task": "api.tasks.persist_analytics_task",
    #     "schedule": crontab(hour=0, minute=5),  # Run at 00:05 every day
    # },
    # 'import-ministry-decisions-daily': {
    #     'task': 'core.tasks.import_ministry_decisions_task',
    #     'schedule': crontab(hour=3, minute=0),  # Run at 3am daily
    #     'args': ('ministries', None),
    # },
    # 'process-new-documents': {
    #     'task': 'core.tasks.process_documents_task',
    #     'schedule': crontab(hour=5, minute=0),  # Run at 5am daily
    #     'kwargs': {'from_date': 'yesterday', 'limit': 500, 'unprocessed_only': True},
    # },
    # # Add a weekly task to catch any missed documents
    # 'process-missed-documents-weekly': {
    #     'task': 'core.tasks.process_documents_task', 
    #     'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Sunday at 2am
    #     'kwargs': {'limit': 1000, 'unprocessed_only': True},  # No date filter = all unprocessed
    # },
    # 'reset-usage-counters-monthly': {
    #     'task': 'users.tasks.reset_monthly_usage',
    #     'schedule': crontab(0, 0, day_of_month='1'),  # First day of month
    # },

    # 'daily-decisions-sync': {
    #     'task': 'core.tasks.daily_decisions_sync_task',
    #     'schedule': crontab(hour=2, minute=30),  # Run at 2:30 AM daily
    #     'kwargs': {'incremental': True},
    # },
    
    # Optional: Half-hourly incremental sync during business hours
    # 'incremental-decisions-sync': {
    #     'task': 'core.tasks.daily_decisions_sync_task',
    #     'schedule': crontab(minute='*/30', hour='8-18'),  # Every 30 min, 8AM-6PM
    #     'kwargs': {'incremental': True},
    # },
    # 'fetch-company-data-hourly': {
    #     'task': 'core.tasks.process_entities_needing_company_data',
    #     'schedule': crontab(minute=0),  # Every hour
    #     'kwargs': {'limit': 20}  # Process 20 entities per hour
    # },
    # 'verify-entity-extraction-daily': {
    #     'task': 'core.tasks.verify_entity_extraction_status',
    #     'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    # },


}
