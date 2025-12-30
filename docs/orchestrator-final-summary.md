# Orchestrator Summary - What You Asked For vs What We Built

## Your Original Question

> "I need to ensure for a SINGLE decision that all various aspects of it (entity extraction, company data finding, document extraction and indexing of opensearch, etc.) happen. I need something central."

## What We Built

### ✅ Single Entry Point: `run_decision_pipeline_task`

**Location:** `backend/core/tasks/tasks_documents.py`

**Does ALL 6 steps for ONE decision:**
1. ✅ Ingestion (verify exists)
2. 🔍 Entity Extraction (AFM detection)
3. 🏢 Company Enrichment (GEMI lookup)
4. 📄 Document Processing (PDF + text)
5. 🔎 OpenSearch Indexing (search)
6. 📊 Coverage Metrics (stats)

**Usage:**
```python
from core.tasks.tasks_documents import run_decision_pipeline_task
run_decision_pipeline_task.delay("ADA_HERE", force_reprocess=True)
```

**Result:** `DecisionHealthCheck` with component-level status + error messages

---

## Your Concern: Overlapping Signals

> "I have a signal waiting to index stuff in opensearch. If that's the DecisionPipelineOrchestrator's job from now on, they might interfere in ways we don't like, right?"

### ✅ Signals Disabled with Feature Flag

**Setting:** `USE_ORCHESTRATOR_MODE=True` (default in `settings.py`)

**Disabled Signals:**
1. `queue_document_processing` - No auto `process_document_task.delay()`
2. `index_document_in_opensearch` - No auto OpenSearch indexing
3. `document_extraction_health_check_signal` - No redundant health checks
4. `decision_saved_health_check_signal` - No health refresh spam
5. `document_extraction_updated_signal` - No duplicate health updates

**When signals are called now:**
```python
# In signal handler
if getattr(settings, 'USE_ORCHESTRATOR_MODE', False):
    logger.debug("⏭️ Skipping legacy signal (orchestrator mode enabled)")
    return

# Original signal logic only runs if USE_ORCHESTRATOR_MODE=False
```

**Benefits:**
- ✅ No double processing
- ✅ No race conditions
- ✅ No wasted Celery tasks
- ✅ Clean separation: signals OFF, orchestrator ON

---

## Where You Trigger Processing

> "My usual point of triggering one single decision is the 'sync-status/' which triggers the 'sync_status_dashboard' which ends up hitting 'action == "extract_selected"' and this was calling 'process_document_task_enhanced.delay(ada)'"

### ✅ Admin UI Now Uses Orchestrator

**File:** `backend/admin_custom/views/documents/sync_status.py` (Line 131)

**Before:**
```python
process_document_task_enhanced.delay(ada)  # Only documents + opensearch
```

**After:**
```python
run_decision_pipeline_task.delay(ada, force_reprocess=True)  # ALL 6 steps!
```

**New message:**
```
🚀 Queued N decisions for FULL pipeline processing
(entities, companies, documents, OpenSearch).
Check DecisionHealthCheck admin for component-level status.
```

---

## Your Goal: "One and only one way to import decisions"

### ✅ Hierarchy Established

```
┌─────────────────────────────────────────────────────────┐
│ BATCH IMPORT (many decisions)                           │
├─────────────────────────────────────────────────────────┤
│ import_decisions_daily --date 2024-12-29               │
│   ↓                                                      │
│ Creates ImportJob #1847                                 │
│ Imports 1000 decisions with import_job FK               │
│ Updates ImportJob status to COMPLETED                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ BATCH PROCESSING (orchestrator for many)                │
├─────────────────────────────────────────────────────────┤
│ run_decision_pipeline --import-job-id 1847 --workers 10│
│   ↓                                                      │
│ DecisionPipelineOrchestrator.run_batch_pipeline()      │
│ Processes all 1000 decisions (parallel, 10 workers)    │
│ Creates DecisionHealthCheck for each                   │
│ Updates ImportJob summary with health metrics          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ SINGLE DECISION (orchestrator for one)                  │
├─────────────────────────────────────────────────────────┤
│ run_decision_pipeline_task.delay("ADA_HERE")           │
│   ↓                                                      │
│ DecisionPipelineOrchestrator.run_pipeline()            │
│ Runs ALL 6 stages for this decision                    │
│ Updates DecisionHealthCheck with component status      │
└─────────────────────────────────────────────────────────┘
```

### Entry Points (All lead to orchestrator)

**1. Admin UI - Sync Status Page**
```
Admin → Sync Status → Select decisions → "Extract Selected"
  ↓
Uses: run_decision_pipeline_task.delay()
```

