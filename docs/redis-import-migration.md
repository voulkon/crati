# Redis-Based Import System Migration

## Summary

Migrated the decision import pipeline from **filesystem pickles** to **Redis-based temporary storage** with proper **ImportJob tracking** for better visibility and reliability.

## Problem

1. **Lost pickle files**: Container restarts caused "FileNotFoundError" for pickles stored in `/code/logs/pickles/`
2. **No progress visibility**: No way to track "how many of 20k decisions have been processed?"
3. **Duplicate detection**: Hard to know if we already started importing a specific date
4. **Mixed tasks**: Tasks from different dates got interleaved with no way to distinguish them

## Solution

### 1. Extended ImportJob Model ✅

**Why not create a new model?** You already had `ImportJob` - we extended it instead of creating duplicate `ImportBatch`.

**New fields added to `ImportJob`:**
```python
# Chunked import tracking
total_chunks = IntegerField()          # Number of Redis chunks created
chunks_completed = IntegerField()      # Successfully processed
chunks_failed = IntegerField()         # Failed chunks
chunk_task_ids = ArrayField()          # Celery task IDs for tracking
search_params = JSONField()            # API parameters used

# New statuses
FETCHING = 'fetching'                  # Fetching from Diavgeia API
SPLITTING = 'splitting'                # Creating Redis chunks
PROCESSING = 'processing'              # Workers processing chunks
PARTIALLY_COMPLETED = 'partially_completed'  # Some chunks failed
```

**New methods:**
- `progress_percentage` property - Calculate % completion
- `is_complete` property - Check if all chunks done
- `mark_chunk_completed(decisions_count)` - Atomic counter increment
- `mark_chunk_failed(error_msg, decisions_count)` - Track failures

### 2. Redis Decision Cache Service ✅

**File**: `backend/core/services/redis_decision_cache.py`

**Redis DB Assignment** (following best practices):
- **DB 0**: Celery results (`CELERY_RESULT_BACKEND`)
- **DB 1**: Django cache (`CACHES['default']`)
- **DB 2**: Import decision chunks (**this service**) ✅

**Centralized Keys** (following `api/redis_keys.py` pattern):
```python
# Keys added to api/redis_keys.py:
IMPORT_CHUNKS_NS = "import"
IMPORT_CHUNK_PREFIX = "import:chunk:"           # import:chunk:123_chunk_5
IMPORT_JOB_METADATA_PREFIX = "import:job:"      # import:job:123
IMPORT_CHUNKS_EXPIRE = 86400  # 24 hours
```

**Key Methods:**
- `store_chunk(chunk_id, decisions, metadata, ttl)` - Store in Redis
- `get_chunk(chunk_id, delete_after_read=True)` - Retrieve and optionally delete
- `chunk_exists(chunk_id)` - Check if exists
- `cleanup_job(job_id)` - Delete all chunks for a job
- `get_job_stats(job_id)` - Count remaining chunks in Redis

### 3. Updated Tasks ✅

**File**: `backend/core/tasks/tasks_decisions_import.py`

#### `fetch_daily_decisions_to_redis(target_date_str, chunk_size=10)`

**Old flow (pickle-based)**:
1. Fetch decisions from API
2. Save to `/code/logs/pickles/decisions_2025-03-09_120033.pkl`
3. Split into chunk pickles: `chunk_2025-03-09_1_120034.pkl`
4. Dispatch tasks with pickle file paths

**New flow (Redis-based)**:
1. Check if ImportJob already exists for this date (prevent duplicates)
2. Create ImportJob with status=FETCHING
3. Fetch all decisions from Diavgeia API
4. Update ImportJob: status=SPLITTING, total_decisions=20000
5. Split into chunks (default 10 decisions each = 2000 chunks)
6. Store each chunk in Redis: `import:chunk:123_chunk_0`
7. Dispatch `store_decisions_from_redis` tasks with chunk_id + job_id
8. Update ImportJob: status=PROCESSING, total_chunks=2000

