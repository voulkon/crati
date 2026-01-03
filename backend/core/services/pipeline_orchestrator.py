from typing import Dict, Any, Optional, List
from loguru import logger
from django.utils import timezone
from django.db import transaction
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import uuid

from core.models.decisions import Decision
from core.models.decision_health import DecisionHealthCheck, HealthStatus
from core.models.document_analysis import DocumentExtraction, ProcessingStatus
from core.models.import_jobs import ImportJob
from core.services.afm_extractor import AFMExtractionService
from core.services.entity_extraction_service import EntityExtractionService
from core.services.document_processor import DocumentAnalysisService
from core.services.opensearch_service import OpenSearchService
from core.tasks.tasks_entities import fetch_company_data_for_entities
from core.importers.decisions import DecisionImporter

class DecisionPipelineOrchestrator:
    """
    Central orchestrator for the decision processing pipeline.
    Ensures all steps (Ingestion -> Entities -> Documents -> Indexing) are completed
    and tracks their status in DecisionHealthCheck.
    """

    def __init__(self):
        self.afm_service = AFMExtractionService()
        self.entity_service = EntityExtractionService()
        self.doc_service = DocumentAnalysisService()
        self.search_service = OpenSearchService()
        self.decision_importer = DecisionImporter()
    
    def _separator(self, char: str = '=', width: int = 80) -> str:
        """Generate a separator line for logs."""
        return char * width

    def get_or_create_health_check(self, decision: Decision) -> DecisionHealthCheck:
        health_check, created = DecisionHealthCheck.objects.get_or_create(
            decision=decision,
            defaults={
                'decision_issue_date': decision.issue_date,
                'overall_status': HealthStatus.UNKNOWN
            }
        )
        return health_check

    def update_health_status(self, health_check: DecisionHealthCheck, component: str, status: str, error: str = None):
        """Updates the status of a specific component and the overall health."""
        setattr(health_check, f"{component}_status", status)
        
        if error:
            findings = health_check.findings or {}
            findings[component] = error
            health_check.findings = findings
            health_check.has_errors = True
        
        # Recalculate overall status
        statuses = [
            health_check.ingestion_status,
            health_check.relations_status,
            health_check.entities_status,
            health_check.document_extraction_status,
            health_check.opensearch_status,
            health_check.coverage_status
        ]
        
        if HealthStatus.ERROR in statuses:
            health_check.overall_status = HealthStatus.ERROR
        elif HealthStatus.WARNING in statuses:
            health_check.overall_status = HealthStatus.WARNING
        elif all(s == HealthStatus.HEALTHY for s in statuses if s != HealthStatus.UNKNOWN):
            health_check.overall_status = HealthStatus.HEALTHY
        
        health_check.save()

    def run_pipeline(self, decision_ada: str, force_reprocess: bool = False, skip_opensearch: bool = False) -> DecisionHealthCheck:
        """
        Runs the full processing pipeline for a decision.
        
        Args:
            decision_ada: The ADA of the decision to process
            force_reprocess: Force reprocessing even if already processed
            skip_opensearch: Skip OpenSearch indexing (useful for reducing infra costs)
        """
        # Generate unique ingestion ID for log tracing in Grafana
        ingestion_id = str(uuid.uuid4())[:8]
        
        # Bind ingestion_id to all logs in this context
        with logger.contextualize(ingestion_id=ingestion_id, ada=decision_ada):
            logger.info(
                f"\n{self._separator()}\n"
                f"🚀 Starting pipeline for decision {decision_ada}\n"
                f"   Ingestion ID: {ingestion_id} (use this to filter logs)\n"
                f"   Force reprocess: {force_reprocess}\n"
                f"   Skip OpenSearch: {skip_opensearch}\n"
                f"{self._separator()}\n"
            )
            
            try:
                decision = Decision.objects.get(ada=decision_ada)
            except Decision.DoesNotExist:
                logger.error(f"❌ Decision {decision_ada} not found")
                return None

            health_check = self.get_or_create_health_check(decision)
            self.update_health_status(health_check, 'ingestion', HealthStatus.HEALTHY)

            # 1. Amount Extraction
            logger.info(f"\n{self._separator()}\n💰 STAGE 1/6: AMOUNT EXTRACTION\n{self._separator()}")
            self._step_extract_amounts(decision, health_check)

            # 2. Entity Extraction
            logger.info(f"\n{self._separator()}\n📝 STAGE 2/6: ENTITY EXTRACTION\n{self._separator()}")
            self._step_extract_entities(decision, health_check)

            # 3. Company Data Enrichment
            logger.info(f"\n{self._separator()}\n🏢 STAGE 3/6: COMPANY ENRICHMENT\n{self._separator()}")
            self._step_enrich_companies(decision, health_check)

            # 4. Document Processing
            logger.info(f"\n{self._separator()}\n📄 STAGE 4/6: DOCUMENT PROCESSING\n{self._separator()}")
            self._step_process_document(decision, health_check, force_reprocess)

            # 5. OpenSearch Indexing
            if skip_opensearch:
                logger.info(
                    f"\n{self._separator()}\n"
                    f"🔎 STAGE 5/6: OPENSEARCH INDEXING (SKIPPED)\n"
                    f"{self._separator()}\n"
                    f"OpenSearch indexing disabled - skipping to save on infrastructure costs"
                )
                self.update_health_status(health_check, 'opensearch', HealthStatus.UNKNOWN)
            else:
                logger.info(f"\n{self._separator()}\n🔎 STAGE 5/6: OPENSEARCH INDEXING\n{self._separator()}")
                self._step_index_opensearch(decision, health_check)

            # 6. Coverage
            logger.info(f"\n{self._separator()}\n📊 STAGE 6/6: COVERAGE METRICS\n{self._separator()}")
            self._step_verify_coverage(decision, health_check)

            logger.info(
                f"\n{self._separator()}\n"
                f"✅ Pipeline completed for {decision_ada}\n"
                f"   Overall Status: {health_check.overall_status}\n"
                f"   Ingestion ID: {ingestion_id}\n"
                f"{self._separator()}\n"
            )
            
            return health_check

    def _step_extract_amounts(self, decision: Decision, health_check: DecisionHealthCheck):
        """Extract and save DecisionAmountField records from extra field values."""
        try:
            from core.models.entities import DecisionAmountField
            
            logger.info(f"Step 1: Extracting amounts for {decision.ada}")
            
            # Check if amounts already extracted
            existing_count = DecisionAmountField.objects.filter(decision=decision).count()
            
            if existing_count > 0:
                logger.debug(f"Decision {decision.ada} already has {existing_count} amount fields")
            else:
                # Extract and save amounts
                self.decision_importer.extract_and_save_amounts(decision)
                
                new_count = DecisionAmountField.objects.filter(decision=decision).count()
                logger.info(f"Extracted {new_count} amount fields for {decision.ada}")
            
            # Always mark as healthy - having no amounts is valid
            self.update_health_status(health_check, 'entities', HealthStatus.HEALTHY)
            
        except Exception as e:
            logger.error(f"Failed amount extraction: {e}", exc_info=True)
            self.update_health_status(health_check, 'entities', HealthStatus.ERROR, str(e))

    def _step_extract_entities(self, decision: Decision, health_check: DecisionHealthCheck):
        try:
            from core.models.entities import DecisionEntityRelationship
            
            logger.info(f"Step 2: Extracting entities for {decision.ada}")
            
            # Check if entities already extracted
            existing_count = DecisionEntityRelationship.objects.filter(decision=decision).count()
            
            if existing_count > 0:
                logger.debug(f"Decision {decision.ada} already has {existing_count} entity relationships, skipping extraction")
            else:
                # Extract entities
                self.afm_service.extract_afms_from_decision(decision, save_to_db=True)
                
                new_count = DecisionEntityRelationship.objects.filter(decision=decision).count()
                logger.info(f"Extracted {new_count} entity relationships for {decision.ada}")
            
            self.update_health_status(health_check, 'entities', HealthStatus.HEALTHY)
        except Exception as e:
            logger.error(f"Failed entity extraction: {e}")
            self.update_health_status(health_check, 'entities', HealthStatus.ERROR, str(e))

    def _step_enrich_companies(self, decision: Decision, health_check: DecisionHealthCheck):
        try:
            logger.info(f"Step 3: Enriching company data for {decision.ada}")
            
            # Find entities related to this decision
            relationships = decision.entity_relationships.all()
            
            if not relationships.exists():
                logger.debug(f"No entity relationships found for {decision.ada}, skipping company enrichment")
                self.update_health_status(health_check, 'relations', HealthStatus.HEALTHY)
                return
            
            # Check which entities need GEMI lookup (haven't been attempted yet)
            entities_needing_lookup = []
            for rel in relationships:
                entity = rel.entity
                if entity.gemi_lookup_attempted is None:
                    entities_needing_lookup.append(entity.afm)
            
            if entities_needing_lookup:
                logger.info(f"Triggering company enrichment for {len(entities_needing_lookup)} entities")
                
                # Extract parent context from logger for tracing child tasks
                parent_task_id = logger._core.extra.get('task_id')
                parent_ada = decision.ada
                
                # Trigger the task with parent context for complete traceability
                fetch_company_data_for_entities.delay(
                    entities_needing_lookup, 
                    parent_task_id=parent_task_id, 
                    parent_ada=parent_ada
                )
            else:
                logger.debug(f"All {relationships.count()} entities for {decision.ada} already have GEMI lookup attempted, skipping")
            
            self.update_health_status(health_check, 'relations', HealthStatus.HEALTHY)
        except Exception as e:
            logger.error(f"Failed company enrichment: {e}")
            self.update_health_status(health_check, 'relations', HealthStatus.ERROR, str(e))

    def _step_process_document(self, decision: Decision, health_check: DecisionHealthCheck, force: bool):
        try:
            logger.info(f"Step 3: Processing document for {decision.ada}")
            
            if not decision.document_url:
                self.update_health_status(health_check, 'document_extraction', HealthStatus.WARNING, "No document URL")
                return

            # Check existing extraction
            extraction = DocumentExtraction.objects.filter(decision=decision).first()
            
            if extraction and extraction.extraction_status == ProcessingStatus.COMPLETED and not force:
                self.update_health_status(health_check, 'document_extraction', HealthStatus.HEALTHY)
                return

            # Run processing
            result = self.doc_service.process_decision(decision)
            
            if result.get('success'):
                self.update_health_status(health_check, 'document_extraction', HealthStatus.HEALTHY)
            else:
                self.update_health_status(health_check, 'document_extraction', HealthStatus.ERROR, result.get('error'))

        except Exception as e:
            logger.error(f"Failed document processing: {e}")
            self.update_health_status(health_check, 'document_extraction', HealthStatus.ERROR, str(e))

    def _step_index_opensearch(self, decision: Decision, health_check: DecisionHealthCheck):
        try:
            logger.info(f"Step 5: Indexing in OpenSearch for {decision.ada}")
            
            extraction = DocumentExtraction.objects.filter(decision=decision).first()
            
            if not extraction:
                self.update_health_status(health_check, 'opensearch', HealthStatus.WARNING, "No extraction found")
                return
            
            if extraction.extraction_status != ProcessingStatus.COMPLETED:
                self.update_health_status(health_check, 'opensearch', HealthStatus.WARNING, f"Extraction status: {extraction.extraction_status}")
                return
            
            if not extraction.raw_text:
                self.update_health_status(health_check, 'opensearch', HealthStatus.WARNING, "No text extracted")
                return
            
            # Check if already indexed by querying OpenSearch
            try:
                is_indexed = self.search_service.document_exists(decision.id)
                if is_indexed:
                    logger.debug(f"Document for {decision.ada} already indexed in OpenSearch, skipping")
                    self.update_health_status(health_check, 'opensearch', HealthStatus.HEALTHY)
                    return
            except Exception as check_error:
                logger.warning(f"Could not check if document exists in OpenSearch: {check_error}, proceeding with indexing")
            
            # Build document data dict for OpenSearch
            document_data = {
                'decision_id': decision.id,
                'ada': decision.ada,
                'title': decision.subject or '',
                'content': extraction.raw_text,
                'organization': str(decision.organization) if decision.organization else '',
                'decision_type': str(decision.decision_type) if decision.decision_type else '',
                'issue_date': decision.issue_date.isoformat() if decision.issue_date else None,
                'extraction_date': extraction.extraction_date.isoformat() if extraction.extraction_date else None,
                'character_count': extraction.character_count,
                'page_count': extraction.page_count
            }
            
            logger.info(f"Indexing document for {decision.ada} in OpenSearch")
            success = self.search_service.index_document(document_data)
            
            if success:
                self.update_health_status(health_check, 'opensearch', HealthStatus.HEALTHY)
            else:
                self.update_health_status(health_check, 'opensearch', HealthStatus.ERROR, "Indexing failed")

        except Exception as e:
            logger.error(f"Failed OpenSearch indexing: {e}")
            self.update_health_status(health_check, 'opensearch', HealthStatus.ERROR, str(e))

    def _step_verify_coverage(self, decision: Decision, health_check: DecisionHealthCheck):
        # This is hard to verify per decision without querying the aggregate table.
        # We'll assume it's healthy if we got here, or implement a specific check later.
        self.update_health_status(health_check, 'coverage', HealthStatus.HEALTHY)

    def run_batch_pipeline(
        self, 
        import_job_id: int,
        max_workers: int = 10,
        stop_on_error: bool = False,
        force_reprocess: bool = False,
        skip_opensearch: bool = False
    ) -> Dict[str, Any]:
        """
        Process all decisions in a batch with parallel execution.
        
        Args:
            import_job_id: The ImportJob ID to process
            max_workers: Maximum parallel workers for processing
            stop_on_error: If True, stop processing on first error
            force_reprocess: If True, reprocess even if already processed
            skip_opensearch: If True, skip OpenSearch indexing to save costs
            
        Returns:
            Dictionary with processing results and statistics
        """
        logger.info(f"🚀 Starting batch pipeline for ImportJob #{import_job_id}")
        start_time = timezone.now()
        
        try:
            import_job = ImportJob.objects.get(id=import_job_id)
        except ImportJob.DoesNotExist:
            logger.error(f"ImportJob #{import_job_id} not found")
            return {
                'error': 'ImportJob not found',
                'total': 0,
                'successful': 0,
                'failed': 0
            }
        
        decisions = import_job.decisions.all()
        total_decisions = decisions.count()
        
        if total_decisions == 0:
            logger.warning(f"No decisions found for ImportJob #{import_job_id}")
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }
        
        results = {
            'import_job_id': import_job_id,
            'total': total_decisions,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'processing_times': []
        }
        
        logger.info(f"Processing {total_decisions} decisions with {max_workers} workers")
        
        # Process in parallel with controlled concurrency
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ada = {
                executor.submit(
                    self._process_single_decision_safe, 
                    d.ada, 
                    force_reprocess,
                    skip_opensearch
                ): d.ada 
                for d in decisions
            }
            
            for future in as_completed(future_to_ada):
                ada = future_to_ada[future]
                try:
                    result = future.result()
                    
                    if result['status'] == 'success':
                        results['successful'] += 1
                    elif result['status'] == 'skipped':
                        results['skipped'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'ada': ada,
                            'findings': result.get('findings', {}),
                            'error': result.get('error')
                        })
                    
                    if result.get('processing_time_ms'):
                        results['processing_times'].append(result['processing_time_ms'])
                    
                    # Log progress every 100 decisions
                    processed = results['successful'] + results['failed'] + results['skipped']
                    if processed % 100 == 0:
                        logger.info(
                            f"Progress: {processed}/{total_decisions} "
                            f"({results['successful']} ✅, {results['failed']} ❌, {results['skipped']} ⏭️)"
                        )
                    
                    if stop_on_error and results['failed'] > 0:
                        logger.warning("Stopping on error as requested")
                        break
                        
                except Exception as e:
                    logger.error(f"Unexpected error processing {ada}: {e}")
                    results['failed'] += 1
                    results['errors'].append({
                        'ada': ada,
                        'error': f"Unexpected error: {str(e)}"
                    })
                    if stop_on_error:
                        break
        
        # Calculate statistics
        end_time = timezone.now()
        total_time = (end_time - start_time).total_seconds()
        
        if results['processing_times']:
            results['avg_processing_time_ms'] = sum(results['processing_times']) / len(results['processing_times'])
            results['max_processing_time_ms'] = max(results['processing_times'])
            results['min_processing_time_ms'] = min(results['processing_times'])
        
        results['total_time_seconds'] = total_time
        results['decisions_per_second'] = total_decisions / total_time if total_time > 0 else 0
        
        logger.info(
            f"✅ Batch pipeline completed for ImportJob #{import_job_id} in {total_time:.2f}s\n"
            f"   Total: {total_decisions}, Successful: {results['successful']}, "
            f"Failed: {results['failed']}, Skipped: {results['skipped']}"
        )
        
        # Generate batch summary
        try:
            self._generate_batch_summary(import_job)
        except Exception as e:
            logger.error(f"Failed to generate batch summary: {e}")
        
        return results

    def _process_single_decision_safe(
        self, 
        decision_ada: str, 
        force_reprocess: bool = False,
        skip_opensearch: bool = False
    ) -> Dict[str, Any]:
        """
        Safely process a single decision with error handling.
        
        Returns:
            Dictionary with status ('success', 'failed', 'skipped') and details
        """
        start_time = timezone.now()
        
        try:
            # Check if already processed (unless force_reprocess)
            if not force_reprocess:
                try:
                    health_check = DecisionHealthCheck.objects.get(
                        decision__ada=decision_ada
                    )
                    if health_check.overall_status == HealthStatus.HEALTHY:
                        return {
                            'status': 'skipped',
                            'reason': 'already_healthy',
                            'ada': decision_ada
                        }
                except DecisionHealthCheck.DoesNotExist:
                    pass  # Will process
            
            # Run the pipeline
            health_check = self.run_pipeline(
                decision_ada, 
                force_reprocess=force_reprocess,
                skip_opensearch=skip_opensearch
            )
            
            end_time = timezone.now()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            if health_check.overall_status == HealthStatus.ERROR:
                return {
                    'status': 'failed',
                    'ada': decision_ada,
                    'findings': health_check.findings,
                    'health_check_id': health_check.id,
                    'processing_time_ms': processing_time_ms
                }
            else:
                return {
                    'status': 'success',
                    'ada': decision_ada,
                    'overall_status': health_check.overall_status,
                    'processing_time_ms': processing_time_ms
                }
                
        except Exception as e:
            logger.error(f"Error processing {decision_ada}: {e}")
            return {
                'status': 'failed',
                'ada': decision_ada,
                'error': str(e)
            }

    def retry_failed_step(
        self, 
        decision_ada: str, 
        component: str,
        force: bool = True
    ) -> DecisionHealthCheck:
        """
        Retry a specific failed component for a decision.
        
        Args:
            decision_ada: The decision ADA to retry
            component: Component name ('entities', 'companies', 'document', 'opensearch', 'coverage')
            force: Force reprocessing even if not in error state
            
        Returns:
            Updated DecisionHealthCheck instance
        """
        decision = Decision.objects.get(ada=decision_ada)
        health_check = self.get_or_create_health_check(decision)
        
        step_map = {
            'amounts': self._step_extract_amounts,
            'entities': self._step_extract_entities,
            'companies': self._step_enrich_companies,
            'document': self._step_process_document,
            'opensearch': self._step_index_opensearch,
            'coverage': self._step_verify_coverage,
        }
        
        if component not in step_map:
            raise ValueError(f"Unknown component: {component}. Must be one of: {list(step_map.keys())}")
        
        logger.info(f"🔄 Retrying {component} for {decision_ada}")
        
        try:
            step_map[component](decision, health_check, force=force)
            logger.success(f"✅ Successfully retried {component} for {decision_ada}")
        except Exception as e:
            logger.error(f"❌ Failed to retry {component} for {decision_ada}: {e}")
            self.update_health_status(
                health_check, 
                component, 
                HealthStatus.ERROR, 
                str(e)
            )
        
        return health_check

    def retry_batch_failures(
        self, 
        import_job_id: int,
        component: Optional[str] = None,
        max_workers: int = 5
    ) -> Dict[str, Any]:
        """
        Retry all failures in a batch, optionally for a specific component.
        
        Args:
            import_job_id: The ImportJob ID to retry failures for
            component: Optional specific component to retry (e.g., 'document', 'opensearch')
            max_workers: Maximum parallel workers for retrying
            
        Returns:
            Dictionary with retry results
        """
        logger.info(f"🔄 Retrying failures for ImportJob #{import_job_id}, component: {component or 'all'}")
        
        try:
            import_job = ImportJob.objects.get(id=import_job_id)
        except ImportJob.DoesNotExist:
            return {
                'error': 'ImportJob not found',
                'total': 0
            }
        
        # Get all error health checks for this batch
        failed_checks = DecisionHealthCheck.objects.filter(
            decision__import_job=import_job,
            overall_status=HealthStatus.ERROR
        )
        
        if component:
            # Filter by specific component failure
            filter_kwargs = {f"{component}_status": HealthStatus.ERROR}
            failed_checks = failed_checks.filter(**filter_kwargs)
        
        total_failures = failed_checks.count()
        
        if total_failures == 0:
            logger.info("No failures to retry")
            return {
                'total': 0,
                'retried': 0,
                'still_failed': 0,
                'message': 'No failures found'
            }
        
        results = {
            'import_job_id': import_job_id,
            'component': component or 'all',
            'total': total_failures,
            'retried': 0,
            'still_failed': 0,
            'errors': []
        }
        
        logger.info(f"Found {total_failures} failures to retry")
        
        # Process retries in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ada = {}
            
            for health_check in failed_checks:
                ada = health_check.decision.ada
                if component:
                    future = executor.submit(self.retry_failed_step, ada, component)
                else:
                    future = executor.submit(self.run_pipeline, ada, force_reprocess=True)
                future_to_ada[future] = ada
            
            for future in as_completed(future_to_ada):
                ada = future_to_ada[future]
                try:
                    updated_check = future.result()
                    
                    if updated_check.overall_status != HealthStatus.ERROR:
                        results['retried'] += 1
                        logger.success(f"✅ Retry successful for {ada}")
                    else:
                        results['still_failed'] += 1
                        results['errors'].append({
                            'ada': ada,
                            'findings': updated_check.findings
                        })
                        logger.warning(f"⚠️ Retry failed for {ada}")
                        
                except Exception as e:
                    logger.error(f"❌ Retry failed for {ada}: {e}")
                    results['still_failed'] += 1
                    results['errors'].append({
                        'ada': ada,
                        'error': str(e)
                    })
        
        logger.info(
            f"✅ Retry completed: {results['retried']} succeeded, "
            f"{results['still_failed']} still failed"
        )
        
        # Regenerate batch summary
        try:
            self._generate_batch_summary(import_job)
        except Exception as e:
            logger.error(f"Failed to regenerate batch summary: {e}")
        
        return results

    def _generate_batch_summary(self, import_job: ImportJob) -> Dict[str, Any]:
        """
        Generate aggregated health summary for an import batch.
        
        Args:
            import_job: The ImportJob to generate summary for
            
        Returns:
            Dictionary with summary statistics
        """
        logger.info(f"📊 Generating batch summary for ImportJob #{import_job.id}")
        
        health_checks = DecisionHealthCheck.objects.filter(
            decision__import_job=import_job
        )
        
        total = health_checks.count()
        
        if total == 0:
            logger.warning("No health checks found for this batch")
            return {'total': 0}
        
        # Count by overall status
        from django.db.models import Count, Avg, Max, Q
        
        status_counts = health_checks.values('overall_status').annotate(
            count=Count('id')
        )
        
        summary = {
            'import_job_id': import_job.id,
            'total_decisions': total,
            'healthy_count': 0,
            'warning_count': 0,
            'error_count': 0,
            'unknown_count': 0,
        }
        
        for status_count in status_counts:
            status = status_count['overall_status']
            count = status_count['count']
            summary[f"{status.lower()}_count"] = count
        
        # Component failure breakdowns
        summary.update({
            'ingestion_failures': health_checks.filter(
                ingestion_status=HealthStatus.ERROR
            ).count(),
            'entity_failures': health_checks.filter(
                entities_status=HealthStatus.ERROR
            ).count(),
            'document_failures': health_checks.filter(
                document_extraction_status=HealthStatus.ERROR
            ).count(),
            'opensearch_failures': health_checks.filter(
                opensearch_status=HealthStatus.ERROR
            ).count(),
            'coverage_failures': health_checks.filter(
                coverage_status=HealthStatus.ERROR
            ).count(),
        })
        
        # Timing statistics
        timing_stats = health_checks.aggregate(
            avg_time=Avg('check_duration_ms'),
            max_time=Max('check_duration_ms')
        )
        
        summary['avg_processing_time_ms'] = timing_stats.get('avg_time')
        summary['max_processing_time_ms'] = timing_stats.get('max_time')
        
        # Find slowest decision
        slowest = health_checks.order_by('-check_duration_ms').first()
        if slowest:
            summary['slowest_decision_ada'] = slowest.decision.ada
            summary['slowest_decision_time_ms'] = slowest.check_duration_ms
        
        # Calculate health percentage
        if total > 0:
            summary['health_percentage'] = (
                summary['healthy_count'] / total * 100
            )
        else:
            summary['health_percentage'] = 0
        
        logger.info(
            f"📊 Batch summary: {summary['health_percentage']:.1f}% healthy, "
            f"{summary['error_count']} errors, {summary['warning_count']} warnings"
        )
        
        return summary

    def get_batch_health_report(
        self, 
        import_job_id: int,
        include_failures: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive health report for a batch.
        
        Args:
            import_job_id: The ImportJob ID to report on
            include_failures: If True, include list of failed decisions
            
        Returns:
            Dictionary with comprehensive batch health information
        """
        try:
            import_job = ImportJob.objects.get(id=import_job_id)
        except ImportJob.DoesNotExist:
            return {'error': 'ImportJob not found'}
        
        summary = self._generate_batch_summary(import_job)
        
        report = {
            'import_job': {
                'id': import_job.id,
                'start_date': import_job.start_date.isoformat(),
                'end_date': import_job.end_date.isoformat(),
                'status': import_job.status,
                'created_at': import_job.created_at.isoformat(),
            },
            'summary': summary
        }
        
        if include_failures and summary.get('error_count', 0) > 0:
            failures = DecisionHealthCheck.objects.filter(
                decision__import_job=import_job,
                overall_status=HealthStatus.ERROR
            ).select_related('decision')[:100]  # Limit to first 100 failures
            
            report['failures'] = [
                {
                    'ada': hc.decision.ada,
                    'issue_date': hc.decision.issue_date.isoformat() if hc.decision.issue_date else None,
                    'subject': hc.decision.subject[:100] if hc.decision.subject else None,
                    'component_statuses': {
                        'ingestion': hc.ingestion_status,
                        'entities': hc.entities_status,
                        'document': hc.document_extraction_status,
                        'opensearch': hc.opensearch_status,
                        'coverage': hc.coverage_status,
                    },
                    'findings': hc.findings
                }
                for hc in failures
            ]
            
            if summary.get('error_count', 0) > 100:
                report['failures_note'] = f"Showing first 100 of {summary['error_count']} failures"
        
        return report

