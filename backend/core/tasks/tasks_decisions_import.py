"""
Decision Import Tasks - Distributed Pipeline for Daily Decision Ingestion

⚠️ CRITICAL BUG FIX (2026-01-04):
   Removed apply_async(countdown=X) due to Celery 5.6.1 bug with RabbitMQ without 
   delayed message exchange plugin. Tasks with countdown were silently lost.
   
   Solution: Moved delay inside tasks using time.sleep() to prevent race conditions.
   See: /docs/celery-countdown-bug-research.md for full investigation.

Architecture:
    1. fetch_daily_decisions_to_pickle: Fetches full day from API
    2. Splits into chunks, dispatches store_decisions_from_pickle for each
    3. Each storage task sleeps before processing (prevents DB deadlocks)
"""
from celery import shared_task
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger
import time
import random
from core.fetchers.diavgeia_fetcher import DiavgeiaFetcher
from core.importers.decisions import DecisionImporter
from core.services.redis_decision_cache import RedisDecisionCache
from core.models.import_jobs import ImportJobStatus, ImportJob
from django.db import transaction
from django.utils import timezone


@shared_task(bind=True, max_retries=3)
def fetch_daily_decisions_to_redis(self, target_date_str: str, 
                                   search_params: Optional[Dict[str, Any]] = None,
                                   chunk_size: int = 10):
    """
    Phase 1: Fetch ALL decisions for a full day and save to Redis with batch tracking.
    
    IMPROVEMENTS:
    - Uses Redis instead of filesystem pickles (no lost files on container restart)
    - Creates ImportBatch record for tracking progress
    - Provides visibility into import status
    
    Args:
        target_date_str: Date in ISO format (e.g., "2025-03-09")
        search_params: Additional search parameters
        chunk_size: Number of decisions per chunk (default: 10)
        
    Returns:
        Dict with batch_id, Redis keys, and metadata
    """
    try:
        from datetime import datetime
        target_date = datetime.fromisoformat(target_date_str).date()
        # Check if job already exists (prevent duplicate imports)
        existing_job = ImportJob.objects.filter(
            start_date=target_date,
            end_date=target_date,
            status__in=[
                ImportJobStatus.FETCHING,
                ImportJobStatus.SPLITTING,
                ImportJobStatus.PROCESSING
            ]
        ).first()
        
        if existing_job:
            logger.warning(
                f"Task {self.request.id}: Import already in progress for {target_date} "
                f"(job ID {existing_job.id})"
            )
            return {
                'status': 'duplicate',
                'message': f'Import already in progress for {target_date}',
                'existing_job_id': existing_job.id
            }
        
        # Create ImportJob record
        import_job = ImportJob.objects.create(
            start_date=target_date,
            end_date=target_date,
            celery_task_id=self.request.id,
            status=ImportJobStatus.FETCHING,
            search_params=search_params,
            created_at=timezone.now()
        )
        
        logger.info(f"Task {self.request.id}: Created ImportJob {import_job.id} for {target_date}")
        
        # Create fetcher and get decisions for the full day
        fetcher = DiavgeiaFetcher()
        
        # Build search parameters for full day
        if search_params is None:
            search_params = {}
        
        search_params.update({
            "from_issue_date": target_date.isoformat(),
            "to_issue_date": (target_date + timedelta(days=1)).isoformat(),
            "page": 0,
            "size": 500
        })
        
        # Fetch all pages for this full day
        all_decisions = []
        page = 0
        total_pages = 1
        
        while page < total_pages:
            search_params["page"] = page
            response = fetcher.fetch_decisions(**search_params)
            
            if response and response.info:
                if page == 0 and response.info.total > 0:
                    page_size = search_params.get("size", 500)
                    total_pages = (response.info.total + page_size - 1) // page_size
                    logger.info(
                        f"Task {self.request.id}: Found {response.info.total} decisions, "
                        f"{total_pages} pages for {target_date}"
                    )
                
                all_decisions.extend(response.decisions)
                page += 1
                
                if response.info.actualSize < search_params.get("size", 500):
                    break
            else:
                logger.warning(f"Task {self.request.id}: No response for page {page}")
                break
        
        # Update job with total count
        import_job.total_decisions = len(all_decisions)
        import_job.status = ImportJobStatus.SPLITTING
        import_job.save(update_fields=['total_decisions', 'status'])
        
        logger.success(
            f"Task {self.request.id}: Fetched {len(all_decisions)} decisions for {target_date}"
        )
        
        # Initialize Redis cache
        redis_cache = RedisDecisionCache()
        
        # Split into chunks and store in Redis
        storage_tasks = []
        total_chunks = (len(all_decisions) + chunk_size - 1) // chunk_size
        
        for i in range(0, len(all_decisions), chunk_size):
            chunk_decisions = all_decisions[i:i + chunk_size]
            chunk_index = i // chunk_size
            chunk_id = f"{import_job.id}_chunk_{chunk_index}"
            
            # Store chunk in Redis with metadata
            metadata = {
                'job_id': import_job.id,
                'target_date': target_date_str,
                'chunk_index': chunk_index,
                'total_chunks': total_chunks,
                'parent_task': self.request.id,
            }
            
            redis_cache.store_chunk(
                chunk_id=chunk_id,
                decisions=chunk_decisions,
                metadata=metadata
            )
            
            # Dispatch storage task with internal delay to prevent race conditions
            delay_seconds = random.uniform(0.1, 2.0)
            
            storage_task = store_decisions_from_redis.apply_async(
                args=[chunk_id, import_job.id],
                kwargs={
                    'delay_seconds': delay_seconds
                }
            )
            storage_tasks.append(storage_task.id)
            
            logger.debug(
                f"Dispatched storage task {storage_task.id} for chunk {chunk_index}/{total_chunks}"
            )
        
        # Update job record with chunk task IDs
        import_job.total_chunks = total_chunks
        import_job.chunk_task_ids = storage_tasks
        import_job.status = ImportJobStatus.PROCESSING
        import_job.save(update_fields=['total_chunks', 'chunk_task_ids', 'status'])
        
        logger.success(
            f"Task {self.request.id}: Split {len(all_decisions)} decisions into "
            f"{total_chunks} chunks, dispatched {len(storage_tasks)} storage tasks"
        )
        
        return {
            'status': 'success',
            'job_id': import_job.id,
            'decisions_count': len(all_decisions),
            'chunks_created': total_chunks,
            'target_date': target_date_str,
            'storage_tasks': storage_tasks,
            'task_id': self.request.id
        }
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Fetch failed: {str(e)}")
        
        # Update job status if it exists
        try:
            import_job = ImportJob.objects.get(celery_task_id=self.request.id)
            import_job.status = ImportJobStatus.FAILED
            import_job.error_details = str(e)
            import_job.save(update_fields=['status', 'error_details'])
        except ImportJob.DoesNotExist:
            pass
        
        # Celery retry with exponential backoff
        raise self.retry(
            countdown=60 * (2 ** self.request.retries),
            exc=e
        )


