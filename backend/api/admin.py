from django.contrib import admin
from .models import APIAnalytics, DailyTraffic, EndpointStats
from django.urls import path
from . import admin_views
from core.admin import DecisionAdmin
from users.models import CustomUser, Subscription
from users.admin import CustomUserAdmin, SubscriptionAdmin, DocumentExtractionAdmin
from core.models.decisions import Decision, Attachment
from core.models.organizations import Organization, Unit, Signer
from core.models.import_jobs import ImportJob, DateCoverage
from core import admin_views as core_admin_views
from core.models.document_analysis import (
    DocumentExtraction,
    DocumentAnalysis,
    DocumentEmbedding,
)


class CustomAdminSite(admin.AdminSite):

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("analytics/", admin_views.redis_analytics, name="redis_analytics"),
            path(
                "analytics/export/",
                admin_views.export_redis_analytics,
                name="export_analytics",
            ),
            path(
                "analytics/patterns/",
                admin_views.pattern_analysis,
                name="pattern_analysis",
            ),
            path(
                "analytics/endpoints/",
                admin_views.endpoint_deep_dive,
                name="endpoint_deep_dive",
            ),
            path(
                "decisions/coverage/",
                core_admin_views.coverage_explorer,
                name="coverage_explorer",
            ),
            path(
                "decisions/entity-search/",
                core_admin_views.entity_search,
                name="entity_search",
            ),
            path(
                "decisions/daily-analysis/",
                core_admin_views.daily_decision_analysis,
                name="daily_decision_analysis",
            ),
            path(
                "decisions/analysis-api/",
                core_admin_views.decision_analysis_api,
                name="decision_analysis_api",
            ),
            path(
                "decisions/fetch-daily/",
                core_admin_views.fetch_daily_decisions,
                name="fetch_daily_decisions",
            ),
            path(
                "organizations/network/",
                core_admin_views.organization_network,
                name="organization_network",
            ),
            path(
                "organizations/chart/",
                core_admin_views.organization_org_chart,
                name="organization_chart",
            ),
            path(
                "documents/search/",
                core_admin_views.document_search,
                name="document_search",
            ),
            path(
                "documents/dashboard/",
                core_admin_views.document_processing_dashboard,
                name="document_dashboard",
            ),
        ]
        return custom_urls + urls

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)

        # Add custom section for analytics
        analytics_app = {
            "name": "Analytics",
            "app_label": "analytics",
            "models": [
                {
                    "name": "Redis Analytics",
                    "object_name": "RedisAnalytics",
                    "admin_url": "/admin/analytics/",
                    "view_only": True,
                },
                {
                    "name": "Export Analytics",
                    "object_name": "ExportAnalytics",
                    "admin_url": "/admin/analytics/export/",
                    "view_only": True,
                },
                {
                    "name": "Pattern Analysis (51/12 Investigation)",
                    "object_name": "PatternAnalysis",
                    "admin_url": "/api/admin/analytics/patterns/",
                    "view_only": True,
                },
                {
                    "name": "Endpoint Deep Dive",
                    "object_name": "EndpointDeepDive",
                    "admin_url": "/api/admin/analytics/endpoints/",
                    "view_only": True,
                },
                {
                    "name": "Organization Network",
                    "object_name": "OrganizationNetwork",
                    "admin_url": "/api/admin/organizations/network/",
                    "view_only": True,
                },
                {
                    "name": "Organization Chart",
                    "object_name": "OrganizationChart",
                    "admin_url": "/api/admin/organizations/chart/",
                    "view_only": True,
                },
                {
                    "name": "Document Search",
                    "object_name": "DocumentSearch",
                    "admin_url": "/api/admin/documents/search/",
                    "view_only": True,
                },
                {
                    "name": "Processing Dashboard",
                    "object_name": "DocumentDashboard",
                    "admin_url": "/api/admin/documents/dashboard/",
                    "view_only": True,
                },
            ],
        }

        app_list.append(analytics_app)

        decision_mgmt_app = {
            "name": "Decision Management",
            "app_label": "decision_management",
            "models": [
                {
                    "name": "Coverage Explorer",
                    "object_name": "CoverageExplorer",
                    "admin_url": "/api/admin/decisions/coverage/",
                    "view_only": True,
                },
                {
                    "name": "Daily Decision Analysis",
                    "object_name": "DailyDecisionAnalysis",
                    "admin_url": "/api/admin/decisions/daily-analysis/",
                    "view_only": True,
                },
                {
                    "name": "Import Decisions",
                    "object_name": "ImportDecisions",
                    "admin_url": "/api/admin/decisions/import/",
                    "view_only": True,
                },
            ],
        }
        app_list.append(decision_mgmt_app)

        return app_list


class APIAnalyticsAdmin(admin.ModelAdmin):
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
        # Identify the 51/12 pattern and other suspicious patterns
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
    list_display = ("endpoint", "count")


class DailyTrafficAdmin(admin.ModelAdmin):
    list_display = ("date", "count")
    date_hierarchy = "date"


class ImportJobAdmin(admin.ModelAdmin):
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


admin_site = CustomAdminSite()

admin_site.register(APIAnalytics, APIAnalyticsAdmin)
admin_site.register(EndpointStats, EndpointStatsAdmin)
admin_site.register(DailyTraffic, DailyTrafficAdmin)
admin_site.register(Decision, DecisionAdmin)
admin_site.register(Attachment)
admin_site.register(Organization)
admin_site.register(Unit)
admin_site.register(Signer)
admin_site.register(CustomUser, CustomUserAdmin)
admin_site.register(Subscription, SubscriptionAdmin)
admin_site.register(ImportJob, ImportJobAdmin)
admin_site.register(DateCoverage)
admin_site.register(DocumentExtraction, DocumentExtractionAdmin)
admin_site.register(DocumentAnalysis)
admin_site.register(DocumentEmbedding)
