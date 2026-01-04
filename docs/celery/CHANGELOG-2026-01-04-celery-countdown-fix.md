# Changelog: Celery Countdown Bug Fix (2026-01-04)

## 🐛 Bug Fixed
**Silent Task Loss in Celery 5.6.1**

Tasks dispatched with `apply_async(countdown=X)` were disappearing without error logs or worker processing.

---

## 📋 Changes Made

### 1. Code Changes

**File**: `backend/core/tasks/tasks_decisions_import.py`

**Lines Modified**:
- Line 1-14: Added module docstring explaining the bug and fix
- Line 126-147: Removed `countdown` parameter from `apply_async()` call
- Line 173-195: Added internal `time.sleep()` delay mechanism

**Before**:
```python
storage_task = store_decisions_from_pickle.apply_async(
    args=[chunk_pickle],
    countdown=delay_seconds  # ❌ BROKEN - tasks lost
)
```

**After**:
```python
storage_task = store_decisions_from_pickle.apply_async(
    args=[chunk_pickle],
    kwargs={'delay_seconds': delay_seconds}  # ✅ FIXED
)

# Inside store_decisions_from_pickle:
if delay_seconds > 0:
    time.sleep(delay_seconds)  # Delay happens in worker
```

### 2. Documentation Added

**File**: `docs/celery-countdown-bug-research.md` (NEW)
- Full investigation report
- Evidence from GitHub issues #9912, #9811, #9867
- Root cause analysis
- Solution comparison
- Testing procedures

---

## ✅ Validation

### Before Fix
- ❌ Tasks stuck in "RECEIVED" state in Flower
- ❌ Pickle files orphaned in `/code/logs/pickles/`
- ❌ No worker logs for missing tasks
- ❌ Silent failures with no errors

### After Fix
- ✅ All tasks process successfully
- ✅ No orphaned pickle files
- ✅ Workers log all task execution
- ✅ Chunks complete reliably

---

## 🔍 Root Cause

1. **Celery 5.6.1 Bug**: countdown parameter broken when RabbitMQ lacks delayed message exchange plugin
2. **Missing Plugin**: `rabbitmq_delayed_message_exchange` not installed
3. **Fallback Mechanism**: Celery's native TTL fallback has race conditions
4. **Result**: Tasks sent to `celery_delayed_x` queues and silently dropped

---

## 🎯 Impact

**Affected**:
- ✅ Daily decision imports (fetch_daily_decisions_to_pickle → store_decisions_from_pickle)
- ✅ Chunk-based processing with staggered delays

**Not Affected**:
- ✅ `self.retry(countdown=X)` - Works correctly (different mechanism)
- ✅ Other tasks without countdown parameter
- ✅ Tasks using `apply_async()` without countdown

---

## 📊 Testing Commands

```bash
# Check for orphaned pickles (should be empty)
docker exec diavgeia_worker find /code/logs/pickles -name "*.pkl" -mmin +10

# Verify task completion
docker exec diavgeia_backend python manage.py shell -c "
from core.models import IngestionRun
run = IngestionRun.objects.latest('started_at')
print(f'Lost tasks: {run.total_chunks - run.processed_chunks}')
"

# Monitor active tasks
docker exec diavgeia_worker celery -A diavgeia_project inspect active
```

---

## 🔗 References

- GitHub Issue #9912: https://github.com/celery/celery/issues/9912
- GitHub Issue #9811: https://github.com/celery/celery/issues/9811
- Full Investigation: `/docs/celery-countdown-bug-research.md`

---

## ⚠️ Important Notes

1. **DO NOT use** `apply_async(countdown=X)` in Celery 5.6.1 without the plugin
2. **self.retry(countdown=X)** is SAFE - uses different mechanism
3. Plugin installation is optional - current fix works without it
4. Consider installing `rabbitmq_delayed_message_exchange` plugin for future flexibility

---

## 👤 Authors

- Investigation & Fix: AI Assistant + User
- Date: 2026-01-04
- System: Celery 5.6.1, RabbitMQ 3.12.14, Django
