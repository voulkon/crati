# Pipeline Observability & Orchestration - Recommendations

## Executive Summary

**Problem:** The decision ingestion pipeline has 6 distinct stages with multiple execution paths (signals vs explicit calls), making it impossible to track failures, retry errors, or get batch-level visibility when processing 1000s of decisions.

**Solution:** Centralize orchestration, add batch tracking, implement retry mechanisms, and create comprehensive monitoring dashboards.

---

## Current State Analysis

### Pipeline Stages (Validated ✓)

1. **Decision Ingestion** - Fetch from API → Save to PostgreSQL
2. **Entity Extraction** - Parse AFMs from JSON → Create entities
3. **Company Enrichment** - Fetch from GEMI registry → Enrich entity data
4. **Document Processing** - Download PDF → Extract text → Save to PostgreSQL
5. **OpenSearch Indexing** - Index extracted text → Make searchable
6. **Coverage Metrics** - Update DateCoverage aggregates

### Current Execution Paths (The Problem)

```
Decision Saved
    ├─> DecisionImporter._trigger_company_data_fetching() [Explicit]
    ├─> Signal: queue_document_processing() [Implicit]
    └─> Signal: update_organization_coverage() [Implicit]

DocumentExtraction Saved
    └─> Signal: index_document_in_opensearch() [Implicit]
```

