from celery import shared_task
from core.models.document_analysis import DocumentExtraction, ProcessingStatus
from loguru import logger
from core.models.import_jobs import DateCoverage
from core.services.opensearch_service import OpenSearchService
from .tasks_opensearch import index_recent_documents

@shared_task(bind=True, max_retries=3)
def process_document_task(self, ada, provider=None):
    """
    Celery task to process a document
    """
    from core.models.decisions import Decision
    from core.services.document_processor import DocumentAnalysisService

    try:
        # TODO: Fix the
        # ERROR: 
        #   Traceback (most recent call last):
        #   File "/code/core/tasks.py", line 186, in process_document_task
        #     decision = Decision.objects.get(ada=ada)
        #   File "/usr/local/lib/python3.13/site-packages/django/db/models/manager.py", line 87, in manager_method
        #     return getattr(self.get_queryset(), name)(*args, **kwargs)
        #            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
        #   File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 633, in get
        #     raise self.model.DoesNotExist(
        #         "%s matching query does not exist." % self.model._meta.object_name
        #     )
        # core.models.decisions.Decision.DoesNotExist: Decision matching query does not exist.

        # During handling of the above exception, another exception occurred:

        # Traceback (most recent call last):
        #   File "/usr/local/lib/python3.13/site-packages/celery/app/trace.py", line 453, in trace_task
        #     R = retval = fun(*args, **kwargs)
        #                  ~~~^^^^^^^^^^^^^^^^^
        #   File "/usr/local/lib/python3.13/site-packages/celery/app/trace.py", line 736, in __protected_call__
        #     return self.run(*args, **kwargs)
        #            ~~~~~~~~^^^^^^^^^^^^^^^^^
        #   File "/code/core/tasks.py", line 200, in process_document_task
        #     raise self.retry(exc=e, countdown=60, max_retries=3)
        #           ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        #   File "/usr/local/lib/python3.13/site-packages/celery/app/task.py", line 764, in retry
        #     raise ret
        # celery.exceptions.Retry: Retry in 60s: DoesNotExist('Decision matching query does not exist.')

        # Get the decision
        decision = Decision.objects.get(ada=ada)

        # Process the document with the specified provider
        service = DocumentAnalysisService()
        result = service.process_decision(decision, provider=provider)

        return {"success": True, "ada": ada, "result": result}
    except Exception as e:
        # Log the error
        from loguru import logger

        logger.error(f"Failed to process document {ada}: {str(e)}")

        # Retry a few times
        raise self.retry(exc=e, countdown=60, max_retries=3)

@shared_task
def process_scanned_document_task(decision_ada, provider="GOOGLE_VISION"):
    """Process a scanned document with OCR"""
    # Implementation here
    pass

@shared_task
def collect_batch_results(results):
    """Collect and process the results of the batch processing"""
    success_count = sum(1 for r in results if r.get("success", False))
    return {
        "processed": len(results),
        "successful": success_count,
        "failed": len(results) - success_count,
    }

@shared_task
def process_document_batch(ada_list, max_concurrency=10):
    """Process a batch of documents with controlled concurrency"""
    from celery import chord

    # Create a chord that will execute the callback when all tasks complete
    header = [process_document_task.s(ada) for ada in ada_list]
    callback = collect_batch_results.s()
    result = chord(header)(callback)

    return {"task_id": result.id, "processed": len(ada_list)}

