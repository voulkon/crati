from celery import shared_task
from typing import List
from loguru import logger
from django.conf import settings
from django_redis import get_redis_connection
from core.services.entity_extraction_service import EntityExtractionService
from core.models.entities import AFMEntity
from core.services.gemi_service import GemiService
from gemi.exceptions import GemiNotFoundError
from api.redis_keys import AFM_FETCH_LOCK_PREFIX, AFM_FETCH_LOCK_TIMEOUT


@shared_task(bind=True, max_retries=3)
def fetch_company_data_for_entities(self, afm_list: List[str], parent_task_id: str = None, parent_ada: str = None, lock_owner: str = None):
    """
    Celery task to fetch company data for a list of AFMs.
    
    The orchestrator has already acquired locks for these AFMs before queuing this task.
    This task processes the AFMs and releases the locks when done.

    Args:
        afm_list: List of AFM numbers to fetch (already locked by orchestrator)
        parent_task_id: Optional parent task ID for tracing
        parent_ada: Optional parent decision ADA for context
        lock_owner: Lock owner ID used by orchestrator (for verification)
    """
    task_id = self.request.id if hasattr(self, 'request') else 'sync'
    redis_client = get_redis_connection("default")
    
    # Deduplicate input (safety check, orchestrator should have done this)
    unique_afms = list(set(afm_list))
    
    with logger.contextualize(
        task_id=task_id,
        task_name="fetch_company_data_for_entities",
        parent_task_id=parent_task_id,
        parent_ada=parent_ada,
        afm_count=len(unique_afms),
        lock_owner=lock_owner
    ):
        try:
            if len(unique_afms) != len(afm_list):
                logger.warning(
                    f"Input deduplication: {len(afm_list)} → {len(unique_afms)} unique AFMs"
                )
            
            # Extend/refresh locks (they may have expired while task was queued)
            if lock_owner:
                locks_extended = 0
                locks_missing = []
                
                for afm in unique_afms:
                    key = f"{AFM_FETCH_LOCK_PREFIX}{afm}"
                    current_owner = redis_client.get(key)
                    
                    # Check if lock expired or owned by someone else
                    if current_owner is None:
                        # Lock expired while in queue - re-acquire it with our owner
                        logger.warning(f"Lock for AFM {afm} expired, re-acquiring")
                        redis_client.set(key, lock_owner, ex=AFM_FETCH_LOCK_TIMEOUT)
                        locks_extended += 1
                    elif (current_owner.decode('utf-8') if isinstance(current_owner, bytes) else current_owner) == lock_owner:
                        # We own it, extend the TTL
                        redis_client.expire(key, AFM_FETCH_LOCK_TIMEOUT)
                        locks_extended += 1
                    else:
                        # Someone else owns it - should not happen!
                        locks_missing.append(afm)
                
                if locks_missing:
                    logger.error(
                        f"Lock verification failed! {len(locks_missing)} AFMs locked by others: {locks_missing}"
                    )
                    return {"status": "lock_verification_failed", "missing_locks": locks_missing}
                
                logger.info(f"Extended/verified {locks_extended}/{len(unique_afms)} locks")
            
            logger.info(f"Starting company data fetch for {len(unique_afms)} AFMs")
            
            # Get entities
            entities = AFMEntity.objects.filter(afm__in=unique_afms)
            
            if not entities.exists():
                logger.warning(f"No entities found for AFMs: {unique_afms}")
                return {"status": "no_entities_found", "afms": unique_afms}

            # Fetch company data
            service = EntityExtractionService()
            stats = service.fetch_company_data_for_entities(
                list(entities), 
                max_requests_per_minute=6,
                retry_failed_after_days=getattr(settings, "RETRY_AFM_FETCHES_AFTER_NUMBER_OF_DAYS", 60)
            )

            logger.info(f"Company data fetch completed", stats=stats)
            return stats

        except Exception as e:
            logger.error(f"Error in company data fetch task", error=str(e), error_type=type(e).__name__)
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        finally:
            # Release locks only if we own them (defensive delete)
            released = 0
            for afm in unique_afms:
                key = f"{AFM_FETCH_LOCK_PREFIX}{afm}"
                if lock_owner:
                    # Only delete if we own the lock
                    current_owner = redis_client.get(key)
                    if current_owner and (current_owner == lock_owner.encode('utf-8') if isinstance(current_owner, bytes) else current_owner == lock_owner):
                        redis_client.delete(key)
                        released += 1
                else:
                    # Fallback: delete unconditionally (for backward compatibility)
                    redis_client.delete(key)
                    released += 1
            
            logger.debug(f"Released {released}/{len(unique_afms)} locks")


