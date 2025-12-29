# Decision Ingestion Pipeline Documentation

This document outlines the current processes involved in ingesting and processing decisions in the Crati system.

## Overview

The ingestion process consists of several distinct stages, triggered by a mix of explicit service calls and Django signals.

### 1. Decision Ingestion (The Entry Point)
- **Trigger:** `fetch_decisions_for_increment` (Celery Task) or `fetch_decisions_for_period` (Service Call).
- **Service:** `DecisionIngestionService` -> `DecisionImporter`.
- **Action:** Fetches decision metadata from the Diavgeia API and saves it to the PostgreSQL database.
- **Key Files:**
    - `backend/core/tasks/tasks_decisions.py`
    - `backend/core/services/decision_ingestion_service.py`
    - `backend/core/importers/decisions.py`

### 2. Entity Extraction (Synchronous during Import)
- **Trigger:** Called explicitly within `DecisionImporter.import_decisions`.
- **Service:** `AFMExtractionService`.
- **Action:** Parses the decision metadata (JSON) to find AFM numbers and creates `AFMEntity` and `DecisionEntityRelationship` records.
- **Key Files:**
    - `backend/core/importers/decisions.py`
    - `backend/core/services/afm_extractor.py`

### 3. Company Data Enrichment (Asynchronous Task)
- **Trigger:** Called explicitly at the end of `DecisionImporter.import_decisions` via `_trigger_company_data_fetching`.
- **Task:** `fetch_company_data_for_entities` (Celery Task).
- **Service:** `EntityExtractionService` -> `GemiService`.
- **Action:** Fetches company details from the GEMI registry for the extracted AFMs.
- **Key Files:**
    - `backend/core/importers/decisions.py`
    - `backend/core/tasks/tasks_entities.py`
    - `backend/core/services/entity_extraction_service.py`

### 4. Document Processing (Asynchronous Task via Signal)
- **Trigger:** `post_save` signal on `Decision` model (`queue_document_processing`).
- **Task:** `process_document_task` (Celery Task).
- **Service:** `DocumentAnalysisService`.
- **Action:** Downloads the PDF from the `document_url`, extracts text using PyMuPDF or Docling, and saves it to `DocumentExtraction`.
- **Key Files:**
    - `backend/core/signals.py`
    - `backend/core/tasks/tasks_documents.py`
    - `backend/core/services/document_processor.py`

### 5. OpenSearch Indexing (Asynchronous via Signal)
- **Trigger:** `post_save` signal on `DocumentExtraction` model (`index_document_in_opensearch`).
- **Service:** `OpenSearchService`.
- **Action:** Indexes the extracted text and decision metadata into OpenSearch.
- **Key Files:**
    - `backend/core/signals.py`
    - `backend/core/services/opensearch_service.py`

### 6. Coverage Metrics (Synchronous via Signal)
- **Trigger:** `post_save` signal on `Decision` model (`update_organization_coverage`).
- **Action:** Updates the `DateCoverage` model to track the number of decisions per organization/signer/date.
- **Key Files:**
    - `backend/core/signals.py`

## Current Visibility & Monitoring

- **DecisionHealthCheck:** A model intended to track the status of these steps (`ingestion_status`, `document_extraction_status`, etc.).
- **SyncStatus:** Tracks the last sync timestamp.
- **Logs:** Distributed across Celery workers and Django logs.

## Pain Points

- **Distributed Logic:** The flow is split between explicit calls and signals, making it hard to trace a single decision's journey.
- **Error Visibility:** Failures in signals (e.g., OpenSearch indexing) might not be immediately visible or linked back to the decision's main status.
- **Orchestration:** There is no central "manager" that ensures all steps complete successfully.

## Proposed Solution: Pipeline Orchestrator

A centralized `DecisionPipelineOrchestrator` that:
1.  Manages the lifecycle of a decision.
2.  Explicitly triggers steps (removing reliance on implicit signals where appropriate, or monitoring them).
3.  Updates a central `DecisionHealthCheck` record with detailed status and errors.
4.  Provides a mechanism to retry failed steps.
