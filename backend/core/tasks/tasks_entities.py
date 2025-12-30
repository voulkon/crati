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
    
    This task is idempotent and race-condition safe - it re-checks which AFMs
    actually need fetching at execution time, so duplicate tasks are harmless.

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

            # RACE CONDITION PROTECTION: Re-check which AFMs actually need fetching
            # This handles cases where:
            # 1. Another task is running concurrently
            # 2. Data was fetched between task queuing and execution
            entities_needing_fetch = []
            entities_already_fetched = []
            
            for entity in entities:
                if entity.gemi_lookup_attempted and entity.gemi_lookup_success:
                    entities_already_fetched.append(entity.afm)
                    logger.info(
                        f"AFM {entity.afm} already has company data (skipping)",
                        companies_count=entity.gemi_companies_count,
                        last_fetch=entity.gemi_lookup_attempted.isoformat()
                    )
                else:
                    entities_needing_fetch.append(entity)
            
            # If all AFMs already have data, exit early
            if not entities_needing_fetch:
                logger.info(
                    f"All AFMs already have company data, task exiting early",
                    total_afms=len(afm_list),
                    already_fetched=len(entities_already_fetched)
                )
                return {
                    "status": "all_already_fetched",
                    "total_afms": len(afm_list),
                    "already_fetched": len(entities_already_fetched),
                    "newly_fetched": 0
                }

            logger.info(
                f"Fetching company data",
                afms_to_fetch=len(entities_needing_fetch),
                afms_skipped=len(entities_already_fetched)
            )

            # Use the extraction service to fetch company data
            service = EntityExtractionService()
            stats = service.fetch_company_data_for_entities(
                entities_needing_fetch, max_requests_per_minute=6  # Respect API limits
            )
            
            stats['already_fetched'] = len(entities_already_fetched)
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

        # Use GemiService directly - no rate limiting needed here since Celery handles it
        try: 
            companies = GemiService.fetch_companies_by_afm(
                afm,
                update_entity=True,
                max_requests_per_minute=60, 
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
