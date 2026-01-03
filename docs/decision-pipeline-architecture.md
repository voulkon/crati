# Decision Processing Pipeline Architecture

**Last Updated:** 2026-01-04  
**Version:** 2.0

## Table of Contents
1. [Overview](#overview)
2. [Pipeline Flow](#pipeline-flow)
3. [Core Components](#core-components)
4. [Task Orchestration](#task-orchestration)
5. [Data Flow](#data-flow)
6. [Observability & Debugging](#observability--debugging)
7. [Architectural Decisions](#architectural-decisions)
8. [Refactoring History](#refactoring-history)
9. [Future Improvements](#future-improvements)

---

## Overview

The decision processing pipeline is designed to handle high-volume government decisions from the Diavgeia API. The architecture follows a **distributed task-based approach** with a central orchestrator to ensure all processing stages complete successfully while providing full observability.

### Key Design Principles

1. **Single Source of Truth**: `run_decision_pipeline_task` is the ONLY entry point for processing a decision through the full pipeline
2. **Unified Orchestrator**: `DecisionPipelineOrchestrator` handles the COMPLETE lifecycle of a decision (import → process)
3. **Distributed Processing**: Work is split across multiple Celery workers to handle high volume
4. **Observability First**: Every decision gets a unique `ingestion_id` for end-to-end tracing in Grafana/Loki
5. **Health Tracking**: `DecisionHealthCheck` model tracks completion status of each pipeline stage
6. **Deadlock Prevention**: Small chunk sizes (10 decisions) with sequential processing to avoid database deadlocks

### Architecture Evolution (v2.0 - 2026-01-04)

**Major Refactoring:**
- Moved decision import logic from `store_decisions_from_pickle` to `DecisionPipelineOrchestrator._step_import_decision`
- Moved organization resolution from `DecisionImporter` to `DecisionPipelineOrchestrator._step_resolve_organizations`
- Added `import_status` and `organization_status` to `DecisionHealthCheck` model
- Simplified `store_decisions_from_pickle` to be a pure dispatcher
- `DecisionImporter` now focuses ONLY on data mapping (DTO → Model)

**Benefits:**
- Clearer separation of concerns
- Unified health tracking for all pipeline stages
- Better error handling and retry logic
- Single responsibility for orchestrator

---

## Pipeline Flow

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PHASE 1: FETCH                              │
│  fetch_daily_decisions_to_pickle()                                  │
│  └─ Fetches ALL decisions for a full day from Diavgeia API          │
│  └─ Saves to pickle file (decisions_YYYY-MM-DD_HHMMSS.pkl)          │
│  └─ Splits into chunks of 10 decisions                              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         PHASE 2: STORAGE                            │
│  store_decisions_from_pickle()                                      │
│  └─ Loads decisions from pickle chunk                               │
│  └─ Calls orchestrator._step_import_decision for each decision      │
│  └─ Dispatches pipeline tasks for each decision                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         PHASE 3: PIPELINE                           │
│  run_decision_pipeline_task() → DecisionPipelineOrchestrator        │
│  └─ Stage 0: Import Decision (DTO → Database)                       │
│  └─ Stage 1: Organization Resolution (signers & units)              │
│  └─ Stage 2: Entity Extraction (AFM detection)                      │
│  └─ Stage 3: Amount Extraction (from extra fields)                  │
│  └─ Stage 4: Company Enrichment (GEMI lookup)                       │
│  └─ Stage 5: Document Processing (PDF + text extraction)            │
│  └─ Stage 6: OpenSearch Indexing (make searchable)                  │
│  └─ Stage 7: Coverage Metrics (DateCoverage updates)                │
└─────────────────────────────────────────────────────────────────────┘
```

### Detailed Flow

#### Phase 1: Fetch Decisions

**Task:** `fetch_daily_decisions_to_pickle`  
**Location:** `core/tasks/tasks_decisions_import.py`

```python
@shared_task(bind=True, max_retries=3)
def fetch_daily_decisions_to_pickle(self, target_date_str: str, 
                                   search_params: Optional[Dict[str, Any]] = None)
```

**Responsibilities:**
- Fetches ALL decisions for a full day from Diavgeia API (no hourly queries supported)
- Paginates through all results (default page size: 500)
- Saves complete dataset to pickle file: `pickles/decisions_{date}_{timestamp}.pkl`
- Splits into chunks of 10 decisions to prevent deadlocks
- Creates chunk-specific pickle files: `pickles/chunk_{chunk_id}_{timestamp}.pkl`
- Dispatches `store_decisions_from_pickle` tasks with 3-second delays between each

**Pickle File Structure:**
```python
{
    'decisions': List[DecisionDTO],      # All decisions for the day
    'target_date': str,                  # ISO format date
    'search_params': Dict,               # API parameters used
    'fetch_timestamp': str,              # ISO format timestamp
    'task_id': str,                      # Celery task ID
    'count': int                         # Total decisions fetched
}
```

**Chunk Pickle Structure:**
```python
{
    'decisions': List[DecisionDTO],      # Subset of decisions (max 10)
    'chunk_id': str,                     # Unique chunk identifier
    'parent_task': str,                  # Parent fetch task ID
    'target_date': str,                  # Original target date
    'chunk_index': int,                  # Chunk sequence number
    'count': int                         # Decisions in this chunk
}
```

---

#### Phase 2: Store Decisions

**Task:** `store_decisions_from_pickle`  
**Location:** `core/tasks/tasks_decisions_import.py`

```python
@shared_task(bind=True, max_retries=5)
def store_decisions_from_pickle(self, pickle_file: str, batch_size: int = 25, 
                               skip_opensearch: bool = False)
```

**Responsibilities:**
- Loads decisions from pickle chunk
- **Simplified:** Calls `orchestrator._step_import_decision()` for each decision (Stage 0)
- **Dispatches:** `run_decision_pipeline_task` for each successfully imported decision
- Moves pickle to `completed/` or `failed/` directory based on result
- Implements aggressive retry logic for database errors (deadlock detection)

**Architecture Note (v2.0):**
> This task is now a simple dispatcher. The actual import logic has been moved to `DecisionPipelineOrchestrator._step_import_decision()` to provide unified health tracking and better error handling.

**Retry Strategy:**
- Database errors (deadlock, lock, transaction): 20s × 3^retries (20s, 60s, 180s, 540s, 1620s)
- Always retries with `batch_size=1` (sequential processing)
- Non-database errors: 30s × 2^retries with halved batch size

**Deadlock Prevention:**
- Processes decisions one-by-one in transaction.atomic blocks
- On deadlock: fails fast, retries with exponential backoff
- Chunk size of 10 limits concurrent database operations

---

#### Phase 3: Pipeline Processing

**Task:** `run_decision_pipeline_task`  
**Location:** `core/tasks/tasks_documents.py`

```python
@shared_task(bind=True, max_retries=3)
def run_decision_pipeline_task(self, ada: str, force_reprocess: bool = False, 
                              skip_opensearch: bool = False)
```

**Responsibilities:**
- **SINGLE SOURCE OF TRUTH** for decision processing
- Generates unique `ingestion_id` for log tracing
- Calls `DecisionPipelineOrchestrator.run_pipeline`
- Returns comprehensive health check results
- Implements retry logic with 60s backoff

**Contextual Logging:**
```python
with logger.contextualize(
    task_id=task_id,
    ada=ada,
    task_name="run_decision_pipeline_task",
    force_reprocess=force_reprocess
):
    # All logs in this context include these fields
    # Filter in Grafana: {component="celery"} | json | record.extra.task_id="abc-123"
```

---

## Core Components

### DecisionPipelineOrchestrator

**Location:** `core/services/pipeline_orchestrator.py`

**Purpose:** Central orchestrator that ensures ALL pipeline stages complete for a decision.

**Architecture Note (v2.0):**
> The orchestrator now handles the COMPLETE lifecycle of a decision:
> - Stage 0: Import decision from DTO to database (moved from store_decisions_from_pickle)
> - Stage 1: Resolve organizations for signers and units (moved from DecisionImporter)
> - Stages 2-7: Entity extraction, amounts, companies, documents, opensearch, coverage
> 
> This provides unified health tracking and better error handling for all stages.

**Key Methods:**

#### `run_pipeline(decision_ada, force_reprocess, skip_opensearch)`

Main entry point for processing a single decision.

**Stages:**

0. **Import Decision** (`_step_import_decision`) - **NEW in v2.0**
   - Imports decision from DTO to database
   - Uses `DecisionImporter.import_many`
   - Creates/updates Decision record with all relations
   - Tracks `import_status` in health check
   
1. **Organization Resolution** (`_step_resolve_organizations`) - **NEW in v2.0**
   - Resolves organizations for signers and units
   - Traverses parent chains to find organizations
   - Creates default organizations if resolution fails
   - Tracks `organization_status` in health check
   - Moved from `DecisionImporter` for better health tracking
   
2. **Entity Extraction** (`_step_extract_entities`)
   - Extracts AFMs from decision text
   - Creates `DecisionEntityRelationship` records
   - Uses `AFMExtractionService`
   
3. **Amount Extraction** (`_step_extract_amounts`)
   - Extracts financial amounts from extra fields
   - Creates `DecisionAmountField` records
   - Links amounts to entity relationships
   
4. **Company Enrichment** (`_step_enrich_companies`)
   - Identifies entities needing GEMI lookup
   - Checks Redis locks to prevent duplicate processing
   - Dispatches `fetch_company_data_for_entities` task
   - Uses `AFM_FETCH_LOCK_PREFIX` for distributed locking
   
5. **Document Processing** (`_step_process_document`)
   - Downloads PDF from `document_url`
   - Extracts text using OCR (Google Vision / Tesseract)
   - Creates `DocumentExtraction` record
   - Uses `DocumentAnalysisService`
   
6. **OpenSearch Indexing** (`_step_index_opensearch`)
   - Checks if already indexed
   - Builds document data dict
   - Indexes to OpenSearch
   - Uses `OpenSearchService`
   
7. **Coverage Verification** (`_step_verify_coverage`)
   - Updates `DateCoverage` metrics
   - Tracks decision dates for coverage reporting

**Health Tracking:**
- Creates/updates `DecisionHealthCheck` record
- Tracks status of each component: `import_status`, `organization_status`, `ingestion_status` (legacy), `entities_status`, `relations_status`, `document_extraction_status`, `opensearch_status`, `coverage_status`
- Calculates `overall_status` (HEALTHY, WARNING, ERROR, UNKNOWN)
- Stores error messages in `findings` dict

**Logging:**
- Generates unique `ingestion_id` (8-char UUID prefix)
- All logs include `ingestion_id` and `ada` for filtering
- Uses separator lines for visual clarity in logs

#### `run_batch_pipeline(import_job_id, max_workers, stop_on_error, force_reprocess, skip_opensearch)`

Processes all decisions in an `ImportJob` with parallel execution.

**Features:**
- Uses `ThreadPoolExecutor` for parallel processing
- Controlled concurrency (default: 10 workers)
- Collects detailed results and statistics
- Generates batch summary
- Tracks processing times

#### `retry_failed_step(decision_ada, component, force)`

Retries a specific failed component for a decision.

**Supported Components:**
- `amounts` - Amount extraction
- `entities` - Entity extraction
- `companies` - Company enrichment
- `document` - Document processing
- `opensearch` - OpenSearch indexing
- `coverage` - Coverage metrics

#### `retry_batch_failures(import_job_id, component, max_workers)`

Retries all failures in a batch, optionally for a specific component.

---

### DecisionImporter

**Location:** `core/importers/decisions.py`

**Purpose:** Imports decision data from Diavgeia API DTOs to the database.

**Architectural Note (2026-01-03):**
> This importer now focuses ONLY on importing decision data (basic fields, relations, attachments). Entity extraction, company enrichment, document processing, and indexing are handled by `DecisionPipelineOrchestrator` to prevent task bursts and provide better control.

**Key Methods:**

#### `import_many(dtos)`

Imports multiple decisions in a single transaction.

**Field Mapping:**
- Uses `field_map` for DTO → Model field name conversion
- Handles special fields separately: `organizationId`, `signerIds`, `unitIds`, `attachments`, `extraFieldValues`, `decisionTypeId`
- Skips auto-managed fields: `created_at`, `id`

**Special Handling:**
- **Organization:** Looks up or fetches from API, caches in `org_cache`
- **Signers:** Looks up or fetches from API, creates M2M relationships
- **Units:** Looks up or fetches from API, resolves organization through parent chain
- **Attachments:** Syncs attachment records (1-M relationship)
- **KAE Amounts:** Syncs `DecisionAmountKAE` records from extra fields
- **Extra Fields:** Extracts promoted fields (financial_year, amount, currency) + stores raw JSON

**Architecture Note (v2.0):**
> Organization resolution methods (`_resolve_unit_organization_through_parents`, `_resolve_signer_organization`) have been moved to `DecisionPipelineOrchestrator._step_resolve_organizations()` for better health tracking. These methods are still available on the importer for backward compatibility and are called by the orchestrator.

**Organization Resolution (Legacy - Now in Orchestrator):**

#### `_resolve_unit_organization_through_parents(unit_id, fetcher, max_depth, visited)`

Resolves organization ID for a unit by traversing up the parent chain.

**Features:**
- Checks database first, then API
- Handles cases where IDs might be orgs instead of units
- Returns resolution path for auditing
- Prevents infinite loops with `visited` set
- Max depth: 5 levels

**Resolution Path Structure:**
```python
{
    "unit_id": str,
    "path": List[Dict],  # Each step: {"unit_id": str, "org_id": Optional[str]}
    "result": str,       # "found", "max_depth_reached", "cycle_detected", "error"
    "timestamp": str
}
```

#### `_resolve_signer_organization(signer_id, fetcher, max_depth, visited)`

Resolves organization for a signer by checking units they belong to.

**Features:**
- Fetches signer from API
- Iterates through signer's units
- Resolves organization for each unit
- Returns first valid organization found
- Tracks resolution path for auditing

#### `_ensure_organization_exists(org_id, org_dto)`

Ensures organization exists in database, importing if necessary.

**Features:**
- Checks `org_cache` first
- Creates organization if not exists
- Caches for future lookups

#### `_ensure_default_organization(entity_type, entity_id)`

Creates default organization for entities without resolvable organizations.

**Default Org UID Format:** `DEFAULT_{ENTITY_TYPE}_ORG`

---

### DecisionHealthCheck

**Location:** `core/models/decision_health.py`

**Purpose:** Tracks completion status of each pipeline stage for a decision.

**Fields:**
- `decision` - FK to Decision
- `decision_issue_date` - Date field for filtering
- `overall_status` - HEALTHY, WARNING, ERROR, UNKNOWN
- `ingestion_status` - Status of ingestion stage
- `import_status` - Status of decision import from DTO (NEW in v2.0)
- `organization_status` - Status of organization resolution (NEW in v2.0)
- `ingestion_status` - Status of ingestion check (legacy field, kept for backward compatibility)
- `relations_status` - Status of company enrichment
- `entities_status` - Status of entity extraction
- `document_extraction_status` - Status of document processing
- `opensearch_status` - Status of OpenSearch indexing
- `coverage_status` - Status of coverage metrics
- `findings` - JSON dict storing error messages per component
- `has_errors` - Boolean flag for quick filtering
- `check_duration_ms` - Processing time in milliseconds

**Status Calculation:**
- ERROR if any component is ERROR
- WARNING if any component is WARNING (and no ERROR)
- HEALTHY if all non-UNKNOWN components are HEALTHY
- UNKNOWN otherwise

**Migration:**
- Migration `0035_add_import_and_organization_status_to_health_check` adds the new fields
- Existing health checks will have `UNKNOWN` for new fields until reprocessed

---

## Task Orchestration

### Celery Task Hierarchy

```
fetch_daily_decisions_distributed (Orchestrator)
    └─ fetch_daily_decisions_to_pickle (Fetch Task)
        ├─ store_decisions_from_pickle (Chunk 1)
        │   ├─ run_decision_pipeline_task (Decision 1)
        │   │   └─ DecisionPipelineOrchestrator.run_pipeline
        │   ├─ run_decision_pipeline_task (Decision 2)
        │   │   └─ DecisionPipelineOrchestrator.run_pipeline
        │   └─ ...
        ├─ store_decisions_from_pickle (Chunk 2)
        │   └─ ...
        └─ ...
```

### Task Configuration

**Fetch Task:**
- `max_retries=3`
- Backoff: 60s × 2^retries (60s, 120s, 240s)

**Storage Task:**
- `max_retries=5`
- Database error backoff: 20s × 3^retries (20s, 60s, 180s, 540s, 1620s)
- Non-database error backoff: 30s × 2^retries

**Pipeline Task:**
- `max_retries=3`
- Backoff: 60s (fixed)

### Distributed Locking

**AFM Fetch Lock:**
- **Prefix:** `AFM_FETCH_LOCK_PREFIX` (from `api.redis_keys`)
- **Key Format:** `{AFM_FETCH_LOCK_PREFIX}{afm}`
- **Purpose:** Prevent duplicate GEMI lookups for same AFM
- **Implementation:** Redis `exists()` check before queuing

**Usage in Company Enrichment:**
```python
redis_client = get_redis_connection("default")
for afm in unique_afms:
    key = f"{AFM_FETCH_LOCK_PREFIX}{afm}"
    if redis_client.exists(key):
        # Skip, already being processed
    else:
        # Queue for processing
```

---

## Data Flow

### Decision Lifecycle

```
1. API Response (DecisionDTO)
   ↓
2. Pickle File (decisions_YYYY-MM-DD_HHMMSS.pkl)
   ↓
3. Chunk Pickle (chunk_{chunk_id}_{timestamp}.pkl)
   ↓
4. Stage 0: Import Decision (DecisionPipelineOrchestrator._step_import_decision)
   ├─ Database (Decision model)
   │  ├─ Basic fields (subject, issue_date, etc.)
   │  ├─ Relations (organization, signers, units)
   │  ├─ Attachments (1-M)
   │  ├─ KAE Amounts (1-M)
   │  └─ Extra Fields (JSON)
   └─ Health Check: import_status = HEALTHY
   ↓
5. Stage 1: Organization Resolution (DecisionPipelineOrchestrator._step_resolve_organizations)
   ├─ Resolve organizations for signers
   ├─ Resolve organizations for units
   ├─ Create default organizations if needed
   └─ Health Check: organization_status = HEALTHY
   ↓
6. Stage 2: Entity Extraction
   ├─ DecisionEntityRelationship (M2M)
   └─ AFMEntity (AFM records)
   ↓
7. Stage 3: Amount Extraction
   └─ DecisionAmountField (linked to relationships)
   ↓
8. Stage 4: Company Enrichment
   └─ AFMEntity.gemi_data (updated with GEMI info)
   ↓
9. Stage 5: Document Processing
   └─ DocumentExtraction (PDF + text)
   ↓
10. Stage 6: OpenSearch Indexing
    └─ Searchable document in OpenSearch
    ↓
11. Stage 7: Coverage Metrics
    └─ DateCoverage (aggregated stats)
```

### Database Models

**Core Models:**
- `Decision` - Main decision record
- `DecisionHealthCheck` - Pipeline status tracking
- `DocumentExtraction` - PDF processing results
- `DateCoverage` - Coverage metrics

**Entity Models:**
- `AFMEntity` - AFM/tax ID records
- `DecisionEntityRelationship` - Links decisions to entities
- `DecisionAmountField` - Financial amounts

**Relation Models:**
- `Organization` - Government organizations
- `Signer` - Decision signers
- `Unit` - Organizational units

**Supporting Models:**
- `ImportJob` - Batch import tracking
- `Attachment` - Decision attachments
- `DecisionAmountKAE` - KAE-coded amounts

---

## Observability & Debugging

### Log Contextualization

**Ingestion ID:**
- Generated per pipeline execution: `str(uuid.uuid4())[:8]`
- Included in all logs via `logger.contextualize()`
- Format: 8-character hex string (e.g., "a1b2c3d4")

**Task ID:**
- Celery task ID: `self.request.id`
- Included in all task logs
- Format: UUID string

**ADA:**
- Decision ADA (unique identifier)
- Included in all decision-specific logs
- Format: String (e.g., "123456789")

### Grafana/Loki Queries

**Filter by Ingestion ID:**
```
{component="celery"} | json | record.extra.ingestion_id="a1b2c3d4"
```

**Filter by Task ID:**
```
{component="celery"} | json | record.extra.task_id="abc-123-def-456"
```

**Filter by ADA:**
```
{component="celery"} | json | record.extra.ada="123456789"
```

**Filter by Task Name:**
```
{component="celery"} | json | record.extra.task_name="run_decision_pipeline_task"
```

**Combine Filters:**
```
{component="celery"} | json | record.extra.ingestion_id="a1b2c3d4" | record.extra.ada="123456789"
```

### Health Check Queries

**Find Failed Decisions:**
```python
from core.models.decision_health import DecisionHealthCheck, HealthStatus

failed_checks = DecisionHealthCheck.objects.filter(
    overall_status=HealthStatus.ERROR
)
```

**Find Failures by Component:**
```python
# Import failures (NEW in v2.0)
import_failures = DecisionHealthCheck.objects.filter(
    import_status=HealthStatus.ERROR
)

# Organization resolution failures (NEW in v2.0)
org_failures = DecisionHealthCheck.objects.filter(
    organization_status=HealthStatus.ERROR
)

entity_failures = DecisionHealthCheck.objects.filter(
    entities_status=HealthStatus.ERROR
)

document_failures = DecisionHealthCheck.objects.filter(
    document_extraction_status=HealthStatus.ERROR
)
```

**Get Batch Health Report:**
```python
from core.services.pipeline_orchestrator import DecisionPipelineOrchestrator

orchestrator = DecisionPipelineOrchestrator()
report = orchestrator.get_batch_health_report(import_job_id=123)
```

**Retry Failed Component:**
```python
orchestrator.retry_failed_step(
    decision_ada="123456789",
    component="document",
    force=True
)
```

---

## Architectural Decisions

### 1. Single Source of Truth for Pipeline

**Decision:** `run_decision_pipeline_task` is the ONLY entry point for processing decisions.

**Rationale:**
- Prevents scattered, inconsistent processing
- Ensures all stages complete
- Provides centralized health tracking
- Simplifies debugging and monitoring

**Alternatives Considered:**
- Multiple entry points (rejected - too complex)
- Signal-based processing (rejected - hard to track)
- Management command only (rejected - no async support)

### 2. Pickle-Based Chunking

**Decision:** Fetch all decisions for a day, save to pickle, split into chunks.

**Rationale:**
- API doesn't support hourly queries
- Prevents API rate limiting
- Enables retry without re-fetching
- Allows parallel processing of chunks
- Deadlock prevention with small chunks

**Alternatives Considered:**
- Direct streaming to database (rejected - no retry capability)
- Hourly fetches (rejected - not supported by API)
- Larger chunks (rejected - deadlock risk)

### 3. Sequential Processing in Storage Task

**Decision:** Process decisions one-by-one in `store_decisions_from_pickle`.

**Rationale:**
- Prevents database deadlocks
- Better error isolation
- Easier retry logic
- Transaction safety

**Alternatives Considered:**
- Batch processing (rejected - deadlock issues)
- Parallel processing (rejected - lock contention)

### 4. Health Check Model

**Decision:** Separate `DecisionHealthCheck` model for tracking pipeline status.

**Rationale:**
- Separates concerns (data vs. processing status)
- Enables querying by status
- Stores error messages per component
- Supports retry logic
- Provides audit trail

**Alternatives Considered:**
- Status fields on Decision (rejected - mixing concerns)
- Separate status models per component (rejected - too complex)
- Log-only tracking (rejected - not queryable)

### 5. Contextual Logging

**Decision:** Use `logger.contextualize()` with ingestion_id, ada, task_id.

**Rationale:**
- End-to-end tracing in Grafana/Loki
- Easy filtering and debugging
- No manual log correlation needed
- Works across async boundaries

**Alternatives Considered:**
- Manual log prefixes (rejected - error-prone)
- Separate tracing system (rejected - overkill)
- No tracing (rejected - impossible to debug)

### 6. Distributed Locking for AFM Lookups

**Decision:** Use Redis locks to prevent duplicate GEMI lookups.

**Rationale:**
- GEMI API rate limiting
- Avoid duplicate work
- Prevent API abuse
- Simple implementation

**Alternatives Considered:**
- Database locks (rejected - too slow)
- No locking (rejected - duplicate work)
- Queue-based deduplication (rejected - complex)

### 7. Unified Orchestrator for Complete Lifecycle (v2.0 - 2026-01-04)

**Decision:** Move decision import and organization resolution to `DecisionPipelineOrchestrator`.

**Rationale:**
- Clearer separation of concerns (importer = data mapping only)
- Orchestrator handles all complex business logic
- Unified health tracking for all pipeline stages
- Better error handling and retry logic
- Single responsibility for orchestrator

**Changes Made:**
- Added `import_status` to `DecisionHealthCheck` model
- Added `organization_status` to `DecisionHealthCheck` model
- Created `DecisionPipelineOrchestrator._step_import_decision()` method
- Created `DecisionPipelineOrchestrator._step_resolve_organizations()` method
- Simplified `store_decisions_from_pickle` to be a pure dispatcher
- `DecisionImporter` now focuses ONLY on DTO → Model mapping

**Alternatives Considered:**
- Keep import in storage task (rejected - split responsibility)
- Keep organization resolution in importer (rejected - no health tracking)
- Separate import orchestrator (rejected - too complex)

---

## Refactoring History

### v2.0 - 2026-01-04: Unified Orchestrator

**Summary:**
Moved decision import and organization resolution logic into `DecisionPipelineOrchestrator` to provide unified health tracking and clearer separation of concerns.

**Changes:**

1. **Database Schema:**
   - Added `import_status` field to `DecisionHealthCheck`
   - Added `organization_status` field to `DecisionHealthCheck`
   - Migration: `0035_add_import_and_organization_status_to_health_check`

2. **Pipeline Orchestrator:**
   - Added `_step_import_decision()` method for Stage 0
   - Added `_step_resolve_organizations()` method for Stage 1
   - Updated `run_pipeline()` to accept optional `decision_dto` parameter
   - Updated `update_health_status()` to include new status fields
   - Renumbered stages from 1-6 to 0-7

3. **Task Layer:**
   - Simplified `store_decisions_from_pickle()` to be a pure dispatcher
   - Removed two-phase processing (import + dispatch)
   - Now calls `orchestrator._step_import_decision()` directly
   - Dispatches pipeline tasks for all successfully imported decisions

4. **Documentation:**
   - Updated architecture documentation to reflect new pipeline stages
   - Added refactoring history section
   - Updated all diagrams and code examples

**Benefits:**
- ✅ Unified health tracking for all pipeline stages
- ✅ Clearer separation of concerns (importer = data mapping only)
- ✅ Better error handling and retry logic
- ✅ Single responsibility for orchestrator
- ✅ Easier to understand and maintain

**Migration Path:**
- Existing health checks will have `UNKNOWN` for new fields
- Reprocessing decisions will populate new status fields
- No breaking changes to existing code

---

## Future Improvements

### 1. Add Pipeline Metrics

**Proposed Features:**
- Track processing time per stage
- Calculate success/failure rates
- Monitor queue depths
- Alert on abnormal patterns

**Implementation:**
- Add metrics to `DecisionHealthCheck`
- Create aggregation queries
- Build Grafana dashboards

### 2. Implement Pipeline Versioning

**Proposed Features:**
- Version pipeline configurations
- Track which version processed each decision
- Enable A/B testing of pipeline changes
- Rollback capability

**Implementation:**
- Add `pipeline_version` field to `DecisionHealthCheck`
- Create pipeline configuration model
- Version orchestrator logic

### 3. Add Retry Queue

**Proposed Features:**
- Separate queue for failed decisions
- Automatic retry with exponential backoff
- Max retry limits per component
- Dead letter queue for permanently failed

**Implementation:**
- Create dedicated Celery queue
- Add retry logic to orchestrator
- Build management UI for retry queue

### 4. Improve Pickle Management

**Proposed Features:**
- Automatic cleanup of old pickles
- Compression to save disk space
- Archive to S3 for long-term storage
- Metadata index for pickle search

**Implementation:**
- Add cleanup task
- Implement compression
- Add S3 upload logic
- Create pickle metadata model

### 3. Add Pipeline Metrics

**Proposed Features:**
- Track processing time per stage
- Calculate success/failure rates
- Monitor queue depths
- Alert on abnormal patterns

**Implementation:**
- Add metrics to `DecisionHealthCheck`
- Create aggregation queries
- Build Grafana dashboards

### 4. Implement Pipeline Versioning

**Proposed Features:**
- Version pipeline configurations
- Track which version processed each decision
- Enable A/B testing of pipeline changes
- Rollback capability

**Implementation:**
- Add `pipeline_version` field to `DecisionHealthCheck`
- Create pipeline configuration model
- Version orchestrator logic

### 5. Add Retry Queue

**Proposed Features:**
- Separate queue for failed decisions
- Automatic retry with exponential backoff
- Max retry limits per component
- Dead letter queue for permanently failed

**Implementation:**
- Create dedicated Celery queue
- Add retry logic to orchestrator
- Build management UI for retry queue

### 6. Improve Pickle Management

**Proposed Features:**
- Automatic cleanup of old pickles
- Compression to save disk space
- Archive to S3 for long-term storage
- Metadata index for pickle search

**Implementation:**
- Add cleanup task
- Implement compression
- Add S3 upload logic
- Create pickle metadata model

---

## References

### Key Files

**Tasks:**
- `core/tasks/tasks_decisions_import.py` - Fetch and storage tasks
- `core/tasks/tasks_documents.py` - Pipeline task (single source of truth)
- `core/tasks/tasks_entities.py` - Company enrichment task

**Services:**
- `core/services/pipeline_orchestrator.py` - Central orchestrator
- `core/services/document_processor.py` - Document processing
- `core/services/opensearch_service.py` - OpenSearch indexing
- `core/services/afm_extractor.py` - AFM extraction
- `core/services/entity_extraction_service.py` - Entity extraction

**Importers:**
- `core/importers/decisions.py` - Decision data importer
- `core/importers/signer.py` - Signer importer
- `core/importers/unit.py` - Unit importer

**Models:**
- `core/models/decisions.py` - Decision model
- `core/models/decision_health.py` - Health check model
- `core/models/document_analysis.py` - Document extraction model
- `core/models/entities.py` - Entity and relationship models
- `core/models/import_jobs.py` - Import job model

**Constants:**
- `core/constants/decision_import_constants.py` - Import constants (PICKLE_DIR, etc.)
- `api/redis_keys.py` - Redis key constants (AFM_FETCH_LOCK_PREFIX, etc.)

### Related Documentation

- `docs/architecture-decision-ingestion-flow.md` - Ingestion flow decisions
- `docs/decision-ingestion-single-source-of-truth.md` - Single source of truth rationale
- `docs/decision-health-check-system.md` - Health check system design
- `docs/orchestrator-final-summary.md` - Orchestrator implementation summary
- `docs/orchestrator-migration-guide.md` - Migration guide to orchestrator

---

## Quick Reference

### Process a Single Decision

```python
from core.tasks.tasks_documents import run_decision_pipeline_task

task = run_decision_pipeline_task.delay(
    ada="123456789",
    force_reprocess=False,
    skip_opensearch=False
)
```

### Process a Day of Decisions

```python
from core.tasks.tasks_decisions_import import fetch_daily_decisions_distributed
from datetime import date

result = fetch_daily_decisions_distributed.delay(
    target_date_str=date.today().isoformat()
)
```

### Retry Failed Decisions

```python
from core.services.pipeline_orchestrator import DecisionPipelineOrchestrator

orchestrator = DecisionPipelineOrchestrator()

# Retry single decision
orchestrator.retry_failed_step(
    decision_ada="123456789",
    component="document",
    force=True
)

# Retry all failures in batch
orchestrator.retry_batch_failures(
    import_job_id=123,
    component="document",
    max_workers=5
)
```

### Get Batch Health Report

```python
from core.services.pipeline_orchestrator import DecisionPipelineOrchestrator

orchestrator = DecisionPipelineOrchestrator()
report = orchestrator.get_batch_health_report(
    import_job_id=123,
    include_failures=True
)

print(f"Health: {report['summary']['health_percentage']:.1f}%")
print(f"Errors: {report['summary']['error_count']}")
```

### Query Logs in Grafana

```
# All logs for a specific decision
{component="celery"} | json | record.extra.ada="123456789"

# All logs for a specific pipeline execution
{component="celery"} | json | record.extra.ingestion_id="a1b2c3d4"

# All errors in pipeline tasks
{component="celery"} | json | level="error" | record.extra.task_name="run_decision_pipeline_task"

# Document processing failures
{component="celery"} | json | record.extra.task_name="run_decision_pipeline_task" | line ~ "document"
```

---

**Document Maintainer:** Development Team  
**Last Review:** 2026-01-03  
**Next Review:** 2026-02-03
