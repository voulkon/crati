"""
Search-related URL patterns.
"""

from django.urls import path

# URL prefix for this module
PREFIX = 'search/'
from api.views import search

urlpatterns = [
    # Basic search endpoints
    path('', search.universal_search_api, name='universal_search'),
    path('dev/', search.universal_search_api_dev, name='universal_search_dev'),
    path('entities-fast/', search.entities_fast_search_api, name='entities_fast_search'),
    path('stream/', search.search_stream_api, name='search_stream'),
    path('autocomplete/', search.autocomplete_suggestions_api, name='autocomplete_suggestions'),
    path('suggestions/', search.default_suggestions_api, name='default_suggestions'),
    path('super/', search.super_search_api, name='super_search'),
    path('org-signer/', search.org_signer_search_api, name='org_signer_search'),
    path('org-signer-unit/', search.org_signer_unit_search_api, name='org_signer_unit_search'),
    path('organization/', search.organization_only_search_api, name='organization_search'),
    path('signer/', search.signer_only_search_api, name='signer_search'),
    path('company/', search.company_only_search_api, name='company_search'),
    path('company-person/', search.company_person_only_search_api, name='company_person_search'),
    path('company-all/', search.company_and_persons_search_api, name='company_and_persons_search'),
    
    # Document search
    path('documents/', search.document_search_api, name='document_search'),
    path('documents-dev/', search.document_search_api_dev, name='document_search_dev'),
]
