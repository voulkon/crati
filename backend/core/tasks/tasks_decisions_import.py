from celery import shared_task
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from loguru import logger
import pickle
import os
from core.fetchers.diavgeia_fetcher import DiavgeiaFetcher
from core.importers.decisions import DecisionImporter


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
        
        # Create pickle directory
        pickle_dir = "/code/logs/pickles"
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
        
        # Now split the storage work into smaller chunks
        chunk_size = 50  # Process 50 decisions per storage task
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
            
            # Dispatch storage task for this chunk
            storage_task = store_decisions_from_pickle.delay(chunk_pickle, batch_size=25)
            storage_tasks.append(storage_task.id)
            logger.info(f"Dispatched storage task {storage_task.id} for chunk {chunk_id}")
        
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
def store_decisions_from_pickle(self, pickle_file: str, batch_size: int = 25):
    """
    Phase 2: Load decisions from pickle and store to database
    
    Args:
        pickle_file: Path to pickle file with decisions
        batch_size: Number of decisions to process per batch
        
    Returns:
        Dict with storage results
    """
    try:
        logger.info(f"Task {self.request.id}: Loading decisions from {pickle_file}")
        
        # Load decisions from pickle
        if not os.path.exists(pickle_file):
            raise FileNotFoundError(f"Pickle file not found: {pickle_file}")
        
        with open(pickle_file, 'rb') as f:
            pickle_data = pickle.load(f)
        
        decisions = pickle_data['decisions']
        logger.info(f"Task {self.request.id}: Loaded {len(decisions)} decisions from pickle")
        
        # Create importer and store decisions
        decision_importer = DecisionImporter()
        created_count = decision_importer.import_decisions_in_batches(decisions, batch_size)
        
        # Check if we actually created any decisions
        if len(decisions) > 0 and created_count == 0:
            logger.warning(f"Task {self.request.id}: No decisions were created from {len(decisions)} decisions in pickle file")
            # This might not be an error if all decisions already exist, but let's log it prominently
        
        # Move pickle to completed folder
        completed_dir = "/code/logs/pickles/completed"
        os.makedirs(completed_dir, exist_ok=True)
        completed_file = os.path.join(completed_dir, os.path.basename(pickle_file))
        os.rename(pickle_file, completed_file)
        
        # Log with appropriate level based on results
        if created_count > 0:
            logger.success(f"Task {self.request.id}: Stored {created_count} decisions, moved pickle to {completed_file}")
        else:
            logger.info(f"Task {self.request.id}: No new decisions created (possibly duplicates), moved pickle to {completed_file}")
        
        return {
            'status': 'success',
            'pickle_file': pickle_file,
            'completed_file': completed_file,
            'decisions_loaded': len(decisions),
            'decisions_created': created_count,
            'task_id': self.request.id,
            'note': 'No new decisions created' if created_count == 0 and len(decisions) > 0 else None
        }
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Storage failed: {str(e)}")
        
        # For storage failures, create a retry pickle with smaller batch size
        if self.request.retries < self.max_retries:
            # Reduce batch size on retry
            new_batch_size = max(5, batch_size // 2)
            logger.info(f"Task {self.request.id}: Retrying with smaller batch size: {new_batch_size}")
            
            raise self.retry(
                countdown=30 * (2 ** self.request.retries),  # 30s, 60s, 120s, 240s, 480s
                kwargs={'pickle_file': pickle_file, 'batch_size': new_batch_size},
                exc=e
            )
        else:
            # Max retries reached, move to failed folder for manual intervention
            failed_dir = "/code/logs/pickles/failed"
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