@shared_task(bind=True, max_retries=5)
def store_decisions_from_redis(self, chunk_id: str, job_id: int, 
                              skip_opensearch: bool = False, delay_seconds: float = 0):
    """
    Phase 2: Load decisions from Redis and run through full pipeline with job tracking.
    
    IMPROVEMENTS:
    - Reads from Redis instead of filesystem (reliable across container restarts)
    - Updates ImportJob progress atomically
    - Automatic cleanup of processed chunks
    - Better error handling and retry logic
    
    ⚠️ CRITICAL: Implements internal delay via time.sleep() to prevent DB race conditions.
    This is safer than apply_async(countdown=X) which causes task loss in Celery 5.6.1.
    
    The orchestrator handles the complete lifecycle:
    - Stage 0: Import decision from DTO to database
    - Stage 1-7: Organizations, entities, amounts, companies, documents, opensearch, coverage
    
    Args:
        chunk_id: Redis key identifier for this chunk
        job_id: ImportJob ID for progress tracking
        skip_opensearch: Skip OpenSearch indexing to reduce infrastructure costs
        delay_seconds: Sleep this many seconds before processing (prevents race conditions)
    """
    # ⚠️ BUG FIX (2026-01-04): Delay INSIDE task instead of countdown parameter
    if delay_seconds > 0:
        logger.info(f"Task {self.request.id}: Sleeping {delay_seconds:.2f}s to prevent race conditions")
        time.sleep(delay_seconds)
    
    try:
        logger.info(f"Task {self.request.id}: Processing chunk {chunk_id} for job {job_id}")
        
        # Initialize Redis cache
        redis_cache = RedisDecisionCache()
        
        # Load decisions from Redis (auto-deletes after read)
        chunk_data = redis_cache.get_chunk(chunk_id, delete_after_read=True)
        
        if not chunk_data:
            raise FileNotFoundError(
                f"Chunk not found in Redis: {chunk_id}. "
                f"May have expired or been processed already."
            )
        
        decisions = chunk_data['decisions']
        metadata = chunk_data.get('metadata', {})
        
        logger.info(
            f"Task {self.request.id}: Loaded {len(decisions)} decisions from Redis chunk {chunk_id}"
        )
        
        # Get ImportJob for progress tracking
        try:
            import_job = ImportJob.objects.get(id=job_id)
        except ImportJob.DoesNotExist:
            logger.error(f"Task {self.request.id}: ImportJob {job_id} not found!")
            import_job = None
        
        # Import decisions and dispatch pipeline tasks using orchestrator
        from core.services.pipeline_orchestrator import DecisionPipelineOrchestrator
        from core.tasks.tasks_documents import run_decision_pipeline_task
        from core.utils.discovery_tracking import (
            DiscoverySource,
            add_discovery_source_to_decision
        )
        
        orchestrator = DecisionPipelineOrchestrator()
        dispatched_tasks = []
        failed_imports = []
        
        logger.info(
            f"Task {self.request.id}: Processing {len(decisions)} decisions through orchestrator"
        )
        
        for i, decision_dto in enumerate(decisions, 1):
            try:
                # Import decision using orchestrator (Stage 0)
                decision = orchestrator._step_import_decision(decision_dto)
                
                if decision:
                    # Tag with discovery source
                    add_discovery_source_to_decision(
                        decision,
                        source_type=DiscoverySource.DEFAULT_SEARCH,
                        search_params=metadata.get('search_params', {}),
                        notes=f"Job {job_id}",
                        save=True
                    )
                    
                    # Check if decision needs processing
                    from core.models.decision_health import DecisionHealthCheck, HealthStatus
                    health_check = DecisionHealthCheck.objects.filter(decision=decision).first()
                    
                    needs_processing = True
                    if health_check and health_check.overall_status == HealthStatus.HEALTHY:
                        needs_processing = False
                        logger.debug(
                            f"Task {self.request.id}: Skipping {decision.ada} - already healthy"
                        )
                    
                    if needs_processing:
                        # Dispatch pipeline task for full processing
                        pipeline_task = run_decision_pipeline_task.delay(
                            ada=decision.ada,
                            force_reprocess=False,
                            skip_opensearch=skip_opensearch
                        )
                        dispatched_tasks.append({
                            'ada': decision.ada,
                            'task_id': pipeline_task.id
                        })
                else:
                    failed_imports.append({
                        'ada': decision_dto.ada,
                        'error': 'Import returned None'
                    })
                        
            except Exception as decision_error:
                error_msg = str(decision_error).lower()
                decision_ada = getattr(decision_dto, 'ada', 'unknown')
                
                # Check if it's a critical database error
                is_critical_db_error = any(keyword in error_msg for keyword in [
                    "deadlock", "lock", "current transaction is aborted"
                ])
                
                if is_critical_db_error:
                    logger.error(
                        f"Task {self.request.id}: Critical DB error on {decision_ada}: {decision_error}"
                    )
                    raise decision_error  # Fail the whole chunk
                else:
                    logger.warning(
                        f"Task {self.request.id}: Failed to process {decision_ada}: {decision_error}"
                    )
                    failed_imports.append({
                        'ada': decision_ada,
                        'error': str(decision_error)
                    })
        
        # Update ImportJob progress
        if import_job:
            if failed_imports:
                import_job.mark_chunk_failed(
                    error_msg=f"{len(failed_imports)} failures in chunk {chunk_id}",
                    decisions_count=len(failed_imports)
                )
            else:
                import_job.mark_chunk_completed(decisions_count=len(dispatched_tasks))
            
            logger.info(
                f"Task {self.request.id}: Updated job {job_id} progress: "
                f"{import_job.chunks_completed}/{import_job.total_chunks} chunks completed "
                f"({import_job.progress_percentage:.1f}%)"
            )
        
        logger.success(
            f"Task {self.request.id}: Processed chunk {chunk_id}, "
            f"dispatched {len(dispatched_tasks)} pipeline tasks"
        )
        
        return {
            'status': 'success',
            'chunk_id': chunk_id,
            'job_id': job_id,
            'decisions_loaded': len(decisions),
            'decisions_processed': len(dispatched_tasks),
            'decisions_failed': len(failed_imports),
            'failed_imports': failed_imports[:10],
            'pipeline_tasks_dispatched': len(dispatched_tasks),
            'task_id': self.request.id,
        }
        
    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"Task {self.request.id}: Storage failed for chunk {chunk_id}: {str(e)}")
        
        # Update job with failure
        try:
            import_job = ImportJob.objects.get(id=job_id)
            import_job.mark_chunk_failed(error_msg=str(e))
        except ImportJob.DoesNotExist:
            pass
        
        # Check for specific database errors
        is_deadlock = "deadlock detected" in error_msg
        is_aborted_transaction = "current transaction is aborted" in error_msg
        is_db_error = any(keyword in error_msg for keyword in [
            "deadlock", "lock", "transaction", "database", "connection"
        ])
        
        have_we_got_any_db_errors = is_deadlock or is_aborted_transaction or is_db_error
        have_we_reached_max_retries = self.request.retries < self.max_retries

        if have_we_got_any_db_errors and have_we_reached_max_retries:
            # For database errors, implement aggressive backoff with jitter
            base_delay = 20 * (3 ** self.request.retries)  # 20s, 60s, 180s, 540s, 1620s
            jitter = random.uniform(0, base_delay * 0.5)
            delay = int(base_delay + jitter)
            
            logger.warning(
                f"Task {self.request.id}: Database error (deadlock:{is_deadlock}, "
                f"aborted:{is_aborted_transaction}), retrying in {delay}s"
            )
            
            raise self.retry(countdown=delay, exc=e)
            
        elif self.request.retries < self.max_retries:
            # For non-database errors, standard retry
            logger.info(f"Task {self.request.id}: Retrying after non-DB error")
            raise self.retry(
                countdown=30 * (2 ** self.request.retries),
                exc=e
            )
        else:
            # Max retries reached - chunk will remain failed in batch
            logger.error(f"Task {self.request.id}: Max retries reached for chunk {chunk_id}")
            raise


