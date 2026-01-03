from celery import shared_task
from typing import List
from loguru import logger
from core.services.entity_extraction_service import EntityExtractionService
from core.models.entities import AFMEntity
from core.models.afm_fetch_jobs import AFMFetchJob
from core.services.gemi_service import GemiService
from gemi.exceptions import GemiNotFoundError

@shared_task(bind=True, max_retries=3)
def fetch_company_data_for_entities(self, afm_list: List[str], parent_task_id: str = None, parent_ada: str = None):
    """
    Celery task to fetch company data for a list of AFMs.
    
    Uses AFMFetchJob table to prevent duplicate tasks across batches.
    Only queues tasks for AFMs not already being fetched.

    Args:
        afm_list: List of AFM numbers to fetch company data for
        parent_task_id: Optional parent task ID for tracing
        parent_ada: Optional parent decision ADA for context
    """
    task_id = self.request.id if hasattr(self, 'request') else 'sync'
    
    # Filter out AFMs that are already being fetched
    afms_to_fetch = []
    afms_skipped = []
    
    for afm in afm_list:
        if AFMFetchJob.is_afm_being_fetched(afm):
            afms_skipped.append(afm)
        else:
            afms_to_fetch.append(afm)
    
    with logger.contextualize(
        task_id=task_id,
        task_name="fetch_company_data_for_entities",
        parent_task_id=parent_task_id,
        parent_ada=parent_ada,
        afm_total=len(afm_list),
        afm_to_fetch=len(afms_to_fetch),
        afm_skipped=len(afms_skipped)
    ):
        try:
            logger.info(
                f"AFM deduplication - Total: {len(afm_list)}, "
                f"Will fetch: {len(afms_to_fetch)}, "
                f"Skipped (in-flight): {len(afms_skipped)}"
            )
            
            if not afms_to_fetch:
                logger.info("All AFMs already being fetched - skipping")
                return {
                    "status": "all_in_flight",
                    "total": len(afm_list),
                    "skipped": len(afms_skipped)
                }
            
            # Create job records for AFMs we'll fetch
            for afm in afms_to_fetch:
                AFMFetchJob.objects.create(
                    afm=afm,
                    task_id=task_id,
                    parent_task_id=parent_task_id,
                    parent_ada=parent_ada,
                    status=AFMFetchJob.Status.PENDING
                )
            
            # Mark as in progress
            AFMFetchJob.mark_in_progress(None, task_id)  # Mark all for this task
            AFMFetchJob.objects.filter(task_id=task_id).update(
                status=AFMFetchJob.Status.IN_PROGRESS
            )
            
            # Get entities
            entities = AFMEntity.objects.filter(afm__in=afms_to_fetch)
            
            if not entities.exists():
                # Mark as failed
                for afm in afms_to_fetch:
                    AFMFetchJob.mark_completed(afm, task_id, False, "Entity not found")
                
                logger.warning(f"No entities found for AFMs: {afms_to_fetch}")
                return {"status": "no_entities_found", "afms": afms_to_fetch}

            # Fetch company data
            service = EntityExtractionService()
            stats = service.fetch_company_data_for_entities(
                list(entities), max_requests_per_minute=6
            )
            
            # Mark all as completed successfully
            for afm in afms_to_fetch:
                AFMFetchJob.mark_completed(afm, task_id, True)

            logger.info(f"Company data fetch completed", stats=stats)
            stats['deduplication'] = {
                'total_requested': len(afm_list),
                'actually_fetched': len(afms_to_fetch),
                'skipped_in_flight': len(afms_skipped)
            }
            return stats

        except Exception as e:
            # Mark all as failed
            for afm in afms_to_fetch:
                AFMFetchJob.mark_completed(afm, task_id, False, str(e))
            
            logger.error(f"Error in company data fetch task", error=str(e), error_type=type(e).__name__)
            raise self.retry(countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=3)
def fetch_company_data_for_single_afm(self, afm: str):
    """
    Celery task to fetch company data for a single AFM.
    
    Uses AFMFetchJob table to prevent duplicate tasks for the same AFM.
    If AFM is already being fetched, this task exits immediately.

    Args:
        afm: AFM number to fetch company data for
    """
    task_id = self.request.id if hasattr(self, 'request') else 'sync'
    
    try:
        # Check if this AFM is already being fetched
        if AFMFetchJob.is_afm_being_fetched(afm):
            logger.info(f"Task {task_id}: AFM {afm} already being fetched by another task - skipping")
            return {"status": "already_in_flight", "afm": afm}
        
        # Create job record
        AFMFetchJob.objects.create(
            afm=afm,
            task_id=task_id,
            status=AFMFetchJob.Status.PENDING
        )
        
        logger.info(f"Task {task_id}: Processing AFM: {afm}")
        
        # Mark as in progress
        AFMFetchJob.mark_in_progress(afm, task_id)
        
        # Try to get the entity
        try:
            entity = AFMEntity.objects.get(afm=afm)        
        except AFMEntity.DoesNotExist:
            AFMFetchJob.mark_completed(afm, task_id, False, "Entity not found")
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
            
            # Mark as successful
            AFMFetchJob.mark_completed(afm, task_id, True)
            
        except GemiNotFoundError:
            logger.info(f"Task {task_id}: No company data found for AFM {afm}")
            # Still mark as successful (not an error, just no data)
            AFMFetchJob.mark_completed(afm, task_id, True)
            return {"status": "no_company_found", "afm": afm}

        result = {"status": "success", "afm": afm, "companies_found": len(companies)}
        logger.info(f"Task {task_id}: Company data fetch completed for {afm}: {result}")
        return result

    except Exception as e:
        # Mark as failed
        AFMFetchJob.mark_completed(afm, task_id, False, str(e))
        
        logger.error(f"Task {task_id}: Error in company data fetch task for {afm}: {e}")
        raise self.retry(countdown=60 * (self.request.retries + 1))


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
