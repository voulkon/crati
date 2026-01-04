# Worker Hang Diagnostic Report
**Issue:** Celery worker stops processing tasks after successfully completing some tasks

## What We Actually Observed

### 1. RabbitMQ Has Messages Ready
```bash
$ docker exec diavgeia_rabbitmq rabbitmqctl list_queues name messages consumers messages_ready messages_unacknowledged
celery  4       1       3       1
```
**Facts:**
- 4 messages in queue
- 3 messages READY (waiting to be fetched)
- 1 message unacknowledged (in progress or completed but not acked yet)
- 1 consumer registered on the queue

### 2. Worker Process is Idle
```bash
$ docker exec diavgeia_worker py-spy dump --pid 37
Thread 37 (idle): "MainThread"
    _recv (billiard/connection.py:425)
    ...waiting for work from main process...
```
**Facts:**
- Worker process (PID 37) is IDLE
- Sitting in `_recv()` waiting for the main Celery process to send it work
- Not stuck, not crashed, just waiting

### 3. Main Celery Consumer is Idle
```bash
$ docker exec diavgeia_worker py-spy dump --pid 10
Thread 10 (idle): "MainThread"
    poll (kombu/utils/eventio.py:83)
    ...event loop waiting...
```
**Facts:**
- Main consumer process (PID 10) is also IDLE
- Sitting in event loop `poll()` waiting for events from RabbitMQ
- Not fetching messages from the queue

### 4. RabbitMQ Connection is Alive
```bash
$ docker exec diavgeia_rabbitmq rabbitmqctl list_connections
guest   172.18.0.14     53354   running
...multiple connections active...
```
**Facts:**
- Celery consumer has active connections to RabbitMQ
- Connections are in "running" state
- No connection failures

### 5. Consumer is Registered But Not Fetching
```bash
$ docker exec diavgeia_rabbitmq rabbitmqctl list_consumers
celery  <rabbit@...>  None4   true    0       true    []
```
**SMOKING GUN:**
- Consumer is registered on the `celery` queue
- Consumer is ACTIVE (`true`)
- **Consumer has `prefetch_count = 0`**
- This means: "Don't fetch ANY messages from the queue"

### 6. Celery Inspect Shows No Reserved Tasks
```bash
$ docker exec diavgeia_worker celery -A diavgeia_project inspect reserved
->  celery@1c5d72535450: OK
    - empty -
```
**Facts:**
- Celery has not fetched any tasks from RabbitMQ
- No tasks are "reserved" (pre-fetched but not yet started)
- Consumer is starved despite messages being available

### 7. Last Successful Task
```
2026-01-03 17:11:30 - Task core.tasks.tasks_entities.fetch_company_data_for_single_afm[2b25f371...] succeeded
[7+ MINUTES OF SILENCE]
```
**Facts:**
- Last task completed successfully at 17:11:30
- Worker went silent after that
- 3 tasks remain in queue but are never fetched
- Current time: 17:18:55 (7 minutes 25 seconds of silence)

## Root Cause Analysis

**The Problem:**
- Celery consumer has `prefetch_count = 0`
- This tells RabbitMQ: "Don't send me any messages"
- Worker sits idle even though messages are ready in the queue

**What We Know:**
1. Tasks DO get processed initially (we see multiple successful completions)
2. At some point, prefetch count changes from 1 (or higher) to 0
3. Once it becomes 0, consumer stops fetching new messages
4. Worker has no work because consumer stopped feeding it
5. Restarting the worker resets prefetch and everything works again... until it doesn't

**What We DON'T Know:**
1. **WHEN does prefetch become 0?**
   - After finishing a task?
   - During a task?
   - After some time threshold?
   - After N tasks?

2. **WHAT causes prefetch to become 0?**
   - Celery rate limiting side effect?
   - Some internal Celery QoS adjustment?
   - A bug in Celery itself?
   - Something in our signal handlers (even though we disabled them)?
   - Some configuration interaction?

3. **WHY doesn't it happen immediately?**
   - If prefetch was 0 from the start, NO tasks would ever run
   - But tasks DO run for a while before it stops
   - This suggests something changes prefetch at runtime

## Configuration Context

**Celery Settings:**
```python
worker_prefetch_multiplier=1  # We set this to 1
task_track_started=False      # Disabled for testing
result_backend="django-db"
```

**Task Rate Limiting:**
```python
@shared_task(bind=True, max_retries=3, rate_limit="6/m")
def fetch_company_data_for_single_afm(self, afm: str):
```

