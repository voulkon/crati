from celery import shared_task
from core.models.document_analysis import DocumentExtraction, ProcessingStatus
from loguru import logger
from core.services.opensearch_service import OpenSearchService

@shared_task
def create_opensearch_backup(repository_name="s3-backup-repo", snapshot_name=None):
    """
    Celery task to create OpenSearch backup
    """
    try:
        opensearch_service = OpenSearchService()
        
        # Ensure repository is registered
        opensearch_service.register_s3_repository(repository_name)
        
        # Create snapshot
        result = opensearch_service.create_snapshot(repository_name, snapshot_name)
        
        if result["success"]:
            logger.info(f"📦 Backup completed: {result['snapshot']}")
            return {"status": "success", "snapshot": result["snapshot"]}
        else:
            logger.error(f"❌ Backup failed: {result['error']}")
            return {"status": "failed", "error": result["error"]}
            
    except Exception as e:
        logger.error(f"❌ Backup task failed: {e}")
        raise

@shared_task
def daily_opensearch_backup():
    """
    Daily automated backup task
    """
    from datetime import datetime
    
    snapshot_name = f"daily-backup-{datetime.now().strftime('%Y%m%d')}"
    return create_opensearch_backup.delay(snapshot_name=snapshot_name)


@shared_task
def check_opensearch_sync():
    """
    Monitoring task to check OpenSearch sync status
    """
    try:
        # Count completed extractions in PostgreSQL
        pg_count = DocumentExtraction.objects.filter(
            extraction_status=ProcessingStatus.COMPLETED,
            raw_text__isnull=False
        ).exclude(raw_text='').count()
        
        # Count documents in OpenSearch
        opensearch_service = OpenSearchService()
        os_results = opensearch_service._test_match_all()
        os_count = os_results.get('hits', {}).get('total', {}).get('value', 0)
        
        diff = pg_count - os_count
        
        logger.info(f"📊 Sync status: PostgreSQL={pg_count}, OpenSearch={os_count}, Diff={diff}")
        
        # If significant difference, trigger sync
        if diff > 10:
            logger.warning(f"⚠️ Large sync difference detected ({diff}), triggering batch indexing")
            index_recent_documents.delay(limit=diff + 50)
        
        return {
            "postgresql_count": pg_count,
            "opensearch_count": os_count,
            "difference": diff,
            "sync_triggered": diff > 10
        }
        
    except Exception as e:
        logger.error(f"❌ Sync check failed: {e}")
        raise

@shared_task
def index_recent_documents(limit=100):
    """
    Task to index recently processed documents to OpenSearch
    """
    logger.info(f"🔍 Starting batch indexing of {limit} recent documents")
    
    try:
        opensearch_service = OpenSearchService()
        initial_count = opensearch_service._test_match_all().get('hits', {}).get('total', {}).get('value', 0)
        
        # Get recently completed extractions
        recent_extractions = DocumentExtraction.objects.filter(
            extraction_status=ProcessingStatus.COMPLETED,
            raw_text__isnull=False
        ).exclude(raw_text='').select_related(
            'decision', 'decision__organization', 'decision__decision_type'
        ).order_by('-extraction_date')[:limit]
        
        indexed_count = 0
        
        for extraction in recent_extractions:
            try:
                document_data = {
                    'decision_id': extraction.decision.id,
                    'ada': extraction.decision.ada,
                    'title': extraction.decision.subject or '',
                    'content': extraction.raw_text,
                    'organization': str(extraction.decision.organization) if extraction.decision.organization else '',
                    'decision_type': str(extraction.decision.decision_type) if extraction.decision.decision_type else '',
                    'issue_date': extraction.decision.issue_date.isoformat() if extraction.decision.issue_date else None,
                    'extraction_date': extraction.extraction_date.isoformat() if extraction.extraction_date else None,
                    'character_count': extraction.character_count,
                    'page_count': extraction.page_count
                }
                
                success = opensearch_service.index_document(document_data)
                if success:
                    indexed_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error indexing {extraction.decision.ada}: {e}")
        
        final_count = opensearch_service._test_match_all().get('hits', {}).get('total', {}).get('value', 0)
        
        logger.info(f"✅ Batch indexing completed: {indexed_count} processed, OpenSearch: {initial_count} → {final_count}")
        
        return {
            "processed": indexed_count,
            "initial_opensearch_count": initial_count,
            "final_opensearch_count": final_count
        }
        
    except Exception as e:
        logger.error(f"❌ Batch indexing failed: {e}")
        raise


