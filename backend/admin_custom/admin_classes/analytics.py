from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
import json

from core.models.decision_health import HealthStatus
from core.services.pipeline_orchestrator import DecisionPipelineOrchestrator
from core.tasks import backfill_health_checks_for_import_job, retry_failed_decisions_for_import_job
from api.models import APIAnalytics, DailyTraffic, EndpointStats


class APIAnalyticsAdmin(admin.ModelAdmin):
    """Admin interface for API Analytics"""
    
    list_display = (
        "timestamp",
        "total_requests",
        "unique_ips",
        "endpoint_count",
        "avg_requests_per_ip",
    )
    date_hierarchy = "timestamp"
    list_filter = ("timestamp",)
    ordering = ("-timestamp",)

    def endpoint_count(self, obj):
        return obj.endpoints.count()
    endpoint_count.short_description = "Endpoints Hit"

    def avg_requests_per_ip(self, obj):
        if obj.unique_ips > 0:
            return round(obj.total_requests / obj.unique_ips, 2)
        return 0
    avg_requests_per_ip.short_description = "Avg Req/IP"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("endpoints")


class EndpointStatsAdmin(admin.ModelAdmin):
    """Admin interface for Endpoint Statistics"""
    list_display = ("endpoint", "count")
    search_fields = ("endpoint",)


class DailyTrafficAdmin(admin.ModelAdmin):
    """Admin interface for Daily Traffic"""
    list_display = ("date", "count")
    date_hierarchy = "date"