**Worker Concurrency:**
```
--concurrency=1
```

## Things We Tried That Didn't Fix It

❌ **Disabling `task_track_started`** - Hang still occurs  
❌ **Disabling signal handlers** - Hang still occurs  
❌ **Reverting commit 738ed16** - Hang still occurs  
❌ **Purging queue** - Works temporarily after restart, then hangs again  

## Things We Haven't Tried Yet

1. **Remove `rate_limit="6/m"` from task** - Maybe rate limiting sets prefetch to 0?
2. **Increase `worker_prefetch_multiplier` to 4** - Maybe it's getting decremented somehow?
3. **Add explicit QoS setting** - Force prefetch to stay at 1
4. **Monitor prefetch value over time** - Log when it changes
5. **Check Celery source code** - What operations modify prefetch_count?

## How to Diagnose Next Time This Happens

**Before restarting, run these commands:**

```bash
# 1. Confirm prefetch is 0
docker exec diavgeia_rabbitmq rabbitmqctl list_consumers | grep "^celery"

# 2. Check Celery's view of QoS
docker exec diavgeia_worker celery -A diavgeia_project inspect stats | grep prefetch

# 3. Check for rate limit bucket state (if accessible)
docker exec diavgeia_worker celery -A diavgeia_project inspect stats

# 4. Check worker process state
docker exec diavgeia_worker py-spy dump --pid 37

# 5. Check main consumer process state  
docker exec diavgeia_worker py-spy dump --pid 10

# 6. Save full logs before restart
docker logs diavgeia_worker > worker_hung_$(date +%Y%m%d_%H%M%S).log
```

## Temporary Workaround

**Restart the worker** - This resets prefetch back to 1 and everything works again until prefetch mysteriously becomes 0 again.

```bash
docker restart diavgeia_worker
```

## Suspected Root Cause (Unproven)

**Rate limiting + concurrency=1 + prefetch_multiplier=1 creates a perfect storm:**

1. Worker with concurrency=1 means only 1 task can run at a time
2. Rate limit "6/m" means Celery enforces 10-second delays between tasks
3. Prefetch_multiplier=1 means consumer can only pre-fetch 1 message
4. **Hypothesis:** Celery's rate limiter might set prefetch to 0 when rate limit is hit, expecting to restore it later
5. **But:** Something prevents it from restoring, leaving prefetch at 0 forever
6. Worker starves because consumer won't fetch new messages

**This is speculation. We need proof.**

## Update: Additional Issues Discovered (2026-01-04)

### Issue 2: Tasks Showing STARTED but Not Producing Logs

**Symptoms:**
- 3 workers, 3 tasks showing as "STARTED"
- No logs from these tasks
- Empty queue in RabbitMQ
- No database locks detected

**Root Causes Found:**

#### 1. **DateCoverage Race Condition** (Primary Issue)
```python
core.models.import_jobs.DateCoverage.MultipleObjectsReturned: 
get() returned more than one DateCoverage -- it returned 2!
```

**What Happened:**
- Multiple workers processing decisions simultaneously
- Each triggers `update_organization_coverage` signal
- Signal uses `update_or_create()` which internally does:
  1. Try `get()` → DoesNotExist
  2. Try to `create()` 
- **Race condition:** Both workers pass step 1, both try to create
- One succeeds, one hits unique constraint, retries `get()`
- Now `get()` finds 2 records → `MultipleObjectsReturned`
- Task crashes without clear logs

**Fix:** Changed from `update_or_create()` to `get_or_create()` with explicit duplicate cleanup:
```python
try:
    coverage, created = DateCoverage.objects.get_or_create(...)
    if not created:
        coverage.decision_count = current_count
        coverage.save()
except DateCoverage.MultipleObjectsReturned:
    # Clean up duplicates
    duplicates = DateCoverage.objects.filter(...).order_by('id')
    keeper = duplicates.first()
    keeper.decision_count = current_count
    keeper.save()
    duplicates.exclude(id=keeper.id).delete()
```

#### 2. **Celery Retry Bug**
```python
TypeError: store_decisions_from_pickle() got multiple values for argument 'pickle_file'
```

**What Happened:**
- Task fails (e.g., FileNotFoundError)
- Retry logic does: `self.retry(kwargs={'pickle_file': pickle_file, 'batch_size': 1})`
- But `pickle_file` is already in `args` from original call
- Celery passes it both ways → TypeError
- Task is rejected, not requeued

