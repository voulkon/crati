# Migrating to Orchestrator Mode

## Quick Start

### Step 1: Enable Orchestrator Mode (Recommended)

Add to your environment or settings:
```bash
export USE_ORCHESTRATOR_MODE=True
```

Or in `settings.py` (already added):
```python
USE_ORCHESTRATOR_MODE = True
```

### Step 2: Restart Services

```bash
# Restart Django
docker-compose restart backend

# Restart Celery workers
docker-compose restart celery worker
```

### Step 3: Verify Mode is Active

Check logs on startup:
```
====================================================
🎯 Orchestrator Mode ENABLED:
   - Legacy document processing signals DISABLED
   - Use run_decision_pipeline_task for processing
   - No automatic document/entity processing on save
====================================================
```

## What Changed?

### Before (Legacy Signals)
```python
# Importing decision automatically triggers:
Decision.objects.create(ada="...", document_url="...")
  ↓
Signal: queue_document_processing fires
  ↓
process_document_task.delay() queued automatically
  ↓
DocumentExtraction created
  ↓
Signal: index_document_in_opensearch fires
  ↓
OpenSearch indexed automatically
```

**Problem:** No control, no visibility, scattered processing

### After (Orchestrator Mode)
```python
# 1. Import decision (no automatic processing)
Decision.objects.create(ada="...", document_url="...")
# Nothing happens automatically!

# 2. Explicitly process through orchestrator
from core.tasks.tasks_documents import run_decision_pipeline_task
run_decision_pipeline_task.delay(ada="...", force_reprocess=True)
  ↓
DecisionPipelineOrchestrator.run_pipeline()
  ↓
  ├─ Entities extracted
  ├─ Companies enriched  
  ├─ Document processed
  ├─ OpenSearch indexed
  └─ Health check updated
  ↓
DecisionHealthCheck shows component-level status
```

**Benefits:** Full control, complete visibility, traceable errors

## Feature Flag Behavior

### USE_ORCHESTRATOR_MODE=True (Recommended)

**Signals Disabled:**
- ✅ `queue_document_processing` - No auto document processing
- ✅ `index_document_in_opensearch` - No auto OpenSearch indexing  
- ✅ `document_extraction_health_check_signal` - No redundant health checks
- ✅ `decision_saved_health_check_signal` - No health check refresh
- ✅ `document_extraction_updated_signal` - No duplicate health updates

**Signals Still Active:**
- ✅ `update_organization_coverage` - DateCoverage updates (safe)
- ✅ `update_signer_coverage` - Signer coverage updates (safe)
- ✅ `update_coverage_on_delete` - Coverage cleanup (safe)

**How to Process:**
```python
# Single decision
run_decision_pipeline_task.delay("ADA_HERE")

# Batch via ImportJob
python manage.py run_decision_pipeline --import-job-id 1847

# Via admin UI
# Admin → Sync Status → Select decisions → "Extract Selected"
```

### USE_ORCHESTRATOR_MODE=False (Legacy)

All signals fire automatically. Use for:
- Testing backward compatibility
- Gradual migration
- Emergency rollback

**Not recommended for production** - leads to scattered processing and poor visibility.

## Migration Checklist

### For New Code (Always Use Orchestrator)

```python
# ❌ DON'T: Use old document task
from core.tasks import process_document_task
process_document_task.delay(ada)

# ✅ DO: Use orchestrator task
from core.tasks import run_decision_pipeline_task  
run_decision_pipeline_task.delay(ada, force_reprocess=True)
```

### For Existing Code

#### 1. Management Commands

**File:** `backend/core/management/commands/process_documents.py`

**Before:**
```python
task = process_document_task.delay(decision.ada)
```

**After:**
```python
from core.tasks.tasks_documents import run_decision_pipeline_task
task = run_decision_pipeline_task.delay(decision.ada, force_reprocess=False)
```

#### 2. API Views

**File:** `backend/core/api/views/document_analysis.py`

**Before:**
```python
task = process_document_task.delay(decision.ada, provider)
```

**After:**
```python
from core.tasks.tasks_documents import run_decision_pipeline_task
# Note: Orchestrator doesn't support provider parameter yet
# Either add it or process through DocumentAnalysisService directly
task = run_decision_pipeline_task.delay(decision.ada, force_reprocess=True)
```

