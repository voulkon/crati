# Decision Processing - Single Source of Truth

## Problem Statement

**Before:** Processing a single decision was scattered across multiple places:
- `process_document_task` - only handled document extraction
- `process_document_task_enhanced` - document + opensearch
- Entity extraction happened via signals (unreliable)
- Company enrichment happened separately
- OpenSearch indexing via signals (could fail silently)
- **No way to know if ALL steps completed for a decision**

**Result:** Impossible to debug when something broke. No central place to see "this decision failed at step X".

## Solution: DecisionPipelineOrchestrator

### 🎯 Single Source of Truth

**For ONE decision, use:**
```python
from core.tasks.tasks_documents import run_decision_pipeline_task

# Async (recommended)
run_decision_pipeline_task.delay(ada="Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ", force_reprocess=True)

# Synchronous (for testing)
from core.services.pipeline_orchestrator import DecisionPipelineOrchestrator
orchestrator = DecisionPipelineOrchestrator()
health_check = orchestrator.run_pipeline("Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ", force_reprocess=True)
```

### What It Does (All 6 Steps)

1. **✅ Ingestion** - Verifies decision exists in DB
2. **🔍 Entity Extraction** - Finds AFMs in text using AFMExtractionService
3. **🏢 Company Enrichment** - Looks up companies in GEMI using EntityExtractionService
4. **📄 Document Processing** - Downloads PDF, extracts text using DocumentAnalysisService
5. **🔎 OpenSearch Indexing** - Makes decision searchable using OpenSearchService
6. **📊 Coverage Metrics** - Updates DateCoverage statistics

### Result: DecisionHealthCheck

Each step's status is tracked:
- `ingestion_status`: HEALTHY/ERROR
- `entities_status`: HEALTHY/WARNING/ERROR
- `relations_status`: HEALTHY/ERROR
- `document_extraction_status`: HEALTHY/ERROR
- `opensearch_status`: HEALTHY/ERROR
- `coverage_status`: HEALTHY/ERROR

Plus error messages for each component:
- `entities_error_message`
- `document_extraction_error_message`
- etc.

## How to Use It

### 1. Admin UI (Recommended)

**Location:** Admin → Sync Status Dashboard (`/api/admin/sync-status/`)

**Steps:**
1. Navigate to sync status page
2. Select decisions you want to process
3. Choose "Extract Selected" button
4. This now calls `run_decision_pipeline_task` (not just documents!)

**What happens:**
- Each selected decision goes through ALL 6 stages
- Creates/updates DecisionHealthCheck with component-level status
- View results in: Admin → Decision Health Checks

### 2. Management Command (Testing)

```bash
# Test a single decision synchronously
python manage.py test_single_decision "Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ"

# Force reprocess everything
python manage.py test_single_decision "Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ" --force

# Run as Celery task (async)
python manage.py test_single_decision "Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ" --async
```

**Output shows:**
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

### 3. Programmatically (Python)

```python
from core.tasks.tasks_documents import run_decision_pipeline_task

# Queue for async processing
result = run_decision_pipeline_task.delay(
    ada="Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ",
    force_reprocess=True
)

print(f"Task ID: {result.id}")

# Wait for result (blocking)
health_status = result.get(timeout=300)
print(f"Overall status: {health_status['overall_status']}")
print(f"Components: {health_status['components']}")
```

## Batch Processing

For processing **multiple decisions** in a batch:

### Option A: Via ImportJob (for daily imports)

```bash
# Import decisions - creates ImportJob automatically
python manage.py import_decisions_daily --date 2024-12-29

# Process all decisions in the batch through pipeline
python manage.py run_decision_pipeline --import-job-id 1847 --workers 10
```

### Option B: Via Admin UI

**Location:** Admin → Import Jobs

**Steps:**
1. Find your ImportJob (created by import_decisions_daily)
2. Select it
3. Actions → "Backfill missing health checks (async)"
   - Processes all decisions that don't have DecisionHealthCheck
4. Actions → "Retry ERROR decisions (async)"
   - Retries only failed decisions

## Monitoring & Troubleshooting

### Check Health Status

