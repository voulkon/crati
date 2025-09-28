# System Architecture & Data Flow Documentation

## Overview
This document maps the complete data processing pipeline from decision ingestion to full-text search indexing.

## 🔄 Complete Data Pipeline Flow

```
┌─────────────────────────┐    ┌─────────────────────────┐    ┌─────────────────────────┐
│ Admin/API Trigger       │───▶│ DecisionIngestionService │───▶│ fetch_daily_decisions   │
│ - calendar_bulk_import  │    │ - ensure_types_before   │    │ _to_pickle (Celery)     │
│ - ProcessDocumentsView  │    │ - fetch_all_decisions   │    │ - DiavgeiaFetcher       │
└─────────────────────────┘    └─────────────────────────┘    └─────────────────────────┘
                                                                              │
                                                               ┌─────────────▼─────────────┐
                                                               │ Pickle Files Created      │
                                                               │ - Full day decisions      │
                                                               │ - Split into chunks       │
                                                               └─────────────┬─────────────┘
                                                                              │
                                                               ┌─────────────▼─────────────┐
                                                               │ store_decisions_from      │
                                                               │ _pickle (Multiple Tasks)  │
                                                               │ - batch_size=1 (sequential)│
                                                               │ - DecisionImporter        │
                                                               └─────────────┬─────────────┘
                                                                              │
┌─────────────────────────┐    ┌─────────────────────────┐    ┌─────────────▼─────────────┐
│ OpenSearch Indexing     │◀───│ DocumentExtraction      │◀───│ Decision Saved to DB      │
│ - index_document_in_    │    │ post_save signal        │    │ - Entity extraction       │
│   opensearch (signal)   │    │ - if COMPLETED status   │    │ - Coverage updates        │
│ - OpenSearchService     │    │ - document_data prep    │    │ - Signal triggers         │
└─────────────────────────┘    └─────────────────────────┘    └─────────────┬─────────────┘
                                                                              │
┌─────────────────────────┐    ┌─────────────────────────┐    ┌─────────────▼─────────────┐
│ Document Processing     │◀───│ queue_document_         │◀───│ Decision post_save signal │
│ - process_document_task │    │ processing (signal)     │    │ - if created & has doc_url│
│ - DocumentAnalysisService│    │ - transaction.on_commit │    │ - @prevent_recursion      │
│ - Text extraction       │    │ - process_document_task │    └───────────────────────────┘
│ - Creates DocumentExtraction│ │   .delay()              │
└─────────────────────────┘    └─────────────────────────┘
```

## 📋 Service Dependencies & Flow Details

### 1. Decision Ingestion Chain
```python
# Entry Points:
api/custom_views/import_decisions.py:calendar_bulk_import()
    ↓
core/services/decision_ingestion_service.py:DecisionIngestionService
    ↓
core/tasks/tasks_decisions_import.py:fetch_daily_decisions_distributed()
    ↓
core/tasks/tasks_decisions_import.py:fetch_daily_decisions_to_pickle()
    ↓
core/tasks/tasks_decisions_import.py:store_decisions_from_pickle()
    ↓
core/importers/decisions.py:DecisionImporter.import_decision()
```

### 2. Signal-Driven Processing
```python
# Decision saved → Document processing queued
core/signals.py:queue_document_processing()
@receiver(post_save, sender=Decision)
    ↓
core/tasks/tasks_documents.py:process_document_task()
    ↓
core/services/document_processor.py:DocumentAnalysisService.process_decision()
    ↓
DocumentExtraction created/updated

# Document extraction completed → OpenSearch indexing
core/signals.py:index_document_in_opensearch()
@receiver(post_save, sender=DocumentExtraction)
    ↓
core/services/opensearch_service.py:OpenSearchService.index_document()
```

### 3. Parallel Processing Patterns
```python
# Chunked Processing (to prevent deadlocks)
fetch_daily_decisions_to_pickle():
    - chunk_size = 10 decisions per pickle
    - 3 second delay between storage tasks
    - batch_size = 1 (sequential processing)
    - Each chunk gets own store_decisions_from_pickle task

# Entity Processing
core/tasks/tasks_entities.py:
    - fetch_company_data_for_single_afm() (rate_limit="6/m")
    - fetch_company_data_for_entities()
    - process_entities_needing_company_data()
```

## 🔍 Key Services & Their Roles

### Core Services
- **DecisionIngestionService**: Orchestrates fetching from Diavgeia API
- **DiavgeiaFetcher**: Handles API calls, pagination, rate limiting
- **DecisionImporter**: Saves decisions, handles entity extraction
- **DocumentAnalysisService**: Orchestrates PDF processing and text extraction
- **OpenSearchService**: Handles full-text search indexing
- **EntityExtractionService**: Extracts AFM entities from decision content

### Celery Tasks
- **Decision Import**: `fetch_daily_decisions_*`, `store_decisions_from_pickle`
- **Document Processing**: `process_document_task*`, `process_documents_task*`
- **Entity Processing**: `fetch_company_data_*`, `process_entities_*`
- **OpenSearch**: `index_recent_documents`, `rebuild_opensearch_index`

### Django Signals
- **Decision Signals**: Coverage updates, document processing queueing
- **DocumentExtraction Signals**: OpenSearch indexing when extraction completes
- **Signal Protection**: `@prevent_recursion` decorator to avoid loops

## 🧪 Critical Integration Points

### 1. Database Transaction Coordination
```python
# Signals use transaction.on_commit() to ensure tasks run after DB commits
transaction.on_commit(lambda: process_document_task.delay(instance.ada))
```

### 2. Status State Management
```python
# Processing statuses must be coordinated:
ProcessingStatus.PENDING → PROCESSING → COMPLETED/FAILED/NEEDS_VISION
# OpenSearch indexing only triggers on COMPLETED status
```

### 3. External Service Dependencies
- **Diavgeia API**: Rate limiting, pagination, data format changes
- **OpenSearch**: Connection health, indexing success/failure
- **Redis/RabbitMQ**: Queue management, task distribution
- **External AI Services**: For OCR, text analysis (Google Vision, OpenAI, etc.)

## 🔧 Configuration Points
- Chunk sizes, delays, retry policies in tasks
- Signal enablement flags and batch sizes
- OpenSearch index configuration
- Celery concurrency and routing
- API rate limiting and timeouts

This architecture handles high-volume data ingestion with fault tolerance, but requires careful orchestration for testing and monitoring.