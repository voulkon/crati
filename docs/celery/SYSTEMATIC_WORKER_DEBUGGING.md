# Systematic Worker Debugging Guide

## When to Use This Guide
When you see tasks in Flower showing as "RECEIVED" but not progressing, or workers appear to be idle despite tasks in the queue.

## Step 1: Run the Diagnostic Script

```bash
cd backend
./diagnose_worker_hang.sh
```

This generates a timestamped log file with all diagnostic information.

## Step 2: Interpret the Results

### Scenario A: Tasks in Queue, Worker Not Fetching
**Symptoms:**
- RabbitMQ shows `messages_ready > 0`
- Celery `inspect active` is empty
- Celery `inspect reserved` is empty

**Diagnosis:**
- Check `rabbitmqctl list_consumers` output
- If `prefetch_count = 0`: Worker is configured to fetch unlimited messages (rare, usually means rate_limit decorator is interfering)
- If consumer missing entirely: Worker not connected to RabbitMQ

**Actions:**
1. Check worker logs for connection errors
2. Check if any tasks have `rate_limit` decorator (this can cause prefetch_count=0)
3. Restart worker: `docker-compose restart diavgeia_worker`

### Scenario B: Tasks "Reserved" but Not Executing
**Symptoms:**
- Celery `inspect reserved` shows tasks
- Celery `inspect active` is empty
- Tasks have been reserved for > 5 minutes

**Diagnosis:**
- Tasks are fetched but worker won't start them
- Usually indicates worker pool exhaustion or deadlock

**Actions:**
1. Check `celery inspect stats` for pool state
2. Check worker logs for errors/exceptions
3. Check database for locks: look at diagnostic script output section 7
4. Nuclear option: `docker-compose restart diavgeia_worker`

### Scenario C: Tasks "Active" for Too Long
**Symptoms:**
- Celery `inspect active` shows tasks
- Tasks have been running for > 10 minutes (or longer than expected)

**Diagnosis:**
- Task is genuinely slow OR task is hung

**Actions:**
1. Check worker logs for task progress
2. Check database for locks (section 7 of diagnostic output)
3. For specific task, check its implementation for:
   - Database operations without timeout
   - External API calls without timeout
   - Signal handlers causing race conditions

### Scenario D: Stale State in Result Backend
**Symptoms:**
- Flower shows task in "RECEIVED" or "STARTED"
- Diagnostic script section 6 shows `age_minutes > 10`
- Celery `inspect` commands show NO such task

**Diagnosis:**
- Zombie task from previous worker crash/restart
- Result backend (django-db) has stale data

**Actions:**
1. Clean up stale tasks:
```sql
docker exec diavgeia_db psql -U diavgeia -d diavgeia -c "
UPDATE django_celery_results_taskresult 
SET status='FAILURE', result='Stale task from worker crash' 
WHERE status IN ('RECEIVED', 'STARTED') 
AND date_created < NOW() - INTERVAL '10 minutes';
"
```

## Step 3: Root Cause Patterns

### Pattern 1: DateCoverage Race Condition
**How to Detect:**
- Worker logs show: `DateCoverage.MultipleObjectsReturned`
- Multiple workers processing decisions simultaneously

**Status:** FIXED in signals.py (changed to get_or_create)

### Pattern 2: Retry Signature Bug
**How to Detect:**
- Worker logs show: `got multiple values for argument 'pickle_file'`

**Status:** FIXED in tasks_decisions_import.py

### Pattern 3: Rate Limit Prefetch Conflict
**How to Detect:**
- Task has `@shared_task(rate_limit="X/m")` decorator
- `rabbitmqctl list_consumers` shows `prefetch_count = 0`

**Status:** RESOLVED - Remove rate_limit decorators, use internal delays instead

### Pattern 4: Missing Task Delays (Race Condition)
**How to Detect:**
- Multiple chunks dispatched simultaneously
- DateCoverage or other race conditions occur

**Status:** FIXED - Added `countdown` parameter to apply_async

## Step 4: What We Changed (Summary)

### Configuration Changes:
1. **celery.py**: Set `worker_prefetch_multiplier=1` in app.conf.update (SINGLE SOURCE OF TRUTH)
2. **Removed redundant prefetch settings** from Django settings and CLI flags
3. **Removed `rate_limit` decorators** from tasks (use manual delays instead)

### Code Fixes:
1. **signals.py**: Changed `update_or_create()` to `get_or_create()` with duplicate cleanup
2. **tasks_decisions_import.py**: 
   - Fixed retry signature (removed duplicate pickle_file)
   - Added countdown delays between chunk tasks
   - Fixed pickle path bug
   - Added file existence checks

### Known Issues That Are NOT the Problem:
- ❌ Signal handlers (disabled them, still hung)
- ❌ `task_track_started` (disabled it, still hung)
- ❌ Database locks (checked, none found during hangs)
- ❌ Prefetch configuration (logs show it's working: "prefetch_count->3")

## Step 5: Configuration State (Current)

**Single Source of Truth for Prefetch:**
```python
# backend/diavgeia_project/celery.py
app.conf.update(
    worker_prefetch_multiplier=1,  # Fetch 1 task per worker process
)
```

**NOT set in:**
- ❌ Django settings (removed CELERY_WORKER_PREFETCH_MULTIPLIER)
- ❌ CLI flags (removed --prefetch-multiplier)

**Why:** Multiple configuration sources caused confusion. One place = one truth.

## Quick Reference Commands

```bash
# Check RabbitMQ queue state
docker exec diavgeia_rabbitmq rabbitmqctl list_queues name messages messages_ready messages_unacknowledged

# Check RabbitMQ consumers and prefetch
docker exec diavgeia_rabbitmq rabbitmqctl list_consumers

# Check Celery active tasks
docker exec diavgeia_worker celery -A diavgeia_project inspect active

# Check Celery reserved tasks
docker exec diavgeia_worker celery -A diavgeia_project inspect reserved

# Check worker stats
docker exec diavgeia_worker celery -A diavgeia_project inspect stats

# Clean up zombie tasks
docker exec diavgeia_db psql -U diavgeia -d diavgeia -c "
UPDATE django_celery_results_taskresult 
SET status='FAILURE', result='Cleaned up zombie task' 
WHERE status IN ('RECEIVED', 'STARTED') 
AND date_created < NOW() - INTERVAL '10 minutes';
"

# Restart worker (last resort)
docker-compose restart diavgeia_worker
```

## Next Time This Happens

1. **DO NOT panic or randomly change configuration**
2. **RUN** `./diagnose_worker_hang.sh`
3. **COMPARE** output to scenarios above
4. **ACT** based on specific diagnosis, not guesses
5. **DOCUMENT** if you find a new pattern not listed here
