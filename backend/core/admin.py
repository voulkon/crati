from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render
from django.contrib import messages
from django.http import HttpResponseRedirect

from core.models.document_analysis import (
    DocumentExtraction, DocumentAnalysis, DocumentEmbedding,
    ProcessingStatus, ProcessingProvider
)
from core.models.decisions import Decision, Attachment
from core.models.organizations import Organization, Unit, Signer
from django import forms

class ImportDecisionsForm(forms.Form):
    ...

class DecisionAdmin(admin.ModelAdmin):
    list_display = ('ada', 'subject', 'organization', 'issue_date', 'status')
    list_filter = ('status', 'decision_type', 'has_private_data')
    search_fields = ('ada', 'subject', 'protocol_number')
    date_hierarchy = 'issue_date'
    
    # Import action implementation
    actions = ['import_decisions']
    
    def import_decisions(self, request, queryset=None):
        ...
        # Implementation

class DocumentExtractionAdmin(admin.ModelAdmin):
    list_display = ('decision_link', 'extraction_status_colored', 'extraction_provider', 
                   'page_count', 'character_count', 'is_scanned_document', 
                   'extraction_date', 'processing_time')
    
    list_filter = ('extraction_status', 'extraction_provider', 'is_scanned_document')
    search_fields = ('decision__ada', 'decision__subject')
    date_hierarchy = 'extraction_date'
    readonly_fields = ('search_vector', 'created_at', 'updated_at', 'task_id', 'processing_time_ms')
    
    fieldsets = (
        ('Decision', {
            'fields': ('decision',)
        }),
        ('Extraction Status', {
            'fields': ('extraction_status', 'extraction_provider', 'extraction_date')
        }),
        ('Document Info', {
            'fields': ('page_count', 'character_count', 'is_scanned_document')
        }),
        ('Content', {
            'fields': ('raw_text',)
        }),
        ('Processing', {
            'fields': ('error_message', 'retry_count', 'processing_time_ms', 'task_id'),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def decision_link(self, obj):
        url = reverse('admin:core_decision_change', args=[obj.decision.id])
        return format_html('<a href="{}">{}</a>', url, obj.decision.ada)
    decision_link.short_description = "Decision"
    
    def extraction_status_colored(self, obj):
        status_colors = {
            ProcessingStatus.COMPLETED: 'green',
            ProcessingStatus.FAILED: 'red',
            ProcessingStatus.PROCESSING: 'blue',
            ProcessingStatus.PENDING: 'orange',
            ProcessingStatus.NEEDS_VISION: 'purple'
        }
        color = status_colors.get(obj.extraction_status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.extraction_status)
    extraction_status_colored.short_description = "Status"
    
    def processing_time(self, obj):
        if obj.processing_time_ms:
            if obj.processing_time_ms < 1000:
                return f"{obj.processing_time_ms} ms"
            return f"{obj.processing_time_ms / 1000:.2f} sec"
        return "-"

    processing_time.short_description = "Processing Time"
    
    # Add actions for batch operations
    actions = ['retry_failed_extractions', 'mark_for_vision_processing']
    
    def retry_failed_extractions(self, request, queryset):
        # Only retry failed extractions
        failed_count = queryset.filter(extraction_status=ProcessingStatus.FAILED).update(
            extraction_status=ProcessingStatus.PENDING
        )
        
        if failed_count:
            self.message_user(
                request, 
                f"Queued {failed_count} documents for re-extraction.", 
                messages.SUCCESS
            )
        else:
            self.message_user(
                request, 
                "No failed documents selected.", 
                messages.WARNING
            )
    retry_failed_extractions.short_description = "Retry failed extractions"
    
    def mark_for_vision_processing(self, request, queryset):
        # Mark selected documents for vision processing
        vision_count = queryset.update(
            extraction_status=ProcessingStatus.NEEDS_VISION
        )
        
        if vision_count:
            self.message_user(
                request, 
                f"Marked {vision_count} documents for vision processing.", 
                messages.SUCCESS
            )
        else:
            self.message_user(request, "No documents selected.", messages.WARNING)
    mark_for_vision_processing.short_description = "Mark for Vision processing"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'batch-process/',
                self.admin_site.admin_view(self.batch_process_view),
                name='documentextraction_batch_process'
            ),
        ]
        return custom_urls + urls

    def batch_process_view(self, request):
        """View for batch processing documents"""
        from core.models.decisions import Decision
        from core.tasks import extract_document_text_task
        
        if request.method == 'POST':
            # Get parameters
            limit = int(request.POST.get('limit', 100))
            provider = request.POST.get('provider', ProcessingProvider.PYMUPDF)
            use_scanned = request.POST.get('use_scanned', False) == 'on'
            
            # Find decisions without text extraction
            decisions = Decision.objects.filter(text_extraction__isnull=True)
            
            # For any with existing extraction attempts marked as failed, retry them
            failed_extractions = DocumentExtraction.objects.filter(
                extraction_status=ProcessingStatus.FAILED
            )
            failed_extraction_decisions = Decision.objects.filter(
                text_extraction__in=failed_extractions
            )
            
            decisions = decisions.union(failed_extraction_decisions)
            
            # Apply limit
            decisions = decisions[:limit]
            
            # Queue tasks
            count = 0
            for decision in decisions:
                # Queue extraction task
                task = extract_document_text_task.delay(
                    decision_id=decision.id,
                    provider=provider,
                    force_ocr=use_scanned
                )
                
                # Create or update extraction record
                DocumentExtraction.objects.update_or_create(
                    decision=decision,
                    defaults={
                        'extraction_status': ProcessingStatus.PENDING,
                        'extraction_provider': provider,
                        'task_id': task.id
                    }
                )
                count += 1
            
            messages.success(
                request, 
                f"Queued {count} documents for text extraction with {provider}."
            )
            return HttpResponseRedirect(
                reverse('admin:core_documentextraction_changelist')
            )
        
        # Get stats for form
        unprocessed_count = Decision.objects.filter(
            text_extraction__isnull=True
        ).count()
        
        failed_count = DocumentExtraction.objects.filter(
            extraction_status=ProcessingStatus.FAILED
        ).count()
        
        providers = [
            (provider.value, provider.label) 
            for provider in ProcessingProvider
            if provider.value not in [
                ProcessingProvider.OPENAI,
                ProcessingProvider.ANTHROPIC, 
                ProcessingProvider.GOOGLE_VERTEX,
                ProcessingProvider.MISTRAL,
                ProcessingProvider.OLLAMA,
                ProcessingProvider.OPENAI_EMBED,
                ProcessingProvider.GOOGLE_EMBED,
                ProcessingProvider.SENTENCE_TRANSFORMERS
            ]
        ]
        
        context = {
            'unprocessed_count': unprocessed_count,
            'failed_count': failed_count,
            'providers': providers,
            'title': 'Batch Process Documents',
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/batch_process_documents.html', context)

    # Add a button to the change list
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['batch_process_url'] = reverse('admin:documentextraction_batch_process')
        return super().changelist_view(request, extra_context)

# These registrations are for the default admin site
admin.site.register(Decision, DecisionAdmin)
admin.site.register(Attachment)
admin.site.register(Organization)
admin.site.register(Unit)
admin.site.register(Signer)
admin.site.register(DocumentExtraction, DocumentExtractionAdmin)
admin.site.register(DocumentAnalysis)
admin.site.register(DocumentEmbedding)

# Register your models here.
