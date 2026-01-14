import os
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, worker_process_init
from celery.schedules import crontab
from opentelemetry import trace
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from .otel_init import initialize_otel
import diavgeia_project.otel_init as otel_init_module

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diavgeia_project.settings")

# Initial setup for Main Process (Beat, Worker Parent, etc)
# This might not be fork-safe, but we fix it in worker_process_init below
try:
    tracer = initialize_otel("diavgeia-celery")
except Exception as e:
    print(f"⚠️ Failed to initialize OpenTelemetry in main process: {e}")

# Configure Loguru for JSON logging BEFORE any Loguru imports
from diavgeia_project.logging.loguru_config import configure_loguru
configure_loguru()

# Create Celery app
app = Celery("diavgeia_project")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Disable Celery's logging setup to use Django's configuration
from celery.signals import setup_logging

@setup_logging.connect
def config_loggers(*args, **kwargs):
    """Prevent Celery from overriding Django's logging configuration"""
    pass  # Do nothing, let Django handle logging

# Fix for "ValueError: Cannot invoke RPC on closed channel!"
# This ensures each forked worker process gets a FRESH OpenTelemetry exporter
@worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):
    """
    Re-initialize OpenTelemetry in the worker child process.
    This is critical because gRPC channels (used by the OTLP exporter) 
    are not fork-safe and break when inherited from the parent process.
    """
    try:
        # 1. Force reset the global state in otel_init module
        # This makes initialize_otel() create a NEW provider instead of returning the parent's
        otel_init_module._global_initialized = False
        otel_init_module._services_initialized.clear()
        
        # 2. Re-initialize with a fresh gRPC channel
        print("🔄 [Worker Child] Re-initializing OpenTelemetry for fork safety...")
        initialize_otel("diavgeia-celery")
        
        # 3. Ensure instrumentation is active
        CeleryInstrumentor().instrument()
        print("✅ [Worker Child] OpenTelemetry re-initialized successfully")
    except Exception as e:
        print(f"❌ [Worker Child] Failed to re-initialize OpenTelemetry: {e}")

# Modern instrumentation for v0.53b1+
# We call it here for the Main Process
CeleryInstrumentor().instrument(
    tracer_provider=trace.get_tracer_provider(),
    # Optional: Add any specific instrumentation configurations
    # enable_propagators=["tracecontext", "baggage"],
    # disable_span_enrich=False
)

app.autodiscover_tasks()

# Import logging utilities after Django setup
from diavgeia_project.logging.logging_utils import task_logger
import time

# Task execution tracking - DISABLED FOR TESTING HANG ISSUE
# task_start_times = {}

# DISABLED: These signal handlers might be causing the worker hang
# @task_prerun.connect
# def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
#     """Log task start and store start time"""
#     task_start_times[task_id] = time.time()
#     task_logger.log_task_start(sender.name, task_id, args, kwargs)

# @task_postrun.connect  
# def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
#     """Log task completion"""
#     start_time = task_start_times.pop(task_id, time.time())
#     duration_s = time.time() - start_time
#     
#     if state == 'SUCCESS':
#         task_logger.log_task_success(sender.name, task_id, duration_s, retval)
#     # Note: failures are handled by task_failure signal

# @task_failure.connect
# def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
#     """Log task failure"""
#     start_time = task_start_times.pop(task_id, time.time()) 
#     duration_s = time.time() - start_time
#     task_logger.log_task_failure(sender.name, task_id, duration_s, exception)

# Configure result backend to store task results
app.conf.update(
    result_backend="django-db",  # Store results in Django's database
    task_track_started=False,  # Track when task starts (stored in result backend)
    result_expires=86400,  # Results expire after 1 day (in seconds)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    worker_prefetch_multiplier=1,  # Fetch 1 task per worker process (concurrency * 1)
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

    # Health Check Tasks - Keep admin data fresh automatically
    'health-check-recent-decisions': {
        'task': 'core.tasks.health_check_tasks.check_recent_decisions_health',
        'schedule': crontab(minute='0'),  # Every hour
    },
    'refresh-problematic-decisions': {
        'task': 'core.tasks.health_check_tasks.refresh_problematic_decisions', 
        'schedule': crontab(minute='30'),  # Every hour at :30
    },
    'auto-fix-simple-issues': {
        'task': 'core.tasks.health_check_tasks.auto_fix_simple_issues',
        'schedule': crontab(hour='*/6', minute=15),  # Every 6 hours
    },
    'cleanup-old-health-checks': {
        'task': 'core.tasks.health_check_tasks.cleanup_old_health_checks',
        'schedule': crontab(hour=1, minute=0, day_of_week=0),  # Weekly on Sunday at 1 AM
    },

}
