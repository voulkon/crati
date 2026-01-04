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
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from loguru import logger
import pickle
import os
from core.fetchers.diavgeia_fetcher import DiavgeiaFetcher
from core.importers.decisions import DecisionImporter
from core.constants.decision_import_constants import PICKLE_DIR
from django.db import transaction
import time
import random


@shared_task(bind=True, max_retries=3)
def fetch_daily_decisions_to_pickle(self, target_date_str: str, 
                                   search_params: Optional[Dict[str, Any]] = None):
    """
    Phase 1: Fetch ALL decisions for a full day and save to pickle
    Note: API doesn't support hourly queries, must fetch entire day
    
    Args:
        target_date_str: Date in ISO format
        search_params: Additional search parameters
        
    Returns:
        Dict with pickle file path and metadata
    """
    try:
        from datetime import datetime
        target_date = datetime.fromisoformat(target_date_str).date()
        
        logger.info(f"Task {self.request.id}: Fetching ALL decisions for {target_date}")
        
        # Create fetcher and get decisions for the full day
        fetcher = DiavgeiaFetcher()
        
        # Build search parameters for full day
        if search_params is None:
            search_params = {}
        
        search_params.update({
            "from_issue_date": target_date.isoformat(),
            "to_issue_date": target_date.isoformat(),
            "page": 0,
            "size": 500
        })
        
        # Fetch all pages for this full day
        all_decisions = []
        page = 0
        total_pages = 1  # Assume at least one page initially
        
        while page < total_pages:
            search_params["page"] = page
            
            response = fetcher.fetch_decisions(**search_params)
            
            if response and response.info:
                if page == 0 and response.info.total > 0:
                    # Calculate total pages from total count and page size
                    page_size = search_params.get("size", 500)
                    total_pages = (response.info.total + page_size - 1) // page_size
                    logger.info(f"Task {self.request.id}: Found {response.info.total} total decisions, {total_pages} pages for {target_date}")
                
                all_decisions.extend(response.decisions)
                page += 1
                logger.info(f"Task {self.request.id}: Fetched page {page}/{total_pages}")
                
                # Check if we've reached the last page
                if response.info.actualSize < search_params.get("size", 500):
                    logger.info(f"Task {self.request.id}: Reached last page (actualSize {response.info.actualSize})")
                    break
            else:
                logger.warning(f"Task {self.request.id}: No response for page {page}")
                break
        
        # Create pickle directory (PICKLE_DIR already includes 'pickles', don't double it)
        pickle_dir = PICKLE_DIR
        os.makedirs(pickle_dir, exist_ok=True)
        
        # Generate pickle file for the full day
        pickle_file = f"{pickle_dir}/decisions_{target_date}_{datetime.now().strftime('%H%M%S')}.pkl"
        
        # Save ALL decisions to pickle
        pickle_data = {
            'decisions': all_decisions,
            'target_date': target_date_str,
            'search_params': search_params,
            'fetch_timestamp': datetime.now().isoformat(),
            'task_id': self.request.id,
            'count': len(all_decisions)
        }
        
        with open(pickle_file, 'wb') as f:
            pickle.dump(pickle_data, f)
        
        logger.success(f"Task {self.request.id}: Saved {len(all_decisions)} decisions for {target_date} to {pickle_file}")
        
        # Now split the storage work into TINY chunks to prevent deadlocks
        chunk_size = 10  # TODO: Make it a global constant or env var
        storage_tasks = []
        
        for i in range(0, len(all_decisions), chunk_size):
            chunk_decisions = all_decisions[i:i + chunk_size]
            chunk_id = f"{target_date}_{i//chunk_size + 1}"
            
            # Create smaller pickle for this chunk
            chunk_pickle = f"{pickle_dir}/chunk_{chunk_id}_{datetime.now().strftime('%H%M%S')}.pkl"
            chunk_data = {
                'decisions': chunk_decisions,
                'chunk_id': chunk_id,
                'parent_task': self.request.id,
                'target_date': target_date_str,
                'chunk_index': i // chunk_size,
                'count': len(chunk_decisions)
            }
            
            with open(chunk_pickle, 'wb') as f:
                pickle.dump(chunk_data, f)
            
            # Dispatch storage task without countdown parameter
            # ⚠️ DO NOT use apply_async(countdown=X) - causes silent task loss in Celery 5.6.1
            # Instead, delay happens INSIDE the task via time.sleep() - see delay_seconds kwarg
            # TODO: NUMBER_OF_WORKERS instead of 4
            delay_seconds = random.uniform(0.1, 2)
            # TODO: NUMBER_OF_WORKERS instead of 4

            storage_task = store_decisions_from_pickle.apply_async(
                args=[chunk_pickle],
                kwargs={
                    'batch_size': 1,  # Always start with sequential processing
                    'delay_seconds': delay_seconds  # Task will sleep before processing
                }
            )
            storage_tasks.append(storage_task.id)
            logger.info(f"Dispatched storage task {storage_task.id} for chunk {chunk_id} (will delay {delay_seconds}s inside task)")
        
        logger.success(f"Task {self.request.id}: Split into {len(storage_tasks)} storage tasks")
        
        return {
            'status': 'success',
            'pickle_file': pickle_file,
            'decisions_count': len(all_decisions),
            'target_date': target_date_str,
            'storage_tasks': storage_tasks,
            'task_id': self.request.id
        }
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Fetch failed: {str(e)}")
        
        # Celery retry with exponential backoff
        raise self.retry(
            countdown=60 * (2 ** self.request.retries),  # 60s, 120s, 240s
            exc=e
        )


