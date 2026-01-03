from celery import shared_task
from typing import List
from loguru import logger
from django_redis import get_redis_connection
from core.services.entity_extraction_service import EntityExtractionService
from core.models.entities import AFMEntity
from core.services.gemi_service import GemiService
from gemi.exceptions import GemiNotFoundError
from api.redis_keys import AFM_FETCH_LOCK_PREFIX, AFM_FETCH_LOCK_TIMEOUT


@shared_task(bind=True, max_retries=3)
def fetch_company_data_for_entities(self, afm_list: List[str], parent_task_id: str = None, parent_ada: str = None):
    """
    Celery task to fetch company data for a list of AFMs.
    
    This task receives only AFMs that were checked to be unlocked by the orchestrator.
    It acquires locks, processes the AFMs, and releases locks when done.

    Args:
        afm_list: List of AFM numbers to fetch (already filtered by orchestrator)
        parent_task_id: Optional parent task ID for tracing
        parent_ada: Optional parent decision ADA for context
    """
    task_id = self.request.id if hasattr(self, 'request') else 'sync'
    redis_client = get_redis_connection("default")
    
    # Deduplicate input (safety check, orchestrator should have done this)
    unique_afms = list(set(afm_list))
    
    # Acquire locks for all AFMs we're about to process
    for afm in unique_afms:
        key = f"{AFM_FETCH_LOCK_PREFIX}{afm}"
        redis_client.set(key, task_id, nx=True, ex=AFM_FETCH_LOCK_TIMEOUT)
    
    with logger.contextualize(
        task_id=task_id,
        task_name="fetch_company_data_for_entities",
        parent_task_id=parent_task_id,
        parent_ada=parent_ada,
        afm_count=len(unique_afms)
    ):
        try:
            if len(unique_afms) != len(afm_list):
                logger.warning(
                    f"Input deduplication: {len(afm_list)} → {len(unique_afms)} unique AFMs"
                )
            
            logger.info(f"Starting company data fetch for {len(unique_afms)} AFMs")
            
            # Get entities
            entities = AFMEntity.objects.filter(afm__in=unique_afms)
            
            if not entities.exists():
                logger.warning(f"No entities found for AFMs: {unique_afms}")
                return {"status": "no_entities_found", "afms": unique_afms}

            # Fetch company data
            service = EntityExtractionService()
            stats = service.fetch_company_data_for_entities(
                list(entities), max_requests_per_minute=6
            )

            logger.info(f"Company data fetch completed", stats=stats)
            return stats

        except Exception as e:
            logger.error(f"Error in company data fetch task", error=str(e), error_type=type(e).__name__)
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        finally:
            # Always release locks
            for afm in unique_afms:
                key = f"{AFM_FETCH_LOCK_PREFIX}{afm}"
                redis_client.delete(key)
            
            logger.debug(f"Released locks for {len(unique_afms)} AFMs")


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