**Benefits**:
- ✅ No lost files on container restart
- ✅ Duplicate detection built-in
- ✅ Full progress tracking from start
- ✅ Redis auto-expires after 24h (no disk cleanup needed)

#### `store_decisions_from_redis(chunk_id, job_id, delay_seconds)`

**Old flow**:
1. Load pickle from filesystem
2. Process decisions one-by-one
3. Move pickle to `/code/logs/pickles/completed/`
4. Hope it doesn't get lost on retry

**New flow**:
1. Get ImportJob from database (job_id)
2. Load chunk from Redis (auto-deletes after read)
3. Process each decision through pipeline orchestrator
4. Call `import_job.mark_chunk_completed(decisions_count)` - atomic update
5. ImportJob auto-transitions to COMPLETED when all chunks done

**Benefits**:
- ✅ No FileNotFoundError on retries
- ✅ Atomic progress tracking (no race conditions)
- ✅ Auto-completion when chunks_completed == total_chunks
- ✅ Detailed error tracking per chunk

### 4. Monitoring & Observability ✅

**Django Admin** (already exists in `admin_custom/admin_classes/analytics.py`):
```python
ImportJobAdmin shows:
- Progress: "1523/2000 chunks (76.2%)"
- Status: PROCESSING → COMPLETED
- Decisions: 15230 processed, 0 failed
- Health checks: Links to view warnings/errors
```

**Query ImportJobs:**
```python
# Check if date already imported
ImportJob.objects.filter(
    start_date='2025-03-09',
    status__in=['FETCHING', 'PROCESSING']
).exists()

# Get active imports
active = ImportJob.objects.filter(
    status__in=['FETCHING', 'SPLITTING', 'PROCESSING']
)

# Monitor progress
job = ImportJob.objects.get(id=123)
print(f"Progress: {job.progress_percentage:.1f}%")
print(f"Completed: {job.chunks_completed}/{job.total_chunks}")
print(f"Failed: {job.chunks_failed}")
```

**Redis Stats:**
```python
from core.services.redis_decision_cache import RedisDecisionCache

cache = RedisDecisionCache()
stats = cache.get_job_stats(job_id=123)
# {'job_id': 123, 'chunks_in_redis': 477}  # Still waiting to be processed
```

**Jaeger Tracing:**
- One span per `fetch_daily_decisions_to_redis` task
- Child spans for each `store_decisions_from_redis` chunk
- Can filter by `job_id` tag to see all tasks for one import

## Migration Guide

### For Scheduled/Cron Tasks

**Old code:**
```python
from core.tasks import fetch_daily_decisions_to_pickle
task = fetch_daily_decisions_to_pickle.delay('2025-03-09')
```

**New code:**
```python
from core.tasks import fetch_daily_decisions_to_redis
task = fetch_daily_decisions_to_redis.delay(
    target_date_str='2025-03-09',
    chunk_size=10  # Optional, defaults to 10
)
```

### For Manual/API Imports

```python
from core.tasks import fetch_daily_decisions_distributed

# This orchestrator wraps the Redis-based flow
result = fetch_daily_decisions_distributed.delay('2025-03-09', chunk_size=10)
# Returns: {'status': 'dispatched', 'fetch_task_id': '...', 'job_id': 123}
```

### Monitoring an Import

```python
from core.models import ImportJob

job = ImportJob.objects.get(id=123)

print(f"Date: {job.start_date}")
print(f"Status: {job.status}")  # FETCHING → SPLITTING → PROCESSING → COMPLETED
print(f"Progress: {job.progress_percentage:.1f}%")
print(f"Decisions: {job.new_decisions} processed, {job.error_count} failed")
print(f"Chunks: {job.chunks_completed}/{job.total_chunks} completed")

if job.is_complete:
    print(f"Completed at: {job.completed_at}")
```

## Deployment Steps

1. **Run migration**:
   ```bash
   cd backend
   python manage.py makemigrations core
   python manage.py migrate core
   ```