@shared_task(bind=True, max_retries=5)
def store_decisions_from_pickle(self, pickle_file: str, batch_size: int = 25, skip_opensearch: bool = False, delay_seconds: int = 0):
    """
    Phase 2: Load decisions from pickle and run through full pipeline.
    
    ⚠️ CRITICAL: Implements internal delay via time.sleep() to prevent DB race conditions.
    This is safer than apply_async(countdown=X) which causes task loss in Celery 5.6.1.
    
    The orchestrator handles the complete lifecycle:
    - Stage 0: Import decision from DTO to database
    - Stage 1: Resolve organizations for signers and units
    - Stage 2-7: Entity extraction, amounts, companies, documents, opensearch, coverage
    
    Args:
        pickle_file: Path to the pickle file containing decisions
        batch_size: Deprecated - kept for compatibility but now processes one-by-one
        skip_opensearch: Skip OpenSearch indexing to reduce infrastructure costs
        delay_seconds: Sleep this many seconds before processing (prevents race conditions)
    """
    # ⚠️ BUG FIX (2026-01-04): Delay INSIDE task instead of countdown parameter
    # Reason: apply_async(countdown=X) silently loses tasks in Celery 5.6.1 without
    #         RabbitMQ delayed message exchange plugin installed
    if delay_seconds > 0:
        import time
        logger.info(f"Task {self.request.id}: Sleeping {delay_seconds}s to prevent race conditions")
        time.sleep(delay_seconds)
    
    try:
        logger.info(f"Task {self.request.id}: Loading decisions from {pickle_file}")
        
        # Load decisions from pickle
        if not os.path.exists(pickle_file):
            raise FileNotFoundError(f"Pickle file not found: {pickle_file}")
        
        with open(pickle_file, 'rb') as f:
            pickle_data = pickle.load(f)
        
        decisions = pickle_data['decisions']
        logger.info(f"Task {self.request.id}: Loaded {len(decisions)} decisions from pickle")
        
        # Import decisions and dispatch pipeline tasks using orchestrator
        from core.services.pipeline_orchestrator import DecisionPipelineOrchestrator
        from core.tasks.tasks_documents import run_decision_pipeline_task
        
        orchestrator = DecisionPipelineOrchestrator()
        dispatched_tasks = []
        failed_imports = []
        
        logger.info(f"Task {self.request.id}: Processing {len(decisions)} decisions through orchestrator")
        
        for i, decision_dto in enumerate(decisions, 1):
            try:
                # Import decision using orchestrator (Stage 0)
                decision = orchestrator._step_import_decision(decision_dto)
                
                if decision:
                    # Dispatch pipeline task for full processing (Stages 1-7)
                    # Note: We don't pass decision_dto here since it's already imported
                    pipeline_task = run_decision_pipeline_task.delay(
                        ada=decision.ada,
                        force_reprocess=False,
                        skip_opensearch=skip_opensearch
                    )
                    dispatched_tasks.append({
                        'ada': decision.ada,
                        'task_id': pipeline_task.id
                    })
                    
                    if i % 10 == 0:
                        logger.info(f"Task {self.request.id}: Processed {i}/{len(decisions)} decisions")
                else:
                    failed_imports.append({
                        'ada': decision_dto.ada,
                        'error': 'Import failed'
                    })
                        
            except Exception as decision_error:
                error_msg = str(decision_error).lower()
                decision_ada = getattr(decision_dto, 'ada', 'unknown')
                
                # Check if it's a deadlock or database error
                is_critical_db_error = any(keyword in error_msg for keyword in [
                    "deadlock", "lock", "current transaction is aborted"
                ])
                
                if is_critical_db_error:
                    logger.error(f"Task {self.request.id}: Critical DB error on decision {decision_ada}: {decision_error}")
                    # For critical errors, fail the whole task
                    raise decision_error
                else:
                    # For non-critical errors, log and continue
                    logger.warning(f"Task {self.request.id}: Failed to process decision {decision_ada}: {decision_error}")
                    failed_imports.append({
                        'ada': decision_ada,
                        'error': str(decision_error)
                    })
        
        logger.success(
            f"Task {self.request.id}: Dispatched {len(dispatched_tasks)} pipeline tasks for parallel processing"
        )
        
        # Check results
        if len(decisions) > 0 and len(dispatched_tasks) == 0 and not failed_imports:
            logger.warning(f"Task {self.request.id}: No decisions were processed from {len(decisions)} decisions (likely duplicates)")
        
        # Move pickle to completed folder (only if file exists - may have been moved by retry)
        completed_dir = f"{PICKLE_DIR}/completed"
        os.makedirs(completed_dir, exist_ok=True)
        completed_file = os.path.join(completed_dir, os.path.basename(pickle_file))
        if os.path.exists(pickle_file):
            os.rename(pickle_file, completed_file)
        else:
            logger.warning(f"Task {self.request.id}: Pickle file {pickle_file} not found (may have been moved already)")
            # Check if it's already in completed
            if os.path.exists(completed_file):
                logger.info(f"Task {self.request.id}: File already in completed folder")
            else:
                logger.error(f"Task {self.request.id}: File missing from both locations")
        
        # Log final results
        if failed_imports:
            logger.warning(f"Task {self.request.id}: {len(failed_imports)} failures out of {len(decisions)}")
        
        if len(dispatched_tasks) > 0:
            logger.success(
                f"Task {self.request.id}: Processed {len(dispatched_tasks)}/{len(decisions)} decisions, "
                f"dispatched {len(dispatched_tasks)} pipeline tasks, moved pickle to {completed_file}"
            )
        else:
            logger.info(f"Task {self.request.id}: No decisions processed (possibly duplicates), moved pickle to {completed_file}")
        
        return {
            'status': 'success',
            'pickle_file': pickle_file,
            'completed_file': completed_file,
            'decisions_loaded': len(decisions),
            'decisions_processed': len(dispatched_tasks),
            'decisions_failed': len(failed_imports),
            'failed_imports': failed_imports[:10],  # Only first 10 failures for logging
            'pipeline_tasks_dispatched': len(dispatched_tasks),
            'dispatched_task_ids': [t['task_id'] for t in dispatched_tasks[:10]],  # First 10 task IDs
            'task_id': self.request.id,
        }
        
    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"Task {self.request.id}: Storage failed: {str(e)}")
        
        # Check for specific database errors
        is_deadlock = "deadlock detected" in error_msg
        is_aborted_transaction = "current transaction is aborted" in error_msg
        is_db_error = any(keyword in error_msg for keyword in [
            "deadlock", "lock", "transaction", "database", "connection"
        ])
        have_we_got_any_db_errors = is_deadlock or is_aborted_transaction or is_db_error
        have_we_reached_max_retries = self.request.retries < self.max_retries

        if have_we_got_any_db_errors and have_we_reached_max_retries:
            # For database errors, implement aggressive backoff
            base_delay = 20 * (3 ** self.request.retries)  # 20s, 60s, 180s, 540s, 1620s
            jitter = random.uniform(0, base_delay * 0.5)  # Add up to 50% jitter
            delay = int(base_delay + jitter)
            
            # On database errors, always go to batch_size=1 (one decision at a time)
            new_batch_size = 1
            
            logger.warning(f"Task {self.request.id}: Database error detected, retrying in {delay}s with batch_size=1 (sequential processing)")
            logger.warning(f"Task {self.request.id}: Error type - deadlock:{is_deadlock}, aborted:{is_aborted_transaction}")
            
            raise self.retry(
                countdown=delay,
                kwargs={'batch_size': new_batch_size, 'skip_opensearch': skip_opensearch},  # Don't pass pickle_file here (it's in args)
                exc=e
            )
        elif self.request.retries < self.max_retries:
            # For non-database errors, use smaller batch size
            new_batch_size = max(1, batch_size // 2)
            logger.info(f"Task {self.request.id}: Retrying with batch_size: {new_batch_size}")
            
            raise self.retry(
                countdown=30 * (2 ** self.request.retries),
                kwargs={'batch_size': new_batch_size, 'skip_opensearch': skip_opensearch},  # Don't pass pickle_file here (it's in args)
                exc=e
            )
        else:
            # Max retries reached
            failed_dir = f"{PICKLE_DIR}/failed"
            os.makedirs(failed_dir, exist_ok=True)
            failed_file = os.path.join(failed_dir, os.path.basename(pickle_file))
            
            try:
                os.rename(pickle_file, failed_file)
                logger.error(f"Task {self.request.id}: Max retries reached, moved to {failed_file}")
            except:
                pass
            
            raise


@shared_task(bind=True)
def fetch_daily_decisions_distributed(self, target_date_str: str):
    """
    Orchestrator task: Fetches full day of decisions and distributes storage work
    
    Args:
        target_date_str: Date to fetch in ISO format
        
    Returns:
        Dict with orchestration results
    """
    try:
        from datetime import datetime
        target_date = datetime.fromisoformat(target_date_str).date()
        
        logger.info(f"Orchestrator {self.request.id}: Starting distributed import for {target_date}")
        
        # Dispatch the single fetch task for the full day
        fetch_task = fetch_daily_decisions_to_pickle.delay(target_date_str)
        
        logger.info(f"Orchestrator {self.request.id}: Dispatched fetch task {fetch_task.id} for {target_date}")
        
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