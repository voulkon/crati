from loguru import logger
from celery import shared_task
from core.services.opensearch_service import OpenSearchService
from core.models.document_analysis import DocumentExtraction, ProcessingStatus

def log_task_start(task_name, **kwargs):
    logger.info(f"Starting {task_name} with args: {kwargs}")

