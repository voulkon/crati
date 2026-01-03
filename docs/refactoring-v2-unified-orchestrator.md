# Refactoring Summary: Unified Orchestrator (v2.0)

**Date:** 2026-01-04  
**Version:** 2.0  
**Status:** ✅ Completed

## Overview

This refactoring addresses two key architectural concerns:

1. **Decision Import Logic:** Previously split between `store_decisions_from_pickle` and `DecisionImporter`
2. **Organization Resolution:** Complex business logic mixed with data mapping in `DecisionImporter`

Both have been moved to `DecisionPipelineOrchestrator` to provide:
- Unified health tracking for all pipeline stages
- Clearer separation of concerns
- Better error handling and retry logic
- Single responsibility for orchestrator

## Changes Made

### 1. Database Schema Changes

**File:** `core/models/decision_health.py`

**New Fields:**
```python
import_status = models.CharField(
    max_length=10,
    choices=HealthStatus.choices,
    default=HealthStatus.UNKNOWN,
    help_text="Decision imported from DTO to database with all relations"
)

organization_status = models.CharField(
    max_length=10,
    choices=HealthStatus.choices,
    default=HealthStatus.UNKNOWN,
    help_text="Organization resolution completed for signers and units"
)
```

**Migration:** `0035_add_import_and_organization_status_to_health_check`

### 2. Pipeline Orchestrator Changes

**File:** `core/services/pipeline_orchestrator.py`

#### New Method: `_step_import_decision()`

**Purpose:** Import decision from DTO to database (Stage 0)

**Responsibilities:**
- Imports decision using `DecisionImporter.import_many()`
- Creates/updates `Decision` record with all relations
- Updates `import_status` in health check
- Returns `Decision` instance or `None` on failure

**Signature:**
```python
def _step_import_decision(self, decision_dto, health_check: DecisionHealthCheck = None) -> Optional[Decision]
```

#### New Method: `_step_resolve_organizations()`

**Purpose:** Resolve organizations for signers and units (Stage 1)

**Responsibilities:**
- Resolves organizations for all signers associated with decision
- Resolves organizations for all units associated with decision
- Traverses parent chains to find organizations
- Creates default organizations if resolution fails
- Updates `organization_status` in health check
- Tracks detailed resolution results

**Signature:**
```python
def _step_resolve_organizations(self, decision: Decision, health_check: DecisionHealthCheck) -> None
```

**Resolution Results Structure:**
```python
{
    'signers_resolved': int,
    'signers_failed': int,
    'units_resolved': int,
    'units_failed': int,
    'details': List[Dict]  # Each with type, uid, resolved, org_id, path
}
```

#### Updated Method: `run_pipeline()`

**Changes:**
- Added optional `decision_dto` parameter
- Added Stage 0: Import Decision (if DTO provided)
- Added Stage 1: Organization Resolution
- Renumbered stages from 1-6 to 0-7
- Updated health check initialization to include new fields

**New Signature:**
```python
def run_pipeline(self, decision_ada: str, force_reprocess: bool = False, 
               skip_opensearch: bool = False, decision_dto=None) -> DecisionHealthCheck
```

#### Updated Method: `update_health_status()`

**Changes:**
- Added `import_status` to status calculation
- Added `organization_status` to status calculation
- Updated overall status calculation to include new fields

### 3. Task Layer Changes

**File:** `core/tasks/tasks_decisions_import.py`

#### Updated Task: `store_decisions_from_pickle()`

**Before:**
```python
# Phase 1: Import all decisions to database
for decision in decisions:
    with transaction.atomic():
        created_count += decision_importer.import_many([decision])
    
    successfully_imported_adas.append(decision.ada)

# Phase 2: Dispatch pipeline tasks
for ada in successfully_imported_adas:
    run_decision_pipeline_task.delay(ada=ada, ...)
```

**After:**
```python
# Import and dispatch using orchestrator
for decision_dto in decisions:
    # Import using orchestrator (Stage 0)
    decision = orchestrator._step_import_decision(decision_dto)
    
    if decision:
        # Dispatch pipeline task for full processing (Stages 1-7)
        pipeline_task = run_decision_pipeline_task.delay(
            ada=decision.ada,
            force_reprocess=False,
            skip_opensearch=skip_opensearch
        )
```

**Benefits:**
- Simpler code (single loop instead of two phases)
- Unified health tracking from Stage 0
- Better error handling (orchestrator handles retries)
- Clearer separation of concerns

### 4. Documentation Changes

**File:** `docs/decision-pipeline-architecture.md`

**Updates:**
- Updated version to 2.0
- Added "Architecture Evolution" section
- Updated pipeline flow diagram (8 stages instead of 6)
- Updated Stage descriptions (0-7 instead of 1-6)
- Added `import_status` and `organization_status` to health check documentation
- Updated decision lifecycle diagram
- Added refactoring history section
- Updated architectural decisions section
- Removed completed items from "Future Improvements"