class ImportJobAdmin(admin.ModelAdmin):
    """Admin interface for Import Jobs with Redis chunking progress tracking"""
    list_display = (
        "id",
        "start_date",
        "end_date",
        "entity_name",
        "status",
        "created_by",
        "created_at",
        "decisions_count",
        "chunk_progress_display",
        "total_decisions",
        "new_decisions",
        "no_health_check_count",
        "no_health_check_link",
        "healthy_count",
        "warning_count",
        "health_error_count",
        "unknown_count",
        "health_percentage",
        "warning_health_checks_link",
        "failed_health_checks_link",
    )
    list_filter = ("status", "created_by", "created_at")
    search_fields = ("organization__label", "signer__first_name", "signer__last_name", "celery_task_id")
    date_hierarchy = "created_at"
    readonly_fields = [
        'created_at',
    ]
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'start_date', 'end_date', 'status', 'created_by', 'created_at', 'completed_at')
        }),
        ('Progress', {
            'fields': ('total_decisions', 'new_decisions', 'updated_decisions', 'error_count')
        }),
        ('Redis Chunks', {
            'fields': ('total_chunks', 'chunks_completed', 'chunks_failed', 'chunk_task_ids', 'search_params'),
            'classes': ('collapse',)
        }),
        ('Entity Filters', {
            'fields': ('organization', 'unit', 'signer'),
            'classes': ('collapse',)
        }),
        ('Error Details', {
            'fields': ('error_details', 'celery_task_id'),
            'classes': ('collapse',)
        }),
    )
    actions = (
        "download_batch_health_report",
        "enqueue_backfill_missing_health_checks",
        "enqueue_retry_failed_decisions",
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            decisions_count=Count("decisions", distinct=True),
            health_checks_count=Count("decisions__health_check", distinct=True),
            healthy_count=Count(
                "decisions__health_check",
                filter=Q(decisions__health_check__overall_status=HealthStatus.HEALTHY),
                distinct=True,
            ),
            warning_count=Count(
                "decisions__health_check",
                filter=Q(decisions__health_check__overall_status=HealthStatus.WARNING),
                distinct=True,
            ),
            health_error_count=Count(
                "decisions__health_check",
                filter=Q(decisions__health_check__overall_status=HealthStatus.ERROR),
                distinct=True,
            ),
            unknown_count=Count(
                "decisions__health_check",
                filter=Q(decisions__health_check__overall_status=HealthStatus.UNKNOWN),
                distinct=True,
            ),
        )

    def entity_name(self, obj):
        if obj.organization:
            return f"Org: {obj.organization.label}"
        elif obj.signer:
            return f"Signer: {obj.signer}"
        return "All"
    entity_name.short_description = "Entity"

    def decisions_count(self, obj):
        return getattr(obj, "decisions_count", 0)
    decisions_count.short_description = "Decisions"
    decisions_count.admin_order_field = "decisions_count"

    def no_health_check_count(self, obj):
        total = getattr(obj, "decisions_count", 0) or 0
        checks = getattr(obj, "health_checks_count", 0) or 0
        missing = total - checks
        return missing if missing >= 0 else 0
    no_health_check_count.short_description = "No health check"

    def no_health_check_link(self, obj):
        missing = self.no_health_check_count(obj)
        if missing <= 0:
            return "-"

        base_url = reverse(f"{self.admin_site.name}:core_decision_changelist")
        query = urlencode(
            {
                "import_job__id__exact": obj.id,
                "health_check__isnull": "1",
            }
        )
        url = f"{base_url}?{query}"
        return format_html('<a href="{}">View {}</a>', url, missing)
    no_health_check_link.short_description = "Missing"

    def healthy_count(self, obj):
        return getattr(obj, "healthy_count", 0)
    healthy_count.short_description = "Healthy"
    healthy_count.admin_order_field = "healthy_count"

    def warning_count(self, obj):
        return getattr(obj, "warning_count", 0)
    warning_count.short_description = "Warnings"
    warning_count.admin_order_field = "warning_count"

    def health_error_count(self, obj):
        return getattr(obj, "health_error_count", 0)
    health_error_count.short_description = "Errors"
    health_error_count.admin_order_field = "health_error_count"

    def unknown_count(self, obj):
        return getattr(obj, "unknown_count", 0)
    unknown_count.short_description = "Unknown"
    unknown_count.admin_order_field = "unknown_count"

    def health_percentage(self, obj):
        total = getattr(obj, "decisions_count", 0) or 0
        healthy = getattr(obj, "healthy_count", 0) or 0
        if total <= 0:
            return "-"
        pct = (healthy / total) * 100
        return f"{pct:.1f}%"
    health_percentage.short_description = "Health %"

    def chunk_progress_display(self, obj):
        """Display chunk processing progress"""
        if obj.total_chunks == 0:
            return "-"
        completed = obj.chunks_completed + obj.chunks_failed
        return f"{completed}/{obj.total_chunks}"
    chunk_progress_display.short_description = 'Chunks'

    def failed_health_checks_link(self, obj):
        errors = getattr(obj, "health_error_count", 0) or 0
        if errors <= 0:
            return "-"

        base_url = reverse(f"{self.admin_site.name}:core_decisionhealthcheck_changelist")
        query = urlencode(
            {
                "decision__import_job__id__exact": obj.id,
                "overall_status__exact": HealthStatus.ERROR,
            }
        )
        url = f"{base_url}?{query}"
        return format_html('<a href="{}">View {} failed</a>', url, errors)
    failed_health_checks_link.short_description = "Failures"

    def warning_health_checks_link(self, obj):
        warnings = getattr(obj, "warning_count", 0) or 0
        if warnings <= 0:
            return "-"

        base_url = reverse(f"{self.admin_site.name}:core_decisionhealthcheck_changelist")
        query = urlencode(
            {
                "decision__import_job__id__exact": obj.id,
                "overall_status__exact": HealthStatus.WARNING,
            }
        )
        url = f"{base_url}?{query}"
        return format_html('<a href="{}">View {} warnings</a>', url, warnings)
    warning_health_checks_link.short_description = "Warnings"

    def download_batch_health_report(self, request, queryset):
        """Download orchestrator-derived batch health report as JSON."""
        if queryset.count() != 1:
            messages.error(request, "Select exactly one ImportJob to download a report.")
            return

        job = queryset.first()
        orchestrator = DecisionPipelineOrchestrator()
        report = orchestrator.get_batch_health_report(import_job_id=job.id, include_failures=True)

        payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        filename = f"import-job-{job.id}-health-report.json"
        response = HttpResponse(payload, content_type="application/json; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    download_batch_health_report.short_description = "Download batch health report (JSON)"

    def enqueue_backfill_missing_health_checks(self, request, queryset):
        """Enqueue a Celery job to create missing DecisionHealthCheck records for this batch."""
        if queryset.count() != 1:
            messages.error(request, "Select exactly one ImportJob to backfill health checks.")
            return

        job = queryset.first()
        async_result = backfill_health_checks_for_import_job.delay(import_job_id=job.id)
        messages.success(
            request,
            f"Queued backfill of missing health checks for ImportJob #{job.id}. "
            f"Task id: {async_result.id}",
        )

    enqueue_backfill_missing_health_checks.short_description = "Backfill missing health checks (async)"

    def enqueue_retry_failed_decisions(self, request, queryset):
        """Enqueue a Celery job to retry all ERROR health checks in this batch."""
        if queryset.count() != 1:
            messages.error(request, "Select exactly one ImportJob to retry failed decisions.")
            return

        job = queryset.first()
        async_result = retry_failed_decisions_for_import_job.delay(
            import_job_id=job.id,
            component=None,  # Retry all components
            max_workers=5
        )
        messages.success(
            request,
            f"Queued retry of failed decisions for ImportJob #{job.id}. "
            f"Task id: {async_result.id}",
        )

    enqueue_retry_failed_decisions.short_description = "Retry ERROR decisions (async)"
