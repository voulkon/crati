from core.services.search_service import SearchService
from api.views.search.entity_search_utils import (
    get_entities_fast, 
    get_documents_slow, 
    get_administrative_terms_autocomplete,
    highlight_query_in_text,
    determine_matched_field
    )
from django.conf import settings
from django.http import StreamingHttpResponse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
import json

def get_search_data_for_api(query, **kwargs):
    """
    Helper function to get search data for API endpoints.
    Extracts common logic used by multiple endpoints.
    """
    search_service = SearchService()
    
    # Extract parameters
    entity_types = kwargs.get('entity_types', ['organization', 'signer', 'unit'])
    organization_id = kwargs.get('organization_id')
    company_id = kwargs.get('company_id')
    limit = kwargs.get('limit', 20)
    include_documents = kwargs.get('include_documents', False)
    
    results = {
        'query': query,
        'results': {},
        'total_count': 0
    }
    
    if not query:
        return results
    
    # Search entities based on requested types
    if 'organization' in entity_types:
        orgs = search_service.search_organizations(query, limit)
        results['results']['organizations'] = [
            {
                'id': org.uid,
                'text': org.label,
                'type': 'organization',
                'title': highlight_query_in_text(org.label, query, 100),
                'subtitle': f"{org.category} • {org.latin_name}",
                'description': f"VAT: {org.vat_number or 'N/A'} • Status: {org.status.title()}",
                'details': {
                    'latin_name': org.latin_name,
                    'category': org.category,
                    'vat_number': org.vat_number,
                    'status': org.status,
                    'website': org.website,
                    'supervisor': org.supervisor_org_name
                },
                'matched_field': determine_matched_field('organization', org, query),
                'icon': 'building'
            }
            for org in orgs
        ]
        results['total_count'] += len(orgs)
    
    if 'signer' in entity_types:
        signers = search_service.search_signers(query, organization_id, limit)
        results['results']['signers'] = [
            {
                'id': signer.uid,
                'text': f"{signer.last_name}, {signer.first_name}",
                'type': 'signer',
                'title': highlight_query_in_text(f"{signer.first_name} {signer.last_name}", query, 100),
                'subtitle': signer.organization.label if signer.organization else 'No organization',
                'description': f"Signer • {'Active' if signer.active else 'Inactive'}",
                'details': {
                    'first_name': signer.first_name,
                    'last_name': signer.last_name,
                    'organization': signer.organization.label if signer.organization else None,
                    'organization_id': signer.organization.uid if signer.organization else None,
                    'active': signer.active,
                    'has_org_sign_rights': signer.has_organization_sign_rights,
                    'active_from': signer.active_from.isoformat() if signer.active_from else None,
                    'active_until': signer.active_until.isoformat() if signer.active_until else None
                },
                'matched_field': determine_matched_field('signer', signer, query),
                'icon': 'user'
            }
            for signer in signers
        ]
        results['total_count'] += len(signers)
    
    if 'unit' in entity_types:
        units = search_service.search_units(query, organization_id, limit)
        results['results']['units'] = [
            {
                'id': unit.uid,
                'text': unit.label,
                'type': 'unit',
                'title': highlight_query_in_text(unit.label, query, 100),
                'subtitle': unit.organization.label if unit.organization else 'No organization',
                'description': f"Unit • {unit.category} • {'Active' if unit.active else 'Inactive'}",
                'details': {
                    'organization': unit.organization.label if unit.organization else None,
                    'organization_id': unit.organization.uid if unit.organization else None,
                    'category': unit.category,
                    'active': unit.active,
                    'active_from': unit.active_from.isoformat() if unit.active_from else None,
                    'active_until': unit.active_until.isoformat() if unit.active_until else None,
                    'parent_unit': unit.parent.label if unit.parent else None
                },
                'matched_field': determine_matched_field('unit', unit, query),
                'icon': 'department'
            }
            for unit in units
        ]
        results['total_count'] += len(units)
    
    if 'company' in entity_types:
        companies = search_service.search_companies(query, limit)
        results['results']['companies'] = [
            {
                'id': company.ar_gemi,
                'text': company.co_name_el or 'No name',
                'type': 'company',
                'title': highlight_query_in_text(company.co_name_el or 'No name', query, 100),
                'subtitle': f"{company.legal_type_name or 'Company'} • {company.municipality_name or 'Unknown location'}",
                'description': f"AFM: {company.afm or 'N/A'} • Status: {company.status_name or 'Unknown'}",
                'details': {
                    'co_name_el': company.co_name_el,
                    'co_names_en': company.co_names_en,
                    'co_titles_el': company.co_titles_el,
                    'co_titles_en': company.co_titles_en,
                    'afm': company.afm,
                    'ar_gemi': company.ar_gemi,
                    'legal_type': company.legal_type_name,
                    'municipality_name': company.municipality_name,
                    'prefecture_name': company.prefecture_name,
                    'status_name': company.status_name,
                    'incorporation_date': company.incorporation_date,
                    'website': company.url,
                    'email': company.email
                },
                'matched_field': determine_matched_field('company', company, query),
                'icon': 'company'
            }
            for company in companies
        ]
        results['total_count'] += len(companies)
    
    if 'company_person' in entity_types:
        company_persons = search_service.search_company_persons(query, company_id, limit)
        results['results']['company_persons'] = [
            {
                'id': person.id,
                'text': person.person_name or person.business_name or 'No name',
                'type': 'company_person',
                'title': highlight_query_in_text(person.person_name or person.business_name or 'No name', query, 100),
                'subtitle': f"{person.role or 'Unknown role'} at {person.company.co_name_el if person.company else 'Unknown company'}",
                'description': f"Company Person • {person.date_from or 'Date unknown'}",
                'details': {
                    'person_name': person.person_name,
                    'business_name': person.business_name,
                    'role': person.role,
                    'company_name': person.company.co_name_el if person.company else None,
                    'company_id': person.company.ar_gemi if person.company else None,
                    'date_from': person.date_from,
                    'date_to': person.date_to,
                    'is_representative_alone': person.is_representative_alone,
                    'is_representative_in_common': person.is_representative_in_common
                },
                'matched_field': determine_matched_field('company_person', person, query),
                'icon': 'user-tie'
            }
            for person in company_persons
        ]
        results['total_count'] += len(company_persons)
    
    if include_documents:
        doc_results = search_service.search_documents(query, limit=limit)
        serialized_docs = []
        for doc in doc_results['results']:
            # Handle both OpenSearch results (dict with 'extraction' key) and PostgreSQL results (DocumentExtraction objects)
            if isinstance(doc, dict) and 'extraction' in doc:
                # OpenSearch result format
                extraction = doc['extraction']
                decision = extraction.decision
                
                # Build a rich document result
                doc_data = {
                    'id': extraction.id,
                    'type': 'document',
                    'title': decision.subject[:100] + ('...' if len(decision.subject) > 100 else '') if decision else 'Untitled Document',
                    'subtitle': f"By {decision.organization.label if decision and decision.organization else 'Unknown Organization'}",
                    'description': doc.get('text_excerpt', 'No preview available'),
                    'details': {
                        'decision_id': decision.id if decision else None,
                        'ada': decision.ada if decision else None,
                        'organization': decision.organization.label if decision and decision.organization else None,
                        'organization_id': decision.organization.uid if decision and decision.organization else None,
                        'decision_type': decision.get_decision_type_label() if decision else None,
                        'issue_date': decision.issue_date.isoformat() if decision and decision.issue_date else None,
                        'amount': str(decision.amount) if decision and decision.amount else None,
                        'currency': decision.currency if decision else None,
                        'status': decision.status if decision else None,
                        'provider': extraction.extraction_provider,
                        'is_scanned': extraction.is_scanned_document,
                        'protocol_number': decision.protocol_number if decision else None,
                        'signers': [f"{s.first_name} {s.last_name}" for s in doc.get('signers', [])]
                    },
                    'search_score': doc.get('search_score', 0),
                    'highlights': doc.get('highlights', {}),
                    'source': 'opensearch',
                    'matched_field': 'content',
                    'icon': 'document'
                }
                serialized_docs.append(doc_data)
            else:
                # PostgreSQL fallback result format (direct DocumentExtraction object)
                extraction = doc['extraction'] if isinstance(doc, dict) else doc
                decision = extraction.decision
                
                doc_data = {
                    'id': extraction.id,
                    'type': 'document',
                    'title': decision.subject[:100] + ('...' if len(decision.subject) > 100 else '') if decision else 'Untitled Document',
                    'subtitle': f"By {decision.organization.label if decision and decision.organization else 'Unknown Organization'}",
                    'description': extraction.raw_text[:300] + ('...' if len(extraction.raw_text or '') > 300 else '') if hasattr(extraction, 'raw_text') and extraction.raw_text else 'No preview available',
                    'details': {
                        'decision_id': decision.id if decision else None,
                        'ada': decision.ada if decision else None,
                        'organization': decision.organization.label if decision and decision.organization else None,
                        'organization_id': decision.organization.uid if decision and decision.organization else None,
                        'decision_type': decision.get_decision_type_label() if decision else None,
                        'issue_date': decision.issue_date.isoformat() if decision and decision.issue_date else None,
                        'amount': str(decision.amount) if decision and decision.amount else None,
                        'currency': decision.currency if decision else None,
                        'status': decision.status if decision else None,
                        'provider': extraction.extraction_provider,
                        'is_scanned': extraction.is_scanned_document,
                        'protocol_number': decision.protocol_number if decision else None,
                        'signers': [f"{s.first_name} {s.last_name}" for s in decision.signers.all()] if decision else []
                    },
                    'search_score': doc.get('search_score', 1.0) if isinstance(doc, dict) else 1.0,
                    'highlights': doc.get('highlights', {}) if isinstance(doc, dict) else {},
                    'source': 'postgresql',
                    'matched_field': 'content',
                    'icon': 'document'
                }
                serialized_docs.append(doc_data)
        
        results['results']['documents'] = serialized_docs
        results['total_count'] += doc_results['count']
    
    return results


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('q', openapi.IN_QUERY, description="Search query", type=openapi.TYPE_STRING, required=True),
        openapi.Parameter('types', openapi.IN_QUERY, description="Comma-separated entity types (organization,signer,unit,company,company_person)", type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('limit', openapi.IN_QUERY, description="Results limit per type", type=openapi.TYPE_INTEGER),
    ]
)
@api_view(['GET'])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def entities_fast_search_api(request):
    """
    Fast entity-only search API
    Returns organizations, signers, units, companies, and company persons quickly
    without including slow document search
    
    Use this for real-time search-as-you-type functionality
    """
    query = request.GET.get('q', '')
    types_param = request.GET.get('types', 'organization,signer,unit,company,company_person')
    limit = int(request.GET.get('limit', 5))
    
    # Parse entity types
    entity_types = [t.strip() for t in types_param.split(',') if t.strip()]
    
    # Use the fast utility function
    results = get_entities_fast(
        query,
        entity_types=entity_types,
        limit=limit
    )
    
    return Response(results)


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('q', openapi.IN_QUERY, description="Search query", type=openapi.TYPE_STRING, required=True),
        openapi.Parameter('include_documents', openapi.IN_QUERY, description="Include document search", type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('limit', openapi.IN_QUERY, description="Results limit per type", type=openapi.TYPE_INTEGER),
    ]
)
@api_view(['GET'])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def search_stream_api(request):
    """
    SSE (Server-Sent Events) streaming search API
    Returns entities first (fast), then documents (slow) incrementally
    
    Usage:
        const eventSource = new EventSource('/api/search/stream/?q=ΔΗΜΟΣ&limit=5');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'entities') { ... }
            if (data.type === 'documents') { ... }
            if (data.type === 'done') { eventSource.close(); }
        };
    """
    query = request.GET.get('q', '')
    include_documents = request.GET.get('include_documents', 'true').lower() == 'true'
    limit = int(request.GET.get('limit', 5))
    
    def event_stream():
        """Generator function that yields SSE-formatted data"""
        try:
            # Phase 1: Fast entity search (organizations, signers, units, companies, company_persons)
            entity_results = get_entities_fast(
                query,
                entity_types=['organization', 'signer', 'unit', 'company', 'company_person'],
                limit=limit
            )
            
            # Send entity results immediately
            yield f"data: {json.dumps(entity_results)}\n\n"
            
            # Phase 2: Slow document search (if requested)
            if include_documents:
                document_results = get_documents_slow(query, limit=limit)
                yield f"data: {json.dumps(document_results)}\n\n"
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done', 'query': query})}\n\n"
            
        except Exception as e:
            # Send error event
            error_data = {
                'type': 'error',
                'message': str(e),
                'query': query
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
    
    return response




@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('q', openapi.IN_QUERY, description="Search query prefix", type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('category', openapi.IN_QUERY, description="Filter by category (organization, company)", type=openapi.TYPE_STRING, required=False),
    ]
)
@api_view(['GET'])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def autocomplete_suggestions_api(request):
    """
    Autocomplete suggestions API
    Returns common Greek administrative terms that match the query
    
    This is designed to help users quickly find organizations by typing
    common prefixes like "ΔΗΜΟΣ", "ΠΕΡΙΦΕΡΕΙΑ", "ΥΠΟΥΡΓΕΙΟ", etc.
    
    Future enhancement: Use analytics to find most common terms in entity names
    """
    query = request.GET.get('q', '').strip().upper()
    category = request.GET.get('category', '').lower()
    
    # Filter terms based on query and category
    suggestions = []
    common_administrative_terms = get_administrative_terms_autocomplete()
    for term in common_administrative_terms:
        # Apply category filter if specified
        if category and term['category'] != category:
            continue
        
        # Match query prefix if provided
        if query and not term['text'].startswith(query):
            continue
        
        suggestions.append(term)
    
    return Response({
        'query': query,
        'suggestions': suggestions,
        'count': len(suggestions)
    })


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('q', openapi.IN_QUERY, description="Search query", type=openapi.TYPE_STRING, required=True),
        openapi.Parameter('types', openapi.IN_QUERY, description="Comma-separated entity types (organization,signer,unit,company,company_person)", type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('organization_id', openapi.IN_QUERY, description="Filter by organization", type=openapi.TYPE_STRING),
        openapi.Parameter('company_id', openapi.IN_QUERY, description="Filter by company ID", type=openapi.TYPE_INTEGER),
        openapi.Parameter('include_documents', openapi.IN_QUERY, description="Include document search", type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('limit', openapi.IN_QUERY, description="Results limit per type", type=openapi.TYPE_INTEGER),
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def universal_search_api(request):
    """Universal search API that can handle multiple entity types"""
    query = request.GET.get('q', '')
    types_param = request.GET.get('types', 'organization,signer,unit')
    organization_id = request.GET.get('organization_id')
    company_id = request.GET.get('company_id')
    include_documents = request.GET.get('include_documents', 'false').lower() == 'true'
    limit = int(request.GET.get('limit', 20))
    
    # Parse entity types
    entity_types = [t.strip() for t in types_param.split(',') if t.strip()]
    
    return Response(get_search_data_for_api(
        query,
        entity_types=entity_types,
        organization_id=organization_id,
        company_id=int(company_id) if company_id and company_id.isdigit() else None,
        include_documents=include_documents,
        limit=limit
    ))

@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('q', openapi.IN_QUERY, description="Search query", type=openapi.TYPE_STRING, required=True),
        openapi.Parameter('types', openapi.IN_QUERY, description="Comma-separated entity types (organization,signer,unit,company,company_person)", type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('organization_id', openapi.IN_QUERY, description="Filter by organization", type=openapi.TYPE_STRING),
        openapi.Parameter('company_id', openapi.IN_QUERY, description="Filter by company ID", type=openapi.TYPE_INTEGER),
        openapi.Parameter('include_documents', openapi.IN_QUERY, description="Include document search", type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('limit', openapi.IN_QUERY, description="Results limit per type", type=openapi.TYPE_INTEGER),
    ]
)
@api_view(['GET'])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def universal_search_api_dev(request):
    """
        Development version of universal search API
        ['organization', 'signer', 'unit', 'company', 'company_person']
    """
    query = request.GET.get('q', '')
    types_param = request.GET.get('types', 'organization,signer,unit')
    organization_id = request.GET.get('organization_id')
    company_id = request.GET.get('company_id')
    include_documents = request.GET.get('include_documents', 'false').lower() == 'true'
    limit = int(request.GET.get('limit', 20))
    
    entity_types = [t.strip() for t in types_param.split(',') if t.strip()]
    
    return Response(get_search_data_for_api(
        query,
        entity_types=entity_types,
        organization_id=organization_id,
        company_id=int(company_id) if company_id and company_id.isdigit() else None,
        include_documents=include_documents,
        limit=limit
    ))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def org_signer_search_api(request):
    """Search organizations and signers only"""
    query = request.GET.get('q', '')
    organization_id = request.GET.get('organization_id')
    limit = int(request.GET.get('limit', 20))
    
    return Response(get_search_data_for_api(
        query,
        entity_types=['organization', 'signer'],
        organization_id=organization_id,
        limit=limit
    ))



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def org_signer_unit_search_api(request):
    """Search organizations, signers, and units"""
    query = request.GET.get('q', '')
    organization_id = request.GET.get('organization_id')
    limit = int(request.GET.get('limit', 20))
    
    return Response(get_search_data_for_api(
        query,
        entity_types=['organization', 'signer', 'unit'],
        organization_id=organization_id,
        limit=limit
    ))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def organization_only_search_api(request):
    """Search organizations only"""
    query = request.GET.get('q', '')
    limit = int(request.GET.get('limit', 20))
    
    return Response(get_search_data_for_api(
        query,
        entity_types=['organization'],
        limit=limit
    ))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def signer_only_search_api(request):
    """Search signers only"""
    query = request.GET.get('q', '')
    organization_id = request.GET.get('organization_id')
    limit = int(request.GET.get('limit', 20))
    
    return Response(get_search_data_for_api(
        query,
        entity_types=['signer'],
        organization_id=organization_id,
        limit=limit
    ))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def company_only_search_api(request):
    """Search companies only"""
    query = request.GET.get('q', '')
    limit = int(request.GET.get('limit', 20))
    
    return Response(get_search_data_for_api(
        query,
        entity_types=['company'],
        limit=limit
    ))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def company_person_only_search_api(request):
    """Search company persons only"""
    query = request.GET.get('q', '')
    company_id = request.GET.get('company_id')
    limit = int(request.GET.get('limit', 20))
    
    return Response(get_search_data_for_api(
        query,
        entity_types=['company_person'],
        company_id=int(company_id) if company_id and company_id.isdigit() else None,
        limit=limit
    ))


@api_view(['GET'])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def company_and_persons_search_api(request):
    """Search companies and company persons together"""
    query = request.GET.get('q', '')
    company_id = request.GET.get('company_id')
    limit = int(request.GET.get('limit', 20))
    
    return Response(get_search_data_for_api(
        query,
        entity_types=['company', 'company_person'],
        company_id=int(company_id) if company_id and company_id.isdigit() else None,
        limit=limit
    ))


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('q', openapi.IN_QUERY, description="Search query", type=openapi.TYPE_STRING, required=True),
        openapi.Parameter('include_documents', openapi.IN_QUERY, description="Include document search", type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('limit', openapi.IN_QUERY, description="Results limit per type", type=openapi.TYPE_INTEGER),
    ]
)
@api_view(['GET'])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def super_search_api(request):
    """
    Super search API that searches across ALL entity types and documents:
    - Organizations, Units, Signers
    - Companies and Company Persons  
    - Document content (via OpenSearch)
    """
    query = request.GET.get('q', '')
    include_documents = request.GET.get('include_documents', 'true').lower() == 'true'
    limit = int(request.GET.get('limit', 10))
    
    return Response(get_search_data_for_api(
        query,
        entity_types=['organization', 'signer', 'unit', 'company', 'company_person'],
        include_documents=include_documents,
        limit=limit
    ))