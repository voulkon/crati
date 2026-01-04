# Reliable Task Tracking Guide

## Problem: Flower Shows RECEIVED but Task Never Executes

Flower uses **Celery Events** which can get out of sync with reality. A task showing "RECEIVED" in Flower doesn't mean it's actually stuck.

## Three Sources of Truth (in order of reliability):

### 1. Celery Worker State (MOST RELIABLE)
```bash
# Check if worker actually has the task
docker exec diavgeia_worker celery -A diavgeia_project inspect reserved

# Check if worker is executing the task  
docker exec diavgeia_worker celery -A diavgeia_project inspect active
```

**If both are empty**: Task is NOT in the worker, regardless of what Flower says.

### 2. Result Backend (django-db)
```bash
docker exec diavgeia_backend python manage.py shell -c "
from django_celery_results.models import TaskResult
from django.utils import timezone

# Check specific task
task = TaskResult.objects.filter(task_id='<TASK_ID>').first()
if task:
    age = (timezone.now() - task.date_created).total_seconds() / 60
    print(f'Status: {task.status}, Age: {age:.1f} minutes')
else:
    print('Task not found in result backend')
"
```

**If not found**: Task was never received by worker OR already completed and cleaned up.

### 3. File System (for pickle-based tasks)
```bash
# Check if pickle file exists
docker exec diavgeia_worker ls -lh /code/logs/pickles/chunk_*.pkl

# Check completed pickles
docker exec diavgeia_worker ls -lh /code/logs/pickles/completed/chunk_*.pkl
```

**If file exists in pickles/ (not in completed/)**: Task was dispatched but never processed!

### 4. Flower UI (LEAST RELIABLE)
Flower tracks tasks via event messages. If events are lost/delayed, Flower shows stale state.

**Trust Celery inspect commands, NOT Flower UI**.

## Complete Diagnostic for "Stuck" Task

```bash
TASK_ID="your-task-id-here"

echo "=== Celery Worker State ==="
docker exec diavgeia_worker celery -A diavgeia_project inspect reserved | grep -A 10 "$TASK_ID" || echo "Not in reserved queue"
docker exec diavgeia_worker celery -A diavgeia_project inspect active | grep -A 10 "$TASK_ID" || echo "Not actively executing"

echo "\n=== Result Backend ==="
docker exec diavgeia_backend python manage.py shell -c "
from django_celery_results.models import TaskResult
task = TaskResult.objects.filter(task_id='$TASK_ID').first()
print(f'Status: {task.status}, Created: {task.date_created}' if task else 'NOT FOUND')
"

echo "\n=== Conclusion ==="
echo "If all three show nothing, task is either:"
echo "  1. Completed (check Flower history or logs)"
echo "  2. Lost/rejected by RabbitMQ"
echo "  3. Never actually dispatched despite Flower showing it"
```

## Common Scenarios

### Scenario: Task Lost Due to Countdown/ETA

**Symptoms:**
- Flower shows RECEIVED with ETA in the past
- `celery inspect reserved` is empty
- Result backend has no record
- Pickle file still exists (for store_decisions_from_pickle tasks)

**Root Cause:**
Tasks with `countdown` are scheduled via RabbitMQ's delayed message exchange. If:
- Worker restarts before ETA
- RabbitMQ restarts before ETA
- Message expires due to TTL
- Queue is purged

The task is lost permanently.

**Solution:**
1. Detect orphaned pickle files
2. Resubmit them without countdown

**Recovery Script:**
```bash
cd /code
python manage.py shell < recover_orphaned_pickles.py
```

### Scenario: Flower Stale State

**Symptoms:**
- Flower shows RECEIVED
- `celery inspect` shows nothing
- Result backend shows SUCCESS or not found
- Logs show task completed

**Root Cause:**
Flower didn't receive the task-succeeded event (worker event broadcasting might be disabled or Flower wasn't connected).

**Solution:**
Ignore Flower. Task actually completed successfully.

### Scenario: Actual Worker Hang

**Symptoms:**
- Flower shows STARTED for > 10 minutes
- `celery inspect active` shows the same task
- Worker logs show no progress
- Database locks detected

**Root Cause:**
Task is genuinely hung (database deadlock, infinite loop, external API timeout).

**Solution:**
1. Kill the worker process
2. Investigate task code for blocking operations
3. Add timeouts to database queries and external calls

## Prevention: Don't Use Countdown for Critical Tasks

The `countdown` parameter is unreliable for critical tasks because:
- Messages can be lost during restarts
- No automatic retry if message expires
- Creates "orphaned" work that was never processed

**Instead:**
1. Use immediate dispatch
2. Implement delays INSIDE the task (time.sleep)
3. Or use Celery Beat for scheduled execution

**Example - BAD:**
```python
task.apply_async(args=[data], countdown=30)  # Can be lost!
```

**Example - GOOD:**
```python
@shared_task
def my_task(data, delay_seconds=0):
    if delay_seconds > 0:
        time.sleep(delay_seconds)  # Delay inside task, guaranteed to run
    # ... do work
```

## Monitoring Script

Save as `check_task_state.sh`:
```bash
#!/bin/bash
TASK_ID=$1

if [ -z "$TASK_ID" ]; then
    echo "Usage: $0 <task_id>"
    exit 1
fi

echo "Checking task: $TASK_ID"
echo ""

docker exec diavgeia_worker celery -A diavgeia_project inspect reserved | grep -q "$TASK_ID" && echo "✓ In reserved queue" || echo "✗ NOT in reserved queue"
docker exec diavgeia_worker celery -A diavgeia_project inspect active | grep -q "$TASK_ID" && echo "✓ Actively executing" || echo "✗ NOT executing"

STATUS=$(docker exec diavgeia_backend python manage.py shell -c "from django_celery_results.models import TaskResult; t = TaskResult.objects.filter(task_id='$TASK_ID').first(); print(t.status if t else 'NOT_FOUND')")
echo "Database status: $STATUS"
```
