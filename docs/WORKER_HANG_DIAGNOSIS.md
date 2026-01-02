# Worker Hang Diagnostic Report
**Date:** 2026-01-03  
**Issue:** Celery worker stops processing tasks, goes silent with 48+ messages stuck in queue

## Evidence Collected

### 1. Worker is Alive but Idle
```bash
$ docker ps | grep worker
79ead0719e60   diavgeia-worker   Up 9 minutes
```
Worker container is running, not crashed.

### 2. RabbitMQ Queue Status
```bash
$ docker exec diavgeia_rabbitmq rabbitmqctl list_queues name messages consumers messages_ready messages_unacknowledged
celery  50      1       49      1
```
**Key Finding:** 
- 50 messages total
- 49 ready to process
- **1 unacknowledged** (worker picked it up but hasn't completed or failed it)
- Worker is stuck processing that 1 message

### 3. Worker Logs Show Task Received But Never Started
```
INFO 2026-01-03 13:47:57,997 Task core.tasks.tasks_entities.fetch_company_data_for_single_afm[461b4e15...] received
{"message": "Task started: ...461b4e15...", "timestamp": "2026-01-03 13:47:58.099"}
...
INFO 2026-01-03 13:47:59,012 Task ...461b4e15... succeeded

INFO 2026-01-03 13:47:58,103 Task core.tasks.tasks_entities.fetch_company_data_for_single_afm[db289773...] received
[NO "Task started" LOG FOR db289773]
[SILENCE FOR 10+ MINUTES]
```

**Key Finding:** Task `db289773` (AFM `094004190`) was RECEIVED but never got the "Task started" log entry.

### 4. No Active Database Queries
```bash
$ docker exec diavgeia_db psql -U local_user -d local_diavgia -c "SELECT pid, state, wait_event, query FROM pg_stat_activity WHERE state != 'idle'"
(0 rows)
```
**Key Finding:** Worker is NOT stuck on a database query.

### 5. No Database Locks
```bash
$ docker exec diavgeia_db psql -U local_user -d local_diavgia -c "SELECT locktype, relation, mode, granted FROM pg_locks WHERE NOT granted"
(0 rows)
```
**Key Finding:** No deadlocks or ungranted locks.

### 6. Database Connections Are Healthy
```bash
$ docker exec diavgeia_worker python -c "...test DB connection..."
✓ Test query succeeded: (1,)
```
**Key Finding:** Database connectivity works fine.

### 7. Writing TaskResult Works Fine
```bash
$ docker exec diavgeia_worker python -c "...create TaskResult..."
✓ Created in 0.007s
```
**Key Finding:** `task_track_started=True` functionality (writing to `django_celery_results_taskresult`) works instantly when tested.

### 8. No Blocking DB Operations
```bash
$ docker exec diavgeia_db psql -U local_user -d local_diavgia -c "SELECT pg_blocking_pids(pid), pid, state, query FROM pg_stat_activity WHERE state != 'idle'"
(0 rows)
```
**Key Finding:** No processes blocking each other.

## Timeline of the Hang

1. **13:47:57** - Worker becomes ready, receives task `461b4e15`
2. **13:47:58.099** - Task `461b4e15` starts processing (log entry present)
3. **13:47:58.103** - Worker receives task `db289773` (prefetched into worker's queue)
4. **13:47:59.012** - Task `461b4e15` **succeeds**
5. **13:47:59+** - Worker should start task `db289773` but **NEVER LOGS "Task started"**
6. **13:48:02** - Last log entry: "Events of group {task} enabled by remote" (Flower monitoring)
7. **13:48+** - **Complete silence, worker processes nothing for 10+ minutes**

## What We Can Rule Out

❌ **Database connection failure** - Tested successfully  
❌ **Database deadlock** - No locks present  
❌ **Task code hanging** - Never reaches task code (no "Processing AFM" log)  
❌ **Worker crashed** - Container still running, `celery inspect` responds  
❌ **RabbitMQ connection loss** - Queue shows worker as active consumer  

## What We Know vs What We Don't Know

### What We Know for Certain:
- Worker hangs **between receiving the task and starting it**
- This is during Celery's internal task initialization, which includes:
  1. Task message deserialization
  2. `task_track_started=True` writes task status to DB (if enabled)
  3. Signal handlers execute (`task_prerun.connect`)
  4. Task execution begins
- The stuck task type is `fetch_company_data_for_single_afm`
- When we manually test DB operations, they work fine
- The worker process is alive but silent

### What We Don't Know:
- **WHERE exactly in the code** the worker is stuck (which line, which function)
- **WHAT operation** it's blocking on (file I/O, network, lock, something else)
- **WHY** it only happens sometimes and not during our manual tests
- **WHETHER** commit 738ed16 is actually related (it modified a different task type)
- **WHETHER** `task_track_started=True` is the culprit (DB writes work when tested)

## Speculative Theories (Unproven)

### Theory 1: Commit 738ed16 Causes Issue
- **Speculation:** Added `AFMEntity.objects.filter()` early in task execution
- **Problem:** The stuck task (`fetch_company_data_for_single_afm`) was NOT modified by this commit
- **Evidence:** None, just timing correlation

### Theory 2: task_track_started=True Causes Issue  
- **Speculation:** DB write before task starts could cause deadlock/hang
- **Problem:** DB writes work instantly when tested (0.007s)
- **Evidence:** None, just suspicion

## What We Need to Actually Diagnose This

### Option 1: See What the Worker Is Actually Doing
```bash
# Get worker process ID
docker exec diavgeia_celery_worker ps aux

# Attach strace to see system calls (file I/O, network, locks)
docker exec diavgeia_celery_worker strace -p <PID>
```
This will show if it's stuck on a read(), write(), select(), futex(), etc.

### Option 2: Get Python Stack Trace
```bash
# Make Python dump stack trace of all threads
docker exec diavgeia_celery_worker kill -USR1 <PID>

# Or attach py-spy
docker exec diavgeia_celery_worker py-spy dump --pid <PID>
```
This will show the exact Python code line where it's stuck.

### Option 3: Trial and Error Testing
Since we can't diagnose the root cause with available evidence:
1. Try reverting commit 738ed16 → test → observe
2. Try disabling `task_track_started=True` → test → observe
3. Try both → test → observe

## Current Status

**We are at diagnostic point 0.**  
We have ruled out many things, but we have not identified the actual cause. We have two unproven theories but no hard evidence supporting either.

Further diagnosis requires either:
- Attaching debugging tools to the stuck worker process
- Empirical trial-and-error testing of configuration changes