# Legacy compatibility wrapper (for existing code that calls the old function)
@shared_task(bind=True, max_retries=5)
def store_decisions_from_pickle(self, pickle_file: str, **kwargs):
    """
    DEPRECATED: Legacy compatibility wrapper for code using pickle files.
    
    This exists only to prevent breaking existing scheduled tasks.
    New code should use store_decisions_from_redis instead.
    """
    logger.warning(
        f"Task {self.request.id}: Using deprecated store_decisions_from_pickle. "
        f"Please migrate to store_decisions_from_redis."
    )
    raise NotImplementedError(
        "Pickle-based imports are deprecated. Use fetch_daily_decisions_to_redis instead."
    )


@shared_task(bind=True)
def fetch_daily_decisions_distributed(self, target_date_str: str, chunk_size: int = 10):
    """
    Orchestrator task: Fetches full day of decisions and distributes storage work using Redis.
    
    This is the main entry point for daily decision imports.
    
    Args:
        target_date_str: Date to fetch in ISO format (e.g., "2025-03-09")
        chunk_size: Number of decisions per chunk (default: 10)
        
    Returns:
        Dict with orchestration results including batch_id for tracking
    """
    try:
        from datetime import datetime
        target_date = datetime.fromisoformat(target_date_str).date()
        
        logger.info(f"Orchestrator {self.request.id}: Starting distributed import for {target_date}")
        
        # Dispatch the fetch task (will create batch and store in Redis)
        fetch_task = fetch_daily_decisions_to_redis.delay(
            target_date_str=target_date_str,
            chunk_size=chunk_size
        )
        
        logger.info(
            f"Orchestrator {self.request.id}: Dispatched fetch task {fetch_task.id} for {target_date}"
        )
        
        return {
            'status': 'dispatched',
            'target_date': target_date_str,
            'fetch_task_id': fetch_task.id,
            'orchestrator_id': self.request.id,
            'note': 'Fetch task will automatically create ImportBatch for progress tracking'
        }
        
    except Exception as e:
        logger.error(f"Orchestrator {self.request.id}: Failed to dispatch: {str(e)}")
        raise
        return {
            'status': 'dispatched',
            'target_date': target_date_str,
            'fetch_task_id': fetch_task.id,
            'orchestrator_id': self.request.id,
            'note': 'Fetch task will automatically split storage into multiple workers'
        }
        
    except Exception as e:
        logger.error(f"Orchestrator {self.request.id}: Failed to dispatch fetch task: {str(e)}")
        raise