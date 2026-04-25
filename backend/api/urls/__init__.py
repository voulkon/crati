"""
Main API URL Configuration

This module organizes API URLs into logical groups for better maintainability.
Each group is in its own file under the api/urls/ directory.

URL Structure:
- /api/auth/* - Authentication endpoints (exempt from stealth mode)
- /api/search/* - Search endpoints
- /api/entity/* - Entity analytics
- /api/explore/* - Temporal exploration
- /api/notifications/* - Notification subscriptions and batches
- /api/decisions/* - Decision details
- /api/companies/* - Company information
- /api/organizations/* - Organization information
- /api/direct-assignments/* - Direct assignment analytics
- /api/system/* - System configuration
- /api/tasks/* - Background task management
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import views
from api.custom_views.document_processing import ProcessDocumentsView
from api.custom_views.import_decisions import calendar_bulk_import
from api.custom_views.task_status import TaskStatusView
from api.views.organization_views import organization_chart_api, organization_chart_api_dev
from api.views import search, decisions as decisions_views, entities as entities_views, system as system_views
from api.views.companies.details import company_detail, company_decisions, company_decision_stats
from api.views.summary import amounts as summary_amounts_views
from api.views.organy import details as details_between_companies_and_orgs
from api.views.tracing_test_views import tracing_test_views
from api.views.organization_entity_relationships import (
    organization_top_counterparts_api, 
    entity_top_organizations_api,
)
from api.views.direct_assignments import (
    organization_direct_assignment_top_recipients,
    entity_direct_assignment_top_organizations,
    direct_assignment_top_pairs_global,
    direct_assignment_top_entities_global,
    direct_assignment_top_organizations_global,
    direct_assignment_stats
)
from users.views import UserDataViewSet

# Create router for user data
router = DefaultRouter()
router.register('user-data', UserDataViewSet, basename='user-data')

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Authentication endpoints (all under /api/auth/ - exempt from stealth mode)
    path('auth/', include('api.urls.auth')),
    
    # Notification endpoints (all under /api/notifications/)
    path('notifications/', include('api.urls.notifications')),
    
    # Search endpoints (all under /api/search/)
    path('search/', include('api.urls.search')),
    
    # Entity analytics (all under /api/entity/)
    path('entity/', include('api.urls.entities')),
    
    # Temporal exploration (all under /api/explore/)
    path('explore/', include('api.urls.explore')),
    
    # System configuration
    path('system/config/', system_views.system_config, name='system_config'),
    path('system/config/auth/', system_views.auth_config, name='auth_config'),
    
    # Background tasks
    path('tasks/process/', ProcessDocumentsView.as_view(), name='process-documents'),
    path('tasks/import-decisions/', calendar_bulk_import, name='admin_import_decisions'),
    path('tasks/status/<str:task_id>/', TaskStatusView.as_view(), name='task-status'),
    
    # Organization chart
    path('org-chart-api/', organization_chart_api, name='org-chart-api'),
    path('org-chart-api-dev/', organization_chart_api_dev, name='org-chart-api-dev'),
    
    # Document content
    path('decision/<int:decision_id>/content/', search.get_document_content_api_dev, name='decision_content_dev'),
    
    # Decision detail endpoints
    path('decisions/<int:decision_id>/', decisions_views.decision_detail, name='decision_detail'),
    path('decisions/<int:decision_id>/entities/', decisions_views.decision_entities, name='decision_entities'),
    path('decisions/<int:decision_id>/related/', decisions_views.decision_related, name='decision_related'),
    path('decisions/<int:decision_id>/companies/', decisions_views.decision_companies, name='decision-companies'),
    
    # Entity endpoints
    path('entity/afm/<str:afm>/', entities_views.afm_entity_detail, name='afm_entity_detail'),
    path('entity/afm/<str:afm>/decisions/', entities_views.afm_entity_decisions, name='afm_entity_decisions'),
    
    # Company endpoints
    path('companies/<int:company_id>/', company_detail, name='company-detail'),
    path('companies/<int:company_id>/decisions/', company_decisions, name='company-decisions'),
    path('companies/<int:company_id>/stats/', company_decision_stats, name='company-decision-stats'),
    path('companies/<str:afm>/transactions/', summary_amounts_views.company_transactions_summary, name='company-transactions'),
    
    # Organization endpoints
    path('organizations/<str:organization_uid>/expenditures/', summary_amounts_views.organization_expenditures_summary, name='organization-expenditures'),
    path('organizations/<str:organization_uid>/transactions/', details_between_companies_and_orgs.organization_entity_transactions, name='organization-transactions'),
    path('organizations/<str:organization_uid>/transactions/<str:afm>/', details_between_companies_and_orgs.organization_entity_transactions, name='organization-entity-transactions'),
    path('organizations/<str:organization_uid>/top-counterparts/', organization_top_counterparts_api, name='organization_top_counterparts'),
    path('organizations/<str:organization_uid>/direct-assignments/top-recipients/', organization_direct_assignment_top_recipients, name='org_direct_assignment_top_recipients'),
    
    # Entity relationship endpoints
    path('entities/<str:afm>/top-organizations/', entity_top_organizations_api, name='entity_top_organizations'),
    path('entities/<str:afm>/direct-assignments/top-organizations/', entity_direct_assignment_top_organizations, name='entity_direct_assignment_top_orgs'),
    
    # Direct assignment analytics (global)
    path('direct-assignments/stats/', direct_assignment_stats, name='direct_assignments_stats'),
    path('direct-assignments/top-entities/', direct_assignment_top_entities_global, name='direct_assignment_top_entities_global'),
    path('direct-assignments/top-organizations/', direct_assignment_top_organizations_global, name='direct_assignment_top_organizations_global'),
    path('direct-assignments/top-pairs/', direct_assignment_top_pairs_global, name='direct_assignment_top_pairs_global'),
    
    # Transaction summaries
    path('transactions/top/', summary_amounts_views.top_transactions, name='top-transactions'),
    
    # Debug/tracing endpoints (consider removing in production)
    path('debug-tracing/test-tracing/', tracing_test_views.test_tracing, name='test-tracing'),
    path('debug-tracing/test-tracing-verbose/', tracing_test_views.test_tracing_verbose, name='test-tracing-verbose'),
    path('debug-tracing/force-export/', tracing_test_views.force_trace_export, name='force-export'),
    path('debug-tracing/environment/', tracing_test_views.debug_environment, name='debug-environment'),
    path('debug-tracing/test-celery/', tracing_test_views.test_celery_tracing, name='test-celery'),
    path('debug-tracing/test-simple-task/', tracing_test_views.test_simple_task, name='test-simple-task'),
    path('debug-tracing/test-error/', tracing_test_views.test_error_tracing, name='test-error'),
    path('debug-tracing/test-nested/', tracing_test_views.test_nested_tracing, name='test-nested'),
]