@shared_task(bind=True, max_retries=3)
def process_document_task_enhanced(self, ada, provider=None):
    """
    Enhanced Celery task to process a document with OpenSearch indexing
    """
    from core.models.decisions import Decision
    from core.services.document_processor import DocumentAnalysisService

    try:
        logger.info(f"🔄 Starting document processing task for {ada}")
        
        # Get the decision
        decision = Decision.objects.get(ada=ada)

        # Process the document with the specified provider
        service = DocumentAnalysisService()
        result = service.process_decision(decision, provider=provider)

        if result.get('success') and result.get('extraction_status') == 'COMPLETED':
            logger.info(f"✅ Document processing completed for {ada}")
            
            # Force OpenSearch indexing if the signal didn't work
            try:
                extraction = DocumentExtraction.objects.get(
                    decision=decision,
                    extraction_status=ProcessingStatus.COMPLETED
                )
                
                if extraction.raw_text:
                    opensearch_service = OpenSearchService()
                    
                    # Prepare document for indexing
                    document_data = {
                        'decision_id': decision.id,
                        'ada': decision.ada,
                        'title': decision.subject or '',
                        'content': extraction.raw_text,
                        'organization': str(decision.organization) if decision.organization else '',
                        'decision_type': str(decision.decision_type) if decision.decision_type else '',
                        'issue_date': decision.issue_date.isoformat() if decision.issue_date else None,
                        'extraction_date': extraction.extraction_date.isoformat() if extraction.extraction_date else None,
                        'character_count': extraction.character_count,
                        'page_count': extraction.page_count
                    }
                    
                    success = opensearch_service.index_document(document_data)
                    if success:
                        logger.info(f"🔍 Force-indexed document {ada} to OpenSearch")
                    else:
                        logger.warning(f"⚠️ Failed to force-index document {ada} to OpenSearch")
                        
            except DocumentExtraction.DoesNotExist:
                logger.warning(f"⚠️ No completed extraction found for {ada}")
            except Exception as e:
                logger.error(f"❌ Error force-indexing {ada}: {e}")

        return {"success": True, "ada": ada, "result": result}
        
    except Exception as e:
        # Log the error
        logger.error(f"❌ Failed to process document {ada}: {str(e)}")
        
        # Retry a few times
        raise self.retry(exc=e, countdown=60, max_retries=3)

@shared_task
def process_documents_task(ada_list=None, from_date=None, limit=50, user_id=None):
    from django.core.management import call_command
    
    logger.info(f"Processing documents: user_id={user_id}, limit={limit}")
    
    args = ['--unprocessed-only']  # Add this flag for the scheduled task
    
    if ada_list:
        for ada in ada_list:
            args.extend(['--ada', ada])
    if from_date:
        # Handle special 'yesterday' value from the scheduled task
        if from_date == 'yesterday':
            from datetime import date, timedelta
            yesterday = date.today() - timedelta(days=1)
            args.extend(['--from-date', yesterday.isoformat()])
        else:
            args.extend(['--from-date', from_date])
    if limit:
        args.extend(['--limit', str(limit)])
    
    try:
        call_command('process_documents', *args)
        return {"status": "completed", "documents_processed": limit}
    except Exception as e:
        logger.error(f"Error processing documents: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def process_documents_task_enhanced(ada_list=None, from_date=None, limit=50, user_id=None, index_to_opensearch=True):
    """
    Enhanced task with OpenSearch indexing option
    """
    from django.core.management import call_command
    
    logger.info(f"Processing documents: user_id={user_id}, limit={limit}, opensearch={index_to_opensearch}")
    
    args = ['--unprocessed-only']  # Add this flag for the scheduled task
    
    if ada_list:
        for ada in ada_list:
            args.extend(['--ada', ada])
    if from_date:
        # Handle special 'yesterday' value from the scheduled task
        if from_date == 'yesterday':
            from datetime import date, timedelta
            yesterday = date.today() - timedelta(days=1)
            args.extend(['--from-date', yesterday.isoformat()])
        else:
            args.extend(['--from-date', from_date])
    if limit:
        args.extend(['--limit', str(limit)])
    
    try:
        call_command('process_documents', *args)
        
        # If indexing is requested, trigger batch indexing
        if index_to_opensearch:
            index_recent_documents.delay(limit=limit)
        
        return {"status": "completed", "documents_processed": limit}
    except Exception as e:
        logger.error(f"Error processing documents: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task
def generate_summary_task(decision_ada, provider="OPENAI"):
    """Generate summary for a document"""
    # Implementation here
    pass