2. **Restart workers** (to load new code):
   ```bash
   docker-compose -f docker/docker-compose.yml restart worker beat
   ```

3. **Verify Redis DB 2 is available**:
   ```bash
   docker exec -it diavgeia_redis redis-cli
   > SELECT 2
   > KEYS import:*
   (empty array) # Should be empty initially
   ```

4. **Test import**:
   ```bash
   python manage.py shell
   >>> from core.tasks import fetch_daily_decisions_distributed
   >>> result = fetch_daily_decisions_distributed.delay('2025-01-15')
   >>> result.id
   'abc123...'
   ```

5. **Monitor in Django Admin**:
   - Go to Admin → Import Jobs
   - Watch progress_percentage increase
   - Check chunks_completed vs total_chunks

## Rollback Plan

If issues arise, the old `store_decisions_from_pickle` function still exists as a deprecated wrapper that will raise `NotImplementedError` with a helpful message. To fully rollback:

1. Revert migrations
2. Restore old task code from git
3. Restart workers

## Performance Considerations

**Redis Memory Usage**:
- Each chunk: ~10 decisions × ~5KB/decision = ~50KB
- 2000 chunks = ~100MB in Redis
- TTL: 24 hours (auto-cleanup)
- **Recommendation**: Monitor Redis memory, consider reducing chunk_size if needed

**Chunk Size Tuning**:
- **Current**: 10 decisions/chunk
- **Smaller** (5): More tasks, more overhead, better parallelism
- **Larger** (50): Fewer tasks, less overhead, slower progress visibility
- **Recommendation**: Start with 10, adjust based on worker count

**Database Load**:
- Each chunk completion = 1 atomic UPDATE (ImportJob counters)
- 2000 chunks = 2000 UPDATEs over time (not a problem)
- Uses `F()` expressions to avoid race conditions

## Testing Checklist

- [ ] Import small batch (100 decisions)
- [ ] Import large batch (20k+ decisions)
- [ ] Test duplicate prevention (run same date twice)
- [ ] Test container restart during import
- [ ] Verify Redis cleanup after completion
- [ ] Check Jaeger spans are properly nested
- [ ] Verify Django Admin shows correct progress
- [ ] Test chunk failure handling
- [ ] Verify auto-completion when all chunks done
- [ ] Check PARTIALLY_COMPLETED status when some chunks fail

## Files Changed

### Modified
- `backend/core/models/import_jobs.py` - Extended ImportJob model
- `backend/core/tasks/tasks_decisions_import.py` - Redis-based tasks
- `backend/api/redis_keys.py` - Added import chunk keys
- `backend/diavgeia_project/settings/__init__.py` - Exposed REDIS_* settings

### Created
- `backend/core/services/redis_decision_cache.py` - Redis cache service
- `docs/redis-import-migration.md` - This document

### Removed
- `backend/core/models/import_batch.py` - Duplicate model (consolidated into ImportJob)
- `backend/core/views/import_batch_views.py` - Unnecessary API (use Django Admin)

## Questions & Answers

**Q: Why not use RabbitMQ queues instead of Redis?**
A: RabbitMQ is the task broker, not a data store. Redis is better for:
- Fast key-value lookups
- Atomic operations
- TTL-based expiration
- Simpler than managing custom queues

**Q: What if Redis goes down?**
A: Tasks will fail with clear error messages. ImportJob status = FAILED. Re-run the import once Redis is back.

**Q: Can I still use the old pickle approach?**
A: No, `store_decisions_from_pickle` now raises `NotImplementedError`. All imports must use the Redis flow.

**Q: How do I clean up old Redis keys manually?**
A: 
```python
from core.services.redis_decision_cache import RedisDecisionCache
cache = RedisDecisionCache()
cache.cleanup_job(job_id=123)  # Deletes all chunks for job 123
```

**Q: Does this work in production with multiple workers?**
A: Yes! Redis is shared across all workers. Atomic operations prevent race conditions. Each worker processes different chunks in parallel.