**Admin → Decision Health Checks**

Filter by:
- Overall status: ERROR, WARNING, HEALTHY
- Specific component status (e.g., document_extraction_status = ERROR)
- Decision ADA
- Date range

### Find Failures for a Batch

**Admin → Import Jobs** → Select batch → Click "View N failed"

Shows all DecisionHealthCheck records with ERROR status for that batch.

### Retry Individual Decision

```bash
# Retry specific component
python manage.py test_single_decision "Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ" --force

# Or via Python
from core.services.pipeline_orchestrator import DecisionPipelineOrchestrator
orchestrator = DecisionPipelineOrchestrator()
orchestrator.retry_failed_step("Ψ9ΞΙ46ΜΠ3Ω-ΨΘΛ", component="documents")
```

### Retry All Failures in Batch

```bash
# Via command line
python manage.py run_decision_pipeline --import-job-id 1847 --failed-only

# Or via admin UI
# Admin → Import Jobs → Select batch → Actions → "Retry ERROR decisions"
```

## Architecture Summary

### Before (Scattered)
```
Decision Import
    ↓
process_document_task (only documents)
    ↓
Signal fires (maybe?) → opensearch indexing
    ↓
Signal fires (maybe?) → entity extraction
    ↓
Task runs separately → company enrichment

❌ No visibility
❌ Can't track if all completed
❌ No error messages per component
```

### After (Orchestrated)
```
run_decision_pipeline_task
    ↓
DecisionPipelineOrchestrator.run_pipeline()
    ↓
    ├─ 1. Ingestion (verify)
    ├─ 2. Entity Extraction (AFMs)
    ├─ 3. Company Enrichment (GEMI)
    ├─ 4. Document Processing (PDF + text)
    ├─ 5. OpenSearch Indexing (search)
    └─ 6. Coverage Metrics (stats)
    ↓
DecisionHealthCheck (component-level status)

✅ Full visibility
✅ Track each step's success/failure
✅ Error messages per component
✅ Can retry specific components
```

## Migration Path

### Old Code (Deprecated)
```python
from core.tasks.tasks_documents import process_document_task_enhanced
process_document_task_enhanced.delay(ada)  # Only does documents!
```

### New Code (Use This)
```python
from core.tasks.tasks_documents import run_decision_pipeline_task
run_decision_pipeline_task.delay(ada, force_reprocess=True)  # Does ALL 6 steps!
```

### Already Updated

✅ **sync_status_dashboard** - "Extract Selected" now uses orchestrator
✅ **Admin UI** - Buttons call the full pipeline
✅ **ImportJob admin** - "Backfill health checks" uses orchestrator

### Still Using Old Tasks (OK for now)

These still use `process_document_task` for bulk operations:
- Daily scheduled tasks for document processing
- Bulk reindex operations

**Recommendation:** Eventually migrate these to use orchestrator's batch methods:
- `DecisionPipelineOrchestrator.run_batch_pipeline(import_job_id)`

## Key Files

| File | Purpose |
|------|---------|
| `core/services/pipeline_orchestrator.py` | Main orchestrator class |
| `core/tasks/tasks_documents.py` | `run_decision_pipeline_task` - Celery wrapper |
| `core/management/commands/test_single_decision.py` | Testing command |
| `admin_custom/views/documents/sync_status.py` | Admin UI integration |
| `core/models/decision_health.py` | DecisionHealthCheck model |

## Quick Reference

```bash
# Test single decision
python manage.py test_single_decision "ADA_HERE"

# Process batch
python manage.py run_decision_pipeline --import-job-id 1847

# Retry failures
python manage.py run_decision_pipeline --import-job-id 1847 --failed-only

# Import + Process
python manage.py import_decisions_daily --date 2024-12-29
python manage.py run_decision_pipeline --import-job-id 1847 --workers 10
```

---

**Bottom Line:** 
- ONE decision → use `run_decision_pipeline_task`
- BATCH of decisions → use `run_batch_pipeline` or ImportJob admin actions
- ALL 6 stages complete
- Full visibility in DecisionHealthCheck
- Component-level retry capability