@shared_task(bind=True, max_retries=3)
def fetch_company_data_for_single_afm(self, afm: str):
    """
    Celery task to fetch company data for a single AFM.
    
    Uses Redis distributed lock to prevent concurrent fetches of the same AFM.

    Args:
        afm: AFM number to fetch company data for
    """
    task_id = self.request.id if hasattr(self, 'request') else 'sync'
    redis_client = get_redis_connection("default")
    
    # Try to acquire lock (atomic: SET with NX + EX)
    key = f"{AFM_FETCH_LOCK_PREFIX}{afm}"
    if not redis_client.set(key, task_id, nx=True, ex=AFM_FETCH_LOCK_TIMEOUT):
        logger.info(f"Task {task_id}: AFM {afm} already being fetched - skipping")
        return {"status": "already_in_flight", "afm": afm}
    
    try:
        logger.info(f"Task {task_id}: Processing AFM: {afm}")
        
        # Try to get the entity
        try:
            entity = AFMEntity.objects.get(afm=afm)        
        except AFMEntity.DoesNotExist:
            logger.warning(f"Task {task_id}: AFMEntity {afm} not found in database")
            return {"status": "entity_not_found", "afm": afm}

        # Fetch from GEMI (it checks DB internally)
        try: 
            logger.info(f"Task {task_id}: Calling GemiService for {afm}")
            companies = GemiService.fetch_companies_by_afm(
                afm,
                update_entity=True,
                max_requests_per_minute=6,
            )
            logger.info(f"Task {task_id}: GemiService returned {len(companies)} companies for {afm}")
            
        except GemiNotFoundError:
            logger.info(f"Task {task_id}: No company data found for AFM {afm}")
            return {"status": "no_company_found", "afm": afm}

        result = {"status": "success", "afm": afm, "companies_found": len(companies)}
        logger.info(f"Task {task_id}: Company data fetch completed for {afm}: {result}")
        return result

    except Exception as e:
        logger.error(f"Task {task_id}: Error in company data fetch task for {afm}: {e}")
        raise self.retry(countdown=60 * (self.request.retries + 1))
    finally:
        # Always release lock
        key = f"{AFM_FETCH_LOCK_PREFIX}{afm}"
        redis_client.delete(key)


@shared_task
def process_entities_needing_company_data(limit: int = 50):
    """
    Celery task to process entities that need company data fetching.
    This can be run periodically to catch up on entities.
    """
    try:
        service = EntityExtractionService()

        # Get entities that need processing
        entities = service.get_entities_needing_company_data(limit=limit)

        if not entities:
            logger.info("No entities need company data fetching")
            return {"status": "no_entities_to_process"}

        # Fetch company data
        stats = service.fetch_company_data_for_entities(entities)

        logger.info(f"Periodic company data fetch completed: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Error in periodic company data fetch: {e}")
        raise


@shared_task(bind=True, max_retries=3)
def process_afm_fetch_queue(self, max_items: int = None):
    """
    Celery task to process the AFM fetch queue.
    
    Processes all pending items in the priority queue, respecting GEMI rate limits.
    Rate limiting is handled by the service itself (6 req/min).
    
    Args:
        max_items: Optional limit on items to process (None = process entire queue)
        
    Returns:
        Processing statistics
    """
    from core.services.afm_fetch_queue_service import AFMFetchQueueService
    
    task_id = self.request.id if hasattr(self, 'request') else 'sync'
    
    with logger.contextualize(
        task_id=task_id,
        task_name="process_afm_fetch_queue",
        max_items=max_items
    ):
        try:
            queue_service = AFMFetchQueueService()
            
            # Get pending count
            pending_count = queue_service.get_pending_count()
            
            if pending_count == 0:
                logger.info("Queue is empty, nothing to process")
                return {'status': 'empty_queue', 'pending': 0}
            
            # Determine batch size (process all or limited)
            items_to_process = min(pending_count, max_items) if max_items else pending_count
            
            logger.info(
                f"Starting queue processing: {items_to_process} items from {pending_count} pending"
            )
            
            # Process batch (rate limiting is handled by GemiService)
            stats = queue_service.process_batch(batch_size=items_to_process)
            
            logger.info(f"Queue processing completed", extra=stats)
            return stats
            
        except Exception as e:
            logger.error(f"Error in queue processing task: {e}")
            raise self.retry(countdown=300)  # Retry after 5 minutes
