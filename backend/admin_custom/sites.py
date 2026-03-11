from django.contrib import admin
from django.urls import path


class CustomAdminSite(admin.AdminSite):
    site_header = "Crati Administration"
    site_title = "Crati Admin"
    index_title = "Welcome to Crati Administration"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # Analytics URLs
            path("analytics/", self._wrap_view('analytics', 'redis_analytics'), name="redis_analytics"),
            path("analytics/export/", self._wrap_view('analytics', 'export_redis_analytics'), name="export_analytics"),
            path("analytics/endpoints/", self._wrap_view('analytics', 'endpoint_deep_dive'), name="endpoint_deep_dive"),
            
            # Decision URLs
            path("decisions/coverage/", self._wrap_view('decisions', 'coverage_explorer'), name="coverage_explorer"),
            path("decisions/entity-search/", self._wrap_view('decisions', 'entity_search'), name="entity_search"),
            path("decisions/daily-analysis/", self._wrap_view('decisions', 'daily_decision_analysis'), name="daily_decision_analysis"),
            path("decisions/analysis-api/", self._wrap_view('decisions', 'decision_analysis_api'), name="decision_analysis_api"),
            path("decisions/fetch-daily/", self._wrap_view('decisions', 'fetch_daily_decisions'), name="fetch_daily_decisions"),
            
            # Organization URLs
            path("organizations/network/", self._wrap_view('organization', 'organization_network'), name="organization_network"),
            path("organizations/chart/", self._wrap_view('organization', 'organization_org_chart'), name="organization_chart"),
            
            # Document URLs
            path("documents/search/", self._wrap_view('documents', 'document_search'), name="document_search"),
            path("documents/dashboard/", self._wrap_view('documents', 'document_processing_dashboard'), name="document_dashboard"),
            path("documents/sync-status/", self._wrap_view('documents', 'sync_status_dashboard'), name="sync_status_dashboard"),
            
            # Health Check URLs
            path("health/dashboard/", self._wrap_view('health', 'health_dashboard_view'), name="health_dashboard"),
            path("health/quick-check/", self._wrap_view('health', 'quick_health_check_view'), name="quick_health_check"),
            path("health/bulk-check/", self._wrap_view('health', 'bulk_check_view'), name="bulk_health_check"),
            path("health/<int:pk>/", self._wrap_view('health', 'health_check_detail_view'), name="health_check_detail"),
            path("health/<int:pk>/refresh/", self._wrap_view('health', 'refresh_single_check'), name="health_refresh_single"),
            path("health/<int:pk>/fix-entities/", self._wrap_view('health', 'fix_entity_data'), name="health_fix_entities"),
            path("health/<int:pk>/retry-extraction/", self._wrap_view('health', 'retry_document_extraction'), name="health_retry_extraction"),
            path("health/<int:pk>/reindex/", self._wrap_view('health', 'reindex_opensearch'), name="health_reindex"),
            path("health/<int:pk>/reextract-entities/", self._wrap_view('health', 'reextract_entities'), name="health_reextract_entities"),
            path("health/<int:pk>/relink-relations/", self._wrap_view('health', 'relink_relations'), name="health_relink_relations"),
            path("health/<int:pk>/update-coverage/", self._wrap_view('health', 'update_coverage'), name="health_update_coverage"),
            
            # AI Job URLs
            path("jobs/<int:job_id>/estimate/", self._wrap_view('ai_jobs', 'estimate_job_cost_view'), name="estimate_job_cost"),
        ]
        return custom_urls + urls
    
    def _wrap_view(self, module_name, view_name):
        """Lazy import and wrap view to avoid circular imports"""
        def view_wrapper(request, *args, **kwargs):
            from importlib import import_module
            module = import_module(f'admin_custom.views.{module_name}')
            view = getattr(module, view_name)
            return view(request, *args, **kwargs)
        return self.admin_view(view_wrapper)

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)

        # Add custom Analytics section
        analytics_app = {
            "name": "Analytics & Monitoring",
            "app_label": "analytics",
            "models": [
                {"name": "Redis Analytics", "object_name": "RedisAnalytics", "admin_url": "/api/admin/analytics/", "view_only": True},
                {"name": "Export Analytics", "object_name": "ExportAnalytics", "admin_url": "/api/admin/analytics/export/", "view_only": True}
            ],
        }
        app_list.append(analytics_app)

        # Add custom Decision Management section
        decision_mgmt_app = {
            "name": "Decision Management",
            "app_label": "decision_management",
            "models": [
                {"name": "Coverage Explorer", "object_name": "CoverageExplorer", "admin_url": "/api/admin/decisions/coverage/", "view_only": True},
                {"name": "Daily Decision Analysis", "object_name": "DailyDecisionAnalysis", "admin_url": "/api/admin/decisions/daily-analysis/", "view_only": True},
                {"name": "Entity Search", "object_name": "EntitySearch", "admin_url": "/api/admin/decisions/entity-search/", "view_only": True},
            ],
        }
        app_list.append(decision_mgmt_app)

        # Add custom Organization Tools section
        org_tools_app = {
            "name": "Organization Tools",
            "app_label": "organization_tools",
            "models": [
                {"name": "Organization Network", "object_name": "OrganizationNetwork", "admin_url": "/api/admin/organizations/network/", "view_only": True},
                {"name": "Organization Chart", "object_name": "OrganizationChart", "admin_url": "/api/admin/organizations/chart/", "view_only": True},
            ],
        }
        app_list.append(org_tools_app)

        # Add custom Document Processing section
        doc_processing_app = {
            "name": "Document Processing",
            "app_label": "document_processing",
            "models": [
                {"name": "Document Search", "object_name": "DocumentSearch", "admin_url": "/api/admin/documents/search/", "view_only": True},
                {"name": "Processing Dashboard", "object_name": "DocumentDashboard", "admin_url": "/api/admin/documents/dashboard/", "view_only": True},
                {"name": "Sync Status Dashboard", "object_name": "SyncStatusDashboard", "admin_url": "/api/admin/documents/sync-status/", "view_only": True},
            ],
        }
        app_list.append(doc_processing_app)

        # Add custom Health Check section
        health_app = {
            "name": "Health & Diagnostics",
            "app_label": "health",
            "models": [
                {"name": "Quick Health Check", "object_name": "QuickHealthCheck", "admin_url": "/api/admin/health/quick-check/", "view_only": True},
                {"name": "Health Dashboard", "object_name": "HealthDashboard", "admin_url": "/api/admin/health/dashboard/", "view_only": True},
                {"name": "Bulk Health Check", "object_name": "BulkHealthCheck", "admin_url": "/api/admin/health/bulk-check/", "view_only": True},
            ],
        }
        app_list.append(health_app)

        return app_list


