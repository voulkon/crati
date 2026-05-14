"""
Admin interface for AFM Scoring and Fetch Queue Management

Provides:
1. Configuration management for scoring criteria
2. View/search scored entities
3. Cockpit dashboard for queue monitoring and control
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django import forms
from django.http import JsonResponse
from decimal import Decimal

from core.models.afm_scoring import AFMScoringConfig, AFMEntityScore
from core.models.entities import AFMEntity
from core.services.afm_scoring_service import AFMEntityScoringService
from core.services.afm_fetch_queue_service import AFMFetchQueueService


class AFMScoringConfigForm(forms.ModelForm):
    """Custom form with weight validation."""
    
    class Meta:
        model = AFMScoringConfig
        exclude = ['created_by']  # Set automatically in admin, avoid circular import
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate weights sum to 1.0
        freq_weight = cleaned_data.get('frequency_weight', 0)
        amount_weight = cleaned_data.get('amount_weight', 0)
        org_weight = cleaned_data.get('organization_weight', 0)
        
        total = freq_weight + amount_weight + org_weight
        if not (0.99 <= total <= 1.01):
            raise forms.ValidationError(
                f'Weights must sum to 1.0, got {total:.2f}. '
                f'Adjust: Frequency={freq_weight}, Amount={amount_weight}, Organization={org_weight}'
            )
        
        return cleaned_data


@admin.register(AFMScoringConfig)
class AFMScoringConfigAdmin(admin.ModelAdmin):
    """Admin for scoring configuration."""
    
    form = AFMScoringConfigForm
    
    change_list_template = 'admin/afm_scoring_config_changelist.html'
    
    list_display = [
        'name', 
        'is_active_badge',
        'weight_summary',
        'threshold_summary',
        'actions_column'
    ]
    list_filter = ['is_active', 'enable_recency_boost']
    search_fields = ['name', 'notes']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'is_active', 'notes')
        }),
        ('Scoring Weights (must sum to 1.0)', {
            'fields': (
                'frequency_weight',
                'amount_weight',
                'organization_weight',
            ),
            'description': 'These weights determine how much each factor contributes to the total score.'
        }),
        ('Filtering Thresholds', {
            'fields': (
                'min_appearances',
                'min_total_amount',
                'min_unique_organizations',
            ),
            'description': 'Minimum requirements for an entity to be eligible for fetching.'
        }),
        ('Retry Configuration', {
            'fields': (
                'retry_failed_after_days',
                'never_retry_after_failures',
            ),
        }),
        ('Recency Boost (Optional)', {
            'fields': (
                'enable_recency_boost',
                'recency_days_threshold',
                'recency_boost_multiplier',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ ACTIVE</span>')
        return format_html('<span style="color: gray;">Inactive</span>')
    is_active_badge.short_description = 'Status'
    
    def weight_summary(self, obj):
        return format_html(
            '<small>Freq: {:.0%} | Amt: {:.0%} | Org: {:.0%}</small>',
            obj.frequency_weight,
            obj.amount_weight,
            obj.organization_weight
        )
    weight_summary.short_description = 'Weights'
    
    def threshold_summary(self, obj):
        return format_html(
            '<small>≥{} apps | ≥€{:,.0f} | ≥{} orgs</small>',
            obj.min_appearances,
            obj.min_total_amount,
            obj.min_unique_organizations
        )
    threshold_summary.short_description = 'Thresholds'
    
    def actions_column(self, obj):
        if obj.is_active:
            return format_html(
                '<a class="button" href="{}">Run Scoring Now</a>',
                reverse('admin:afm_cockpit') + f'?config_id={obj.id}&action=score'
            )
        return '-'
    actions_column.short_description = 'Actions'


@admin.register(AFMEntityScore)
class AFMEntityScoreAdmin(admin.ModelAdmin):
    """Admin for viewing scored entities."""
    
    change_list_template = 'admin/afm_entity_score_changelist.html'
    
    list_display = [
        'afm_link',
        'priority_badge',
        'total_score_bar',
        'eligibility_badge',
        'metrics_summary',
        'gemi_status',
        'scored_at',
    ]
    list_filter = [
        'is_eligible',
        'entity__gemi_lookup_success',
        'entity__entity_type',
        'config_used',
    ]
    search_fields = ['entity__afm', 'entity__name']
    readonly_fields = [
        'entity',
        'total_score',
        'frequency_score',
        'amount_score',
        'organization_score',
        'total_appearances',
        'total_amount',
        'unique_organizations',
        'is_eligible',
        'fetch_priority',
        'config_used',
        'scored_at',
    ]
    
    # Default ordering: highest priority first
    ordering = ['fetch_priority']
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def afm_link(self, obj):
        admin_url = reverse('admin:core_afmentity_change', args=[obj.entity.pk])
        return format_html(
            '<a href="{}" target="_blank"><strong>{}</strong></a><br/><small>{}</small>',
            admin_url,
            obj.entity.afm,
            obj.entity.name[:50] if obj.entity.name else 'No name'
        )
    afm_link.short_description = 'AFM Entity'
    
    def priority_badge(self, obj):
        if not obj.is_eligible:
            return format_html('<span style="color: gray;">-</span>')
        
        # Color code by priority
        if obj.fetch_priority <= 10:
            color = '#d32f2f'  # Red for top 10
        elif obj.fetch_priority <= 50:
            color = '#f57c00'  # Orange for top 50
        elif obj.fetch_priority <= 100:
            color = '#fbc02d'  # Yellow for top 100
        else:
            color = '#757575'  # Gray for others
        
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">#{}</span>',
            color,
            obj.fetch_priority
        )
    priority_badge.short_description = 'Priority'
    
    def total_score_bar(self, obj):
        # Visual progress bar for score
        width = min(obj.total_score, 100)
        
        # Color gradient
        if width >= 75:
            color = '#4caf50'  # Green
        elif width >= 50:
            color = '#ff9800'  # Orange
        else:
            color = '#9e9e9e'  # Gray
        
        return format_html(
            '<div style="width: 100px; background: #e0e0e0; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; color: white; text-align: center; font-size: 11px; font-weight: bold; padding: 2px 0;">'
            '{:.1f}'
            '</div></div>',
            width,
            color,
            obj.total_score
        )
    total_score_bar.short_description = 'Score'
    
    def eligibility_badge(self, obj):
        if obj.is_eligible:
            return format_html('<span style="color: green;">✓ Eligible</span>')
        return format_html('<span style="color: #999;">✗ Ineligible</span>')
    eligibility_badge.short_description = 'Eligible'
    
    def metrics_summary(self, obj):
        return format_html(
            '<small>'
            '{} apps<br/>'
            '€{:,.0f}<br/>'
            '{} orgs'
            '</small>',
            obj.total_appearances,
            obj.total_amount,
            obj.unique_organizations
        )
    metrics_summary.short_description = 'Metrics'
    
    def gemi_status(self, obj):
        entity = obj.entity
        
        if entity.gemi_lookup_success:
            return format_html(
                '<span style="color: green;">✓ Fetched</span><br/>'
                '<small>{} companies</small>',
                entity.gemi_companies_count
            )
        elif entity.gemi_lookup_attempted:
            return format_html(
                '<span style="color: orange;">⚠ Failed</span><br/>'
                '<small>{} attempts</small>',
                entity.error_count
            )
        else:
            return format_html('<span style="color: gray;">Not attempted</span>')
    gemi_status.short_description = 'GEMI Status'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('cockpit/', self.admin_site.admin_view(self.cockpit_view), name='afm_cockpit'),
            path('cockpit/score/', self.admin_site.admin_view(self.run_scoring_view), name='afm_run_scoring'),
            path('cockpit/populate/', self.admin_site.admin_view(self.populate_queue_view), name='afm_populate_queue'),
            path('cockpit/process/', self.admin_site.admin_view(self.process_batch_view), name='afm_process_batch'),
            path('cockpit/status/', self.admin_site.admin_view(self.queue_status_api), name='afm_queue_status_api'),
        ]
        return custom_urls + urls
    
    def cockpit_view(self, request):
        """Main cockpit dashboard."""
        
        # Get active config
        config = AFMScoringConfig.get_active()
        
        # Get queue service
        queue_service = AFMFetchQueueService()
        queue_status = queue_service.get_queue_status()
        
        # Get top entities
        top_unfetched = AFMEntityScore.objects.filter(
            is_eligible=True,
            entity__gemi_lookup_success=False
        ).select_related('entity').order_by('fetch_priority')[:20]
        
        # Get recently fetched
        recently_fetched = AFMEntity.objects.filter(
            gemi_lookup_success=True,
            gemi_lookup_attempted__isnull=False
        ).order_by('-gemi_lookup_attempted')[:10]
        
        # Get overall statistics
        total_entities = AFMEntity.objects.count()
        total_scored = AFMEntityScore.objects.count()
        eligible_count = AFMEntityScore.objects.filter(is_eligible=True).count()
        fetched_count = AFMEntity.objects.filter(gemi_lookup_success=True).count()
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'AFM Fetch Queue Cockpit',
            'config': config,
            'queue_status': queue_status,
            'top_unfetched': top_unfetched,
            'recently_fetched': recently_fetched,
            'total_entities': total_entities,
            'total_scored': total_scored,
            'eligible_count': eligible_count,
            'fetched_count': fetched_count,
            'fetch_percentage': round(fetched_count / eligible_count * 100, 1) if eligible_count > 0 else 0,
        }
        
        return render(request, 'admin/afm_cockpit.html', context)
    
    def run_scoring_view(self, request):
        """Trigger scoring algorithm."""
        if request.method == 'POST':
            try:
                service = AFMEntityScoringService()
                stats = service.score_all_entities(
                    batch_size=1000,
                    exclude_already_fetched=False
                )
                
                messages.success(
                    request,
                    f"Scoring completed! "
                    f"Scored: {stats['total_scored']}, "
                    f"Eligible: {stats['eligible_for_fetch']}"
                )
                
            except Exception as e:
                messages.error(request, f"Scoring failed: {str(e)}")
        
        return redirect('admin:afm_cockpit')
    
    def populate_queue_view(self, request):
        """Populate Redis queue from scores."""
        if request.method == 'POST':
            try:
                limit = request.POST.get('limit')
                limit = int(limit) if limit else None
                force = request.POST.get('force_refresh') == 'on'
                
                queue_service = AFMFetchQueueService()
                stats = queue_service.populate_queue_from_scores(
                    limit=limit,
                    force_refresh=force
                )
                
                messages.success(
                    request,
                    f"Queue populated! Added: {stats['added']}, "
                    f"Total pending: {stats['total_pending']}"
                )
                
            except Exception as e:
                messages.error(request, f"Queue population failed: {str(e)}")
        
        return redirect('admin:afm_cockpit')
    
    def process_batch_view(self, request):
        """Process a batch from the queue."""
        if request.method == 'POST':
            try:
                batch_size = int(request.POST.get('batch_size', 50))
                
                queue_service = AFMFetchQueueService()
                stats = queue_service.process_batch(batch_size=batch_size)
                
                if stats.get('status') == 'locked':
                    messages.warning(request, stats['message'])
                elif stats.get('status') == 'empty_queue':
                    messages.info(request, "Queue is empty")
                else:
                    messages.success(
                        request,
                        f"Batch processed! "
                        f"Successful: {stats['successful']}, "
                        f"Failed: {stats['failed']}, "
                        f"Not found: {stats['not_found']}"
                    )
                
            except Exception as e:
                messages.error(request, f"Batch processing failed: {str(e)}")
        
        return redirect('admin:afm_cockpit')
    
    def queue_status_api(self, request):
        """API endpoint for real-time queue status (AJAX)."""
        try:
            queue_service = AFMFetchQueueService()
            status = queue_service.get_queue_status()
            return JsonResponse(status)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
