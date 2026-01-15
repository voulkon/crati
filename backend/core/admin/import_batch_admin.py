"""
Import Batch Admin Interface

Provides Django admin interface for monitoring and managing import batches.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from core.models import ImportBatch


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = [
        'batch_id',
        'target_date',
        'status_badge',
        'progress_bar',
        'total_decisions',
        'decisions_processed',
        'decisions_failed',
        'created_at',
        'duration',
    ]
    list_filter = ['status', 'target_date', 'created_at']
    search_fields = ['batch_id', 'fetch_task_id']
    readonly_fields = [
        'batch_id',
        'fetch_task_id',
        'target_date',
        'total_decisions',
        'total_chunks',
        'chunks_completed',
        'chunks_failed',
        'decisions_processed',
        'decisions_failed',
        'chunk_task_ids',
        'search_params',
        'error_details',
        'created_at',
        'updated_at',
        'started_at',
        'completed_at',
        'progress_display',
    ]
    
    fieldsets = (
        ('Identification', {
            'fields': ('batch_id', 'target_date', 'fetch_task_id', 'status')
        }),
        ('Progress', {
            'fields': (
                'progress_display',
                'total_decisions',
                'decisions_processed',
                'decisions_failed',
            )
        }),
        ('Chunks', {
            'fields': (
                'total_chunks',
                'chunks_completed',
                'chunks_failed',
                'chunk_task_ids',
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('search_params', 'error_details'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'started_at', 'completed_at')
        }),
    )
    
    def status_badge(self, obj):
        """Display status with colored badge"""
        colors = {
            'fetching': '#3498db',  # Blue
            'splitting': '#9b59b6',  # Purple
            'processing': '#f39c12',  # Orange
            'completed': '#27ae60',  # Green
            'failed': '#e74c3c',  # Red
            'partially_completed': '#e67e22',  # Dark orange
        }
        color = colors.get(obj.status, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def progress_bar(self, obj):
        """Display visual progress bar"""
        percentage = obj.progress_percentage
        
        # Color based on status
        if obj.status == 'completed':
            color = '#27ae60'
        elif obj.status == 'failed':
            color = '#e74c3c'
        elif obj.chunks_failed > 0:
            color = '#e67e22'
        else:
            color = '#3498db'
        
        return format_html(
            '<div style="width: 200px; background-color: #ecf0f1; border-radius: 3px; '
            'overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; height: 20px; '
            'transition: width 0.3s;"></div>'
            '</div>'
            '<span style="font-size: 11px; color: #7f8c8d;">{:.1f}%</span>',
            percentage,
            color,
            percentage
        )
    progress_bar.short_description = 'Progress'
    
    def progress_display(self, obj):
        """Detailed progress display for detail view"""
        percentage = obj.progress_percentage
        
        html = f'''
        <div style="margin: 10px 0;">
            <h3>Overall Progress: {percentage:.1f}%</h3>
            <div style="width: 100%; background-color: #ecf0f1; border-radius: 5px; overflow: hidden; margin: 10px 0;">
                <div style="width: {percentage}%; background-color: #3498db; height: 30px; transition: width 0.3s;"></div>
            </div>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <tr>
                    <td style="padding: 5px; border: 1px solid #ddd;"><strong>Total Chunks:</strong></td>
                    <td style="padding: 5px; border: 1px solid #ddd;">{obj.total_chunks}</td>
                </tr>
                <tr>
                    <td style="padding: 5px; border: 1px solid #ddd;"><strong>Completed Chunks:</strong></td>
                    <td style="padding: 5px; border: 1px solid #ddd; color: #27ae60;">{obj.chunks_completed}</td>
                </tr>
                <tr>
                    <td style="padding: 5px; border: 1px solid #ddd;"><strong>Failed Chunks:</strong></td>
                    <td style="padding: 5px; border: 1px solid #ddd; color: #e74c3c;">{obj.chunks_failed}</td>
                </tr>
                <tr>
                    <td style="padding: 5px; border: 1px solid #ddd;"><strong>Pending Chunks:</strong></td>
                    <td style="padding: 5px; border: 1px solid #ddd;">{obj.total_chunks - obj.chunks_completed - obj.chunks_failed}</td>
                </tr>
            </table>
        </div>
        '''
        return mark_safe(html)
    progress_display.short_description = 'Progress Details'
    
    def duration(self, obj):
        """Calculate and display duration"""
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            minutes = int(delta.total_seconds() / 60)
            seconds = int(delta.total_seconds() % 60)
            return f"{minutes}m {seconds}s"
        elif obj.started_at:
            from django.utils import timezone
            delta = timezone.now() - obj.started_at
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes}m (ongoing)"
        return "-"
    duration.short_description = 'Duration'
    
    def has_add_permission(self, request):
        """Prevent manual creation (batches are created by tasks)"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion only for old completed/failed batches"""
        if obj and obj.status in ['completed', 'failed', 'partially_completed']:
            return True
        return False
