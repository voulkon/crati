from django.contrib import admin
from django.db.models import Count
from api.models import APIAnalytics, DailyTraffic, EndpointStats


class APIAnalyticsAdmin(admin.ModelAdmin):
    """Admin interface for API Analytics"""
    
    list_display = (
        "timestamp",
        "total_requests",
        "unique_ips",
        "endpoint_count",
        "avg_requests_per_ip",
        "pattern_analysis",
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

    def pattern_analysis(self, obj):
        """Identify the 51/12 pattern and other suspicious patterns"""
        if obj.total_requests == 51 and obj.unique_ips == 12:
            return "🔍 51/12 PATTERN"
        elif obj.total_requests == obj.unique_ips:
            return "⚠️ 1:1 RATIO"
        elif obj.total_requests % obj.unique_ips == 0:
            ratio = obj.total_requests // obj.unique_ips
            return f"📊 EXACT {ratio}:1"
        return "✅ Normal"
    pattern_analysis.short_description = "Pattern"
    pattern_analysis.admin_order_field = "total_requests"

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
    """Admin interface for Import Jobs"""
    list_display = (
        "id",
        "start_date",
        "end_date",
        "entity_name",
        "status",
        "created_by",
        "created_at",
        "total_decisions",
    )
    list_filter = ("status", "created_by", "created_at")
    search_fields = ("organization__label", "signer__label")
    date_hierarchy = "created_at"

    def entity_name(self, obj):
        if obj.organization:
            return f"Org: {obj.organization.label}"
        elif obj.signer:
            return f"Signer: {obj.signer.label}"
        return "All"
    entity_name.short_description = "Entity"
