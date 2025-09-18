from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from core.models.import_jobs import ImportJob, ImportJobStatus
from core.services.decision_ingestion_service import DecisionIngestionService
from core.fetchers.diavgeia_fetcher import DiavgeiaFetcher
from core.importers.decisions import DecisionImporter
from datetime import datetime
import json

@csrf_exempt
@require_POST
@staff_member_required
def calendar_bulk_import(request):
    """
    Admin view for importing decisions from a calendar date range selection.
    
    Expects POST data with:
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    - entity_type: 'organization', 'unit', or 'signer'
    - entity_id: ID of the organization, unit, or signer
    """
    try:
        # Parse request data
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        entity_type = request.POST.get('entity_type')
        entity_id = request.POST.get('entity_id')
        
        if not all([start_date, end_date, entity_type, entity_id]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters'
            }, status=400)
        
        # Create import job record
        job = ImportJob.objects.create(
            start_date=start_date,
            end_date=end_date,
            organization_id=entity_id if entity_type == 'organization' else None,
            unit_id=entity_id if entity_type == 'unit' else None,
            signer_id=entity_id if entity_type == 'signer' else None,
            status=ImportJobStatus.PENDING,
            created_by=request.user,
            created_at=datetime.now(),
        )
        
        # Build search params
        search_params = {}
        if entity_type == 'organization':
            search_params['org'] = entity_id
        elif entity_type == 'unit':
            search_params['unit'] = entity_id
        else:  # signer
            search_params['signer'] = entity_id
        
        # Use the service directly with background processing
        # This is more direct than going through a separate task
        try:
            # Create service components
            fetcher = DiavgeiaFetcher()
            importer = DecisionImporter()
            service = DecisionIngestionService(
                diavgeia_fetcher=fetcher,
                decision_importer=importer
            )
            
            # Start the import in a background thread/task using the job_id
            # Using the enhanced service that handles job tracking
            from core.tasks import process_fetch_period
            
            task = process_fetch_period.delay(
                start_date_str=start_date,
                end_date_str=end_date,
                search_params=search_params,
                job_id=job.id
            )
            
            # Return success with job ID for tracking
            return JsonResponse({
                'success': True,
                'job_id': job.id,
                'task_id': task.id,
                'message': f'Import job started for {entity_type} {entity_id} from {start_date} to {end_date}'
            })
            
        except Exception as e:
            # Update job status on error
            job.status = ImportJobStatus.FAILED
            job.error_details = str(e)
            job.save()
            
            return JsonResponse({
                'success': False,
                'job_id': job.id,
                'error': str(e)
            }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)