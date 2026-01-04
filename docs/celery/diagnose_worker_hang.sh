#!/bin/bash
# Worker Hang Diagnostic Script
# Run this when you suspect workers are stuck/hung
# Usage: ./diagnose_worker_hang.sh

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOGFILE="worker_diagnosis_${TIMESTAMP}.log"

echo "==================================================================" | tee -a $LOGFILE
echo "Worker Hang Diagnostic - $(date)" | tee -a $LOGFILE
echo "==================================================================" | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# 1. Check RabbitMQ Queue State
echo "1. RabbitMQ Queue State:" | tee -a $LOGFILE
echo "-------------------------" | tee -a $LOGFILE
docker exec diavgeia_rabbitmq rabbitmqctl list_queues name messages consumers messages_ready messages_unacknowledged 2>&1 | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# 2. Check RabbitMQ Consumer Configuration
echo "2. RabbitMQ Consumer Configuration (CHECK PREFETCH_COUNT!):" | tee -a $LOGFILE
echo "-----------------------------------------------------------" | tee -a $LOGFILE
docker exec diavgeia_rabbitmq rabbitmqctl list_consumers 2>&1 | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# 3. Check Celery Active Tasks (Currently Executing)
echo "3. Celery Active Tasks (currently executing):" | tee -a $LOGFILE
echo "---------------------------------------------" | tee -a $LOGFILE
docker exec diavgeia_worker celery -A diavgeia_project inspect active 2>&1 | grep -A 100 "^->" | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# 4. Check Celery Reserved Tasks (Fetched but not started)
echo "4. Celery Reserved Tasks (fetched but not started):" | tee -a $LOGFILE
echo "---------------------------------------------------" | tee -a $LOGFILE
docker exec diavgeia_worker celery -A diavgeia_project inspect reserved 2>&1 | grep -A 100 "^->" | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# 5. Check Celery Worker Stats
echo "5. Celery Worker Stats (prefetch, pool state):" | tee -a $LOGFILE
echo "----------------------------------------------" | tee -a $LOGFILE
docker exec diavgeia_worker celery -A diavgeia_project inspect stats 2>&1 | grep -E "(prefetch|pool|total)" | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# 6. Check Database Result Backend for Stale States
echo "6. Database Result Backend - Tasks in RECEIVED/STARTED state:" | tee -a $LOGFILE
echo "-------------------------------------------------------------" | tee -a $LOGFILE
docker exec diavgeia_backend python manage.py shell -c "
from django_celery_results.models import TaskResult
from django.utils import timezone

stale_tasks = TaskResult.objects.filter(
    status__in=['RECEIVED', 'STARTED']
).order_by('-date_created')[:20]

print(f\"{'task_id':<40} {'status':<10} {'task_name':<50} {'age_minutes':>12}\")
print('-' * 115)
for task in stale_tasks:
    age_minutes = (timezone.now() - task.date_created).total_seconds() / 60
    task_name_short = (task.task_name[:47] + '...') if task.task_name and len(task.task_name) > 50 else (task.task_name or 'N/A')
    print(f\"{task.task_id:<40} {task.status:<10} {task_name_short:<50} {age_minutes:>12.1f}\")
" 2>&1 | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# 7. Check for Database Locks
echo "7. PostgreSQL Locks:" | tee -a $LOGFILE
echo "--------------------" | tee -a $LOGFILE
docker exec diavgeia_backend python manage.py shell -c "
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute(\"\"\"
        SELECT 
            pid,
            usename,
            application_name,
            state,
            query_start,
            state_change,
            wait_event_type,
            wait_event,
            LEFT(query, 100) as query
        FROM pg_stat_activity 
        WHERE state != 'idle'
          AND pid != pg_backend_pid()
        ORDER BY query_start;
    \"\"\")
    rows = cursor.fetchall()
    if rows:
        print(f'{"pid":<8} {"usename":<12} {"app_name":<20} {"state":<10} {"wait_event":<20}')
        print('-' * 80)
        for row in rows:
            print(f'{row[0]:<8} {row[1]:<12} {row[2]:<20} {row[3]:<10} {str(row[6] or ""):<20}')
    else:
        print('No active queries (no locks)')
" 2>&1 | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# 8. Check Worker Container Health
echo "8. Worker Container Stats:" | tee -a $LOGFILE
echo "--------------------------" | tee -a $LOGFILE
docker stats diavgeia_worker --no-stream 2>&1 | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# 9. Check Recent Worker Logs
echo "9. Recent Worker Logs (last 50 lines):" | tee -a $LOGFILE
echo "---------------------------------------" | tee -a $LOGFILE
docker logs --tail 50 diavgeia_worker 2>&1 | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# Summary & Interpretation
echo "==================================================================" | tee -a $LOGFILE
echo "INTERPRETATION GUIDE" | tee -a $LOGFILE
echo "==================================================================" | tee -a $LOGFILE
echo "" | tee -a $LOGFILE
echo "CHECK #1: RabbitMQ Queue State" | tee -a $LOGFILE
echo "  - messages_ready > 0: Tasks waiting in queue" | tee -a $LOGFILE
echo "  - messages_unacknowledged > 0: Tasks fetched by worker but not acked" | tee -a $LOGFILE
echo "  - If ready > 0 AND active=empty: Worker NOT fetching from queue" | tee -a $LOGFILE
echo "" | tee -a $LOGFILE
echo "CHECK #2: Consumer Configuration" | tee -a $LOGFILE
echo "  - prefetch_count = 0: PROBLEM! Worker will fetch ALL messages" | tee -a $LOGFILE
echo "  - prefetch_count = 1-10: OK, controlled prefetch" | tee -a $LOGFILE
echo "" | tee -a $LOGFILE
echo "CHECK #3 & #4: Active vs Reserved" | tee -a $LOGFILE
echo "  - active > 0: Worker IS executing tasks" | tee -a $LOGFILE
echo "  - reserved > 0: Worker fetched tasks but hasn't started them" | tee -a $LOGFILE
echo "  - Both empty + messages_ready > 0: Worker not fetching!" | tee -a $LOGFILE
echo "" | tee -a $LOGFILE
echo "CHECK #6: Database Result Backend" | tee -a $LOGFILE
echo "  - age_minutes > 10: Likely zombie task from crash/restart" | tee -a $LOGFILE
echo "  - status=RECEIVED but not in Celery reserved: STALE data in DB" | tee -a $LOGFILE
echo "" | tee -a $LOGFILE
echo "==================================================================" | tee -a $LOGFILE
echo "Diagnostic log saved to: $LOGFILE" | tee -a $LOGFILE
echo "==================================================================" | tee -a $LOGFILE