**Issues:**
- ❌ Mixed explicit/implicit execution (hard to trace)
- ❌ No batch-level tracking (can't see "Batch #123: 850/1000 succeeded")
- ❌ No decision-to-batch linkage (can't answer "which batch was this decision from?")
- ❌ No retry mechanism (if document download fails, decision is stuck)
- ❌ Error discovery requires log diving or manual DB queries

---

## Recommended Architecture

### Option A: Hybrid (Signals + Orchestrator Verification)

**Keep:**
- Signals for automatic real-time processing
- Existing flow unchanged

**Add:**
- Orchestrator runs periodically to **verify** and **heal**
- Finds decisions with incomplete pipelines
- Retries failed steps
- Generates health reports

**Pros:** Minimal changes, backwards compatible
**Cons:** Still dual execution paths, signals can fail silently

---

### Option B: Orchestrator-First (Recommended) 🎯

**Change:**
- Disable document processing signals
- Make orchestrator the **only** execution path
- Signals only for metrics (DateCoverage, monitoring)

**Flow:**
```
ImportJob Created
    ├─> Fetch Decisions (batch)
    ├─> Save to DB
    └─> FOR EACH Decision:
          └─> PipelineOrchestrator.run_pipeline(decision_ada)
                ├─> Extract Entities
                ├─> Enrich Companies (async task)
                ├─> Process Document
                ├─> Index to OpenSearch
                └─> Update HealthCheck
```

**Pros:** 
- ✅ Single source of truth
- ✅ Explicit, traceable execution
- ✅ Easy to retry individual steps
- ✅ Clear error reporting

**Cons:** 
- Requires signal refactoring
- Breaking change (needs testing)

---

## Implementation Plan

### Phase 1: Add Batch Tracking (Immediate Value)

#### 1.1 Link Decisions to Batches

```python
# Add to Decision model
class Decision(models.Model):
    # ... existing fields ...
    import_job = models.ForeignKey(
        'ImportJob', 
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='decisions',
        help_text="The import batch this decision belongs to"
    )
```

#### 1.2 Link Health Checks to Batches

```python
# Add to DecisionHealthCheck model
class DecisionHealthCheck(models.Model):
    # ... existing fields ...
    import_job = models.ForeignKey(
        'ImportJob',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='health_checks',
        help_text="The import batch this decision belongs to"
    )
```

#### 1.3 Add Batch Health Summary

```python
class BatchHealthSummary(models.Model):
    """Aggregated health metrics for an import batch"""
    import_job = models.OneToOneField(ImportJob, on_delete=models.CASCADE)
    
    # Counts by overall status
    total_decisions = models.IntegerField(default=0)
    healthy_count = models.IntegerField(default=0)
    warning_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    unknown_count = models.IntegerField(default=0)
    
    # Component failure breakdowns
    ingestion_failures = models.IntegerField(default=0)
    entity_failures = models.IntegerField(default=0)
    document_failures = models.IntegerField(default=0)
    opensearch_failures = models.IntegerField(default=0)
    coverage_failures = models.IntegerField(default=0)
    
    # Timing
    avg_processing_time_ms = models.IntegerField(null=True, blank=True)
    slowest_decision_ada = models.CharField(max_length=20, null=True)
    slowest_decision_time_ms = models.IntegerField(null=True)
    
    last_updated = models.DateTimeField(auto_now=True)
```

### Phase 2: Enhanced Orchestrator

#### 2.1 Add Batch Processing

```python
class DecisionPipelineOrchestrator:
    def run_batch_pipeline(
        self, 
        import_job_id: int,
        max_workers: int = 10,
        stop_on_error: bool = False
    ) -> Dict[str, Any]:
        """
        Process all decisions in a batch with parallel execution
        """
        import_job = ImportJob.objects.get(id=import_job_id)
        decisions = import_job.decisions.all()
        
        results = {
            'total': decisions.count(),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        # Process in parallel with controlled concurrency
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.run_pipeline, d.ada): d.ada 
                for d in decisions
            }
            
            for future in as_completed(futures):
                ada = futures[future]
                try:
                    health_check = future.result()
                    if health_check.overall_status == HealthStatus.ERROR:
                        results['failed'] += 1
                        results['errors'].append({
                            'ada': ada,
                            'findings': health_check.findings
                        })
                    else:
                        results['successful'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'ada': ada,
                        'error': str(e)
                    })
                    if stop_on_error:
                        break
        
        # Generate batch summary
        self._generate_batch_summary(import_job)
        
        return results
```

#### 2.2 Add Retry Mechanism

```python
def retry_failed_step(
    self, 
    decision_ada: str, 
    component: str
) -> DecisionHealthCheck:
    """
    Retry a specific failed component for a decision
    """
    decision = Decision.objects.get(ada=decision_ada)
    health_check = self.get_or_create_health_check(decision)
    
    step_map = {
        'entities': self._step_extract_entities,
        'companies': self._step_enrich_companies,
        'document': self._step_process_document,
        'opensearch': self._step_index_opensearch,
        'coverage': self._step_verify_coverage,
    }
    
    if component not in step_map:
        raise ValueError(f"Unknown component: {component}")
    
    logger.info(f"🔄 Retrying {component} for {decision_ada}")
    step_map[component](decision, health_check, force=True)
    
    return health_check

def retry_batch_failures(
    self, 
    import_job_id: int,
    component: str = None
) -> Dict[str, Any]:
    """
    Retry all failures in a batch, optionally for a specific component
    """
    import_job = ImportJob.objects.get(id=import_job_id)
    
    # Get all error health checks for this batch
    failed_checks = DecisionHealthCheck.objects.filter(
        import_job=import_job,
        overall_status=HealthStatus.ERROR
    )
    
    if component:
        # Filter by specific component failure
        filter_kwargs = {f"{component}_status": HealthStatus.ERROR}
        failed_checks = failed_checks.filter(**filter_kwargs)
    
    results = {
        'total': failed_checks.count(),
        'retried': 0,
        'still_failed': 0
    }
    
    for health_check in failed_checks:
        try:
            if component:
                updated_check = self.retry_failed_step(
                    health_check.decision.ada, 
                    component
                )
            else:
                updated_check = self.run_pipeline(
                    health_check.decision.ada,
                    force_reprocess=True
                )
            
            if updated_check.overall_status != HealthStatus.ERROR:
                results['retried'] += 1
            else:
                results['still_failed'] += 1
        except Exception as e:
            logger.error(f"Retry failed for {health_check.decision.ada}: {e}")
            results['still_failed'] += 1
    
    return results
```

### Phase 3: Admin Dashboard Improvements

#### 3.1 Batch Health Overview

Create admin view showing:
- List of import batches with health percentages
- Component failure breakdown (bar chart)
- Quick filters: "Show failed batches", "Show incomplete batches"
- Bulk actions: "Retry failed documents", "Retry failed indexing"

#### 3.2 Decision Investigation View

For a specific decision:
```
Decision: ΩΓ7Κ46904Ο-13Λ
Import Batch: #1847 (2024-12-29)
Overall Status: ⚠️ WARNING

Pipeline Steps:
✅ Ingestion       (23ms) - OK
✅ Entities        (145ms) - Found 3 AFMs
⚠️ Companies       (2.3s) - 2/3 enriched (1 timeout)
✅ Document        (8.7s) - Text extracted (15 pages)
❌ OpenSearch      (failed) - Connection timeout

[Retry Failed Steps] [View Full Logs] [Export Report]
```

### Phase 4: Management Commands

```bash
# Process a specific batch
python manage.py run_decision_pipeline --batch-id 1847

# Process recent unprocessed decisions
python manage.py run_decision_pipeline --unprocessed --days 7

# Retry failures in a batch
python manage.py retry_pipeline_failures --batch-id 1847 --component opensearch

# Generate health report
python manage.py pipeline_health_report --batch-id 1847 --format json > report.json
```

---

## Migration Strategy

### Week 1: Add Observability (No Breaking Changes)

1. Add `import_job` FK to `Decision` and `DecisionHealthCheck`
2. Create `BatchHealthSummary` model
3. Add batch summary generation to orchestrator
4. Create admin views for batch health

**Result:** Can now see batch-level health without changing execution

### Week 2: Integrate Orchestrator (Optional Breaking Change)

**Option A (Safe):** Keep signals, use orchestrator for verification/retry only
**Option B (Recommended):** Disable signals, make orchestrator primary

1. Add feature flag: `USE_PIPELINE_ORCHESTRATOR = True`
2. When enabled: Disable document processing signals
3. Call orchestrator from import flow
4. Test thoroughly with small batches
5. Monitor for issues
6. Gradually roll out

### Week 3: Retry Mechanisms & Admin Tools

1. Implement retry methods
2. Add bulk admin actions
3. Create management commands
4. Document troubleshooting workflows

---

## Monitoring & Alerting

### Key Metrics to Track

1. **Batch Health Percentage**
   - Alert if < 95% healthy
   
2. **Component Failure Rates**
   - Track which steps fail most often
   - Alert on sudden spikes
   
3. **Processing Time**
   - 90th percentile processing time per component
   - Alert on slowdowns
   
4. **Backlog Size**
   - Number of decisions with incomplete pipelines
   - Alert if growing

### Health Check Dashboard

```
Import Batch #1847 (2024-12-29)
─────────────────────────────────────────────
Total Decisions: 1,247
Health: 91.2% ⚠️

Status Breakdown:
  ✅ Healthy:   1,138 (91.2%)
  ⚠️ Warning:      78 (6.3%)
  ❌ Error:        31 (2.5%)

Component Failures:
  Document Processing: 18 failures
  OpenSearch Indexing: 13 failures
  Entity Extraction:    0 failures
  
Top Errors:
  1. "Connection timeout" (13 occurrences)
  2. "PDF download failed" (8 occurrences)
  3. "Text extraction timeout" (5 occurrences)

[View Failed Decisions] [Retry All Failures] [Export Report]
```

---

## Troubleshooting Workflows

### Scenario 1: "Batch shows 50 document failures"

```bash
# 1. View the failures
python manage.py pipeline_health_report --batch-id 1847 \
    --filter component=document --filter status=error

# 2. Check if it's a specific error
# (Might be "PDF not found" vs "Text extraction timeout")

# 3. Retry with fresh download
python manage.py retry_pipeline_failures \
    --batch-id 1847 --component document --force-download

# 4. Verify resolution
python manage.py pipeline_health_report --batch-id 1847
```

### Scenario 2: "Decision ADA ΩΓ7Κ123 shows error, but I don't know why"

```bash
# 1. Get detailed health check
python manage.py check_decision_health ΩΓ7Κ123 --verbose

# Output shows:
# ❌ OpenSearch Status: ERROR
#    Error: "Index 'decisions' does not exist"
#    Last attempt: 2024-12-29 14:32:18

# 2. Retry just the OpenSearch step
python manage.py retry_pipeline_step ΩΓ7Κ123 --component opensearch

# 3. Verify
python manage.py check_decision_health ΩΓ7Κ123
```

---

## Next Steps

### Immediate (This Week)
1. ✅ Review this document
2. Add `import_job` FK to models (migration)
3. Create `BatchHealthSummary` model
4. Add batch summary method to orchestrator

### Short Term (Next 2 Weeks)
5. Create batch health admin views
6. Add retry methods to orchestrator
7. Create management commands
8. Test on small batches

### Medium Term (Next Month)
9. Decide: Keep signals or go orchestrator-first?
10. Implement chosen approach
11. Add monitoring/alerting
12. Document for team

---

## Questions to Answer

1. **Signal vs Orchestrator:** Do you want to keep signals (less refactoring) or go orchestrator-first (cleaner architecture)?

2. **Retry Strategy:** Should retries happen automatically (with backoff) or manually triggered?

3. **Performance:** With 1000 decisions/day, do we need rate limiting for GEMI lookups or OpenSearch indexing?

4. **Alerting:** What failure threshold should trigger alerts? (e.g., >5% failures, >10 consecutive failures)

5. **Data Retention:** How long should we keep `DecisionHealthCheck` records? Should we archive old batches?

---

## Conclusion

Your current setup has all the pieces but needs **integration and observability**. The recommended path:

1. **Phase 1 (Quick Win):** Add batch tracking and health summaries
2. **Phase 2 (Architecture Decision):** Choose signal-based or orchestrator-first
3. **Phase 3 (Ops Excellence):** Add retry mechanisms and monitoring

This will give you:
- ✅ "What went wrong in Batch #1847?"
- ✅ "Retry all failed document extractions"
- ✅ "Show me decisions stuck in the pipeline"
- ✅ "Alert if >5% of decisions fail"

**Recommendation:** Start with Phase 1 this week. It adds visibility without breaking anything.