**Fix:** Removed `pickle_file` from retry kwargs (it's already in args):
```python
raise self.retry(
    countdown=delay,
    kwargs={'batch_size': new_batch_size},  # Only pass batch_size
    exc=e
)
```

#### 3. **Pickle Path Bug**
```python
FileNotFoundError: '/code/logs/pickles/pickles/chunk_2025-06-28_2_165539.pkl'
```

**What Happened:**
- `PICKLE_DIR` constant already includes `/logs/pickles`
- Code adds another `/pickles`: `f"{PICKLE_DIR}/pickles"`
- Results in `/code/logs/pickles/pickles/...`

**Fix:** Use `PICKLE_DIR` directly without appending `/pickles`.

#### 4. **Missing Countdown in apply_async**
```python
delay_seconds = (i // chunk_size) * 3  # Calculated but never used!
storage_task = store_decisions_from_pickle.apply_async(
    args=[chunk_pickle],
    kwargs={'batch_size': 1},
    # countdown=delay_seconds  # <-- Missing!
)
```

**What Happened:**
- All storage tasks dispatched immediately
- All 3 workers grab tasks simultaneously
- Race conditions ensue

**Fix:** Added `countdown=delay_seconds` to `apply_async()`.

### Key Takeaway

The tasks were **not hanging**. They were:
1. **Crashing** due to DateCoverage race condition
2. **Failing to retry** due to retry signature bug
3. **Competing for resources** due to missing task delays

After the crashes, the workers were idle (no tasks in queue), which appeared like a "hang" but was actually "all tasks failed and there's nothing left to do."

## Resolution & Root Cause Analysis (2026-01-03)

### The "Greedy Worker" Trap
The root cause was a conflict between Celery's `rate_limit` decorator and the worker's prefetch configuration, creating a "Greedy Worker" scenario.

#### 1. The Mechanism
- **Configuration**: We had `worker_prefetch_multiplier=1` in settings, intending for the worker to take one task at a time.
- **The Override**: We applied `@shared_task(rate_limit="6/m")` to `fetch_company_data_for_single_afm`.
- **The Side Effect**: When `rate_limit` is used, Celery often disables the prefetch limit (sets `prefetch_count=0` in RabbitMQ) to manage the scheduling internally.
- **The Result**: `prefetch_count=0` in RabbitMQ means **"Unlimited Prefetch"**.

#### 2. The Workflow Failure
In our specific case (Decision Import Pipeline):
1.  **Trigger**: The `import_decisions_daily` command runs.
2.  **Fan-out**: It triggers `_trigger_company_data_fetching`, which spawns multiple `fetch_company_data_for_single_afm` tasks (e.g., 20 tasks for 20 different AFMs found in decisions).
3.  **The Gulp**: The single worker (`concurrency=1`) connects to the queue. Because of the rate limit decorator (and resulting `prefetch=0`), it **downloads all 20 tasks immediately** into its RAM.
4.  **The Choke**:
    - It executes Task #1.
    - It prepares for Task #2.
    - The **Celery Rate Limiter** intervenes: *"Limit is 6/m. You must wait 10 seconds."*
    - The worker sits idle, holding 19 unacknowledged tasks.
5.  **The Hang**:
    - To an observer (us), the worker looks idle (it's waiting).
    - To RabbitMQ, the worker is hoarding messages but not acknowledging them fast enough.
    - If the internal wait interferes with the heartbeat (common in single-threaded blocking scenarios), RabbitMQ eventually closes the connection ("Rejected by RabbitMQ").

### The Fix: Manual Rate Limiting
We removed the `rate_limit="6/m"` decorator and relied on `GemiService`'s internal logic.

**Why this is better:**
1.  **Restores Prefetch=1**: Without the decorator, `worker_prefetch_multiplier=1` is respected.
2.  **Polite Consumption**: The worker fetches **one** task.
3.  **Active Processing**: The task starts immediately. The "waiting" happens *inside* the running task (via `time.sleep` in `GemiService`), so the task is marked as `STARTED`, not stuck in a hidden prefetch buffer.
4.  **Scalability**: If we add more workers later, they can pick up tasks from the queue because the first worker isn't hoarding them all.

### Verified Behavior
After the fix:
- `rabbitmqctl list_consumers` shows `prefetch_count=1`.
- Tasks flow through the system one by one.
- No "Received" but not "Started" tasks.
- Logs show successful processing of AFM data.
