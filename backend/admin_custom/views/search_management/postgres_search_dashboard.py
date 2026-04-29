"""
PostgreSQL Search Management Dashboard

Admin interface for managing PostgreSQL full-text search infrastructure:
- View status of feature flags, triggers, and indexes
- Execute management commands (backfill, cleanup, enable/disable)
- Monitor disk usage and record counts
- Safe execution with confirmation dialogs
"""

from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import connection
from django.core.management import call_command
from io import StringIO
from loguru import logger
import json

from core.services.feature_flag_service import feature_flags
from core.models.document_analysis import DocumentExtraction, DocumentPage


@staff_member_required
def postgres_search_dashboard(request):
    """Main dashboard for PostgreSQL search management"""
    
    # Get status for both models
    extraction_status = _get_model_status('extraction')
    page_status = _get_model_status('page')
    
    # Get feature flag status
    opensearch_enabled = feature_flags.is_enabled('INDEX_THE_OPENSEARCH')
    postgres_enabled = feature_flags.is_enabled('INDEX_THE_POSTGRES')
    
    # Calculate summary statistics
    total_records = extraction_status['total_count'] + page_status['total_count']
    total_indexed = extraction_status['indexed_count'] + page_status['indexed_count']
    total_null = extraction_status['null_count'] + page_status['null_count']
    
    # Calculate estimated space usage
    extraction_index_size_bytes = extraction_status.get('index_size_bytes', 0)
    page_index_size_bytes = page_status.get('index_size_bytes', 0)
    total_index_size_gb = (extraction_index_size_bytes + page_index_size_bytes) / (1024**3)
    
    # Estimate search_vector data size (rough: ~7GB for 500k records)
    estimated_vector_size_gb = (total_indexed / 500000) * 7 if total_indexed > 0 else 0
    total_search_size_gb = total_index_size_gb + estimated_vector_size_gb
    
    context = {
        'title': 'PostgreSQL Search Management',
        'extraction_status': extraction_status,
        'page_status': page_status,
        'opensearch_enabled': opensearch_enabled,
        'postgres_enabled': postgres_enabled,
        'summary': {
            'total_records': total_records,
            'total_indexed': total_indexed,
            'total_null': total_null,
            'index_size_gb': round(total_index_size_gb, 2),
            'estimated_vector_size_gb': round(estimated_vector_size_gb, 2),
            'total_search_size_gb': round(total_search_size_gb, 2),
            'indexing_percentage': round((total_indexed / total_records * 100) if total_records > 0 else 0, 1),
        },
        # Workflow recommendations
        'workflows': _get_workflow_recommendations(opensearch_enabled, postgres_enabled, extraction_status, page_status),
    }
    
    return render(request, 'admin/postgres_search_dashboard.html', context)


