from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Q
from core.models.decisions import Decision
from core.models.document_analysis import DocumentExtraction, ProcessingStatus
from core.services.opensearch_service import OpenSearchService
from core.tasks.tasks_opensearch import index_recent_documents
from loguru import logger


@staff_member_required
def sync_status_dashboard(request):
    """Dashboard for monitoring and managing PostgreSQL <-> OpenSearch sync"""
    
    opensearch_service = OpenSearchService()
    
    # Handle actions
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "reindex_all":
            # Trigger bulk reindexing for all missing documents
            try:
                missing_count = _get_missing_count()
                task = index_recent_documents.delay(limit=missing_count + 100)
                messages.success(
                    request, 
                    f"Bulk reindexing initiated for ~{missing_count} documents. Task ID: {task.id}"
                )
                logger.info(f"Bulk reindexing triggered by user, task ID: {task.id}")
            except Exception as e:
                messages.error(request, f"Failed to trigger reindexing: {str(e)}")
                logger.error(f"Failed to trigger bulk reindexing: {e}")
        
        elif action == "reindex_selected":
            # Reindex specific decisions
            selected_adas = request.POST.getlist("selected_decisions")
            if selected_adas:
                try:
                    reindexed_count = 0
                    failed_count = 0
                    
                    for ada in selected_adas:
                        try:
                            extraction = DocumentExtraction.objects.select_related(
                                'decision', 
                                'decision__organization', 
                                'decision__decision_type'
                            ).get(
                                decision__ada=ada,
                                extraction_status=ProcessingStatus.COMPLETED
                            )
                            
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
                                reindexed_count += 1
                            else:
                                failed_count += 1
                        except Exception as e:
                            failed_count += 1
                            logger.error(f"Failed to reindex {ada}: {e}")
                    
                    messages.success(
                        request, 
                        f"Reindexed {reindexed_count} documents. {failed_count} failed."
                    )
                except Exception as e:
                    messages.error(request, f"Error during selective reindexing: {str(e)}")
            else:
                messages.warning(request, "No decisions selected for reindexing.")
        
        return redirect('admin:sync_status_dashboard')
    
    # Get counts and stats
    try:
        # PostgreSQL counts
        total_decisions = Decision.objects.count()
        completed_extractions = DocumentExtraction.objects.filter(
            extraction_status=ProcessingStatus.COMPLETED,
            raw_text__isnull=False
        ).exclude(raw_text='').count()
        
        # OpenSearch count
        os_results = opensearch_service._test_match_all()
        opensearch_count = os_results.get('hits', {}).get('total', {}).get('value', 0)
        
        # Calculate difference
        sync_diff = completed_extractions - opensearch_count
        sync_percentage = (opensearch_count / completed_extractions * 100) if completed_extractions > 0 else 0
        
        # Get sample of missing documents (paginated)
        page = int(request.GET.get('page', 1))
        page_size = 50
        offset = (page - 1) * page_size
        
        missing_decisions = _get_missing_decisions(opensearch_service, offset, page_size)
        
        # Calculate pagination
        total_missing = len(_get_all_missing_adas(opensearch_service))
        total_pages = (total_missing + page_size - 1) // page_size
        
        context = {
            'total_decisions': total_decisions,
            'completed_extractions': completed_extractions,
            'opensearch_count': opensearch_count,
            'sync_diff': sync_diff,
            'sync_percentage': round(sync_percentage, 2),
            'missing_decisions': missing_decisions,
            'page': page,
            'total_pages': total_pages,
            'total_missing': total_missing,
            'has_previous': page > 1,
            'has_next': page < total_pages,
            'previous_page': page - 1,
            'next_page': page + 1,
        }
        
    except Exception as e:
        logger.error(f"Error loading sync dashboard: {e}")
        messages.error(request, f"Error loading dashboard: {str(e)}")
        context = {
            'total_decisions': 0,
            'completed_extractions': 0,
            'opensearch_count': 0,
            'sync_diff': 0,
            'sync_percentage': 0,
            'missing_decisions': [],
            'error': str(e)
        }
    
    return render(request, "admin/sync_status_dashboard.html", context)


def _get_missing_count():
    """Get count of documents in DB but not in OpenSearch"""
    opensearch_service = OpenSearchService()
    missing_adas = _get_all_missing_adas(opensearch_service)
    return len(missing_adas)


def _get_all_missing_adas(opensearch_service):
    """Get all ADAs that exist in PostgreSQL but not in OpenSearch"""
    # Get all completed extractions with their ADAs
    completed_adas = set(
        DocumentExtraction.objects.filter(
            extraction_status=ProcessingStatus.COMPLETED,
            raw_text__isnull=False
        ).exclude(raw_text='').values_list('decision__ada', flat=True)
    )
    
    # Get all indexed ADAs from OpenSearch
    try:
        # Query all documents from OpenSearch (this might need pagination for large datasets)
        response = opensearch_service._test_match_all(size=10000)  # Adjust size as needed
        indexed_adas = set(
            hit['_source']['ada'] 
            for hit in response.get('hits', {}).get('hits', [])
        )
    except Exception as e:
        logger.error(f"Error fetching indexed ADAs from OpenSearch: {e}")
        indexed_adas = set()
    
    # Find the difference
    missing_adas = completed_adas - indexed_adas
    return list(missing_adas)


def _get_missing_decisions(opensearch_service, offset=0, limit=50):
    """Get decisions that exist in PostgreSQL but not in OpenSearch (paginated)"""
    missing_adas = _get_all_missing_adas(opensearch_service)
    
    # Paginate
    paginated_adas = missing_adas[offset:offset + limit]
    
    # Fetch the actual decision objects
    decisions = Decision.objects.filter(
        ada__in=paginated_adas
    ).select_related(
        'organization', 'decision_type'
    ).prefetch_related(
        'text_extraction'
    ).order_by('-issue_date')[:limit]
    
    # Enrich with extraction info
    result = []
    for decision in decisions:
        try:
            extraction = decision.text_extraction
            result.append({
                'id': decision.id,  # Add ID for admin URL
                'ada': decision.ada,
                'subject': decision.subject,
                'organization': str(decision.organization) if decision.organization else 'N/A',
                'decision_type': str(decision.decision_type) if decision.decision_type else 'N/A',
                'issue_date': decision.issue_date,
                'character_count': extraction.character_count if extraction else None,
                'page_count': extraction.page_count if extraction else None,
                'extraction_date': extraction.extraction_date if extraction else None,
            })
        except DocumentExtraction.DoesNotExist:
            result.append({
                'id': decision.id,  # Add ID for admin URL
                'ada': decision.ada,
                'subject': decision.subject,
                'organization': str(decision.organization) if decision.organization else 'N/A',
                'decision_type': str(decision.decision_type) if decision.decision_type else 'N/A',
                'issue_date': decision.issue_date,
                'character_count': None,
                'page_count': None,
                'extraction_date': None,
            })
    
    return result