## Benefits

### 1. Unified Health Tracking

**Before:**
- Import status not tracked in health check
- Organization resolution not tracked in health check
- No visibility into Stage 0 and Stage 1 failures

**After:**
- All 8 stages tracked in `DecisionHealthCheck`
- Clear visibility into failures at any stage
- Better debugging and monitoring

### 2. Clearer Separation of Concerns

**Before:**
- `DecisionImporter` mixed data mapping with business logic
- `store_decisions_from_pickle` handled import logic
- Organization resolution buried in importer

**After:**
- `DecisionImporter` focuses ONLY on DTO → Model mapping
- `DecisionPipelineOrchestrator` handles all business logic
- Clear responsibilities for each component

### 3. Better Error Handling

**Before:**
- Import errors handled in storage task
- Organization resolution errors buried in importer
- Inconsistent retry logic

**After:**
- All errors tracked in health check
- Consistent retry logic across all stages
- Better error messages and context

### 4. Single Responsibility

**Before:**
- Import logic split across multiple components
- No single owner for decision lifecycle
- Hard to understand flow

**After:**
- `DecisionPipelineOrchestrator` owns complete lifecycle
- Clear entry point for all processing
- Easier to understand and maintain

## Migration Path

### Existing Data

**Health Checks:**
- Existing `DecisionHealthCheck` records will have `UNKNOWN` for new fields
- No breaking changes to existing functionality
- Reprocessing decisions will populate new status fields

**Decisions:**
- No changes to `Decision` model
- Existing decisions continue to work
- No data migration needed

### Code Compatibility

**Backward Compatibility:**
- `DecisionImporter` methods still available for backward compatibility
- `ingestion_status` field kept for legacy queries
- No breaking changes to public APIs

**Forward Compatibility:**
- New `import_status` and `organization_status` fields available
- Orchestrator methods can be called directly
- Support for both DTO-based and ADA-based processing

## Testing Recommendations

### Unit Tests

1. **Test `_step_import_decision()`:**
   - Import new decision
   - Import duplicate decision (update)
   - Import with invalid DTO
   - Verify health check status

2. **Test `_step_resolve_organizations()`:**
   - Resolve with existing organizations
   - Resolve with missing organizations (create defaults)
   - Resolve with complex parent chains
   - Verify health check status

3. **Test `run_pipeline()` with DTO:**
   - Full pipeline with new decision
   - Full pipeline with existing decision
   - Pipeline with skip_opensearch=True
   - Verify all 8 stages complete

### Integration Tests

1. **Test `store_decisions_from_pickle()`:**
   - Process chunk of new decisions
   - Process chunk with duplicates
   - Process chunk with errors
   - Verify pickle moved to completed/failed

2. **Test end-to-end flow:**
   - Fetch → Store → Pipeline
   - Verify health check at each stage
   - Verify logs with ingestion_id
   - Verify Grafana queries work

### Manual Testing

1. **Process a day of decisions:**
   - Run `fetch_daily_decisions_distributed`
   - Monitor Celery tasks
   - Check health check statuses
   - Verify all stages complete

2. **Test retry logic:**
   - Force a deadlock
   - Verify retry with backoff
   - Verify health check error tracking
   - Verify eventual success

## Rollback Plan

If issues arise, rollback steps:

1. **Revert code changes:**
   ```bash
   git revert <commit-hash>
   ```

2. **Rollback migration:**
   ```bash
   python manage.py migrate core 0034
   ```

3. **Restart services:**
   ```bash
   docker-compose restart backend
   ```

4. **Verify functionality:**
   - Test import flow
   - Test pipeline processing
   - Check health checks
   - Review logs

## Next Steps

1. ✅ Code changes completed
2. ✅ Migration created and applied
3. ✅ Documentation updated
4. ⏳ Unit tests (recommended)
5. ⏳ Integration tests (recommended)
6. ⏳ Manual testing (recommended)
7. ⏳ Monitor production (after deployment)

## Questions & Considerations

### Open Questions

1. **Should we deprecate `ingestion_status` field?**
   - Currently kept for backward compatibility
   - Could be removed in future version
   - Need to check usage in queries

2. **Should we add more granular health tracking?**
   - Track individual signer/unit resolution
   - Track attachment processing
   - Track KAE amount processing

3. **Should we add pipeline metrics?**
   - Processing time per stage
   - Success/failure rates
   - Queue depths

### Future Enhancements

1. **Add pipeline versioning:**
   - Track which version processed each decision
   - Enable A/B testing
   - Support rollback

2. **Add retry queue:**
   - Separate queue for failed decisions
   - Automatic retry with backoff
   - Dead letter queue

3. **Improve pickle management:**
   - Automatic cleanup
   - Compression
   - S3 archival

---

**Author:** Development Team  
**Reviewers:** TBD  
**Approved:** TBD
