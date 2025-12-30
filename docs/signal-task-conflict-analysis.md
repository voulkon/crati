# Signal & Task Conflict Analysis

## 🚨 Problem: Double Processing Risk

We created `DecisionPipelineOrchestrator` as the single source of truth, but **old signals and tasks are still active**. This causes:

1. **Double document processing** - Signal triggers task, orchestrator also processes
2. **Double OpenSearch indexing** - Signal indexes, orchestrator indexes
3. **Race conditions** - Entity extraction running twice simultaneously
4. **Wasted resources** - Celery queue filled with duplicate work

## Current Conflicting Signals

### 📍 File: `backend/core/signals.py`

#### 1. `queue_document_processing` (Line 160)
```python
@receiver(post_save, sender=Decision)
def queue_document_processing(sender, instance, created, **kwargs):
    if created and instance.document_url:
        from core.tasks import process_document_task
        transaction.on_commit(lambda: process_document_task.delay(instance.ada))
```

**Conflict:** When a decision is imported, this signal automatically queues `process_document_task`.  
**Problem:** If we also call `run_decision_pipeline_task`, document processing happens TWICE.

---

#### 2. `index_document_in_opensearch` (Line 171)
```python
@receiver(post_save, sender=DocumentExtraction)
def index_document_in_opensearch(sender, instance, created, **kwargs):
    if instance.extraction_status == 'COMPLETED' and instance.raw_text:
        opensearch_service = OpenSearchService()
        success = opensearch_service.index_document(document_data)
```

**Conflict:** When DocumentExtraction completes, this signal automatically indexes to OpenSearch.  
**Problem:** Orchestrator's `_step_index_opensearch()` also indexes. Result: **duplicate indexing**.

---

#### 3. `document_extraction_health_check_signal` (Line 256)
```python
@receiver(post_save, sender=DocumentExtraction)
def document_extraction_health_check_signal(sender, instance, created, **kwargs):
    if instance.extraction_status in significant_statuses:
        from core.tasks.health_check_tasks import check_single_decision_health
        check_single_decision_health.delay(instance.decision.ada)
```

**Conflict:** Triggers separate health check update.  
**Problem:** Orchestrator already updates DecisionHealthCheck after each step. Redundant.

---

### 📍 File: `backend/core/signals/health_check_signals.py`

#### 4. `decision_saved_signal` (Line 19)
```python
@receiver(post_save, sender=Decision)
def decision_saved_signal(sender, instance, created, **kwargs):
    # Marks health check for refresh
```

**Conflict:** Marks health check as stale on every save.  
**Problem:** Orchestrator already creates/updates health check explicitly. Signal causes unnecessary refreshes.

---

#### 5. `document_extraction_updated_signal` (Line 45)
```python
@receiver(post_save, sender=DocumentExtraction)
def document_extraction_updated_signal(sender, instance, created, **kwargs):
    if instance.extraction_status in significant_statuses:
        check_single_decision_health.delay(decision.ada)
```

**Conflict:** Duplicate of signal #3 above.  
**Problem:** Same as #3 - redundant health check updates.

---

## Current Task Usages (Need Migration)

### Critical Usages (Must Replace)

1. **`backend/core/signals.py:167`** - Signal calling `process_document_task.delay`
   - **Replace with:** Remove signal entirely, rely on orchestrator

2. **`backend/admin_custom/views/documents/sync_status.py:138`** - ✅ Already fixed!
   - **Status:** NOW calls `run_decision_pipeline_task`

3. **`backend/core/management/commands/process_documents.py:61`**
   - **Replace with:** Add orchestrator option to command

4. **`backend/core/api/views/document_analysis.py:50`**
   - **Replace with:** Use `run_decision_pipeline_task` for API endpoint

5. **`backend/api/custom_views/document_processing.py:21`**
   - **Replace with:** Use orchestrator for batch processing

### Non-Critical Usages (Can Keep for Now)

6. **`backend/core/management/commands/investigate_decision_issues.py:427`**
   - **Status:** Diagnostic/debugging script - OK to keep legacy task

7. **`backend/admin_custom/views/documents/sync_status.py:108,115`** (extract_all action)
   - **Status:** Bulk processing - can migrate later

---

## Recommended Solution

### Phase 1: Feature Flag (Immediate) ✅

Add setting to disable conflicting signals when using orchestrator:

```python
# settings.py
USE_ORCHESTRATOR_MODE = True  # Set to True to disable legacy signals
```

### Phase 2: Conditional Signal Disable (This PR)

Wrap signals in conditional checks:

```python
@receiver(post_save, sender=Decision)
def queue_document_processing(sender, instance, created, **kwargs):
    # Skip if orchestrator mode enabled
    if getattr(settings, 'USE_ORCHESTRATOR_MODE', False):
        logger.debug(f"Skipping legacy document queue for {instance.ada} (orchestrator mode)")
        return
    
    # Original signal logic...
```

### Phase 3: Migrate Task Usages (Next PR)

Replace all `process_document_task` calls with `run_decision_pipeline_task`:

- [ ] Update `process_documents` command
- [ ] Update document analysis API view
- [ ] Update custom document processing view
- [ ] Update bulk extraction in sync_status

### Phase 4: Remove Signals (Future PR)

Once all code uses orchestrator:
- Delete conflicting signals entirely
- Keep only essential signals (coverage metrics)
- Clean up signal files

---

## Migration Checklist

### Immediate Actions (Do Now)
- [x] Create this analysis document
- [ ] Add `USE_ORCHESTRATOR_MODE` setting
- [ ] Wrap conflicting signals in feature flag checks
- [ ] Test with orchestrator mode ON vs OFF

### Short-term (This Week)
- [ ] Update `process_documents` management command
- [ ] Update document analysis API endpoint
- [ ] Update bulk processing views
- [ ] Add migration guide to docs

### Long-term (Next Sprint)
- [ ] Remove signal wrappers (delete signals entirely)
- [ ] Clean up legacy task definitions
- [ ] Update all documentation
- [ ] Add monitoring for double-processing detection

---

## Testing Strategy

### Test Case 1: Import Single Decision (Orchestrator Mode OFF)
**Expected:** Signal processes document automatically  
**Verify:** Only ONE DocumentExtraction record created

### Test Case 2: Import Single Decision (Orchestrator Mode ON)
**Expected:** Signal skipped, must call orchestrator explicitly  
**Verify:** No DocumentExtraction until orchestrator runs

### Test Case 3: Run Orchestrator on Existing Decision
**Expected:** All 6 stages complete, DecisionHealthCheck updated  
**Verify:** No duplicate indexing in OpenSearch

### Test Case 4: Batch Import via ImportJob
**Expected:** 1000 decisions imported, orchestrator processes batch  
**Verify:** Signal doesn't trigger 1000 duplicate tasks

---

## Specific Signal Conflicts

### Signal: `queue_document_processing`
**When Fired:** Every time a new Decision is saved with `document_url`  
**What It Does:** Queues `process_document_task.delay(ada)`  
**Orchestrator Overlap:** Orchestrator's `_step_process_document()` does the same  
**Resolution:** Disable when `USE_ORCHESTRATOR_MODE=True`

### Signal: `index_document_in_opensearch`
**When Fired:** Every time DocumentExtraction status becomes COMPLETED  
**What It Does:** Calls `opensearch_service.index_document()`  
**Orchestrator Overlap:** Orchestrator's `_step_index_opensearch()` does the same  
**Resolution:** Disable when `USE_ORCHESTRATOR_MODE=True`

### Signal: `document_extraction_health_check_signal`
**When Fired:** When DocumentExtraction changes to significant status  
**What It Does:** Queues `check_single_decision_health.delay()`  
**Orchestrator Overlap:** Orchestrator updates DecisionHealthCheck after each step  
**Resolution:** Disable when `USE_ORCHESTRATOR_MODE=True`

---

## Example: What Happens Without Fix

```
User: import_decisions_daily --date 2024-12-29
  ↓
[1000 decisions imported]
  ↓
Signal: queue_document_processing fires 1000 times
  ↓
[1000 x process_document_task.delay() queued]
  ↓
User: run_decision_pipeline --import-job-id 1847
  ↓
[1000 x run_decision_pipeline_task called]
  ↓
RESULT: 2000 tasks in Celery queue!
  ↓
[Documents processed TWICE]
[OpenSearch indexed TWICE per document]
[Wasted $$ on Celery workers]
```

---

## Recommended Settings

### Development (Test Both Modes)
```python
# settings/development.py
USE_ORCHESTRATOR_MODE = False  # Test legacy behavior
# or
USE_ORCHESTRATOR_MODE = True   # Test orchestrator behavior
```

### Production (Orchestrator Mode)
```python
# settings/production.py
USE_ORCHESTRATOR_MODE = True   # Always use orchestrator
ENABLE_LEGACY_SIGNALS = False  # Explicitly disable old signals
```

---

## Next Steps

1. **Add feature flag** - Let you toggle orchestrator mode
2. **Wrap signals** - Make them check the flag before running
3. **Test both modes** - Verify no regressions
4. **Migrate task usages** - One file at a time
5. **Remove signals** - Once everything uses orchestrator

This ensures **zero downtime** and **no data corruption** during migration.