# Create singleton instance
admin_site = CustomAdminSite(name='custom_admin')


# Register all models with the custom admin site
def register_all_models():
    """Register all models with the custom admin site"""
    from admin_custom.admin_classes import (
        DecisionAdmin, AttachmentAdmin, OrganizationAdmin, UnitAdmin, SignerAdmin,
        DocumentExtractionAdmin, DocumentAnalysisAdmin, DocumentEmbeddingAdmin,
        DecisionHealthCheckAdmin, DecisionHealthSummaryAdmin,
        APIAnalyticsAdmin, EndpointStatsAdmin, DailyTrafficAdmin, ImportJobAdmin,
        CustomUserAdmin, SubscriptionAdmin, BackupAdmin,
        AIModelPricingAdmin, TaskOutputEstimateAdmin, AIJobDefinitionAdmin, AIJobExecutionAdmin,
        ImportThresholdAdmin,
        NotificationSubscriptionAdmin, NotificationAdmin,
        NotificationBatchAdmin, NotificationBatchDecisionAdmin
    )
    
    from core.models.decisions import Decision, Attachment
    from core.models.organizations import Organization, Unit, Signer
    from core.models.document_analysis import DocumentExtraction, DocumentAnalysis, DocumentEmbedding
    from core.models.ai_pricing import AIModelPricing, TaskOutputEstimate, AIJobDefinition, AIJobExecution
    from core.models.decision_health import DecisionHealthCheck, DecisionHealthSummary
    from core.models.import_jobs import ImportJob, DateCoverage
    from core.models.import_thresholds import ImportThreshold
    from core.models.backups import Backup
    from api.models import APIAnalytics, EndpointStats, DailyTraffic
    from users.models import CustomUser, Subscription
    from notifications.models import NotificationSubscription, Notification, NotificationBatch, NotificationBatchDecision
    
    # Register Decision models
    admin_site.register(Decision, DecisionAdmin)
    admin_site.register(Attachment, AttachmentAdmin)
    admin_site.register(Organization, OrganizationAdmin)
    admin_site.register(Unit, UnitAdmin)
    admin_site.register(Signer, SignerAdmin)
    
    # Register Document models
    admin_site.register(DocumentExtraction, DocumentExtractionAdmin)
    admin_site.register(DocumentAnalysis, DocumentAnalysisAdmin)
    admin_site.register(DocumentEmbedding, DocumentEmbeddingAdmin)
    
    # Register AI Pricing models
    admin_site.register(AIModelPricing, AIModelPricingAdmin)
    admin_site.register(TaskOutputEstimate, TaskOutputEstimateAdmin)
    admin_site.register(AIJobDefinition, AIJobDefinitionAdmin)
    admin_site.register(AIJobExecution, AIJobExecutionAdmin)
    
    # Register Health models
    admin_site.register(DecisionHealthCheck, DecisionHealthCheckAdmin)
    admin_site.register(DecisionHealthSummary, DecisionHealthSummaryAdmin)
    
    # Register Analytics models
    admin_site.register(APIAnalytics, APIAnalyticsAdmin)
    admin_site.register(EndpointStats, EndpointStatsAdmin)
    admin_site.register(DailyTraffic, DailyTrafficAdmin)
    admin_site.register(ImportJob, ImportJobAdmin)
    admin_site.register(DateCoverage)
    
    # Register User models
    admin_site.register(CustomUser, CustomUserAdmin)
    admin_site.register(Subscription, SubscriptionAdmin)

    # Register Backup models
    admin_site.register(Backup, BackupAdmin)
    
    # Register Import Validation models
    admin_site.register(ImportThreshold, ImportThresholdAdmin)
    
    # Register Notification models
    admin_site.register(NotificationSubscription, NotificationSubscriptionAdmin)
    admin_site.register(Notification, NotificationAdmin)
    admin_site.register(NotificationBatch, NotificationBatchAdmin)
    admin_site.register(NotificationBatchDecision, NotificationBatchDecisionAdmin)


# Auto-register models when module is imported
register_all_models()

