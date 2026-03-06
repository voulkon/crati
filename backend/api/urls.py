from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .simple_views import public_endpoint, protected_endpoint, check_api_usage
from .custom_views.document_processing import ProcessDocumentsView
from .custom_views.import_decisions import calendar_bulk_import
from .custom_views.task_status import TaskStatusView
from .admin_views import redis_analytics, export_redis_analytics
from .views.organization_views import organization_chart_api, organization_chart_api_dev
from .views import search
from .views import decisions as decisions_views
from .views import entities as entities_views
from .views import system as system_views
from .views.companies.details import company_detail, company_decisions, company_decision_stats
from .views.summary import amounts as summary_amounts_views
from .views.organy import details as details_between_companies_and_orgs
from .views.tracing_test_views import tracing_test_views
from .views.organization_entity_relationships import (
    organization_top_counterparts_api, 
    entity_top_organizations_api, 
    temporal_top_relationship_pairs_api
    )
from users.views import UserDataViewSet
from .auth_views import django_login, django_logout, current_user
from notifications.views import NotificationSubscriptionViewSet, NotificationViewSet

router = DefaultRouter()
# Register viewsets
router.register('user-data', UserDataViewSet, basename='user-data')
router.register('notifications/subscriptions', NotificationSubscriptionViewSet, basename='notification-subscription')
router.register('notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path("", include(router.urls)),
    path("public/", public_endpoint, name="public"),
    path("protected/", protected_endpoint, name="protected"),
    path("usage/", check_api_usage, name="check_api_usage"),
    
    # Django authentication endpoints (for when Clerk is not configured)
    path("auth/login/", django_login, name="django_login"),
    path("auth/logout/", django_logout, name="django_logout"),
    path("auth/me/", current_user, name="current_user"),
    
    # System configuration
    path("system/config/", system_views.system_config, name="system_config"),
    
    path('tasks/process/', ProcessDocumentsView.as_view(), name='process-documents'),
    path('tasks/import-decisions/', calendar_bulk_import, name='admin_import_decisions'),
    path('tasks/status/<str:task_id>/', TaskStatusView.as_view(), name='task-status'),

    path('org-chart-api/', organization_chart_api, name='org-chart-api'),
    path('org-chart-api-dev/', organization_chart_api_dev, name='org-chart-api-dev'),

    # Basic search endpoints
    path('search/', search.universal_search_api, name='universal_search'),
    path('search-dev/', search.universal_search_api_dev, name='universal_search_dev'),
    path('search/entities-fast/', search.entities_fast_search_api, name='entities_fast_search'),  # Fast entity-only search
    path('search/stream/', search.search_stream_api, name='search_stream'),  # SSE streaming endpoint
    path('search/autocomplete/', search.autocomplete_suggestions_api, name='autocomplete_suggestions'),
    path('search/super/', search.super_search_api, name='super_search'),
    path('search/org-signer/', search.org_signer_search_api, name='org_signer_search'),
    path('search/org-signer-unit/', search.org_signer_unit_search_api, name='org_signer_unit_search'),
    path('search/organization/', search.organization_only_search_api, name='organization_search'),
    path('search/signer/', search.signer_only_search_api, name='signer_search'),
    path('search/company/', search.company_only_search_api, name='company_search'),
    path('search/company-person/', search.company_person_only_search_api, name='company_person_search'),
    path('search/company-all/', search.company_and_persons_search_api, name='company_and_persons_search'),

    # Document search
    path('search/documents/', search.document_search_api, name='document_search'),
    path('search/documents-dev/', search.document_search_api_dev, name='document_search_dev'),

    # Entity analytics
    path('entity/<str:entity_type>/<str:entity_id>/statistics/', search.entity_statistics_api_dev, name='entity_statistics_dev'),
    path('entity/<str:entity_type>/<str:entity_id>/decisions/', search.entity_decisions_api_dev, name='entity_decisions_dev'),
    path('entity/<str:entity_type>/<str:entity_id>/documents/', search.entity_search_documents_api_dev, name='entity_documents_dev'),
    path('entity/<str:entity_type>/<str:entity_id>/timeline/', search.entity_timeline_api_dev, name='entity_timeline_dev'),
    path('entity/<str:entity_type>/<str:entity_id>/decision-types/', search.entity_decision_types_api_dev, name='entity_decision_types_dev'),
    path('entity/<str:entity_type>/<str:entity_id>/date-range/', search.entity_date_range_api_dev, name='entity_date_range_dev'),
    
    # Temporal exploration
    path('explore/date-range/', search.explore_date_range_api_dev, name='explore_date_range_dev'),
    path('explore/statistics/', search.explore_statistics_api_dev, name='explore_statistics_dev'),
    path('explore/decisions/', search.explore_decisions_api_dev, name='explore_decisions_dev'),
    path('explore/decision-types/', search.explore_decision_types_api_dev, name='explore_decision_types_dev'),
    path('explore/organizations/', search.explore_organizations_api_dev, name='explore_organizations_dev'),
    
    path('explore/decisions-optimized/', search.explore_decisions_optimized_api, name='explore_decisions_optimized'),
    
    # Organization-Entity Relationships (financial flows)
    path('organizations/<str:organization_uid>/top-counterparts/', 
        organization_top_counterparts_api, 
        name='organization_top_counterparts'
        ),
    path('entities/<str:afm>/top-organizations/', 
        entity_top_organizations_api, 
        name='entity_top_organizations'
        ),
    path(
        'explore/temporal/top-relationships/',
        temporal_top_relationship_pairs_api,
        name='temporal-top-relationships'
    ),
    # Document content
    path('decision/<int:decision_id>/content/', search.get_document_content_api_dev, name='decision_content_dev'),
    
    # Decision detail endpoints (using integer ID)
    path('decisions/<int:decision_id>/', decisions_views.decision_detail, name='decision_detail'),
    path('decisions/<int:decision_id>/entities/', decisions_views.decision_entities, name='decision_entities'),
    path('decisions/<int:decision_id>/related/', decisions_views.decision_related, name='decision_related'),
    path('decisions/<int:decision_id>/companies/', decisions_views.decision_companies, name='decision-companies'),
    
    path('entity/afm/<str:afm>/', entities_views.afm_entity_detail, name='afm_entity_detail'),
    path('entity/afm/<str:afm>/decisions/', entities_views.afm_entity_decisions, name='afm_entity_decisions'),

    path('companies/<int:company_id>/', company_detail, name='company-detail'),
    path('companies/<int:company_id>/decisions/', company_decisions, name='company-decisions'),
    path('companies/<int:company_id>/stats/', company_decision_stats, name='company-decision-stats'),
    path('companies/<str:afm>/transactions/', summary_amounts_views.company_transactions_summary, name='company-transactions'),

    path('organizations/<str:organization_uid>/expenditures/', summary_amounts_views.organization_expenditures_summary, name='organization-expenditures'),
    
    path('transactions/top/', summary_amounts_views.top_transactions, name='top-transactions'),
    
    path('organizations/<str:organization_uid>/transactions/', details_between_companies_and_orgs.organization_entity_transactions, name='organization-transactions'),
    path('organizations/<str:organization_uid>/transactions/<str:afm>/', details_between_companies_and_orgs.organization_entity_transactions, name='organization-entity-transactions'),

    path('debug-tracing/test-tracing/', tracing_test_views.test_tracing, name='test-tracing'),
    path('debug-tracing/test-tracing-verbose/', tracing_test_views.test_tracing_verbose, name='test-tracing-verbose'),
    path('debug-tracing/force-export/', tracing_test_views.force_trace_export, name='force-export'),
    path('debug-tracing/environment/', tracing_test_views.debug_environment, name='debug-environment'),
    path('debug-tracing/test-celery/', tracing_test_views.test_celery_tracing, name='test-celery'),
    path('debug-tracing/test-simple-task/', tracing_test_views.test_simple_task, name='test-simple-task'),
    path('debug-tracing/test-error/', tracing_test_views.test_error_tracing, name='test-error'),
    path('debug-tracing/test-nested/', tracing_test_views.test_nested_tracing, name='test-nested'),

]