**2. Admin UI - ImportJob Dashboard**
```
Admin → Import Jobs → Select batch → Actions → "Retry ERROR decisions"
  ↓
Uses: DecisionPipelineOrchestrator.retry_batch_failures()
```

**3. Management Command - Test Single**
```bash
python manage.py test_single_decision "ADA_HERE" --force
  ↓
Uses: DecisionPipelineOrchestrator.run_pipeline()
```

**4. Management Command - Process Batch**
```bash
python manage.py run_decision_pipeline --import-job-id 1847
  ↓
Uses: DecisionPipelineOrchestrator.run_batch_pipeline()
```

**5. Programmatic (API/Scripts)**
```python
from core.tasks.tasks_documents import run_decision_pipeline_task
run_decision_pipeline_task.delay(ada, force_reprocess=True)
```

---

## What We Fixed

### Problem 1: Scattered Processing
**Before:** `process_document_task` (only documents), signals (maybe entities), separate tasks (maybe indexing)  
**After:** `run_decision_pipeline_task` does ALL 6 steps in sequence

### Problem 2: No Visibility
**Before:** Logs only, no way to see "which step failed for which decision"  
**After:** `DecisionHealthCheck` model with component-level status + error messages

### Problem 3: Double Processing
**Before:** Signal fires task, you also call task → 2x processing  
**After:** Signals disabled when `USE_ORCHESTRATOR_MODE=True` → orchestrator only

### Problem 4: No Retry Mechanism
**Before:** Failed step → decision stuck, manual investigation required  
**After:** Admin actions to retry specific component or all failures

### Problem 5: Multiple "Sources of Truth"
**Before:** `process_document_task`, `process_document_task_enhanced`, `process_documents_task`, signals, etc.  
**After:** `run_decision_pipeline_task` → single entry point

---

## Files Changed

### Core Implementation
1. `backend/core/services/pipeline_orchestrator.py` - Main orchestrator class
2. `backend/core/tasks/tasks_documents.py` - Added `run_decision_pipeline_task`
3. `backend/core/tasks/__init__.py` - Exported new task with 🎯 marker

### Signal Disabling
4. `backend/diavgeia_project/settings.py` - Added `USE_ORCHESTRATOR_MODE=True`
5. `backend/core/signals.py` - Wrapped 3 signals with feature flag check
6. `backend/core/signals/health_check_signals.py` - Wrapped 2 signals with check

### Admin Integration
7. `backend/admin_custom/views/documents/sync_status.py` - "Extract Selected" uses orchestrator
8. `backend/admin_custom/admin_classes/analytics.py` - ImportJob admin with health metrics

### Commands & Utilities
9. `backend/core/management/commands/test_single_decision.py` - Testing command
10. `backend/core/management/commands/run_decision_pipeline.py` - Batch processing

### Documentation
11. `docs/single-decision-processing.md` - Complete guide for single decision
12. `docs/signal-task-conflict-analysis.md` - Detailed conflict analysis
13. `docs/orchestrator-migration-guide.md` - Migration instructions
14. `docs/decision-ingestion-single-source-of-truth.md` - Batch import guide

---

## Test It Now

```bash
# 1. Pick a decision ADA from your database
python manage.py test_single_decision "Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ" --force

# Or via admin UI:
# → /api/admin/sync-status/
# → Select a decision
# → Click "Extract Selected"
# → Check /api/admin/core/decisionhealthcheck/ for results
```

**Expected output:**
```
================================================================================
🔧 Testing Pipeline for Decision: Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ
================================================================================

📊 Overall Status: ✅ HEALTHY

Component Status:
--------------------------------------------------------------------------------
   ✅ Ingestion                  HEALTHY
   ✅ Entity Extraction          HEALTHY
   ✅ Company Enrichment         HEALTHY
   ✅ Document Processing        HEALTHY
   ✅ OpenSearch Indexing        HEALTHY
   ✅ Coverage Metrics           HEALTHY
--------------------------------------------------------------------------------
```

---

## Summary

✅ **ONE task for single decision:** `run_decision_pipeline_task`  
✅ **ALL 6 stages complete:** Entities, companies, documents, opensearch, coverage  
✅ **Signals disabled:** No double processing when orchestrator mode ON  
✅ **Full visibility:** DecisionHealthCheck with component-level status  
✅ **Admin UI integrated:** Sync status page uses orchestrator  
✅ **Feature flag:** `USE_ORCHESTRATOR_MODE=True` (default)  
✅ **Rollback ready:** Set to `False` to re-enable signals  

**You now have exactly what you asked for:** A central, transparent, controllable way to process decisions through all stages! 🎯
