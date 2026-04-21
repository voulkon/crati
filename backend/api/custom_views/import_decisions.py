from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from core.models.import_jobs import ImportJob, ImportJobStatus
from datetime import datetime, timedelta
import json
from loguru import logger

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
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        entity_type = request.POST.get('entity_type')
        entity_id = request.POST.get('entity_id')
        
        if not all([start_date_str, end_date_str, entity_type, entity_id]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters'
            }, status=400)
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()
        
        # Use the single source of truth: fetch_daily_decisions_distributed
        # This ensures consistency with validate_imports and other import flows
        try:
            from core.tasks.tasks_decisions_import import fetch_daily_decisions_distributed
            
            # Dispatch one task per day in the range
            dispatched_tasks = []
            current_date = start_date
            
            while current_date <= end_date:
                # Create ImportJob for this specific date
                job = ImportJob.objects.create(
                    start_date=current_date,
                    end_date=current_date,
                    organization_id=entity_id if entity_type == 'organization' else None,
                    unit_id=entity_id if entity_type == 'unit' else None,
                    signer_id=entity_id if entity_type == 'signer' else None,
                    status=ImportJobStatus.PENDING,
                    created_by=request.user,
                    created_at=datetime.now(),
                )
                
                # Dispatch distributed import task (single source of truth)
                task = fetch_daily_decisions_distributed.delay(
                    target_date_str=current_date.isoformat(),
                    chunk_size=10,
                    force=False,
                    job_id=job.id
                )
                
                dispatched_tasks.append({
                    'date': current_date.isoformat(),
                    'job_id': job.id,
                    'task_id': task.id
                })
                
                logger.info(
                    f"Coverage Explorer: Dispatched import for {current_date} "
                    f"({entity_type} {entity_id}), ImportJob #{job.id}, Task {task.id}"
                )
                
                current_date += timedelta(days=1)
            
            # Return success with all dispatched tasks
            return JsonResponse({
                'success': True,
                'tasks': dispatched_tasks,
                'count': len(dispatched_tasks),
                'message': f'Dispatched {len(dispatched_tasks)} import tasks for {entity_type} {entity_id} from {start_date_str} to {end_date_str}'
            })
            
        except Exception as e:
            logger.error(f"Coverage Explorer import failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)