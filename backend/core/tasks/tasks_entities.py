from celery import shared_task
from typing import List
from loguru import logger
from core.services.entity_extraction_service import EntityExtractionService
from core.models.entities import AFMEntity
from core.services.gemi_service import GemiService
from gemi.exceptions import GemiNotFoundError

@shared_task(bind=True, max_retries=3)
def fetch_company_data_for_entities(self, afm_list: List[str], parent_task_id: str = None, parent_ada: str = None):
    """
    Celery task to fetch company data for a list of AFMs.

    Args:
        afm_list: List of AFM numbers to fetch company data for
        parent_task_id: Optional parent task ID for tracing
        parent_ada: Optional parent decision ADA for context
    """
    # Get this task's ID
    task_id = self.request.id if hasattr(self, 'request') else 'sync'
    
    # Use contextualize to propagate context to all logs in this task
    with logger.contextualize(
        task_id=task_id,
        task_name="fetch_company_data_for_entities",
        parent_task_id=parent_task_id,
        parent_ada=parent_ada,
        afm_count=len(afm_list)
    ):
        try:
            logger.info(f"Starting company data fetch for {len(afm_list)} AFMs")
            
            # Get the actual entities
            entities = AFMEntity.objects.filter(afm__in=afm_list)

            if not entities.exists():
                logger.warning(f"No entities found for AFMs: {afm_list}")
                return {"status": "no_entities_found", "afms": afm_list}

            # Use the extraction service to fetch company data
            service = EntityExtractionService()
            stats = service.fetch_company_data_for_entities(
                list(entities), max_requests_per_minute=6  # Respect API limits
            )

            logger.info(f"Company data fetch task completed", stats=stats)
            return stats

        except Exception as e:
            logger.error(f"Error in company data fetch task", error=str(e), error_type=type(e).__name__)
            # Retry the task
            raise self.retry(countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=3, rate_limit="6/m")
def fetch_company_data_for_single_afm(self, afm: str):
    """
    Celery task to fetch company data for a single AFM.
    Rate limited to 6 per minute to respect API limits.

    Args:
        afm: AFM number to fetch company data for
    """
    try:
        logger.info(f"Processing AFM: {afm}")

        # Try to get the entity
        try:
            entity = AFMEntity.objects.get(afm=afm)        
        except AFMEntity.DoesNotExist:
            logger.warning(f"AFMEntity {afm} not found in database")
            return {"status": "entity_not_found", "afm": afm}

        # Use GemiService directly - rate limit matches Celery's rate_limit decorator
        try: 
            companies = GemiService.fetch_companies_by_afm(
                afm,
                update_entity=True,
                max_requests_per_minute=6,  # Matches task rate_limit="6/m"
            )
        except GemiNotFoundError:
            logger.info(f"No company data found for AFM {afm}")
            return {"status": "no_company_found", "afm": afm}

        result = {"status": "success", "afm": afm, "companies_found": len(companies)}

        logger.info(f"Company data fetch completed for {afm}: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in company data fetch task for {afm}: {e}")
        # Retry the task
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
