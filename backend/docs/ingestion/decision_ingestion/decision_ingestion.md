# Decision Ingestion Pipeline Documentation

This document describes the end-to-end process for ingesting, processing, and indexing decisions in the crati platform. It includes references to the relevant code, signals, Celery tasks, and admin endpoints.

---

## Overview

The decision ingestion pipeline is responsible for:

- Fetching decisions from external sources (e.g., Diavgeia)
- Importing decisions into the database
- Triggering document processing and entity extraction
- Indexing processed documents in OpenSearch
- Providing admin interfaces for manual and scheduled ingestion

---

## Pipeline Steps

### 1. Triggering Ingestion

**Manual Trigger:**
- Admins can trigger ingestion via the admin UI (`🔄 Fetch Day` button)
- Endpoint: [`/api/admin/decisions/fetch-daily/`](core/admin_views.py#L1)
- URL mapping: [`path('decisions/fetch-daily/', core_admin_views.fetch_daily_decisions, name='fetch_daily_decisions')`](api/admin.py)

**Scheduled Trigger:**
- Celery Beat schedules periodic ingestion tasks
- See [`backend/diavgeia_project/celery.py`](diavgeia_project/celery.py)
    - Example: `daily-decisions-sync` runs at 2:30 AM daily

---

### 2. Fetching Decisions

- Service: [`DecisionIngestionService`](core/services/decision_ingestion_service.py)
- Fetches decisions from Diavgeia using [`DiavgeiaClient`](diavgeia_api/client.py)
- Logs show initialization and fetch parameters:
    - `Initialized DecisionIngestionService with delay: ...`
    - `Fetching all decisions for ...`
    - `search_decisions: ...`

---

### 3. Importing Decisions

- Importer: [`DecisionImporter`](core/importers/decisions.py)
- Saves decisions to the database
- Handles entity extraction:
    - `Extracted 0 entities from decision ...`
- Signals are fired after each decision is saved

---

### 4. Signals and Coverage Updates

- Signals: [`backend/core/signals.py`](core/signals.py)
- Coverage updates:
    - [`update_organization_coverage`](core/signals.py)
    - [`update_signer_coverage`](core/signals.py)
    - [`update_coverage_on_delete`](core/signals.py)
- Metrics are recorded for each signal event

---

### 5. Document Processing (Celery)

- Signal: [`queue_document_processing`](core/signals.py)
    - Uses `transaction.on_commit` to queue document processing only after DB commit
    - `process_document_task.delay(instance.ada)`
    - Log: `Queued document processing for decision ... (will run after transaction commit)`
- Task: [`process_document_task`](core/tasks/tasks_documents.py)
    - Fetches decision by ADA
    - Processes document with [`DocumentAnalysisService`](core/services/document_processor.py)
    - Handles retries if decision is not found

---

### 6. Batch and Enhanced Processing

- Batch task: [`process_document_batch`](core/tasks/tasks_documents.py)
    - Uses Celery chord for batch processing
- Enhanced task: [`process_document_task_enhanced`](core/tasks/tasks_documents.py)
    - Adds OpenSearch indexing if extraction is completed
- Scheduled batch: [`process_documents_task`](core/tasks/tasks_documents.py)
    - Used by Celery Beat for daily/weekly processing

---

### 7. Indexing in OpenSearch

- Signal: [`index_document_in_opensearch`](core/signals.py)
    - Triggered when document extraction status is `COMPLETED`
    - Indexes document in OpenSearch
    - Log: `Auto-indexed document for decision ... in OpenSearch`

---

## Admin Endpoints and Views

- Admin endpoints are defined in [`api/admin.py`](api/admin.py)
- Key views:
    - `fetch_daily_decisions` (manual ingestion)
    - `coverage_explorer` (coverage by org/unit/signer)
    - `document_processing_dashboard` (processing status)
    - `organization_network` and `organization_org_chart` (visualizations)

---

## Celery Beat Schedule

- Defined in [`diavgeia_project/celery.py`](diavgeia_project/celery.py)
- Example tasks:
    - `daily-decisions-sync`: Syncs decisions daily
    - `process-new-documents`: Processes new documents daily
    - `process-missed-documents-weekly`: Catches missed documents weekly

---

## Error Handling and Reliability

- Use of `transaction.on_commit` in signals prevents race conditions
- Celery tasks have retry logic for transient errors
- Signal metrics and logging for monitoring

---

## Example Log Timeline

```
INFO | DecisionIngestionService: Initialized
INFO | Fetching all decisions for 2025-07-09
DEBUG | DiavgeiaClient: Search parameters...
DEBUG | DecisionImporter: Extracted 0 entities from decision ...
DEBUG | queue_document_processing: Queued document processing for decision ... (will run after transaction commit)
INFO | entity_extraction_service: Extracted 0 AFM entities from decision ...
```

---

## References

- [`core/services/decision_ingestion_service.py`](../core/services/decision_ingestion_service.py)
- [`core/importers/decisions.py`](../core/importers/decisions.py)
- [`core/signals.py`](../core/signals.py)
- [`core/tasks/tasks_documents.py`](../core/tasks/tasks_documents.py)
- [`diavgeia_project/celery.py`](../diavgeia_project/celery.py)
- [`api/admin.py`](../api/admin.py)

---

## Diagram

> See attached draw.io diagram for a visual overview of the pipeline (recommended to create and link here)

---

## Notes

- All tasks and signals are designed to be idempotent and robust against race conditions.
- For troubleshooting, check logs for signal metrics and Celery retries.
