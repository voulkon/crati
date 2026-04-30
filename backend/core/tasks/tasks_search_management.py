"""
Celery tasks for PostgreSQL search management operations.

These tasks handle long-running search management operations like:
- Backfilling search vectors
- Cleaning up search vectors
- Managing triggers and indexes
"""

from celery import shared_task
from django.core.management import call_command
from io import StringIO
from loguru import logger
import time


@shared_task(bind=True, name="search.backfill_search_vectors")
def backfill_search_vectors_task(self, model: str = 'both', batch_size: int = 1000, only_null: bool = True):
    """
    Backfill search_vector for DocumentExtraction and/or DocumentPage.
    
    Args:
        model: Which model to backfill ('extraction', 'page', or 'both')
        batch_size: Number of records to process per batch
        only_null: If True, only backfill NULL search_vector fields
    
    Returns:
        dict with status, duration, and output
    """
    logger.info(f"Starting backfill_search_vectors task: model={model}, batch_size={batch_size}")
    
    # Update task state
    self.update_state(
        state='STARTED',
        meta={
            'model': model,
            'batch_size': batch_size,
            'status': 'Running backfill...'
        }
    )
    
    start_time = time.time()
    output = StringIO()
    
    try:
        call_command(
            'backfill_search_vectors',
            model=model,
            batch_size=batch_size,
            only_null=only_null,
            force=True,
            stdout=output
        )
        
        elapsed = time.time() - start_time
        output_text = output.getvalue()
        
        result = {
            'status': 'success',
            'model': model,
            'duration_seconds': round(elapsed, 2),
            'output': output_text,
            'message': f'Backfill completed successfully in {elapsed:.1f} seconds'
        }
        
        logger.info(f"Completed backfill_search_vectors for {model} in {elapsed:.1f}s")
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Backfill failed for {model}: {error_msg}")
        
        return {
            'status': 'error',
            'model': model,
            'duration_seconds': round(elapsed, 2),
            'error': error_msg,
            'message': f'Backfill failed: {error_msg}'
        }
    finally:
        output.close()


@shared_task(bind=True, name="search.cleanup_search_vectors")
def cleanup_search_vectors_task(self, model: str = 'both', batch_size: int = 5000, 
                                no_vacuum: bool = False, vacuum_full: bool = False):
    """
    NULL out search_vector data and VACUUM to reclaim disk space.
    
    Args:
        model: Which model to clean up ('extraction', 'page', or 'both')
        batch_size: Number of records to process per batch
        no_vacuum: If True, skip VACUUM (faster, but no space reclaimed)
        vacuum_full: If True, use VACUUM FULL (max space reclamation, locks table)
    
    Returns:
        dict with status, duration, and output
    """
    logger.info(f"Starting cleanup_search_vectors task: model={model}, vacuum_full={vacuum_full}")
    
    # Update task state
    self.update_state(
        state='STARTED',
        meta={
            'model': model,
            'vacuum_full': vacuum_full,
            'status': 'Cleaning up search vectors...'
        }
    )
    
    start_time = time.time()
    output = StringIO()
    
    try:
        call_command(
            'cleanup_search_vectors',
            model=model,
            batch_size=batch_size,
            no_vacuum=no_vacuum,
            vacuum_full=vacuum_full,
            force=True,
            stdout=output
        )
        
        elapsed = time.time() - start_time
        output_text = output.getvalue()
        
        result = {
            'status': 'success',
            'model': model,
            'duration_seconds': round(elapsed, 2),
            'output': output_text,
            'message': f'Cleanup completed successfully in {elapsed:.1f} seconds'
        }
        
        logger.info(f"Completed cleanup_search_vectors for {model} in {elapsed:.1f}s")
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Cleanup failed for {model}: {error_msg}")
        
        return {
            'status': 'error',
            'model': model,
            'duration_seconds': round(elapsed, 2),
            'error': error_msg,
            'message': f'Cleanup failed: {error_msg}'
        }
    finally:
        output.close()


@shared_task(bind=True, name="search.manage_postgres_search")
def manage_postgres_search_task(self, action: str, model: str = 'both'):
    """
    Manage PostgreSQL search infrastructure (triggers, indexes, etc.).
    
    Args:
        action: Action to perform (e.g., 'disable-trigger', 'enable-trigger', 
                'drop-index', 'create-index', 'disable-all', 'enable-all')
        model: Which model to operate on ('extraction', 'page', or 'both')
    
    Returns:
        dict with status, duration, and output
    """
    logger.info(f"Starting manage_postgres_search task: action={action}, model={model}")
    
    # Update task state
    self.update_state(
        state='STARTED',
        meta={
            'action': action,
            'model': model,
            'status': f'Running {action}...'
        }
    )
    
    start_time = time.time()
    output = StringIO()
    
    try:
        # Convert action to command-line argument
        action_arg = f'--{action}'
        
        call_command(
            'manage_postgres_search',
            action_arg,
            model=model,
            force=True,
            stdout=output
        )
        
        elapsed = time.time() - start_time
        output_text = output.getvalue()
        
        result = {
            'status': 'success',
            'action': action,
            'model': model,
            'duration_seconds': round(elapsed, 2),
            'output': output_text,
            'message': f'{action} completed successfully in {elapsed:.1f} seconds'
        }
        
        logger.info(f"Completed {action} for {model} in {elapsed:.1f}s")
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = str(e)
        logger.error(f"{action} failed for {model}: {error_msg}")
        
        return {
            'status': 'error',
            'action': action,
            'model': model,
            'duration_seconds': round(elapsed, 2),
            'error': error_msg,
            'message': f'{action} failed: {error_msg}'
        }
    finally:
        output.close()
