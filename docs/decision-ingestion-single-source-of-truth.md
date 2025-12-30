# Decision Ingestion - Single Source of Truth

## Overview

Your **single source of truth** for ingesting decisions is the `import_decisions_daily` management command, which now automatically creates `ImportJob` records for full batch observability.

## Entry Points (All lead to the same command)

### 1. Admin UI (Recommended) ✅
**Path:** Admin → Decision Management → Daily Decision Analysis → "Fetch Daily Decisions" button

**Flow:**
```
Admin UI (/api/admin/decisions/fetch-daily/)
    ↓
fetch_daily_decisions view
    ↓
call_command('import_decisions_daily', ...)
    ↓
Creates ImportJob automatically
    ↓
Imports decisions linked to ImportJob
```

**Returns:**
- ImportJob ID
- Link to view batch in admin
- Processed count
- Log file location

### 2. Management Command (Direct)
```bash
# Yesterday's decisions (default)
python manage.py import_decisions_daily

# Specific date
python manage.py import_decisions_daily --date 2024-12-29

# With reconciliation
python manage.py import_decisions_daily --date 2024-12-29 --reconcile

# Distributed (for large batches)
python manage.py import_decisions_daily --date 2024-12-29 --distributed
```

### 3. Celery Task (Advanced)
```python
from core.tasks import import_decisions_task

# For programmatic imports
import_decisions_task.delay(
    start_date='2024-12-29',
    end_date='2024-12-29',
    job_id=<existing_job_id>  # Optional
)
```

## What Happens Automatically

Every time you run `import_decisions_daily`, it now:

1. **Creates ImportJob record** (`status=RUNNING`)
2. **Links all imported decisions** to that ImportJob via `Decision.import_job` FK
3. **Updates job status** on completion:
   - `COMPLETED` with counts
   - `FAILED` with error details
4. **Enables batch observability**:
   - View in Admin → ImportJob list
   - See healthy/warning/error counts
   - Drill down into failures
   - Download health reports
   - Retry failed decisions

## Batch Observability Dashboard

After import completes, go to:
**Admin → Import Jobs** (or `/api/admin/core/importjob/`)

You'll see:
- **Decisions**: Total count
- **No health check**: Decisions not yet processed by pipeline
- **Healthy/Warnings/Errors/Unknown**: Health breakdown
- **Health %**: Overall batch health percentage
- **Links**: Drill down into specific failures or warnings

## Actions Available

### On ImportJob List
1. **Download batch health report (JSON)** - Get detailed failure analysis
2. **Backfill missing health checks (async)** - Run pipeline for decisions that weren't processed
3. **Retry ERROR decisions (async)** - Re-run failed steps for all errors in batch

### Via Management Command
```bash
# Process all decisions in a batch through the full pipeline
python manage.py run_decision_pipeline --import-job-id 1847 --workers 10

# Retry only failed decisions
python manage.py run_decision_pipeline --import-job-id 1847 --failed-only
```

## Decision Processing Pipeline

Once decisions are imported, they go through:

1. **Ingestion** ✅ (done by import_decisions_daily)
2. **Entity Extraction** (AFM detection)
3. **Company Enrichment** (GEMI lookup)
4. **Document Processing** (PDF download + text extraction)
5. **OpenSearch Indexing** (make searchable)
6. **Coverage Metrics** (DateCoverage updates)

**Status tracked in:** `DecisionHealthCheck` model per decision

## Monitoring & Troubleshooting

### Check Import Status
```bash
# View recent ImportJobs
python manage.py shell
>>> from core.models.import_jobs import ImportJob
>>> ImportJob.objects.order_by('-created_at')[:5]
```

### Investigate Failures
1. Admin → ImportJob list → find your batch
2. Click "View N failed" link
3. Opens DecisionHealthCheck filtered to errors
4. Each health check shows which component failed

### Retry Failures
**Option A: Admin UI**
- Select ImportJob → Actions → "Retry ERROR decisions (async)"

**Option B: Command Line**
```bash
python manage.py run_decision_pipeline --import-job-id 1847 --failed-only
```

## Migration Required

Before using batch observability, run:
```bash
python manage.py migrate
```

This adds the `Decision.import_job` foreign key field (migration `0029_decision_import_job.py`).

## Key Files

- **Command**: `backend/core/management/commands/import_decisions_daily.py`
- **Admin View**: `backend/admin_custom/views/decisions/decisions_fetching.py`
- **Orchestrator**: `backend/core/services/pipeline_orchestrator.py`
- **ImportJob Admin**: `backend/admin_custom/admin_classes/analytics.py`
- **Tasks**: `backend/core/tasks/health_check_tasks.py`

## Recommendations

1. **Always use `import_decisions_daily`** - It's your single source of truth
2. **Check ImportJob admin after each import** - Verify batch health
3. **Use retry actions for failures** - Don't re-import, just retry failed steps
4. **Monitor health percentages** - Alert if < 95% healthy
5. **Download health reports for investigation** - Better than log diving

## Example Workflow

```bash
# 1. Import yesterday's decisions
python manage.py import_decisions_daily --reconcile

# Output:
# ImportJob #1847 created for tracking
# ✅ ImportJob #1847: View in admin for batch health status

# 2. Check admin UI
# Navigate to: Admin → Import Jobs
# See: ImportJob #1847 | Health: 91.2% | Errors: 50

# 3. Investigate failures
# Click "View 50 failed" → opens DecisionHealthCheck list

# 4. Retry failures
# Select ImportJob #1847 → Actions → "Retry ERROR decisions (async)"

# 5. Verify fix
# Refresh ImportJob list → see updated health percentage
```

---

**Bottom Line:** Use `import_decisions_daily` (via admin UI or command line). It automatically creates ImportJob records and links decisions, giving you full batch-level observability without any extra work.
