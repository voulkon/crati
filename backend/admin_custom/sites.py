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
            path("analytics/", self._wrap_view('analytics_views', 'redis_analytics'), name="redis_analytics"),
            path("analytics/export/", self._wrap_view('analytics_views', 'export_redis_analytics'), name="export_analytics"),
            path("analytics/patterns/", self._wrap_view('analytics_views', 'pattern_analysis'), name="pattern_analysis"),
            path("analytics/endpoints/", self._wrap_view('analytics_views', 'endpoint_deep_dive'), name="endpoint_deep_dive"),
            
            # Decision URLs
            path("decisions/coverage/", self._wrap_view('decision_views', 'coverage_explorer'), name="coverage_explorer"),
            path("decisions/entity-search/", self._wrap_view('decision_views', 'entity_search'), name="entity_search"),
            path("decisions/daily-analysis/", self._wrap_view('decision_views', 'daily_decision_analysis'), name="daily_decision_analysis"),
            path("decisions/analysis-api/", self._wrap_view('decision_views', 'decision_analysis_api'), name="decision_analysis_api"),
            path("decisions/fetch-daily/", self._wrap_view('decision_views', 'fetch_daily_decisions'), name="fetch_daily_decisions"),
            
            # Organization URLs
            path("organizations/network/", self._wrap_view('organization_views', 'organization_network'), name="organization_network"),
            path("organizations/chart/", self._wrap_view('organization_views', 'organization_org_chart'), name="organization_chart"),
            
            # Document URLs
            path("documents/search/", self._wrap_view('document_views', 'document_search'), name="document_search"),
            path("documents/dashboard/", self._wrap_view('document_views', 'document_processing_dashboard'), name="document_dashboard"),
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
                {"name": "Export Analytics", "object_name": "ExportAnalytics", "admin_url": "/api/admin/analytics/export/", "view_only": True},
                {"name": "Pattern Analysis", "object_name": "PatternAnalysis", "admin_url": "/api/admin/analytics/patterns/", "view_only": True},
                {"name": "Endpoint Deep Dive", "object_name": "EndpointDeepDive", "admin_url": "/api/admin/analytics/endpoints/", "view_only": True},
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
            ],
        }
        app_list.append(doc_processing_app)

        return app_list


# Create singleton instance
admin_site = CustomAdminSite(name='custom_admin')