#### 3. Custom Views

**File:** `backend/admin_custom/views/documents/sync_status.py`

**Status:** ✅ Already migrated!

Now uses `run_decision_pipeline_task` instead of `process_document_task_enhanced`.

### Signals vs Orchestrator - Side by Side

| Aspect | Legacy Signals | Orchestrator Mode |
|--------|----------------|-------------------|
| **Trigger** | Automatic on save | Explicit call required |
| **Control** | None | Full control |
| **Visibility** | Logs only | DecisionHealthCheck + logs |
| **Error Tracking** | Scattered | Component-level in DB |
| **Retry** | Manual requeue | Built-in retry per component |
| **Testing** | Hard (signals fire) | Easy (explicit calls) |
| **Debugging** | Log diving | Admin UI + structured data |

## Testing Your Migration

### Test 1: Import Without Processing

```bash
# With orchestrator mode ON
python manage.py import_decisions_daily --date 2024-12-29

# Expected: 1000 decisions imported, NO document processing started
# Verify: No DocumentExtraction records created automatically
```

### Test 2: Explicit Processing

```bash
# Process the batch through orchestrator
python manage.py run_decision_pipeline --import-job-id 1847 --workers 10

# Expected: All 1000 decisions processed through full pipeline
# Verify: DecisionHealthCheck records created with component status
```

### Test 3: Single Decision

```python
from core.tasks.tasks_documents import run_decision_pipeline_task

# Queue one decision
result = run_decision_pipeline_task.delay("Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ", force_reprocess=True)

# Check result
health_status = result.get(timeout=300)
print(health_status['overall_status'])  # Should be HEALTHY or ERROR
```

### Test 4: Check Signal Logs

With orchestrator mode ON, you should see in logs:
```
⏭️ Skipping legacy document queue for Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ (orchestrator mode enabled)
⏭️ Skipping legacy OpenSearch indexing for Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ (orchestrator mode enabled)
```

## Rollback Plan

If something breaks:

### Emergency: Disable Orchestrator Mode

```bash
export USE_ORCHESTRATOR_MODE=False
docker-compose restart backend celery worker
```

All signals re-activate immediately. System reverts to old behavior.

### Permanent Rollback

1. Keep `USE_ORCHESTRATOR_MODE=False` in settings
2. Revert admin UI changes to use old tasks
3. Continue using legacy approach (not recommended)

## FAQ

**Q: Do I need to migrate all code at once?**  
A: No. Orchestrator mode only affects NEW processing. Existing code continues to work.

**Q: What if I import decisions with orchestrator mode OFF?**  
A: Signals fire, documents process automatically. Works like before.

**Q: Can I mix orchestrator and signals?**  
A: Not recommended. Choose one mode. Mixing causes double processing.

**Q: How do I know if orchestrator mode is ON?**  
A: Check startup logs for "🎯 Orchestrator Mode ENABLED" message.

**Q: Does this affect existing data?**  
A: No. Only affects how NEW decisions are processed after import.

**Q: What about scheduled tasks?**  
A: Update them to use orchestrator. See migration checklist above.

## Next Steps

1. ✅ Enable orchestrator mode (done - it's the default)
2. ✅ Signals wrapped with feature flag (done)
3. ⏸️ Test with small batch (your next step)
4. ⏸️ Migrate remaining task usages (process_documents command, API views)
5. ⏸️ Update scheduled tasks to use orchestrator
6. ⏸️ Monitor production for 1 week
7. ⏸️ Remove signal wrappers (delete legacy signals entirely)

## Summary

- **Feature Flag:** `USE_ORCHESTRATOR_MODE=True` (default)
- **Signals Affected:** 5 signals disabled when orchestrator mode ON
- **How to Process:** Use `run_decision_pipeline_task` instead of old tasks
- **Visibility:** DecisionHealthCheck shows component-level status
- **Rollback:** Set `USE_ORCHESTRATOR_MODE=False` to re-enable signals
- **Benefits:** Full control, complete visibility, no double processing

You're now ready to use the orchestrator as your single source of truth! 🎯
