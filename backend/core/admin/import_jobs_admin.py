"""
Admin views for Import Job Queue monitoring
"""
from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse
from core.models.import_jobs import ImportJob, ImportJobStatus
from core.services.import_job_queue import ImportJobQueue


class ImportJobQueueAdmin(admin.ModelAdmin):
    """
    Custom admin for ImportJob with queue status display
    """
    list_display = ['id', 'start_date', 'status', 'total_decisions', 'progress_percentage', 'created_at', 'completed_at']
    list_filter = ['status', 'start_date']
    search_fields = ['id', 'start_date']
    readonly_fields = ['created_at', 'completed_at', 'celery_task_id', 'progress_percentage']
    ordering = ['-created_at']
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('queue-status/', self.admin_site.admin_view(self.queue_status_view), name='import_job_queue_status'),
        ]
        return custom_urls + urls
    
    def queue_status_view(self, request):
        """JSON endpoint for queue status (for AJAX polling)"""
        queue = ImportJobQueue()
        status = queue.get_queue_status()
        return JsonResponse(status)
    
    def changelist_view(self, request, extra_context=None):
        """Add queue status to changelist view"""
        queue = ImportJobQueue()
        extra_context = extra_context or {}
        extra_context['queue_status'] = queue.get_queue_status()
        return super().changelist_view(request, extra_context=extra_context)


# Register with custom admin
admin.site.register(ImportJob, ImportJobQueueAdmin)