@staff_member_required
def execute_search_command(request):
    """Execute a PostgreSQL search management command via AJAX"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        command_type = data.get('command')
        model = data.get('model', 'both')
        options = data.get('options', {})
        
        # Validate command type
        valid_commands = [
            'backfill_search_vectors',
            'cleanup_search_vectors',
            'disable_trigger',
            'enable_trigger',
            'drop_index',
            'create_index',
            'disable_all',
            'enable_all',
            'check_status',
        ]
        
        if command_type not in valid_commands:
            return JsonResponse({
                'success': False,
                'error': f'Invalid command: {command_type}'
            }, status=400)
        
        # Execute the command
        result = _execute_command(command_type, model, options)
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error executing search command: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def _get_model_status(model_name):
    """Get detailed status for a specific model"""
    
    if model_name == 'extraction':
        table = 'core_documentextraction'
        trigger = 'document_extraction_search_vector_update'
        index = 'core_docume_search__d7ddb0_gin'
    else:  # page
        table = 'core_documentpage'
        trigger = 'document_page_search_vector_update'
        index = 'core_docume_search__9e73d9_gin'
    
    with connection.cursor() as cursor:
        # Get record counts
        cursor.execute(f"""
            SELECT 
                COUNT(*) FILTER (WHERE search_vector IS NULL) as null_count,
                COUNT(*) FILTER (WHERE search_vector IS NOT NULL) as indexed_count,
                COUNT(*) as total_count
            FROM {table}
        """)
        counts = cursor.fetchone()
        
        # Get trigger status
        cursor.execute("""
            SELECT 
                CASE tgenabled 
                    WHEN 'O' THEN 'enabled'
                    WHEN 'D' THEN 'disabled'
                    ELSE 'unknown'
                END as status
            FROM pg_trigger 
            WHERE tgname = %s
        """, [trigger])
        trigger_row = cursor.fetchone()
        trigger_status = trigger_row[0] if trigger_row else 'not_found'
        
        # Get index status and size
        cursor.execute("""
            SELECT 
                pg_relation_size(pg_class.oid) as size_bytes,
                pg_size_pretty(pg_relation_size(pg_class.oid)) as size_pretty
            FROM pg_indexes
            JOIN pg_class ON pg_class.relname = pg_indexes.indexname
            WHERE indexname = %s
        """, [index])
        index_row = cursor.fetchone()
        
        if index_row:
            index_status = 'exists'
            index_size_bytes = index_row[0]
            index_size = index_row[1]
        else:
            index_status = 'missing'
            index_size_bytes = 0
            index_size = 'N/A'
        
        # Get table size
        cursor.execute(f"""
            SELECT 
                pg_size_pretty(pg_total_relation_size(%s)) as total_size,
                pg_size_pretty(pg_relation_size(%s)) as table_size
        """, [table, table])
        sizes = cursor.fetchone()
    
    return {
        'model': model_name,
        'table': table,
        'trigger_name': trigger,
        'index_name': index,
        'null_count': counts[0],
        'indexed_count': counts[1],
        'total_count': counts[2],
        'indexing_percentage': round((counts[1] / counts[2] * 100) if counts[2] > 0 else 0, 1),
        'trigger_status': trigger_status,
        'index_status': index_status,
        'index_size': index_size,
        'index_size_bytes': index_size_bytes,
        'total_table_size': sizes[0],
        'main_table_size': sizes[1],
    }


def _get_workflow_recommendations(opensearch_enabled, postgres_enabled, extraction_status, page_status):
    """Generate workflow recommendations based on current state"""
    
    workflows = []
    
    # Check if both search methods are disabled
    if not opensearch_enabled and not postgres_enabled:
        workflows.append({
            'title': '⚠️ No Search Available',
            'type': 'warning',
            'description': 'Both OpenSearch and PostgreSQL search are disabled. Document content search is unavailable.',
            'actions': [
                {
                    'label': 'Enable PostgreSQL Search',
                    'command': 'enable_all',
                    'model': 'both',
                    'style': 'primary'
                }
            ]
        })
    
    # Check if triggers are enabled but indexes are missing
    extraction_triggers_on = extraction_status['trigger_status'] == 'enabled'
    extraction_index_missing = extraction_status['index_status'] == 'missing'
    page_triggers_on = page_status['trigger_status'] == 'enabled'
    page_index_missing = page_status['index_status'] == 'missing'
    
    if (extraction_triggers_on and extraction_index_missing) or (page_triggers_on and page_index_missing):
        workflows.append({
            'title': '⚠️ Triggers Without Indexes',
            'type': 'warning',
            'description': 'Triggers are enabled but indexes are missing. Searches will be slow.',
            'actions': [
                {
                    'label': 'Create Indexes',
                    'command': 'create_index',
                    'model': 'both',
                    'style': 'primary'
                }
            ]
        })
    
    # Check if there are unindexed records
    total_null = extraction_status['null_count'] + page_status['null_count']
    if total_null > 0 and postgres_enabled:
        workflows.append({
            'title': '🔄 Backfill Needed',
            'type': 'info',
            'description': f'{total_null:,} records need search_vector backfill for full-text search.',
            'actions': [
                {
                    'label': 'Backfill Search Vectors',
                    'command': 'backfill_search_vectors',
                    'model': 'both',
                    'style': 'primary'
                }
            ]
        })
    
    # Suggest cleanup if PostgreSQL search is disabled and vectors exist
    total_indexed = extraction_status['indexed_count'] + page_status['indexed_count']
    if not postgres_enabled and total_indexed > 0:
        workflows.append({
            'title': '💾 Reclaim Disk Space',
            'type': 'info',
            'description': f'PostgreSQL search is disabled but {total_indexed:,} records still have search_vector data (~7GB).',
            'actions': [
                {
                    'label': 'Cleanup & Reclaim Space',
                    'command': 'cleanup_search_vectors',
                    'model': 'both',
                    'style': 'warning'
                }
            ]
        })
    
    # Recommend disabling if not being used
    if postgres_enabled and opensearch_enabled:
        workflows.append({
            'title': '💡 Optimization Opportunity',
            'type': 'suggestion',
            'description': 'Both search engines are enabled. If OpenSearch is your primary search, you can disable PostgreSQL search to save ~16GB.',
            'actions': [
                {
                    'label': 'Disable PostgreSQL Search',
                    'command': 'disable_all',
                    'model': 'both',
                    'style': 'secondary'
                }
            ]
        })
    
    return workflows


def _execute_command(command_type, model, options):
    """Execute a management command and capture output"""
    
    try:
        # Capture command output
        output = StringIO()
        
        if command_type == 'check_status':
            # Just return current status
            extraction_status = _get_model_status('extraction')
            page_status = _get_model_status('page')
            return {
                'success': True,
                'message': 'Status refreshed',
                'data': {
                    'extraction': extraction_status,
                    'page': page_status,
                }
            }
        
        elif command_type == 'backfill_search_vectors':
            # Backfill search vectors
            call_command(
                'backfill_search_vectors',
                model=model,
                batch_size=options.get('batch_size', 1000),
                only_null=options.get('only_null', True),
                force=True,
                stdout=output
            )
            
        elif command_type == 'cleanup_search_vectors':
            # Cleanup search vectors
            call_command(
                'cleanup_search_vectors',
                model=model,
                batch_size=options.get('batch_size', 5000),
                no_vacuum=options.get('no_vacuum', False),
                vacuum_full=options.get('vacuum_full', False),
                force=True,
                stdout=output
            )
            
        elif command_type in ['disable_trigger', 'enable_trigger', 'drop_index', 'create_index']:
            # Individual trigger/index operations
            action_map = {
                'disable_trigger': '--disable-trigger',
                'enable_trigger': '--enable-trigger',
                'drop_index': '--drop-index',
                'create_index': '--create-index',
            }
            
            call_command(
                'manage_postgres_search',
                action_map[command_type],
                model=model,
                force=True,
                stdout=output
            )
            
        elif command_type == 'disable_all':
            # Complete disable workflow
            call_command(
                'manage_postgres_search',
                '--disable-all',
                model=model,
                force=True,
                stdout=output
            )
            
        elif command_type == 'enable_all':
            # Complete enable workflow
            call_command(
                'manage_postgres_search',
                '--enable-all',
                model=model,
                force=True,
                stdout=output
            )
        
        output_text = output.getvalue()
        logger.info(f"Executed search command {command_type} on {model}: {output_text}")
        
        return {
            'success': True,
            'message': f'Command {command_type} completed successfully',
            'output': output_text
        }
        
    except Exception as e:
        logger.error(f"Error executing {command_type}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        output.close()
